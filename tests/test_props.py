"""Prop pricing and ranking, and the Q&A context builders (Phase 3).

    python -m tests.test_props

No network and no Claude calls: synthetic lines and simulations.
"""

from __future__ import annotations

from src import game_context
from src.props import MAX_GAP, market_view, match_player, p_over, pnorm, rank

PASS, FAIL = 0, 0


def check(label: str, got, want, tol: float | None = None) -> None:
    global PASS, FAIL
    ok = abs(got - want) <= tol if tol is not None else got == want
    if ok:
        PASS += 1
        print(f"  ok    {label}: {got!r}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got {got!r}, want {want!r}")


def test_p_over():
    counts = {"ge": [1.0, 0.95, 0.8, 0.6, 0.4, 0.2, 0.1, 0.0]}
    check("counts: over 3.5 is P(>= 4)", p_over(counts, 3.5), 0.4)
    check("counts: past the tail", p_over(counts, 20.5), 0.0)
    grid = {"pct": [float(v) for v in range(10, 105, 5)]}      # 5th pct = 10 ... 95th = 100
    check("grid: at the median", round(p_over(grid, 55.0), 3), 0.5)
    check("grid: below the 5th percentile", round(p_over(grid, 0.0), 3), 0.975)
    five = {"p10": 20, "p25": 40, "median": 60, "p75": 80, "p90": 100}
    check("quantiles: at the median", round(p_over(five, 60), 3), 0.5)
    check("quantiles: halfway p25-median", round(p_over(five, 50), 3), 0.625)
    tied = {"p10": 0, "p25": 0, "median": 10, "p75": 10, "p90": 30}
    check("tied quantiles don't break it", 0 <= p_over(tied, 5) <= 1, True)


def test_market_view():
    books = {"dk": {"point": 62.5, "over": -110, "under": -110},
             "fd": {"point": 62.5, "over": -105, "under": -115},
             "mgm": {"point": 63.5, "over": -110, "under": -110},
             "half": {"point": 62.5, "over": -110}}
    mv = market_view(books)
    check("consensus line is the most common", mv["point"], 62.5)
    check("only books at that line, with both sides", mv["books"], 2)
    check("fair P(over) near 50%", mv["p_over"], 0.5, tol=0.02)
    check("best over price", mv["best"]["over"], (-105, "fd"))
    check("no two-sided prices -> none", market_view({"x": {"point": 1.5, "over": -110}}), None)


def test_names():
    players = [("home", {"player": "Kenneth Walker"}), ("away", {"player": "AJ Brown"})]
    check("suffix dropped", match_player("Kenneth Walker III", players)[1]["player"], "Kenneth Walker")
    check("initials punctuation", match_player("A.J. Brown", players)[1]["player"], "AJ Brown")
    check("no false match", match_player("Josh Allen", players), None)
    check("pnorm", pnorm("Amon-Ra St. Brown Jr."), "amon ra st brown")


def _sim(rec_median: float) -> dict:
    q = {"median": rec_median, "mean": rec_median, "p10": rec_median - 40, "p25": rec_median - 20,
         "p75": rec_median + 20, "p90": rec_median + 40}
    return {"home_win_prob": 0.6, "margin": {"p50": 3}, "total": {"p50": 45}, "generated_at": "x",
            "box_score": {"home": {"players": [
                {"player": "Star Receiver", "position": "WR", "depth_rank": 1, "touches": 8,
                 # P(rec >= 6) = 0.5: the receptions line at 5.5 carries no gap.
                 "receiving": {"yds": q, "rec": {"ge": [1, 1, 1, 0.95, 0.85, 0.7, 0.5, 0.3, 0.1, 0]}}},
                {"player": "Bad Role Back", "position": "RB", "depth_rank": 1, "touches": 15,
                 "rushing": {"yds": {**q, "median": 150, "p10": 120, "p25": 135, "p75": 165, "p90": 180}}},
            ]}, "away": {"players": []}}}


def test_rank():
    lines = {"games": {"g1": {"home": "BUF", "away": "DET", "kickoff": "k", "players": {
        "Star Receiver": {"player_reception_yds": {"dk": {"point": 60.5, "over": -110, "under": -110}},
                          "player_receptions": {"dk": {"point": 5.5, "over": -110, "under": -110}}},
        "Bad Role Back": {"player_rush_yds": {"dk": {"point": 60.5, "over": -110, "under": -110}}},
        "Nobody Here": {"player_rush_yds": {"dk": {"point": 10.5, "over": -110, "under": -110}}},
    }}}}
    out = rank(lines, {"g1": _sim(75.0)})
    top = out["ranked"][0]
    check("ranked by gap: receiving yards over first", (top["player"], top["market"], top["pick"]),
          ("Star Receiver", "player_reception_yds", "over"))
    check("gap = model minus market", round(top["gap"], 3), round(top["p_model"] - top["p_market"], 3))
    check(f"gaps over {MAX_GAP:.0%} held out", [r["player"] for r in out["held_out"]], ["Bad Role Back"])
    check("unmatched names counted", out["unmatched_players"], 1)


def test_context():
    game = {"home": "BUF", "away": "DET", "kickoff": "2026-09-18T00:15:00+00:00", "neutral": False,
            "market": {"spread": -4.5, "total": 48.5},
            "baseline": {"model_spread": -4.8, "margin_home": 4.8, "win_prob_home": 0.64, "edge": 0.3,
                         "confidence": "high", "is_value": False,
                         "market_edge": {"weight": 0.15, "side": "home", "p_side_blend": 0.51,
                                         "breakeven": 0.524, "flag": False}},
            "injuries": {"home": [], "away": []}}
    text = game_context.pregame_text(game, {"home": "BUF", "away": "DET", "pregame": {
        "n_sims": 10000, "median": {"home": 26, "away": 21}, "home_win_prob": 0.63,
        "margin": {"p10": -12, "p25": -4, "p50": 4, "p75": 13, "p90": 21},
        "total": {"p10": 32, "p25": 39, "p50": 48, "p75": 57, "p90": 65},
        "box_score": _sim(70)["box_score"]}}, [], "NFL")
    check("market line named", "BUF -4.5" in text, True)
    check("stage 1 result stated", "does not pass" in text, True)
    check("simulation summarised", "median final DET 21 - 26 BUF" in text, True)
    check("key players included", "Star Receiver" in text, True)
    check("compact (well under 4k chars)", len(text) < 4000, True)
    live = game_context.live_text({"home": "BUF", "away": "DET", "home_score": 17, "away_score": 10,
                                   "detail": "Q3 8:12", "possession": "DET", "down_distance": "3rd & 4",
                                   "live_sim": {"n_sims": 10000, "home_win_prob": 0.78, "pregame_win_prob_home": 0.63,
                                                "median_home_points": 27, "median_away_points": 20}})
    check("live score and state", "LIVE: DET 10 - 17 BUF, Q3 8:12; DET ball, 3rd & 4" in live, True)
    check("live model vs pregame", "BUF win 78% (pregame 63%)" in live, True)


if __name__ == "__main__":
    for fn in [test_p_over, test_market_view, test_names, test_rank, test_context]:
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    raise SystemExit(1 if FAIL else 0)
