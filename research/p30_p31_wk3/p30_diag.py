"""P30 diagnosis (criteria: calibration-log 2026-09-29, written before running).

The 9/29 re-check harness, unchanged except for the share:
  B0  raw usage_rates share (p30_test.run_week)            -> must reproduce 0.881
  B1  production roles vector, trim off, team-normalised   (roles_asof 'pre')
  B2  same, trim on (tau 0.10) = today's engine shares
  A   actual targets x league yds/target (efficiency only)
Bootstrap draws are generated in the same order as p30_recheck.py (seed 7,
top then bottom per window), and shared by every arm (paired).
"""
import os, sys
os.environ["USAGE_PARTICIPATION_TRIM"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, r"C:\Users\alexr\OneDrive\Desktop\Football Predictor")
sys.path.insert(0, HERE)
import numpy as np, pandas as pd
from p30_test import load_pbp, prep, BUCKETS, MIN_PRIOR_TGT
import p30_test
from src import simulate_nfl

CATS = {"rz": "tgt_rz", "deep": "tgt_deep", "short": "tgt_short"}


def role_shares(season, week):
    f = os.path.join(HERE, "roles", f"{season}_w{week:02d}_pre.parquet")
    if not os.path.exists(f):
        return None
    r = pd.read_parquet(f)
    out = {}
    for team, sq in r.groupby("team"):
        sq = sq.sort_values(["position", "rank"]).reset_index(drop=True)
        base = sq[list(CATS.values())].to_numpy(float)
        on = simulate_nfl._participation_trim(sq, base)
        for arm, m in (("B1", base), ("B2", on)):
            tot = m.sum(axis=0)
            n = np.divide(m, tot, out=np.zeros_like(m), where=tot > 0)
            for i, pid in enumerate(sq["player_id"]):
                out[(arm, team, pid)] = n[i]
    return out


def run_week(pbp, season, week, out):
    """p30_test.run_week, plus B1/B2 on the same rows."""
    start = len(out)
    p30_test.run_week(pbp, season, week, out)
    rs = role_shares(season, week)
    cur = prep(pbp[(pbp["season"] == season) & (pbp["week"] == week)])
    prior = pbp[(pbp["season"] < season) | ((pbp["season"] == season) & (pbp["week"] < week))]
    ypt_lg = prep(prior).groupby("bucket")["yds"].mean()
    y = np.array([ypt_lg[b] for b in BUCKETS])
    tc = cur.groupby(["game_id", "posteam", "bucket"]).size().unstack(fill_value=0)
    gid_of = cur.groupby(["posteam", "receiver_player_id"])["game_id"].first()
    own = cur.groupby(["posteam", "receiver_player_id", "bucket"]).size().unstack(fill_value=0)
    for row in out[start:]:
        row["A_tgt"] = row["Ax_tgt"] = row["act_tgt"]
        o = own.loc[(row["team"], row["pid"])]
        row["Ax_yds"] = float(sum(o.get(b, 0) * ypt_lg[b] for b in BUCKETS))  # actual bucket counts
        for arm in ("B1", "B2"):
            if rs is None:
                row[f"{arm}_yds"] = row[f"{arm}_tgt"] = np.nan
                continue
            s = rs.get((arm, row["team"], row["pid"]))
            row[f"{arm}_miss"] = s is None
            if s is None:
                s = np.zeros(3)
            gid = gid_of.get((row["team"], row["pid"]))
            cnt = np.array([tc.loc[(gid, row["team"])].get(b, 0) for b in BUCKETS], dtype=float)
            n = s * cnt
            row[f"{arm}_tgt"], row[f"{arm}_yds"] = n.sum(), float((n * y).sum())


rng = np.random.default_rng(7)
B = 2000


def terciles(df):
    d = df[df["prior_tgt"] >= MIN_PRIOR_TGT].dropna(subset=["ypt_own"]).copy()
    d["terc"] = pd.qcut(d["ypt_own"], 3, labels=["bottom", "mid", "top"])
    return d


def ci(g, col, idx):
    a, b = g[col].to_numpy(), g["act_yds"].to_numpy()
    r = a[idx].sum(1) / b[idx].sum(1)
    return np.percentile(r, [5, 95])


pbp = load_pbp((2023, 2024, 2025, 2026))
windows = [("2025 wk 1-2", 2025, (1, 2)), ("2025 wk 3-4", 2025, (3, 4)),
           ("2025 wk 5-10", 2025, tuple(range(5, 11))),
           ("2025 wk 11-18", 2025, tuple(range(11, 19))),
           ("2026 wk 1-2", 2026, (1, 2)), ("2026 wk 3", 2026, (3,)), ("2026 wk 1-3", 2026, (1, 2, 3))]
rows_all = []
for label, season, weeks in windows:
    out = []
    for wk in weeks:
        run_week(pbp, season, wk, out)
    d = terciles(pd.DataFrame(out))
    top, bot = d[d["terc"] == "top"], d[d["terc"] == "bottom"]
    it = rng.integers(0, len(top), (B, len(top)))      # same order as p30_recheck.boot
    ib = rng.integers(0, len(bot), (B, len(bot)))
    print(f"\n== {label}  n={len(d)}")
    for arm in ("B0", "B1", "B2", "A", "Ax"):
        col = "B_yds" if arm == "B0" else f"{arm}_yds"
        tcol = "B_tgt" if arm == "B0" else f"{arm}_tgt"
        if d[col].isna().any():
            print(f"  {arm}: no roles vector for this window"); continue
        ct, cb = ci(top, col, it), ci(bot, col, ib)
        rt, rb = top[col].sum() / top["act_yds"].sum(), bot[col].sum() / bot["act_yds"].sum()
        tt = top[tcol].sum() / top["act_tgt"].sum()
        allr = d[col].sum() / d["act_yds"].sum()
        miss = f"  (not in vector: {int(d[f'{arm}_miss'].sum())} rows)" if f"{arm}_miss" in d else ""
        print(f"  {arm:<2} top {rt:.3f} [{ct[0]:.3f}, {ct[1]:.3f}]  top tgt/act {tt:.3f}  "
              f"bottom {rb:.3f} [{cb[0]:.3f}, {cb[1]:.3f}]  all {allr:.3f}{miss}")
    d["window"] = label
    rows_all.append(d)
pd.concat(rows_all).to_parquet(os.path.join(HERE, "p30_diag_rows.parquet"))
