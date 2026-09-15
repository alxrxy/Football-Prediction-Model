"""Tests for closing line value (src/clv.py).

    python -m tests.test_clv
"""

from __future__ import annotations

import sys

from src.clv import _num, apply_close, ats_result

PASS, FAIL = 0, 0


def check(label: str, got, want, tol: float | None = None) -> None:
    global PASS, FAIL
    ok = abs(got - want) <= tol if tol is not None else got == want
    if ok:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got {got!r}, want {want!r}")


# DEN @ KC: the lean was DEN at KC -2; DraftKings closed KC -2.5, home -108 / away -112.
ROW = {"sport": "nfl", "line": -2.0, "side": "away", "p_market": 0.5, "devig_method": "multiplicative",
       "ref_book": None, "ref_line": None, "ref_price_home": None, "ref_price_away": None}
CLOSE = {"close_line": -2.5, "close_price_home": -108, "close_price_away": -112,
         "close_source": "espn:draftkings", "close_at": None}


def test_same_book():
    """Same book both times: DEN +2.5 at -110/-110 then, -112 at the close."""
    row = {**ROW, "line": -2.5, "ref_book": "oddsapi:draftkings", "ref_line": -2.5,
           "ref_price_home": -110, "ref_price_away": -110}
    out = apply_close(row, CLOSE)
    check("basis", out["clv_basis"], "same_book")
    # away 112/212 = 0.52830, home 108/208 = 0.51923; share 0.50433
    check("DEN's close probability", out["p_close"], 0.5043, 1e-4)
    check("CLV positive: the price moved toward DEN", out["clv_pp"], 0.0043, 1e-4)


def test_consensus_line_moved_against():
    """Consensus DEN +2 then; the close is DEN +2.5, a better number than was
    taken, so at +2 the lean is worth less than the close says DEN +2.5 is."""
    out = apply_close(ROW, CLOSE)
    check("basis", out["clv_basis"], "consensus")
    check("restated at +2, DEN is below 50%", out["p_close"] < 0.5, True)
    check("CLV negative", out["clv_pp"] < 0, True)


def test_implausible_move_is_suspect():
    """Georgia stored at -69.5, closed -40.5: bad line data, not CLV."""
    row = {**ROW, "sport": "ncaaf", "line": -69.5}
    out = apply_close(row, {**CLOSE, "close_line": -40.5})
    check("marked suspect", out["clv_basis"], "suspect_line")
    check("no CLV", out["clv_pp"], None)
    ok = apply_close({**ROW, "sport": "ncaaf", "line": -6.5}, {**CLOSE, "close_line": -10.0})
    check("a 3.5-pt college move still counts", ok["clv_basis"], "consensus")


def test_after_kickoff_has_no_clv():
    row = {**ROW, "kickoff_time": "2026-09-12T16:00:00+00:00", "flagged_at": "2026-09-12T18:37:00+00:00"}
    out = apply_close(row, CLOSE)
    check("marked after kickoff", out["clv_basis"], "after_kickoff")
    check("no CLV", out["clv_pp"], None)


def test_ats_result():
    game = {"completed": True, "home_points": 31, "away_points": 10}
    check("DEN +2 lost", ats_result(ROW, game), "L")
    check("KC -2 won", ats_result({**ROW, "side": "home"}, game), "W")
    check("push", ats_result({**ROW, "line": -21.0}, game), "P")
    check("not final", ats_result(ROW, {"completed": False}), None)


def test_espn_strings():
    check("-2.5", _num("-2.5"), -2.5)
    check("+100", _num("+100"), 100.0)
    check("EVEN price", _num("EVEN"), 100.0)
    check("PK line", _num("PK"), 0.0)
    check("junk", _num("n/a"), None)


if __name__ == "__main__":
    for fn in [test_same_book, test_consensus_line_moved_against, test_implausible_move_is_suspect,
               test_after_kickoff_has_no_clv, test_ats_result, test_espn_strings]:
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
