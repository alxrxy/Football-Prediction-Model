"""P17 recheck on 2026 weeks 1-4, the frozen 9/19 design. Read-only; nothing live.

    python research/p17/p17_recheck_2026.py

Criteria set with the user 2026-09-30 (calibration-log.md, P17 row), before running:
- the decision claim: is per-player efficiency modelling worth building;
- the 9/19 design re-run FROZEN: k = 100, position prior, prior season at weight 0.5, outcome-aware crediting with
  IPF, targets split by pre-week category shares; no re-tuning; each week sees only earlier data;
- REOPEN if the rec-yds MSE gain vs the current engine is >= 1% and better in >= 3 of 4 weeks, else still closed;
- bootstrap CI reported alongside; receptions MSE and tercile calibration reported, not gated.

The scoring functions are the harness's own (`p17_walkforward.py`), executed from its source with one edit: the
prior-season literal 2024 becomes 2025 (asserted to occur exactly once). Seasons shift by one: history = 2025 at
weight 0.5 + 2026 weeks before w.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
import nfl_data_py as nfl  # noqa: E402
from src import sim_data as sd  # noqa: E402

PRIOR, CUR, WEEKS = 2025, 2026, range(1, 5)
K, PRIOR_KIND, W_PRIOR = 100, "pos", 0.5          # frozen 9/19 choice
CHOSEN = f"k{K}-{PRIOR_KIND}-w24={W_PRIOR}"

src = (HERE / "p17_walkforward.py").read_text(encoding="utf-8")
body = src[src.index("EDGES = ["):src.index("VARIANTS = [")]
start = body.index("def rates(")
pre, funcs = body[:start], body[start:]
assert funcs.count('hist["season"] == 2024') == 1
funcs = funcs.replace('hist["season"] == 2024', f'hist["season"] == {PRIOR}')

pbp = sd.load_pbp((PRIOR, CUR))
pbp = pbp[pbp["season_type"] == "REG"] if "season_type" in pbp else pbp
t = pbp[(pbp["pass_attempt"] == 1) & (pbp["sack"] != 1) & pbp["receiver_player_id"].notna()
        & (pbp["play_type"] == "pass")].copy()
t["cat"] = np.where(t["yardline_100"] <= sd.RZ_YL, 0, np.where(t["air_yards"].fillna(0) >= sd.DEEP_AIR_YARDS, 1, 2))
t["cmp"] = (t["complete_pass"] == 1).astype(int)
t["yds"] = np.where(t["cmp"] == 1, t["yards_gained"].fillna(0), 0.0)
g = {"np": np, "pd": pd, "nfl": nfl, "sd": sd, "t": t}
# the harness's bins and roster positions, for the shifted seasons
exec(pre.replace("[2024, 2025]", f"[{PRIOR}, {CUR}]"), g)
exec(funcs, g)
t = g["t"]
print(f"pbp {PRIOR}-{CUR}: {len(t):,} targeted passes; {CUR} weeks present: {sorted(t[t.season == CUR].week.unique())}")

rows = []
for w in WEEKS:
    hist = t[(t["season"] == PRIOR) | ((t["season"] == CUR) & (t["week"] < w))]
    wk = t[(t["season"] == CUR) & (t["week"] == w)]
    actual = wk.groupby(["game_id", "posteam", "pid"]).agg(yds=("yds", "sum"), rec=("cmp", "sum"), tgt=("pid", "size")).reset_index()
    team_tot = actual.groupby(["game_id", "posteam"])[["yds", "rec"]].sum()
    own_all = hist.groupby("pid").agg(ht=("pid", "size"), hy=("yds", "sum"))
    catmix = hist.groupby(["pid", "cat"]).size().unstack(fill_value=0).reindex(columns=range(3), fill_value=0)
    posmix = hist.groupby(["pos", "cat"]).size().unstack(fill_value=0).reindex(columns=range(3), fill_value=0)
    posmix = posmix.div(posmix.sum(1), axis=0)
    for name, k, prior, w24 in (("baseline", None, None, 1.0), (CHOSEN, K, PRIOR_KIND, W_PRIOR),
                                ("posprior-only", 1e9, "pos", 1.0)):
        pr = g["predict"](wk, *g["rates"](hist, w24), k, prior, catmix, posmix)
        pr = pr.groupby(["game_id", "team", "pid"])[["yds_raw", "rec_raw"]].sum().reset_index()
        m = actual.merge(pr, left_on=["game_id", "posteam", "pid"], right_on=["game_id", "team", "pid"])
        for col, raw in (("yds", "yds_raw"), ("rec", "rec_raw")):
            s = m.groupby(["game_id", "posteam"])[raw].transform("sum")
            tt = m.set_index(["game_id", "posteam"]).index.map(team_tot[col])
            m[col + "_pred"] = np.where(s > 0, m[raw] / s * np.asarray(tt, float), 0.0)
        m = m.merge(own_all, left_on="pid", right_index=True, how="left")
        m["variant"], m["week"] = name, w
        rows.append(m[["variant", "week", "game_id", "posteam", "pid", "tgt", "yds", "rec", "yds_pred", "rec_pred", "ht", "hy"]])
    print(f"week {w}: {len(actual)} receiver-games", flush=True)

df = pd.concat(rows, ignore_index=True)
df.to_pickle(HERE / "p17_recheck_2026.pkl")


def mse(x, c):
    return float(((x[c + "_pred"] - x[c]) ** 2).mean())


b = df[df.variant == "baseline"]
tg = b.groupby(["week", "game_id", "posteam"])[["yds", "yds_pred", "rec", "rec_pred"]].sum()
print(f"\nidentity: max |sum pred - team actual| yds {np.abs(tg.yds_pred - tg.yds).max():.2e}, rec {np.abs(tg.rec_pred - tg.rec).max():.2e}")
print(f"receiver-games scored: {len(b)} ({b.groupby('week').size().to_dict()})")

base_y, base_r = mse(b, "yds"), mse(b, "rec")
print("\n== 2026 weeks 1-4 ==")
for v in ["baseline", "posprior-only", CHOSEN]:
    x = df[df.variant == v]
    per = {w: mse(x[x.week == w], "yds") / mse(b[b.week == w], "yds") - 1 for w in WEEKS}
    better = sum(d < 0 for d in per.values())
    print(f"  {v:<18} yds MSE {mse(x, 'yds'):8.1f} ({(mse(x, 'yds') / base_y - 1) * 100:+.2f}%)  better in {better}/4 weeks"
          f"  per week {', '.join(f'{w}:{d * 100:+.2f}%' for w, d in per.items())}"
          f" | rec MSE {mse(x, 'rec'):.3f} ({(mse(x, 'rec') / base_r - 1) * 100:+.2f}%)")

g0 = b.set_index(["week", "game_id", "posteam", "pid"])
g1 = df[df.variant == CHOSEN].set_index(["week", "game_id", "posteam", "pid"])
j = g0.join(g1[["yds_pred"]], rsuffix="_b").reset_index()
j["e0"], j["e1"] = (j.yds_pred - j.yds) ** 2, (j.yds_pred_b - j.yds) ** 2
tgsum = j.groupby(["week", "game_id", "posteam"])[["e0", "e1"]].sum()
rng = np.random.default_rng(0)
bs = np.array([(lambda s: s.e1.sum() / s.e0.sum() - 1)(tgsum.iloc[rng.integers(0, len(tgsum), len(tgsum))]) for _ in range(1000)])
gain = tgsum.e1.sum() / tgsum.e0.sum() - 1
print(f"  {CHOSEN} yds change {gain * 100:+.2f}%; team-game bootstrap 90% CI {np.percentile(bs, 5) * 100:+.2f}% to "
      f"{np.percentile(bs, 95) * 100:+.2f}%, 95% CI {np.percentile(bs, 2.5) * 100:+.2f}% to {np.percentile(bs, 97.5) * 100:+.2f}%")

per = {w: mse(g1.reset_index().query("week == @w"), "yds") / mse(b[b.week == w], "yds") - 1 for w in WEEKS}
reopen = gain <= -0.01 and sum(d < 0 for d in per.values()) >= 3
print(f"\nDECISION RULE (gain >= 1% and better in >= 3 of 4 weeks): gain {-gain * 100:+.2f}%, weeks better "
      f"{sum(d < 0 for d in per.values())}/4  -> {'REOPEN (design discussion; nothing built)' if reopen else 'STILL CLOSED'}")

print("\n== tercile calibration (players with 20+ prior targets, terciles by pre-week own yds/target) ==")
e = df[df.ht >= 20].copy()
e["ypt"] = e.hy / e.ht
cuts = e[e.variant == "baseline"].ypt.quantile([1 / 3, 2 / 3]).to_numpy()
e["terc"] = np.digitize(e.ypt, cuts)
for v in ["baseline", "posprior-only", CHOSEN]:
    x = e[e.variant == v].groupby("terc")[["yds_pred", "yds", "rec_pred", "rec"]].sum()
    print(f"  {v:<18} yds pred/actual  bottom {x.yds_pred[0] / x.yds[0]:.3f}  middle {x.yds_pred[1] / x.yds[1]:.3f}  top {x.yds_pred[2] / x.yds[2]:.3f}"
          f"   | rec bottom {x.rec_pred[0] / x.rec[0]:.3f} top {x.rec_pred[2] / x.rec[2]:.3f}")
print(f"  n per tercile: {e[e.variant == 'baseline'].groupby('terc').size().to_dict()}; cut points {cuts.round(2)}")
