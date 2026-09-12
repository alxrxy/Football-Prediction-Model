"""CFBD ingestion — games, SP+/Elo ratings, betting lines, venues.

Independently runnable:  python -m src.ingest_cfbd
Writes raw rows to venues / games / team_ratings / odds.

Free-tier discipline: one call per resource per week. Never loop per team.
"""

from __future__ import annotations

import argparse
import re
from datetime import date, datetime, timezone

from . import config, db
from .http import get_json

FBS = "fbs"


def _headers() -> dict:
    return {"Authorization": f"Bearer {config.require('CFBD_API_KEY')}"}


def _get(path: str, params: dict | None = None, cache_minutes: int = 60):
    return get_json(
        config.CFBD_BASE + path,
        params=params,
        headers=_headers(),
        cache_minutes=cache_minutes,
        cache_tag="cfbd",
    )


# --- week resolution -------------------------------------------------------

def current_week(season: int, on: date | None = None) -> tuple[int, str]:
    """Find the CFBD week containing `on` (default: today, UTC)."""
    on = on or datetime.now(timezone.utc).date()
    calendar = _get("/calendar", {"year": season}, cache_minutes=60 * 24)
    for entry in calendar:
        start = _parse_dt(entry["startDate"]).date()
        end = _parse_dt(entry["endDate"]).date()
        if start <= on <= end:
            return int(entry["week"]), entry.get("seasonType", "regular")
    # Past the last listed week — fall back to the final one.
    last = calendar[-1]
    return int(last["week"]), last.get("seasonType", "regular")


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# --- venues ----------------------------------------------------------------

def ingest_venues(store: db.Store) -> int:
    """One-time-ish pull. Gives lat/long + dome flag for weather and travel."""
    raw = _get("/venues", cache_minutes=60 * 24 * 30)
    rows = []
    for v in raw:
        if v.get("latitude") is None or v.get("longitude") is None:
            continue
        rows.append(
            {
                "venue_id": str(v["id"]),
                "sport": "ncaaf",
                "name": v.get("name"),
                "city": v.get("city"),
                "state": v.get("state"),
                "latitude": float(v["latitude"]),
                "longitude": float(v["longitude"]),
                "elevation_m": _as_float(v.get("elevation")),
                "is_dome": bool(v.get("dome")),
                "capacity": v.get("capacity"),
                "timezone": v.get("timezone"),
            }
        )
    store.upsert("venues", db.stamp(rows))
    return len(rows)


def _as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def ingest_teams(store: db.Store, season: int) -> int:
    """Team identity + home venue coordinates (drives the travel feature)."""
    raw = _get("/teams/fbs", {"year": season}, cache_minutes=60 * 24 * 7)
    rows = []
    for t in raw:
        loc = t.get("location") or {}
        rows.append(
            {
                "team": t["school"],
                "sport": "ncaaf",
                "full_name": t["school"],
                "conference": t.get("conference"),
                "classification": t.get("classification"),
                "abbreviation": t.get("abbreviation"),
                "mascot": t.get("mascot"),
                "color": t.get("color"),
                "home_venue_id": str(loc["id"]) if loc.get("id") else None,
                "home_latitude": _as_float(loc.get("latitude")),
                "home_longitude": _as_float(loc.get("longitude")),
                "home_timezone": loc.get("timezone"),
            }
        )
    store.upsert("teams", db.stamp(rows))
    return len(rows)


# --- games -----------------------------------------------------------------

def ingest_games(store: db.Store, season: int, week: int, season_type: str,
                 cache_minutes: int = 30) -> list[dict]:
    """Pull the week's slate.

    Note: CFBD ignores the `division` param on this endpoint (Division II games
    come back regardless), so FBS filtering happens here, client-side.

    `cache_minutes` is overridable because grading needs fresh final scores,
    where a half-hour-old cached response would report games as still in
    progress.
    """
    raw = _get(
        "/games",
        {"year": season, "week": week, "seasonType": season_type},
        cache_minutes=cache_minutes,
    )
    rows = []
    for g in raw:
        if FBS not in (g.get("homeClassification"), g.get("awayClassification")):
            continue
        rows.append(
            {
                "game_id": str(g["id"]),
                "sport": "ncaaf",
                "season": g["season"],
                "week": g["week"],
                "season_type": g.get("seasonType"),
                "home_team": g["homeTeam"],
                "away_team": g["awayTeam"],
                "home_conference": g.get("homeConference"),
                "away_conference": g.get("awayConference"),
                "kickoff_time": g.get("startDate"),
                "venue": g.get("venue"),
                "venue_id": str(g["venueId"]) if g.get("venueId") else None,
                "is_neutral_site": bool(g.get("neutralSite")),
                "is_conference": bool(g.get("conferenceGame")),
                "home_points": g.get("homePoints"),
                "away_points": g.get("awayPoints"),
                "completed": bool(g.get("completed")),
            }
        )
    store.upsert("games", db.stamp(rows))
    return rows


# --- ratings ---------------------------------------------------------------

