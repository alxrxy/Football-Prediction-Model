"""P79 redesign: evidence-based clearing of stale feed-sourced charges. Shadow replay, read-only.

Rule and gates: calibration-log 2026-11-19 (rule) and 2026-10-29 (R1-R5, unchanged).

    python calibration/p79b_replay.py 1,2,3,4,5,6,7,8,9,10

A charged row whose in-force source rows are all `espn` and all from a week before
the game's week is a candidate. It is
  kept    if status is ir, or the player is on reserve on the weekly roster for the game's week;
  cleared if he took offensive/defensive snaps in a week after the row's week and before the game's week;
  cleared if his team had filed a report for the game's week (nflverse or manual rows stored
          before the prediction), he has no row on it, and he is on the team's latest depth
          chart dated before the prediction;
  kept    otherwise.
Everything is as of the prediction's generated_at (walk-forward).
"""
import collections
import json
import sys

sys.path.insert(0, ".")
import nfl_data_py as nfl  # noqa: E402
import pandas as pd  # noqa: E402

from src import db  # noqa: E402
from src.features import INJURY_MAX_POINTS, latest_injury_report, parse_dt  # noqa: E402
from src.ingest_injuries import player_key  # noqa: E402

WEEKS = [int(w) for w in sys.argv[1].split(",")]
RESERVE = ("RES", "PUP", "NFI", "SUS", "EXE")
K = player_key

sn = nfl.import_snap_counts([2026])
inj = nfl.import_injuries([2026])
ros = nfl.import_weekly_rosters([2026])
dc = nfl.import_depth_charts([2026])
dc["dt"] = pd.to_datetime(dc.dt, utc=True)

snap_any = {(int(r.week), K(r.team, r.player)) for r in sn.itertuples()
            if (r.offense_snaps or 0) + (r.defense_snaps or 0) + (r.st_snaps or 0) > 0}
snap_od = collections.defaultdict(set)
for r in sn.itertuples():
    if (r.offense_snaps or 0) + (r.defense_snaps or 0) > 0:
        snap_od[K(r.team, r.player)].add(int(r.week))
official = {(int(r.week), K(r.team, r.full_name)) for r in inj.itertuples() if isinstance(r.report_status, str)}
reserve = {(int(r.week), K(r.team, r.player_name)) for r in ros.itertuples() if r.status in RESERVE}
dc_times = sorted(dc.dt.unique())
dc_cache: dict = {}


def on_depth_chart(team: str, name: str, at) -> bool:
    earlier = [t for t in dc_times if t <= at]
    if not earlier:
        return False
    t = earlier[-1]
    if t not in dc_cache:
        cur = dc[dc.dt == t]
        dc_cache[t] = {K(a, b) for a, b in zip(cur.team, cur.player_name)}
    return K(team, name) in dc_cache[t]


st = db.get_store()
rows = st.select("injuries", {"sport": "nfl"})
games = {g["game_id"]: g for g in st.select("games", {"sport": "nfl", "season": 2026})}
preds = [p for p in st.select("predictions", {"sport": "nfl"})
         if p["model_version"] == "baseline-v1" and p["game_id"].startswith("2026_")]

