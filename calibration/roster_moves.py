"""Roster moves from nflverse weekly rosters: team changes and reserve <-> active transitions. Read-only.

    python calibration/roster_moves.py 2026 11

Used to check the hand file's "IR-R / PUP-R not activated" rows and to list trades / claims the
engine does not model (P78). nflverse rosters lag the league by up to a day; a row here is a
lead to confirm on the team's transaction page, not a clearance.
"""
import csv
import sys

sys.path.insert(0, ".")
import nfl_data_py as nfl  # noqa: E402

from src.ingest_injuries import _snap_shares, player_key  # noqa: E402

season, week = int(sys.argv[1]), int(sys.argv[2])
ros = nfl.import_weekly_rosters([season])
idc = "player_id" if "player_id" in ros.columns else "gsis_id"
cur = ros[ros.week == week].drop_duplicates(idc).set_index(idc)
prev = ros[ros.week == week - 1].drop_duplicates(idc).set_index(idc)
shares = _snap_shares(season)
print(f"weekly roster rows: week {week - 1} {len(prev)}, week {week} {len(cur)}; statuses week {week}: {cur.status.value_counts().to_dict()}")

print(f"\nTEAM CHANGES week {week - 1} -> {week} (snap share with the old team >= 0.20):")
for pid in cur.index.intersection(prev.index):
    a, b = prev.loc[pid], cur.loc[pid]
    if a.team != b.team:
        sh = shares.get(player_key(a.team, a.player_name)) or 0
        if sh >= 0.20:
            print(f"  {a.player_name:<26} {a.position:<4} {a.team} -> {b.team}  old-team share {sh:.2f}  status {b.status}")

print(f"\nALL TEAM CHANGES since week 1 (share >= 0.30 with the old team), by first week on the new team:")
seen = {}
for wk in sorted(ros.week.unique()):
    for r in ros[ros.week == wk].drop_duplicates(idc).itertuples():
        pid = getattr(r, idc)
        if pid in seen and seen[pid][0] != r.team:
            sh = shares.get(player_key(seen[pid][0], r.player_name)) or 0
            if sh >= 0.30:
                print(f"  wk{int(wk):<2} {r.player_name:<26} {r.position:<4} {seen[pid][0]} -> {r.team}  old-team share {sh:.2f}")
        seen[pid] = (r.team, wk)

print(f"\nRESERVE -> ACTIVE week {week - 1} -> {week}:")
for pid in cur.index.intersection(prev.index):
    a, b = prev.loc[pid], cur.loc[pid]
    if a.status in ("RES", "PUP", "NFI") and b.status == "ACT":
        print(f"  {b.team} {b.player_name} {b.position}")
print(f"\nACTIVE -> RESERVE week {week - 1} -> {week}:")
for pid in cur.index.intersection(prev.index):
    a, b = prev.loc[pid], cur.loc[pid]
    if a.status == "ACT" and b.status in ("RES", "PUP", "NFI"):
        sh = shares.get(player_key(b.team, b.player_name)) or 0
        print(f"  {b.team} {b.player_name} {b.position} share {sh:.2f}")

print("\nHAND FILE rows marked not activated / IR, against the week's roster status:")
status = {player_key(t, n): s for t, n, s in zip(cur.team, cur.player_name, cur.status)}
with open(f"data/manual_injuries/{season}-wk{week:02d}.csv", encoding="utf-8") as fh:
    for row in csv.reader(l for l in fh if not l.startswith("#")):
        if len(row) < 8 or row[0] == "team":
            continue
        team, name, pos, injury, *_days, game = row[:8]
        if "not activated" in injury.lower() or "ir-r" in injury.lower() or "pup" in injury.lower() or "(ir" in injury.lower():
            s = status.get(player_key(team, name), "NOT ON ROSTER FILE")
            flag = "  <-- CONFLICT: file says Out / not activated, roster says ACTIVE" if s == "ACT" and game == "Out" else ""
            print(f"  {team:<4} {name:<24} {pos:<3} file: {game or 'no status':<12} roster: {s}{flag}   [{injury}]")
