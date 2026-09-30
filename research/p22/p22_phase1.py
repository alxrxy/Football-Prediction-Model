"""P22 phase 1: opponent-adjusted NFL rating, walk-forward. Research only; nothing live.

    python research/p22/p22_phase1.py [out.md]

Design, arms and bars were fixed in calibration-log.md (2026-09-30, "P22 phase 1
scoped") before this ran. R0 is P37's replay of the live Layer 1
(calibration/p37_edge_diagnosis.py), rebuilt here from the local pbp cache and
checked against P37's published numbers before anything else is read.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.linear_model import Ridge

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src import features as F  # noqa: E402
from src.ingest_nflverse import PLAYS_PER_GAME, PRIOR_PLAYS_WEIGHT, PRIOR_SEASON_REGRESSION  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else None
CANON = {"OAK": "LV", "SD": "LAC", "STL": "LA"}          # as P37
THRESHOLDS = (0.0, 2.0, 3.0, 4.0, 6.0)                  # as P37
RNG = np.random.default_rng(37)
N_PERM = 10_000
LAMBDAS = (10, 30, 100, 300, 1000, 3000)
TRAIN, TEST = range(2016, 2022), range(2022, 2026)
GARBAGE_WP = (0.10, 0.90)
lines: list[str] = []


def say(text=""):
    print(text)
    lines.append(text)


# --- data -------------------------------------------------------------------

def load():
    import nfl_data_py as nfl

    sch = nfl.import_schedules(list(range(2015, 2027)))
    neutral = set(sch.loc[sch["location"] == "Neutral", "game_id"])
    pbp = {}
    for y in range(2015, 2027):
        path = ROOT / "data" / "cache" / f"sim_pbp_{y}.parquet"
        if path.exists():
            d = pd.read_parquet(path)
        else:
            from src.sim_data import load_pbp
            d = load_pbp((y,))
        d = d[d["play_type"].isin(["pass", "run"]) & d["posteam"].notna()].copy()
        d = d[["game_id", "season", "week", "season_type", "posteam", "defteam", "epa", "qtr", "wp"]]
        home = d["game_id"].str.split("_").str[-1]
        d["home"] = np.where(d["game_id"].isin(neutral), 0, np.where(d["posteam"] == home, 1, -1))
        pbp[y] = d.reset_index(drop=True)
    sch["total"] = sch["home_score"] + sch["away_score"]
    league_ppg = (sch[sch["game_type"] == "REG"].groupby("season")["total"].mean() / 2).to_dict()
    return pbp, sch.set_index("game_id")["total"].to_dict(), league_ppg


# --- team means: raw (live) or ridge-adjusted --------------------------------

_cache: dict = {}


def garbage_mask(d):
    lo, hi = GARBAGE_WP
    return ~((d["qtr"] == 4) & ((d["wp"] < lo) | (d["wp"] > hi)))


def team_means(d, adj: bool, lam: float | None, key):
    """(off DataFrame[mean,count], def DataFrame[mean,count]) for a play sample."""
    ck = (key, adj, lam)
    if ck in _cache:
        return _cache[ck]
    off = d.groupby("posteam")["epa"].agg(["mean", "count"])
    dfn = d.groupby("defteam")["epa"].agg(["mean", "count"])
    if adj and len(d):
        s = d[d["epa"].notna()]
        teams = sorted(set(s["posteam"]) | set(s["defteam"]))
        ix = {t: i for i, t in enumerate(teams)}
        n, k = len(s), len(teams)
        rows = np.arange(n)
        X = sparse.hstack([
            sparse.csr_matrix((np.ones(n), (rows, s["posteam"].map(ix).to_numpy())), shape=(n, k)),
            sparse.csr_matrix((np.ones(n), (rows, s["defteam"].map(ix).to_numpy())), shape=(n, k)),
            sparse.csr_matrix(s["home"].to_numpy(dtype=float).reshape(-1, 1)),
        ]).tocsr()
        m = Ridge(alpha=lam, fit_intercept=True).fit(X, s["epa"].to_numpy(dtype=float))
        c0 = float(m.intercept_)
        off["mean"] = [c0 + m.coef_[ix[t]] for t in off.index]
        dfn["mean"] = [c0 + m.coef_[k + ix[t]] for t in dfn.index]
    _cache[ck] = (off, dfn)
    return off, dfn


def blend(cur, pri, team, r):
    cm = float(cur.loc[team, "mean"]) if team in cur.index else None
    cn = float(cur.loc[team, "count"]) if team in cur.index else 0.0
    pm = float(pri.loc[team, "mean"]) * r if team in pri.index else None
    if cm is None:
        return pm
    if pm is None:
        return cm
    w = cn / (cn + PRIOR_PLAYS_WEIGHT)
    return w * cm + (1 - w) * pm


def samples(pbp, season, week, filt):
    cur = pbp[season]
    cur = cur[(cur["season_type"] == "REG") & (cur["week"] < week)]
    pri = pbp[season - 1]
    if filt:
        cur, pri = cur[garbage_mask(cur)], pri[garbage_mask(pri)]
    return cur, pri


def ratings(pbp, season, week, arm):
    """{team: (off_epa, def_epa)} blended, per the arm."""
    adj, filt, lam, r_off, r_def = arm["adj"], arm["filt"], arm.get("lam"), arm["r_off"], arm["r_def"]
    cur, pri = samples(pbp, season, week, filt)
    off_c, def_c = team_means(cur, adj, lam, ("cur", season, week, filt))
    off_p, def_p = team_means(pri, adj, lam, ("pri", season - 1, filt))
    out = {}
    for t in sorted(set(off_c.index) | set(off_p.index)):
        o, d = blend(off_c, off_p, t, r_off), blend(def_c, def_p, t, r_def)
        if o is not None and d is not None:
            out[t] = (o, d)
    return out


def carry_factors(pbp, adj, filt, lam):
    """B: through-origin slope of a team's REG mean on its previous full season, off and def (2016-2021)."""
    xs = {"off": [], "def": []}
    ys = {"off": [], "def": []}
    for s in TRAIN:
        cur = pbp[s][pbp[s]["season_type"] == "REG"]
        pri = pbp[s - 1]
        if filt:
            cur, pri = cur[garbage_mask(cur)], pri[garbage_mask(pri)]
        oc, dc = team_means(cur, adj, lam, ("full", s, filt))
        op, dp = team_means(pri, adj, lam, ("pri", s - 1, filt))
        for side, c, p in (("off", oc, op), ("def", dc, dp)):
            t = c.index.intersection(p.index)
            xs[side] += list(p.loc[t, "mean"] - p["mean"].mean())
            ys[side] += list(c.loc[t, "mean"] - c["mean"].mean())
    f = {k: float(np.dot(xs[k], ys[k]) / np.dot(xs[k], xs[k])) for k in xs}
    return f["off"], f["def"]


