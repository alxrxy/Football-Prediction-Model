"""P22 phase 2 criteria 1-3 and 6 (calibration-log 2026-09-30, set before the build).
Everything in memory: no table, sim, prop or export is written.

    python research/p22/p22_phase2_checks.py [week]
"""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src import config, db, ingest_nflverse as ING, props, simulate_nfl  # noqa: E402
from src.export_sims import pregame_view  # noqa: E402
from src.features import FeatureContext  # noqa: E402
from src.predict_baseline import predict_game  # noqa: E402

SEASON, WEEK = 2026, int(sys.argv[1]) if len(sys.argv) > 1 else 4
say = print


# --- phase-1 harness, with its ridge solved exactly (sklearn's sparse_cg is within 6e-6 EPA) ---
sys.argv = [sys.argv[0]]
spec = importlib.util.spec_from_file_location("p22h", ROOT / "research" / "p22" / "p22_phase1.py")
H = importlib.util.module_from_spec(spec)
spec.loader.exec_module(H)


class ExactRidge:
    def __init__(self, alpha, fit_intercept=True):
        self.alpha = alpha

    def fit(self, X, y):
        X = X.toarray() if hasattr(X, "toarray") else X
        xm, ym = X.mean(0), y.mean()
        Xc = X - xm
        self.coef_ = np.linalg.solve(Xc.T @ Xc + self.alpha * np.eye(X.shape[1]), Xc.T @ (y - ym))
        self.intercept_ = ym - xm @ self.coef_
        return self


H.Ridge = ExactRidge
hpbp, htotals, hppg = H.load()
sched = __import__("nfl_data_py").import_schedules([SEASON - 1, SEASON])


def feed_harness_pbp():
    """Make compute_ratings read exactly the harness's plays."""
    def imp(years, columns=None, downcast=True, cache=False):
        d = pd.concat([hpbp[y] for y in years], ignore_index=True)
        return d.assign(play_type="pass")          # the harness keeps only pass/run already
    ING._import = lambda: SimpleNamespace(import_pbp_data=imp)


def live_ratings(adjust: bool, unrounded=False, carry_only=False):
    config.RATING_OPPONENT_ADJUST = adjust
    saved = ING._adjusted_by_team
    if carry_only:                                  # new carry, raw means: attribution only
        ING._adjusted_by_team = lambda pbp, neutral, penalty=ING.RIDGE_PENALTY: ING._epa_by_team(pbp)
    if unrounded:
        ING.round = lambda x, n=None: x
    try:
        return {r["team"]: r for r in ING.compute_ratings(SEASON, WEEK, sched)}
    finally:
        ING._adjusted_by_team = saved
        if unrounded:
            del ING.round
        config.RATING_OPPONENT_ADJUST = True


feed_harness_pbp()

# --- 1(a) port fidelity -------------------------------------------------------------------
arm = {"adj": True, "filt": False, "lam": ING.RIDGE_PENALTY,
       "r_off": ING.PRIOR_REGRESSION_OFF, "r_def": ING.PRIOR_REGRESSION_DEF}
hr = H.ratings(hpbp, SEASON, WEEK, arm)
lr = live_ratings(True, unrounded=True)
d = max(max(abs(lr[t]["off_epa"] - hr[t][0]), abs(lr[t]["def_epa"] - hr[t][1])) for t in hr)
say(f"1(a) port fidelity, week {WEEK}: {len(hr)} teams, max |live - harness| = {d:.2e} EPA  "
    f"-> {'pass' if d < 1e-9 else 'FAIL'}")

# --- served numbers before / after ------------------------------------------------------------
old, new, carry = live_ratings(False), live_ratings(True), live_ratings(True, carry_only=True)
store = db.get_store()
ctx = FeatureContext(store, "nfl")
stored = {t: r for t, r in ctx.ratings.items()}
drift = max(abs(stored[t]["power_rating"] - old[t]["power_rating"]) for t in old if t in stored)
say(f"    sanity: flag-off recompute vs the stored live ratings, max |power_rating diff| = {drift:.3f}")


