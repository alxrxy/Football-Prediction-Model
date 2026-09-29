"""Tests for the line movement display block (src/line_movement.py, P52).

    python -m tests.test_line_movement
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

from src import line_movement as lm

PASS, FAIL = 0, 0


def check(label: str, got, want) -> None:
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got {got!r}, want {want!r}")


T0 = datetime(2026, 9, 16, 6, 0, tzinfo=timezone.utc)
KICK = datetime(2026, 9, 27, 17, 0, tzinfo=timezone.utc)
PREV = datetime(2026, 9, 20, 20, 25, tzinfo=timezone.utc)


def snap(t: datetime, book: str, spread, total=40.0) -> dict:
    return {"game_id": "G", "book": book, "pulled_at": t.isoformat(), "spread": spread, "total": total}


def test_single_pull_is_none():
    rows = [snap(T0, "a", 2.5), snap(T0, "b", 2.0)]
    check("one pull -> None", lm.compute(rows, "WAS", "SEA", KICK, PREV), None)
    check("no rows -> None", lm.compute([], "WAS", "SEA", KICK, PREV), None)


def test_sign_convention():
    """spread is the home line: more negative = toward home."""
    t1 = T0 + timedelta(days=1)
    rows = [snap(T0, "a", 2.5), snap(T0, "b", 2.5), snap(t1, "a", 1.5), snap(t1, "b", 1.5)]
    sp = lm.compute(rows, "WAS", "SEA", KICK, None)["since_first"]["spread"]
    check("home line falls -> toward home", sp["toward"], "WAS")
    check("move -1.0", sp["move"], -1.0)
    rows = [snap(T0, "a", -3.5), snap(T0, "b", -3.5), snap(t1, "a", -2.5), snap(t1, "b", -2.5)]
    check("home favourite shrinks -> toward away",
          lm.compute(rows, "WAS", "SEA", KICK, None)["since_first"]["spread"]["toward"], "SEA")


def test_book_set_change_is_not_movement():
    """A book joining with a different number must not move the line."""
    t1 = T0 + timedelta(days=1)
    rows = [snap(T0, "a", 2.5), snap(T0, "b", 2.5),
            snap(t1, "a", 2.5), snap(t1, "b", 2.5), snap(t1, "c", 7.0), snap(t1, "d", 7.0), snap(t1, "e", 7.0)]
    sp = lm.compute(rows, "WAS", "SEA", KICK, None)["since_first"]["spread"]
    check("same-book move is 0", sp["move"], 0.0)
    check("compared on 2 books", sp["books"], 2)
    check("no direction under 0.5", sp["toward"], None)


def test_min_books():
    t1 = T0 + timedelta(days=1)
    rows = [snap(T0, "a", 2.5), snap(t1, "a", 4.5), snap(t1, "b", 4.5)]
    check("1 common book -> None", lm.compute(rows, "WAS", "SEA", KICK, None), None)


def test_reopen_point():
    before = PREV + timedelta(hours=3)          # still inside the previous game's window
    reopen = PREV + timedelta(days=2)
    last = KICK - timedelta(hours=2)
    rows = [snap(t, b, s) for t, s in ((T0, 2.0), (before, 2.5), (reopen, 7.0), (last, 8.5)) for b in ("a", "b")]
    out = lm.compute(rows, "WAS", "SEA", KICK, PREV)
    check("reopen = first pull >= previous kickoff + 4h", out["reopen_at"], reopen.isoformat())
    check("since reopen 7.0 -> 8.5", (out["since_reopen"]["spread"]["from"], out["since_reopen"]["spread"]["to"]), (7.0, 8.5))
    check("from/to/move add up", out["since_reopen"]["spread"]["move"], 1.5)
    check("since first crosses 3 and 7", out["since_first"]["spread"]["key_numbers"], [3, 7])
    check("toward the away side", out["since_first"]["spread"]["toward"], "SEA")
    # no pull after the cut yet
    out = lm.compute(rows[:4], "WAS", "SEA", KICK, PREV)
    check("no reopen pull -> since_reopen None", (out["reopen_at"], out["since_reopen"]), (None, None))
    # reopen is the first tracked pull: only one comparison
    out = lm.compute(rows[4:], "WAS", "SEA", KICK, PREV)
    check("reopen == first -> flagged, one comparison", (out["reopen_is_first"], out["since_reopen"]), (True, None))


def test_post_kickoff_pulls_ignored():
    t1 = T0 + timedelta(days=1)
    after = KICK + timedelta(minutes=30)
    rows = [snap(T0, "a", 2.5), snap(T0, "b", 2.5), snap(t1, "a", 3.5), snap(t1, "b", 3.5),
            snap(after, "a", 10.5), snap(after, "b", 10.5)]
    check("current is the last pregame pull", lm.compute(rows, "WAS", "SEA", KICK, None)["since_first"]["spread"]["to"], 3.5)


def test_thin_pull_skipped():
    """A latest pull pricing one book must not blank the history before it."""
    t1, t2 = T0 + timedelta(days=1), T0 + timedelta(days=2)
    rows = [snap(T0, "a", 2.5), snap(T0, "b", 2.5), snap(t1, "a", 3.5), snap(t1, "b", 3.5), snap(t2, "a", 9.5)]
    out = lm.compute(rows, "WAS", "SEA", KICK, None)
    check("current is the last pull with 2+ books", out["current_at"], t1.isoformat())
    check("move 2.5 -> 3.5", out["since_first"]["spread"]["move"], 1.0)


def test_previous_game():
    played = {"SEA": [PREV - timedelta(days=7), PREV], "WAS": [PREV - timedelta(hours=3, minutes=25)]}
    check("later of the two teams' last games", lm.previous_game(played, "WAS", "SEA", KICK), PREV)
    check("a team with no earlier game -> None", lm.previous_game({"SEA": [PREV]}, "WAS", "SEA", KICK), None)
    check("games at or after kickoff are ignored",
          lm.previous_game({"SEA": [PREV, KICK], "WAS": [PREV]}, "WAS", "SEA", KICK), PREV)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(name)
            fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
