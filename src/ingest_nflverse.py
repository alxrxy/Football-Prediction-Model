"""nflverse ingestion — schedules, venues, teams, and NFL power ratings.

    python -m src.ingest_nflverse

No auth; nfl_data_py reads the nflverse GitHub releases.

Layer 1 for the NFL (architecture §5): "compute a simple EPA-based Elo from
nflverse pbp — no need to reinvent SP+, just get points-per-play differential
rolling by week."

So `power_rating` here is a points-per-game figure built from offensive EPA per
play minus defensive EPA per play allowed. A conventional result-based Elo is
computed alongside it as a cross-check and fallback, not as the primary input.

Early-season shrinkage matters more than the rating formula. In week 1 the
current season has ~0 plays, so a raw current-season EPA would be noise or
undefined. Prior-season EPA is therefore carried forward and the current
season is blended in as plays accumulate.
"""

from __future__ import annotations

import argparse
import math
import warnings
from datetime import datetime, timedelta, timezone

from . import db, nfl_venues

warnings.filterwarnings("ignore")

SPORT = "nfl"

# --- rating parameters (priors, not fitted) --------------------------------

PLAYS_PER_GAME = 63.0        # offensive plays per team per game
PRIOR_PLAYS_WEIGHT = 900.0   # how many current-season plays it takes to fully
                             # outweigh the prior season (~2/3 of a season)
PRIOR_SEASON_REGRESSION = 0.75  # shrink prior-season EPA toward league average

ELO_START = 1500.0
ELO_K = 20.0
ELO_HOME_ADVANTAGE = 48.0    # Elo points, ~1.9 scoreboard points
ELO_SEASON_REGRESSION = 1 / 3  # fraction pulled back to the mean each offseason


def _import():
    import nfl_data_py as nfl
    return nfl


# --- teams -----------------------------------------------------------------

def ingest_teams(store: db.Store, schedules) -> int:
    """Team identity plus home coordinates, derived from where they host.

    The home stadium is taken from the schedule rather than hardcoded, so a
    team changing venues needs no code change.
    """
    nfl = _import()
    desc = nfl.import_team_desc()

    home_games = schedules[schedules["location"] == "Home"]
    home_stadium = (
        home_games.groupby("home_team")["stadium"]
        .agg(lambda s: s.value_counts().idxmax() if len(s) else None)
        .to_dict()
    )

    active = set(schedules["home_team"]) | set(schedules["away_team"])
    rows = []
    for _, t in desc.iterrows():
        abbr = t["team_abbr"]
        if abbr not in active:
            continue
        stadium = home_stadium.get(abbr)
        coords = nfl_venues.lookup(stadium)
        rows.append(
            {
                "team": abbr,
                "sport": SPORT,
                "full_name": t.get("team_name"),
                "conference": t.get("team_conf"),
                "classification": t.get("team_division"),
                "abbreviation": abbr,
                "mascot": t.get("team_nick"),
                "color": t.get("team_color"),
                "home_venue_id": stadium,
                "home_latitude": coords[0] if coords else None,
                "home_longitude": coords[1] if coords else None,
                "home_timezone": None,
            }
        )
    store.upsert("teams", db.stamp(rows))
    missing = [r["team"] for r in rows if r["home_latitude"] is None]
    if missing:
        print(f"  [warn] no home coordinates for: {', '.join(missing)}")
    return len(rows)


# --- venues ----------------------------------------------------------------

def ingest_venues(store: db.Store, schedules) -> int:
    rows, unknown = [], []
    for stadium in sorted(set(schedules["stadium"].dropna())):
        coords = nfl_venues.lookup(stadium)
        if coords is None:
            unknown.append(stadium)
            continue
        lat, lon, roof_type = coords
        rows.append(
            {
                "venue_id": stadium,
                "sport": SPORT,
                "name": stadium,
                "latitude": lat,
                "longitude": lon,
                "is_dome": roof_type in ("fixed", "retractable"),
            }
        )
    store.upsert("venues", db.stamp(rows))
    if unknown:
        print(f"  [warn] {len(unknown)} stadium(s) missing from nfl_venues.py: {', '.join(unknown)}")
        print("         those games get no weather and no travel distance until added")
    return len(rows)


# --- games -----------------------------------------------------------------

