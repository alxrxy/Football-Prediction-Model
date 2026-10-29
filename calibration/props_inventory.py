"""Pool every graded prop row, weeks 4-7: per game, the last archived list generated before kickoff (P67 rule).
Rows: top 25 ('props') + 'more'. Graded vs nflverse weekly stats; snap-count row with no stat row -> 0; no snaps -> void."""
import sys, os, json, glob, collections; sys.path.insert(0, os.getcwd())
import pandas as pd, nfl_data_py as nfl
from datetime import datetime
from src.ingest_injuries import player_key
st = pd.read_csv(sys.argv[1]); snaps = nfl.import_snap_counts([2026])
COL = {"player_pass_yds": "passing_yards", "player_rush_yds": "rushing_yards", "player_reception_yds": "receiving_yards", "player_receptions": "receptions"}
stat = {(int(r.week), player_key(r.team, r.player_display_name)): r for r in st.itertuples()}
played = {(int(r.week), player_key(r.team, r.player)) for r in snaps.itertuples() if (r.offense_snaps or 0) + (r.st_snaps or 0) > 0}
ts = lambda x: datetime.fromisoformat(str(x).replace("Z", "+00:00"))
files = sorted(glob.glob("data/props_archive/2026_w0*/*.json"))
docs = [(ts(json.load(open(f))["generated_at"]), f) for f in files]
last = {}   # game -> (gen, file)
for gen, f in docs:
    d = json.load(open(f))
    for r in d["props"] + d["more"]:
        if gen < ts(r["kickoff"]) and (r["game_id"] not in last or last[r["game_id"]][0] < gen): last[r["game_id"]] = (gen, f)
out = []
for gid, (gen, f) in sorted(last.items()):
    d = json.load(open(f)); wk = int(gid[5:7])
    for part in ("props", "more"):
        for i, r in enumerate(x for x in d[part] if x["game_id"] == gid):
            k = (wk, player_key(r["team"], r["odds_name"])); s = stat.get(k)
            if s is None and k not in played: res, v = "void", None
            else:
                v = getattr(s, COL[r["market"]]) if s is not None else 0; v = 0 if pd.isna(v) else float(v)
                res = "P" if v == r["line"] else ("W" if (v > r["line"]) == (r["pick"] == "over") else "L")
            u = (r["price"] / 100 if r["price"] > 0 else 100 / -r["price"]) if res == "W" else (-1.0 if res == "L" else 0.0)
            out.append({**{k2: r.get(k2) for k2 in ("game_id", "player", "team", "position", "market", "line", "pick", "price", "gap", "gap_adjusted", "p_model", "p_market", "books", "rank", "passes_stage1", "touches")},
                        "week": wk, "part": part, "file": os.path.basename(f), "served_at": gen.isoformat(), "hours_before": (ts(r["kickoff"]) - gen).total_seconds() / 3600,
                        "actual": v, "result": res, "u": u})
df = pd.DataFrame(out); df.to_csv(sys.argv[2], index=False)
g = df[df.result.isin(["W", "L"])]
print(f"rows {len(df)}, graded W/L {len(g)}, push {sum(df.result=='P')}, void {sum(df.result=='void')}, games {df.game_id.nunique()}")
def tab(by):
    t = g.groupby(by).agg(n=("result", "size"), w=("result", lambda s: (s == "W").sum()), u=("u", "sum"))
    t["win%"] = (100 * t.w / t.n).round(1); t["roi%"] = (100 * t.u / t.n).round(1); return t
print(tab(["week", "part"]).to_string())
print(tab("market").to_string())
g = g.assign(price_band=pd.cut(g.price, [-1000, -140, -115, -100, 100, 130, 1000], labels=["<=-140", "-139..-115", "-114..-101", "-100..+100", "+101..+130", ">+130"]),
             gap_band=pd.cut(g.gap, [0, .05, .10, .15, .20, .25, 1], labels=["0-.05", ".05-.10", ".10-.15", ".15-.20", ".20-.25", ">.25"]),
             rank_band=pd.cut(g["rank"].fillna(999), [0, 10, 25, 50, 100, 1000], labels=["1-10", "11-25", "26-50", "51-100", "100+"]),
             age_band=pd.cut(g.hours_before, [0, 3, 12, 48, 1000], labels=["<3h", "3-12h", "12-48h", ">48h"]))
for b in ["pick", "price_band", "gap_band", "rank_band", "age_band"]: print(tab(b).to_string())
print(tab(["market", "pick"]).to_string())
g.to_pickle(sys.argv[2] + ".pkl")
