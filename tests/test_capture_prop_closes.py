"""Tests for the P61 prop closing-line capture (src/capture_prop_closes.py).

    python -m tests.test_capture_prop_closes
"""

from __future__ import annotations

import csv
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.capture_prop_closes import SCHEDULE_PATH, capture, report

PASS, FAIL = 0, 0


def check(label: str, got, want) -> None:
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got {got!r}, want {want!r}")


KICK = datetime(2026, 10, 2, 0, 15, tzinfo=timezone.utc)
EV = "sr:sport_event:71515842"


def sched(*ids):
    return {"schedules": [{"sport_event": {"id": i, "start_time": KICK.isoformat(), "competitors": [
        {"qualifier": "away", "abbreviation": "PIT"}, {"qualifier": "home", "abbreviation": "CLE"}]}}
        for i in ids]}


def props(total="45.5", removed=False, status="not_started"):
    book = {"id": "sr:book:18149", "removed": removed, "outcomes": [
        {"type": "over", "total": total, "odds_american": "-110", "removed": removed},
        {"type": "under", "total": total, "odds_american": "-110", "removed": removed}]}
    td = {"id": "sr:market:td", "is_live": False, "books": [
        {"id": "sr:book:18149", "removed": removed, "outcomes": [{"player_id": "p1", "odds_american": "+150"}]}]}
    return {"generated_at": "x", "sport_event_players_props": {
        "sport_event": {"status": status},
        "players_props": [{"player": {"id": "p1"}, "markets": [{"id": "m", "is_live": False, "books": [book]}]}],
        "players_markets": {"markets": [td]}}}


class Api:
    def __init__(self, schedule=None, event=None):
        self.calls, self.schedule, self.event = [], schedule or sched(EV), event or (lambda: props())

    def __call__(self, path):
        self.calls.append(path)
        if path == SCHEDULE_PATH:
            return self.schedule
        if isinstance(self.event, Exception):
            raise self.event
        return self.event()


def manifest(out):
    with (out / "manifest.csv").open(newline="") as f:
        return [(r["checkpoint"], r["result"]) for r in csv.DictReader(f)]


def test_quiet_pass_makes_no_call_once_schedule_cached():
    with tempfile.TemporaryDirectory() as tmp:
        out, api = Path(tmp), Api()
        capture(out, api, KICK - timedelta(hours=10))
        check("first pass reads the schedule only", api.calls, [SCHEDULE_PATH])
        capture(out, api, KICK - timedelta(hours=9))
        check("second pass within 12 h: no call", len(api.calls), 1)
        capture(out, api, KICK - timedelta(hours=10) + timedelta(hours=12, minutes=1))
        check("schedule re-read after 12 h", api.calls.count(SCHEDULE_PATH), 2)


def test_checkpoint_saved_once_with_counts():
    with tempfile.TemporaryDirectory() as tmp:
        out, api = Path(tmp), Api()
        rows = capture(out, api, KICK - timedelta(minutes=10))
        check("t-15 taken at T-10", [(r["checkpoint"], r["result"]) for r in rows], [("t-15", "saved")])
        check("counts both blocks", (rows[0]["book_lines"], rows[0]["removed"], rows[0]["is_live"]), (2, 0, 0))
        check("raw file written", (out / rows[0]["file"]).exists(), True)
        capture(out, api, KICK - timedelta(minutes=2))
        check("same window again: not re-pulled", manifest(out), [("t-15", "saved")])


def test_missed_window_logged_not_silent():
    with tempfile.TemporaryDirectory() as tmp:
        out, api = Path(tmp), Api()
        capture(out, api, KICK - timedelta(hours=2))          # task starts well before kickoff
        capture(out, api, KICK - timedelta(minutes=10))
        rows = capture(out, api, KICK + timedelta(minutes=20))
        check("t+0 missed, t+15 saved", [(r["checkpoint"], r["result"]) for r in rows],
              [("t+0", "missed"), ("t+15", "saved")])


def test_windows_before_first_pass_not_called_missed():
    with tempfile.TemporaryDirectory() as tmp:
        out, api = Path(tmp), Api()
        rows = capture(out, api, KICK + timedelta(minutes=20))   # first ever pass, mid-game
        check("only t+15; earlier windows predate the capture", [(r["checkpoint"], r["result"]) for r in rows],
              [("t+15", "saved")])


def test_error_logged_not_raised():
    with tempfile.TemporaryDirectory() as tmp:
        out, api = Path(tmp), Api(event=RuntimeError("503"))
        rows = capture(out, api, KICK - timedelta(minutes=10))
        check("error recorded", rows[0]["result"].startswith("error: 503"), True)


def test_ended_game_kept_after_schedule_drops_it():
    with tempfile.TemporaryDirectory() as tmp:
        out, api = Path(tmp), Api()
        capture(out, api, KICK - timedelta(minutes=10))
        api.schedule = sched()                                  # game gone from the schedule
        capture(out, api, KICK + timedelta(hours=13))           # stale -> re-read, game dropped
        rows = capture(out, api, KICK + timedelta(hours=24, minutes=5))
        check("t+24h still taken", [(r["checkpoint"], r["result"]) for r in rows if r["result"] == "saved"],
              [("t+24h", "saved")])


def test_report_counts_changes_between_checkpoints():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        api = Api(event=lambda: props())
        capture(out, api, KICK - timedelta(minutes=10))
        api.event = lambda: props(total="47.5", removed=True, status="live")
        capture(out, api, KICK + timedelta(minutes=5))
        rep = report(out).splitlines()
        check("t-15 has no previous", rep[0].endswith("changed_vs_prev="), True)
        check("t+0 shows both lines changed", rep[1].endswith("changed_vs_prev=2"), True)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            print(name)
            fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
