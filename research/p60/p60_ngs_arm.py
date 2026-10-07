"""P60: does an NGS-informed prior improve P17's frozen receiver-efficiency design? Research only; nothing live.

    python research/p60/p60_ngs_arm.py

Bars: calibration-log.md, P60 row (2026-09-30). Arm B as specified in the 2026-10-07 'P60 arm B specified' entry,
written before this ran. Arm A = the harness's own functions from research/p17/p17_walkforward.py, executed from
source; arm B's predict is the same source with the one prior line swapped (asserted to occur once).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
import nfl_data_py as nfl  # noqa: E402
from src import sim_data as sd  # noqa: E402

K, W_PRIOR = 100, 0.5
CS = (0.01, 0.1, 1.0)
FIT_YEARS = 7
FEATS = ["sep", "cush", "iay", "ttt"]
POS = ["WR", "TE", "RB"]
OUT_LINES: list[str] = []


def say(s=""):
    print(s, flush=True)
    OUT_LINES.append(str(s))


# --- harness source -----------------------------------------------------------------------------------
SRC = (ROOT / "research" / "p17" / "p17_walkforward.py").read_text(encoding="utf-8")
BODY = SRC[SRC.index("EDGES = ["):SRC.index("VARIANTS = [")]
FUNCS_AT = BODY.index("def rates(")
PRE, FUNCS = BODY[:FUNCS_AT], BODY[FUNCS_AT:]
A_LINE = 'pri = (pp.loc[(x["pos"], cat)].to_numpy(float) if prior == "pos" and (x["pos"], cat) in pp.index else mix)'
assert FUNCS.count(A_LINE) == 1
B_FUNCS = FUNCS.replace(A_LINE, 'pri = PRIOR_B(pid, x["pos"], cat, pp, mix, prior)').replace("def predict(", "def predict_b(")
B_FUNCS = B_FUNCS[B_FUNCS.index("def predict_b("):]
assert 'hist["season"] == 2024' in FUNCS


# --- data ---------------------------------------------------------------------------------------------
YEARS = list(range(2018, 2027))
pbp = sd.load_pbp(tuple(YEARS))
pbp = pbp[pbp["season_type"] == "REG"] if "season_type" in pbp else pbp
T_ALL = pbp[(pbp["pass_attempt"] == 1) & (pbp["sack"] != 1) & pbp["receiver_player_id"].notna()
            & (pbp["play_type"] == "pass")].copy()
T_ALL["cat"] = np.where(T_ALL["yardline_100"] <= sd.RZ_YL, 0,
                        np.where(T_ALL["air_yards"].fillna(0) >= sd.DEEP_AIR_YARDS, 1, 2))
T_ALL["cmp"] = (T_ALL["complete_pass"] == 1).astype(int)
T_ALL["yds"] = np.where(T_ALL["cmp"] == 1, T_ALL["yards_gained"].fillna(0), 0.0)
EDGES = [-99, 4.5, 9.5, 19.5, 999]
T_ALL["bin"] = np.where(T_ALL["cmp"] == 0, 0, np.digitize(T_ALL["yds"], EDGES[1:-1]) + 1)
T_ALL["pid"] = T_ALL["receiver_player_id"]
ros_all = nfl.import_seasonal_rosters(YEARS)[["player_id", "position", "season"]]
pos_all = ros_all.sort_values("season").drop_duplicates("player_id", keep="last").set_index("player_id")["position"]
T_ALL["pos_fit"] = T_ALL["pid"].map(pos_all).where(lambda s: s.isin(POS), "WR")
say(f"pbp {YEARS[0]}-{YEARS[-1]}: {len(T_ALL):,} targeted passes")

# NGS weekly rows (regular season, week >= 1) with the team's main passer's time to throw
rec = nfl.import_ngs_data("receiving", list(range(2017, 2027)))
pas = nfl.import_ngs_data("passing", list(range(2017, 2027)))
rec = rec[(rec.season_type == "REG") & (rec.week >= 1)]
pas = pas[(pas.season_type == "REG") & (pas.week >= 1)].sort_values("attempts", ascending=False)
ttt = pas.drop_duplicates(["season", "week", "team_abbr"]).set_index(["season", "week", "team_abbr"])["avg_time_to_throw"]
N = rec.assign(ttt=[ttt.get((s, w, tm), np.nan) for s, w, tm in zip(rec.season, rec.week, rec.team_abbr)])
N = N.rename(columns={"player_gsis_id": "pid", "avg_separation": "sep", "avg_cushion": "cush",
                      "avg_intended_air_yards": "iay", "targets": "tg"})
N = N.dropna(subset=["pid", "tg"] + FEATS)
N = N[N.tg > 0]
N["key"] = N.season * 100 + N.week
N = N.sort_values(["pid", "key"])
CUM = {}
for pid, g in N.groupby("pid"):
    w = g.tg.to_numpy(float)
    CUM[pid] = (g.key.to_numpy(), np.cumsum(w), np.cumsum(g[FEATS].to_numpy(float) * w[:, None], axis=0))
say(f"NGS receiving weekly rows used: {len(N):,} ({N.pid.nunique():,} receivers)")


def profile(pid, s, w):
    """Target-weighted NGS means from season s-1 and season s weeks < w; None when there are no rows."""
    c = CUM.get(pid)
    if c is None:
        return None
    keys, cw, cf = c
    lo, hi = np.searchsorted(keys, (s - 1) * 100 + 1), np.searchsorted(keys, s * 100 + w)   # [lo, hi)
    if hi <= lo:
        return None
    wsum = cw[hi - 1] - (cw[lo - 1] if lo else 0.0)
    fsum = cf[hi - 1] - (cf[lo - 1] if lo else 0.0)
    return fsum / wsum


# --- mapping ------------------------------------------------------------------------------------------
_PROF_CACHE: dict = {}


def fit_rows(season):
    """Targets from the FIT_YEARS seasons before `season`, with each target's as-of profile."""
    if season in _PROF_CACHE:
        return _PROF_CACHE[season]
    d = T_ALL[(T_ALL.season >= season - FIT_YEARS) & (T_ALL.season < season)]
    keys = d[["pid", "season", "week"]].drop_duplicates()
    prof = {(p, s, w): profile(p, s, w) for p, s, w in keys.itertuples(index=False)}
    X = np.array([prof[(p, s, w)] if prof[(p, s, w)] is not None else [np.nan] * 4
                  for p, s, w in zip(d.pid, d.season, d.week)])
    ok = ~np.isnan(X).any(1)
    out = (d[ok], X[ok])
    _PROF_CACHE[season] = out
    return out


