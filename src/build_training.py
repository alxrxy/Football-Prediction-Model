"""Historical training set for the ML layer (architecture §5, Layer 3).

    python -m src.build_training --sport nfl --start 2015
    python -m src.build_training --sport ncaaf --start 2016

Writes data/training_<sport>.csv.

LOOKAHEAD IS THE WHOLE PROBLEM HERE. The obvious way to build this set is to
join each historical game against CFBD's SP+ ratings, which is also the fastest
way to produce a model that looks excellent and is worthless: SP+ for a season
is computed from that entire season, including the game being predicted. A
model trained on it learns to read the answer.

So no rating used as a feature is allowed to have seen the game it describes.
Every rating here is built walk-forward: games are replayed in chronological
order, each game's features are recorded from the state *before* it is played,
and only then is the result folded into the ratings. That is slower and the
resulting model is weaker — it is also the only version whose backtest means
anything.
"""

from __future__ import annotations

import argparse
import math
import warnings
from datetime import datetime, timezone

from . import config, db
from .ingest_cfbd import _get as cfbd_get
from .features import haversine_miles
from .qb_prior import MIN_STARTS, qb_id

warnings.filterwarnings("ignore")

ELO_START = 1500.0
ELO_K = {"nfl": 20.0, "ncaaf": 24.0}
ELO_HOME_ADV = {"nfl": 48.0, "ncaaf": 60.0}
ELO_SEASON_REGRESSION = {"nfl": 1 / 3, "ncaaf": 0.25}

# How much of a team's offensive/defensive EPA carries into a new season.
EPA_SEASON_CARRY = 0.55
EPA_PRIOR_PLAYS = 400.0  # shrinkage toward league average early in a season
PLAYS_PER_GAME = 63.0


class RollingElo:
    """Walk-forward Elo. Read before a game, updated after it."""

    def __init__(self, sport: str):
        self.sport = sport
        self.rating: dict[str, float] = {}
        self.season: int | None = None

    def start_season(self, season: int) -> None:
        if self.season is not None and season != self.season:
            pull = ELO_SEASON_REGRESSION[self.sport]
            for team in self.rating:
                self.rating[team] += (ELO_START - self.rating[team]) * pull
        self.season = season

    def pre(self, team: str) -> float:
        return self.rating.setdefault(team, ELO_START)

    def update(self, home: str, away: str, margin: float, neutral: bool) -> None:
        h, a = self.pre(home), self.pre(away)
        h_adj = h + (0.0 if neutral else ELO_HOME_ADV[self.sport])
        expected = 1.0 / (1.0 + 10 ** (-(h_adj - a) / 400.0))
        actual = 1.0 if margin > 0 else (0.5 if margin == 0 else 0.0)
        mov = math.log(abs(margin) + 1.0) * (2.2 / ((h_adj - a) * 0.001 + 2.2))
        shift = ELO_K[self.sport] * mov * (actual - expected)
        self.rating[home] = h + shift
        self.rating[away] = a - shift


