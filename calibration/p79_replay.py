"""P79 shadow replay (criteria 10/29). Read-only."""
import sys, json, collections; sys.path.insert(0, ".")
import pandas as pd, nfl_data_py as nfl
from src import db
from src.features import latest_injury_report, parse_dt, INJURY_MAX_POINTS
from src.ingest_injuries import player_key
WEEKS = [int(w) for w in sys.argv[1].split(",")]
sn = nfl.import_snap_counts([2026]); inj = nfl.import_injuries([2026]); ros = nfl.import_weekly_rosters([2026])
K = lambda t, n: player_key(t, n)
snap_any = {(int(r.week), K(r.team, r.player)) for r in sn.itertuples() if (r.offense_snaps or 0) + (r.defense_snaps or 0) + (r.st_snaps or 0) > 0}
snap_od = collections.defaultdict(set)
for r in sn.itertuples():
    if (r.offense_snaps or 0) + (r.defense_snaps or 0) > 0: snap_od[K(r.team, r.player)].add(int(r.week))
official = {(int(r.week), K(r.team, r.full_name)) for r in inj.itertuples() if isinstance(r.report_status, str)}
reserve = {(int(r.week), K(r.team, r.player_name)) for r in ros.itertuples() if r.status in ("RES", "PUP", "NFI", "SUS")}
st = db.get_store()
rows = st.select("injuries", {"sport": "nfl"})
games = {g["game_id"]: g for g in st.select("games", {"sport": "nfl", "season": 2026})}
preds = [p for p in st.select("predictions", {"sport": "nfl"}) if p["model_version"] == "baseline-v1" and p["game_id"].startswith("2026_")]
removed, kept_lt, changed, ALL = [], [], [], []
for p in sorted(preds, key=lambda p: p["game_id"]):
    gid = p["game_id"]; wk = int(gid[5:7]); g = games[gid]
    if wk not in WEEKS: continue
    at = parse_dt(p["generated_at"])
    cur = latest_injury_report([r for r in rows if parse_dt(r.get("pulled_at")) and parse_dt(r["pulled_at"]) <= at])
    by = collections.defaultdict(list)
    for r in cur: by[K(r["team"], r["player"])].append(r)
    c = p["components"] if isinstance(p["components"], dict) else json.loads(p["components"])
    delta = 0.0
    for side, sign in (("home", 1), ("away", -1)):
        team = g[f"{side}_team"]; br = c["layer2"].get(f"{side}_injuries") or []
        rem = []
        for b in br:
            if (b.get("status") or "") == "inactive": continue          # inactive-list row: untouched (R3)
            src = by.get(K(team, b["player"]), [])
            if not src or any(r["source"] != "espn" or int(r.get("week") or 0) >= wk for r in src): continue
            rw = max(int(r.get("week") or 0) for r in src); k = K(team, b["player"])
            window = set(range(rw + 1, wk))
            lt_reason = ("ir" if (b.get("status") or "") == "ir" else "reserve" if (wk, k) in reserve else
                         "no snaps since" if window and not (snap_od[k] & window) else None)
            rec = dict(wk=wk, gid=gid, team=team, player=b["player"], status=b.get("status"), pts=b["points"], row_week=rw,
                       played=(wk, k) in snap_any, on_report=(wk, k) in official, lt=lt_reason)
            (kept_lt if lt_reason else rem).append(rec); ALL.append({**rec, "fate": lt_reason or "would drop"})
        if rem:
            raw = sum(x["points"] for x in br); d = min(raw, INJURY_MAX_POINTS) - min(raw - sum(x["pts"] for x in rem), INJURY_MAX_POINTS)
            delta += sign * d; removed += rem
    if delta and g.get("home_points") is not None:
        am = g["home_points"] - g["away_points"]; m0 = p["model_margin_home"]; m1 = m0 + delta; sp = p["market_spread"]
        ats = lambda m: "P" if am + sp == 0 else ("W" if (am + sp > 0) == (m + sp > 0) else "L")
        changed.append((wk, gid, round(delta, 2), m0, round(m1, 2), am, abs(m0 - am), abs(m1 - am), ats(m0), ats(m1)))
n = len(removed); pl = sum(r["played"] for r in removed); bad = [r for r in removed if not r["played"] and r["on_report"]]
print(f"weeks {WEEKS}: removed {n} charges ({sum(r['pts'] for r in removed):.2f} pts); kept as long-term {len(kept_lt)} ({collections.Counter(r['lt'] for r in kept_lt)})")
print(f"R1a played that game: {pl}/{n} = {100*pl/max(1,n):.1f}%  (gate >= 80%)")
print(f"R1b removed but did not play AND on official report: {len(bad)}  (gate 0)")
for r in bad: print("   ", r)
lt_wrong = [r for r in removed if r["status"] == "ir" or (r["wk"], K(r["team"], r["player"])) in reserve]
print(f"R2 long-term absences removed: {len(lt_wrong)}  (gate 0)")
print("removed rows:")
for r in removed: print(f"  wk{r['wk']} {r['gid']:<17} {r['team']:<4} {r['player']:<26} {str(r['status']):<12} {r['pts']:>5.2f} rowwk {r['row_week']} played {r['played']} on_report {r['on_report']}")
print("R4 changed graded games:")
for x in changed: print("  ", x)
if changed:
    for w in WEEKS:
        cw = [x for x in changed if x[0] == w]
        if cw: print(f"  wk{w}: {len(cw)} games MAE {sum(x[6] for x in cw)/len(cw):.2f} -> {sum(x[7] for x in cw)/len(cw):.2f}; ATS W {sum(x[8]=='W' for x in cw)} -> {sum(x[9]=='W' for x in cw)}")
print("\nALL feed-sourced charges older than the game's week:")
for r in ALL: print(f"  {r['gid']:<17} {r['team']:<4} {r['player']:<26} {str(r['status']):<12} {r['pts']:>5.2f} from wk{r['row_week']} -> {r['fate']}")
