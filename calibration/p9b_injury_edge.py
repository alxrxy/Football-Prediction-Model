"""P9 part 2: a scaled-down injury coefficient, judged on betting edges, and how
stable that coefficient is across seasons. Diagnosis only. Read-only.

    python calibration/p9b_injury_edge.py <pbp_dir> calibration/2026-09-22_p9b_injury_edge.md

Arms, criteria and verdicts were fixed in calibration-log.md (2026-09-22,
"P9 part 2 scoped") before this ran. Baseline, term and line come from part 1's
build (calibration/p9_injury_coefficient.py), which passed its input gate.

    edge_c = baseline + c x term + market_spread      (+ => lean home)
    L: c = 1.0   B: c = walk-forward beta   M: c = walk-forward beta_mkt   0: c = 0
"""
import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
from scipy import stats

HERE = Path(__file__).resolve().parent
PBP_DIR = sys.argv[1]
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else None

_argv, sys.argv = sys.argv, [str(HERE / "p9_injury_coefficient.py"), PBP_DIR]
_spec = importlib.util.spec_from_file_location("p9", HERE / "p9_injury_coefficient.py")
p9 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p9)
sys.argv = _argv

sys.path.insert(0, str(HERE.parent))
from src import market  # noqa: E402

p37, say, table, ols = p9.p37, p9.say, p9.table, p9.ols
WF_SEASONS = p9.WF_SEASONS
ALL_SEASONS = list(range(2016, 2026))
THRESHOLDS = (0.0, 2.0, 3.0, 4.0, 6.0)
BIG = 3.0                 # E2
HEAVY = 2.0               # E3: |raw term| >= 2
TOL = 0.15                # S3 / S4
BREAKEVEN = 0.524
FLAG_PTS = market.points_to_flag(p9.SIGMA)
ARMS = ("L", "B", "M", "0")
NAME = {"L": "L, c = 1.0 (live)", "B": "B, c = walk-forward beta", "M": "M, c = walk-forward beta_mkt",
        "0": "0, c = 0 (reference)"}
COEF_Y = {"B": "y_mag", "M": "y_mkt"}


def coef(d, y):
    return ols(d, y, ["term"])["term"]


def rec(edge, resid):
    w, l, _ = p37.ats_record(edge, resid)
    return w, l


def fmt(w, l):
    return f"{w}-{l} ({w / (w + l) * 100:.1f}%)" if w + l else "-"


def binom_ge(k, n, p=0.5):
    return float(stats.binom.sf(k - 1, n, p)) if n else 1.0


# --- edges ---------------------------------------------------------------------

def walk_forward(d):
    rows, path = [], {"B": {}, "M": {}}
    for y in WF_SEASONS:
        prior, t = d[d.season < y], d[d.season == y].copy()
        c = {"L": 1.0, "0": 0.0}
        for arm in ("B", "M"):
            c[arm] = coef(prior, COEF_Y[arm])[0]
            path[arm][y] = c[arm]
        for arm in ARMS:
            t[f"e{arm}"] = t["base"] + c[arm] * t["term"] + t["market"]
        rows.append(t)
    import pandas as pd
    return pd.concat(rows), path


