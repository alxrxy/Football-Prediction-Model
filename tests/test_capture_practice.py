"""Tests for the P47 practice-report capture (src/capture_practice.py).

    python -m tests.test_capture_practice
"""

from __future__ import annotations

import csv
import io
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from src.capture_practice import capture

PASS, FAIL = 0, 0


def check(label: str, got, want) -> None:
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got {got!r}, want {want!r}")


T0 = datetime(2026, 9, 30, 3, 0, tzinfo=timezone.utc)


def parquet(statuses: list[str]) -> bytes:
    buf = io.BytesIO()
    pd.DataFrame({"week": [4] * len(statuses), "full_name": [f"P{i}" for i in range(len(statuses))],
                  "practice_status": statuses}).to_parquet(buf)
    return buf.getvalue()


def test_saves_on_change_and_logs_every_run():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        wed, thu = parquet(["Did Not Participate In Practice"]), parquet(["Limited Participation in Practice"])
        r1 = capture(2026, out, lambda s: wed, T0)
        r2 = capture(2026, out, lambda s: wed, T0 + timedelta(hours=24))
        r3 = capture(2026, out, lambda s: thu, T0 + timedelta(hours=48))

        def boom(season):
            raise ConnectionError("down")

        r4 = capture(2026, out, boom, T0 + timedelta(hours=72))
        check("first run saved", r1["result"], "saved")
        check("identical bytes -> unchanged, no file", r2["result"], "unchanged")
        check("changed bytes -> saved", r3["result"], "saved")
        check("fetch failure logged as error", (r4["result"], r4["error"].startswith("ConnectionError")), ("error", True))
        files = sorted(p.name for p in (out / "2026").glob("*.parquet"))
        check("two files kept", files, ["injuries_20260930T030000Z.parquet", "injuries_20261002T030000Z.parquet"])
        check("raw bytes kept exactly", (out / "2026" / files[1]).read_bytes(), thu)
        rows = list(csv.DictReader((out / "manifest.csv").open(encoding="utf-8")))
        check("every run in the manifest", [r["result"] for r in rows], ["saved", "unchanged", "saved", "error"])
        check("manifest summary", (rows[0]["rows"], rows[0]["max_week"]), ("1", "4"))


if __name__ == "__main__":
    test_saves_on_change_and_logs_every_run()
    print(f"\n{PASS} passed, {FAIL} FAILED")
    sys.exit(1 if FAIL else 0)
