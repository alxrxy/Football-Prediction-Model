"""P17 walk-forward, 2025 weeks 3-18. Read-only. See the 2026-09-19 P17 design-stage entry in calibration-log.md.

For each week w, per team-game and target category (rz / deep / short), receivers get the week's plays by
outcome-aware crediting (IPF: row sums = each receiver's actual share of that category's targets, column sums = the
league outcome mix), using outcome rates estimated only from pbp before week w. Predicted yards and receptions are then
scaled to the team-game's actual totals, so only the split between players is scored.
"""
import itertools, sys
from pathlib import Path
import numpy as np
import pandas as pd
ROOT = Path(r"C:\Users\alexr\OneDrive\Desktop\Football Predictor"); OUT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
import nfl_data_py as nfl  # noqa: E402
from src import sim_data as sd  # noqa: E402

pbp = sd.load_pbp((2024, 2025))
pbp = pbp[pbp["season_type"] == "REG"] if "season_type" in pbp else pbp
t = pbp[(pbp["pass_attempt"] == 1) & (pbp["sack"] != 1) & pbp["receiver_player_id"].notna()
        & (pbp["play_type"] == "pass")].copy()
t["cat"] = np.where(t["yardline_100"] <= sd.RZ_YL, 0, np.where(t["air_yards"].fillna(0) >= sd.DEEP_AIR_YARDS, 1, 2))
t["cmp"] = (t["complete_pass"] == 1).astype(int)
t["yds"] = np.where(t["cmp"] == 1, t["yards_gained"].fillna(0), 0.0)
EDGES = [-99, 4.5, 9.5, 19.5, 999]          # completion bands: <5, 5-9, 10-19, 20+
t["bin"] = np.where(t["cmp"] == 0, 0, np.digitize(t["yds"], EDGES[1:-1]) + 1)   # 0 = incomplete, 1..4
NB = 5
ros = nfl.import_seasonal_rosters([2024, 2025])[["player_id", "position", "season"]]
pos = ros.sort_values("season").drop_duplicates("player_id", keep="last").set_index("player_id")["position"]
t["pos"] = t["receiver_player_id"].map(pos).where(lambda s: s.isin(["WR", "TE", "RB"]), "WR")
t["pid"] = t["receiver_player_id"]


def rates(hist, w24):
    """League and position outcome mixes by category, per-player counts, and mean yards per bin."""
    wt = np.where(hist["season"] == 2024, w24, 1.0)
    h = hist.assign(w=wt)
    lg = h.groupby(["cat", "bin"])["w"].sum().unstack(fill_value=0).reindex(columns=range(NB), fill_value=0)
    lg = lg.div(lg.sum(1), axis=0)
    pp = h.groupby(["pos", "cat", "bin"])["w"].sum().unstack(fill_value=0).reindex(columns=range(NB), fill_value=0)
    pp = pp.div(pp.sum(1), axis=0)
    pl = h.groupby(["pid", "cat", "bin"])["w"].sum().unstack(fill_value=0).reindex(columns=range(NB), fill_value=0)
    ymean = h[h["cmp"] == 1].groupby(["cat", "bin"])["yds"].mean()
    return lg, pp, pl, ymean


def ipf(W, row, col, iters=200):
    W = W.copy()
    for _ in range(iters):
        W *= (row / np.maximum(W.sum(1), 1e-12))[:, None]
        W *= (col / np.maximum(W.sum(0), 1e-12))[None, :]
        if np.abs(W.sum(1) - row).max() < 1e-10:
            break
    return W


CAT_PRIOR_M = 10.0   # pseudo-targets of the position's category mix, for players with thin history