class RollingEpa:
    """Walk-forward offensive/defensive EPA per play (NFL only).

    Holds running sums so a team's rating at any point reflects only the plays
    it has already run this season, carried partly over from the last one.
    """

    def __init__(self):
        self.off_sum: dict[str, float] = {}
        self.off_n: dict[str, float] = {}
        self.def_sum: dict[str, float] = {}
        self.def_n: dict[str, float] = {}
        self.season: int | None = None
        # team -> [(starting qb, offensive epa sum, plays)] per game, this
        # season and last, for the quarterback-conditional prior (P13).
        self.games: dict[str, list[tuple[str | None, float, float]]] = {}
        self.last_games: dict[str, list[tuple[str | None, float, float]]] = {}
        self.conditioned: set[str] = set()

    def start_season(self, season: int) -> None:
        if self.season is not None and season != self.season:
            for store in (self.off_sum, self.off_n, self.def_sum, self.def_n):
                for team in store:
                    store[team] *= EPA_SEASON_CARRY
            self.last_games, self.games = self.games, {}
            self.conditioned = set()
        self.season = season

    def condition_on_starter(self, team: str, qb: str | None) -> None:
        """At a team's first game of a season, restate the carried share of
        last season's offense at the mean of the games this game's starter
        started for it (src/qb_prior.py). Volume is unchanged, so only the
        carried rating moves, not how fast this season outweighs it."""
        if team in self.conditioned:
            return
        self.conditioned.add(team)
        last = self.last_games.get(team, [])
        mine = [(s, n) for q, s, n in last if qb is not None and q == qb]
        if len(mine) < MIN_STARTS:
            return
        q_n = sum(n for _, n in mine)
        if not q_n:
            return
        last_sum = sum(s for _, s, _ in last)
        last_n = sum(n for _, _, n in last)
        q_mean = sum(s for s, _ in mine) / q_n
        self.off_sum[team] = self.off_sum.get(team, 0.0) + EPA_SEASON_CARRY * (last_n * q_mean - last_sum)

    def rating(self, team: str) -> float:
        """Net EPA per play, shrunk toward 0 when the sample is thin."""
        off_n = self.off_n.get(team, 0.0)
        def_n = self.def_n.get(team, 0.0)
        off = self.off_sum.get(team, 0.0) / off_n if off_n else 0.0
        dfn = self.def_sum.get(team, 0.0) / def_n if def_n else 0.0
        shrink = min(off_n, def_n) / (min(off_n, def_n) + EPA_PRIOR_PLAYS)
        return (off - dfn) * shrink

    def update(self, team: str, epa_sum: float, plays: float, allowed_sum: float, allowed_plays: float,
               qb: str | None = None) -> None:
        self.games.setdefault(team, []).append((qb, epa_sum, plays))
        self.off_sum[team] = self.off_sum.get(team, 0.0) + epa_sum
        self.off_n[team] = self.off_n.get(team, 0.0) + plays
        self.def_sum[team] = self.def_sum.get(team, 0.0) + allowed_sum
        self.def_n[team] = self.def_n.get(team, 0.0) + allowed_plays


# --- NFL -------------------------------------------------------------------

