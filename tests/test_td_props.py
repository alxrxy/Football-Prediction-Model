"""Anytime-TD line parsing, devigging and ranking.

    python -m tests.test_td_props

No network: synthetic lines and simulations.
"""

from __future__ import annotations

import math

from src import market
from src.ingest_td_props import parse_event
from src.td_props import TD_MAX_GAP, TD_PER_POINT, book_factors, is_team_entry, market_view, rank

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


def test_parse_event():
    data = {"bookmakers": [
        {"key": "dk", "markets": [{"key": "player_anytime_td", "outcomes": [
            {"name": "Yes", "description": "Bijan Robinson", "price": -190},
            {"name": "No", "description": "Bijan Robinson", "price": 150},
            {"name": "Yes", "description": "Drake London", "price": 165},
        ]}]},
        {"key": "ou", "markets": [{"key": "player_anytime_td", "outcomes": [
            {"name": "Over", "description": "Drake London", "point": 0.5, "price": 160},
            {"name": "Over", "description": "Drake London", "point": 1.5, "price": 900},   # 2+ TDs
        ]}]},
        {"key": "other", "markets": [{"key": "player_rush_yds", "outcomes": [
            {"name": "Over", "description": "Bijan Robinson", "point": 80.5, "price": -110}]}]},
    ]}
    p = parse_event(data)
    check("yes and no kept", p["Bijan Robinson"]["dk"], {"yes": -190, "no": 150})
    check("over 0.5 read as yes", p["Drake London"]["ou"], {"yes": 160})
    check("other markets ignored", "other" in p["Bijan Robinson"], False)


def test_team_entries():
    check("D/ST", is_team_entry("Atlanta Falcons D/ST"), True)
    check("Defense", is_team_entry("Atlanta Falcons Defense"), True)
    check("a player", is_team_entry("Bijan Robinson"), False)


def _slate(n=14, yes=150):
    return {f"Player {i}": {"a": {"yes": yes}} for i in range(n)}


def test_devig():
    players = _slate()
    players["Falcons D/ST"] = {"a": {"yes": 500}}
    k = book_factors(players, 44)["a"]
    lam = -math.log(1 - market.implied(150))
    check("scaled to the total's TDs", k * lam * 14, 44 * TD_PER_POINT, 1e-9)
    check("too few players: no factor", book_factors(_slate(5), 44), {})
    check("no total: no factor", book_factors(players, None), {})

    mv = market_view({"a": {"yes": 150}}, {"a": k})
    check("fair below the raw price", mv["p_yes"] < market.implied(150), True)
    check("fair = 1 - exp(-k lambda)", mv["p_yes"], 1 - math.exp(-k * lam), 1e-12)
    two = market_view({"b": {"yes": -120, "no": 100}}, {})
    check("two-sided book devigged directly", two["p_yes"], market.devig([-120, 100])[0], 1e-12)
    check("best No price kept", two["best"]["no"], (100, "b"))
    check("yes-only book with no factor is skipped", market_view({"c": {"yes": 150}}, {}), None)


def _sim(players):
    return {"market_total": 44, "market_spread": -3, "home_win_prob": 0.6, "total": {"p50": 44},
            "margin": {"p50": 3}, "generated_at": "t",
            "box_score": {"home": {"players": players}, "away": {"players": []}},
            "scorers": {"home": [{"player": "Star Back", "expected_tds": 0.9, "rz_target_share": 0.05,
                                  "rz_carry_share": 0.6, "gl_carry_share": 0.7}]}}


def test_rank():
    lines = {"games": {"G": {"home": "ATL", "away": "CAR", "kickoff": "k", "players": {
        **{f"Filler {i}": {"a": {"yes": 250}} for i in range(12)},
        "Star Back": {"a": {"yes": 100}},
        "Slot Guy": {"a": {"yes": 300}},
        "Ghost": {"a": {"yes": 200}},
        "Atlanta Falcons D/ST": {"a": {"yes": 600}},
    }}}}
    box = [{"player": "Star Back", "position": "RB", "depth_rank": 1, "anytime_td": 0.05, "touches": 20},
           {"player": "Slot Guy", "position": "WR", "depth_rank": 3, "anytime_td": 0.30, "touches": 4},
           *({"player": f"Filler {i}", "position": "WR", "depth_rank": 4, "anytime_td": 0.2, "touches": 2}
             for i in range(12))]
    out = rank(lines, {"G": _sim(box)})
    rows = {r["player"]: r for r in out["ranked"] + out["held_out"]}
    check("team defence skipped", out["team_entries"], 1)
    check("unmatched player listed", [u["player"] for u in out["unmatched"]], ["Ghost"])
    check("sim far below: held out", rows["Star Back"] in out["held_out"], True)
    check("held-out gap is past the cap", abs(rows["Star Back"]["gap"]) > TD_MAX_GAP, True)
    check("sim lower picks no", rows["Star Back"]["pick"], "no")
    check("no price when books don't sell No", rows["Star Back"]["price"], None)
    check("no stage 1 without a price", rows["Star Back"]["passes_stage1"], False)
    check("usage attached from the scorer table", rows["Star Back"]["usage"]["gl_carry_share"], 0.7)
    check("sim higher picks yes", rows["Slot Guy"]["pick"], "yes")
    check("yes carries its price", rows["Slot Guy"]["price"], 300)
    ranked = out["ranked"]
    check("ranked by absolute gap", all(abs(a["gap"]) >= abs(b["gap"]) for a, b in zip(ranked, ranked[1:])), True)
    check("ranks are 1..n", [r["rank"] for r in ranked], list(range(1, len(ranked) + 1)))


if __name__ == "__main__":
    for fn in [test_parse_event, test_team_entries, test_devig, test_rank]:
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    raise SystemExit(1 if FAIL else 0)
