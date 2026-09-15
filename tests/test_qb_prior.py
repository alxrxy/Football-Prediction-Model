"""QB-conditional prior season (P13).

    python -m tests.test_qb_prior
"""

from __future__ import annotations

import math

import pandas as pd

from src.build_training import EPA_SEASON_CARRY, RollingEpa
from src.qb_prior import conditional_offense, expected_starters, game_starters

FAILED = []


def check(label, got, want, tol=1e-9):
    ok = (math.isclose(got, want, abs_tol=tol) if isinstance(want, float) and got is not None
          else got == want)
    print(f"  {'ok ' if ok else 'FAIL'} {label}: {got!r}" + ("" if ok else f" (want {want!r})"))
    if not ok:
        FAILED.append(label)


def schedule():
    nan = float("nan")
    return pd.DataFrame({
        "game_id": ["2025_01_KC_BUF", "2025_02_DEN_KC", "2025_03_KC_LV", "2025_04_KC_NYJ"],
        "season": [2025, 2025, 2025, 2025],
        "week": [1, 2, 3, 4],
        "gameday": ["2025-09-07", "2025-09-14", "2025-09-21", "2025-09-28"],
        "home_team": ["BUF", "KC", "LV", "NYJ"],
        "away_team": ["KC", "DEN", "KC", "KC"],
        "home_score": [20, 24, 17, nan],
        "home_qb_id": ["allen", "starter", "lvqb", "nyjqb"],
        "away_qb_id": ["starter", "nix", "backup", "starter"],
    })


def test_starters():
    s = schedule()
    starters = game_starters(s)
    check("home starter", starters[("2025_02_DEN_KC", "KC")], "starter")
    check("away starter", starters[("2025_03_KC_LV", "KC")], "backup")
    exp = expected_starters(s, 2025)
    check("next game's listed starter beats the last one played", exp["KC"], "starter")
    check("team with no unplayed game keeps its latest starter", exp["DEN"], "nix")


def test_conditional_offense():
    rows = []
    for g in range(6):
        qb = "starter" if g < 4 else "backup"
        epa = 0.1 if qb == "starter" else -0.3
        rows += [{"game_id": f"g{g}", "posteam": "KC", "epa": epa}] * 60
    plays = pd.DataFrame(rows)
    starters = {(f"g{g}", "KC"): ("starter" if g < 4 else "backup") for g in range(6)}
    got = conditional_offense(plays, starters, "KC", "starter")
    check("mean over the starter's games only", got[0], 0.1, tol=1e-6)
    check("his plays and starts", got[1:], (240, 4))
    check("two starts is too few to condition on", conditional_offense(plays, starters, "KC", "backup"), None)
    check("a new starter keeps the whole season", conditional_offense(plays, starters, "KC", "newguy"), None)


def test_rolling_epa_condition():
    epa = RollingEpa()
    epa.start_season(2025)
    for g in range(6):
        qb, mean = ("starter", 0.1) if g < 4 else ("backup", -0.3)
        epa.update("KC", mean * 60, 60, 0.0, 60, qb=qb)
    epa.start_season(2026)
    carried_n = epa.off_n["KC"]
    check("carry scales volume", carried_n, 360 * EPA_SEASON_CARRY)

    epa.condition_on_starter("KC", "starter")
    check("carried offense restated at the starter's mean", epa.off_sum["KC"] / epa.off_n["KC"], 0.1, tol=1e-9)
    check("volume unchanged", epa.off_n["KC"], carried_n)

    before = epa.off_sum["KC"]
    epa.condition_on_starter("KC", "backup")
    check("only the first game of a season conditions", epa.off_sum["KC"], before)

    other = RollingEpa()
    other.start_season(2025)
    other.update("NYJ", -6.0, 60, 0.0, 60, qb="old")
    other.start_season(2026)
    was = other.off_sum["NYJ"]
    other.condition_on_starter("NYJ", "new")
    check("a starter without enough starts leaves it alone", other.off_sum["NYJ"], was)


if __name__ == "__main__":
    for fn in [test_starters, test_conditional_offense, test_rolling_epa_condition]:
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{'ALL PASSED' if not FAILED else f'{len(FAILED)} FAILED: {FAILED}'}")
    raise SystemExit(1 if FAILED else 0)
