"""P68 decision 5: raw roster responses are logged only.

    python -m pytest tests/test_inactives_raw.py

`ingest_inactives.fetch` must return the same rows and log, byte for byte, with the raw save on, off, failing
inside, or raising at the call site; the saved file holds the response exactly as received. No network or
database: a hand-built scoreboard and rosters, and a stub store.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from src import ingest_inactives as II
from src import inactives_raw as RAW

NOW = datetime(2026, 10, 11, 16, 0, tzinfo=timezone.utc)
KICK = "2026-10-11T17:00Z"


class Store:
    def select(self, table, where=None):
        if table == "games":
            return [{"game_id": "2026_05_CLE_NYJ", "sport": "nfl", "season": 2026, "week": 5,
                     "home_team": "NYJ", "away_team": "CLE"}]
        if table == "teams":
            return [{"team": "NYJ", "full_name": "New York Jets"}, {"team": "CLE", "full_name": "Cleveland Browns"}]
        return []


def _entry(pid, name, pos_id, dnp):
    return {"playerId": pid, "displayName": name, "didNotPlay": dnp,
            "position": {"$ref": f"http://x/positions/{pos_id}?lang=en"},
            "athlete": {"$ref": f"http://x/athletes/{pid}"}}


SCOREBOARD = {"events": [{"id": "401", "date": KICK, "competitions": [{
    "status": {"type": {"state": "pre"}},
    "competitors": [{"homeAway": "home", "team": {"id": "20", "displayName": "New York Jets"}},
                    {"homeAway": "away", "team": {"id": "5", "displayName": "Cleveland Browns"}}]}]}]}
ROSTERS = {
    "20": {"entries": [_entry(1, "G. Smith", 8, False), _entry(2, "A. Player", 9, True), _entry(3, "B. Player", 29, True)]},
    "5": None,     # not posted: a 404
}


@pytest.fixture
def stub(monkeypatch):
    def fake_get(url, params=None):
        if url.endswith("/scoreboard"):
            return 200, SCOREBOARD
        team_id = url.rstrip("/").split("/")[-2]
        body = ROSTERS[team_id]
        return (200, body) if body is not None else (404, None)

    monkeypatch.setattr(II, "_get", fake_get)
    monkeypatch.setattr(II, "_athlete", lambda ref: (f"Full {ref.rsplit('/', 1)[-1]}", "WR"))


def _run():
    rows, log = II.fetch(Store(), 2026, 5, now=NOW, shares={})
    return json.dumps([rows, log], sort_keys=True)


def test_rows_identical_on_off_and_failing(stub, monkeypatch, tmp_path):
    monkeypatch.setattr(RAW, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setenv("INACTIVES_RAW", "1")
    on = _run()
    monkeypatch.setenv("INACTIVES_RAW", "0")
    off = _run()
    # a failure inside save(): the target directory is a file, so mkdir fails
    blocker = tmp_path / "blocked"
    blocker.write_text("x")
    monkeypatch.setenv("INACTIVES_RAW", "1")
    monkeypatch.setattr(RAW, "RAW_DIR", blocker)
    failing_inside = _run()
    # a failure at the call site: save() itself raises
    monkeypatch.setattr(RAW, "save", lambda **kw: (_ for _ in ()).throw(OSError("disk full")))
    raising = _run()
    assert on == off == failing_inside == raising
    rows = json.loads(on)[0]
    assert [r["player"] for r in rows] == ["Full 2", "Full 3"]


def test_saved_file_is_the_response_as_received(stub, monkeypatch, tmp_path):
    root = tmp_path / "raw"
    monkeypatch.setattr(RAW, "RAW_DIR", root)
    monkeypatch.setenv("INACTIVES_RAW", "1")
    _run()
    files = sorted(root.glob("2026_w05/2026_05_CLE_NYJ/*.json"))
    assert len(files) == 2                                  # both teams, the 404 included
    by_team = {json.loads(f.read_text(encoding="utf-8"))["team"]: json.loads(f.read_text(encoding="utf-8")) for f in files}
    assert by_team["NYJ"]["body"] == ROSTERS["20"] and by_team["NYJ"]["http"] == 200
    assert by_team["CLE"]["body"] is None and by_team["CLE"]["http"] == 404
    assert by_team["NYJ"]["lead_hours"] == 1.0 and by_team["NYJ"]["origin"] == "live"
    index = (root / "index.csv").read_text(encoding="utf-8").splitlines()
    assert index[0].startswith("read_at,") and len(index) == 3
    assert ",2,1.0,live," in index[1] or ",2,1.0,live," in index[2]   # NYJ: 3 entries, 2 flagged


def test_append_only(monkeypatch, tmp_path):
    monkeypatch.setenv("INACTIVES_RAW", "1")
    kw = dict(season=2026, week=5, game_id="g", team="T", event_id="1", url="u", http=200, body={"entries": []},
              lead_hours=1.0, root=tmp_path, now=NOW)
    a, b = RAW.save(**kw), RAW.save(**kw)
    assert a != b and a.exists() and b.exists()


def test_off_writes_nothing(monkeypatch, tmp_path):
    monkeypatch.setenv("INACTIVES_RAW", "0")
    assert RAW.save(season=2026, week=5, game_id="g", team="T", event_id="1", url="u", http=200, body={},
                    lead_hours=1.0, root=tmp_path, now=NOW) is None
    assert not any(tmp_path.iterdir())


def test_nothing_reads_the_raw_files():
    """Logging only: no module outside the writer and its caller refers to the raw store."""
    import pathlib

    src = pathlib.Path(II.__file__).parent
    users = [p.name for p in src.glob("*.py") if "inactives_raw" in p.read_text(encoding="utf-8")]
    assert sorted(users) == ["inactives_raw.py", "ingest_inactives.py"]
