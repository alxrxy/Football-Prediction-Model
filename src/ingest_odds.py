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
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

from . import config, db
from .http import get_json

SPORT_KEYS = {"ncaaf": "americanfootball_ncaaf", "nfl": "americanfootball_nfl"}

# Odds API names carry mascots ("Oklahoma State Cowboys"); CFBD does not.
_NOISE = re.compile(r"[^a-z0-9 ]+")
_APOSTROPHE = re.compile(r"[‘’'`´]")
_MATCH_THRESHOLD = 0.72
_KICKOFF_WINDOW_HOURS = 26

# Confirmed divergences between Odds API and CFBD naming, normalized form.
# Keyed by the Odds API side, valued by the CFBD side.
_ALIASES = {
    "appalachian state": "app state",
    "umass": "massachusetts",
    "fiu": "florida international",
    "southern mississippi": "southern miss",
    "louisiana lafayette": "louisiana",
    "louisiana ragin cajuns": "louisiana",
    "louisiana monroe": "ul monroe",
    "miami fl": "miami",
    "miami florida": "miami",
    "miami oh": "miami oh",
    "miami ohio": "miami oh",
    "connecticut": "uconn",
    "middle tennessee state": "middle tennessee",
    "sam houston state": "sam houston",
    "texas san antonio": "utsa",
    "texas el paso": "utep",
    "nevada las vegas": "unlv",
}


def _norm(name: str) -> str:
    """Casefold, strip diacritics and apostrophes, drop filler words.

    Apostrophes are deleted rather than replaced with a space so CFBD's
    "Hawai'i" collapses to "hawaii" and matches the Odds API spelling.
    """
    name = unicodedata.normalize("NFKD", name or "")
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = _APOSTROPHE.sub("", name.lower())
    name = _NOISE.sub(" ", name)
    name = re.sub(r"\b(university|univ|of|the)\b", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def _similarity(odds_name: str, cfbd_name: str) -> float:
    """Score an Odds API name against a CFBD name.

    The CFBD side is expanded into every Odds-API spelling that aliases to it,
    then each variant is tested as a prefix of the Odds name (which carries a
    mascot the CFBD name lacks).
    """
    a, b = _norm(odds_name), _norm(cfbd_name)
    if not a or not b:
        return 0.0

    variants = {b} | {k for k, v in _ALIASES.items() if v == b}
    best = 0.0
    for variant in variants:
        if a == variant:
            return 1.0
        if a.startswith(variant + " "):
            # Score by how much of the Odds name the CFBD name accounts for.
            # A bare "Texas" covers little of "Texas Tech Red Raiders" and must
            # not outscore the real "Texas Tech" — coverage separates them
            # where a flat prefix bonus does not.
            best = max(best, 0.80 + 0.20 * (len(variant) / len(a)))
        else:
            best = max(best, SequenceMatcher(None, a, variant).ratio())
    return best


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
            home = _similarity(event.get("home_team", ""), game["_match_home"])
            away = _similarity(event.get("away_team", ""), game["_match_away"])
            score = (home + away) / 2
            best_any[i] = max(best_any.get(i, 0.0), score)
            if score >= _MATCH_THRESHOLD:
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


def _extract(bookmaker: dict, odds_home: str, odds_away: str) -> dict:
    """Pull spread/total/moneyline out of one bookmaker's markets.

    Spread is normalized to the home-team line (negative = home favored),
    matching the convention used everywhere else in this project.
    """
    out: dict = {"spread": None, "total": None, "moneyline_home": None, "moneyline_away": None}
    for market in bookmaker.get("markets") or []:
        key = market.get("key")
        for outcome in market.get("outcomes") or []:
            name = outcome.get("name")
            if key == "spreads":
                if name == odds_home:
                    out["spread"] = outcome.get("point")
            elif key == "totals":
                if name == "Over":
                    out["total"] = outcome.get("point")
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
        key = (_norm(event.get("home_team", "")), _norm(event.get("away_team", "")))
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
    events = get_json(
        f"{config.ODDS_BASE}/sports/{sport_key}/odds",
        params={
            "apiKey": config.require("ODDS_API_KEY"),
            "regions": "us",
            "markets": "h2h,spreads,totals",
            "oddsFormat": "american",
        },
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
    matches, name_misses, out_of_slate = match_events(events, games)

    for i, game in matches.items():
        event = events[i]
        odds_home, odds_away = event.get("home_team", ""), event.get("away_team", "")
        spreads, totals, ml_h, ml_a = [], [], [], []

        for bookmaker in event.get("bookmakers") or []:
            vals = _extract(bookmaker, odds_home, odds_away)
            rows.append(
                {
                    "game_id": game["game_id"],
                    "book": f"oddsapi:{bookmaker.get('key')}",
                    "source": "the_odds_api",
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
                    "moneyline_home": int(_median(ml_h)) if ml_h else None,
                    "moneyline_away": int(_median(ml_a)) if ml_a else None,
                    "source": "the_odds_api",
                }
            )

    store.upsert("odds", db.stamp(rows))
    print(f"  matched {len(matches)}/{len(events)} events -> {len(rows)} odds rows")
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