def design(pos, Z):
    return np.column_stack([np.array([[p == q for q in POS[1:]] for p in pos], float), Z])


class Mapping:
    def __init__(self, season, C):
        d, X = fit_rows(season)
        self.mu, self.sd = X.mean(0), X.std(0)
        Z = (X - self.mu) / self.sd
        self.models, self.posmean = {}, {}
        for p in POS:
            m = (d.pos_fit == p).to_numpy()
            self.posmean[p] = np.average(Z[m], axis=0, weights=None) if m.any() else np.zeros(4)
        for cat in range(3):
            m = (d.cat == cat).to_numpy()
            lr = LogisticRegression(C=C, max_iter=2000)
            lr.fit(design(d.pos_fit[m].to_numpy(), Z[m]), d.bin[m].to_numpy())
            self.models[cat] = lr
        self.n = len(d)

    def ratio(self, pos, prof, cat):
        lr = self.models[cat]
        z = (np.asarray(prof) - self.mu) / self.sd
        pa = lr.predict_proba(design([pos], z[None, :]))[0]
        pb = lr.predict_proba(design([pos], self.posmean.get(pos, np.zeros(4))[None, :]))[0]
        r = np.ones(5)
        r[lr.classes_] = pa / pb
        return r


# --- one season's walk-forward ------------------------------------------------------------------------
def season_run(prior_season, cur, weeks, Cs):
    g = {"np": np, "pd": pd, "nfl": nfl, "sd": sd}
    t = T_ALL[T_ALL.season.isin([prior_season, cur])].drop(columns=["pos_fit"]).copy()
    g["t"] = t
    exec(PRE.replace("[2024, 2025]", f"[{prior_season}, {cur}]"), g)
    exec(FUNCS.replace('hist["season"] == 2024', f'hist["season"] == {prior_season}'), g)
    exec(B_FUNCS, g)
    t = g["t"]
    rows = []
    maps = {C: Mapping(cur, C) for C in Cs}
    say(f"  mapping for {cur}: fitted on {maps[Cs[0]].n:,} profiled targets ({cur - FIT_YEARS}-{cur - 1})")
    for w in weeks:
        hist = t[(t["season"] == prior_season) | ((t["season"] == cur) & (t["week"] < w))]
        wk = t[(t["season"] == cur) & (t["week"] == w)]
        actual = wk.groupby(["game_id", "posteam", "pid"]).agg(yds=("yds", "sum"), rec=("cmp", "sum"), tgt=("pid", "size")).reset_index()
        team_tot = actual.groupby(["game_id", "posteam"])[["yds", "rec"]].sum()
        catmix = hist.groupby(["pid", "cat"]).size().unstack(fill_value=0).reindex(columns=range(3), fill_value=0)
        posmix = hist.groupby(["pos", "cat"]).size().unstack(fill_value=0).reindex(columns=range(3), fill_value=0)
        posmix = posmix.div(posmix.sum(1), axis=0)
        profs = {pid: profile(pid, cur, w) for pid in wk.pid.unique()}
        r = g["rates"](hist, W_PRIOR)
        arms = [("engine", g["predict"], None, None, 1.0), ("A", g["predict"], K, "pos", W_PRIOR)]
        arms += [(f"B C={C}", g["predict_b"], K, "pos", W_PRIOR) for C in Cs]
        for name, fn, k, prior, w24 in arms:
            if name.startswith("B"):
                mp = maps[float(name.split("=")[1])]

                def PRIOR_B(pid, pos, cat, pp, mix, prior, mp=mp):
                    base = pp.loc[(pos, cat)].to_numpy(float) if prior == "pos" and (pos, cat) in pp.index else mix
                    pr = profs.get(pid)
                    if pr is None:
                        return base
                    x = base * mp.ratio(pos, pr, cat)
                    return x / x.sum()
                g["PRIOR_B"] = PRIOR_B
            rr = g["rates"](hist, w24) if w24 != W_PRIOR else r
            pr = fn(wk, *rr, k, prior, catmix, posmix)
            pr = pr.groupby(["game_id", "team", "pid"])[["yds_raw", "rec_raw"]].sum().reset_index()
            m = actual.merge(pr, left_on=["game_id", "posteam", "pid"], right_on=["game_id", "team", "pid"])
            for col, raw in (("yds", "yds_raw"), ("rec", "rec_raw")):
                s = m.groupby(["game_id", "posteam"])[raw].transform("sum")
                tt = m.set_index(["game_id", "posteam"]).index.map(team_tot[col])
                m[col + "_pred"] = np.where(s > 0, m[raw] / s * np.asarray(tt, float), 0.0)
            m["arm"], m["week"], m["season"] = name, w, cur
            m["profiled"] = m.pid.map(lambda p: profs.get(p) is not None)
            rows.append(m[["arm", "season", "week", "game_id", "posteam", "pid", "tgt", "yds", "rec", "yds_pred", "rec_pred", "profiled"]])
        say(f"  {cur} week {w}: {len(actual)} receiver-games, {sum(v is not None for v in profs.values())} profiled")
    return pd.concat(rows, ignore_index=True)


