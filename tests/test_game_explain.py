"""Game explanations: display only, tied to the served number.

    python -m tests.test_game_explain
"""
from __future__ import annotations

import sys

from src import game_explain as ge

PASS, FAIL = 0, 0


def check(label, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got {got!r}, want {want!r}")


# TEN @ NYG as served 2026-09-25: (7.0 + 1.9 - 0.12 + 0.34 - 1.52) x 0.9478 = 7.2
LAYERS = {"home_field": 1.9, "rest": -0.12, "travel": 0.34, "injury": -1.52, "wind_factor": 0.9478,
          "home_rest_days": 6, "away_rest_days": 7, "away_travel_miles": 757.0, "wind_mph": 23.7,
          "home_injury_points": -2.58, "away_injury_points": -1.06}


def game(margin=7.2, injuries=None):
    return {"game_id": "2026_03_TEN_NYG", "home": "NYG", "away": "TEN", "neutral": False,
            "baseline": {"margin_home": margin, "market_spread": -2.5, "layers": LAYERS,
                         "layer1": {"baseline_margin": 7.0}},
            "ml": {"margin_home": 4.36},
            "injuries": injuries or {"home": [], "away": []}}


def test_factors_reconcile_with_served_margin():
    f = ge.factors(game())
    check("factors built", f is not None, True)
    check("favoured team", f["favoured"], "NYG")
    check("weather is the compression, not a flat add", f["parts"]["weather"], -0.4)
    check("parts add back to the margin", abs(sum(f["parts"].values()) - 7.2) <= 0.15, True)
    check("gap to market", f["gap_to_market"], 4.7)


def test_breakdown_that_does_not_reconcile_gets_no_note():
    check("a margin the parts can't produce -> None", ge.factors(game(margin=9.9)), None)
    check("no baseline -> None", ge.factors({"home": "A", "away": "B", "baseline": None}), None)


def test_rating_split_offence_defence():
    ratings = {"NYG": {"off_epa": 0.02, "def_epa": 0.05}, "TEN": {"off_epa": -0.05, "def_epa": 0.0911}}
    s = ge.factors(game(), ratings)["rating_split"]
    check("offence + defence = rating gap", abs(s["offence"] + s["defence"] - 7.0) <= 0.1, True)


def test_caveats():
    inj = {"home": [{"player": "Rob Beal Jr.", "position": "DE", "points": 0.6},
                    {"player": "Robert Beal Jr.", "position": "DE", "points": 0.5},
                    {"player": "Jaxson Dart", "position": "QB", "points": 3.4, "status": "ir"}],
           "away": [{"player": "Micah Robinson", "position": "CB", "points": 0.4, "status": "questionable",
                     "play_prob": 0.55}]}
    c = " ".join(ge.factors(game(injuries=inj), prior=0.88)["caveats"])
    check("P43 duplicate named", "Rob Beal Jr. / Robert Beal Jr." in c, True)
    check("QB generic charge names the player", "NYG QB Jaxson Dart" in c, True)
    check("flat 55% names the player with no practice report", "Micah Robinson (TEN, questionable)" in c, True)
    inj["away"][0]["practice"] = "limited"
    c = " ".join(ge.factors(game(injuries=inj), prior=0.88)["caveats"])
    check("questionable + limited practice is not called the flat default", "flat 55%" in c, False)
    check("prior share rounded to 10%", "about 90%" in c, True)
    # P22: the caveat matches the rating actually served.
    from src import config
    saved = config.RATING_OPPONENT_ADJUST
    try:
        config.RATING_OPPONENT_ADJUST = True
        c = " ".join(ge.factors(game(injuries=inj), prior=0.88)["caveats"])
        check("P22 on: says adjusted for opponents", "adjusted for the opponents it has faced" in c, True)
        check("P22 on: says last season is shrunk", "shrunk well toward average" in c, True)
        check("P22 on: never says not adjusted", "not adjusted for opponents" in c, False)
        config.RATING_OPPONENT_ADJUST = False
        c = " ".join(ge.factors(game(injuries=inj), prior=0.88)["caveats"])
        check("P22 off: old caveat", "not adjusted for opponents" in c, True)
    finally:
        config.RATING_OPPONENT_ADJUST = saved


def test_prompt_names_the_team_each_factor_helps():
    line = ge.describe("g", ge.factors(game()))
    check("home factor names home team", "home field 1.9 toward NYG" in line, True)
    check("negative factor names away team", "rest 0.1 toward TEN" in line, True)
    check("no signed home-team numbers", "+1.9" in line or "-0.1" in line, False)


def test_number_guard():
    src = "model: NYG by 7.2 over TEN | market: NYG by 2.5 | injuries cost 5.5"
    check("given numbers pass", ge.unsupported_numbers("NYG by 7.2, about 7, market 2.5", src), [])
    check("rounded whole number passes", ge.unsupported_numbers("injuries cost about 6 points", src), [])
    check("invented figure caught", ge.unsupported_numbers("a 9.5-point edge", src), [9.5])
    check("invented small decimal caught", ge.unsupported_numbers("worth 3.5 points", src), [3.5])
    check("small count passes", ge.unsupported_numbers("two factors, 2 of them", src), [])
    check("a team name with digits is not a figure", ge.unsupported_numbers("the 49ers by 7.2", src), [])


def test_kicked_off_games_get_no_note():
    g = game()
    g["kickoff"] = "2026-09-01T17:00:00+00:00"
    ge.attach([g], call_claude=False)
    check("played game keeps no explanation", g.get("explanation"), None)


if __name__ == "__main__":
    for t in [v for k, v in dict(globals()).items() if k.startswith("test_")]:
        t()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