def build_nfl(seasons: list[int], qb_conditional: bool | None = None) -> tuple[list[dict], RollingElo, RollingEpa]:
    import nfl_data_py as nfl
    from .nfl_venues import lookup as venue_lookup

    if qb_conditional is None:
        qb_conditional = config.QB_CONDITIONAL_PRIOR

    schedules = nfl.import_schedules(seasons)
    schedules = schedules[schedules["home_score"].notna()].copy()
    schedules = schedules.sort_values(["season", "week", "gameday"])
    print(f"  {len(schedules)} completed games across {len(seasons)} seasons")

    # Per-game team EPA totals, so ratings can be advanced game by game.
    print("  loading play-by-play (this is the slow part)...")
    cols = ["season", "week", "posteam", "defteam", "epa", "play_type", "game_id"]
    pbp = nfl.import_pbp_data(seasons, columns=cols, downcast=True, cache=False)
    pbp = pbp[pbp["play_type"].isin(["pass", "run"]) & pbp["posteam"].notna()]
    agg = pbp.groupby(["game_id", "posteam"])["epa"].agg(["sum", "count"])
    game_epa: dict[tuple[str, str], tuple[float, float]] = {
        (str(gid), str(team)): (float(r["sum"]), float(r["count"]))
        for (gid, team), r in agg.iterrows()
    }

    injury_by_team_week = _nfl_injury_features(seasons)

    home_coords = _nfl_home_coords(schedules, venue_lookup)
    elo, epa = RollingElo("nfl"), RollingEpa()
    rows = []

    for _, g in schedules.iterrows():
        season, week = int(g["season"]), int(g["week"])
        elo.start_season(season)
        epa.start_season(season)
        home, away = str(g["home_team"]), str(g["away_team"])
        neutral = str(g.get("location")) == "Neutral"
        # The starter is known at kickoff, so conditioning on him is no leak.
        home_starter, away_starter = qb_id(g.get("home_qb_id")), qb_id(g.get("away_qb_id"))
        if qb_conditional:
            epa.condition_on_starter(home, home_starter)
            epa.condition_on_starter(away, away_starter)

        venue = venue_lookup(g.get("stadium"))
        travel_away = _travel(home_coords.get(away), venue)
        travel_home = _travel(home_coords.get(home), venue)

        home_inj, home_qb = injury_by_team_week.get((season, week, home), (0.0, 0.0))
        away_inj, away_qb = injury_by_team_week.get((season, week, away), (0.0, 0.0))

        rows.append(
            {
                "game_id": str(g["game_id"]),
                "sport": "nfl",
                "season": season,
                "week": week,
                "home_team": home,
                "away_team": away,
                "elo_diff": elo.pre(home) - elo.pre(away),
                "epa_diff": (epa.rating(home) - epa.rating(away)) * PLAYS_PER_GAME,
                "rest_diff": _num(g.get("home_rest")) - _num(g.get("away_rest")),
                "travel_away": travel_away or 0.0,
                "travel_diff": (travel_away or 0.0) - (travel_home or 0.0),
                "is_neutral": int(neutral),
                "is_division": int(bool(g.get("div_game"))),
                "is_indoor": int(str(g.get("roof", "")).lower() in ("dome", "closed")),
                # Positive when the away side is the more banged-up team.
                "injury_diff": home_inj - away_inj,
                "qb_loss_diff": away_qb - home_qb,
                "wind": _num(g.get("wind")),
                "temp": _num(g.get("temp"), default=60.0),
                # nflverse spread_line is positive when home is favored; this
                # project's convention is the reverse.
                "market_spread": -_num(g.get("spread_line"), default=float("nan")),
                "market_total": _num(g.get("total_line"), default=float("nan")),
                "target_margin": float(g["home_score"]) - float(g["away_score"]),
            }
        )

        margin = float(g["home_score"]) - float(g["away_score"])
        elo.update(home, away, margin, neutral)
        gid = str(g["game_id"])
        h_sum, h_n = game_epa.get((gid, home), (0.0, 0.0))
        a_sum, a_n = game_epa.get((gid, away), (0.0, 0.0))
        epa.update(home, h_sum, h_n, a_sum, a_n, qb=home_starter)
        epa.update(away, a_sum, a_n, h_sum, h_n, qb=away_starter)

    # The rating objects are returned alongside the rows so live prediction can
    # reuse the exact same end state. Rebuilding ratings by a second, separate
    # code path is how train/serve skew gets in.
    return rows, elo, epa


