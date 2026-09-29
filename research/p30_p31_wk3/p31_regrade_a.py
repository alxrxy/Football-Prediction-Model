"""Run from this directory after p31_roles_week.py has written w2.parquet / w3.parquet:
  python p31_roles_week.py 2 2026-09-20T15:48:41Z w2.parquet
  python p31_roles_week.py 3 2026-09-27T15:45:00Z w3.parquet"""
import numpy as np, pandas as pd
def prep(f, drop=()):
    v = pd.read_parquet(f)
    v = v[~v["team"].isin(drop)].copy()
    for a in ("off", "on"):
        v[f"n_{a}"] = v.groupby("team")[f"w_{a}"].transform(lambda s: s / s.sum() if s.sum() > 0 else s)
        v[f"e_{a}"] = v[f"n_{a}"] * v["team_act"]
    v["pq"] = pd.qcut(v["n_off"].where(v["n_off"] >= 0.02), 4, labels=["Q1", "Q2", "Q3", "Q4"])
    v["top2"] = v.groupby("team")["n_off"].rank(ascending=False, method="first") <= 2
    v["tw"] = v["week"].astype(str) + v["team"]
    return v
def report(v, label, B=3000):
    rng = np.random.default_rng(1)
    print(f"\n== {label}: {v['tw'].nunique()} team-games, {len(v)} pool rows, {int(v.groupby('tw')['team_act'].first().sum())} real targets")
    for a in ("off", "on"):
        raw = v.groupby("tw")[f"w_{a}"].sum().mean()
        pq = v.dropna(subset=["pq"]).groupby("pq", observed=True).apply(lambda x: x["act"].sum() / x[f"e_{a}"].sum())
        mae = (v[f"n_{a}"] - v["act"] / v["team_act"]).abs().mean()
        t = v[v["top2"]]
        tws = t["tw"].unique(); g = {k: d for k, d in t.groupby("tw")}
        bs = []
        for _ in range(B):
            pick = rng.choice(tws, len(tws))
            a_ = sum(g[k]["act"].sum() for k in pick); e_ = sum(g[k][f"e_{a}"].sum() for k in pick)
            bs.append(a_ / e_)
        print(f"  trim {a:<3} raw sum {raw:.3f} | pregame-quartile real/sim " +
              " ".join(f"{k} {pq.get(k):.3f}" for k in ("Q1", "Q2", "Q3", "Q4")) +
              f" | top-2 {t['act'].sum()/t[f'e_{a}'].sum():.3f} [{np.percentile(bs,2.5):.3f}, {np.percentile(bs,97.5):.3f}] | MAE {mae:.4f}")
    cut = v[(v["w_off"] > 0) & (v["w_on"] == 0)]
    tot = v.groupby("tw")["team_act"].first().sum()
    print(f"  trimmed: {len(cut)} players, raw share {cut['w_off'].sum()/v['tw'].nunique():.3f}/team; real targets taken "
          f"{int(cut['act'].sum())} = {cut['act'].sum()/tot:.1%}; with >=1 target {(cut['act']>0).sum()}")
w2s = prep(f"w2.parquet", drop=("NYG", "LA"))
report(w2s, "week 2 Sunday only (reproduces 9/21)")
w2, w3 = prep("w2.parquet"), prep("w3.parquet")
report(w2, "week 2 incl. MNF")
report(w3, "week 3 (Sunday + MNF)")
# pooled: quartiles cut within each week, then pooled
report(pd.concat([w2, w3]), "POOLED weeks 2-3")