def edge_report(w):
    say("## Edges, walk-forward 2019-25")
    say()
    say(f"{len(w)} games. Live flag threshold at -110 against a 50/50 line: **{FLAG_PTS:.2f} pts**. "
        "Games at or past it: " + ", ".join(f"{a} {int((w[f'e{a}'].abs() >= FLAG_PTS).sum())}" for a in ARMS) + ".")
    say()
    rows = []
    for arm in ARMS:
        e = w[f"e{arm}"]
        rows.append([NAME[arm]] + [fmt(*rec(e[e.abs() >= t], w.resid[e.abs() >= t])) for t in THRESHOLDS])
    table(rows, ["arm"] + [f"|edge| >= {t:g}" for t in THRESHOLDS])
    say()

    rows = []
    for arm in ARMS:
        e = w[f"e{arm}"]
        b, s = ols(w.assign(x=e), "resid", ["x"])["x"]
        big = e.abs() >= BIG
        bw, bl = rec(e[big], w.resid[big])
        rows.append([NAME[arm], f"{e.abs().mean():.2f}", p9.ci(b, s), fmt(bw, bl),
                     f"{binom_ge(bw, bw + bl, BREAKEVEN):.3f}"])
    table(rows, ["arm", "mean |edge|", "slope resid on edge (95% CI)", "ATS |edge| >= 3",
                 "p vs 52.4% (one-sided)"])
    say()

    say("### Per season, all leans")
    say()
    rows = []
    for y in WF_SEASONS:
        t = w[w.season == y]
        rows.append([str(y)] + [fmt(*rec(t[f"e{a}"], t.resid)) for a in ARMS])
    table(rows, ["season"] + list(ARMS))
    say()

    verdicts = {}
    for arm in ("B", "M"):
        eL, eC = w["eL"], w[f"e{arm}"]
        flip = ((eL > 0) != (eC > 0)) & (w.resid != 0)
        k = int(((eC[flip] > 0) == (w.resid[flip] > 0)).sum())
        n = int(flip.sum())
        p = binom_ge(k, n)
        bigC, bigL = eC.abs() >= BIG, eL.abs() >= BIG
        rC, rL = rec(eC[bigC], w.resid[bigC]), rec(eL[bigL], w.resid[bigL])
        heavy = w.term_raw.abs() >= HEAVY
        hC, hL = rec(eC[heavy], w.resid[heavy]), rec(eL[heavy], w.resid[heavy])
        t25 = w[w.season == 2025]
        aC, aL = rec(t25[f"e{arm}"], t25.resid), rec(t25.eL, t25.resid)
        pct = lambda r: r[0] / (r[0] + r[1]) if sum(r) else 0.0  # noqa: E731
        crit = {
            "E1 paired, p < 0.05": (p < 0.05, f"{k}-{n - k} on {n} flipped games, p {p:.3f}"),
            "E2 |edge| >= 3 not below L": (pct(rC) >= pct(rL), f"{fmt(*rC)} vs L {fmt(*rL)}"),
            "E3 |term| >= 2 not below L": (pct(hC) >= pct(hL), f"{fmt(*hC)} vs L {fmt(*hL)} ({int(heavy.sum())} games)"),
            "E4 2025 not below L": (pct(aC) >= pct(aL), f"{fmt(*aC)} vs L {fmt(*aL)}"),
        }
        verdicts[arm] = crit
        say(f"### {NAME[arm]} against L")
        say()
        table([[k_, "pass" if v else "fail", d_] for k_, (v, d_) in crit.items()], ["criterion", "verdict", "detail"])
        say()
    # arm 0 against L, recorded only
    e0 = w["e0"]; flip = ((w.eL > 0) != (e0 > 0)) & (w.resid != 0)
    k = int(((e0[flip] > 0) == (w.resid[flip] > 0)).sum())
    say(f"Reference, arm 0 against L on flipped games: {k}-{int(flip.sum()) - k}, p {binom_ge(k, int(flip.sum())):.3f}.")
    say()
    return verdicts


# --- stability -------------------------------------------------------------------