def use(rt):
    for t, r in rt.items():
        if t in ctx.ratings:
            ctx.ratings[t] = dict(ctx.ratings[t], power_rating=r["power_rating"], off_epa=r["off_epa"], def_epa=r["def_epa"])


games = [g for g in ctx.games if g.get("season") == SEASON and g.get("week") == WEEK]
games.sort(key=lambda g: g["kickoff_time"])
ctx.load_prices(g["game_id"] for g in games)
rows = []
for name, rt in (("old", old), ("new", new)):
    use(rt)
    for g in games:
        f = ctx.build(g)
        p = predict_game(f)
        rows.append({"arm": name, "game_id": g["game_id"], "margin": p["model_margin_home"],
                     "line": f.get("market_spread"), "home": g["home_team"], "away": g["away_team"]})
m = pd.DataFrame(rows).pivot_table(index="game_id", columns="arm", values=["margin", "line"], aggfunc="first")
m["move"] = m[("margin", "new")] - m[("margin", "old")]
edge_old = (m[("margin", "old")] + m[("line", "old")]).abs()
edge_new = (m[("margin", "new")] + m[("line", "new")]).abs()
say(f"1(b) week {WEEK}, {len(m)} games: mean |model - line| {edge_old.mean():.2f} -> {edge_new.mean():.2f}  "
    f"-> {'pass' if edge_new.mean() < edge_old.mean() else 'FAIL'}")
for gid, r in m.sort_values("move", key=abs, ascending=False).iterrows():
    h, a = gid.split("_")[3], gid.split("_")[2]
    parts = {}
    for lab, (x, y) in (("carry", (old, carry)), ("adjust", (carry, new))):
        for side, k, sgn in (("off", "off_epa", 1), ("def", "def_epa", -1)):
            parts[f"{side} {lab}"] = sgn * ((y[h][k] - x[h][k]) - (y[a][k] - x[a][k])) * ING.PLAYS_PER_GAME
    flag = "  <-- > 3 pts" if abs(r["move"].iloc[0]) > 3 else ""
    say(f"    {a}@{h}: {r[('margin', 'old')]:+6.2f} -> {r[('margin', 'new')]:+6.2f} (line {r[('line', 'new')]}), move "
        f"{r['move'].iloc[0]:+.2f} = " + ", ".join(f"{k} {v:+.2f}" for k, v in parts.items()) + flag)

# --- 2 sim totals vs the phase-1 proxy ---------------------------------------------------------
say("2  sims before / after (10,000 each, in memory)")
inputs = simulate_nfl.load_inputs(SEASON)
known = inputs.roles["participation"].notna().mean()
say(f"   inputs: participation known for {known:.0%} of roles (the P31 trim needs it)")
if known < 0.9:
    sys.exit("   snap participation missing (feed failure): the sims would run without the live P31 trim. Re-run.")
L = hppg[SEASON - 1]
sims, prox = {}, {}
for name, rt in (("old", old), ("new", new)):
    use(rt)
    ob = np.mean([r["off_epa"] for r in rt.values()])
    db_ = np.mean([r["def_epa"] for r in rt.values()])
    for g in games:
        row = simulate_nfl.simulate_one(g, ctx, inputs)
        sims[(name, g["game_id"])] = row
        h, a = rt[g["home_team"]], rt[g["away_team"]]
        prox[(name, g["game_id"])] = 2 * L + ING.PLAYS_PER_GAME * (
            (h["off_epa"] - ob) + (a["off_epa"] - ob) + (h["def_epa"] - db_) + (a["def_epa"] - db_))
