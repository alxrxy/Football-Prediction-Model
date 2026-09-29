"""Is the 2026 week-1/2 compression an early-season effect, or noise?
Same harness, run on every comparable window, with bootstrap CIs."""
import sys
sys.path.insert(0, r"C:\Users\alexr\OneDrive\Desktop\Football Predictor")
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import numpy as np, pandas as pd
from p30_test import load_pbp, run_week, MIN_PRIOR_TGT

rng = np.random.default_rng(7)

def terciles(df):
    d = df[df["prior_tgt"] >= MIN_PRIOR_TGT].dropna(subset=["ypt_own"]).copy()
    if len(d) < 30: return None
    d["terc"] = pd.qcut(d["ypt_own"], 3, labels=["bottom", "mid", "top"])
    return d

def boot(g, col, B=2000):
    """Bootstrap the ratio by player-game."""
    a, b = g[col].to_numpy(), g["act_yds"].to_numpy()
    idx = rng.integers(0, len(a), (B, len(a)))
    r = a[idx].sum(1) / b[idx].sum(1)
    return np.percentile(r, [5, 95])

pbp = load_pbp((2023, 2024, 2025, 2026))

windows = [("2025 wk 1-2", 2025, (1, 2)), ("2025 wk 3-4", 2025, (3, 4)),
           ("2025 wk 5-10", 2025, tuple(range(5, 11))),
           ("2025 wk 11-18", 2025, tuple(range(11, 19))),
           ("2026 wk 1-2", 2026, (1, 2)), ("2026 wk 3", 2026, (3,)), ("2026 wk 1-3", 2026, (1, 2, 3))]

print(f"{'window':<15} {'n':>5}  {'top B/act':>22}  {'bottom B/act':>22}  {'all B/act':>9}")
for label, season, weeks in windows:
    out = []
    for wk in weeks:
        run_week(pbp, season, wk, out)
    d = terciles(pd.DataFrame(out))
    if d is None:
        print(f"{label:<15} too few"); continue
    top, bot = d[d["terc"] == "top"], d[d["terc"] == "bottom"]
    rt = top["B_yds"].sum() / top["act_yds"].sum()
    rb = bot["B_yds"].sum() / bot["act_yds"].sum()
    ct, cb = boot(top, "B_yds"), boot(bot, "B_yds")
    allr = d["B_yds"].sum() / d["act_yds"].sum()
    print(f"{label:<15} {len(d):>5}  {rt:>8.3f} [{ct[0]:.3f}, {ct[1]:.3f}]  "
          f"{rb:>8.3f} [{cb[0]:.3f}, {cb[1]:.3f}]  {allr:>9.3f}")