def _nfl_injury_features(seasons: list[int]) -> dict[tuple[int, int, str], tuple[float, float]]:
    """(season, week, team) -> (injury points, starting-QB availability loss).

    Two lookahead traps here, both easy to miss:

    1. Snap share. A player's season-long snap share includes the games that
       come *after* the one being predicted, so using it would leak. Shares are
       therefore accumulated week by week — only weeks already played count —
       falling back to the prior season, which is entirely in the past.

    2. The injury report itself is published before kickoff, so the report is
       legitimate; it is only the usage weighting attached to it that can leak.

    Scoring uses features.score_injuries, the same function the live pipeline
    calls, so the model is trained on exactly the feature it will be served.
    """
    import bisect

    import nfl_data_py as nfl

    from .features import score_injuries, qb_availability_loss
    from .ingest_injuries import _practice, _status, play_probability, player_key

    try:
        injuries = nfl.import_injuries(seasons)
        snaps = nfl.import_snap_counts(seasons)
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] historical injuries unavailable ({exc}); injury features will be 0")
        return {}

    # --- walk-forward snap share -------------------------------------------
    snaps = snaps.copy()
    snaps["share"] = snaps[["offense_pct", "defense_pct"]].max(axis=1)
    history: dict[tuple, list] = {}
    for row in snaps[["season", "week", "team", "player", "share"]].itertuples(index=False):
        if row.share != row.share:  # NaN
            continue
        key = (int(row.season),) + player_key(row.team, row.player)
        history.setdefault(key, []).append((int(row.week), float(row.share)))

    prefix: dict[tuple, tuple[list, list]] = {}
    season_mean: dict[tuple, float] = {}
    for key, entries in history.items():
        entries.sort()
        weeks, running, total = [], [], 0.0
        for week, share in entries:
            total += share
            weeks.append(week)
            running.append(total)
        prefix[key] = (weeks, running)
        season_mean[key] = total / len(entries)

    def share_before(season: int, week: int, team, player) -> float | None:
        key = (season,) + player_key(team, player)
        weeks, running = prefix.get(key, ([], []))
        idx = bisect.bisect_left(weeks, week)
        if idx > 0:
            return running[idx - 1] / idx
        prior = (season - 1,) + player_key(team, player)
        return season_mean.get(prior)

    # --- score each team-week ----------------------------------------------
    grouped: dict[tuple[int, int, str], list[dict]] = {}
    for row in injuries.itertuples(index=False):
        status = _status(getattr(row, "report_status", None))
        practice = _practice(getattr(row, "practice_status", None))
        if status is None and practice in (None, "full"):
            continue
        season, week, team = int(row.season), int(row.week), str(row.team)
        grouped.setdefault((season, week, team), []).append(
            {
                "player": str(row.full_name),
                "position": str(getattr(row, "position", "") or "").upper(),
                "status": status,
                "practice_trend": practice,
                "play_probability": play_probability(status, practice),
                "snap_share": share_before(season, week, team, row.full_name),
            }
        )

    out = {}
    for key, rows in grouped.items():
        points, _ = score_injuries(rows, "nfl")
        out[key] = (points, qb_availability_loss(rows))
    print(f"  injury reports scored for {len(out)} team-weeks")
    return out


def _nfl_home_coords(schedules, venue_lookup) -> dict[str, tuple]:
    home = schedules[schedules["location"] == "Home"]
    out = {}
    for team, group in home.groupby("home_team"):
        stadium = group["stadium"].value_counts().idxmax()
        coords = venue_lookup(stadium)
        if coords:
            out[str(team)] = coords
    return out


# --- NCAAF -----------------------------------------------------------------

def build_ncaaf(seasons: list[int]) -> tuple[list[dict], RollingElo, RollingEpa]:
    """College has no leak-free rating available off the shelf.

    CFBD publishes SP+ per season, not per week, and a season's SP+ already
    contains every game in it. So college gets a walk-forward Elo built from
    results only — weaker than SP+, but honest.
    """
    store = db.get_store()
    venues = {v["venue_id"]: v for v in store.select("venues")}
    teams = {t["team"]: t for t in store.select("teams", {"sport": "ncaaf"})}
    store.close()

    elo = RollingElo("ncaaf")
    rows = []

    for season in seasons:
        games = cfbd_get("/games", {"year": season, "seasonType": "regular"},
                         cache_minutes=60 * 24 * 30)
        lines_by_game = _cfbd_lines(season)
        games = [g for g in games if g.get("homePoints") is not None]
        games.sort(key=lambda g: (g.get("week") or 0, g.get("startDate") or ""))
        elo.start_season(season)
        print(f"  {season}: {len(games)} completed games")

        for g in games:
            home, away = g.get("homeTeam"), g.get("awayTeam")
            if not home or not away:
                continue
            neutral = bool(g.get("neutralSite"))
            fbs = {g.get("homeClassification"), g.get("awayClassification")}

            venue = venues.get(str(g.get("venueId"))) if g.get("venueId") else None
            venue_pt = (venue["latitude"], venue["longitude"], "") if venue else None
            travel_away = _travel(_team_coords(teams.get(away)), venue_pt)
            travel_home = _travel(_team_coords(teams.get(home)), venue_pt)

            rows.append(
                {
                    "game_id": str(g["id"]),
                    "sport": "ncaaf",
                    "season": season,
                    "week": int(g.get("week") or 0),
                    "home_team": home,
                    "away_team": away,
                    "elo_diff": elo.pre(home) - elo.pre(away),
                    "epa_diff": 0.0,  # no leak-free college EPA available free
                    "rest_diff": 0.0,
                    "travel_away": travel_away or 0.0,
                    "travel_diff": (travel_away or 0.0) - (travel_home or 0.0),
                    "is_neutral": int(neutral),
                    "is_division": int(bool(g.get("conferenceGame"))),
                    "is_indoor": int(bool(venue and venue.get("is_dome"))),
                    # College has no historical injury feed at all, so these
                    # stay constant here and are held at 0 live to match.
                    "injury_diff": 0.0,
                    "qb_loss_diff": 0.0,
                    "wind": float("nan"),
                    "temp": 60.0,
                    "market_spread": lines_by_game.get(str(g["id"]), float("nan")),
                    "market_total": float("nan"),
                    "target_margin": float(g["homePoints"]) - float(g["awayPoints"]),
                    "both_fbs": int(fbs == {"fbs"}),
                }
            )
            elo.update(home, away, float(g["homePoints"]) - float(g["awayPoints"]), neutral)

    return rows, elo, RollingEpa()


