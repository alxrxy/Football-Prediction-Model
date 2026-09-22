"""Tests for the Record page's flagged-edge and edge-size split.

    python -m tests.test_export_edges

No network or database: hand-built graded rows with known results.
"""

from __future__ import annotations

import sys

from src.export_dashboard import _edge_record
from src.grade import evaluate

PASS, FAIL = 0, 0


def check(label: str, got, want) -> None:
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got {got!r}, want {want!r}")


def row(gid, edge, market, margin, flagged=False):
    return {"game_id": gid, "edge": edge, "market_spread": market, "actual_margin": margin,
            "is_value": flagged, "model_margin_home": -market + edge, "model_win_prob_home": 0.5}


GAMES = {g: {"week": w, "home_team": h, "away_team": a, "kickoff_time": k}
         for g, w, h, a, k in [("A", 1, "HA", "AA", "2026-09-13T17:00Z"), ("B", 1, "HB", "AB", "2026-09-13T20:00Z"),
                               ("C", 2, "HC", "AC", "2026-09-20T17:00Z"), ("D", 2, "HD", "AD", "2026-09-20T20:00Z"),
                               ("E", 2, "HE", "AE", "2026-09-21T00:15Z")]}
ROWS = [
    row("A", 7.0, -3.0, 10, flagged=True),   # took home at -3, won by 10: W
    row("B", -2.5, -6.0, 9, flagged=True),   # took away +6, home won by 9: L
    row("C", 3.0, -3.0, 3),                  # push
    row("D", 0.0, -1.5, 7),                  # zero edge: graded as the away side, so L
    row("E", -6.5, 2.5, -10),                # took away, away won by 10: W
]


def test_edge_record():
    e = _edge_record(ROWS, GAMES)
    check("flagged", e["flagged"], {"win": 1, "loss": 1, "push": 0})
    check("unflagged, push counted", e["unflagged"], {"win": 1, "loss": 1, "push": 1})
    by = {b["min"]: (b["win"], b["loss"], b["push"]) for b in e["by_edge"]}
    check("all picks", by[0.0], (2, 2, 1))
    check(">= 3 keeps the push", by[3.0], (2, 0, 1))
    check(">= 6", by[6.0], (2, 0, 0))
    check("flagged games in kickoff order", [(g["game_id"], g["lean"], g["ats"]) for g in e["flagged_games"]],
          [("A", "HA", "W"), ("B", "AB", "L")])
    stats = evaluate(ROWS)["ats"]
    check("adds up to the grader's headline", (by[0.0][0], by[0.0][1], by[0.0][2]),
          (stats["win"], stats["loss"], stats["push"]))


if __name__ == "__main__":
    print("\ntest_edge_record")
    test_edge_record()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
