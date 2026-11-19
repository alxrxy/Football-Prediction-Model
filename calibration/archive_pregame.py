"""Read-only archive of a game's stored pregame record (user rule, week 10 on).

    python calibration/archive_pregame.py 2026 11 tnf_preliminary "FIRST PREGAME (PRELIMINARY ...)" 2026_11_IND_HOU [...]

Copies the stored predictions and game_simulations rows for the named games to
data/archive/pregame_first/<season>_w<week>/<UTC stamp>_<label>.json and marks
the file read-only. It never overwrites, and it refuses a game that has kicked
off unless --allow-started is given (for a record made before kickoff that is
being archived late). Reads the store; writes only the archive file.
"""
import json
import os
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config, db  # noqa: E402
from src.features import parse_dt  # noqa: E402


def main(argv):
    allow = "--allow-started" in argv
    argv = [a for a in argv if a != "--allow-started"]
    season, week, label, kind, *game_ids = argv
    store = db.get_store()
    games = {g["game_id"]: g for g in store.select("games", {"sport": "nfl", "season": int(season)})}
    now = datetime.now(timezone.utc)
    preds, sims = [], []
    for gid in game_ids:
        k = parse_dt(games[gid]["kickoff_time"])
        if k <= now and not allow:
            raise SystemExit(f"{gid} has kicked off; not archiving a post-kickoff state as pregame")
        preds += store.select("predictions", {"game_id": gid})
        sims += db.select_merged(store, "game_simulations", {"game_id": gid})
    for p in preds:
        if parse_dt(p["generated_at"]) >= parse_dt(games[p["game_id"]]["kickoff_time"]):
            raise SystemExit(f"{p['game_id']} {p['model_version']} was generated after kickoff")
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    out = config.DATA_DIR / "archive" / "pregame_first" / f"{season}_w{int(week):02d}"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{stamp}_{label}.json"
    if path.exists():
        raise SystemExit(f"{path} exists; never overwritten")
    doc = {"captured_at": stamp, "kind": kind,
           "kickoff": {gid: games[gid]["kickoff_time"] for gid in game_ids},
           "predictions": preds, "simulations": sims}
    path.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.chmod(path, stat.S_IREAD)
    print(f"archived {len(preds)} prediction rows, {len(sims)} sim rows -> {path} (read-only)")


if __name__ == "__main__":
    main(sys.argv[1:])
