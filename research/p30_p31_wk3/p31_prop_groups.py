"""P31: where the partial trim (alpha 0.34) wins and loses, by player group, and
how many real priced props sit in each group. Read-only (user request 2026-09-29).

Groups are fixed from the trim-OFF pregame shares, per team-week:
  targets  T1 top-2 by target share | T2 rest of the top half (>= team-week Q3 cut
           of 2%+ shares) | T3 other 2%+ | T4 under 2%
  carries  C1 carry rank 1 | C2 carry rank 2 | C3 the rest
Errors: walk-forward test windows (2025 wk 11-18, 2026 wk 2-3 prod cutoffs).
Props: week 4 as currently priced (data/props.json) and the full week-3 slate
(data/snapshots/wk3-props_2026-09-28/props.json).
"""
import os, sys, json
sys.argv = sys.argv[:1]
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"C:\Users\alexr\OneDrive\Desktop\Football Predictor"
import numpy as np, pandas as pd
import p31_partial as P
from src.ingest_injuries import player_key

ALPHA = 0.3403


def tag(v):
    v = v.copy()
    full, part, off = P.shares(v, 0.0), P.shares(v, ALPHA), P.shares(v, 1.0)
    v["nf"], v["np"], v["n0"] = full["tgt"], part["tgt"], off["tgt"]
    v["cf"], v["cp"], v["c0"] = full["car"], part["car"], off["car"]
    sk = v["position"].isin(P.SKILL)
    v["trank"] = v[sk].groupby("tw")["n0"].rank(ascending=False, method="first")
    q3 = v[sk & (v["n0"] >= 0.02)].groupby(["season", "week"])["n0"].quantile(0.5)
    cut = v.set_index(["season", "week"]).index.map(q3.to_dict()).to_numpy(float)
    v["tg"] = np.select([v["trank"] <= 2, v["n0"] >= cut, v["n0"] >= 0.02], ["T1 top-2", "T2 upper half", "T3 lower half"], "T4 <2%")
    v.loc[~sk, "tg"] = "QB/other"
    v["crank"] = v.groupby("tw")["c0"].rank(ascending=False, method="first")
    v["cg"] = np.select([v["crank"] == 1, v["crank"] == 2], ["C1 carry rank 1", "C2 carry rank 2"], "C3 rest")
    return v


def errors(v, label):
    v = tag(v)
    v["rt"], v["rc"] = v["a_tgt"] / v["T_tgt"], v["a_car"] / v["T_car"]
    print(f"\n== {label}")
    rows = []
    for g, d in v[v["tg"] != "QB/other"].groupby("tg"):
        rows.append({"group": g, "rows": len(d), "real tgt share": d["rt"].sum() / d["tw"].nunique(),
                     "MAE full": (d["nf"] - d["rt"]).abs().mean(), "MAE part": (d["np"] - d["rt"]).abs().mean(),
                     "real/sim full": d["a_tgt"].sum() / (d["nf"] * d["T_tgt"]).sum(),
                     "real/sim part": d["a_tgt"].sum() / (d["np"] * d["T_tgt"]).sum()})
    c = v[(v["c0"] > 0) | (v["a_car"] > 0)]
    for g, d in c.groupby("cg"):
        rows.append({"group": g, "rows": len(d), "real tgt share": np.nan,
                     "MAE full": (d["cf"] - d["rc"]).abs().mean(), "MAE part": (d["cp"] - d["rc"]).abs().mean(),
                     "real/sim full": d["a_car"].sum() / (d["cf"] * d["T_car"]).sum(),
                     "real/sim part": d["a_car"].sum() / (d["cp"] * d["T_car"]).sum()})
    t = pd.DataFrame(rows)
    t["MAE part-full"] = t["MAE part"] - t["MAE full"]
    print(t.round(4).to_string(index=False))


def props_week(season, week, tag_, path, label):
    v = tag(P.load(season, week, tag_)) if tag_ else None
    return v


def prop_groups(v, props_file, label):
    d = json.load(open(props_file))
    rows = [r for k in ("props", "more", "held_out", "started", "structural_holdouts") for r in d.get(k, []) or []]
    pr = pd.DataFrame(rows)
    v = v.copy()
    v["key"] = [player_key(t, n) for t, n in zip(v["team"], v["player"])]
    pr["key"] = [player_key(t, n) for t, n in zip(pr["team"], pr["player"])]
    m = pr.merge(v[["team", "key", "tg", "cg", "n0", "nf", "np", "c0", "cf", "cp"]], on=["team", "key"], how="left")
    m["kind"] = m["market"].map({"player_receptions": "receiving", "player_reception_yds": "receiving",
                                 "player_rush_yds": "rushing", "player_pass_yds": "passing"})
    m["group"] = np.where(m["kind"] == "receiving", m["tg"], np.where(m["kind"] == "rushing", m["cg"], "passing (no share)"))
    m.loc[m["kind"] == "rushing", "group"] = m["cg"] + " (" + m["position"].str[:2] + ")"
    print(f"\n== {label}: {len(pr)} priced props, {m['tg'].isna().sum()} not matched to the roles vector")
    print(m.groupby(["kind", "group"]).size().rename("props").to_string())
    rec = m[m["kind"] == "receiving"]
    print("  receiving: share full -> partial, mean by group")
    print(rec.groupby("tg")[["nf", "np"]].mean().round(4).to_string())
    return m


if __name__ == "__main__":
    t25 = pd.concat([P.load(2025, w, "pre") for w in range(11, 19)], ignore_index=True)
    t26 = pd.concat([P.load(2026, 2, "prod"), P.load(2026, 3, "prod")], ignore_index=True)
    errors(t25, "walk-forward 2025 wk 11-18")
    errors(t26, "2026 wk 2-3 (prod cutoffs)")
    w3 = tag(P.load(2026, 3, "prod"))
    prop_groups(w3, os.path.join(ROOT, r"data\snapshots\wk3-props_2026-09-28\props.json"), "week 3 full slate (noon roles)")
    # week 4 has no played games yet, so load() has no team rows; tag the raw vector directly
    r = pd.read_parquet(os.path.join(HERE, "roles", "2026_w04_prod.parquet"))
    rows = []
    for t, sq in r.groupby("team"):
        sq = sq.sort_values(["position", "rank"]).reset_index(drop=True)
        base = sq[P.CATS].to_numpy(float)
        on = P.simulate_nfl._participation_trim(sq, base)
        s = sq[["team", "player_id", "player", "position", "rank"]].copy()
        s["cut"] = (base != on).any(axis=1)
        s["w_tgt"], s["w_car"] = base[:, P.TG], base[:, P.CA]
        s["a_tgt"] = s["a_car"] = 0.0
        s["T_tgt"] = s["T_car"] = 1.0
        s["sum_tgt_keep"] = base[~s["cut"].to_numpy(), P.TG].sum()
        s["sum_car_keep"] = base[~s["cut"].to_numpy(), P.CA].sum()
        rows.append(s)
    w4 = pd.concat(rows, ignore_index=True)
    w4["season"], w4["week"], w4["tw"] = 2026, 4, "2026-4-" + w4["team"]
    prop_groups(tag(w4), os.path.join(ROOT, r"data\props.json"), "week 4 as currently priced")
