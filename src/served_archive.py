"""Immutable copies of every served props and anytime-TD list.

    python -m src.served_archive --status     # what the archive holds; any gap or edit
    python -m src.served_archive --capture    # store the lists being served right now

`props.run` and `td_props.run` call `archive()` before they write the served
file, so a list is on disk here before the page can show it; if the archive
fails the refresh stops and the last archived list stays up. Each list goes to
data/archive/served_lists/<kind>/<season>_w<WW>/<stamp>.json as the exact served
bytes (rows carry the pick, line, prices, model and market chances, and rank),
read-only, with one row in index.csv. The raw lines that list ranked are kept
once per content in lines/<sha12>.json. Nothing here is rebuilt from other data:
a week that was not captured stays missing. `archived_at` is the time the list
was stored, so a capture made after kickoff shows as one. Nothing served reads
the archive. data/ is gitignored, so it is local (OneDrive-backed).

data/props_archive (P67) stays as it is: the props record and report card read it.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .props_archive import _sha, _stamp, _write_new, git_commit

ARCHIVE_DIR = config.DATA_DIR / "archive" / "served_lists"
INDEX_FIELDS = ["kind", "stamp", "season", "week", "generated_at", "archived_at", "lines_pulled_at", "git_commit",
                "origin", "served_sha256", "lines_sha256", "rows", "games", "file"]
LISTS = ("props", "more", "held_out", "model_only")   # `started` rows can no longer be bet


def served_files() -> dict[str, list[Path]]:
    """The files the props and TD tabs and the Q&A read."""
    public = config.ROOT / "dashboard" / "public"
    return {"props": [config.DATA_DIR / "props.json", public / "props.json"],
            "td": [config.DATA_DIR / "td_props.json", public / "td_props.json"]}


def _summary(payload: dict) -> dict:
    rows = [r for key in LISTS for r in payload.get(key) or []]
    return {"rows": len(rows), "games": " ".join(sorted({r["game_id"] for r in rows if r.get("game_id")}))}


def index_rows(out: Path | None = None) -> list[dict]:
    path = (out or ARCHIVE_DIR) / "index.csv"
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def archive(kind: str, served: bytes, lines: bytes = b"", *, origin: str = "live", commit: str | None = None,
            out: Path | None = None) -> Path:
    """Store one served list. Bytes already held for this kind store nothing
    new. Raises on failure, and the caller lets that stop the refresh."""
    out = out or ARCHIVE_DIR
    sha = _sha(served)
    for r in index_rows(out):
        if r["kind"] == kind and r["served_sha256"] == sha:
            return out / r["file"]
    payload = json.loads(served.decode("utf-8"))
    folder = out / kind / f"{payload['season']}_w{int(payload['week']):02d}"
    path = _write_new(folder, _stamp(payload.get("generated_at")), served)
    os.chmod(path, stat.S_IREAD)
    lines_sha = _sha(lines) if lines else ""
    if lines:
        kept = out / "lines" / f"{lines_sha[:12]}.json"
        if not kept.exists():
            kept.parent.mkdir(parents=True, exist_ok=True)
            kept.write_bytes(lines)
            os.chmod(kept, stat.S_IREAD)
    index = out / "index.csv"
    new = not index.exists()
    with index.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=INDEX_FIELDS)
        if new:
            w.writeheader()
        w.writerow({
            "kind": kind, "stamp": path.stem, "season": payload["season"], "week": payload["week"],
            "generated_at": payload.get("generated_at"), "archived_at": datetime.now(timezone.utc).isoformat(),
            "lines_pulled_at": payload.get("lines_pulled_at"), "git_commit": commit or git_commit(), "origin": origin,
            "served_sha256": sha, "lines_sha256": lines_sha, **_summary(payload),
            "file": path.relative_to(out).as_posix(),
        })
    return path


def unarchived(files: dict[str, list[Path]] | None = None, out: Path | None = None) -> list[Path]:
    """Served files whose exact bytes the archive does not hold."""
    have = {(r["kind"], r["served_sha256"]) for r in index_rows(out)}
    return [path for kind, paths in (files or served_files()).items() for path in paths
            if path.exists() and (kind, _sha(path.read_bytes())) not in have]


def verify(out: Path | None = None) -> list[str]:
    """Archived files that are gone or no longer match their recorded hash."""
    out = out or ARCHIVE_DIR
    bad = []
    for r in index_rows(out):
        path = out / r["file"]
        if not path.exists():
            bad.append(f"{r['file']}: missing")
        elif _sha(path.read_bytes()) != r["served_sha256"]:
            bad.append(f"{r['file']}: changed since it was archived")
    return bad


def capture() -> list[Path]:
    """Store the files being served now, byte for byte. Copies what is live; it
    never rebuilds an earlier list."""
    kept = []
    for kind, paths in served_files().items():
        for path in paths:
            if path.exists():
                kept.append(archive(kind, path.read_bytes(), origin="capture"))
    return kept


def main() -> None:
    ap = argparse.ArgumentParser(description="Immutable archive of served props and TD lists.")
    ap.add_argument("--capture", action="store_true")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()
    if args.capture:
        for path in dict.fromkeys(capture()):
            print(f"  {path.relative_to(ARCHIVE_DIR).as_posix()}")
    rows = index_rows()
    print(f"{ARCHIVE_DIR}: {len(rows)} list(s)")
    for r in rows:
        print(f"  {r['kind']:<5} wk{r['week']:>2} {r['stamp']} {r['origin']:<7} {r['rows']:>4} rows, archived {r['archived_at']}")
    for line in [f"NOT ARCHIVED: {p}" for p in unarchived()] + verify():
        print(f"  {line}")


if __name__ == "__main__":
    main()
