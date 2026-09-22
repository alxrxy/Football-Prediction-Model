"""Tests for devigging, blending and the edge test (src/market.py).

    python -m tests.test_market
"""

from __future__ import annotations

import sys

from src import market
from src.market import MarginTable, blend, devig, implied, spread_edge

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


def test_implied():
    check("-110 break-even", implied(-110), 110 / 210, 1e-12)
    check("+150", implied(150), 0.4, 1e-12)
    check("-200", implied(-200), 2 / 3, 1e-12)


def test_median_price_across_even_money():
    """P34: books straddling even money must not median into the -100..+100 gap."""
    straddle = [-108, -105, -102, 100, 100, 104]     # CIN@HOU away at -2.5, 2026-09-20
    got = market.median_price(straddle)
    check("straddling set gives a real price", got <= -100 or got >= 100, True)
    # probabilities 0.519, 0.512, 0.505, 0.5, 0.5, 0.490 -> median 0.5025
    check("near even money", implied(got), 0.5025, 0.002)
    check("[-102, +100] is not -1", market.median_price([-102, 100]), -101)
    check("odd count returns the middle book", market.median_price([-120, -110, 105]), -110)
    check("even count, no straddle", market.median_price([-110, -105]), -107)
    check("None skipped", market.median_price([None, -110]), -110)
    check("nothing priced", market.median_price([]), None)


def test_devig_sums_and_symmetry():
    for method in market.DEVIG_METHODS:
        p = devig([-110, -110], method)
        check(f"{method}: -110/-110 is 50/50", p[0], 0.5, 1e-9)
        p = devig([-200, 170], method)
        check(f"{method}: sums to 1", sum(p), 1.0, 1e-9)


def test_devig_favourite_longshot():
    """Every non-crude method gives the favourite more than equal-margin does."""
    base = devig([-300, 240], "multiplicative")[0]
    for method in ("shin", "odds_ratio", "log"):
        fav = devig([-300, 240], method)[0]
        check(f"{method}: favourite above multiplicative", fav > base, True)
    # Shin by hand, -300/+240: q = 0.75, 0.2941, S = 1.0441. At z = 0.045 the
    # two probabilities are 0.7279 + 0.2719 = 0.9998, so z ~ 0.0445.
    check("shin -300/+240", devig([-300, 240], "shin")[0], 0.7279, 5e-4)


def test_blend():
    check("weight 0 is the market", blend(0.8, 0.5, 0.0), 0.5, 1e-12)
    check("weight 1 is the model", blend(0.8, 0.5, 1.0), 0.8, 1e-12)
    # logit(0.8) = 1.3863; 0.15 * 1.3863 = 0.2079 -> 0.5518
    check("weight 0.15 on 0.8 vs 0.5", blend(0.8, 0.5, 0.15), 0.5518, 1e-4)


def test_edge_no_prices():
    """DEN@KC as stored: model KC -1.46 vs market KC -2, no prices stored."""
    e = spread_edge(-1.46, 13.0, -2.0, [], "nfl", weight=0.15, buffer=0.03, method="shin")
    check("market assumed 50/50", e["p_market_home"], 0.5, 1e-9)
    check("lean DEN (away)", e["side"], "away")
    # P(home covers) = Phi(-3.46/13) = 0.3951; blend -> 0.4841; away 0.5159
    check("model P(KC covers)", e["p_model_home"], 0.3951, 1e-4)
    check("blended P(DEN covers)", e["p_side_blend"], 0.5159, 1e-4)
    check("edge vs -110 break-even", e["edge_pp"], 0.5159 - 110 / 210, 2e-4)
    check("not flagged", e["flag"], False)


def test_edge_flags_past_threshold():
    need = market.points_to_flag(13.0, 0.15, 0.03)
    check("points needed at w=0.15, 3pp, -110", need, 11.34, 0.02)
    # margin + line is the points gap, so margin = gap - line.
    hit = spread_edge(need + 0.1 + 2.0, 13.0, -2.0, [], "nfl", 0.15, 0.03, "shin")
    miss = spread_edge(need - 0.1 + 2.0, 13.0, -2.0, [], "nfl", 0.15, 0.03, "shin")
    check("just past threshold flags", hit["flag"], True)
    check("just short does not", miss["flag"], False)


def test_edge_uses_prices():
    """A juiced side needs more: -130 break-even is 56.5%, not 52.4%."""
    books = [{"book": "a", "spread": -2.0, "spread_price_home": 110, "spread_price_away": -130}]
    e = spread_edge(-1.46, 13.0, -2.0, books, "nfl", 0.15, 0.03, "shin")
    check("market leans away", e["p_market_home"] < 0.5, True)
    check("away price used", e["price"], -130)
    check("break-even at -130", e["breakeven"], round(130 / 230, 4))


def test_margin_table_push_and_move():
    t = MarginTable("nfl", spreads=[-3, -3, -3, -3], margins=[3, 3, 4, 2], smooth=0.0)
    # Home -3: covers on 4 (0.25), pushes on 3 (0.5) -> 0.25 / 0.5
    check("push excluded", t.cover(-3.0), 0.5, 1e-12)
    check("-2.5 covers on 3 and 4", t.cover(-2.5), 0.75, 1e-12)
    real = market.margin_table("nfl")
    across_3 = real.cover(-2.5) - real.cover(-3.5)
    across_5 = real.cover(-4.5) - real.cover(-5.5)
    check("a point across 3 is worth more than across 5", across_3 > across_5, True)
    check("move is identity at same line", real.move(0.6, -3.0, -3.0), 0.6, 1e-12)
    check("worse line, lower probability", real.move(0.5, -2.5, -3.5) < 0.5, True)


if __name__ == "__main__":
    for fn in [
        test_implied,
        test_median_price_across_even_money,
        test_devig_sums_and_symmetry,
        test_devig_favourite_longshot,
        test_blend,
        test_edge_no_prices,
        test_edge_flags_past_threshold,
        test_edge_uses_prices,
        test_margin_table_push_and_move,
    ]:
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
