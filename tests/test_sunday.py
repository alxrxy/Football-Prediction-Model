"""Tests for the Sunday window schedule.

    python -m tests.test_sunday

The windows are read from the day's kickoff times rather than hardcoded, so
the clustering is what decides whether a refresh lands after a team's inactive
list posts and before its game starts. A 20-minute stagger inside the late
slate must stay one window; a three-hour gap must not.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

from run_sunday import LEAD_MINUTES, Window, lists_posted, windows

PASS, FAIL = 0, 0


def check(label: str, got, want) -> None:
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got {got!r}, want {want!r}")


def game(hour, minute=0, away="AAA", home="HHH", day=20):
    return {"game_id": f"2026_03_{away}_{home}_{day}{hour:02d}{minute:02d}",
            "away_team": away, "home_team": home,
            "kickoff_time": f"2026-09-{day:02d}T{hour:02d}:{minute:02d}:00+00:00"}


def shape(ws):
    return [len(w.games) for w in ws]


def test_a_real_sunday():
    """Eight early, five late on a 20-minute stagger, one at night."""
    early = [game(17, 0, away=f"A{i}") for i in range(8)]
    late = [game(20, 5, away=f"B{i}") for i in range(3)] + \
           [game(20, 25, away=f"C{i}") for i in range(2)]
    night = [game(0, 20, away="IND", home="KC", day=21)]
    check("three windows", shape(windows(early + late + night)), [8, 5, 1])


def test_stagger_stays_one_window():
    """20 minutes apart is one slate, not two refreshes."""
    check("17:00 + 17:25", shape(windows([game(17, 0), game(17, 25, away="B")])), [2])


def test_slates_split():
    """Three hours apart is a window of its own."""
    check("17:00 + 20:05", shape(windows([game(17, 0), game(20, 5, away="B")])), [1, 1])


def test_london_morning_schedules_itself():
    """A 09:30 ET kickoff is its own window, with no special case for it."""
    ws = windows([game(13, 30, away="MIN", home="CLE"), game(17, 0, away="B"), game(20, 5, away="C")])
    check("London + early + late", shape(ws), [1, 1, 1])


def test_trigger_leads_the_earliest_kickoff():
    """The refresh time comes off the first kickoff in the window, not the last."""
    ws = windows([game(20, 5), game(20, 25, away="B")])
    want = datetime(2026, 9, 20, 20, 5, tzinfo=timezone.utc) - timedelta(minutes=LEAD_MINUTES)
    check("one window", len(ws), 1)
    check("trigger off the earliest", ws[0].trigger, want)
    check("trigger is before kickoff", ws[0].trigger < ws[0].kickoff, True)


def test_no_games_no_windows():
    check("empty slate", windows([]), [])


def test_missing_kickoff_is_skipped():
    """A game with no kickoff time cannot be scheduled around."""
    rows = [game(17, 0), {"game_id": "x", "kickoff_time": None, "away_team": "A", "home_team": "H"}]
    check("unschedulable game dropped", shape(windows(rows)), [1])


class FakeStore:
    """Enough of a store for lists_posted: sqlite skips the mirror merge."""

    backend = "sqlite"

    def __init__(self, rows):
        self.rows = rows

    def select(self, table, where=None):
        ids = (where or {}).get("game_id") or []
        return [r for r in self.rows if r["game_id"] in ids]


def test_lists_posted_counts_teams_not_rows():
    """Eight inactive players on one list is one team posted, not eight."""
    g = game(17, 0, away="PIT", home="NE")
    w = Window(datetime(2026, 9, 20, 17, 0, tzinfo=timezone.utc), [g])
    rows = [{"game_id": g["game_id"], "team": "NE", "player": f"P{i}"} for i in range(8)]
    check("one team posted", lists_posted(FakeStore(rows), w), (1, 2))
    rows += [{"game_id": g["game_id"], "team": "PIT", "player": "Q"}]
    check("both teams posted", lists_posted(FakeStore(rows), w), (2, 2))
    check("nothing posted", lists_posted(FakeStore([]), w), (0, 2))


def test_lists_posted_ignores_other_games():
    """A list from the early window does not count towards the late one."""
    mine, other = game(20, 5, away="LV", home="LAC"), game(17, 0, away="PIT", home="NE")
    w = Window(datetime(2026, 9, 20, 20, 5, tzinfo=timezone.utc), [mine])
    rows = [{"game_id": other["game_id"], "team": "NE", "player": "P"}]
    check("other window's list ignored", lists_posted(FakeStore(rows), w), (0, 2))


def test_no_failures():
    """Keeps pytest honest: check() only counts, so a mismatch must fail here."""
    assert FAIL == 0, f"{FAIL} check(s) failed; see the printed output"


if __name__ == "__main__":
    for fn in [
        test_a_real_sunday,
        test_stagger_stays_one_window,
        test_slates_split,
        test_london_morning_schedules_itself,
        test_trigger_leads_the_earliest_kickoff,
        test_no_games_no_windows,
        test_missing_kickoff_is_skipped,
        test_lists_posted_counts_teams_not_rows,
        test_lists_posted_ignores_other_games,
    ]:
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