# --- games --------------------------------------------------------------------

def situational(row):     # P37's copy of the live terms
    hfa = 0.0 if row["is_neutral"] else F.HOME_FIELD_POINTS["nfl"]
    rest = max(-F.REST_CAP_POINTS, min(F.REST_CAP_POINTS, row["rest_diff"] * F.REST_POINTS_PER_DAY))
    away_mi, home_mi = row["travel_away"], row["travel_away"] - row["travel_diff"]
    pen = lambda mi: min(F.TRAVEL_CAP_POINTS, max(mi, 0) / 1000.0 * F.TRAVEL_POINTS_PER_1000MI)  # noqa: E731
    wind = row["wind"] or 0.0
    wf = 1.0 - min(F.WIND_COMPRESSION_CAP, (wind - F.WIND_THRESHOLD_MPH) * F.WIND_COMPRESSION_PER_MPH) \
        if wind > F.WIND_THRESHOLD_MPH else 1.0
    return hfa + rest + pen(away_mi) - pen(home_mi), wf


def evaluate(pbp, games, totals, league_ppg, arm):
    rows, cache = [], {}
    for _, g in games.iterrows():
        key = (int(g["season"]), int(g["week"]))
        if key not in cache:
            rt = ratings(pbp, *key, arm)
            bars = (np.mean([v[0] for v in rt.values()]), np.mean([v[1] for v in rt.values()])) if rt else (0, 0)
            cache[key] = (rt, bars)
        rt, (ob, db_) = cache[key]
        h, a = rt.get(CANON.get(g["home_team"], g["home_team"])), rt.get(CANON.get(g["away_team"], g["away_team"]))
        if not h or not a:
            continue
        sit, wf = situational(g)
        margin = ((h[0] - h[1]) - (a[0] - a[1])) * PLAYS_PER_GAME + sit
        margin *= wf
        L = league_ppg.get(key[0] - 1)
        tot_hat = 2 * L + PLAYS_PER_GAME * ((h[0] - ob) + (a[0] - ob) + (h[1] - db_) + (a[1] - db_))
        rows.append({"game_id": g["game_id"], "season": key[0], "week": key[1], "margin": margin,
                     "actual": g["target_margin"], "edge": margin + g["market_spread"],
                     "resid": g["target_margin"] + g["market_spread"], "tot_hat": tot_hat,
                     "tot": totals.get(g["game_id"]), "mkt_tot": g["market_total"]})
    r = pd.DataFrame(rows)
    r["err"] = (r["margin"] - r["actual"]).abs()
    return r


