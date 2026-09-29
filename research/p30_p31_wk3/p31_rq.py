"""9/20-style realised-share quartiles, pooled per player over the window (definition check)."""
import sys; sys.argv=[sys.argv[0]]
import numpy as np, pandas as pd
import p31_partial as P
test25 = pd.concat([P.load(2025, w, "pre") for w in range(11, 19)], ignore_index=True)
test26 = pd.concat([P.load(2026, 2, "prod"), P.load(2026, 3, "prod")], ignore_index=True)
for label, v in (("2025 wk 11-18", test25), ("2026 wk 2-3", test26)):
    print("==", label)
    for a in (1.0, 0.0, 0.3403):
        s = P.shares(v, a); x = v.assign(n=s["tgt"])
        x = x[x["position"].isin(P.SKILL)]
        for pop, flt in (("real>0", lambda d: d["real"] > 0), ("real>=2%", lambda d: d["real"] >= 0.02)):
            g = x.groupby(["team", "player_id"]).agg(n=("n", "mean"), a=("a_tgt", "sum"), T=("T_tgt", "sum"))
            g["real"] = g["a"] / g["T"]; g = g[flt(g)]
            g["q"] = pd.qcut(g["real"], 4, labels=False)
            r = g.groupby("q").apply(lambda d: d["n"].sum() / d["real"].sum())
            print(f"  alpha {a:.3f} {pop:<8} " + " ".join(f"Q{q+1} {r[q]:.3f}" for q in range(4)))
