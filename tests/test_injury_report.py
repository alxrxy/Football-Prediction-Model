"""Tests for picking the current injury report out of the injuries table.

    python -m tests.test_injury_report

Rows are upserted and never deleted, so the table holds every report ever
pulled. Charging a player from an old pull is exactly the bug these pin down:
a player who has since been cleared must stop costing his team points.
"""

from __future__ import annotations

import sys

from src.features import latest_injury_report

PASS, FAIL = 0, 0


def check(label: str, got, want) -> None:
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got {got!r}, want {want!r}")


def row(player, source, pulled_at):
    return {"player": player, "source": source, "pulled_at": pulled_at}


def players(rows):
    return sorted(r["player"] for r in rows)


def test_dropped_player_not_charged():
    """A player missing from the latest pull is no longer on the report."""
    rows = [
        row("Cleared Guy", "nflverse", "2026-09-12T08:46:00+00:00"),
        row("Still Out", "nflverse", "2026-09-13T16:18:00+00:00"),
    ]
    check("only the latest pull", players(latest_injury_report(rows)), ["Still Out"])


def test_latest_is_per_source():
    """A feed that failed this run falls back to its own previous report."""
    rows = [
        row("Espn Old", "espn", "2026-09-12T18:38:00+00:00"),
        row("Espn New", "espn", "2026-09-13T16:18:00+00:00"),
        # nflverse failed on the 16:18 run; its last good pull is still used.
        row("Nflverse Last", "nflverse", "2026-09-12T08:46:00+00:00"),
    ]
    check("per-source latest", players(latest_injury_report(rows)),
          ["Espn New", "Nflverse Last"])


def test_mixed_timestamp_formats():
    """Supabase and SQLite render the same instant differently."""
    rows = [
        row("A", "espn", "2026-09-13T16:18:00Z"),
        row("B", "espn", "2026-09-13T16:18:00+00:00"),
        row("C", "espn", "2026-09-13T11:18:00-05:00"),
    ]
    check("same instant kept", players(latest_injury_report(rows)), ["A", "B", "C"])


def test_empty():
    check("empty table", latest_injury_report([]), [])


if __name__ == "__main__":
    for fn in [
        test_dropped_player_not_charged,
        test_latest_is_per_source,
        test_mixed_timestamp_formats,
        test_empty,
    ]:
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