def stability(d, path):
    say("## Stability of each candidate coefficient")
    say()
    out = {}
    for arm in ("B", "M"):
        y = COEF_Y[arm]
        est = np.array([coef(d[d.season == s], y) for s in ALL_SEASONS])
        e, se = est[:, 0], est[:, 1]
        wt = 1 / se ** 2
        pooled = float((wt * e).sum() / wt.sum())
        q = float((wt * (e - pooled) ** 2).sum())
        q_p = float(stats.chi2.sf(q, len(e) - 1))
        i2 = max(0.0, (q - (len(e) - 1)) / q) if q > 0 else 0.0
        X = np.column_stack([np.ones(len(e)), np.array(ALL_SEASONS, float) - 2020.5])
        cov = np.linalg.inv(X.T @ (X * wt[:, None]))
        slope = float((cov @ X.T @ (wt * e))[1]); slope_se = float(math.sqrt(cov[1, 1]))
        full = coef(d, y)[0]
        loso = {s: coef(d[d.season != s], y)[0] for s in ALL_SEASONS}
        loso_dev = max(abs(v - full) for v in loso.values())
        wf = path[arm]; last = wf[2025]
        wf_dev = max(abs(v - last) for v in wf.values())
        crit = {
            "S1 heterogeneity Q p >= 0.05": (q_p >= 0.05, f"Q {q:.1f} on {len(e) - 1} df, p {q_p:.4f}, I^2 {i2 * 100:.0f}%"),
            "S2 trend CI includes 0": (abs(slope) <= 1.96 * slope_se,
                                       f"slope {slope:+.3f}/season ({slope - 1.96 * slope_se:+.3f} to {slope + 1.96 * slope_se:+.3f})"),
            f"S3 leave-one-out within +/-{TOL}": (loso_dev <= TOL, f"full {full:.3f}; max deviation {loso_dev:.3f} "
                                                  f"(drop {max(loso, key=lambda s: abs(loso[s] - full))})"),
            f"S4 walk-forward path within +/-{TOL}": (wf_dev <= TOL, f"2025 value {last:.3f}; path "
                                                      f"{min(wf.values()):.3f}-{max(wf.values()):.3f}, max deviation {wf_dev:.3f}"),
        }
        out[arm] = crit
        label = "beta (outcome-implied)" if arm == "B" else "beta_mkt (market-implied)"
        say(f"### {label}")
        say()
        table([[str(s), p9.ci(a, b)] for s, (a, b) in zip(ALL_SEASONS, est)]
              + [["inverse-variance pooled", f"{pooled:+.3f}"]], ["season", "single-season estimate (95% CI)"])
        say()
        table([[k, "pass" if v else "fail", t] for k, (v, t) in crit.items()], ["criterion", "verdict", "detail"])
        say()
        table([[str(s), f"{loso[s]:.3f}"] for s in ALL_SEASONS], ["season dropped", "full-sample estimate"])
        say()
    return out


def main():
    say("# P9 part 2 — a scaled-down injury coefficient, judged on edges (diagnosis only)")
    say()
    say("Rules fixed in calibration-log.md (2026-09-22, \"P9 part 2 scoped\") before this ran.")
    say()
    post = p9.regen(old_key=False)
    d, gate = p9.build(p37.load_pbp(), post, post)
    assert gate["post_mismatch"] == 0, "part 1's input gate no longer holds"
    d["term_raw"] = d["term"]            # E3's subset: the same games for every arm
    w, path = walk_forward(d)
    say("Walk-forward coefficients (fitted on 2016..Y-1):")
    say()
    table([[str(y), f"{path['B'][y]:.3f}", f"{path['M'][y]:.3f}"] for y in WF_SEASONS], ["season", "beta (B)", "beta_mkt (M)"])
    say()
    ev = edge_report(w)
    sv = stability(d, path)
    say("## Verdict by the pre-set rules")
    say()
    rows = []
    for arm in ("B", "M"):
        e_ok, s_ok = all(v for v, _ in ev[arm].values()), all(v for v, _ in sv[arm].values())
        s_fail = [k.split()[0] for k, (v, _) in sv[arm].items() if not v]
        verdict = ("propose to the user" if e_ok and s_ok
                   else "better than 1.0 but not a stable number" if e_ok
                   else "fails the edge test: 1.0 stays on this evidence")
        rows.append([NAME[arm], "pass" if e_ok else "fail", "pass" if s_ok else "fail (" + ", ".join(s_fail) + ")", verdict])
    table(rows, ["arm", "E1-E4", "S1-S4", "verdict"])
    say()


if __name__ == "__main__":
    main()
    if OUT:
        OUT.write_text("\n".join(p37.lines) + "\n", encoding="utf-8")
        print(f"\nwrote {OUT}")
