"""P30, decisive test. Read-only; no production code touched.

Two models of a receiver's yards in a team-game, both given the team's ACTUAL
play mix for that game, both using only pre-week history:

  A  "walk-forward":  his ACTUAL targets, split by his own pre-week category MIX
  B  "the engine":    team's ACTUAL bucket counts x his pre-week category SHARE

A is what the 2026-09-19 P17 walk-forward scored (0.97 / 1.01 per tercile).
B is what the simulator actually does. If B shows the 0.80 / 1.24 compression
and A does not, the cause is the share -> target-count step, i.e. the
simulated target distribution, which is what P30 asks.

Yards per target within a bucket are league-average in both, pre-week.
"""
import sys
sys.path.insert(0, r"C:\Users\alexr\OneDrive\Desktop\Football Predictor")

import numpy as np, pandas as pd
from src.sim_data import load_pbp, usage_rates, DEEP_AIR_YARDS, RZ_YL

BUCKETS = ("rz", "deep", "short")
MIN_PRIOR_TGT = 20


def prep(pbp):
    t = pbp[(pbp["pass_attempt"] == 1) & (pbp["sack"] != 1) & pbp["receiver_player_id"].notna()].copy()
    deep = t["air_yards"].fillna(0) >= DEEP_AIR_YARDS
    rz = t["yardline_100"] <= RZ_YL
    t["bucket"] = np.where(rz, "rz", np.where(deep, "deep", "short"))
    t["yds"] = t["yards_gained"].fillna(0) * t["complete_pass"].fillna(0)
    return t


def shares(prior_pbp, season):
    """Pre-week per-bucket share, on the engine's own definitions."""
    u = usage_rates(prior_pbp, season)
    return u[["tgt_all", "tgt_rz", "tgt_deep", "tgt_short"]]


def own_ypt(prior_t):
    y = prior_t.groupby("receiver_player_id")["yds"].sum()
    n = prior_t.groupby("receiver_player_id").size()
    return (y / n).where(n >= MIN_PRIOR_TGT), n


def run_week(all_pbp, season, week, out):
    prior = all_pbp[(all_pbp["season"] < season) |
                    ((all_pbp["season"] == season) & (all_pbp["week"] < week))]
    cur = all_pbp[(all_pbp["season"] == season) & (all_pbp["week"] == week)]
    if not len(prior) or not len(cur):
        return
    pt, ct = prep(prior), prep(cur)
    ypt_lg = pt.groupby("bucket")["yds"].mean()          # pre-week league yards per target
    sh = shares(prior, season)
    ypt_own, prior_n = own_ypt(pt)

    team_cnt = ct.groupby(["game_id", "posteam", "bucket"]).size().unstack(fill_value=0)
    for b in BUCKETS:
        if b not in team_cnt:
            team_cnt[b] = 0

    act = ct.groupby(["game_id", "posteam", "receiver_player_id", "bucket"]).agg(
        n=("yds", "size"), y=("yds", "sum")).unstack(fill_value=0)
    for (gid, team), grp in act.groupby(level=[0, 1]):
        tc = team_cnt.loc[(gid, team)]
        for pid in grp.index.get_level_values(2):
            row = grp.loc[(gid, team, pid)]
            a_n = {b: float(row.get(("n", b), 0)) for b in BUCKETS}
            a_y = float(sum(row.get(("y", b), 0) for b in BUCKETS))
            tot = sum(a_n.values())
            if pid not in sh.index or tot == 0:
                continue
            s = sh.loc[pid]
            # A: actual targets, own pre-week category mix
            mix = np.array([s["tgt_rz"], s["tgt_deep"], s["tgt_short"]], dtype=float)
            # the engine's mix is a share of different denominators; turn it into
            # a per-player mix the same way the walk-forward did: weight by the
            # league bucket frequency the player's own team produced
            w = mix * np.array([tc[b] for b in BUCKETS], dtype=float)
            if w.sum() <= 0:
                continue
            mixA = w / w.sum()
            yA = tot * float((mixA * np.array([ypt_lg[b] for b in BUCKETS])).sum())
            # B: team bucket counts x share
            nB = np.array([s[f"tgt_{b}"] * tc[b] for b in BUCKETS], dtype=float)
            yB = float((nB * np.array([ypt_lg[b] for b in BUCKETS])).sum())
            out.append({"season": season, "week": week, "pid": pid, "team": team,
                        "act_tgt": tot, "act_yds": a_y, "A_yds": yA,
                        "B_tgt": nB.sum(), "B_yds": yB,
                        "ypt_own": ypt_own.get(pid, np.nan),
                        "prior_tgt": float(prior_n.get(pid, 0))})


def report(df, label):
    d = df[df["prior_tgt"] >= MIN_PRIOR_TGT].dropna(subset=["ypt_own"])
    if not len(d):
        print(f"\n{label}: no qualifying players"); return
    d = d.copy()
    d["terc"] = pd.qcut(d["ypt_own"], 3, labels=["bottom", "mid", "top"])
    print(f"\n=== {label}  (n={len(d)} player-games, {MIN_PRIOR_TGT}+ prior targets) ===")
    print(f"  overall   A yds/actual {d['A_yds'].sum()/d['act_yds'].sum():.3f}   "
          f"B yds/actual {d['B_yds'].sum()/d['act_yds'].sum():.3f}   "
          f"B tgt/actual {d['B_tgt'].sum()/d['act_tgt'].sum():.3f}")
    rows = []
    for t, g in d.groupby("terc", observed=True):
        rows.append({"tercile": t, "n": len(g),
                     "A yds": g["A_yds"].sum() / g["act_yds"].sum(),
                     "B yds": g["B_yds"].sum() / g["act_yds"].sum(),
                     "B tgt": g["B_tgt"].sum() / g["act_tgt"].sum(),
                     "act ypt": g["act_yds"].sum() / g["act_tgt"].sum()})
    print(pd.DataFrame(rows).round(3).to_string(index=False))


if __name__ == "__main__":
 pbp = load_pbp((2024, 2025, 2026))
 out = []
 for wk in (1, 2):
     run_week(pbp, 2026, wk, out)
 report(pd.DataFrame(out), "2026 weeks 1-2")

 out25 = []
 for wk in range(11, 19):
     run_week(pbp, 2025, wk, out25)
 report(pd.DataFrame(out25), "2025 weeks 11-18")
