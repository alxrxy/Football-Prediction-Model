"""Tests for stored NFL kickoff times (P80).

    python -m tests.test_kickoff_times

nflverse schedules give US Eastern wall-clock times. A fixed UTC offset stored
every game after the clocks changed one hour early, and each kickoff gate then
treated unstarted games as already started.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

import pandas as pd

from src import clv, config, ingest_nflverse as nv

PASS, FAIL = 0, 0


def check(label: str, got, want) -> None:
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got {got!r}, want {want!r}")


def utc(*parts) -> datetime:
    return datetime(*parts, tzinfo=timezone.utc)


class Store:
    def __init__(self):
        self.written = {}

    def upsert(self, table, rows):
        self.written[table] = rows


def schedule_row(game_id, day, gametime, **extra) -> dict:
    return {"game_id": game_id, "season": 2026, "week": 8, "game_type": "REG", "home_team": "LA",
            "away_team": "LAC", "gameday": day, "gametime": gametime, "location": "Home",
            "stadium": "SoFi Stadium", "div_game": 0, **extra}


def test_daylight_time() -> None:
    check("10/25 13:00 ET is UTC-4", nv._kickoff({"gameday": "2026-10-25", "gametime": "13:00"}),
          utc(2026, 10, 25, 17, 0))
    check("TNF 10/29 20:15 ET crosses midnight UTC", nv._kickoff({"gameday": "2026-10-29", "gametime": "20:15"}),
          utc(2026, 10, 30, 0, 15))


def test_standard_time() -> None:
    check("11/1 16:05 ET is UTC-5", nv._kickoff({"gameday": "2026-11-01", "gametime": "16:05"}),
          utc(2026, 11, 1, 21, 5))
    check("SNF 11/1 20:20 ET", nv._kickoff({"gameday": "2026-11-01", "gametime": "20:20"}),
          utc(2026, 11, 2, 1, 20))
    check("MNF 11/2 20:15 ET", nv._kickoff({"gameday": "2026-11-02", "gametime": "20:15"}),
          utc(2026, 11, 3, 1, 15))
    check("January playoff 13:00 ET", nv._kickoff({"gameday": "2027-01-09", "gametime": "13:00"}),
          utc(2027, 1, 9, 18, 0))


def test_missing_time_defaults_to_1pm_eastern() -> None:
    check("no gametime", nv._kickoff({"gameday": "2026-11-08", "gametime": None}), utc(2026, 11, 8, 18, 0))
    check("no gameday", nv._kickoff({"gameday": None, "gametime": "13:00"}), None)


def test_no_fixed_offset_left() -> None:
    check("fixed offset constant is gone", hasattr(nv, "ET_UTC_OFFSET_HOURS"), False)


def test_schedule_reingest_cannot_restore_bad_times() -> None:
    frame = pd.DataFrame([schedule_row("2026_08_LAC_LA", "2026-11-01", "16:05"),
                          schedule_row("2026_08_CHI_SEA", "2026-11-02", "20:15")])
    store = Store()
    nv.ingest_games(store, frame, 2026)
    got = {r["game_id"]: r["kickoff_time"] for r in store.written["games"]}
    check("LAC @ LA", got["2026_08_LAC_LA"], "2026-11-01T21:05:00+00:00")
    check("CHI @ SEA", got["2026_08_CHI_SEA"], "2026-11-03T01:15:00+00:00")


def test_clv_scoreboard_day_is_the_eastern_date() -> None:
    check("SNF at 01:20Z is Sunday in the East", clv.eastern_day(utc(2026, 11, 2, 1, 20)), "20261101")
    check("EDT SNF at 00:20Z is Sunday in the East", clv.eastern_day(utc(2026, 10, 26, 0, 20)), "20261025")
    check("noon slate", clv.eastern_day(utc(2026, 11, 1, 18, 0)), "20261101")


def test_named_zones() -> None:
    check("eastern", str(config.EASTERN), "America/New_York")
    check("central", str(config.CENTRAL), "America/Chicago")


def main() -> int:
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(name)
            try:
                fn()
            except Exception as exc:  # noqa: BLE001 - reported as a failure, the rest still run
                global FAIL
                FAIL += 1
                print(f"  FAIL  {name}: {exc!r}")
    print(f"{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
