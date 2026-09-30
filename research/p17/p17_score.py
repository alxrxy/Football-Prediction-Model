from pathlib import Path
import numpy as np
import pandas as pd
OUT = Path(__file__).parent
df = pd.read_pickle(OUT / "p17_wf2.pkl")
mse = lambda g, c: float(((g[c + "_pred"] - g[c]) ** 2).mean())

# identity: per team-game predictions sum to the actual team totals
b = df[df.variant == "baseline"]
tg = b.groupby(["week", "game_id", "posteam"])[["yds", "yds_pred", "rec", "rec_pred"]].sum()
print(f"identity: max |sum pred - team actual| yds {np.abs(tg.yds_pred - tg.yds).max():.2e}, rec {np.abs(tg.rec_pred - tg.rec).max():.2e}")

tr, te = df[df.week <= 10], df[df.week >= 11]
base_tr, base_te = mse(tr[tr.variant == "baseline"], "yds"), mse(te[te.variant == "baseline"], "yds")
sel = sorted(((mse(tr[tr.variant == v], "yds") / base_tr - 1, v) for v in df.variant.unique() if v != "baseline"))
print("\nselection on weeks 3-10 (yds MSE vs baseline), best 6:")
for d, v in sel[:6]:
    print(f"  {v:<20} {d * 100:+.2f}%")
best = sel[0][1]
print(f"\nchosen: {best}")

print("\n== judged on weeks 11-18 ==")
for v in ["baseline", "posprior-only", best]:
    g = te[te.variant == v]
    wk_better = sum(mse(g[g.week == w], "yds") < mse(te[(te.variant == "baseline") & (te.week == w)], "yds") for w in range(11, 19))
    rb = mse(te[te.variant == "baseline"], "rec")
    print(f"  {v:<20} yds MSE {mse(g, 'yds'):8.1f} ({(mse(g, 'yds') / base_te - 1) * 100:+.2f}%)  better in {wk_better}/8 weeks"
          f" | rec MSE {mse(g, 'rec'):.3f} ({(mse(g, 'rec') / rb - 1) * 100:+.2f}%)")

# bootstrap CI on the out-of-sample yds improvement, resampling team-games
g0 = te[te.variant == "baseline"].set_index(["week", "game_id", "posteam", "pid"])
g1 = te[te.variant == best].set_index(["week", "game_id", "posteam", "pid"])
j = g0.join(g1[["yds_pred"]], rsuffix="_b").reset_index()
j["e0"], j["e1"] = (j.yds_pred - j.yds) ** 2, (j.yds_pred_b - j.yds) ** 2
tgsum = j.groupby(["week", "game_id", "posteam"])[["e0", "e1"]].sum()
rng = np.random.default_rng(0)
bs = [(lambda s: s.e1.sum() / s.e0.sum() - 1)(tgsum.iloc[rng.integers(0, len(tgsum), len(tgsum))]) for _ in range(1000)]
print(f"  {best} yds improvement 90% CI (team-game bootstrap): {np.percentile(bs, 5) * 100:+.2f}% to {np.percentile(bs, 95) * 100:+.2f}%")

print("\n== tercile calibration, weeks 11-18 (players with 20+ prior targets, terciles by pre-week own yds/target) ==")
e = te[te.ht >= 20].copy()
e["ypt"] = e.hy / e.ht
cuts = e[e.variant == "baseline"].ypt.quantile([1 / 3, 2 / 3]).to_numpy()
e["terc"] = np.digitize(e.ypt, cuts)
for v in ["baseline", "posprior-only", best]:
    g = e[e.variant == v].groupby("terc")[["yds_pred", "yds", "rec_pred", "rec"]].sum()
    print(f"  {v:<20} yds pred/actual  bottom {g.yds_pred[0] / g.yds[0]:.3f}  middle {g.yds_pred[1] / g.yds[1]:.3f}  top {g.yds_pred[2] / g.yds[2]:.3f}"
          f"   | rec bottom {g.rec_pred[0] / g.rec[0]:.3f} top {g.rec_pred[2] / g.rec[2]:.3f}")
print(f"  tercile cut points (own yds/target): {cuts.round(2)}")