def mse(x, c):
    return float(((x[c + "_pred"] - x[c]) ** 2).mean())


def compare(df, a, b, weeks, label, filt=None):
    x0, x1 = df[df.arm == a], df[df.arm == b]
    if filt is not None:
        x0, x1 = x0[filt(x0)], x1[filt(x1)]
    gy = mse(x1, "yds") / mse(x0, "yds") - 1
    gr = mse(x1, "rec") / mse(x0, "rec") - 1
    per = {w: mse(x1[x1.week == w], "yds") / mse(x0[x0.week == w], "yds") - 1 for w in weeks}
    j = x0.set_index(["week", "game_id", "posteam", "pid"]).join(
        x1.set_index(["week", "game_id", "posteam", "pid"])[["yds_pred"]], rsuffix="_b").reset_index()
    j["e0"], j["e1"] = (j.yds_pred - j.yds) ** 2, (j.yds_pred_b - j.yds) ** 2
    tg = j.groupby(["week", "game_id", "posteam"])[["e0", "e1"]].sum()
    rng = np.random.default_rng(0)
    bs = np.array([(lambda s: s.e1.sum() / s.e0.sum() - 1)(tg.iloc[rng.integers(0, len(tg), len(tg))]) for _ in range(1000)])
    say(f"  {label}: n {len(x1)}, yds {gy * 100:+.2f}% (better in {sum(d < 0 for d in per.values())}/{len(per)} weeks; "
        f"90% CI {np.percentile(bs, 5) * 100:+.2f} to {np.percentile(bs, 95) * 100:+.2f}%, "
        f"95% CI {np.percentile(bs, 2.5) * 100:+.2f} to {np.percentile(bs, 97.5) * 100:+.2f}%), rec {gr * 100:+.2f}%")
    say("      per week: " + ", ".join(f"{w}:{d * 100:+.2f}%" for w, d in per.items()))
    return gy, sum(d < 0 for d in per.values()), gr


