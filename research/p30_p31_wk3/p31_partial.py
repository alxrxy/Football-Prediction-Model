"""P31 partial trim walk-forward (criteria: calibration-log 2026-09-29, written
before running). Read-only.

A trimmed player (production `_participation_trim` rule, tau 0.10) keeps
alpha x his raw share in every category instead of 0. alpha is fitted on
2025 weeks 3-10 so the trimmed players' normalised expected targets equal
the real targets they took, then frozen and scored on 2025 weeks 11-18 and
2026 weeks 2-3 pooled (the 9/29 part-A production cutoffs).
Roles vectors come from roles_asof.py.
"""
import os, sys
os.environ["USAGE_PARTICIPATION_TRIM"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, r"C:\Users\alexr\OneDrive\Desktop\Football Predictor")
import numpy as np, pandas as pd, nfl_data_py as nfl
from src import sim_data, simulate_nfl
from src.sim_data import USAGE_CATEGORIES

SKILL = ["WR", "TE", "RB", "FB"]
CATS = list(USAGE_CATEGORIES)
TG, CA = CATS.index("tgt_all"), CATS.index("car_all")

sch = nfl.import_schedules([2025, 2026])
sch["ko"] = pd.to_datetime(sch["gameday"] + " " + sch["gametime"]).dt.tz_localize("America/New_York").dt.tz_convert("UTC")
pbp = sim_data.load_pbp((2025, 2026))
ev = sim_data._usage_events(pbp)                 # the engine's own target / designed-carry events


def load(season, week, tag):
    """One week's pool: raw shares, trim mask, real targets and carries."""
    r = pd.read_parquet(os.path.join(HERE, "roles", f"{season}_w{week:02d}_{tag}.parquet"))
    cutoff = pd.Timestamp(r["cutoff"].iloc[0])
    g = sch[(sch["season"] == season) & (sch["week"] == week) & (sch["game_type"] == "REG") & (sch["ko"] >= cutoff)]
    e = ev[ev["game_id"].isin(set(g["game_id"]))]
    act = e.groupby(["team", "pid"])[["tgt_all", "car_all"]].sum()
    team = e.groupby("team")[["tgt_all", "car_all"]].sum()
    rows = []
    for t, sq in r[r["team"].isin(team.index)].groupby("team"):
        sq = sq.sort_values(["position", "rank"]).reset_index(drop=True)
        base = sq[CATS].to_numpy(float)
        on = simulate_nfl._participation_trim(sq, base)
        s = sq[["team", "player_id", "player", "position", "rank"]].copy()
        s["cut"] = (base != on).any(axis=1)
        s["w_tgt"], s["w_car"] = base[:, TG], base[:, CA]
        a = act.reindex(list(zip(s["team"], s["player_id"]))).fillna(0).to_numpy()
        s["a_tgt"], s["a_car"] = a[:, 0], a[:, 1]
        s["T_tgt"], s["T_car"] = team.loc[t, "tgt_all"], team.loc[t, "car_all"]
        # full-squad column sums (team_shares normalises over every position)
        s["sum_tgt_keep"] = base[~s["cut"].to_numpy(), TG].sum()
        s["sum_car_keep"] = base[~s["cut"].to_numpy(), CA].sum()
        rows.append(s)
    v = pd.concat(rows, ignore_index=True)
    v["season"], v["week"], v["tw"] = season, week, f"{season}-{week}-" + v["team"]
    return v


def shares(v, alpha):
    """Normalised target / carry shares at a given alpha (1 = no trim, 0 = full trim)."""
    out = {}
    for k in ("tgt", "car"):
        w = np.where(v["cut"], alpha * v[f"w_{k}"], v[f"w_{k}"])
        cut_mass = pd.Series(np.where(v["cut"], w, 0.0)).groupby(v["tw"].to_numpy()).transform("sum").to_numpy()
        out[k] = w / (v[f"sum_{k}_keep"].to_numpy() + cut_mass)
    return out


def fit_alpha(v):
    target = v.loc[v["cut"], "a_tgt"].sum()
    lo, hi = 0.0, 1.0
    f = lambda a: (shares(v, a)["tgt"] * v["T_tgt"])[v["cut"]].sum() - target
    if f(lo) > 0 or f(hi) < 0:
        return np.nan
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if f(mid) < 0 else (lo, mid)
    return (lo + hi) / 2