def ingest_ratings(store: db.Store, season: int, week: int) -> int:
    """SP+ (season-level) merged with Elo (week-level) into one row per team."""
    merged: dict[str, dict] = {}

    for r in _get("/ratings/sp", {"year": season}, cache_minutes=60 * 6):
        team = r.get("team")
        if not team or team == "nationalAverages":
            continue
        merged[team] = {
            "team": team,
            "sport": "ncaaf",
            "season": season,
            "week": week,
            "conference": r.get("conference"),
            # power_rating is the sport-neutral baseline the model reads.
            # For NCAAF that is SP+ directly, already expressed in points.
            "power_rating": _as_float(r.get("rating")),
            "sp_plus": _as_float(r.get("rating")),
            "sp_plus_off": _as_float((r.get("offense") or {}).get("rating")),
            "sp_plus_def": _as_float((r.get("defense") or {}).get("rating")),
        }

    try:
        elo_raw = _get("/ratings/elo", {"year": season, "week": week}, cache_minutes=60 * 6)
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] Elo pull failed ({exc}); continuing with SP+ only")
        elo_raw = []

    for r in elo_raw:
        team = r.get("team")
        if not team:
            continue
        row = merged.setdefault(
            team,
            {"team": team, "sport": "ncaaf", "season": season, "week": week,
             "conference": r.get("conference")},
        )
        row["elo"] = _as_float(r.get("elo"))

    rows = list(merged.values())
    store.upsert("team_ratings", db.stamp(rows))
    return len(rows)


# --- betting lines ---------------------------------------------------------

_FAV_RE = re.compile(r"^(?P<team>.+?)\s+(?P<num>-?\d+(?:\.\d+)?)$")


def _home_spread(line: dict, home_team: str, away_team: str) -> float | None:
    """Return the market spread from the HOME team's perspective.

    Negative = home favored. Derived from `formattedSpread` ("Oregon -23.5")
    because that string names the favorite explicitly and so can't be flipped
    by a sign-convention change upstream. Falls back to the raw `spread` field.
    """
    formatted = (line.get("formattedSpread") or "").strip()
    match = _FAV_RE.match(formatted)
    if match:
        fav, num = match.group("team").strip(), float(match.group("num"))
        magnitude = -abs(num)  # favorite's line is always negative
        if fav == home_team:
            return magnitude
        if fav == away_team:
            return -magnitude
        if fav.upper() == "EVEN" or num == 0:
            return 0.0
    return _as_float(line.get("spread"))


def ingest_lines(store: db.Store, season: int, week: int, season_type: str) -> int:
    """CFBD lines are free and don't touch the Odds API quota — use them as the
    primary market anchor, with The Odds API as a live refresh on top.
    """
    raw = _get(
        "/lines",
        {"year": season, "week": week, "seasonType": season_type},
        cache_minutes=30,
    )
    rows: list[dict] = []
    disagreements = 0

    for g in raw:
        game_id = str(g["id"])
        home, away = g["homeTeam"], g["awayTeam"]
        spreads, totals, ml_home, ml_away = [], [], [], []

        for line in g.get("lines") or []:
            spread = _home_spread(line, home, away)
            raw_spread = _as_float(line.get("spread"))
            if spread is not None and raw_spread is not None and abs(spread - raw_spread) > 0.01:
                disagreements += 1
            rows.append(
                {
                    "game_id": game_id,
                    "book": f"cfbd:{line.get('provider', 'unknown')}",
                    "spread": spread,
                    "total": _as_float(line.get("overUnder")),
                    "moneyline_home": line.get("homeMoneyline"),
                    "moneyline_away": line.get("awayMoneyline"),
                    "source": "cfbd",
                }
            )
            if spread is not None:
                spreads.append(spread)
            if line.get("overUnder") is not None:
                totals.append(float(line["overUnder"]))
            if line.get("homeMoneyline") is not None:
                ml_home.append(line["homeMoneyline"])
            if line.get("awayMoneyline") is not None:
                ml_away.append(line["awayMoneyline"])

        # Consensus row = median across books. This is what the model compares to.
        if spreads:
            rows.append(
                {
                    "game_id": game_id,
                    "book": "cfbd_consensus",
                    "spread": _median(spreads),
                    "total": _median(totals) if totals else None,
                    "moneyline_home": int(_median(ml_home)) if ml_home else None,
                    "moneyline_away": int(_median(ml_away)) if ml_away else None,
                    "source": "cfbd",
                }
            )

    if disagreements:
        print(
            f"  [note] {disagreements} line(s) where CFBD's raw `spread` sign "
            f"disagreed with formattedSpread; used formattedSpread."
        )
    store.upsert("odds", db.stamp(rows))
    return len(rows)


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    return ordered[mid] if n % 2 else (ordered[mid - 1] + ordered[mid]) / 2


# --- entrypoint ------------------------------------------------------------

def run(season: int | None = None, week: int | None = None,
        lookback: int = 1, lookahead: int = 1) -> dict:
    store = db.get_store()
    season = season or datetime.now(timezone.utc).year
    if week is None:
        week, season_type = current_week(season)
    else:
        season_type = "regular"

    print(f"[cfbd] season {season}, week {week} ({season_type}) -> {store.backend}")
    n_venues = ingest_venues(store)
    print(f"  venues:  {n_venues}")
    n_teams = ingest_teams(store, season)
    print(f"  teams:   {n_teams}")

    # Load a window of weeks, not just the target one:
    #   back  — previous games supply each team's rest days
    #   ahead — the Odds API returns events several days out, and those lines
    #           can't be matched without next week's games loaded
    total_games = 0
    for offset in range(-lookback, lookahead + 1):
        target = week + offset
        if target < 1:
            continue
        games = ingest_games(store, season, target, season_type)
        total_games += len(games)
        label = "games" if offset == 0 else f"  wk{target}"
        print(f"  {label}:{'   ' if offset == 0 else ' '}{len(games)} FBS-involved")

    n_ratings = ingest_ratings(store, season, week)
    print(f"  ratings: {n_ratings} teams")
    n_lines = ingest_lines(store, season, week, season_type)
    print(f"  lines:   {n_lines} rows")

    store.close()
    return {"season": season, "week": week, "season_type": season_type, "games": total_games}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest CFBD data for a week.")
    parser.add_argument("--season", type=int)
    parser.add_argument("--week", type=int)
    args = parser.parse_args()
    run(args.season, args.week)
