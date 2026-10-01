"""P67 phase A: keep every served props ranking, so the weekly props record can
grade each game against the last list actually served before its kickoff.

    python -m src.props_archive --status       # what the archive holds, by week
    python -m src.props_archive --seed-p62     # copy in the week-4+ rankings the P62 shadow kept

`props.run` overwrites data/props.json at every ranking; after writing it, it
calls `archive()`, which stores the exact bytes on disk at
data/props_archive/<season>_w<WW>/<stamp>.json and appends a row to
data/props_archive/index.csv. The lines file that ranking read is kept once per
distinct content (lines/<sha12>.json). Append-only: nothing is overwritten, a
stamp collision gets a suffix. Nothing served reads the archive; the record
builder (phase B) is its only reader. data/ is gitignored, so the archive is
local (OneDrive-backed), like the P58 archive.

Criteria A1-A5: calibration-log.md, 2026-10-01 'P67 scoped'.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from . import config

ARCHIVE_DIR = config.DATA_DIR / "props_archive"
INDEX_FIELDS = ["stamp", "season", "week", "generated_at", "lines_pulled_at", "git_commit", "line_source",
                "served_sha256", "lines_sha256", "top", "more", "held_out", "started", "origin", "file"]
LINE_SOURCE = "odds_api"   # the only served source until a P62 switch (S5c marks the record then)


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def git_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=config.ROOT, capture_output=True,
                             text=True, timeout=5)
        return out.stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001 - a missing commit never blocks the archive
        return "unknown"


def _stamp(generated_at: str | None) -> str:
    try:
        dt = datetime.fromisoformat(str(generated_at).replace("Z", "+00:00")).astimezone(timezone.utc)
    except (TypeError, ValueError):
        dt = datetime.now(timezone.utc)
    return f"{dt:%Y%m%dT%H%M%SZ}"


def _write_new(folder: Path, stem: str, data: bytes) -> Path:
    """Write to a file that does not exist yet; never overwrite (A3)."""
    folder.mkdir(parents=True, exist_ok=True)
    for n in range(1, 1000):
        path = folder / (f"{stem}.json" if n == 1 else f"{stem}_{n}.json")
        try:
            with path.open("xb") as f:
                f.write(data)
            return path
        except FileExistsError:
            continue
    raise RuntimeError(f"no free archive name for {stem} in {folder}")


def archive(served: bytes, lines: bytes, *, origin: str = "live", commit: str | None = None,
            out: Path = ARCHIVE_DIR) -> Path:
    """Store one served ranking (the exact bytes of props.json) and its lines.
    Returns the archive file. Raises on failure; the caller isolates it."""
    payload = json.loads(served.decode("utf-8"))
    season, week = payload.get("season"), payload.get("week")
    folder = out / f"{season}_w{int(week):02d}" if week is not None else out / "unknown_week"
    path = _write_new(folder, _stamp(payload.get("generated_at")), served)
    lines_sha = _sha(lines) if lines else ""
    if lines:
        kept = out / "lines" / f"{lines_sha[:12]}.json"
        if not kept.exists():
            kept.parent.mkdir(parents=True, exist_ok=True)
            kept.write_bytes(lines)
    index = out / "index.csv"
    new = not index.exists()
    with index.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=INDEX_FIELDS)
        if new:
            w.writeheader()
        w.writerow({
            "stamp": path.stem, "season": season, "week": week, "generated_at": payload.get("generated_at"),
            "lines_pulled_at": payload.get("lines_pulled_at"), "git_commit": commit or git_commit(),
            "line_source": LINE_SOURCE, "served_sha256": _sha(served), "lines_sha256": lines_sha,
            "top": len(payload.get("props") or []), "more": len(payload.get("more") or []),
            "held_out": len(payload.get("held_out") or []), "started": len(payload.get("started") or []),
            "origin": origin, "file": path.relative_to(out).as_posix(),
        })
    return path


def index_rows(out: Path = ARCHIVE_DIR) -> list[dict]:
    path = out / "index.csv"
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def seed_from_p62(pulls: Path | None = None, served_now: Path | None = None, out: Path = ARCHIVE_DIR,
                  min_week: int = 4) -> list[str]:
    """A5: copy in the rankings the P62 shadow kept beside its pulls (week >= min_week).
    The shadow wrote them with json.dumps(..., default=str); each is checked to
    re-serialise to its own bytes the way props.run writes, and the newest is
    compared with the served props.json. Differences are reported, never
    normalised. Already-seeded files (same served sha) are skipped."""
    from .shadow_props_sr import OUT_DIR

    pulls = pulls or OUT_DIR / "pulls"
    served_now = served_now or config.DATA_DIR / "props.json"
    have = {r["served_sha256"] for r in index_rows(out)}
    notes = []
    found = sorted(pulls.glob("*/rank_*/props.json"), key=lambda p: p.parent.name)
    for f in found:
        b = f.read_bytes()
        payload = json.loads(b.decode("utf-8"))
        if (payload.get("week") or 0) < min_week:
            continue
        tag = f"{f.parent.parent.name}/{f.parent.name}"
        if _sha(b) in have:
            notes.append(f"{tag}: already archived, skipped")
            continue
        same = json.dumps(payload).encode("utf-8") == b
        lines_file = f.parent.parent / "odds.json"
        lines = lines_file.read_bytes() if lines_file.exists() else b""
        path = archive(b, lines, origin="p62_shadow", commit="unknown (seeded)", out=out)
        have.add(_sha(b))
        notes.append(f"{tag} -> {path.relative_to(out).as_posix()}; "
                     f"{'re-serialises byte-identically' if same else 'DIFFERS from a props.run-style re-serialisation'}")
    if found and served_now.exists():
        newest = max(found, key=lambda p: p.parent.name)
        eq = newest.read_bytes() == served_now.read_bytes()
        notes.append(f"newest shadow ranking {newest.parent.parent.name}/{newest.parent.name} "
                     f"{'==' if eq else '!='} served {served_now.name} (bytes)")
    return notes


def main() -> None:
    ap = argparse.ArgumentParser(description="P67 archive of served props rankings.")
    ap.add_argument("--seed-p62", action="store_true")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()
    if args.seed_p62:
        for n in seed_from_p62():
            print(" ", n)
    rows = index_rows()
    by_week: dict[str, list[dict]] = {}
    for r in rows:
        by_week.setdefault(f"{r['season']} week {r['week']}", []).append(r)
    print(f"{ARCHIVE_DIR}: {len(rows)} ranking(s)")
    for wk, rs in by_week.items():
        print(f"  {wk}: {len(rs)} — " + ", ".join(f"{r['stamp']} ({r['origin']})" for r in rs))


if __name__ == "__main__":
    main()
