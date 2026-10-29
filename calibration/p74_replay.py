"""P74 replay, weeks 1-7, on the served baseline breakdowns (10/15 method). Read-only.
Expected starter (walk-forward): most 2026 QB offensive snaps for the team in weeks before this game; week 1 (or no
2026 snaps yet): the 2025 leader for that team. A QB row is removed when it is not the expected starter and the
expected starter is not in the breakdown under a ruled-out status. Team charge recomputed with the 8.0 cap."""
import json, sys, collections; sys.path.insert(0, ".")
import pandas as pd, nfl_data_py as nfl
from src import db
from src.ingest_injuries import player_key
from src.features import INJURY_MAX_POINTS, LEADER_RULED_STATUSES
K = lambda t, n: player_key(t, n)[1]
sn = nfl.import_snap_counts([2025, 2026]); q = sn[(sn.position == "QB") & (sn.game_type == "REG")]
stats = pd.read_csv(sys.argv[1]); stats = stats[stats.season == 2026]
att = collections.defaultdict(dict)
for r in stats.itertuples():
    if r.attempts and r.attempts > 0: att[(r.week, r.team)][K(r.team, r.player_display_name)] = r.attempts
snapped = {(int(r.week), r.team, K(r.team, r.player)): r.offense_snaps for r in q[q.season == 2026].itertuples()}
def expected(team, wk):
    d = q[(q.season == 2026) & (q.team == team) & (q.week < wk)]
    if not len(d) or d.offense_snaps.sum() == 0: d = q[(q.season == 2025) & (q.team == team)]
    return d.groupby("player")["offense_snaps"].sum().idxmax() if len(d) else None
st = db.get_store()
games = {g["game_id"]: g for g in st.select("games", {"sport": "nfl", "season": 2026})}
preds = [p for p in st.select("predictions", {"sport": "nfl"}) if p["model_version"] == "baseline-v1" and p["game_id"].startswith("2026_")]
G1 = G2 = True; changed = []; wkagg = collections.defaultdict(lambda: [0, 0.0, 0, 0.0, 0.0, 0, 0, 0]); removed_all = []
for p in sorted(preds, key=lambda p: p["game_id"]):
    gid = p["game_id"]; g = games[gid]; wk = int(gid[5:7])
    if wk > 7: continue
    c = p["components"] if isinstance(p["components"], dict) else json.loads(p["components"]); l2 = c["layer2"]
    delta = 0.0; notes = []
    for side, sign in (("home", 1), ("away", -1)):
        team = g[f"{side}_team"]; rows = l2.get(f"{side}_injuries") or []
        exp = expected(team, wk); 
        if exp is None: continue
        ek = K(team, exp)
        if any((r.get("position") or "").upper() == "QB" and K(team, r["player"]) == ek and (r.get("status") or "").lower() in LEADER_RULED_STATUSES for r in rows):
            continue
        rem = [r for r in rows if (r.get("position") or "").upper() == "QB" and K(team, r["player"]) != ek]
        if not rem: continue
        raw = sum(r["points"] for r in rows); old = min(raw, INJURY_MAX_POINTS); new = min(raw - sum(r["points"] for r in rem), INJURY_MAX_POINTS)
        d = old - new; delta += sign * d
        a = att.get((wk, team), {}); starter = max(a, key=a.get) if a else None
        for r in rem:
            rk = K(team, r["player"]); took = snapped.get((wk, team, rk), 0) or 0
            g1 = (starter is not None and rk != starter) or took > 0
            g2 = starter is not None and starter in (ek, rk)
            G1 &= g1; G2 &= g2
            removed_all.append(dict(wk=wk, gid=gid, team=team, qb=r["player"], status=r.get("status"), pts=r["points"], snaps=took,
                                    expected=exp, actual_starter=starter, g1=g1, g2=g2, p48=r.get("share_source") in (None, "default")))
        notes.append(f"{team} -{','.join(r['player'] for r in rem)} {d:.2f}")
    if not delta: continue
    am = (g["home_points"] - g["away_points"]) if g.get("home_points") is not None else None
    m0 = p["model_margin_home"]; m1 = m0 + delta; sp = p["market_spread"]
    def ats(m):
        if am is None or sp is None: return "-"
        cv = am + sp; ln = m + sp
        return "P" if cv == 0 else ("W" if (cv > 0) == (ln > 0) else "L")
    changed.append((gid, notes, m0, m1, am, ats(m0), ats(m1)))
    w = wkagg[wk]; w[0] += 1; w[1] += abs(delta)
    if am is not None: w[2] += 1; w[3] += abs(m0 - am); w[4] += abs(m1 - am); w[5] += ats(m0) == "W"; w[6] += ats(m1) == "W"
print(f"removed charges: {len(removed_all)}  pts {sum(r['pts'] for r in removed_all):.2f}  (no-snap/default-share subset {sum(r['p48'] for r in removed_all)})")
for r in removed_all: print(f"  wk{r['wk']} {r['gid']:<17} {r['team']:<4} {r['qb']:<22} {str(r['status']):<12} {r['pts']:>5.2f} snaps {r['snaps']:>4} | expected {r['expected']} | actual starter {r['actual_starter']} | G1 {'ok' if r['g1'] else 'FAIL'} G2 {'ok' if r['g2'] else 'FAIL'}")
print(f"\nG1 {'PASS' if G1 else 'FAIL'} ({sum(r['g1'] for r in removed_all)}/{len(removed_all)})   G2 {'PASS' if G2 else 'FAIL'} ({sum(r['g2'] for r in removed_all)}/{len(removed_all)})")
print("\nG4 changed games:")
for gid, notes, m0, m1, am, a0, a1 in changed: print(f"  {gid:<17} {'; '.join(notes):<40} margin {m0:+.1f} -> {m1:+.1f} actual {am} | abs err {abs(m0-am) if am is not None else '-'} -> {abs(m1-am) if am is not None else '-'} | ATS {a0} -> {a1}")
print("week: games changed, |delta| pts, graded, MAE before, MAE after (changed games), ATS W before, after")
for wk in sorted(wkagg):
    w = wkagg[wk]; print(f"  wk{wk}: {w[0]} games, {w[1]:.2f} pts, graded {w[2]}, MAE {w[3]/max(1,w[2]):.2f} -> {w[4]/max(1,w[2]):.2f}, ATS W {w[5]} -> {w[6]}")
