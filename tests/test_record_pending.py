"""P50: the Record page must show a predicted, not-yet-played game as pending.

    python -m pytest tests/test_record_pending.py

`export_dashboard._weeks` builds each week's rows from graded predictions only,
so a game with a stored prediction that hasn't been played yet (Monday night,
while Sunday is graded) comes out `predicted: False` and the page labels it
"not predicted - kicked off before the first pipeline run". Found 2026-09-28
on PHI @ CHI.

Marked xfail(strict=True) until the fix ships with the week-4 batch: it
documents the bug without failing the suite, and fails as XPASS the moment
the fix lands, as the reminder to remove the marker. The fix is expected to
pass the week's predicted game ids into `_weeks` (`predicted_ids=`) and add
a `pending` flag per row; `grade.py` is not involved.

No network or database: hand-built rows.
"""

from __future__ import annotations

import pytest

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


@pytest.mark.xfail(strict=True, raises=(AssertionError, TypeError),
                   reason="P50 display bug; fix ships with the week-4 batch")
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
