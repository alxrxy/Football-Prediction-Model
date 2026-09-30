"""P53 safety net: paged reads are checked against the server's count, and
each sim's starting QB is cross-checked against a second injury read and the
books.

    python -m tests.test_p53
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pandas as pd

from src import db
from src.db import IncompleteRead, SupabaseStore
from src.simulate_nfl import QbCheck, qb_warnings
from src.ingest_injuries import player_key

PASS, FAIL = 0, 0


def check(label: str, got, want) -> None:
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got {got!r}, want {want!r}")


class FakeTable:
    """Serves one scripted read per attempt: attempts[i] is the list of pages."""

    def __init__(self, attempts, count):
        self.attempts, self.count, self.count_calls, self.page_calls = attempts, count, 0, 0
        self.attempt = 0
        self.page_orders = []

    def table(self, _name):
        return self

    def select(self, _cols, count=None, head=False):
        self._is_count = count == "exact" and head
        self._order = []
        return self

    def order(self, col):
        self._order.append(col)
        return self

    def eq(self, *_a):
        return self

    in_ = eq

    def range(self, lo, _hi):
        self._lo = lo
        return self

    def execute(self):
        if self._is_count:
            self.count_calls += 1
            self.attempt += 1          # a count closes one attempt
            return SimpleNamespace(data=[], count=self.count)
        pages = self.attempts[min(self.attempt, len(self.attempts) - 1)]
        i = self._lo // 2
        self.page_calls += 1
        self.page_orders.append(list(self._order))
        return SimpleNamespace(data=pages[i] if i < len(pages) else [], count=None)


def store(fake) -> SupabaseStore:
    s = object.__new__(SupabaseStore)
    s.client, s.PAGE_SIZE = fake, 2
    return s


def row(p):
    return {"player": p, "team": "WAS", "sport": "nfl", "season": 2026, "week": 3}


A, B, C = row("A"), row("B"), row("C")


def test_complete_multipage_read():
    fake = FakeTable([[[A, B], [C]]], count=3)
    check("complete 2-page read returned", len(store(fake).select("injuries")), 3)
    check("one count call", fake.count_calls, 1)


def test_every_page_ordered_by_primary_key():
    """Root-cause fix (R1): each OFFSET page is sorted by the table's full key."""
    fake = FakeTable([[[A, B], [C]]], count=3)
    store(fake).select("injuries")
    check("two page requests", len(fake.page_orders), 2)
    check("every page sorted by the full primary key",
          all(o == db.TABLE_KEYS["injuries"] for o in fake.page_orders), True)


def test_single_page_makes_no_count_call():
    fake = FakeTable([[[A]]], count=1)
    store(fake).select("injuries")
    check("no count call on one page", fake.count_calls, 0)


def test_overlap_retried_then_complete():
    """First attempt repeats B (4 rows against a count of 3); the retry is clean."""
    fake = FakeTable([[[A, B], [B, C]], [[A, B], [C]]], count=3)
    got = store(fake).select("injuries")
    check("retry returns the complete read", sorted(r["player"] for r in got), ["A", "B", "C"])
    check("two attempts", fake.count_calls, 2)


def test_overlap_same_length_caught():
    """The dangerous case: a repeated row hides a skipped one, so the length matches."""
    fake = FakeTable([[[A, B], [B]]] * 3, count=3)
    try:
        store(fake).select("injuries")
        check("raises on a persistent overlap", False, True)
    except IncompleteRead:
        check("raises on a persistent overlap", True, True)
    check("three attempts before raising", fake.count_calls, 3)


def test_short_read_caught():
    fake = FakeTable([[[A, B], [C]]] * 3, count=4)
    try:
        store(fake).select("injuries")
        check("short read raises", False, True)
    except IncompleteRead:
        check("short read raises", True, True)


def test_select_merged_does_not_hide_it():
    fake = FakeTable([[[A, B], [B]]] * 3, count=3)
    s = store(fake)
    s.backend = "supabase"
    db._MIRRORED.discard("injuries")
    try:
        db.select_merged(s, "injuries")
        check("select_merged re-raises", False, True)
    except IncompleteRead:
        check("select_merged re-raises", True, True)
    check("table not marked as mirrored", "injuries" in db._MIRRORED, False)


GAME = {"game_id": "2026_04_IND_WAS", "home_team": "WAS", "away_team": "IND", "season": 2026, "week": 4}


def squads(was_qbs=("Jayden Daniels", "Marcus Mariota")):
    was = pd.DataFrame({"player": list(was_qbs), "position": ["QB"] * len(was_qbs)})
    ind = pd.DataFrame({"player": ["Daniel Jones"], "position": ["QB"]})
    return {"WAS": (was, {}, []), "IND": (ind, {}, [])}


def pools(was_starter="Jayden Daniels"):
    was = SimpleNamespace(names=["Jayden Daniels", "Marcus Mariota"],
                          passer_weights=[1.0, 0.0] if was_starter == "Jayden Daniels" else [0.0, 1.0])
    ind = SimpleNamespace(names=["Daniel Jones"], passer_weights=[1.0])
    return (was, ind)


def books(week=4):
    return {"2026_04_IND_WAS": {"season": 2026, "week": week,
                                "pass": {"Marcus Mariota", "Daniel Jones"}, "td": set()}}


def test_was_case_warns():
    report = {player_key("WAS", "Jayden Daniels"): {"status": "out", "play_probability": 0}}
    w = qb_warnings(GAME, squads(), pools("Jayden Daniels"), QbCheck(report, books()))
    check("two warnings for the 9/29 WAS case", len(w), 2)
    check("names the second read", any("second injury read" in x for x in w), True)
    check("names the books' QB", any("Marcus Mariota" in x for x in w), True)


def test_clean_case_silent():
    report = {player_key("WAS", "Jayden Daniels"): {"status": "out", "play_probability": 0}}
    check("correct starter: no warning",
          qb_warnings(GAME, squads(), pools("Marcus Mariota"), QbCheck(report, books())), [])


def test_other_week_books_ignored():
    check("last week's lines are not used",
          qb_warnings(GAME, squads(), pools("Jayden Daniels"), QbCheck({}, books(week=3))), [])


def test_no_priced_qb_silent():
    b = {"2026_04_IND_WAS": {"season": 2026, "week": 4, "pass": set(), "td": {"Terry McLaurin"}}}
    check("no QB priced: no warning", qb_warnings(GAME, squads(), pools("Jayden Daniels"), QbCheck({}, b)), [])


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(name)
            fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
