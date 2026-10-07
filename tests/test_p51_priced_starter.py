"""Tests for P51: promote the one priced QB over a ruled-out depth-chart QB1.

    python -m tests.test_p51_priced_starter
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from src.box_score import passer_weights
from src.simulate_nfl import USAGE_CATEGORIES, priced_starter, team_shares

PASS, FAIL = 0, 0


def check(label: str, got, want) -> None:
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got {got!r}, want {want!r}")


def roles() -> pd.DataFrame:
    rows = [("CHI", "q1", "Caleb Williams", "QB", 1), ("CHI", "q2", "Tyson Bagent", "QB", 2),
            ("CHI", "q3", "Case Keenum", "QB", 3), ("CHI", "w1", "DJ Moore", "WR", 1)]
    df = pd.DataFrame(rows, columns=["team", "player_id", "player", "position", "rank"])
    for c in USAGE_CATEGORIES:
        df[c] = [0.0, 0.0, 0.0, 0.3]
    return df


def inj(**status):
    names = {"williams": "Caleb Williams", "bagent": "Tyson Bagent", "keenum": "Case Keenum"}
    return [{"team": "CHI", "player": names[k], "status": v,
             "play_probability": 0.0 if v in ("out", "ir", "inactive") else (0.1 if v == "doubtful" else 1.0)}
            for k, v in status.items()]


def qb1(injuries, priced):
    squad, _, _ = team_shares(roles(), "CHI", injuries, None, priced)
    w = passer_weights(squad)
    return squad.at[int(w.argmax()), "player"]


def test_rule():
    check("CHI wk3: Williams out, Keenum priced -> Keenum", qb1(inj(williams="out"), {"Case Keenum", "Jalen Hurts"}), "Case Keenum")
    check("no rule without a price -> Bagent (depth order)", qb1(inj(williams="out"), None), "Tyson Bagent")
    check("QB1 healthy -> no promotion", qb1([], {"Case Keenum"}), "Caleb Williams")
    check("QB1 questionable is not ruled out", qb1(inj(williams="questionable"), {"Case Keenum"}), "Caleb Williams")
    check("QB1 doubtful counts as ruled out", qb1(inj(williams="doubtful"), {"Case Keenum"}), "Case Keenum")
    check("QB1 applied-inactive counts as ruled out", qb1(inj(williams="inactive"), {"Case Keenum"}), "Case Keenum")
    check("two backups priced -> depth order", qb1(inj(williams="out"), {"Case Keenum", "Tyson Bagent"}), "Tyson Bagent")
    check("priced backup himself inactive -> depth order", qb1(inj(williams="out", keenum="inactive"), {"Case Keenum"}),
          "Tyson Bagent")
    check("priced QB is already next in line -> same outcome", qb1(inj(williams="out"), {"Tyson Bagent"}), "Tyson Bagent")
    check("suffix/case tolerant match", priced_starter(roles(), "CHI", {("CHI", "caleb williams"): {"status": "out"}},
                                                      {"CASE KEENUM"}), "q3")


def test_non_firing_identical():
    for injuries, priced in (([], {"Case Keenum"}), (inj(williams="out"), None), (inj(williams="questionable"), {"Case Keenum"})):
        a = team_shares(roles(), "CHI", injuries, None, None)
        b = team_shares(roles(), "CHI", injuries, None, priced)
        same = a[0].equals(b[0]) and all(np.array_equal(a[1][c], b[1][c]) for c in a[1]) and a[2] == b[2]
        check(f"non-firing case byte-identical ({len(injuries)} rows, priced={bool(priced)})", same, True)


if __name__ == "__main__":
    test_rule()
    test_non_firing_identical()
    print(f"\n{PASS} passed, {FAIL} FAILED")
    sys.exit(1 if FAIL else 0)