def _cfbd_lines(season: int) -> dict[str, float]:
    from .ingest_cfbd import _home_spread, _median

    out: dict[str, float] = {}
    try:
        raw = cfbd_get("/lines", {"year": season, "seasonType": "regular"},
                       cache_minutes=60 * 24 * 30)
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] no lines for {season}: {exc}")
        return out
    for g in raw:
        spreads = [
            s for line in (g.get("lines") or [])
            if (s := _home_spread(line, g["homeTeam"], g["awayTeam"])) is not None
        ]
        if spreads:
            out[str(g["id"])] = _median(spreads)
    return out


def _team_coords(team_row):
    if not team_row or team_row.get("home_latitude") is None:
        return None
    return (team_row["home_latitude"], team_row["home_longitude"], "")


# --- shared ----------------------------------------------------------------

def _travel(origin, venue) -> float | None:
    if not origin or not venue:
        return None
    return haversine_miles(origin[0], origin[1], venue[0], venue[1])


def _num(value, default: float = 0.0) -> float:
    try:
        f = float(value)
        return default if math.isnan(f) else f
    except (TypeError, ValueError):
        return default


FIELDS = [
    "game_id", "sport", "season", "week", "home_team", "away_team",
    "elo_diff", "epa_diff", "rest_diff", "travel_away", "travel_diff",
    "is_neutral", "is_division", "is_indoor", "wind", "temp",
    "injury_diff", "qb_loss_diff",
    "market_spread", "market_total", "target_margin", "both_fbs",
]


def run(sport: str, start: int, end: int | None = None, path=None,
        qb_conditional: bool | None = None) -> str:
    import csv

    end = end or datetime.now(timezone.utc).year
    seasons = list(range(start, end + 1))
    print(f"[training] {sport} {start}-{end}, walk-forward features only")

    rows, _elo, _epa = (build_nfl(seasons, qb_conditional) if sport == "nfl"
                        else build_ncaaf(seasons))
    for row in rows:
        row.setdefault("both_fbs", 1)

    config.ensure_dirs()
    path = path or config.DATA_DIR / f"training_{sport}.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    with_market = sum(1 for r in rows if not math.isnan(r.get("market_spread", float("nan"))))
    print(f"  wrote {len(rows)} rows to {path} ({with_market} with a market line)")
    return str(path)


def replay_state(sport: str, start: int = 2016, end: int | None = None):
    """Replay all history and hand back the final ratings.

    Live prediction needs Elo and EPA in exactly the state the training rows
    were generated from, which means running the same replay rather than
    reimplementing it.
    """
    end = end or datetime.now(timezone.utc).year
    seasons = list(range(start, end + 1))
    _rows, elo, epa = build_nfl(seasons) if sport == "nfl" else build_ncaaf(seasons)
    return elo, epa


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the ML training set.")
    parser.add_argument("--sport", default="nfl", choices=["nfl", "ncaaf"])
    parser.add_argument("--start", type=int, default=2015)
    parser.add_argument("--end", type=int)
    args = parser.parse_args()
    run(args.sport, args.start, args.end)
