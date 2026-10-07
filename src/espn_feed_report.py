"""P68 decision 4, C: report ESPN injury-feed rows that may be stale. Report-only.

A player only ESPN's injury feed lists is added to the report with ESPN's status (`ingest_injuries.merge_feeds`).
That is how a stale `out` reached PIT @ CLE on 10/1. C lists, at each injury refresh, every ESPN-only row with status
out or doubtful for a player who is not on the official (nflverse) report and who played last week (any snap in nflverse
snap counts), and keeps them in one persistent file so decision 4's B can be counted:

    data/espn_feed_flags/flags.csv     one row per (season, week, team, player)

with when it was first / last flagged, the estimated charge at flag time (position weight x snap share x
(1 - play probability) x 6, as `features.score_injuries` prices it), the served baseline charge once a prediction
for that game exists, and the later snap outcome (played / did not play) once that week's snaps post. A **stale
charged case** = served charge > 0 and played. B needs 5 by the end of week 10, or it closes (calibration-log, P68).

Isolation, by construction:
- Called after the injury rows are stored, with copies; it returns nothing the caller uses.
- Writes only its own file (atomically, via a temp file); every failure is caught and printed as one warning.
- `ESPN_FEED_REPORT=0` turns it off.
"""

from __future__ import annotations

import copy
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from . import config

OUT_DIR = config.DATA_DIR / "espn_feed_flags"
FIELDS = ["season", "week", "team", "player", "position", "status", "play_probability", "snap_share",
          "est_charge", "last_week_snaps", "first_flagged_at", "last_flagged_at", "times_flagged",
          "served_charge", "outcome", "outcome_snaps", "outcome_checked_at"]
RULED = ("out", "doubtful")


def enabled() -> bool:
    return os.getenv("ESPN_FEED_REPORT", "1").strip().lower() not in ("0", "false", "off", "no")


def _snaps(season: int):
    """{(week, team, player_key): total snaps} for the season, or None when unavailable."""
    import nfl_data_py as nfl

    from .ingest_injuries import player_key

    try:
        df = nfl.import_snap_counts([season])
    except Exception:  # noqa: BLE001
        return None
    out = {}
    for w, t, p, o, d, s in zip(df.week, df.team, df.player, df.offense_snaps, df.defense_snaps, df.st_snaps):
        k = (int(w), t, player_key(t, p))
        out[k] = out.get(k, 0) + (o or 0) + (d or 0) + (s or 0)
    return out


def _charge(row: dict) -> float:
    from .features import DEFAULT_POSITION_WEIGHT, DEFAULT_SNAP_SHARE, INJURY_POINTS_SCALE, POSITION_WEIGHTS

    weight = POSITION_WEIGHTS.get((row.get("position") or "").upper(), DEFAULT_POSITION_WEIGHT)
    share = row.get("snap_share")
    share = DEFAULT_SNAP_SHARE if share is None else share
    pp = row.get("play_probability") or 0.0
    return round(weight * share * (1 - pp) * INJURY_POINTS_SCALE["nfl"], 3)


def flagged(official: list[dict], final: list[dict], week: int, snaps: dict | None) -> list[dict]:
    """ESPN-only out / doubtful rows for players off the official report who played last week."""
    from .ingest_injuries import player_key

    if snaps is None:
        return []
    on_report = {player_key(r["team"], r["player"]) for r in official}
    out = []
    for r in final:
        if not str(r.get("source") or "").startswith("espn") or (r.get("status") or "").lower() not in RULED:
            continue
        k = player_key(r["team"], r["player"])
        last = snaps.get((week - 1, r["team"], k), 0)
        if k in on_report or last <= 0:
            continue
        out.append({**r, "_last_week_snaps": last})
    return out


def _served(store, season: int) -> dict:
    """{(week, team, player_key): served baseline charge} from stored baseline predictions."""
    from .ingest_injuries import player_key

    games = {g["game_id"]: g for g in store.select("games", {"sport": "nfl"}) if g.get("season") == season}
    out = {}
    for p in store.select("predictions", {"sport": "nfl"}):
        g = games.get(p.get("game_id"))
        if p.get("model_version") != config.MODEL_VERSION or not g:
            continue
        c = p.get("components")
        c = json.loads(c) if isinstance(c, str) else c
        for side in ("home", "away"):
            for x in ((c or {}).get("layer2") or {}).get(f"{side}_injuries") or []:
                t = g[f"{side}_team"]
                out[(int(g["week"]), t, player_key(t, x["player"]))] = x.get("points") or 0.0
    return out


def _read(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as f:
        return {(r["season"], r["week"], r["team"], r["player"]): r for r in csv.DictReader(f)}


def _write(path: Path, rows: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for k in sorted(rows):
            w.writerow({f: rows[k].get(f, "") for f in FIELDS})
    os.replace(tmp, path)


def report(season: int, week: int, official: list[dict], final: list[dict], store=None,
           out_dir: Path | None = None, now: datetime | None = None, snaps: dict | None = None) -> int | None:
    """Print and record this refresh's flags, then fill served charges and outcomes for earlier weeks.
    Returns the number flagged now, or None when off or on failure. Never raises."""
    if not enabled():
        return None
    try:
        from .ingest_injuries import player_key

        official, final = copy.deepcopy(official), copy.deepcopy(final)
        now = (now or datetime.now(timezone.utc)).isoformat()
        path = (out_dir or OUT_DIR) / "flags.csv"
        snaps = _snaps(season) if snaps is None else snaps
        rows = _read(path)
        hits = flagged(official, final, week, snaps)
        for r in hits:
            k = (str(season), str(week), r["team"], r["player"])
            old = rows.get(k, {})
            rows[k] = {**old, "season": season, "week": week, "team": r["team"], "player": r["player"],
                       "position": r.get("position"), "status": r.get("status"),
                       "play_probability": r.get("play_probability"), "snap_share": r.get("snap_share"),
                       "est_charge": _charge(r), "last_week_snaps": r["_last_week_snaps"],
                       "first_flagged_at": old.get("first_flagged_at") or now, "last_flagged_at": now,
                       "times_flagged": int(old.get("times_flagged") or 0) + 1,
                       "outcome": old.get("outcome") or "pending"}
        served = _served(store, season) if store is not None else {}
        for k, r in rows.items():
            w, t = int(r["week"]), r["team"]
            pk = player_key(t, r["player"])
            if (w, t, pk) in served:
                r["served_charge"] = served[(w, t, pk)]
            if r.get("outcome") in (None, "", "pending") and snaps is not None and any(
                    kk[0] == w and kk[1] == t for kk in snaps):
                s = snaps.get((w, t, pk), 0)
                r.update(outcome="played" if s > 0 else "did not play", outcome_snaps=s, outcome_checked_at=now)
        _write(path, rows)
        stale = [r for r in rows.values() if r.get("outcome") == "played" and float(r.get("served_charge") or 0) > 0]
        print(f"  [P68 C] ESPN-only out/doubtful, off the official report, played last week: {len(hits)} this refresh"
              f" | file {len(rows)} rows, stale charged cases so far {len(stale)} (B needs 5 by end of week 10)")
        for r in hits:
            print(f"    {r['team']} {r['player']} ({r.get('position')}, {r.get('status')}, last week {r['_last_week_snaps']:g}"
                  f" snaps, est. charge {_charge(r):.2f})")
        return len(hits)
    except Exception as exc:  # noqa: BLE001 - report-only: never stops a refresh
        try:
            print(f"  [warn] P68 C report not written: {type(exc).__name__}: {exc}")
        except Exception:  # noqa: BLE001
            pass
        return None
