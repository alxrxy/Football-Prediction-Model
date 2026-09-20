"""Prop pricing and ranking, and the Q&A context builders (Phase 3).

    python -m tests.test_props

No network and no Claude calls: synthetic lines and simulations.
"""

from __future__ import annotations

import math

from src import game_context
from src.props import MAX_GAP, market_view, match_player, p_over, pick_alt, pnorm, rank

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
    check("gap = raw model minus market", round(top["gap"], 3), round(top["p_model_raw"] - top["p_market"], 3))
    check(f"gaps over {MAX_GAP:.0%} held out", [r["player"] for r in out["held_out"]], ["Bad Role Back"])
    check("unmatched names counted", out["unmatched_players"], 1)
    check("no defect note by default", top.get("defect_note"), None)

    from src import props
    props.KNOWN_DEFECTS[("g1", "Star Receiver")] = "Known defect (test)"
    try:
        out = rank(lines, {"g1": _sim(75.0)})
        top = out["ranked"][0]
        check("a known defect is labelled, not removed", (top["player"], top["defect_note"]),
              ("Star Receiver", "Known defect (test)"))
        check("and reaches the explanation prompt", "Known defect (test)" in props._describe(top), True)
    finally:
        del props.KNOWN_DEFECTS[("g1", "Star Receiver")]
    props.KNOWN_DEFECTS[("g1", "team:BUF")] = "Team issue (test)"
    try:
        out = rank(lines, {"g1": _sim(75.0)})
        check("a team-wide issue labels every prop of that team",
              {r["defect_note"] for r in out["ranked"] + out["held_out"]}, {"Team issue (test)"})
    finally:
        del props.KNOWN_DEFECTS[("g1", "team:BUF")]


def test_qb_rushing_ranked_with_its_own_offset():
    from src import config, props

    q = {"median": 20, "mean": 20, "p10": 5, "p25": 12, "p75": 28, "p90": 36}
    sim = {"home_win_prob": 0.6, "margin": {"p50": 3}, "total": {"p50": 45}, "generated_at": "x",
           "box_score": {"home": {"players": [
               {"player": "Pocket Passer", "position": "QB", "depth_rank": 1, "touches": 4, "rushing": {"yds": q}},
               {"player": "Lead Back", "position": "RB", "depth_rank": 1, "touches": 18, "rushing": {"yds": q}},
           ]}, "away": {"players": []}}}
    book = {"dk": {"point": 19.5, "over": -110, "under": -110}}
    lines = {"games": {"g1": {"home": "BUF", "away": "DET", "kickoff": "k", "players": {
        "Pocket Passer": {"player_rush_yds": book}, "Lead Back": {"player_rush_yds": book}}}}}
    out = rank(lines, {"g1": sim})
    check("QB rushing is ranked again (P24)", sorted(r["player"] for r in out["ranked"]), ["Lead Back", "Pocket Passer"])
    check("nothing held out as an engine defect", out["held_out"], [])
    props.PROP_HOLDOUTS[("g1", "Pocket Passer", "player_rush_yds")] = "Known meaningless (test)"
    try:
        out = rank(lines, {"g1": sim})
        check("a single prop can still be held out as a defect",
              [(r["player"], r["held_reason"], r.get("held_note")) for r in out["held_out"]],
              [("Pocket Passer", "structural", "Known meaningless (test)")])
        check("and the rest of the category stays ranked", [r["player"] for r in out["ranked"]], ["Lead Back"])
    finally:
        del props.PROP_HOLDOUTS[("g1", "Pocket Passer", "player_rush_yds")]
    saved = config.PROPS_BIAS_ADJUST
    config.PROPS_BIAS_ADJUST = True
    try:
        rb = props.bias_adjust(0.5, "player_rush_yds", "RB")
        check("RB rushing gets its own offset", round(rb, 4),
              round(1 / (1 + math.exp(-props.BIAS_FIT["position_offsets"]["player_rush_yds"]["RB"])), 4))
        check("QB rushing gets its own offset", round(props.bias_adjust(0.5, "player_rush_yds", "QB"), 4),
              round(1 / (1 + math.exp(-props.BIAS_FIT["position_offsets"]["player_rush_yds"]["QB"])), 4))
        by_pos = props.BIAS_FIT["position_offsets"]["player_reception_yds"]
        check("receiving yards: RB and WR get different offsets",
              props.bias_adjust(0.5, "player_reception_yds", "RB") < props.bias_adjust(0.5, "player_reception_yds", "WR"),
              True)
        check("receiving yards: a position it was not fitted on stays raw",
              props.bias_adjust(0.5, "player_reception_yds", "FB"), 0.5)
        check("receiving yards has no category offset left to fall back on",
              "player_reception_yds" in props.BIAS_FIT["offsets"], False)
        check("every split position has an n", set(by_pos) == set(props.BIAS_FIT["position_n"]["player_reception_yds"]), True)
    finally:
        config.PROPS_BIAS_ADJUST = saved


