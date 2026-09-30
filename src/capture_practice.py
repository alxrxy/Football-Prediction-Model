"""Forward-only capture of the weekly injury report as it fills in (P47).

    python -m src.capture_practice            # current season
    python -m src.capture_practice --season 2026

nflverse publishes one injury file per season and rewrites it through the
week: each player carries one `practice_status`, that day's. The file has no
history, so Wednesday's DNP is gone once Thursday's LP lands, and no source we
can use can supply it later. Saving the raw file every evening keeps each day.

Capture only: nothing reads these files yet. The raw bytes are kept exactly as
downloaded, and a new file is written only when they change. Every run, change
or not, appends a line to `manifest.csv`, so a gap in the record means a run
that didn't happen, not a quiet day.

The official team injury pages would show all three days in one table, but
their terms forbid automated downloading (see P47's row), so they are not used.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from . import config

URL = "https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_{season}.parquet"
OUT_DIR = Path(config.ROOT) / "data" / "practice_snapshots"
MANIFEST_FIELDS = ["checked_at", "season", "result", "bytes", "sha256", "rows", "max_week", "file", "error"]


def fetch(season: int) -> bytes:
    req = urllib.request.Request(URL.format(season=season), headers={"User-Agent": "football-predictor"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def _summary(raw: bytes) -> tuple[int | None, int | None]:
    """Row count and latest week, for the manifest. A file that won't parse
    is still saved; the summary is just left blank."""
    try:
        import pandas as pd

        df = pd.read_parquet(io.BytesIO(raw))
        return len(df), (int(df["week"].max()) if len(df) else None)
    except Exception:  # noqa: BLE001 - summary only
        return None, None


def _last_sha(season_dir: Path) -> str | None:
    saved = sorted(season_dir.glob("injuries_*.parquet"))
    return hashlib.sha256(saved[-1].read_bytes()).hexdigest() if saved else None


def capture(season: int, out_dir: Path = OUT_DIR, fetcher=fetch, now: datetime | None = None) -> dict:
    """One check: save the file if it changed, and log the check either way."""
    now = now or datetime.now(timezone.utc)
    season_dir = out_dir / str(season)
    season_dir.mkdir(parents=True, exist_ok=True)
    row = {k: "" for k in MANIFEST_FIELDS}
    row.update(checked_at=now.isoformat(timespec="seconds"), season=season)
    try:
        raw = fetcher(season)
    except Exception as exc:  # noqa: BLE001 - logged, and the exit code says so
        row.update(result="error", error=f"{type(exc).__name__}: {exc}"[:300])
    else:
        sha = hashlib.sha256(raw).hexdigest()
        rows, max_week = _summary(raw)
        row.update(bytes=len(raw), sha256=sha, rows=rows if rows is not None else "",
                   max_week=max_week if max_week is not None else "")
        if sha == _last_sha(season_dir):
            row["result"] = "unchanged"
        else:
            name = f"injuries_{now.strftime('%Y%m%dT%H%M%SZ')}.parquet"
            (season_dir / name).write_bytes(raw)
            row.update(result="saved", file=name)

    manifest = out_dir / "manifest.csv"
    new = not manifest.exists()
    with manifest.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=MANIFEST_FIELDS)
        if new:
            writer.writeheader()
        writer.writerow(row)
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description="Save today's nflverse injury file (P47 capture).")
    parser.add_argument("--season", type=int, default=datetime.now(timezone.utc).year)
    args = parser.parse_args()
    row = capture(args.season)
    print(f"[practice capture] {row['checked_at']} season {row['season']}: {row['result']}"
          + (f" -> {row['file']}" if row["file"] else "")
          + (f" ({row['rows']} rows, through week {row['max_week']})" if row["rows"] != "" else "")
          + (f" {row['error']}" if row["error"] else ""))
    return 1 if row["result"] == "error" else 0


if __name__ == "__main__":
    sys.exit(main())
