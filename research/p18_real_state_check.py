"""P18 criterion 1 (read-only): at every real non-penalty snap inside the 10 (2023-25),
P(a play drawn from the engine's mapped bucket converts at that real spot), using the
engine's diagnostic rule (off_td or reaching the goal line counts as full distance;
conv = yards >= togo; penalty draws excluded, as in simulate.track). Compared with the
real conversion (yards_gained >= ydstogo or offensive TD) per down x distance bin."""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, r"C:\Users\alexr\OneDrive\Desktop\Football Predictor")
from src import sim_data as sd
t = sd.build_tables()
p = sd._scrimmage(sd._snaps(sd.load_pbp(sd.POOL_SEASONS)))
p = p[~p["pen"] & (p["yardline_100"] <= 10)].copy()
p["conv"] = (p["yards_gained"].fillna(0) >= p["ydstogo"]) | p["o_td"]
eng = np.empty(len(p))
for i, (dn, tg, yl) in enumerate(zip(p["down"].astype(int), p["ydstogo"].astype(int), p["yardline_100"].astype(int))):
    b = t.bucket_map[sd.bucket_index(dn, tg, yl)]
    r = np.arange(t.offsets[b], t.offsets[b + 1]); r = r[~t.is_penalty[r]]
    y = t.yards[r].astype(int)
    yd = np.where(t.off_td[r] | (yl - y <= 0), np.maximum(y, yl), y)
    eng[i] = (yd >= tg).mean()
p["eng"] = eng
p["dn"] = np.where(p["down"] >= 3, "3/4", p["down"].astype(int).astype(str))
p["dist"] = pd.cut(p["ydstogo"], [0, 2.5, 5.5, 9.5, 10.5, 99], labels=["0-2.5", "2.5-5.5", "5.5-9.5", "9.5-10.5", "10.5+"])
g = p.groupby(["dn", "dist"], observed=True).agg(n=("conv", "size"), real=("conv", "mean"), eng=("eng", "mean"))
g["gap_pp"] = 100 * (g["eng"] - g["real"])
g["test"] = np.where(g["n"] < 100, "n<100", np.where(g["gap_pp"].abs() <= 1.5, "pass", "MISS"))
print(f"tables v{sd.TABLES_VERSION}, zones {sd.N_ZONE}")
print(g.round(3).to_string())
for dn in (3, 4):
    q = p[(p["down"] == dn) & (p["ydstogo"] <= 2)]
    print(f"  down {dn} & 0-2.5 alone: n {len(q)} real {q.conv.mean():.3f} eng {q.eng.mean():.3f} gap {100*(q.eng.mean()-q.conv.mean()):+.2f}")
f = p[p["down"] == 1]
print(f"sub-10 1st downs: {len(f)}")