def ingest_games(store: db.Store, schedules, season: int) -> int:
    """Schedules carry rest days and closing lines, so both are captured here."""
    rows, odds_rows = [], []
    for _, g in schedules.iterrows():
        kickoff = _kickoff(g)
        neutral = str(g.get("location")) == "Neutral"
        rows.append(
            {
                "game_id": str(g["game_id"]),
                "sport": SPORT,
                "season": int(g["season"]),
                "week": int(g["week"]),
                "season_type": "postseason" if str(g.get("game_type")) != "REG" else "regular",
                "home_team": g["home_team"],
                "away_team": g["away_team"],
                "home_conference": None,
                "away_conference": None,
                "kickoff_time": kickoff.isoformat() if kickoff else None,
                "venue": g.get("stadium"),
                "venue_id": g.get("stadium"),
                "is_neutral_site": neutral,
                "is_conference": bool(g.get("div_game")),
                "home_points": _int(g.get("home_score")),
                "away_points": _int(g.get("away_score")),
                "completed": _int(g.get("home_score")) is not None,
                "home_rest_days": _float(g.get("home_rest")),
                "away_rest_days": _float(g.get("away_rest")),
            }
        )

        # nflverse's spread_line is POSITIVE when the home team is favored,
        # the opposite of this project's convention, so it is negated here.
        spread = _float(g.get("spread_line"))
        if spread is not None:
            odds_rows.append(
                {
                    "game_id": str(g["game_id"]),
                    "book": "nflverse_close",
                    "spread": -spread,
                    "total": _float(g.get("total_line")),
                    "moneyline_home": _int(g.get("home_moneyline")),
                    "moneyline_away": _int(g.get("away_moneyline")),
                    "source": "nflverse",
                }
            )

    store.upsert("games", db.stamp(rows))
    store.upsert("odds", db.stamp(odds_rows))
    print(f"  odds:    {len(odds_rows)} nflverse line rows")
    return len(rows)


# nflverse gameday/gametime are US Eastern. Treating that as UTC-4 (EDT) is
# correct for the whole regular season; January playoff games land an hour off,
# which is immaterial for a kickoff-hour weather lookup.
ET_UTC_OFFSET_HOURS = 4


def _kickoff(row):
    day, t = row.get("gameday"), row.get("gametime")
    if not day or str(day) == "nan":
        return None
    try:
        if t and str(t) != "nan":
            hh, mm = str(t).split(":")[:2]
        else:
            hh, mm = "13", "00"
        eastern = datetime.fromisoformat(str(day)).replace(hour=int(hh), minute=int(mm))
    except (ValueError, TypeError):
        return None
    return (eastern + timedelta(hours=ET_UTC_OFFSET_HOURS)).replace(tzinfo=timezone.utc)


def _float(value):
    try:
        f = float(value)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _int(value):
    f = _float(value)
    return int(f) if f is not None else None


# --- ratings ---------------------------------------------------------------

def _epa_by_team(pbp):
    """Offensive and defensive EPA per play, with play counts, per team."""
    plays = pbp[pbp["play_type"].isin(["pass", "run"]) & pbp["posteam"].notna()]
    off = plays.groupby("posteam")["epa"].agg(["mean", "count"])
    deff = plays.groupby("defteam")["epa"].agg(["mean", "count"])
    return off, deff


def compute_ratings(season: int, week: int) -> list[dict]:
    """EPA-based power rating in points, blended across seasons."""
    nfl = _import()
    cols = ["season", "week", "season_type", "posteam", "defteam", "epa", "play_type", "game_id"]

    current = nfl.import_pbp_data([season], columns=cols, downcast=True, cache=False)
    try:
        prior = nfl.import_pbp_data([season - 1], columns=cols, downcast=True, cache=False)
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] prior season pbp unavailable ({exc}); current season only")
        prior = current.iloc[0:0]

    off_c, def_c = _epa_by_team(current)
    off_p, def_p = _epa_by_team(prior)

    teams = sorted(set(off_c.index) | set(off_p.index))
    rows = []
    for team in teams:
        off = _blend(off_c, off_p, team)
        dfn = _blend(def_c, def_p, team)
        if off is None or dfn is None:
            continue
        net_epa = off - dfn
        rows.append(
            {
                "team": team,
                "sport": SPORT,
                "season": season,
                "week": week,
                "power_rating": round(net_epa * PLAYS_PER_GAME, 3),
                "off_epa": round(off, 5),
                "def_epa": round(dfn, 5),
            }
        )

    # Center on the league so power_rating reads as points above average.
    if rows:
        mean = sum(r["power_rating"] for r in rows) / len(rows)
        for r in rows:
            r["power_rating"] = round(r["power_rating"] - mean, 3)

    plays_now = int(off_c["count"].sum()) if len(off_c) else 0
    per_team = plays_now / max(len(teams), 1)
    prior_share = PRIOR_PLAYS_WEIGHT / (PRIOR_PLAYS_WEIGHT + per_team)
    print(
        f"  ratings: {len(rows)} teams | {plays_now} plays in {season} so far "
        f"({per_team:.0f}/team) -> prior season carries "
        f"~{prior_share * 100:.0f}% of each rating"
    )
    return rows


