"""NFL player-prop lines from The Odds API, for the coming week's games.

    python -m src.ingest_props            # cached for ODDS_CACHE_MINUTES
    python -m src.ingest_props --fresh    # bypass the cache (costs quota)

Props are only served one game at a time (/events/{id}/odds). The event list
is free; each game costs one credit per market per region, so the default
four markets (PROP_MARKETS) across a 16-game week cost 64 credits a pull. The
cache makes re-runs free. Games already under way are skipped: their props
are in-play prices, not pregame lines.

Writes data/props_lines.json, which src/props.py ranks against the
simulations.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from . import config, db
from .http import get_json
from .ingest_odds import SPORT_KEYS, _parse_dt, match_events

PROPS_LINES_JSON = config.DATA_DIR / "props_lines.json"


def week_games(store) -> list[dict]:
    """Unplayed games in the NFL week that contains the next kickoff."""
    now = datetime.now(timezone.utc)
    games = store.select("games", {"sport": "nfl"})
    upcoming = [g for g in games
                if not g.get("completed") and (k := _parse_dt(g.get("kickoff_time"))) and k > now]
    if not upcoming:
        return []
    first = min(upcoming, key=lambda g: _parse_dt(g["kickoff_time"]))
    return [g for g in upcoming
            if g.get("season") == first.get("season") and g.get("week") == first.get("week")]


def parse_event(data: dict, markets: set[str]) -> dict:
    """player -> market -> book -> {point, over, under} from one event's odds."""
    players: dict = {}
    for book in data.get("bookmakers") or []:
        for market in book.get("markets") or []:
            if market.get("key") not in markets:
                continue
            for o in market.get("outcomes") or []:
                who, side = o.get("description"), str(o.get("name") or "").lower()
                if not who or side not in ("over", "under") or o.get("point") is None:
                    continue
                slot = players.setdefault(who, {}).setdefault(market["key"], {}).setdefault(book["key"], {})
                if side == "over" or "point" not in slot:
                    slot["point"] = float(o["point"])
                slot[side] = o.get("price")
    return players


def fetch_alternates(needs: dict[str, set[str]], lines: dict,
                     cache_minutes: int | None = None) -> tuple[dict, str]:
    """Alternate lines for just the (game, market) pairs a ranking needs.

    Requesting only those pairs costs one credit each, about 25 for a top-25
    list, instead of four more per game for every stat. Returns
    ({game_id: {player: {market: [{book, side, point, price}]}}}, pulled_at).
    """
    key = config.require("ODDS_API_KEY")
    cache_minutes = config.ODDS_CACHE_MINUTES if cache_minutes is None else cache_minutes
    base = {"apiKey": key, "oddsFormat": "american"}
    base.update({"bookmakers": config.ODDS_BOOKMAKERS} if config.ODDS_BOOKMAKERS else {"regions": "us"})
    out, live, meta = {}, 0, {}
    for gid, markets in needs.items():
        event_id = ((lines.get("games") or {}).get(gid) or {}).get("event_id")
        if not event_id:
            continue
        meta = {}
        data = get_json(f"{config.ODDS_BASE}/sports/{SPORT_KEYS['nfl']}/events/{event_id}/odds",
                        params={**base, "markets": ",".join(sorted(markets))}, cache_minutes=cache_minutes,
                        cache_tag=f"props_alt_{gid}", capture_meta=meta)
        live += 0 if meta.get("from_cache") else 1
        players: dict = {}
        for book in (data if isinstance(data, dict) else {}).get("bookmakers") or []:
            for market in book.get("markets") or []:
                if market.get("key") not in markets:
                    continue
                for o in market.get("outcomes") or []:
                    side = str(o.get("name") or "").lower()
                    if not o.get("description") or side not in ("over", "under") \
                            or o.get("point") is None or o.get("price") is None:
                        continue
                    players.setdefault(o["description"], {}).setdefault(market["key"], []).append(
                        {"book": book["key"], "side": side, "point": float(o["point"]), "price": int(o["price"])})
        out[gid] = players
    print(f"  alt lines: {len(needs)} game(s), {sum(len(m) for m in needs.values())} market(s), "
          f"{live} live call(s); quota remaining: {meta.get('quota_remaining')}")
    return out, datetime.now(timezone.utc).isoformat()


def run(cache_minutes: int | None = None) -> dict:
    store = db.get_store()
    cache_minutes = config.ODDS_CACHE_MINUTES if cache_minutes is None else cache_minutes
    key = config.require("ODDS_API_KEY")
    sport_key = SPORT_KEYS["nfl"]
    markets = [m.strip() for m in config.PROP_MARKETS.split(",") if m.strip()]

    games = week_games(store)
    if not games:
        print("[props] no upcoming NFL games")
        store.close()
        return {}
    full_names = {t["team"]: (t.get("full_name") or t["team"]) for t in store.select("teams", {"sport": "nfl"})}
    store.close()
    for g in games:
        g["_match_home"] = full_names.get(g["home_team"], g["home_team"])
        g["_match_away"] = full_names.get(g["away_team"], g["away_team"])

    # The event list costs nothing, but cache it briefly anyway.
    events = get_json(f"{config.ODDS_BASE}/sports/{sport_key}/events", params={"apiKey": key},
                      cache_minutes=min(cache_minutes, 60) if cache_minutes else 0, cache_tag="events_nfl")
    matched, name_misses, _ = match_events(events, games)

    params = {"apiKey": key, "markets": ",".join(markets), "oddsFormat": "american"}
    if config.ODDS_BOOKMAKERS:
        params["bookmakers"] = config.ODDS_BOOKMAKERS
    else:
        params["regions"] = "us"

    out = {"pulled_at": datetime.now(timezone.utc).isoformat(), "season": games[0].get("season"),
           "week": games[0].get("week"), "markets": markets, "games": {}}
    meta: dict = {}
    live_calls = 0
    for i, game in matched.items():
        event = events[i]
        meta = {}
        data = get_json(f"{config.ODDS_BASE}/sports/{sport_key}/events/{event['id']}/odds",
                        params=params, cache_minutes=cache_minutes,
                        cache_tag=f"props_{game['game_id']}", capture_meta=meta)
        live_calls += 0 if meta.get("from_cache") else 1
        players = parse_event(data if isinstance(data, dict) else {}, set(markets))
        out["games"][game["game_id"]] = {
            "home": game["home_team"], "away": game["away_team"], "kickoff": game.get("kickoff_time"),
            "event_id": event["id"], "books": len((data or {}).get("bookmakers") or []), "players": players,
        }
        if meta.get("quota_remaining") is not None:
            out["quota_remaining"] = meta["quota_remaining"]

    config.ensure_dirs()
    PROPS_LINES_JSON.write_text(json.dumps(out), encoding="utf-8")
    priced = sum(len(g["players"]) for g in out["games"].values())
    print(f"[props] week {out['week']}: {len(out['games'])}/{len(games)} games, {priced} players priced "
          f"({live_calls} live call(s), rest cached); quota remaining: {out.get('quota_remaining')}")
    if name_misses:
        print(f"  [warn] unmatched events: {', '.join(name_misses[:5])}")
    print(f"  wrote {PROPS_LINES_JSON}")
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pull NFL player-prop lines from The Odds API.")
    parser.add_argument("--fresh", action="store_true", help="bypass the cache (costs quota)")
    args = parser.parse_args()
    run(cache_minutes=0 if args.fresh else None)
