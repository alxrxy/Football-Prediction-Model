import sys, json, glob, math, collections; sys.path.insert(0, ".")
import pandas as pd
from src.ingest_injuries import player_key
st = pd.read_csv(sys.argv[1]); st = st[st.season == 2026]
stat = {(int(r.week), player_key(r.team, r.player_display_name)): r for r in st.itertuples()}
rows = []
for f in sorted(glob.glob("data/sims_archive/2026_w0*.json")):
    d = json.load(open(f)); wk = int(d["week"])
    for s in d["slates"]:
        for g in s["games"]:
            pg = g.get("pregame") or {}
            if not pg or pg.get("after_kickoff") or not g.get("actual"): continue
            for side in ("home", "away"):
                team = g[side] if isinstance(g[side], str) else g[side].get("abbr") or g[side].get("team")
                for p in (pg.get("scorers") or {}).get(side) or []:
                    if p.get("actual_tds") is None: continue
                    s_ = stat.get((wk, player_key(team, p["player"])))
                    rows.append(dict(week=wk, game_id=g["game_id"], team=team, player=p["player"], pos=p["position"], depth=p.get("depth_rank"),
                                     p=p["anytime_td"], exp=p.get("expected_tds"), y=int(p["actual_tds"] > 0), n_td=p["actual_tds"],
                                     rz_t=p.get("rz_target_share"), rz_c=p.get("rz_carry_share"), gl_c=p.get("gl_carry_share"),
                                     rush_td=getattr(s_, "rushing_tds", None) if s_ is not None else None, rec_td=getattr(s_, "receiving_tds", None) if s_ is not None else None,
                                     sim_team_td=sum(float(k.rstrip("+")) * v for k, v in pg["td"][side].items() if k[0].isdigit())))
df = pd.DataFrame(rows); df.to_pickle(sys.argv[2])
print("rows", len(df), "games", df.game_id.nunique(), "by week", df.groupby("week").size().to_dict())
ll = lambda p, y: -(y * math.log(max(p, 1e-6)) + (1 - y) * math.log(max(1 - p, 1e-6)))
df["brier"] = (df.p - df.y) ** 2; df["ll"] = [ll(a, b) for a, b in zip(df.p, df.y)]
print(f"overall mean p {df.p.mean():.3f} rate {df.y.mean():.3f} Brier {df.brier.mean():.4f} logloss {df.ll.mean():.4f}; sum expected TDs {df.exp.sum():.0f} vs actual {df.n_td.sum():.0f}")
df["band"] = pd.cut(df.p, [0, .05, .1, .2, .3, .4, .5, 1])
print(df.groupby("band").agg(n=("y", "size"), mean_p=("p", "mean"), rate=("y", "mean"), brier=("brier", "mean"), ll=("ll", "mean")).round(3).to_string())
print(df.groupby("pos").agg(n=("y", "size"), mean_p=("p", "mean"), rate=("y", "mean"), exp=("exp", "sum"), act=("n_td", "sum"), brier=("brier", "mean")).round(3).to_string())
print(df.groupby("week").agg(mean_p=("p", "mean"), rate=("y", "mean"), exp=("exp", "sum"), act=("n_td", "sum")).round(3).to_string())
g = df.groupby(["game_id", "team"]).agg(sim=("sim_team_td", "first")); print("sim team TDs per game mean", round(g.sim.mean(), 2))
pos_split = df[df.rush_td.notna()].groupby("pos")[["rush_td", "rec_td"]].sum(); print("actual TD type by position (stat rows):\n", pos_split.to_string())
