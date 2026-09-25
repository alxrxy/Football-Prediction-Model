"""NFL gameday inactives from ESPN (P10).

    python -m src.ingest_inactives                       games in the window this week
    python -m src.ingest_inactives --week 2 --replay     every game that week, finished ones too; nothing stored

Each team's inactive list comes from ESPN's core API, one call per team:
events/{event}/competitions/{event}/competitors/{team}/roster, where an
inactive player has `didNotPlay: true`. (`active` is false even for starters,
so it is ignored.) Before a list is posted the endpoint usually answers 404;
that, or a roster with no one flagged, means "not posted yet" and writes
nothing. Asked well before kickoff it can instead answer 200 with a roster
whose `didNotPlay` flags are stale and look exactly like a real list, so only
games within LOOKAHEAD_HOURS of kickoff are asked at all (P33).

Names in the roster are abbreviated ("K. Allen"), so each inactive's athlete
record is fetched for his full name and matched by team and name with
`player_key`, exactly as the ESPN injury rows are.

Rows go to their own `inactives` table, not `injuries`: that table's key has no
source column, so an ESPN injury re-pull would overwrite an inactive row and the
player would read as active. `first_seen_at` records when a list first appeared;
note it is bounded by when we poll, and since the endpoint serves a
plausible-looking roster early (P33) it cannot witness a true posting time.
`features.apply_inactives` turns the lists into play probabilities.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

import requests

from . import config, db
from .features import parse_dt
from .http import get_json
from .ingest_injuries import BROWSER_UA, _resolve_team, _snap_shares, player_key

CORE = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"
SOURCE = "espn_inactives"
# How long before kickoff to start asking. The NFL deadline is ~90 minutes
# before kickoff, and this endpoint is only trustworthy inside that window
# (P33): asked earlier it answers 200 with a roster carrying stale didNotPlay
# flags, which is indistinguishable from a real list by size. Measured on the
# live 2026-09-20 slate, 93% of the ruled-out players were missing from the 11
# lists read 4.3-8.6 h out, against 39% for the 16 read at T-72m, and a
# re-poll 15 min later returned them byte-identical. Worse than a wrong list:
# features.apply_inactives treats a "posted" team as resolved and promotes its
# unlisted questionable players to a play probability of 1.0.
#
# 2.0 h loses nothing, because run_sunday.py refreshes once per kickoff cluster
# at T-75m: the widest lead any game has at its own window's refresh is 1.58 h
# (a 20:25Z game refreshed at 18:50Z with the 20:05Z kickoffs).
LOOKAHEAD_HOURS = 2.0
ATHLETE_CACHE_MINUTES = 60 * 24 * 30

# ESPN's position id for quarterback, read off each roster entry's position
# $ref (".../positions/8?lang=en"), so validating a list needs no extra calls.
QB_POSITION_ID = "8"


def _position_id(entry: dict) -> str | None:
    ref = (entry.get("position") or {}).get("$ref") or ""
    tail = ref.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
    return tail or None


def impossible_list(entries: list[dict]) -> str | None:
    """Why a posted list cannot be right, or None (P42).

    A team must dress a quarterback, so a roster whose every QB is flagged
    didNotPlay is a feed error, not a gameday decision: on 2026-09-24 ESPN
    flagged all four ATL quarterbacks, Penix started, and the list charged
    ATL 5.6 points for him. When no entry carries a QB position the list
    cannot be judged and passes; this rule only rejects what it can see.
    """
    qbs = [x for x in entries if _position_id(x) == QB_POSITION_ID]
    if qbs and all(x.get("didNotPlay") for x in qbs):
        return f"no active QB ({len(qbs)} on the roster, all flagged inactive)"
    return None


def _get(url: str, params: dict | None = None) -> tuple[int | None, dict | None]:
    """(HTTP status, JSON). A 404 is an answer here (not posted yet), not a failure."""
    try:
        r = requests.get(url, params=params, headers={"User-Agent": BROWSER_UA}, timeout=20)
    except requests.RequestException:
        return None, None
    if r.status_code != 200:
        return r.status_code, None
    try:
        return 200, r.json()
    except ValueError:
        return 200, None


def _athlete(ref: str | None) -> tuple[str | None, str | None]:
    """(full name, position abbreviation) from an athlete $ref. Names don't change, so it is cached."""
    if not ref:
        return None, None
    try:
        a = get_json(ref, headers={"User-Agent": BROWSER_UA}, retries=2, cache_minutes=ATHLETE_CACHE_MINUTES,
                     cache_tag="espn_athlete")
    except Exception:  # noqa: BLE001 - the abbreviated name is the fallback
        return None, None
    return a.get("displayName") or a.get("fullName"), ((a.get("position") or {}).get("abbreviation") or None)


