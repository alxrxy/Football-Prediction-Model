"""Tests for the read-only P33 inactives probe (src/probe_inactives.py).

    python -m tests.test_probe_inactives
"""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src import http, probe_inactives as pi

PASS, FAIL = 0, 0


def check(label: str, got, want) -> None:
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got {got!r}, want {want!r}")


KICK = datetime(2026, 10, 4, 17, 0, tzinfo=timezone.utc)
GAME = {"game_id": "2026_04_PIT_CLE", "season": 2026, "week": 4, "home_team": "CLE", "away_team": "PIT",
        "kickoff_time": KICK.isoformat()}
LATE = {**GAME, "game_id": "2026_04_LATE", "home_team": "SEA", "away_team": "LAC",
        "kickoff_time": (KICK + timedelta(hours=4)).isoformat()}


class FakeStore:
    def __init__(self):
        self.writes = 0

    def select(self, table, where=None):
        if table == "games":
            return [GAME, LATE]
        if table == "teams":
            return [{"team": "CLE", "full_name": "Cleveland Browns"}, {"team": "PIT", "full_name": "Pittsburgh Steelers"},
                    {"team": "SEA", "full_name": "Seattle Seahawks"}, {"team": "LAC", "full_name": "Los Angeles Chargers"}]
        if table == "injuries":
            stamp = "2026-10-03T20:00:00+00:00"
            return [
                {"player": "Joe Flacco", "team": "CLE", "status": "out", "source": "nflverse", "season": 2026, "week": 4, "pulled_at": stamp},
                {"player": "Hurt Guy", "team": "CLE", "status": "ir", "source": "nflverse", "season": 2026, "week": 4, "pulled_at": stamp},
                {"player": "Maybe Guy", "team": "CLE", "status": "questionable", "source": "nflverse", "season": 2026, "week": 4, "pulled_at": stamp},
            ]
        return []

    def upsert(self, table, rows):
        self.writes += 1

    def close(self):
        pass


def fake_get(calls):
    def get(url, params=None):
        calls.append(url)
        if url.endswith("/scoreboard"):
            return 200, {"events": [{"id": "E1", "competitions": [{"competitors": [
                {"homeAway": "home", "team": {"id": "5", "displayName": "Cleveland Browns"}},
                {"homeAway": "away", "team": {"id": "23", "displayName": "Pittsburgh Steelers"}}]}]}]}
        if url.endswith("/competitors/5/roster"):
            return 200, {"entries": [{"playerId": 1, "didNotPlay": True, "athlete": {"$ref": "ath/1"}},
                                     {"playerId": 2, "didNotPlay": False}]}
        if url.endswith("/competitors/23/roster"):
            return 404, None
        if url == "ath/1":
            return 200, {"displayName": "Joe Flacco", "position": {"abbreviation": "QB"}}
        return 404, None
    return get


def test_window_and_records():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        calls = []
        store = FakeStore()
        idle = pi.probe(lambda: pi.ReadOnlyStore(store), KICK - timedelta(hours=3.5), out, fake_get(calls))
        check("before T-3h: nothing read", (idle, calls), ([], []))
        recs = pi.probe(lambda: pi.ReadOnlyStore(store), KICK - timedelta(hours=1.5), out, fake_get(calls))
        check("one record per team in the window (late game excluded)", sorted(r["team"] for r in recs), ["CLE", "PIT"])
        cle = next(r for r in recs if r["team"] == "CLE")
        check("full list saved", cle["flagged"], [{"espn_id": "1", "player": "Joe Flacco", "position": "QB"}])
        check("lead time", cle["lead_hours"], 1.5)
        check("coverage counts out + IR, not questionable", cle["coverage"],
              {"ruled": 2, "listed": 1, "ruled_excl_ir": 1, "listed_excl_ir": 1})
        pit = next(r for r in recs if r["team"] == "PIT")
        check("unposted list recorded", (pit["http"], pit["list_size"]), (404, 0))
        lines = (out / "2026-10-04" / "reads.jsonl").read_text(encoding="utf-8").splitlines()
        check("appended to the day's file", len(lines), 2)
        n = len(calls)
        pi.probe(lambda: pi.ReadOnlyStore(store), KICK - timedelta(hours=1.25), out, fake_get(calls))
        check("athlete name from the probe's own cache on the next read", "ath/1" in calls[n:], False)
        check("no store writes", store.writes, 0)
        check("files only in the probe folder", sorted(p.name for p in out.iterdir()),
              ["2026-10-04", "athletes.json", "schedule.json"])


def test_isolation():
    ro = pi.ReadOnlyStore(FakeStore())
    for method in ("upsert", "delete", "insert"):
        try:
            getattr(ro, method)
            check(f"store.{method} blocked", False, True)
        except PermissionError:
            check(f"store.{method} blocked", True, True)
    check("default output is its own folder", pi.OUT_DIR.name, "inactives_probe")
    src = Path(pi.__file__).read_text(encoding="utf-8")
    check("never touches the live gate or the shared HTTP cache",
          [w for w in ("LOOKAHEAD_HOURS =", "get_json(", "safe_get_json", "upsert(", "_write_cache") if w in src.split('"""', 2)[2]],
          [])
    check("uses the uncached ESPN getter", pi._get.__module__, "src.ingest_inactives")
    check("http cache module untouched", hasattr(http, "_write_cache"), True)


if __name__ == "__main__":
    test_window_and_records()
    test_isolation()
    print(f"\n{PASS} passed, {FAIL} FAILED")
    sys.exit(1 if FAIL else 0)
