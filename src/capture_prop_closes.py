"""P61: capture each NFL game's player-prop lines around kickoff (Sportradar), so a
closing line exists to measure prop CLV against.

    python -m src.capture_prop_closes                  # one pass; no call unless a game is at a checkpoint
    python -m src.capture_prop_closes --now 2026-10-02T00:05Z --out <dir>   # dry run at a chosen moment
    python -m src.capture_prop_closes --report          # per game: lines, removed, changes between checkpoints

Passive: nothing reads these files and no prediction, sim, prop or export
changes. Sportradar calls go through `sportradar.KeyManager`, so they are
counted with the rest of the Sportradar usage.

Each game is pulled once per checkpoint (minutes from kickoff):

    t-60 [-60,-45)  t-45 [-45,-30)  t-30 [-30,-15)  t-15 [-15,0)
    t+0  [0,15)     t+15 [15,30)    t+120 [120,240) t+24h [1440,1680)

A pass takes every checkpoint whose window contains "now" and that this game
has not saved yet; a window that passes with no run is logged `missed` by the
next pass, so a gap is never silent. The pre- and post-kickoff checkpoints
exist to validate the capture point itself (P61's criteria in
calibration-log.md): whether books pull their lines at kickoff, whether lines
still move after it, and how long Sportradar keeps an ended game.

The schedule (event ids and kickoffs) is cached in the output folder and
re-read from Sportradar at most every SCHEDULE_MAX_AGE_HOURS (2 calls a day);
otherwise a pass with no game at a checkpoint makes no call. An ended game the
new schedule drops is kept until its last checkpoint. Written only under data/prop_closes/:
raw responses in <kickoff date>_<away>_<home>_<event>/, and manifest.csv.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from . import config

OUT_DIR = config.DATA_DIR / "prop_closes"
BASE_PATH = "/oddscomparison-player-props/trial/v2/en"
SCHEDULE_PATH = f"{BASE_PATH}/competitions/sr:competition:31/schedules.json"
SCHEDULE_MAX_AGE_HOURS = 12.0
CHECKPOINTS = [  # (name, window start, window end), minutes from kickoff
    ("t-60", -60, -45), ("t-45", -45, -30), ("t-30", -30, -15), ("t-15", -15, 0),
    ("t+0", 0, 15), ("t+15", 15, 30), ("t+120", 120, 240), ("t+24h", 1440, 1680),
]
MANIFEST_FIELDS = ["run_utc", "event_id", "game", "kickoff", "checkpoint", "offset_min",
                   "result", "event_status", "book_lines", "removed", "is_live", "generated_at", "file"]


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _game(se: dict) -> str:
    teams = {c["qualifier"]: c["abbreviation"] for c in se["competitors"]}
    return f"{teams.get('away', '?')}_{teams.get('home', '?')}"


def line_counts(payload: dict) -> tuple[int, int, int]:
    """(book lines, lines flagged removed, lines in live markets) across both blocks."""
    ev = payload.get("sport_event_players_props") or {}
    markets = [m for pp in ev.get("players_props") or [] for m in pp.get("markets") or []]
    markets += (ev.get("players_markets") or {}).get("markets") or []
    total = removed = live = 0
    for m in markets:
        for b in m.get("books") or []:
            total += 1
            removed += bool(b.get("removed"))
            live += bool(m.get("is_live"))
    return total, removed, live


def load_schedule(out: Path, get: Callable[[str], dict], now: datetime) -> list[dict]:
    path = out / "schedule.json"
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
        if now - _parse(cached["fetched_at"]) < timedelta(hours=SCHEDULE_MAX_AGE_HOURS):
            return cached["events"]
    except (OSError, ValueError, KeyError):
        pass
    data = get(SCHEDULE_PATH)
    events = [{"id": s["sport_event"]["id"], "start_time": s["sport_event"]["start_time"],
               "game": _game(s["sport_event"])} for s in data.get("schedules") or []]
    # keep events the new schedule dropped (ended games leave it quickly) until their last checkpoint passes
    try:
        old = json.loads(path.read_text(encoding="utf-8"))["events"]
    except (OSError, ValueError, KeyError):
        old = []
    ids = {e["id"] for e in events}
    last = CHECKPOINTS[-1][2]
    events += [e for e in old if e["id"] not in ids
               and now < _parse(e["start_time"]) + timedelta(minutes=last)]
    out.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"fetched_at": now.isoformat(), "events": events}, indent=1), encoding="utf-8")
    return events


def _done(out: Path) -> set[tuple[str, str]]:
    path = out / "manifest.csv"
    if not path.exists():
        return set()
    with path.open(newline="", encoding="utf-8") as f:
        return {(r["event_id"], r["checkpoint"]) for r in csv.DictReader(f)}


def _log(out: Path, row: dict) -> None:
    path = out / "manifest.csv"
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in MANIFEST_FIELDS})


def capture(out: Path, get: Callable[[str], dict], now: datetime) -> list[dict]:
    """One pass. Returns the manifest rows written."""
    out.mkdir(parents=True, exist_ok=True)
    started_path = out / "started_at.txt"
    if not started_path.exists():
        started_path.write_text(now.isoformat(), encoding="utf-8")
    started = _parse(started_path.read_text(encoding="utf-8").strip())
    rows: list[dict] = []
    events = load_schedule(out, get, now)   # a call only when the cached schedule is stale
    done = _done(out)
    for ev in events:
        kickoff = _parse(ev["start_time"])
        offset = (now - kickoff).total_seconds() / 60
        for name, lo, hi in CHECKPOINTS:
            if (ev["id"], name) in done:
                continue
            base = {"run_utc": now.isoformat(timespec="seconds"), "event_id": ev["id"], "game": ev["game"],
                    "kickoff": ev["start_time"], "checkpoint": name, "offset_min": round(offset, 1)}
            if offset >= hi:
                # a miss only for windows open after the first pass (earlier ones were never capturable)
                if kickoff + timedelta(minutes=lo) >= started:
                    rows.append({**base, "result": "missed"})
                continue
            if not lo <= offset < hi:
                continue
            folder = out / f"{kickoff:%Y-%m-%d}_{ev['game']}_{ev['id'].rsplit(':', 1)[-1]}"
            try:
                data = get(f"{BASE_PATH}/sport_events/{ev['id']}/players_props.json")
            except Exception as exc:  # noqa: BLE001 - logged, never raised: a capture must not crash the task
                rows.append({**base, "result": f"error: {str(exc)[:120]}"})
                continue
            folder.mkdir(parents=True, exist_ok=True)
            file = folder / f"{name}_{now:%Y%m%dT%H%M%SZ}.json"
            file.write_text(json.dumps(data), encoding="utf-8")
            total, removed, live = line_counts(data)
            status = ((data.get("sport_event_players_props") or {}).get("sport_event") or {}).get("status", "")
            rows.append({**base, "result": "saved", "event_status": status, "book_lines": total,
                         "removed": removed, "is_live": live, "generated_at": data.get("generated_at", ""),
                         "file": str(file.relative_to(out))})
    for row in rows:
        _log(out, row)
    return rows


def report(out: Path) -> str:
    """Per game and checkpoint: lines, removed, and how many (player, market, book)
    lines changed total or price since the previous saved checkpoint."""
    path = out / "manifest.csv"
    if not path.exists():
        return "no captures yet"
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    lines, prev_by_event = [], {}
    for r in rows:
        if r["result"] != "saved":
            lines.append(f"{r['game']:8s} {r['checkpoint']:6s} {r['result']}")
            continue
        snap = _lines(json.loads((out / r["file"]).read_text(encoding="utf-8")))
        prev = prev_by_event.get(r["event_id"])
        changed = sum(1 for k, v in snap.items() if prev and k in prev and prev[k] != v) if prev else ""
        lines.append(f"{r['game']:8s} {r['checkpoint']:6s} {r['offset_min']:>7s} min  status={r['event_status']:11s} "
                     f"lines={r['book_lines']:>4s} removed={r['removed']:>4s} live={r['is_live']:>3s} "
                     f"changed_vs_prev={changed}")
        prev_by_event[r["event_id"]] = snap
    return "\n".join(lines)


def _lines(payload: dict) -> dict:
    ev = payload.get("sport_event_players_props") or {}
    out = {}
    for pp in ev.get("players_props") or []:
        for m in pp.get("markets") or []:
            for b in m.get("books") or []:
                key = (pp["player"]["id"], m["id"], b["id"])
                out[key] = tuple((o.get("type"), o.get("total"), o.get("odds_american"),
                                  bool(o.get("removed") or b.get("removed"))) for o in b.get("outcomes") or [])
    for m in (ev.get("players_markets") or {}).get("markets") or []:
        for b in m.get("books") or []:
            for o in b.get("outcomes") or []:
                out[(o.get("player_id"), m["id"], b["id"])] = (o.get("odds_american"),
                                                              bool(o.get("removed") or b.get("removed")))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--now", help="dry-run clock, e.g. 2026-10-02T00:05Z")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    if args.report:
        print(report(args.out))
        return
    from .sportradar import KeyManager
    km = KeyManager()
    now = _parse(args.now) if args.now else datetime.now(timezone.utc)
    rows = capture(args.out, km.get, now)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"{stamp} P61 pass at {now:%Y-%m-%dT%H:%MZ}: "
          + (", ".join(f"{r['game']} {r['checkpoint']} {r['result']}" for r in rows) or "nothing due"))


if __name__ == "__main__":
    main()
