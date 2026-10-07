"""P68 decision 5: keep every raw ESPN roster response that `ingest_inactives.fetch` reads. Logging only.

Until now only the parsed inactive rows were stored, so a disputed read (the 10/1 TNF stale lists) could not be
re-examined: a roster entry's `didNotPlay`, its position and the whole list are gone once parsed. This writes, for
each roster call, the HTTP status and the body exactly as received (the decoded JSON, or null), with the game, team,
read time and lead to kickoff, to

    data/inactives_raw/<season>_w<WW>/<game_id>/<team>_<read stamp>.json     (+ one row in data/inactives_raw/index.csv)

Isolation, by construction:
- Nothing reads these files. `fetch` passes the response it already holds and ignores the return value; the parsed
  rows, the log and everything downstream are the same with this on, off or failing (tests/test_inactives_raw.py).
- Every failure (disk, permissions, an unserialisable body) is caught here and printed as one warning line; it
  never raises into the refresh.
- No extra request: it stores the response `fetch` already made.
`INACTIVES_RAW=0` turns it off. `data/` is gitignored, so the files are local (OneDrive-backed), like P67's archive.
"""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from . import config

RAW_DIR = config.DATA_DIR / "inactives_raw"
INDEX_FIELDS = ["read_at", "season", "week", "game_id", "team", "event_id", "http", "entries", "flagged",
                "lead_hours", "origin", "file"]


def enabled() -> bool:
    return os.getenv("INACTIVES_RAW", "1").strip().lower() not in ("0", "false", "off", "no")


def save(*, season: int, week: int, game_id: str, team: str, event_id: str, url: str, http: int | None,
         body: dict | None, lead_hours: float | None, origin: str = "live",
         root: Path | None = None, now: datetime | None = None) -> Path | None:
    """Write one roster read. Returns the file path, or None when off or on any failure (never raises)."""
    if not enabled():
        return None
    try:
        root = root or RAW_DIR
        now = now or datetime.now(timezone.utc)
        stamp = now.strftime("%Y%m%dT%H%M%S%fZ")
        folder = root / f"{int(season)}_w{int(week):02d}" / str(game_id)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{team}_{stamp}.json"
        n = 2
        while path.exists():                       # append-only: never overwrite a read
            path = folder / f"{team}_{stamp}_{n}.json"
            n += 1
        entries = (body.get("entries") or []) if isinstance(body, dict) else []
        flagged = sum(1 for x in entries if isinstance(x, dict) and x.get("didNotPlay"))
        record = {"read_at": now.isoformat(), "season": season, "week": week, "game_id": game_id, "team": team,
                  "event_id": event_id, "url": url, "http": http, "lead_hours": lead_hours, "origin": origin,
                  "body": body}
        path.write_text(json.dumps(record), encoding="utf-8")
        index = root / "index.csv"
        new = not index.exists()
        with index.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=INDEX_FIELDS)
            if new:
                w.writeheader()
            w.writerow({"read_at": now.isoformat(), "season": season, "week": week, "game_id": game_id,
                        "team": team, "event_id": event_id, "http": http, "entries": len(entries),
                        "flagged": flagged, "lead_hours": lead_hours, "origin": origin,
                        "file": str(path.relative_to(root))})
        return path
    except Exception as exc:  # noqa: BLE001 - logging only; a failed save must never stop a refresh
        try:
            print(f"  [warn] P68 raw roster not saved ({game_id} {team}): {type(exc).__name__}: {exc}")
        except Exception:  # noqa: BLE001
            pass
        return None
