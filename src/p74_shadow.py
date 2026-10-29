"""P74 shadow (user, 2026-10-29): log what the P74 rule WOULD change on the stored pregame baseline predictions
of a week, never served. Read-only on the store; appends one JSON line per run to data/p74_shadow/<season>-wkNN.jsonl.
Judged after the week by the outcome gates in calibration-log.md (2026-10-29 P74 shadow entry).

    python -m src.p74_shadow --week 8
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from . import config, db
from .features import INJURY_MAX_POINTS, LEADER_RULED_STATUSES
from .ingest_injuries import player_key

OUT = config.DATA_DIR / "p74_shadow"


def expected_starters(season: int, week: int) -> dict[str, str]:
    """Walk-forward expected starter per team: most regular-season QB snaps in weeks before `week`; the prior
    season's team leader if none (the 10/25 definition)."""
    import nfl_data_py as nfl

    sn = nfl.import_snap_counts([season - 1, season])
    q = sn[(sn.position == "QB") & (sn.game_type == "REG")]
    out = {}
    for team in set(q.team):
        d = q[(q.season == season) & (q.team == team) & (q.week < week)]
        if not len(d) or d.offense_snaps.sum() == 0:
            d = q[(q.season == season - 1) & (q.team == team)]
        if len(d):
            out[team] = d.groupby("player")["offense_snaps"].sum().idxmax()
    return out


def would_change(pred: dict, game: dict, exp: dict[str, str]) -> list[dict]:
    c = pred["components"] if isinstance(pred["components"], dict) else json.loads(pred["components"])
    out = []
    for side in ("home", "away"):
        team = game[f"{side}_team"]
        rows = c["layer2"].get(f"{side}_injuries") or []
        e = exp.get(team)
        if not e:
            continue
        ek = player_key(team, e)[1]
        if any((r.get("position") or "").upper() == "QB" and player_key(team, r["player"])[1] == ek
               and (r.get("status") or "").lower() in LEADER_RULED_STATUSES for r in rows):
            continue
        rem = [r for r in rows if (r.get("position") or "").upper() == "QB" and player_key(team, r["player"])[1] != ek]
        if rem:
            raw = sum(r["points"] for r in rows)
            d = min(raw, INJURY_MAX_POINTS) - min(raw - sum(r["points"] for r in rem), INJURY_MAX_POINTS)
            out.append({"team": team, "side": side, "expected_starter": e, "removed": [
                {"player": r["player"], "status": r.get("status"), "points": r["points"]} for r in rem],
                "margin_change_home": round(d if side == "home" else -d, 2)})
    return out


def run(season: int, week: int) -> dict:
    store = db.get_store()
    games = {g["game_id"]: g for g in store.select("games", {"sport": "nfl", "season": season, "week": week})}
    preds = [p for p in store.select("predictions", {"sport": "nfl"})
             if p["model_version"] == "baseline-v1" and p["game_id"] in games]
    store.close()
    exp = expected_starters(season, week)
    rec = {"run_at": datetime.now(timezone.utc).isoformat(), "season": season, "week": week, "games": {}}
    for p in preds:
        ch = would_change(p, games[p["game_id"]], exp)
        rec["games"][p["game_id"]] = {"prediction_at": p["generated_at"], "served_margin_home": p["model_margin_home"],
                                      "changes": ch,
                                      "shadow_margin_home": round(p["model_margin_home"] + sum(x["margin_change_home"] for x in ch), 2)}
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / f"{season}-wk{week:02d}.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    n = sum(bool(g["changes"]) for g in rec["games"].values())
    print(f"[p74-shadow] week {week}: {len(preds)} predictions read, {n} would change (logged, not served)")
    for gid, g in rec["games"].items():
        for x in g["changes"]:
            print(f"  {gid} {x['team']}: remove {', '.join(r['player'] for r in x['removed'])} -> margin {x['margin_change_home']:+.2f}")
    return rec


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--week", type=int, required=True)
    a = ap.parse_args()
    run(a.season, a.week)
