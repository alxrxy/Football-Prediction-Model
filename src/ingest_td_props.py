"""NFL anytime-touchdown lines from The Odds API, for the coming week's games.

    python -m src.ingest_td_props                          # every game, cached
    python -m src.ingest_td_props --games CIN_HOU,CAR_ATL  # just these games
    python -m src.ingest_td_props --fresh                  # bypass the cache

Kept apart from src/ingest_props.py on purpose: its own market, its own file
(data/td_props_lines.json), its own ranking (src/td_props.py). Nothing here
touches props_lines.json or the yardage ranking.

One market, so each game costs one credit a pull. Books quote the market as a
Yes/No pair or, more often, Yes only; both are kept per book, and some books
use Over/Under 0.5 for the same thing, which is read as Yes/No.

A later pull for a subset of games carries the other games forward from the
previous file, so a sample pull never wipes a full one.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from . import config, db
from .http import get_json
from .ingest_odds import SPORT_KEYS, match_events
from .ingest_props import week_games

TD_LINES_JSON = config.DATA_DIR / "td_props_lines.json"
TD_MARKET = "player_anytime_td"

_YES = {"yes", "over"}
_NO = {"no", "under"}


def parse_event(data: dict) -> dict:
    """player -> book -> {yes, no} American prices from one event's odds."""
    players: dict = {}
    for book in data.get("bookmakers") or []:
        for market in book.get("markets") or []:
            if market.get("key") != TD_MARKET:
                continue
            for o in market.get("outcomes") or []:
                name = str(o.get("name") or "").lower()
                # Some books name the player in `name` and the side in `description`.
                who, side = o.get("description"), name
                if side not in _YES | _NO:
                    who, side = o.get("name"), str(o.get("description") or "").lower()
                if not who or side not in _YES | _NO or o.get("price") is None:
                    continue
                # Over/Under at anything but 0.5 is a 2+ TD market, not anytime.
                if o.get("point") is not None and float(o["point"]) != 0.5:
                    continue
                slot = players.setdefault(who, {}).setdefault(book["key"], {})
                slot["yes" if side in _YES else "no"] = int(o["price"])
    return players


def run(cache_minutes: int | None = None, only: set[str] | None = None) -> dict:
    store = db.get_store()
    cache_minutes = config.ODDS_CACHE_MINUTES if cache_minutes is None else cache_minutes
    key = config.require("ODDS_API_KEY")
    sport_key = SPORT_KEYS["nfl"]

    games = week_games(store)
    if not games:
        print("[td-props] no upcoming NFL games")
        store.close()
        return {}
    full_names = {t["team"]: (t.get("full_name") or t["team"]) for t in store.select("teams", {"sport": "nfl"})}
    store.close()
    for g in games:
        g["_match_home"] = full_names.get(g["home_team"], g["home_team"])
        g["_match_away"] = full_names.get(g["away_team"], g["away_team"])

    events = get_json(f"{config.ODDS_BASE}/sports/{sport_key}/events", params={"apiKey": key},
                      cache_minutes=min(cache_minutes, 60) if cache_minutes else 0, cache_tag="events_nfl")
    matched, name_misses, _ = match_events(events, games)

    params = {"apiKey": key, "markets": TD_MARKET, "oddsFormat": "american"}
    if config.ODDS_BOOKMAKERS:
        params["bookmakers"] = config.ODDS_BOOKMAKERS
    else:
        params["regions"] = "us"

    prev: dict = {}
    if TD_LINES_JSON.exists():
        try:
            prev = json.loads(TD_LINES_JSON.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            prev = {}
    # Carry games forward only from the same week.
    prev_games = (prev.get("games") or {}) if prev.get("week") == games[0].get("week") else {}

    now = datetime.now(timezone.utc).isoformat()
    out = {"pulled_at": now, "season": games[0].get("season"), "week": games[0].get("week"),
           "market": TD_MARKET, "games": {}}
    meta: dict = {}
    live_calls = carried = 0
    for i, game in matched.items():
        gid = game["game_id"]
        if only and gid[8:] not in only and gid not in only:
            if gid in prev_games:
                out["games"][gid] = prev_games[gid]
                carried += 1
            continue
        event = events[i]
        meta = {}
        data = get_json(f"{config.ODDS_BASE}/sports/{sport_key}/events/{event['id']}/odds",
                        params=params, cache_minutes=cache_minutes,
                        cache_tag=f"td_props_{gid}", capture_meta=meta)
        live_calls += 0 if meta.get("from_cache") else 1
        data = data if isinstance(data, dict) else {}
        out["games"][gid] = {
            "home": game["home_team"], "away": game["away_team"], "kickoff": game.get("kickoff_time"),
            "event_id": event["id"], "books": len(data.get("bookmakers") or []),
            "players": parse_event(data), "pulled_at": now,
        }
        if meta.get("quota_remaining") is not None:
            out["quota_remaining"] = meta["quota_remaining"]
    if "quota_remaining" not in out and prev.get("quota_remaining") is not None:
        out["quota_remaining"] = prev["quota_remaining"]

    config.ensure_dirs()
    TD_LINES_JSON.write_text(json.dumps(out), encoding="utf-8")
    priced = sum(len(g["players"]) for g in out["games"].values())
    empty = sorted(g[8:] for g, v in out["games"].items() if not v.get("players"))
    print(f"[td-props] week {out['week']}: {len(out['games'])}/{len(games)} games, {priced} players priced "
          f"({live_calls} live call(s), {carried} carried forward); "
          f"quota remaining: {out.get('quota_remaining')}")
    if empty:
        print(f"  no anytime-TD market yet for: {', '.join(empty)}")
    if name_misses:
        print(f"  [warn] unmatched events: {', '.join(name_misses[:5])}")
    print(f"  wrote {TD_LINES_JSON}")
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pull NFL anytime-TD lines from The Odds API.")
    parser.add_argument("--fresh", action="store_true", help="bypass the cache (costs quota)")
    parser.add_argument("--games", default="",
                        help="comma-separated games to pull, e.g. CIN_HOU,CAR_ATL (default: all, 1 credit each)")
    args = parser.parse_args()
    only = {g.strip().upper() for g in args.games.split(",") if g.strip()} or None
    run(cache_minutes=0 if args.fresh else None, only=only)