# --- 2025 weeks 3-18 ------------------------------------------------------------------------------------
say("\n# 2025 walk-forward (weeks 3-18)")
d25 = season_run(2024, 2025, range(3, 19), CS)
e_te, a_te = d25[(d25.arm == "engine") & (d25.week >= 11)], d25[(d25.arm == "A") & (d25.week >= 11)]
say(f"\nArm A reproduces 9/19 (weeks 11-18): engine {mse(e_te, 'yds'):.1f} (9/19: 260.5), A {mse(a_te, 'yds'):.1f} (9/19: 257.2)")
tr = d25[d25.week <= 10]
sel = sorted((mse(tr[tr.arm == f"B C={C}"], "yds") / mse(tr[tr.arm == "A"], "yds") - 1, C) for C in CS)
say("Selection on weeks 3-10 (B vs A, yds MSE): " + ", ".join(f"C={C}: {d * 100:+.3f}%" for d, C in sorted(sel, key=lambda x: x[1])))
C = sel[0][1]
B = f"B C={C}"
say(f"chosen: {B}")
te = d25[d25.week >= 11]
say("\n## Judged on 2025 weeks 11-18 (B vs A)")
g1, wk1, r1 = compare(te, "A", B, range(11, 19), "bar 1, all receivers")
g2, wk2, _ = compare(te, "A", B, range(11, 19), "bar 2, profiled receivers", lambda x: x.profiled)
compare(te, "engine", "A", range(11, 19), "(context) A vs engine")
# bar 4
a, b = te[te.arm == "A"].set_index(["week", "game_id", "posteam", "pid"]), te[te.arm == B].set_index(["week", "game_id", "posteam", "pid"])
j = a.join(b[["yds_pred", "rec_pred"]], rsuffix="_b")
j["d"] = (j.yds_pred - j.yds_pred_b).abs() + (j.rec_pred - j.rec_pred_b).abs()
tgp = j.groupby(level=[0, 1, 2]).profiled.any()
none_cells = tgp[~tgp].index
unp = j[~j.profiled]
say(f"\n  bar 4: unprofiled receivers {len(unp)}; prior identical by construction; predictions identical "
    f"{(unp.d == 0).sum()}/{len(unp)} (others move via IPF with a profiled teammate); team-games with no profiled "
    f"receiver: {len(none_cells)}, max diff there {j.loc[j.index.droplevel(3).isin(none_cells), 'd'].max() if len(none_cells) else float('nan')}")
ok1 = g1 <= -0.01 and wk1 >= 6
ok2 = g2 <= -0.01 and wk2 >= 6
ok3 = r1 <= 0
say(f"\nBARS: (1) {'PASS' if ok1 else 'FAIL'}  (2) {'PASS' if ok2 else 'FAIL'}  (3) {'PASS' if ok3 else 'FAIL'}  "
    f"(5) stop rule: gain {-g1 * 100:+.2f}% {'>= 1%' if g1 <= -0.01 else '< 1%: STOP'}")
say(f"VERDICT: {'PASS: reopens the design discussion (nothing built)' if ok1 and ok2 and ok3 else 'FAILS: P60 closed by its pre-set bars'}")

# --- 2026 weeks 1-4 (reported, not gated) -------------------------------------------------------------
say("\n# 2026 weeks 1-4 (reported, not gated; mapping refitted on 2019-2025, same C)")
d26 = season_run(2025, 2026, range(1, 5), (C,))
compare(d26, "A", B, range(1, 5), "B vs A, all")
compare(d26, "A", B, range(1, 5), "B vs A, profiled", lambda x: x.profiled)
pd.concat([d25, d26]).to_pickle(HERE / "p60_results.pkl")
(HERE / "p60_results.txt").write_text("\n".join(OUT_LINES) + "\n", encoding="utf-8")
