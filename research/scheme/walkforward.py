"""P46 walk-forward: do scheme features add to the live baseline, out of sample?
Research only; writes nothing to the store. Criteria were fixed in
calibration-log.md ("P46 scoped", 2026-09-25) before this ran.

    python -m research.scheme.walkforward calibration/2026-09-25_p46_scheme_walkforward.md

Baseline: P37's exact replay of live Layer 1 + HFA/rest/travel/wind (its own
ratings() and situational(), re-assembled here only to keep game ids). Line:
the training file's market spread / total. Terms are fitted through the origin
on standardised features, on training seasons only.
"""
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research.scheme import features as SF  # noqa: E402
from src.features import MARGIN_SIGMA  # noqa: E402
from src.sim_data import load_pbp  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else None
P37_PBP = SF.CACHE / "p37_pbp"
SIGMA = MARGIN_SIGMA["nfl"]
LINES: list[str] = []


def say(text=""):
    print(text)
    LINES.append(text)


def _p37():
    """calibration/p37_edge_diagnosis.py, loaded as P39 loads it."""
    P37_PBP.mkdir(parents=True, exist_ok=True)
    for y in range(2015, 2026):
        path = P37_PBP / f"pbp_{y}.parquet"
        if not path.exists():
            d = load_pbp([y])
            d = d[d["play_type"].isin(["pass", "run"]) & d["posteam"].notna()]
            d.assign(season=y)[["season", "week", "season_type", "posteam", "defteam", "epa"]].to_parquet(path)
    argv, sys.argv = sys.argv, ["p37", str(P37_PBP)]
    spec = importlib.util.spec_from_file_location("p37", ROOT / "calibration" / "p37_edge_diagnosis.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.argv = argv
    return mod


def baseline_games() -> pd.DataFrame:
    import nfl_data_py as nfl

    p37 = _p37()
    pbp = p37.load_pbp()
    train = pd.read_csv(ROOT / "data" / "training_nfl.csv")
    train = train[(train["season"].between(2016, 2025)) & (train["week"] <= 18) & train["market_spread"].notna()]
    sched = nfl.import_schedules(list(range(2016, 2026)))
    totals = dict(zip(sched["game_id"], sched["home_score"] + sched["away_score"]))
    cache, rows = {}, []
    for _, g in train.iterrows():
        key = (int(g["season"]), int(g["week"]))
        if key not in cache:
            cache[key] = p37.ratings(*key, pbp)
        rt = cache[key]
        home, away = p37.CANON.get(g["home_team"], g["home_team"]), p37.CANON.get(g["away_team"], g["away_team"])
        h, a = rt.get(home), rt.get(away)
        if not h or not a:
            continue
        sit, wf = p37.situational(g)
        margin = (sum(h[k] - a[k] for k in h) + sit) * wf
        rows.append({"game_id": g["game_id"], "season": key[0], "week": key[1], "home": home, "away": away,
                     "base": margin, "spread": g["market_spread"], "mtotal": g["market_total"],
                     "actual": g["target_margin"], "total": totals.get(g["game_id"], np.nan)})
    return pd.DataFrame(rows)


def attach(games: pd.DataFrame, feats: pd.DataFrame, names) -> pd.DataFrame:
    f = feats.set_index(["season", "week", "team"])[list(names)]
    h = f.reindex(pd.MultiIndex.from_frame(games[["season", "week", "home"]])).to_numpy()
    a = f.reindex(pd.MultiIndex.from_frame(games[["season", "week", "away"]])).to_numpy()
    out = games.copy()
    for i, n in enumerate(names):
        out[f"d_{n}"], out[f"s_{n}"] = h[:, i] - a[:, i], h[:, i] + a[:, i]
    return out.dropna(subset=[f"d_{n}" for n in names])


def fit_origin(X, y):
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return beta


def corr_p(x, y):
    """Pearson r and its one-sided p (r > 0), normal approximation to t."""
    r = float(np.corrcoef(x, y)[0, 1])
    n = len(x)
    t = r * math.sqrt((n - 2) / max(1e-12, 1 - r * r))
    return r, 0.5 * math.erfc(t / math.sqrt(2))


def ats(edge, resid):
    m = (edge != 0) & (resid != 0)
    w = int(((edge > 0) == (resid > 0))[m].sum())
    return w, int(m.sum()) - w


def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def brier(margin, actual):
    m = actual != 0
    p = np.array([phi(v / SIGMA) for v in margin[m]])
    return float(np.mean((p - (actual[m] > 0)) ** 2))


def run_set(label, games, names, tests):
    d_cols, s_cols = [f"d_{n}" for n in names], [f"s_{n}" for n in names]
    per, pooled = [], []
    for ys in tests:
        tr, te = games[games["season"] < ys], games[games["season"] == ys]
        mu, sd = tr[d_cols].mean(), tr[d_cols].std().replace(0, 1)
        beta = fit_origin(((tr[d_cols] - mu) / sd).to_numpy(), (tr["actual"] - tr["base"]).to_numpy())
        term = ((te[d_cols] - mu) / sd).to_numpy() @ beta
        tt = tr.dropna(subset=["total", "mtotal"])
        mus, sds = tt[s_cols].mean(), tt[s_cols].std().replace(0, 1)
        gamma = fit_origin(((tt[s_cols] - mus) / sds).to_numpy(), (tt["total"] - tt["mtotal"]).to_numpy())
        tterm = ((te[s_cols] - mus) / sds).to_numpy() @ gamma
        x = te.assign(term=term, tterm=tterm)
        pooled.append(x)
        per.append(summ(ys, x, beta, names))
    say(f"### Set {label}: {', '.join(names)}")
    say()
    say("| test season | games | margin MAE base | + term | gain | Brier base | + term | ATS base | ATS + term | corr(term, cover) | corr(total term, total resid) | total MAE mkt | + term |")
    say("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in per:
        say(f"| {r['season']} | {r['n']} | {r['mae_b']:.3f} | {r['mae_t']:.3f} | {r['mae_b'] - r['mae_t']:+.3f} | "
            f"{r['br_b']:.4f} | {r['br_t']:.4f} | {r['ats_b'][0]}-{r['ats_b'][1]} | {r['ats_t'][0]}-{r['ats_t'][1]} | "
            f"{r['r']:+.3f} | {r['rt']:+.3f} | {r['tm_b']:.3f} | {r['tm_t']:.3f} |")
    allx = pd.concat(pooled)
    P = summ("pooled", allx, None, names)
    say(f"| **pooled** | {P['n']} | {P['mae_b']:.3f} | {P['mae_t']:.3f} | {P['mae_b'] - P['mae_t']:+.3f} | "
        f"{P['br_b']:.4f} | {P['br_t']:.4f} | {P['ats_b'][0]}-{P['ats_b'][1]} | {P['ats_t'][0]}-{P['ats_t'][1]} | "
        f"{P['r']:+.3f} (p {P['p']:.3f}) | {P['rt']:+.3f} (p {P['pt']:.3f}) | {P['tm_b']:.3f} | {P['tm_t']:.3f} |")
    say()
    last = per[-1]
    need = 5 if label == "A" else 2
    improved = sum(r["mae_b"] - r["mae_t"] > 0 for r in per)
    rules = [
        ("S1 pooled MAE gain >= 0.10", P["mae_b"] - P["mae_t"] >= 0.10),
        ("S1 2025 MAE gain >= 0.10", last["mae_b"] - last["mae_t"] >= 0.10),
        (f"S2 improves in >= {need} of {len(per)} seasons ({improved})", improved >= need),
        ("S3 pooled Brier not worse", P["br_t"] <= P["br_b"]),
        ("E1 pooled corr(term, cover) > 0, one-sided p < 0.05", P["r"] > 0 and P["p"] < 0.05),
        ("E2 pooled ATS with term >= baseline", P["ats_t"][0] / max(1, sum(P["ats_t"])) >= P["ats_b"][0] / max(1, sum(P["ats_b"]))),
        ("E3 2025 corr(term, cover) > 0", last["r"] > 0),
        ("T1 pooled corr(total term, total resid) > 0, one-sided p < 0.05", P["rt"] > 0 and P["pt"] < 0.05),
        ("T2 pooled total MAE gain >= 0.10", P["tm_b"] - P["tm_t"] >= 0.10),
        ("T3 2025 total corr > 0", last["rt"] > 0),
    ]
    say("| criterion | result |")
    say("|---|---|")
    for name, ok in rules:
        say(f"| {name} | {'**pass**' if ok else 'fail'} |")
    say()
    say("Coefficients per test season (margin term, standardised features, points per SD):")
    for r in per:
        say(f"- {r['season']}: " + ", ".join(f"{n} {b:+.2f}" for n, b in zip(names, r["beta"])))
    say()
    return {name: ok for name, ok in rules}


def summ(season, x, beta, names):
    tm = x.dropna(subset=["total", "mtotal"])
    r, p = corr_p(x["term"].to_numpy(), (x["actual"] + x["spread"]).to_numpy())
    rt, pt = corr_p(tm["tterm"].to_numpy(), (tm["total"] - tm["mtotal"]).to_numpy())
    return {
        "season": season, "n": len(x), "beta": beta if beta is not None else [],
        "mae_b": float(np.mean(np.abs(x["actual"] - x["base"]))),
        "mae_t": float(np.mean(np.abs(x["actual"] - x["base"] - x["term"]))),
        "br_b": brier(x["base"].to_numpy(), x["actual"].to_numpy()),
        "br_t": brier((x["base"] + x["term"]).to_numpy(), x["actual"].to_numpy()),
        "ats_b": ats((x["base"] + x["spread"]).to_numpy(), (x["actual"] + x["spread"]).to_numpy()),
        "ats_t": ats((x["base"] + x["term"] + x["spread"]).to_numpy(), (x["actual"] + x["spread"]).to_numpy()),
        "r": r, "p": p, "rt": rt, "pt": pt,
        "tm_b": float(np.mean(np.abs(tm["total"] - tm["mtotal"]))),
        "tm_t": float(np.mean(np.abs(tm["total"] - tm["mtotal"] - tm["tterm"]))),
    }


def main():
    say("# P46 walk-forward: scheme features against the live baseline (research only)")
    say()
    say("Criteria fixed in calibration-log.md (2026-09-25, \"P46 scoped\") before this ran.")
    say()
    games = baseline_games()
    say(f"Baseline replay: {len(games)} REG games 2016-2025 with a line.")
    say()
    res = {}
    for label, names, tests in (("A", SF.SET_A, range(2019, 2026)), ("B", SF.SET_B, range(2023, 2026))):
        g = attach(games, SF.build(label), names)
        say(f"Set {label}: {len(g)} games with every feature ({g['season'].min()}-{g['season'].max()}).")
        say()
        res[label] = run_set(label, g, names, tests)
    if OUT:
        OUT.write_text("\n".join(LINES) + "\n", encoding="utf-8")
    return res


if __name__ == "__main__":
    main()