agree = n = 0
ds, dp = [], []
for g in games:
    gid = g["game_id"]
    tot = lambda nm: sims[(nm, gid)]["median_home_points"] + sims[(nm, gid)]["median_away_points"]  # noqa: E731
    s_move, p_move = tot("new") - tot("old"), prox[("new", gid)] - prox[("old", gid)]
    ds.append(s_move)
    dp.append(p_move)
    if abs(p_move) >= 1:
        n += 1
        agree += np.sign(s_move) == np.sign(p_move)
    say(f"    {g['away_team']}@{g['home_team']}: sim median total {tot('old'):.0f} -> {tot('new'):.0f} ({s_move:+.0f}); "
        f"proxy {prox[('old', gid)]:.1f} -> {prox[('new', gid)]:.1f} ({p_move:+.1f})")
say(f"   games with |proxy move| >= 1: {n}, sim moved the same way in {agree} "
    f"({agree / n * 100 if n else float('nan'):.0f}%); slate mean: sim {np.mean(ds):+.2f}, proxy {np.mean(dp):+.2f}  "
    f"-> {'pass' if (n == 0 or agree / n >= 0.75) and np.sign(np.mean(ds)) == np.sign(np.mean(dp)) else 'FAIL'}")

# --- 3 props bias: raw P(over) by category, before vs after ----------------------------------
lines = json.loads((config.DATA_DIR / "props_lines.json").read_text(encoding="utf-8"))
kick = {g["game_id"]: g["kickoff_time"] for g in games}


def price(name):
    view = {}
    for g in games:
        row = copy.deepcopy(sims[(name, g["game_id"])])
        v = pregame_view(row, kick[g["game_id"]])
        v["box_score"] = row["box_score"]
        view[g["game_id"]] = v
    out = props.rank(lines, view, now=pd.Timestamp("2026-09-30T00:00:00Z").to_pydatetime())
    recs = [r for k in ("props", "more", "held_out", "started") for r in out.get(k, [])]
    df = pd.DataFrame(recs)
    df["p_over"] = np.where(df["pick"] == "over", df["p_model_raw"], 1 - df["p_model_raw"])
    pos = df["position"].str[:2]
    df["cat"] = np.select(
        [df["market"] == "player_receptions", df["market"] == "player_reception_yds",
         (df["market"] == "player_rush_yds") & (pos == "QB"), df["market"] == "player_rush_yds",
         df["market"] == "player_pass_yds"],
        ["receptions", "rec yds", "rush yds QB", "rush yds RB/other", "pass yds"], "other")
    return df.set_index(["game_id", "player", "market"])


a, b = price("old"), price("new")
j = a[["cat", "p_over"]].join(b[["p_over"]], rsuffix="_new", how="inner")
g3 = j.groupby("cat").agg(n=("p_over", "size"), before=("p_over", "mean"), after=("p_over_new", "mean"))
g3["shift_pp"] = (g3["after"] - g3["before"]) * 100
say("3  props raw P(over) by category, week " + str(WEEK) + " lines:")
say(g3.round(4).to_string())
worst = g3["shift_pp"].abs().max()
say(f"   largest category shift {worst:.2f} pp -> {'no refit needed' if worst <= 1.0 else 'REFIT FLAGGED (> 1.0 pp)'}")

# --- 6 ML predictions, before vs after -----------------------------------------------------------
from src import build_training, predict_ml  # noqa: E402

model, meta = predict_ml.load_model("nfl")
elo, epa = build_training.replay_state("nfl")
outs = []
for name, rt in (("old", old), ("new", new)):
    use(rt)
    fr = pd.DataFrame(predict_ml.build_live_features("nfl", games, ctx, elo, epa))[meta["features"]]
    outs.append(model.predict(fr))
say(f"6  ML predictions with the old vs new rating: max |diff| = {np.abs(outs[0] - outs[1]).max():.2e}  "
    f"-> {'pass' if np.abs(outs[0] - outs[1]).max() == 0 else 'FAIL'}")
store.close()