# --- statistics (P37's) ---------------------------------------------------------

def ats_record(edge, resid):
    took_home = edge > 0
    push = resid == 0
    win = (~push) & (took_home == (resid > 0))
    return int(win.sum()), int((~push & ~win).sum()), int(push.sum())


def fmt_rec(w, l, p):
    return f"{w}-{l}" + (f"-{p}" if p else "") + (f" ({w / (w + l) * 100:.0f}%)" if w + l else "")


def win_pct(edge, resid):
    w, l, _ = ats_record(edge, resid)
    return w / (w + l) if w + l else float("nan")


def corr_ci(x, y):
    n = len(x)
    r = float(np.corrcoef(x, y)[0, 1])
    z, se = math.atanh(max(min(r, 0.999999), -0.999999)), 1 / math.sqrt(n - 3)
    p = math.erfc(abs(z) / se / math.sqrt(2))
    return r, (math.tanh(z - 1.96 * se), math.tanh(z + 1.96 * se)), p


def slope_ci(x, y):
    b = float((x * y).sum() / (x * x).sum())
    res = y - b * x
    se = math.sqrt((res ** 2).sum() / (len(x) - 1) / (x * x).sum())
    return b, (b - 1.96 * se, b + 1.96 * se)


def lean_slope(edge, resid):
    x, y = np.abs(edge), np.sign(edge) * resid
    x = x - x.mean()
    return float((x * (y - y.mean())).sum() / (x * x).sum())


def perm_p(edge, resid):
    obs = lean_slope(edge, resid)
    null = np.array([lean_slope(edge, RNG.permutation(resid)) for _ in range(N_PERM)])
    return obs, float((np.abs(null) >= abs(obs)).mean())


def table(rows, headers):
    say("| " + " | ".join(headers) + " |")
    say("|" + "|".join("---" for _ in headers) + "|")
    for r in rows:
        say("| " + " | ".join(str(x) for x in r) + " |")
    say()


# --- run ------------------------------------------------------------------------

def mae(r, m=None):
    s = r if m is None else r[m]
    return float(s["err"].mean())


def tune(pbp, games, totals, league_ppg, adj, filt, split):
    """Returns the frozen arm. For adj: 1-SE rule toward the larger penalty on 2016-2021 MAE."""
    base = {"adj": adj, "filt": filt}
    def make(lam):
        a = dict(base, lam=lam)
        a["r_off"], a["r_def"] = (carry_factors(pbp, adj, filt, lam) if split
                                  else (PRIOR_SEASON_REGRESSION, PRIOR_SEASON_REGRESSION))
        return a
    if not adj:
        return make(None), None
    tr = games[games["season"].isin(TRAIN)]
    res = []
    for lam in LAMBDAS:
        a = make(lam)
        r = evaluate(pbp, tr, totals, league_ppg, a)
        res.append((lam, r["err"].mean(), r["err"].std() / math.sqrt(len(r)), a))
    best = min(res, key=lambda x: x[1])
    ok = [x for x in res if x[1] <= best[1] + best[2]]
    pick = max(ok, key=lambda x: x[0])
    return pick[3], [(x[0], round(x[1], 4)) for x in res]


