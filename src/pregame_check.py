"""P71: reminder-only pregame check. Warns when an NFL game nears kickoff with no stored prediction.

    python -m src.pregame_check                          # one pass (Task Scheduler, every 15 min)
    python -m src.pregame_check --now 2026-10-15T23:00Z --dry-run   # what a pass at that moment would say

Two checkpoints per game, T-4h and T-90m. At each, a game with no stored
baseline prediction made before the pass raises one alert: a line in
data/live/alerts.log (the tracker's log) and a desktop toast. Each (game,
checkpoint) alerts once; that memory is the only state, kept in
data/pregame_check/state.json.

Reminder only, by construction (user, 2026-10-16 and 10/25):
- the store is read through `probe_inactives.ReadOnlyStore`, so any write raises;
- no API call, no prediction, no window run;
- it writes nothing outside data/pregame_check/ except the alert line.
It cannot fire while the laptop sleeps (the tasks have WakeToRun off).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config, db
from .features import parse_dt
from .probe_inactives import ReadOnlyStore

OUT_DIR = config.DATA_DIR / "pregame_check"
ALERT_LOG = config.DATA_DIR / "live" / "alerts.log"
CHECKPOINTS = (("T-4h", 240), ("T-90m", 90))   # minutes before kickoff
MODEL = "baseline-v1"


def due(games: list[dict], predictions: list[dict], now: datetime, alerted: set[str]) -> list[dict]:
    """Alerts this pass should raise: one per game and checkpoint reached, with no
    prediction stored at or before `now`, not already raised. Pure; no I/O."""
    made = {}
    for p in predictions:
        if p.get("model_version") != MODEL:
            continue
        at = parse_dt(p.get("generated_at"))
        if at is not None and at <= now:
            made[p["game_id"]] = at
    out = []
    for g in games:
        kickoff = parse_dt(g.get("kickoff_time"))
        if kickoff is None or kickoff <= now:
            continue
        lead = (kickoff - now).total_seconds() / 60
        for name, minutes in CHECKPOINTS:
            key = f"{g['game_id']}|{name}"
            if lead <= minutes and key not in alerted and g["game_id"] not in made:
                out.append({"key": key, "game_id": g["game_id"], "checkpoint": name,
                            "game": f"{g['away_team']} @ {g['home_team']}", "kickoff": kickoff.isoformat(),
                            "minutes_to_kickoff": round(lead)})
    return out


def _load_state(path: Path) -> set[str]:
    try:
        return set(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return set()


def run(now: datetime, dry_run: bool = False, out_dir: Path = OUT_DIR, store_factory=None,
        notify: bool = True) -> list[dict]:
    store_factory = store_factory or (lambda: ReadOnlyStore(db.get_store()))
    state_path = out_dir / "state.json"
    alerted = set() if dry_run else _load_state(state_path)
    store = store_factory()
    try:
        games = [g for g in store.select("games", {"sport": "nfl"})
                 if (k := parse_dt(g.get("kickoff_time"))) and now < k <= now + timedelta(minutes=CHECKPOINTS[0][1])]
        preds = [p for p in store.select("predictions", {"sport": "nfl"}) if p["game_id"] in {g["game_id"] for g in games}] \
            if games else []
    finally:
        store.close()
    alerts = due(games, preds, now, alerted)
    for a in alerts:
        line = (f"[{now:%Y-%m-%d %H:%M:%S}Z] PREGAME  {a['game']} ({a['checkpoint']}, kickoff in "
                f"{a['minutes_to_kickoff']} min): no stored {MODEL} prediction; the window has not been run (P71)")
        print(line)
        if dry_run:
            continue
        try:
            ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)
            with open(ALERT_LOG, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError as exc:
            print(f"  [warn] could not append to {ALERT_LOG}: {exc}")
        if notify:
            from .live_tracker import toast   # best-effort, fire and forget

            toast(f"No prediction: {a['game']}", f"{a['checkpoint']}: kickoff in {a['minutes_to_kickoff']} min")
    if alerts and not dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(sorted(alerted | {a["key"] for a in alerts})), encoding="utf-8")
    return alerts


def main() -> int:
    ap = argparse.ArgumentParser(description="P71 reminder-only pregame check.")
    ap.add_argument("--now", help="pretend it is this UTC time")
    ap.add_argument("--dry-run", action="store_true", help="print only: no alert line, toast or state")
    ap.add_argument("--no-notify", action="store_true")
    args = ap.parse_args()
    now = parse_dt(args.now) if args.now else datetime.now(timezone.utc)
    alerts = run(now, dry_run=args.dry_run or bool(args.now), notify=not args.no_notify)
    print(f"[pregame-check] {now:%Y-%m-%dT%H:%MZ}: {len(alerts)} alert(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
