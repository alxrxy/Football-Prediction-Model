"""Tests for the grading maths.

    python -m tests.test_grade

Grading is the one place in this project where a silent sign error would be
actively harmful: it would report the model as winning when it is losing, and
nothing downstream would contradict it. The cases below are hand-computed so
the arithmetic is checked against known answers rather than against whatever
the code happens to produce.

No network and no database — evaluate() is pure.
"""

from __future__ import annotations

import sys

from src.grade import evaluate

PASS, FAIL = 0, 0


def check(label: str, got, want) -> None:
    global PASS, FAIL
    ok = got == want if not isinstance(want, float) else abs(got - want) < 1e-9
    if ok:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got {got!r}, want {want!r}")


def p(margin, market, edge, actual, prob=None, conf="high"):
    """One prediction row. Spreads are home-team lines, as everywhere else."""
    return {
        "model_version": "test",
        "model_margin_home": margin,
        "market_spread": market,
        "edge": edge,
        "actual_margin": actual,
        "model_win_prob_home": prob,
        "confidence": conf,
    }


def test_ats_sides():
    """The side the edge points to must be the side that is graded."""
    rows = [
        # Model likes HOME (+edge). Market has home -3, home wins by 10 -> covers. WIN
        p(margin=10.0, market=-3.0, edge=7.0, actual=10),
        # Model likes HOME (+edge). Home wins by 1, needed 3 -> fails. LOSS
        p(margin=10.0, market=-3.0, edge=7.0, actual=1),
        # Model likes AWAY (-edge). Market home -7, home wins by 3 -> away covers. WIN
        p(margin=-2.0, market=-7.0, edge=-5.0, actual=3),
        # Model likes AWAY (-edge). Home wins by 14 -> home covers. LOSS
        p(margin=-2.0, market=-7.0, edge=-5.0, actual=14),
    ]
    stats = evaluate(rows)
    check("ats wins", stats["ats"]["win"], 2)
    check("ats losses", stats["ats"]["loss"], 2)
    check("ats pushes", stats["ats"]["push"], 0)


def test_push_excluded():
    """A result landing exactly on the number is a push, not a win or a loss."""
    rows = [p(margin=5.0, market=-3.0, edge=2.0, actual=3)]
    stats = evaluate(rows)
    check("push counted", stats["ats"]["push"], 1)
    check("push not a win", stats["ats"]["win"], 0)
    check("push not a loss", stats["ats"]["loss"], 0)
    check("push excluded from decided", stats["ats"]["decided"], 0)


def test_underdog_cover():
    """An away underdog covers by losing narrowly. Easy sign error, so pinned."""
    # Market: home -10. Away loses by 7 -> away covers. Model liked away.
    rows = [p(margin=-4.0, market=-10.0, edge=-6.0, actual=7)]
    stats = evaluate(rows)
    check("away dog cover = win", stats["ats"]["win"], 1)

    # Same game, model liked home instead -> must be a loss.
    rows = [p(margin=-4.0, market=-10.0, edge=+6.0, actual=7)]
    check("home side on same game = loss", evaluate(rows)["ats"]["loss"], 1)


def test_straight_up():
    """Straight up follows win probability, and ties are excluded."""
    rows = [
        p(margin=3.0, market=-1.0, edge=2.0, actual=7, prob=0.7),    # picked home, home won
        p(margin=3.0, market=-1.0, edge=2.0, actual=-7, prob=0.7),   # picked home, home lost
        p(margin=-3.0, market=1.0, edge=-2.0, actual=-7, prob=0.3),  # picked away, away won
        p(margin=0.0, market=0.0, edge=0.0, actual=0, prob=0.5),     # tie, excluded
    ]
    stats = evaluate(rows)
    check("su correct", stats["su"]["right"], 2)
    check("su graded (tie excluded)", stats["su"]["n"], 3)


def test_margin_error_vs_market():
    """MAE is computed for the model and the line over the same games."""
    # Model says home by 10, market implies home by 3, home wins by 6.
    # model error |10-6| = 4 ; market error |3-6| = 3
    rows = [p(margin=10.0, market=-3.0, edge=7.0, actual=6)]
    stats = evaluate(rows)
    check("model mae", stats["mae"], 4.0)
    check("market mae", stats["market_mae"], 3.0)


def test_brier():
    """Brier score over a certain-and-correct and a certain-and-wrong call."""
    rows = [
        p(margin=1.0, market=0.0, edge=1.0, actual=7, prob=1.0),   # (1-1)^2 = 0
        p(margin=1.0, market=0.0, edge=1.0, actual=-7, prob=1.0),  # (1-0)^2 = 1
    ]
    check("brier", evaluate(rows)["brier"], 0.5)


def test_edge_buckets_are_cumulative():
    """A 5-point edge counts in every bucket at or below 5."""
    rows = [p(margin=8.0, market=-3.0, edge=5.0, actual=10)]
    buckets = evaluate(rows)["by_edge"]
    check("bucket >=0.0", buckets[0.0], [1, 1])
    check("bucket >=4.0", buckets[4.0], [1, 1])
    check("bucket >=6.0 excluded", buckets[6.0], [0, 0])


def test_missing_market_skipped():
    """No line means no ATS result, but the margin error still counts."""
    rows = [p(margin=6.0, market=None, edge=None, actual=3, prob=0.6)]
    stats = evaluate(rows)
    check("no ats result", stats["ats"]["decided"], 0)
    check("mae still counted", stats["mae"], 3.0)
    check("market mae absent", stats["market_mae"], 0.0)


if __name__ == "__main__":
    for fn in [
        test_ats_sides,
        test_push_excluded,
        test_underdog_cover,
        test_straight_up,
        test_margin_error_vs_market,
        test_brier,
        test_edge_buckets_are_cumulative,
        test_missing_market_skipped,
    ]:
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