if __name__ == "__main__":
    pbp, totals, league_ppg = load()
    games = pd.read_csv(ROOT / "data" / "training_nfl.csv")
    games = games[(games["season"] >= 2016) & (games["week"] <= 18) & games["market_spread"].notna()]
    hist = games[games["season"] <= 2025]
    g26 = games[games["season"] == 2026]

    say("# P22 phase 1: opponent-adjusted rating, walk-forward (research only)")
    say()
    R0 = {"adj": False, "filt": False, "r_off": PRIOR_SEASON_REGRESSION, "r_def": PRIOR_SEASON_REGRESSION}
    r0 = evaluate(pbp, hist, totals, league_ppg, R0)
    rec = ats_record(r0["edge"].to_numpy(), r0["resid"].to_numpy())
    cr = corr_ci(r0["edge"].to_numpy(), r0["resid"].to_numpy())[0]
    # The corrected P37 replay (OAK/SD/STL restored 2026-09-22), as used by P9 / P46; its 9/21 figures
    # (2,582 games) predate that fix. Edge-for-edge equality with P37's replay() was also checked (7e-15).
    say(f"**R0 check against the corrected P37 replay:** n {len(r0)} (2,661); all-weeks ATS {fmt_rec(*rec)} "
        f"(1294-1302-65); corr {cr:+.3f} (-0.002).")
    ok = len(r0) == 2661 and rec == (1294, 1302, 65) and round(cr, 3) == -0.002
    say(f"Reproduces P37: **{'YES' if ok else 'NO - stopping'}**")
    say()
    if not ok:
        OUT and OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        sys.exit(1)

    arms, tuning = {"R0": R0}, {}
    specs = {"A": (True, False, False), "B": (False, False, True), "C": (False, True, False), "ABC": (True, True, True)}
    for name, (adj, filt, split) in specs.items():
        arms[name], tuning[name] = tune(pbp, hist, totals, league_ppg, adj, filt, split)
    say("**Frozen settings (2016-2021 only):**")
    for name, a in arms.items():
        say(f"- {name}: penalty {a.get('lam')}, carry off {a['r_off']:.3f} / def {a['r_def']:.3f}, "
            f"garbage filter {'on' if a['filt'] else 'off'}" + (f"; training MAE by penalty {tuning[name]}" if tuning.get(name) else ""))
    say()

    res = {n: evaluate(pbp, hist, totals, league_ppg, a) for n, a in arms.items()}
    test = {n: r[r["season"].isin(TEST)] for n, r in res.items()}
    base = mae(test["R0"])
    gains = {n: base - mae(test[n]) for n in ("A", "B", "C")}
    keep = [n for n in ("A", "B", "C") if gains[n] >= 0.03]
    say("**Bar 5, attribution (test 2022-2025, margin MAE gain vs R0; a part needs >= 0.03):** "
        + ", ".join(f"{n} {gains[n]:+.3f}{' (kept)' if n in keep else ' (dropped)'}" for n in ("A", "B", "C")))
    say()

    cand_name = "+".join(keep) if keep else None
    if keep and set(keep) != {"A", "B", "C"}:
        arms[cand_name], tuning[cand_name] = tune(pbp, hist, totals, league_ppg, "A" in keep, "C" in keep, "B" in keep)
        res[cand_name] = evaluate(pbp, hist, totals, league_ppg, arms[cand_name])
        test[cand_name] = res[cand_name][res[cand_name]["season"].isin(TEST)]
        a = arms[cand_name]
        say(f"Candidate {cand_name} frozen: penalty {a.get('lam')}, carry off {a['r_off']:.3f} / def {a['r_def']:.3f}")
        say()
    elif keep:
        cand_name = "ABC"

    # summary table, every arm
    rows = []
    for n, r in res.items():
        t, tr = test[n], r[r["season"].isin(TRAIN)]
        per = [mae(t, t["season"] == s) for s in TEST]
        rows.append([n, f"{mae(tr):.3f}", f"{mae(t):.3f}", f"{base - mae(t):+.3f}",
                     " / ".join(f"{x:.2f}" for x in per), f"{mae(t, t['week'] <= 4):.3f}",
                     f"{t['edge'].abs().mean():.2f}", f"{win_pct(t['edge'].to_numpy()[t['edge'].abs() >= 4], t['resid'].to_numpy()[t['edge'].abs() >= 4]) * 100:.1f}",
                     f"{(t['tot_hat'] - t['tot']).abs().mean():.3f}"])
    table(rows, ["arm", "train MAE", "test MAE", "gain vs R0", "test MAE by season 22/23/24/25", "test wk 1-4 MAE",
                 "test mean abs edge", "test ATS% at abs edge>=4", "test implied-total MAE"])
    say(f"Line on the test games: margin MAE {(test['R0']['resid']).abs().mean():.3f}, "
        f"total MAE {(test['R0']['mkt_tot'] - test['R0']['tot']).abs().mean():.3f}.")
    say()

    if cand_name is None:
        say("**No part clears 0.03, so there is no candidate: P22 fails bar 5. Stop rule applies.**")
    else:
        c, b0 = test[cand_name], test["R0"]
        per_c = [mae(c, c["season"] == s) for s in TEST]
        per_0 = [mae(b0, b0["season"] == s) for s in TEST]
        better = sum(x < y for x, y in zip(per_c, per_0))
        g = base - mae(c)
        e4c = win_pct(c["edge"].to_numpy()[c["edge"].abs() >= 4], c["resid"].to_numpy()[c["edge"].abs() >= 4])
        e40 = win_pct(b0["edge"].to_numpy()[b0["edge"].abs() >= 4], b0["resid"].to_numpy()[b0["edge"].abs() >= 4])
        bars = [
            ("1 pooled gain >= 0.10, better in >= 3/4 seasons", f"{g:+.3f}, better in {better}/4", g >= 0.10 and better >= 3),
            ("2 weeks 1-4 not worse", f"{mae(c, c['week'] <= 4):.3f} vs {mae(b0, b0['week'] <= 4):.3f}",
             mae(c, c["week"] <= 4) <= mae(b0, b0["week"] <= 4)),
            ("3 mean abs edge <= R0 + 0.05; ATS% at >= 4 not > 2 pp below",
             f"{c['edge'].abs().mean():.2f} vs {b0['edge'].abs().mean():.2f}; {e4c * 100:.1f}% vs {e40 * 100:.1f}%",
             c["edge"].abs().mean() <= b0["edge"].abs().mean() + 0.05 and e4c >= e40 - 0.02),
            ("4 implied totals MAE not worse", f"{(c['tot_hat'] - c['tot']).abs().mean():.3f} vs {(b0['tot_hat'] - b0['tot']).abs().mean():.3f}",
             (c["tot_hat"] - c["tot"]).abs().mean() <= (b0["tot_hat"] - b0["tot"]).abs().mean()),
        ]
        say(f"### Bars 1-4 on the candidate ({cand_name})")
        say()
        table([[n, v, "**pass**" if p else "**fail**"] for n, v, p in bars], ["bar", "result", "verdict"])

    # bar 7: P37 Test 2 on R0 and the candidate
    say("### Bar 7 (reported, not a bar): P37 Test 2, ATS information in the edge")
    say()
    for n in ["R0"] + ([cand_name] if cand_name else []):
        rows = []
        for scope, frame in (("test 2022-25", test[n]), ("all 2016-25", res[n])):
            for wk, m in (("all weeks", frame["week"] > 0), ("weeks 1-4", frame["week"] <= 4)):
                s = frame[m]
                e, r = s["edge"].to_numpy(), s["resid"].to_numpy()
                cr, ci, cp = corr_ci(e, r)
                b, bci = slope_ci(e, r)
                ls, lp = perm_p(e, r)
                rows.append([scope, wk, len(s), *[fmt_rec(*ats_record(e[np.abs(e) >= t], r[np.abs(e) >= t])) for t in THRESHOLDS],
                             f"{cr:+.3f} ({ci[0]:+.2f}, {ci[1]:+.2f}) p={cp:.3f}", f"{b:+.2f} ({bci[0]:+.2f}, {bci[1]:+.2f})",
                             f"{ls:+.3f} p={lp:.3f}"])
        say(f"**{n}**")
        say()
        table(rows, ["seasons", "weeks", "n", *[f">= {t:g}" for t in THRESHOLDS], "corr (95% CI)", "b (95% CI)", "lean slope (perm p)"])

    # 2026, reported only
    if len(g26):
        say("### 2026 rows in the training file (reported only)")
        say()
        rows = []
        for n in ["R0"] + ([cand_name] if cand_name else []):
            r = evaluate(pbp, g26, totals, league_ppg, arms[n])
            rows.append([n, len(r), f"{r['err'].mean():.3f}", f"{r['edge'].abs().mean():.2f}", fmt_rec(*ats_record(r["edge"].to_numpy(), r["resid"].to_numpy()))])
        table(rows, ["arm", "n", "MAE", "mean abs edge", "ATS"])

    if OUT:
        OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\nwrote {OUT}")
