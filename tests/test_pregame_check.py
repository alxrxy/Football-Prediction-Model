"""P71 reminder-only pregame check: the pure `due` rule and the read-only run."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src import pregame_check
from src.probe_inactives import ReadOnlyStore

KICK = "2026-10-16T00:15:00+00:00"
GAME = {"game_id": "2026_06_SEA_DEN", "home_team": "DEN", "away_team": "SEA", "kickoff_time": KICK}
at = lambda s: datetime.fromisoformat(s).replace(tzinfo=timezone.utc)  # noqa: E731


def test_fires_at_t4h_and_t90m_when_no_prediction():
    assert [a["checkpoint"] for a in pregame_check.due([GAME], [], at("2026-10-15T20:15:00"), set())] == ["T-4h"]
    got = pregame_check.due([GAME], [], at("2026-10-15T22:45:00"), set())
    assert [a["checkpoint"] for a in got] == ["T-4h", "T-90m"]


def test_silent_before_t4h_after_kickoff_and_once_alerted():
    assert pregame_check.due([GAME], [], at("2026-10-15T20:00:00"), set()) == []
    assert pregame_check.due([GAME], [], at("2026-10-16T00:20:00"), set()) == []
    done = {"2026_06_SEA_DEN|T-4h", "2026_06_SEA_DEN|T-90m"}
    assert pregame_check.due([GAME], [], at("2026-10-15T23:00:00"), done) == []


def test_silent_when_a_prediction_exists_but_not_one_made_later():
    pred = {"game_id": "2026_06_SEA_DEN", "model_version": "baseline-v1", "generated_at": "2026-10-15T21:00:00+00:00"}
    assert pregame_check.due([GAME], [pred], at("2026-10-15T23:00:00"), set()) == []
    # a prediction stamped after the pass is invisible to it (dry runs at a past moment)
    assert len(pregame_check.due([GAME], [pred], at("2026-10-15T20:30:00"), set())) == 1
    ml = {**pred, "model_version": "ml-v1"}
    assert len(pregame_check.due([GAME], [ml], at("2026-10-15T23:00:00"), set())) == 2


class _Fake:
    def __init__(self, games, preds):
        self.t = {"games": games, "predictions": preds}

    def select(self, table, where=None):
        return [dict(r) for r in self.t[table]]

    def upsert(self, *a, **k):
        raise AssertionError("pregame_check must not write")


def test_run_is_read_only_and_writes_state(tmp_path, monkeypatch):
    monkeypatch.setattr(pregame_check, "ALERT_LOG", tmp_path / "alerts.log")
    factory = lambda: ReadOnlyStore(_Fake([{**GAME, "sport": "nfl"}], []))  # noqa: E731
    got = pregame_check.run(at("2026-10-15T23:00:00"), out_dir=tmp_path, store_factory=factory, notify=False)
    assert len(got) == 2
    assert (tmp_path / "alerts.log").read_text(encoding="utf-8").count("PREGAME") == 2
    again = pregame_check.run(at("2026-10-15T23:30:00"), out_dir=tmp_path, store_factory=factory, notify=False)
    assert again == []


def test_dry_run_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(pregame_check, "ALERT_LOG", tmp_path / "alerts.log")
    factory = lambda: ReadOnlyStore(_Fake([{**GAME, "sport": "nfl"}], []))  # noqa: E731
    assert len(pregame_check.run(at("2026-10-15T23:00:00"), dry_run=True, out_dir=tmp_path,
                                 store_factory=factory, notify=False)) == 2
    assert not (tmp_path / "alerts.log").exists() and not (tmp_path / "state.json").exists()


def test_read_only_store_blocks_writes():
    with pytest.raises(PermissionError):
        ReadOnlyStore(_Fake([], [])).upsert("predictions", [])