def metrics(v, alpha, rng_seed=1, B=3000):
    s = shares(v, alpha)
    v = v.copy()
    v["n"], v["nc"] = s["tgt"], s["car"]
    n_off = shares(v, 1.0)["tgt"]
    v["n_off"] = n_off
    v["e"] = v["n"] * v["T_tgt"]
    sk = v[v["position"].isin(SKILL)].copy()
    tot = v.groupby("tw")["T_tgt"].first().sum()
    m = {"alpha": alpha}
    m["raw_sum"] = sk.assign(w=np.where(sk["cut"], alpha * sk["w_tgt"], sk["w_tgt"])).groupby("tw")["w"].sum().mean()
    m["kept_mass"] = sk.loc[sk["cut"], "e"].sum() / tot
    m["real_mass"] = sk.loc[sk["cut"], "a_tgt"].sum() / tot
    m["mae"] = (sk["n"] - sk["a_tgt"] / sk["T_tgt"]).abs().mean()
    # pregame quartiles (trim-off share, 2%+), cut within each week, real/sim
    sk["pq"] = sk.groupby(["season", "week"])["n_off"].transform(
        lambda x: pd.qcut(x.where(x >= 0.02), 4, labels=False))
    for q in range(4):
        g = sk[sk["pq"] == q]
        m[f"pQ{q+1}"] = g["a_tgt"].sum() / g["e"].sum()
    # top-2 per team by pregame share, team-clustered bootstrap
    sk["top2"] = sk.groupby("tw")["n_off"].rank(ascending=False, method="first") <= 2
    t = sk[sk["top2"]]
    m["top2"] = t["a_tgt"].sum() / t["e"].sum()
    ga = t.groupby("tw")["a_tgt"].sum(); ge = t.groupby("tw")["e"].sum()
    rng = np.random.default_rng(rng_seed)
    idx = rng.integers(0, len(ga), (B, len(ga)))
    bs = ga.to_numpy()[idx].sum(1) / ge.to_numpy()[idx].sum(1)
    m["top2_lo"], m["top2_hi"] = np.percentile(bs, [2.5, 97.5])
    # 9/20 table: sim/real by quartile of REALISED share (real share > 0), cut within each week
    rr = sk[sk["a_tgt"] > 0].copy()
    rr["real"] = rr["a_tgt"] / rr["T_tgt"]
    rr["rq"] = rr.groupby(["season", "week"])["real"].transform(lambda x: pd.qcut(x, 4, labels=False))
    for q in range(4):
        g = rr[rr["rq"] == q]
        m[f"rQ{q+1}"] = g["n"].sum() / g["real"].sum()
    # carries: all squad rows with a designed-carry share or a real carry
    c = v[(v["w_car"] > 0) | (v["a_car"] > 0)]
    m["car_mae"] = (c["nc"] - c["a_car"] / c["T_car"]).abs().mean()
    rb1 = v[(v["position"] == "RB") & (v["rank"] == 1)]
    m["rb1_car"] = rb1["a_car"].sum() / (rb1["nc"] * rb1["T_car"]).sum()
    # team totals: normalised shares sum to 1 per team (structural)
    m["sum_dev"] = float(np.abs(pd.Series(v["n"]).groupby(v["tw"]).sum() - 1).max())
    return m


if __name__ == "__main__":
    train = pd.concat([load(2025, w, "pre") for w in range(3, 11)], ignore_index=True)
    test25 = pd.concat([load(2025, w, "pre") for w in range(11, 19)], ignore_index=True)
    test26 = pd.concat([load(2026, 2, "prod"), load(2026, 3, "prod")], ignore_index=True)
    alpha = fit_alpha(train)
    print(f"fitted alpha (2025 wk 3-10): {alpha:.4f}")
    cols = ["alpha", "raw_sum", "kept_mass", "real_mass", "mae", "pQ1", "pQ2", "pQ3", "pQ4",
            "top2", "top2_lo", "top2_hi", "rQ1", "rQ2", "rQ3", "rQ4", "car_mae", "rb1_car", "sum_dev"]
    for label, v in (("TRAIN 2025 wk 3-10", train), ("TEST 2025 wk 11-18", test25), ("TEST 2026 wk 2-3 (prod cutoffs)", test26)):
        print(f"\n== {label}: {v['tw'].nunique()} team-games, {int(v.groupby('tw')['T_tgt'].first().sum())} targets")
        grid = [1.0, 0.75, 0.5, 0.25, 0.0] + ([alpha] if np.isfinite(alpha) else [])
        print(pd.DataFrame([metrics(v, a) for a in grid])[cols].round(4).to_string(index=False))
    for wk in (2, 3):
        v = load(2026, wk, "prod")
        print(f"\n-- 2026 wk {wk} alone (check vs 9/29 part A)")
        print(pd.DataFrame([metrics(v, a) for a in (1.0, 0.0)])[["alpha", "raw_sum", "mae", "pQ1", "pQ4", "top2", "real_mass"]].round(4).to_string(index=False))