def _blend(current, prior, team):
    """Shrink toward the prior season, weighted by current-season volume."""
    cur_mean = float(current.loc[team, "mean"]) if team in current.index else None
    cur_n = float(current.loc[team, "count"]) if team in current.index else 0.0
    pri_mean = float(prior.loc[team, "mean"]) if team in prior.index else None

    if pri_mean is not None:
        pri_mean *= PRIOR_SEASON_REGRESSION
    if cur_mean is None:
        return pri_mean
    if pri_mean is None:
        return cur_mean
    weight = cur_n / (cur_n + PRIOR_PLAYS_WEIGHT)
    return weight * cur_mean + (1 - weight) * pri_mean


def compute_elo(schedules_all, season: int, week: int) -> dict[str, float]:
    """Conventional margin-aware Elo over completed games.

    Kept as a cross-check on the EPA rating and as the fallback when a team
    has no play-by-play (an expansion team, or a season that failed to load).
    """
    played = schedules_all[schedules_all["home_score"].notna()].sort_values(
        ["season", "week"]
    )
    elo: dict[str, float] = {}
    current_season = None

    for _, g in played.iterrows():
        home, away = g["home_team"], g["away_team"]
        if g["season"] != current_season:
            if current_season is not None:
                for team in elo:
                    elo[team] += (ELO_START - elo[team]) * ELO_SEASON_REGRESSION
            current_season = g["season"]

        h = elo.setdefault(home, ELO_START)
        a = elo.setdefault(away, ELO_START)
        neutral = str(g.get("location")) == "Neutral"
        h_adj = h + (0.0 if neutral else ELO_HOME_ADVANTAGE)

        expected_home = 1.0 / (1.0 + 10 ** (-(h_adj - a) / 400.0))
        margin = float(g["home_score"]) - float(g["away_score"])
        actual = 1.0 if margin > 0 else (0.5 if margin == 0 else 0.0)

        # Margin-of-victory multiplier, damped for blowouts by favorites.
        mov = math.log(abs(margin) + 1.0) * (2.2 / ((h_adj - a) * 0.001 + 2.2))
        shift = ELO_K * mov * (actual - expected_home)
        elo[home] = h + shift
        elo[away] = a - shift

    return elo


def ingest_ratings(store: db.Store, schedules_all, season: int, week: int) -> int:
    rows = compute_ratings(season, week)
    elo = compute_elo(schedules_all, season, week)
    for row in rows:
        row["elo"] = round(elo.get(row["team"], ELO_START), 1)
    store.upsert("team_ratings", db.stamp(rows))
    return len(rows)


# --- entrypoint ------------------------------------------------------------

def current_week(schedules) -> int:
    """First week that still has an unplayed game."""
    pending = schedules[schedules["home_score"].isna()]
    if len(pending):
        return int(pending["week"].min())
    return int(schedules["week"].max())


def run(season: int | None = None) -> dict:
    nfl = _import()
    store = db.get_store()
    season = season or datetime.now(timezone.utc).year

    schedules = nfl.import_schedules([season])
    week = current_week(schedules)
    print(f"[nflverse] season {season}, week {week} -> {store.backend}")

    n_venues = ingest_venues(store, schedules)
    print(f"  venues:  {n_venues}")
    n_teams = ingest_teams(store, schedules)
    print(f"  teams:   {n_teams}")
    n_games = ingest_games(store, schedules, season)
    print(f"  games:   {n_games}")

    # Elo needs history; ratings need the prior season for shrinkage.
    history = nfl.import_schedules([season - 2, season - 1, season])
    n_ratings = ingest_ratings(store, history, season, week)

    store.close()
    return {"season": season, "week": week, "games": n_games, "teams": n_ratings}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest nflverse data.")
    parser.add_argument("--season", type=int)
    args = parser.parse_args()
    run(args.season)
