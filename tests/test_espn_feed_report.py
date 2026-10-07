"""P68 decision 4, C: the ESPN injury-feed report is report-only.

    python -m pytest tests/test_espn_feed_report.py

`ingest_injuries.run` must store the same rows and return the same count with the report on, off, failing inside,
or raising at the call site; the report flags exactly ESPN-only out / doubtful rows for players off the official
report who played last week, keeps them in one file, and fills the served charge and snap outcome later.
No network or database: stubs throughout.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone

import pytest

from src import espn_feed_report as C
from src import ingest_injuries as II
from src.ingest_injuries import player_key

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
OFFICIAL = [{"player": "Official Guy", "team": "PIT", "status": "out", "play_probability": 0.0, "position": "WR",
             "snap_share": 0.5, "source": "nflverse", "season": 2026, "week": 5, "sport": "nfl"}]
ESPN = [
    {"player": "Joey Porter Jr.", "team": "PIT", "status": "out", "play_probability": 0.0, "position": "CB",
     "snap_share": 0.946, "source": "espn", "season": 2026, "week": 5, "sport": "nfl"},       # stale-looking: flagged
    {"player": "Idle Backup", "team": "PIT", "status": "out", "play_probability": 0.0, "position": "CB",
     "snap_share": 0.0, "source": "espn", "season": 2026, "week": 5, "sport": "nfl"},          # no snaps last week
    {"player": "Hurt Starter", "team": "PIT", "status": "ir", "play_probability": 0.0, "position": "G",
     "snap_share": 0.9, "source": "espn", "season": 2026, "week": 5, "sport": "nfl"},          # IR: never flagged
    {"player": "Maybe Guy", "team": "PIT", "status": "questionable", "play_probability": 0.55, "position": "LB",
     "snap_share": 0.6, "source": "espn", "season": 2026, "week": 5, "sport": "nfl"},          # not out / doubtful
]
SNAPS = {(4, "PIT", player_key("PIT", "Joey Porter Jr.")): 60, (4, "PIT", player_key("PIT", "Hurt Starter")): 50,
         (4, "PIT", player_key("PIT", "Maybe Guy")): 40, (4, "PIT", player_key("PIT", "Official Guy")): 30}


class Store:
    def __init__(self):
        self.upserts = []

    def select(self, table, where=None):
        if table == "teams":
            return [{"team": "PIT"}, {"team": "CLE"}]
        if table == "games":
            return [{"game_id": "2026_05_PIT_CLE", "season": 2026, "week": 5, "home_team": "CLE", "away_team": "PIT"}]
        if table == "predictions":
            comp = {"layer2": {"away_injuries": [{"player": "Joey Porter Jr.", "points": 1.59}], "home_injuries": []}}
            return [{"game_id": "2026_05_PIT_CLE", "model_version": "baseline-v1", "components": json.dumps(comp)}]
        return []

    def upsert(self, table, rows):
        self.upserts.append((table, json.dumps([{k: v for k, v in r.items() if k != "pulled_at"} for r in rows],
                                               sort_keys=True, default=str)))
        return len(rows)

    def close(self):
        pass

    backend = "stub"


@pytest.fixture
def stub(monkeypatch):
    import copy

    import src.ingest_inactives as INA

    stores = []

    def get_store():
        s = Store()
        stores.append(s)
        return s

    monkeypatch.setattr(II.db, "get_store", get_store)
    monkeypatch.setattr(II, "_load_manual", lambda *a, **k: None)
    monkeypatch.setattr(II, "_snap_shares", lambda season: {})
    monkeypatch.setattr(II, "ingest_nfl", lambda *a, **k: copy.deepcopy(OFFICIAL))
    monkeypatch.setattr(II, "ingest_espn", lambda *a, **k: copy.deepcopy(ESPN))
    monkeypatch.setattr(INA, "run", lambda *a, **k: [])
    monkeypatch.setattr(C, "_snaps", lambda season: SNAPS)
    return stores


def _run(stores):
    n = II.run("nfl", 2026, 5)
    return n, stores[-1].upserts


def test_stored_rows_identical_on_off_failing_raising(stub, monkeypatch, tmp_path):
    monkeypatch.setattr(C, "OUT_DIR", tmp_path / "c")
    monkeypatch.setenv("ESPN_FEED_REPORT", "1")
    on = _run(stub)
    monkeypatch.setenv("ESPN_FEED_REPORT", "0")
    off = _run(stub)
    blocker = tmp_path / "blocked"
    blocker.write_text("x")
    monkeypatch.setenv("ESPN_FEED_REPORT", "1")
    monkeypatch.setattr(C, "OUT_DIR", blocker)
    failing = _run(stub)
    monkeypatch.setattr(C, "report", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    raising = _run(stub)
    assert on == off == failing == raising
    assert on[0] == 5


def test_flags_only_espn_only_out_who_played_last_week():
    hits = C.flagged(OFFICIAL, OFFICIAL + ESPN, 5, SNAPS)
    assert [h["player"] for h in hits] == ["Joey Porter Jr."]
    assert C.flagged(OFFICIAL, OFFICIAL + ESPN, 5, None) == []        # no snap data: nothing claimed


def test_file_charge_and_outcome(monkeypatch, tmp_path):
    monkeypatch.setenv("ESPN_FEED_REPORT", "1")
    final = OFFICIAL + ESPN
    assert C.report(2026, 5, OFFICIAL, final, store=Store(), out_dir=tmp_path, now=NOW, snaps=SNAPS) == 1
    rows = list(csv.DictReader((tmp_path / "flags.csv").open(encoding="utf-8")))
    assert len(rows) == 1 and rows[0]["player"] == "Joey Porter Jr." and rows[0]["outcome"] == "pending"
    assert float(rows[0]["est_charge"]) == pytest.approx(0.28 * 0.946 * 6, abs=1e-3)
    assert float(rows[0]["served_charge"]) == pytest.approx(1.59)
    # next refresh, after week 5's snaps post: he played -> one stale charged case
    later = {**SNAPS, (5, "PIT", player_key("PIT", "Joey Porter Jr.")): 55}
    C.report(2026, 6, [], [], store=Store(), out_dir=tmp_path, now=NOW, snaps=later)
    rows = list(csv.DictReader((tmp_path / "flags.csv").open(encoding="utf-8")))
    assert rows[0]["outcome"] == "played" and rows[0]["outcome_snaps"] == "55"
    assert rows[0]["times_flagged"] == "1"


def test_inputs_not_mutated_and_off_writes_nothing(monkeypatch, tmp_path):
    import copy

    final = copy.deepcopy(OFFICIAL + ESPN)
    before = json.dumps(final, sort_keys=True)
    monkeypatch.setenv("ESPN_FEED_REPORT", "1")
    C.report(2026, 5, OFFICIAL, final, out_dir=tmp_path, now=NOW, snaps=SNAPS)
    assert json.dumps(final, sort_keys=True) == before
    monkeypatch.setenv("ESPN_FEED_REPORT", "0")
    assert C.report(2026, 5, OFFICIAL, final, out_dir=tmp_path / "off", now=NOW, snaps=SNAPS) is None
    assert not (tmp_path / "off").exists()