def test_started_games_not_ranked():
    from datetime import datetime, timezone

    book = {"dk": {"point": 60.5, "over": -110, "under": -110}}
    game = lambda kick: {"home": "BUF", "away": "DET", "kickoff": kick, "players": {  # noqa: E731
        "Star Receiver": {"player_reception_yds": book}}}
    lines = {"games": {"done": game("2026-09-18T00:15:00+00:00"), "later": game("2026-09-20T17:00:00+00:00")}}
    now = datetime(2026, 9, 18, 12, tzinfo=timezone.utc)
    out = rank(lines, {"done": _sim(75.0), "later": _sim(75.0)}, now=now)
    check("a kicked-off game is not ranked", [r["game_id"] for r in out["ranked"]], ["later"])
    check("nor held out", out["held_out"], [])
    check("but its rows are kept", [r["game_id"] for r in out["started"]], ["done"])


def test_pick_alt():
    q = {"p10": 150, "p25": 180, "median": 220, "p75": 260, "p90": 290}   # passing yards
    row = {"pick": "under", "line": 240.5}
    offers = [
        {"book": "dk", "side": "under", "point": 240.5, "price": -110},   # the main line itself
        {"book": "dk", "side": "under", "point": 270.5, "price": -400},   # safe but too short
        {"book": "dk", "side": "under", "point": 260.5, "price": -230},   # sim 75%
        {"book": "fd", "side": "under", "point": 255.5, "price": -170},   # sim ~69%
        {"book": "dk", "side": "under", "point": 225.5, "price": +160},   # sim <65%: not "safe"
        {"book": "dk", "side": "over", "point": 200.5, "price": -200},    # wrong side
    ]
    alt = pick_alt(row, q, offers)
    check("an alt is found", alt is not None, True)
    check("never the main line, never past -250", alt["line"] not in (240.5, 270.5), True)
    check("simulation at least 65%", alt["p_model"] >= 0.65, True)
    check("best expected return in the band", (alt["line"], alt["book"]), (255.5, "fd"))
    check("nothing qualifies -> none", pick_alt(row, q, offers[:2]), None)
    harder = [{"book": "dk", "side": "under", "point": 230.5, "price": -120}]   # tougher than 240.5
    check("never a harder line than the pick", pick_alt(row, q, harder), None)
    over = {"pick": "over", "line": 200.5}
    got = pick_alt(over, q, [{"book": "dk", "side": "over", "point": 185.5, "price": -200},
                             {"book": "dk", "side": "over", "point": 215.5, "price": +120}])
    check("over: the easier (lower) line", got["line"], 185.5)


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


def test_starter_mismatch_holdout():
    """A priced quarterback the sim has at a median of 0 is held out, not ranked (P28)."""
    import src.config as cfg
    from src.props import _starter_mismatch

    was = cfg.QB_EXPECTED_STARTER
    try:
        cfg.QB_EXPECTED_STARTER = True
        note = _starter_mismatch("player_pass_yds", "QB2", 207.5, {"median": 0.0})
        check("QB2 with a median of 0 is held", bool(note), True)
        check("the note names the line", "207.5" in (note or ""), True)
        check("a QB who does simulate is not held",
              _starter_mismatch("player_pass_yds", "QB1", 245.5, {"median": 238.0}), None)
        check("a receiver at 0 is not a starter mismatch",
              _starter_mismatch("player_reception_yds", "WR4", 25.5, {"median": 0.0}), None)
        check("no line, nothing to compare",
              _starter_mismatch("player_pass_yds", "QB2", 0, {"median": 0.0}), None)
        cfg.QB_EXPECTED_STARTER = False
        check("off behind the flag",
              _starter_mismatch("player_pass_yds", "QB2", 207.5, {"median": 0.0}), None)
    finally:
        cfg.QB_EXPECTED_STARTER = was


def test_tied_lines_pick_a_real_line():
    """An even number of tied modal lines must not average into a line nobody posts (P29)."""
    def bk(pts):
        return {f"book{i}": {"point": p, "over": -110, "under": -110} for i, p in enumerate(pts)}

    v = market_view(bk([182.5, 182.5, 183.5, 183.5]))
    check("a tie resolves to a real posted line", v is not None, True)
    check("and it is one of the tied lines", v["point"] in (182.5, 183.5), True)

    v = market_view(bk([60.5, 60.5, 61.5, 61.5, 63.5]))
    check("nearest the consensus wins", v["point"], 61.5)

    v = market_view(bk([10.5, 11.5]))
    check("two books, one line each", v is not None, True)

    v = market_view(bk([242.5, 242.5, 242.5, 244.5]))
    check("a clear mode is untouched", v["point"], 242.5)

    v = market_view(bk([100.5, 100.5, 101.5, 102.5, 102.5, 101.5]))
    check("an odd median that is real is left alone", v["point"], 101.5)

    check("no books, no view", market_view({}), None)


if __name__ == "__main__":
    for fn in [test_p_over, test_starter_mismatch_holdout, test_tied_lines_pick_a_real_line, test_market_view, test_names, test_rank, test_qb_rushing_ranked_with_its_own_offset, test_started_games_not_ranked, test_pick_alt, test_context]:
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    raise SystemExit(1 if FAIL else 0)