def fetch(store: db.Store, season: int, week: int, now: datetime | None = None,
          include_final: bool = False, shares: dict | None = None) -> tuple[list[dict], list[dict]]:
    """(inactive rows, one status line per game). Nothing is written here."""
    now = now or datetime.now(timezone.utc)
    games = [g for g in store.select("games", {"sport": "nfl"}) if g.get("season") == season and g.get("week") == week]
    by_teams = {(g["home_team"], g["away_team"]): g for g in games}
    known = {(t.get("full_name") or t["team"]): t["team"] for t in store.select("teams", {"sport": "nfl"})}
    status, sb = _get(f"{config.ESPN_NFL}/scoreboard", params={"week": week, "seasontype": 2, "dates": season})
    if not sb:
        print(f"  [warn] ESPN scoreboard unavailable (HTTP {status}); no inactives this run")
        return [], []

    rows, log = [], []
    for event in sb.get("events") or []:
        comp = (event.get("competitions") or [{}])[0]
        state = ((comp.get("status") or {}).get("type") or {}).get("state")
        kickoff = parse_dt(event.get("date"))
        sides = {c.get("homeAway"): (c["team"]["id"], _resolve_team(c["team"].get("displayName") or "", known))
                 for c in comp.get("competitors") or []}
        home, away = sides.get("home", (None, None)), sides.get("away", (None, None))
        game = by_teams.get((home[1], away[1]))
        label = f"{away[1]} @ {home[1]}"
        if game is None:
            log.append({"game": label, "result": "no matching game"})
            continue
        if state == "post" and not include_final:
            log.append({"game": label, "result": "final, skipped"})
            continue
        if not include_final and kickoff and kickoff - now > timedelta(hours=LOOKAHEAD_HOURS):
            log.append({"game": label, "result": "outside window"})
            continue
        for team_id, team in (home, away):
            code, data = _get(f"{CORE}/events/{event['id']}/competitions/{event['id']}/competitors/{team_id}/roster")
            entries = (data or {}).get("entries") or []
            flagged = [x for x in entries if x.get("didNotPlay")]
            if not flagged:
                log.append({"game": label, "team": team, "result": f"not posted (HTTP {code}, {len(entries)} entries)"})
                continue
            reason = impossible_list(entries)
            if reason:
                # Not stored: the team keeps its injury-report probabilities,
                # exactly as if its list had not posted.
                log.append({"game": label, "team": team, "result": f"rejected: {reason}"})
                continue
            for x in flagged:
                name, pos = _athlete((x.get("athlete") or {}).get("$ref"))
                name = name or x.get("displayName")
                rows.append({
                    "game_id": game["game_id"], "team": team, "player": name, "sport": "nfl",
                    "season": season, "week": week, "espn_id": str(x.get("playerId") or ""),
                    "position": pos, "snap_share": (shares or {}).get(player_key(team, name)),
                    "source": SOURCE,
                })
            lead = (kickoff - now).total_seconds() / 3600 if kickoff else None
            log.append({"game": label, "team": team, "result": f"posted: {len(flagged)} inactive",
                        "hours_before_kickoff": None if lead is None else round(lead, 2)})
    return rows, log


def run(season: int | None = None, week: int | None = None, replay: bool = False) -> list[dict]:
    """Fetch this week's posted lists and store them (replay: every game, stored nowhere)."""
    from .ingest_injuries import _infer_week

    store = db.get_store()
    season = season or datetime.now(timezone.utc).year
    week = week or _infer_week(store, "nfl", season)
    try:
        shares = _snap_shares(season)
    except Exception:  # noqa: BLE001 - snap shares only size the injury charge
        shares = {}
    rows, log = fetch(store, season, week, include_final=replay, shares=shares)
    posted = [x for x in log if x["result"].startswith("posted")]
    print(f"[inactives] nfl {season} week {week}: {len(rows)} inactive players, "
          f"{len(posted)} team lists posted" + (" (replay: nothing stored)" if replay else ""))
    for x in log:
        if x["result"].startswith("rejected"):
            print(f"  [reject] {x['game']:<12} {x.get('team', ''):<4} {x['result'][len('rejected: '):]}; "
                  "list not stored, the team stays on its injury report")
        elif x["result"].startswith("posted") or x["result"].startswith("not posted"):
            lead = x.get("hours_before_kickoff")
            print(f"  {x['game']:<12} {x.get('team', ''):<4} {x['result']}"
                  + (f", {lead:+.1f} h to kickoff" if lead is not None and not replay else ""))
    if rows and not replay:
        prior = {(r["game_id"], r["team"], r["player"]): r.get("first_seen_at")
                 for r in db.select_merged(store, "inactives", {"season": season, "week": week})}
        now = db.utcnow()
        for r in rows:
            r["first_seen_at"] = prior.get((r["game_id"], r["team"], r["player"])) or now
        where = db.upsert_or_mirror(store, "inactives", db.stamp(rows))
        print(f"  wrote {len(rows)} rows to inactives ({where})")
    store.close()
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest NFL gameday inactives from ESPN.")
    parser.add_argument("--season", type=int)
    parser.add_argument("--week", type=int)
    parser.add_argument("--replay", action="store_true", help="every game of the week, finished ones too; stores nothing")
    args = parser.parse_args()
    run(args.season, args.week, args.replay)
