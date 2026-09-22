"""The Odds API ingestion.

Quota discipline (architecture §9): ~500 requests/month shared across NFL and
NCAAF. That means exactly ONE request per sport per run, disk-cached for
ODDS_CACHE_MINUTES so repeated runs while debugging cost nothing. Remaining
quota is printed every run.

CFBD lines already give a free market anchor; this layer adds live named-book
prices on top and is the only market source NFL will have in step 5.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from . import config, db, market
from .http import get_json
from .names import MATCH_THRESHOLD, norm, similarity

_KICKOFF_WINDOW_HOURS = 26

SPORT_KEYS = {"ncaaf": "americanfootball_ncaaf", "nfl": "americanfootball_nfl"}

def _parse_dt(value):
    if not value:
        return None
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def match_events(events: list[dict], games: list[dict]) -> tuple[dict, list, list]:
    """Match Odds API events to CFBD games by global assignment.

    Every (event, game) pair inside the kickoff window is scored, then pairs
    are claimed best-first across the whole slate. Assigning globally rather
    than per-event stops an early event from stealing a game that a later
    event matches far better.

    Returns (event_index -> game, name_misses, out_of_slate).
    """
    pairs: list[tuple[float, int, int]] = []
    candidates_for: dict[int, int] = {i: 0 for i in range(len(events))}
    best_any: dict[int, float] = {}

    for i, event in enumerate(events):
        commence = _parse_dt(event.get("commence_time"))
        for j, game in enumerate(games):
            kickoff = _parse_dt(game.get("kickoff_time"))
            if commence and kickoff:
                if abs((commence - kickoff).total_seconds()) > _KICKOFF_WINDOW_HOURS * 3600:
                    continue
            candidates_for[i] += 1
            home = similarity(event.get("home_team", ""), game["_match_home"])
            away = similarity(event.get("away_team", ""), game["_match_away"])
            score = (home + away) / 2
            best_any[i] = max(best_any.get(i, 0.0), score)
            if score >= MATCH_THRESHOLD:
                pairs.append((score, i, j))

    pairs.sort(reverse=True)
    matched: dict[int, dict] = {}
    used_games: set[int] = set()

    for score, i, j in pairs:
        if i in matched or j in used_games:
            continue
        matched[i] = games[j]
        used_games.add(j)

    name_misses, out_of_slate = [], []
    for i, event in enumerate(events):
        if i in matched:
            continue
        label = f"{event.get('away_team')} @ {event.get('home_team')}"
        if candidates_for[i] == 0:
            out_of_slate.append(label)
        else:
            name_misses.append(f"{label} (best {best_any.get(i, 0.0):.2f})")

    return matched, name_misses, out_of_slate


ODDS_COLUMNS = ("spread", "total", "moneyline_home", "moneyline_away")


def _extract(bookmaker: dict, odds_home: str, odds_away: str) -> dict:
    """Pull spread/total/moneyline, and the price on each side, out of one
    bookmaker's markets.

    Spread is normalized to the home-team line (negative = home favored),
    matching the convention used everywhere else in this project. The prices
    go to odds_snapshots only: devigging needs both sides' prices, and a
    -105/-115 spread is not the 50/50 a bare line implies.
    """
    out: dict = {"spread": None, "total": None, "moneyline_home": None, "moneyline_away": None,
                 "spread_price_home": None, "spread_price_away": None,
                 "over_price": None, "under_price": None}
    for market in bookmaker.get("markets") or []:
        key = market.get("key")
        for outcome in market.get("outcomes") or []:
            name = outcome.get("name")
            if key == "spreads":
                if name == odds_home:
                    out["spread"] = outcome.get("point")
                    out["spread_price_home"] = outcome.get("price")
                elif name == odds_away:
                    out["spread_price_away"] = outcome.get("price")
            elif key == "totals":
                if name == "Over":
                    out["total"] = outcome.get("point")
                    out["over_price"] = outcome.get("price")
                elif name == "Under":
                    out["under_price"] = outcome.get("price")
            elif key == "h2h":
                if name == odds_home:
                    out["moneyline_home"] = outcome.get("price")
                elif name == odds_away:
                    out["moneyline_away"] = outcome.get("price")
    return out


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    return ordered[mid] if n % 2 else (ordered[mid - 1] + ordered[mid]) / 2


def _dedupe(events: list[dict]) -> list[dict]:
    """Collapse repeat listings of the same fixture.

    The feed sometimes carries one matchup twice under different event ids and
    disagreeing commence_times (one stale). Two teams only meet once in a
    season, so the normalized (home, away) pair identifies the fixture. The
    copies are merged rather than dropped so no book's prices are lost, and
    the kickoff time is taken from the copy quoting the most books.
    """
    merged: dict[tuple, dict] = {}
    for event in events:
        key = (norm(event.get("home_team", "")), norm(event.get("away_team", "")))
        incumbent = merged.get(key)
        if incumbent is None:
            merged[key] = dict(event)
            continue
        books = {b.get("key"): b for b in incumbent.get("bookmakers") or []}
        for book in event.get("bookmakers") or []:
            existing = books.get(book.get("key"))
            if existing is None or (book.get("last_update") or "") > (existing.get("last_update") or ""):
                books[book.get("key")] = book
        if len(event.get("bookmakers") or []) > len(incumbent.get("bookmakers") or []):
            incumbent["commence_time"] = event.get("commence_time")
        incumbent["bookmakers"] = list(books.values())
    return list(merged.values())


def run(sport: str = "ncaaf", cache_minutes: int | None = None) -> int:
    store = db.get_store()
    sport_key = SPORT_KEYS[sport]
    cache_minutes = config.ODDS_CACHE_MINUTES if cache_minutes is None else cache_minutes

    meta: dict = {}
    params = {
        "apiKey": config.require("ODDS_API_KEY"),
        "markets": "h2h,spreads,totals",
        "oddsFormat": "american",
    }
    # A named list of up to 10 books costs the same as one region, which is
    # how a sharp anchor (pinnacle) gets in alongside the US books.
    if config.ODDS_BOOKMAKERS:
        params["bookmakers"] = config.ODDS_BOOKMAKERS
    else:
        params["regions"] = "us"
    events = get_json(
        f"{config.ODDS_BASE}/sports/{sport_key}/odds",
        params=params,
        cache_minutes=cache_minutes,
        cache_tag=f"odds_{sport}",
        capture_meta=meta,
    )

    remaining = meta.get("quota_remaining")
    source = "cache" if meta.get("from_cache") else "live"
    raw_count = len(events)
    events = _dedupe(events)
    dupes = raw_count - len(events)
    print(
        f"[odds] {sport}: {len(events)} events ({source}); quota remaining: {remaining}"
        + (f"; dropped {dupes} duplicate event(s) from upstream" if dupes else "")
    )

    # Only try to match games that are actually upcoming.
    now = datetime.now(timezone.utc)
    games = [
        g
        for g in store.select("games", {"sport": sport})
        if (_parse_dt(g.get("kickoff_time")) or now) > now - timedelta(days=1)
    ]

    # The Odds API always names teams in full ("Kansas City Chiefs"), but the
    # games table stores whatever the ingest source uses — school names for
    # CFBD, bare abbreviations ("KC") for nflverse. Resolve each side to its
    # full name for matching only; the stored rows keep the canonical key.
    full_names = {
        t["team"]: (t.get("full_name") or t["team"])
        for t in store.select("teams", {"sport": sport})
    }
    for game in games:
        game["_match_home"] = full_names.get(game["home_team"], game["home_team"])
        game["_match_away"] = full_names.get(game["away_team"], game["away_team"])

    rows: list[dict] = []
    snapshots: list[dict] = []
    in_play = 0
    matches, name_misses, out_of_slate = match_events(events, games)

    for i, game in matches.items():
        event = events[i]
        # The feed also carries in-play prices for games under way. Storing
        # them overwrote the pregame line with a live one (19 college
        # consensus rows on 09-12 were pulled after kickoff), so a game that
        # has started keeps its last pregame line, which is its closing line.
        commence = _parse_dt(event.get("commence_time")) or _parse_dt(game.get("kickoff_time"))
        if commence is not None and commence <= now:
            in_play += 1
            continue
        odds_home, odds_away = event.get("home_team", ""), event.get("away_team", "")
        spreads, totals, ml_h, ml_a = [], [], [], []

        for bookmaker in event.get("bookmakers") or []:
            vals = _extract(bookmaker, odds_home, odds_away)
            book = f"oddsapi:{bookmaker.get('key')}"
            rows.append(
                {
                    "game_id": game["game_id"],
                    "book": book,
                    "source": "the_odds_api",
                    **{k: vals[k] for k in ODDS_COLUMNS},
                }
            )
            snapshots.append(
                {
                    "game_id": game["game_id"],
                    "book": book,
                    "source": "the_odds_api",
                    "commence_time": event.get("commence_time"),
                    **vals,
                }
            )
            if vals["spread"] is not None:
                spreads.append(float(vals["spread"]))
            if vals["total"] is not None:
                totals.append(float(vals["total"]))
            if vals["moneyline_home"] is not None:
                ml_h.append(vals["moneyline_home"])
            if vals["moneyline_away"] is not None:
                ml_a.append(vals["moneyline_away"])

        if spreads:
            rows.append(
                {
                    "game_id": game["game_id"],
                    "book": "oddsapi_consensus",
                    "spread": _median(spreads),
                    "total": _median(totals) if totals else None,
                    "moneyline_home": market.median_price(ml_h),
                    "moneyline_away": market.median_price(ml_a),
                    "source": "the_odds_api",
                }
            )

    store.upsert("odds", db.stamp(rows))
    where = db.upsert_or_mirror(store, "odds_snapshots", db.stamp(snapshots))
    print(f"  matched {len(matches)}/{len(events)} events -> {len(rows)} odds rows, "
          f"{len(snapshots)} priced snapshots ({where})")
    if in_play:
        print(f"  [info] {in_play} game(s) already under way: kept their pregame line")
    if out_of_slate:
        print(f"  [info] {len(out_of_slate)} event(s) outside the loaded slate (later week / not ingested)")
    if name_misses:
        print(f"  [warn] {len(name_misses)} event(s) had candidates but no name match:")
        for line in name_misses[:8]:
            print(f"    - {line}")
        if len(name_misses) > 8:
            print(f"    ... and {len(name_misses) - 8} more")
    store.close()
    return len(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest lines from The Odds API.")
    parser.add_argument("--sport", default="ncaaf", choices=list(SPORT_KEYS))
    parser.add_argument("--fresh", action="store_true", help="bypass cache (costs quota)")
    args = parser.parse_args()
    run(args.sport, cache_minutes=0 if args.fresh else None)
