"""How a game's line has moved since we first tracked it and since the week
reopened (P52). Display only: nothing here feeds a prediction.

`odds_snapshots` keeps every pregame pull per (game, book). Two comparisons
are made against the latest pull:

- **since first tracked**: our first pull, which is not the market's opening
  line. For NFL weeks 3-4 it is a look-ahead line taken before the previous
  week's games, so it includes re-rating on those results.
- **since reopen**: the first pull after both teams' previous games ended
  (the later kickoff + REOPEN_AFTER). Books re-post after each team's own game,
  not after Monday night, so a team that played Sunday reopens Sunday night.
  This is the better proxy for market pressure.

Both ends use only the books priced at both ends, and the move is the change
in their median, so a book joining or leaving the feed never reads as
movement and the from / to / move figures always add up.
"""

from __future__ import annotations

import statistics
from datetime import datetime, timedelta

from .features import parse_dt

REOPEN_AFTER = timedelta(hours=4)
MIN_BOOKS = 2
MIN_MOVE = 0.5
KEY_NUMBERS = (3, 7)
LABEL = ("Line movement, not bet percentages. We have no handle or ticket data; a move can reflect sharp money, "
         "injury or other news, or book risk management.")


def _pulls(rows: list[dict], kickoff: datetime | None) -> list[tuple[datetime, dict[str, dict]]]:
    """[(pull time, {book: row})], oldest first, pregame only."""
    by_t: dict[datetime, dict[str, dict]] = {}
    for r in rows:
        t = parse_dt(r.get("pulled_at"))
        if t is None or (kickoff is not None and t >= kickoff):
            continue
        by_t.setdefault(t, {})[r["book"]] = r
    return sorted(by_t.items())


def _compare(start: dict[str, dict], end: dict[str, dict], field: str) -> dict | None:
    books = sorted(b for b in start.keys() & end.keys()
                   if start[b].get(field) is not None and end[b].get(field) is not None)
    if len(books) < MIN_BOOKS:
        return None
    a = [float(start[b][field]) for b in books]
    z = [float(end[b][field]) for b in books]
    lo, hi = statistics.median(a), statistics.median(z)
    return {"from": lo, "to": hi, "move": hi - lo, "books": len(books)}


def _spread_side(c: dict | None, home: str, away: str) -> dict | None:
    """`spread` is the home-team line: more negative = the market moved toward home."""
    if c is None:
        return None
    m = c["move"]
    c["toward"] = None if abs(m) < MIN_MOVE else (home if m < 0 else away)
    lo, hi = sorted((c["from"], c["to"]))
    c["key_numbers"] = [k for n in KEY_NUMBERS for k in (-n, n) if lo < k < hi]
    return c


def _total_side(c: dict | None) -> dict | None:
    if c is None:
        return None
    m = c["move"]
    c["direction"] = None if abs(m) < MIN_MOVE else ("up" if m > 0 else "down")
    return c


def compute(rows: list[dict], home: str, away: str, kickoff: datetime | None,
            prev_game_kickoff: datetime | None) -> dict | None:
    """The `line_movement` block for one game, or None with fewer than two pulls."""
    # A thin pull (one book priced) can never be compared on 2+ common books,
    # so it is not a candidate for first, reopen or current.
    pulls = [(t, p) for t, p in _pulls(rows, kickoff)
             if sum(r.get("spread") is not None or r.get("total") is not None for r in p.values()) >= MIN_BOOKS]
    if len(pulls) < 2:
        return None
    (t0, first), (tn, current) = pulls[0], pulls[-1]

    reopen_t, reopen = None, None
    if prev_game_kickoff is not None:
        cut = prev_game_kickoff + REOPEN_AFTER
        after = [(t, p) for t, p in pulls if t >= cut]
        if after:
            reopen_t, reopen = after[0]

    def pair(start):
        if start is None:
            return None
        return {"spread": _spread_side(_compare(start, current, "spread"), home, away),
                "total": _total_side(_compare(start, current, "total"))}

    since_first = pair(first)
    # The reopen pull is the first pull or the latest one: nothing separate to show.
    since_reopen = pair(reopen) if reopen_t not in (None, t0, tn) else None
    if since_first and not any(since_first.values()):
        since_first = None
    if since_reopen and not any(since_reopen.values()):
        since_reopen = None
    if since_first is None and since_reopen is None:
        return None
    return {
        "first_at": t0.isoformat(),
        "reopen_at": reopen_t.isoformat() if reopen_t is not None else None,
        "reopen_is_first": reopen_t == t0,
        "current_at": tn.isoformat(),
        "pulls": len(pulls),
        "since_first": since_first,
        "since_reopen": since_reopen,
        "label": LABEL,
    }


def attach(games: list[dict], snapshots: list[dict], all_games: list[dict]) -> None:
    """Set `line_movement` on each exported game dict (in place)."""
    played: dict[str, list[datetime]] = {}
    for g in all_games:
        k = parse_dt(g.get("kickoff_time"))
        if k is None:
            continue
        for team in (g.get("home_team"), g.get("away_team")):
            played.setdefault(team, []).append(k)
    rows_by_game: dict[str, list[dict]] = {}
    for r in snapshots:
        rows_by_game.setdefault(r["game_id"], []).append(r)
    for out in games:
        kickoff = parse_dt(out.get("kickoff"))
        out["line_movement"] = compute(rows_by_game.get(out["game_id"], []), out["home"], out["away"],
                                       kickoff, previous_game(played, out["home"], out["away"], kickoff))


def previous_game(played: dict[str, list[datetime]], home: str, away: str,
                  kickoff: datetime | None) -> datetime | None:
    """The later of the two teams' last kickoffs before this game (None if
    either has no earlier game, e.g. week 1)."""
    if kickoff is None:
        return None
    last = []
    for team in (home, away):
        before = [k for k in played.get(team, []) if k < kickoff]
        if not before:
            return None
        last.append(max(before))
    return max(last)