def predict(week_df, lg, pp, pl, ymean, k, prior, catmix, posmix):
    """Expected yards and receptions per (game, team, pid) before scaling to team totals.

    As the engine does it: each player's targets are split across categories by his PRE-WEEK category shares
    (not that week's actual split, which would leak the outcome), then each category's plays are credited.
    """
    out = []
    for (gid, team), g in week_df.groupby(["game_id", "posteam"]):
        tg = g.groupby("pid").agg(n=("pid", "size"), pos=("pos", "first"))
        q = []
        for pid, x in tg.iterrows():
            own = catmix.loc[pid].to_numpy(float) if pid in catmix.index else np.zeros(3)
            pm = posmix.loc[x["pos"]].to_numpy(float) if x["pos"] in posmix.index else np.full(3, 1 / 3)
            q.append((own + CAT_PRIOR_M * pm) / (own.sum() + CAT_PRIOR_M))
        q = np.array(q) * tg["n"].to_numpy(float)[:, None]          # expected targets by category
        yds = np.zeros(len(tg)); rec = np.zeros(len(tg))
        for cat in range(3):
            rowt = q[:, cat]
            n_tot = rowt.sum()
            if n_tot <= 0:
                continue
            share = rowt / n_tot
            mix = lg.loc[cat].to_numpy(float) if cat in lg.index else np.full(NB, 1 / NB)
            yb = np.array([0.0] + [ymean.get((cat, b), 0.0) for b in range(1, NB)])
            if k is None:
                W = share[:, None] * mix[None, :]
            else:
                P = []
                for pid, x in tg.iterrows():
                    pri = (pp.loc[(x["pos"], cat)].to_numpy(float) if prior == "pos" and (x["pos"], cat) in pp.index else mix)
                    own = pl.loc[(pid, cat)].to_numpy(float) if (pid, cat) in pl.index else np.zeros(NB)
                    P.append((own + k * pri) / (own.sum() + k))
                W = ipf(share[:, None] * np.array(P), share, mix)
            yds += (W * yb[None, :]).sum(1) * n_tot
            rec += W[:, 1:].sum(1) * n_tot
        for j, pid in enumerate(tg.index):
            out.append((gid, team, pid, float(yds[j]), float(rec[j])))
    return pd.DataFrame(out, columns=["game_id", "team", "pid", "yds_raw", "rec_raw"])


VARIANTS = [("baseline", None, None, 1.0)] + [
    (f"k{k}-{prior}-w24={w}", k, prior, w) for k, prior, w in itertools.product([10, 25, 50, 100, 200], ["lg", "pos"], [1.0, 0.5])]
VARIANTS.append(("posprior-only", 1e9, "pos", 1.0))    # position effect alone, no player signal

rows = []
for w in range(3, 19):
    hist = t[(t["season"] == 2024) | (t["week"] < w)]
    wk = t[(t["season"] == 2025) & (t["week"] == w)]
    actual = wk.groupby(["game_id", "posteam", "pid"]).agg(yds=("yds", "sum"), rec=("cmp", "sum"), tgt=("pid", "size")).reset_index()
    team_tot = actual.groupby(["game_id", "posteam"])[["yds", "rec"]].sum()
    own_all = hist.groupby("pid").agg(ht=("pid", "size"), hy=("yds", "sum"))
    catmix = hist.groupby(["pid", "cat"]).size().unstack(fill_value=0).reindex(columns=range(3), fill_value=0)
    posmix = hist.groupby(["pos", "cat"]).size().unstack(fill_value=0).reindex(columns=range(3), fill_value=0)
    posmix = posmix.div(posmix.sum(1), axis=0)
    cache = {}
    for name, k, prior, w24 in VARIANTS:
        if w24 not in cache:
            cache[w24] = rates(hist, w24)
        pr = predict(wk, *cache[w24], k, prior, catmix, posmix)
        pr = pr.groupby(["game_id", "team", "pid"])[["yds_raw", "rec_raw"]].sum().reset_index()
        m = actual.merge(pr, left_on=["game_id", "posteam", "pid"], right_on=["game_id", "team", "pid"])
        for col, raw in (("yds", "yds_raw"), ("rec", "rec_raw")):
            s = m.groupby(["game_id", "posteam"])[raw].transform("sum")
            tt = m.set_index(["game_id", "posteam"]).index.map(team_tot[col])
            m[col + "_pred"] = np.where(s > 0, m[raw] / s * np.asarray(tt, float), 0.0)
        m = m.merge(own_all, left_on="pid", right_index=True, how="left")
        m["variant"], m["week"] = name, w
        rows.append(m[["variant", "week", "game_id", "posteam", "pid", "tgt", "yds", "rec", "yds_pred", "rec_pred", "ht", "hy"]])
    print(f"week {w} done", flush=True)

df = pd.concat(rows, ignore_index=True)
df.to_pickle(OUT / "p17_wf2.pkl")
print("rows", len(df))