cleared, kept, changed, weeks_with_stale = [], [], [], collections.Counter()
for p in sorted(preds, key=lambda p: p["game_id"]):
    gid = p["game_id"]
    wk = int(gid[5:7])
    g = games[gid]
    if wk not in WEEKS:
        continue
    at = parse_dt(p["generated_at"])
    before = [r for r in rows if parse_dt(r.get("pulled_at")) and parse_dt(r["pulled_at"]) <= at]
    cur = latest_injury_report(before)
    by = collections.defaultdict(list)
    for r in cur:
        by[K(r["team"], r["player"])].append(r)
    filed = {r["team"] for r in before if int(r.get("week") or 0) == wk and r.get("season") == 2026
             and r["source"] in ("nflverse", "manual")}
    c = p["components"] if isinstance(p["components"], dict) else json.loads(p["components"])
    delta = 0.0
    for side, sign in (("home", 1), ("away", -1)):
        team = g[f"{side}_team"]
        br = c["layer2"].get(f"{side}_injuries") or []
        rem = []
        for b in br:
            if (b.get("status") or "") == "inactive":
                continue                                   # inactive-list row: untouched (R3)
            src = by.get(K(team, b["player"]), [])
            if not src or any(r["source"] != "espn" or int(r.get("week") or 0) >= wk for r in src):
                continue                                   # manual / own-week rows: untouched (R3)
            rw = max(int(r.get("week") or 0) for r in src)
            k = K(team, b["player"])
            weeks_with_stale[wk] += 1
            window = set(range(rw + 1, wk))
            if (b.get("status") or "") == "ir":
                fate, why = "kept", "ir"
            elif (wk, k) in reserve:
                fate, why = "kept", "reserve"
            elif snap_od[k] & window:
                fate, why = "cleared", "snaps since"
            elif team in filed and on_depth_chart(team, b["player"], pd.Timestamp(at)):
                fate, why = "cleared", "off filed report + on depth chart"
            else:
                fate, why = "kept", ("no report filed" if team not in filed else "off depth chart")
            rec = dict(wk=wk, gid=gid, team=team, player=b["player"], status=b.get("status"), pts=b["points"],
                       row_week=rw, played=(wk, k) in snap_any, on_report=(wk, k) in official, why=why)
            (rem if fate == "cleared" else kept).append(rec)
        if rem:
            raw = sum(x["points"] for x in br)
            d = min(raw, INJURY_MAX_POINTS) - min(raw - sum(x["pts"] for x in rem), INJURY_MAX_POINTS)
            delta += sign * d
            cleared += rem
    if delta and g.get("home_points") is not None:
        am = g["home_points"] - g["away_points"]
        m0 = p["model_margin_home"]
        m1 = m0 + delta
        sp = p["market_spread"]
        ats = (lambda m: None) if sp is None else (
            lambda m: "P" if am + sp == 0 else ("W" if (am + sp > 0) == (m + sp > 0) else "L"))
        changed.append((wk, gid, round(delta, 2), m0, round(m1, 2), am, abs(m0 - am), abs(m1 - am), ats(m0), ats(m1)))

n = len(cleared)
pl = sum(r["played"] for r in cleared)
bad = [r for r in cleared if not r["played"] and r["on_report"]]
print(f"weeks {WEEKS}: stale feed-sourced charged rows by week: {dict(sorted(weeks_with_stale.items()))}")
print(f"cleared {n} charges ({sum(r['pts'] for r in cleared):.2f} pts) {dict(collections.Counter(r['why'] for r in cleared))}; "
      f"kept {len(kept)} {dict(collections.Counter(r['why'] for r in kept))}")
print(f"minimum sample (>= 10 cleared): {'met' if n >= 10 else 'NOT MET -> not testable -> fail to ship'}")
print(f"R1a played that game: {pl}/{n} = {100 * pl / max(1, n):.1f}%  (gate >= 80%)")
print(f"R1b cleared but did not play AND on that week's official report: {len(bad)}  (gate 0)")
for r in bad:
    print("   ", r)
lt_wrong = [r for r in cleared if r["status"] == "ir" or (r["wk"], K(r["team"], r["player"])) in reserve]
print(f"R2 long-term absences cleared: {len(lt_wrong)}  (gate 0)")
print("cleared rows:")
for r in cleared:
    print(f"  wk{r['wk']} {r['gid']:<17} {r['team']:<4} {r['player']:<26} {str(r['status']):<12} {r['pts']:>5.2f} "
          f"rowwk {r['row_week']} played {r['played']} on_report {r['on_report']} [{r['why']}]")
print("kept rows that then PLAYED (stale charge left in force on a player who played):")
for r in kept:
    if r["played"]:
        print(f"  wk{r['wk']} {r['gid']:<17} {r['team']:<4} {r['player']:<26} {str(r['status']):<12} {r['pts']:>5.2f} [{r['why']}]")
print("R4 changed graded games (wk, game, delta, before, after, actual, |err| before, after, ATS before, after):")
for x in changed:
    print("  ", x)
if changed:
    b = sum(x[6] for x in changed) / len(changed)
    a = sum(x[7] for x in changed) / len(changed)
    print(f"  all: {len(changed)} games MAE {b:.2f} -> {a:.2f} ({a - b:+.2f}); "
          f"ATS W {sum(x[8] == 'W' for x in changed)} -> {sum(x[9] == 'W' for x in changed)}")
    for w in WEEKS:
        cw = [x for x in changed if x[0] == w]
        if cw:
            print(f"  wk{w}: {len(cw)} games MAE {sum(x[6] for x in cw) / len(cw):.2f} -> {sum(x[7] for x in cw) / len(cw):.2f}; "
                  f"ATS W {sum(x[8] == 'W' for x in cw)} -> {sum(x[9] == 'W' for x in cw)}")
