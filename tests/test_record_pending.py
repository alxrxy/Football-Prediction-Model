"""P50: the Record page must show a predicted, not-yet-played game as pending.

    python -m pytest tests/test_record_pending.py

`export_dashboard._weeks` builds each week's rows from graded predictions only,
so a game with a stored prediction that hasn't been played yet (Monday night,
while Sunday is graded) comes out `predicted: False` and the page labels it
"not predicted - kicked off before the first pipeline run". Found 2026-09-28
on PHI @ CHI.

Fixed 2026-09-29: `_weeks` takes the stored prediction ids (`predicted_ids=`)
and each row carries `pending`; `grade.py` is not involved.

No network or database: hand-built rows.
"""

from __future__ import annotations

from src.export_dashboard import _weeks

GAMES = {
    # Sunday: played and graded.
    "2026_03_KC_MIA": {
        "game_id": "2026_03_KC_MIA", "season": 2026, "week": 3,
        "kickoff_time": "2026-09-27T17:00:00+00:00", "home_team": "MIA", "away_team": "KC",
        "home_points": 10, "away_points": 24, "is_neutral_site": False, "completed": True,
    },
    # Monday: predicted, kickoff in the future, not graded.
    "2026_03_PHI_CHI": {
        "game_id": "2026_03_PHI_CHI", "season": 2026, "week": 3,
        "kickoff_time": "2099-09-29T00:15:00+00:00", "home_team": "CHI", "away_team": "PHI",
        "home_points": None, "away_points": None, "is_neutral_site": False, "completed": False,
    },
}

GRADED = [{
    "game_id": "2026_03_KC_MIA", "model_version": "baseline-v1", "edge": 2.0,
    "market_spread": 10.0, "model_spread": 8.0, "model_margin_home": -8.0, "model_win_prob_home": 0.27,
    "actual_margin": -14, "actual_home_points": 10, "actual_away_points": 24, "is_value": False,
}]


def test_ungraded_game_with_prediction_and_future_kickoff_is_pending_not_unpredicted():
    week = _weeks(GRADED, GAMES, predicted_ids={"2026_03_KC_MIA", "2026_03_PHI_CHI"})[0]
    row = {g["game_id"]: g for g in week["games"]}["2026_03_PHI_CHI"]
    assert row["predicted"] is True, "a stored prediction must count as predicted"
    assert row["pending"] is True, "an unplayed game with a future kickoff is pending"
    assert week["n_predicted"] == 2


def test_graded_game_is_unchanged():
    """Guard for the fix: the graded row keeps its result (passes today)."""
    week = _weeks(GRADED, GAMES)[0]
    row = {g["game_id"]: g for g in week["games"]}["2026_03_KC_MIA"]
    assert row["predicted"] is True
    assert row["actual_margin"] == -14
    assert week["models"]["baseline-v1"]["su"]["n"] == 1


def test_week_note_is_carried_without_changing_the_record():
    """Week 4 (2026) carries its how-predicted note; weeks without one carry None."""
    from src.export_dashboard import WEEK_NOTES

    week = _weeks(GRADED, GAMES)[0]
    assert week["note"] is None
    assert WEEK_NOTES[(2026, 4)].startswith("Predicted 3–5 days before kickoff")
    games4 = {gid.replace("_03_", "_04_"): {**g, "game_id": gid.replace("_03_", "_04_"), "week": 4}
              for gid, g in GAMES.items()}
    graded4 = [{**r, "game_id": r["game_id"].replace("_03_", "_04_")} for r in GRADED]
    week4 = _weeks(graded4, games4)[0]
    assert week4["note"] == WEEK_NOTES[(2026, 4)]
    assert week4["models"] == week["models"]
