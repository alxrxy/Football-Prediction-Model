"""Stale-row audit: every in-force injury row, by source and by the week it was pulled for. Read-only.

    python calibration/stale_row_audit.py 2026 11
"""
import collections
import sys

sys.path.insert(0, ".")
from src import db  # noqa: E402
from src.features import latest_injury_report  # noqa: E402

season, week = int(sys.argv[1]), int(sys.argv[2])
s = db.get_store()
rows = s.select("injuries", {"sport": "nfl"})
allrows = collections.Counter((r.get("season"), r.get("week"), r["source"]) for r in rows)
games = [g for g in s.select("games", {"sport": "nfl", "season": season}) if g["week"] == week]
playing = {g["home_team"] for g in games} | {g["away_team"] for g in games}
cur = latest_injury_report(rows)
print(f"stored injury rows: {len(rows)} | in force now: {len(cur)} | teams playing week {week}: {len(playing)}")
by = collections.Counter((r["source"], r.get("season"), r.get("week")) for r in cur)
for k, n in sorted(by.items(), key=str):
    print(f"  in force: source {k[0]:<9} season {k[1]} week {k[2]}: {n}")
stale = [r for r in cur if (r.get("season"), r.get("week")) != (season, week)]
stale_playing = [r for r in stale if r["team"] in playing]
print(f"in-force rows from an earlier week: {len(stale)} (on teams playing this week: {len(stale_playing)})")
for r in sorted(stale_playing, key=lambda r: (r["team"], r["player"])):
    print(f"   STALE {r['team']} {r['player']} {r['position']} {r['status']} wk{r.get('week')} {r['source']} pulled {str(r.get('pulled_at'))[:10]} share {r.get('snap_share')}")
print("stored rows per week (all sources):", {w: sum(n for (se, wk, _), n in allrows.items() if wk == w and se == season) for w in range(1, week + 1)})
bye = [r for r in cur if r["team"] not in playing]
print(f"in-force rows on bye teams (not used this week): {len(bye)}")
