"""calibration/live_record.py: the metric maths on a hand-computed case, and that it cannot write."""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("live_record", Path(__file__).resolve().parents[1] / "calibration" / "live_record.py")
lr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lr)


def test_metrics_hand_computed():
    rows = [  # p_home, home_won, predicted margin, actual margin, home line
        {"p_home": 0.80, "home_won": 1, "margin_pred": 7.0, "margin_actual": 10, "market_spread": -6.0},
        {"p_home": 0.60, "home_won": 0, "margin_pred": 3.0, "margin_actual": -4, "market_spread": -2.5},
        {"p_home": 0.30, "home_won": 0, "margin_pred": -5.0, "margin_actual": -1, "market_spread": 3.0},
        {"p_home": 0.52, "home_won": 1, "margin_pred": 0.5, "margin_actual": 3, "market_spread": None},
    ]
    m = lr.metrics(rows)
    assert m["n"] == 4 and m["winner_accuracy"] == 0.75
    assert m["brier"] == pytest.approx((0.04 + 0.36 + 0.09 + 0.2304) / 4)
    assert m["log_loss"] == pytest.approx(-(math.log(0.8) + math.log(0.4) + math.log(0.7) + math.log(0.52)) / 4)
    assert m["margin_mae"] == pytest.approx((3 + 7 + 4 + 2.5) / 4)
    assert m["n_with_line"] == 3 and m["market_margin_mae"] == pytest.approx((4 + 6.5 + 2) / 3)
    assert m["market_favourite_accuracy"] == pytest.approx(2 / 3)
    by = {b["bin"]: b for b in m["calibration"]}
    assert by["0.80-1.00"]["n"] == 1 and by["0.80-1.00"]["actual"] == 1.0
    assert by["0.70-0.80"]["mean_predicted"] == pytest.approx(0.70) and by["0.70-0.80"]["actual"] == 1.0   # the 0.30 pick on the away side
    assert by["0.60-0.65"]["actual"] == 0.0 and by["0.50-0.55"]["n"] == 1


def test_collect_drops_post_kickoff_ties_and_unfinished_and_never_writes():
    games = [{"game_id": g, "sport": "nfl", "season": 2026, "kickoff_time": "2026-09-13T17:00:00+00:00", "completed": c,
              "home_points": h, "away_points": a}
             for g, c, h, a in (("A", True, 24, 17), ("B", True, 20, 20), ("C", False, None, None), ("D", True, 10, 13), ("E", True, 3, 30))]
    pred = lambda g, at: {"game_id": g, "sport": "nfl", "model_version": "baseline-v1", "generated_at": at,  # noqa: E731
                          "model_win_prob_home": 0.6, "model_margin_home": 3.0, "market_spread": -2.5}
    preds = [pred("A", "2026-09-13T15:00:00+00:00"), pred("B", "2026-09-13T15:00:00+00:00"),
             pred("C", "2026-09-13T15:00:00+00:00"), pred("D", "2026-09-13T18:30:00+00:00")]

    class Inner:
        def select(self, table, where=None):
            return {"games": games, "predictions": preds}[table]

        def upsert(self, *a, **k):
            raise AssertionError("written")

        def close(self):
            pass

    store = lr.ReadOnlyStore(Inner())
    rows, info = lr.collect(store, 2026)
    assert [r["margin_actual"] for r in rows["baseline-v1"]] == [7]            # only A: B tied, C unfinished, D stamped late
    assert info["after_kickoff"] == 1 and info["ties"] == 1
    assert info["finished_without_pregame_prediction"] == ["D", "E"]
    with pytest.raises(PermissionError):
        store.upsert("predictions", [{}])
