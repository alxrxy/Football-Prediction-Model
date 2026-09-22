"""P39: the QB-vs-rating term, tested for edge against the line and as the sim anchor.
Design and validation only. Read-only.

    python calibration/p39_qb_rating_term.py <pbp_dir> <schedules.parquet> calibration/2026-09-22_p39_qb_rating_term.md

Tests, arms and pass rules were fixed in calibration-log.md (2026-09-22, "P39
scoped") before this ran. <pbp_dir> holds pbp_<season>.parquet for 2015-2025
with the part-1 columns plus qb_dropback and passer_id:

    cols = ["game_id", "season", "week", "season_type", "posteam", "defteam", "epa",
            "play_type", "qb_dropback", "passer_id"]
    (then keep play_type in pass/run with a posteam, as p37_edge_diagnosis.py does)

The baseline margin is P37's exact replay of live Layer 1 plus the situational
terms (no injury term), graded against nflverse's near-close spread_line.
"""
import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PBP_DIR, SCHED = sys.argv[1], sys.argv[2]
OUT = Path(sys.argv[3]) if len(sys.argv) > 3 else None

_argv, sys.argv = sys.argv, [str(HERE / "p37_edge_diagnosis.py"), PBP_DIR]
_spec = importlib.util.spec_from_file_location("p37", HERE / "p37_edge_diagnosis.py")
p37 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p37)
sys.argv = _argv

sys.path.insert(0, str(HERE.parent))
from src.features import MARGIN_SIGMA  # noqa: E402
from src.ingest_nflverse import PRIOR_PLAYS_WEIGHT, PRIOR_SEASON_REGRESSION  # noqa: E402

say, table, fmt_rec, ats_record = p37.say, p37.table, p37.fmt_rec, p37.ats_record
SHRINK_DB = 200          # dropbacks of league-average prior on a QB's own EPA/db (P28)
DB_PER_PLAY, PLAYS = 0.603, 63
SIGMA = MARGIN_SIGMA["nfl"]
ARMS = ("U", "I", "S")
ARM_NAME = {"U": "U, unrestricted (as logged)", "I": "I, identity (QB change)", "S": "S, scale (rating regression)"}


def canon(t):
    return p37.CANON.get(t, t)


# --- the term ---------------------------------------------------------------

class Term:
    """Per (season, week): each team's R, its rating-weighted QB mix, and Q for any QB."""

    def __init__(self, pbp):
        self.pbp = pbp
        self.db = {y: d[(d["season_type"] == "REG") & (d["qb_dropback"] == 1) & d["epa"].notna()]
                   for y, d in pbp.items()}
        self.cache = {}

    def at(self, season, week):
        key = (season, week)
        if key in self.cache:
            return self.cache[key]
        pri_db = self.db[season - 1]
        cur_db = self.db[season][self.db[season]["week"] < week]
        cur_plays = self.pbp[season]
        cur_plays = cur_plays[(cur_plays["season_type"] == "REG") & (cur_plays["week"] < week)]
        n_plays = cur_plays[cur_plays["epa"].notna()].groupby("posteam").size()   # the rating's own count

        window = pd.concat([pri_db, cur_db])
        league = float(window["epa"].mean())
        g = window.groupby("passer_id")["epa"].agg(["sum", "count"])
        q = ((g["sum"] + SHRINK_DB * league) / (g["count"] + SHRINK_DB)).to_dict()

        teams = {}
        for team in set(pri_db["posteam"]) | set(cur_db["posteam"]):
            cp, pp = cur_db[cur_db["posteam"] == team], pri_db[pri_db["posteam"] == team]
            cn = float(n_plays.get(team, 0))
            if not len(pp) and not len(cp):
                continue
            # the live blend: no current plays -> prior only; no prior season -> current only
            w = 1.0 if not len(pp) else (cn / (cn + PRIOR_PLAYS_WEIGHT) if len(cp) else 0.0)
            r = (w * cp["epa"].mean() if len(cp) else 0.0) + \
                ((1 - w) * PRIOR_SEASON_REGRESSION * pp["epa"].mean() if len(pp) else 0.0)
            mix = 0.0
            for part, weight in ((cp, w), (pp, 1 - w)):
                if len(part) and weight:
                    shares = part["passer_id"].value_counts(normalize=True)
                    mix += weight * sum(s * q.get(pid, league) for pid, s in shares.items())
            teams[team] = {"R": r, "mix": mix}
        self.cache[key] = (teams, q, league)
        return self.cache[key]

    def team_parts(self, season, week, team, qb):
        teams, q, league = self.at(season, week)
        t = teams.get(team)
        if t is None or qb is None:
            return None
        qv = q.get(qb, league)       # a QB with no dropbacks in the window: league average
        scale = DB_PER_PLAY * PLAYS
        return {"U": (qv - t["R"]) * scale, "I": (qv - t["mix"]) * scale, "S": (t["mix"] - t["R"]) * scale}


# --- data --------------------------------------------------------------------

def build(pbp, sched):
    starters = {}
    for g in sched.itertuples(index=False):
        starters[str(g.game_id)] = (g.home_qb_id if isinstance(g.home_qb_id, str) else None,
                                    g.away_qb_id if isinstance(g.away_qb_id, str) else None)
    train = pd.read_csv(HERE.parent / "data" / "training_nfl.csv")
    train = train[(train["season"] >= 2016) & (train["season"] <= 2025) & (train["week"] <= 18)
                  & train["market_spread"].notna()]
    term = Term(pbp)
    cache, rows, missing = {}, [], 0
    for _, g in train.iterrows():
        key = (int(g["season"]), int(g["week"]))
        if key not in cache:
            cache[key] = p37.ratings(*key, pbp)
        rt = cache[key]
        home, away = canon(g["home_team"]), canon(g["away_team"])
        h, a = rt.get(home), rt.get(away)
        if not h or not a:
            continue
        sit, wf = p37.situational(g)
        margin = (sum(h.values()) - sum(a.values()) + sit) * wf
        hq, aq = starters.get(g["game_id"], (None, None))
        th, ta = term.team_parts(*key, home, hq), term.team_parts(*key, away, aq)
        if th is None or ta is None:
            missing += 1
            continue
        rows.append({"season": key[0], "week": key[1], "game_id": g["game_id"],
                     "margin": margin, "actual": g["target_margin"], "market": g["market_spread"],
                     **{f"t{k}": (th[k] - ta[k]) * wf for k in ARMS}})
    d = pd.DataFrame(rows)
    d["resid"] = d["actual"] + d["market"]            # + => home beat the line
    return d, missing


# --- statistics ---------------------------------------------------------------

def fit_k(d, col):
    x, y = d[col].to_numpy(), (d["actual"] - d["margin"]).to_numpy()
    return float((x * y).sum() / (x * x).sum())


def corr_p(x, y):
    """Pearson r and one-sided p for r > 0 (Fisher z)."""
    r = float(np.corrcoef(x, y)[0, 1])
    z = math.atanh(max(min(r, 0.999999), -0.999999)) * math.sqrt(len(x) - 3)
    return r, 0.5 * math.erfc(z / math.sqrt(2))


def brier(margin, actual):
    m = actual != 0
    p = 0.5 * (1 + np.vectorize(math.erf)(margin[m] / SIGMA / math.sqrt(2)))
    return float(((p - (actual[m] > 0)) ** 2).mean())


def ats(edge, resid):
    w, l, _ = ats_record(edge, resid)
    return w, l


def judge(s, col, k):
    new = s["margin"] + k * s[col]
    e0 = (s["margin"] + s["market"]).to_numpy()
    e1 = (new + s["market"]).to_numpy()
    r, p = corr_p(s[col].to_numpy(), s["resid"].to_numpy())
    return {"n": len(s), "k": k,
            "mae0": float((s["actual"] - s["margin"]).abs().mean()),
            "mae1": float((s["actual"] - new).abs().mean()),
            "brier0": brier(s["margin"].to_numpy(), s["actual"].to_numpy()),
            "brier1": brier(new.to_numpy(), s["actual"].to_numpy()),
            "r": r, "p": p, "ats0": ats(e0, s["resid"].to_numpy()), "ats1": ats(e1, s["resid"].to_numpy()),
            "mean_abs": float((k * s[col]).abs().mean()), "mean_abs_raw": float(s[col].abs().mean()),
            "r_mkt": float(np.corrcoef(s[col], s["market"])[0, 1])}


def pct(w_l):
    w, l = w_l
    return f"{w}-{l} ({w / (w + l) * 100:.1f}%)"


# --- run ----------------------------------------------------------------------

def gate0(d):
    say("## Gate 0: is the rebuild the logged term? (arm U, k fitted 2022-23, judged 2024-25)")
    say()
    fit, test = d[d["season"].isin([2022, 2023])], d[d["season"].isin([2024, 2025])]
    k = fit_k(fit, "tU")
    j = judge(test, "tU", k)
    k_test = fit_k(test, "tU")
    table([["k (fitted 2022-23)", "0.780", f"{k:.3f}"],
           ["k on 2024-25 itself", "0.727", f"{k_test:.3f}"],
           ["margin MAE without the term, 2024-25", "11.557", f"{j['mae0']:.3f}"],
           ["margin MAE with the term, 2024-25", "10.903", f"{j['mae1']:.3f}"],
           ["mean |term| (k applied / raw)", "4.17", f"{j['mean_abs']:.2f} / {j['mean_abs_raw']:.2f}"],
           ["corr(term, market spread)", "-0.324", f"{j['r_mkt']:+.3f}"]],
          ["quantity", "logged 2026-09-20", "rebuild"])
    ok = abs(j["mae0"] - 11.557) <= 0.10 and abs(j["mae1"] - 10.903) <= 0.10 and abs(k - 0.780) <= 0.10
    say(f"**{'Reproduced' if ok else 'Not an exact rebuild'}** by the pre-set tolerance (both MAEs within 0.10, "
        f"k within 0.10). n = {j['n']} games.")
    say()
    return ok


def walk_forward(d):
    out = {}
    for arm in ARMS:
        col = f"t{arm}"
        per = []
        for season in range(2019, 2026):
            k = fit_k(d[(d["season"] >= 2016) & (d["season"] < season)], col)
            s = d[d["season"] == season]
            per.append((season, k, s.assign(pred=k * s[col])))
        pooled = pd.concat([p[2] for p in per])
        out[arm] = (per, pooled)
    return out


def phase1(wf):
    say("## Phase 1: edge against the line (walk-forward, k refitted each season on 2016 to the season before)")
    say()
    verdict = {}
    for arm in ARMS:
        per, pooled = wf[arm]
        col = f"t{arm}"
        rows = []
        for season, k, s in per:
            j = judge(s, col, k)
            rows.append([season, f"{k:+.3f}", f"{j['r']:+.3f}", pct(j["ats0"]), pct(j["ats1"]), f"{j['r_mkt']:+.3f}"])
        # pooled: judge each season with its own k, so compare predictions directly
        pr, pp = corr_p(pooled["pred"].to_numpy(), pooled["resid"].to_numpy())
        e0 = (pooled["margin"] + pooled["market"]).to_numpy()
        e1 = (pooled["margin"] + pooled["pred"] + pooled["market"]).to_numpy()
        a0, a1 = ats(e0, pooled["resid"].to_numpy()), ats(e1, pooled["resid"].to_numpy())
        rows.append(["pooled 2019-25", "per season", f"{pr:+.3f} (p {pp:.3f})", pct(a0), pct(a1),
                     f"{np.corrcoef(pooled['pred'], pooled['market'])[0, 1]:+.3f}"])
        say(f"### Arm {ARM_NAME[arm]}")
        say()
        table(rows, ["season", "k", "corr(term, cover residual)", "ATS without", "ATS with", "corr(term, spread)"])
        r25 = next(corr_p(s["pred"].to_numpy(), s["resid"].to_numpy())[0] for season, k, s in per if season == 2025)
        e1_ok, e2_ok, e3_ok = pr > 0 and pp < 0.05, a1[0] / sum(a1) >= a0[0] / sum(a0), r25 > 0
        verdict[arm] = e1_ok and e2_ok and e3_ok
        say(f"E1 pooled corr > 0 at p < 0.05: **{'yes' if e1_ok else 'no'}**. E2 ATS not worse: "
            f"**{'yes' if e2_ok else 'no'}**. E3 2025 corr > 0: **{'yes' if e3_ok else 'no'}** ({r25:+.3f}). "
            f"Phase 1 for arm {arm}: **{'PASS' if verdict[arm] else 'fail'}**.")
        say()
    return verdict


def phase2(wf):
    say("## Phase 2: the sim anchor (walk-forward margin accuracy)")
    say()
    res = {}
    for arm in ARMS:
        per, pooled = wf[arm]
        rows, better = [], 0
        for season, k, s in per:
            new = s["margin"] + s["pred"]
            m0, m1 = (s["actual"] - s["margin"]).abs().mean(), (s["actual"] - new).abs().mean()
            better += m1 < m0
            rows.append([season, len(s), f"{k:+.3f}", f"{m0:.3f}", f"{m1:.3f}", f"{m1 - m0:+.3f}"])
        new = pooled["margin"] + pooled["pred"]
        m0, m1 = (pooled["actual"] - pooled["margin"]).abs().mean(), (pooled["actual"] - new).abs().mean()
        b0 = brier(pooled["margin"].to_numpy(), pooled["actual"].to_numpy())
        b1 = brier(new.to_numpy(), pooled["actual"].to_numpy())
        line = (pooled["actual"] + pooled["market"]).abs().mean()
        rows.append(["pooled", len(pooled), "", f"{m0:.3f}", f"{m1:.3f}", f"{m1 - m0:+.3f}"])
        say(f"### Arm {ARM_NAME[arm]}")
        say()
        table(rows, ["season", "n", "k", "MAE without", "MAE with", "change"])
        s25 = next(s for season, k, s in per if season == 2025)
        d25 = (s25["actual"] - s25["margin"] - s25["pred"]).abs().mean() - (s25["actual"] - s25["margin"]).abs().mean()
        s1 = d25 <= -0.10 and (m1 - m0) <= -0.10
        s2 = better >= 5
        s3 = b1 <= b0
        res[arm] = {"gain": m0 - m1, "s1": s1, "s2": s2, "s3": s3}
        say(f"Brier (sigma {SIGMA}) {b0:.4f} -> {b1:.4f}. The line's own MAE on these games: {line:.3f}. "
            f"S1 (>= 0.10 better in 2025 and pooled): **{'yes' if s1 else 'no'}** (2025 {d25:+.3f}). "
            f"S2 (better in >= 5 of 7): **{'yes' if s2 else 'no'}** ({better}/7). "
            f"S3 (Brier not worse): **{'yes' if s3 else 'no'}**.")
        say()
    gu, gs = res["U"]["gain"], res["S"]["gain"]
    s4_scale = gu > 0 and gs >= 2 / 3 * gu
    say(f"**S4, what the gain is:** arm U pooled gain {gu:+.3f}, arm S {gs:+.3f}, arm I {res['I']['gain']:+.3f}. "
        f"Arm S carries >= 2/3 of arm U: **{'yes, a rating-regression finding (P22 / P5)' if s4_scale else 'no'}**.")
    say()
    return res, s4_scale


if __name__ == "__main__":
    say("# P39 — the QB-vs-rating term: edge first, then the sim anchor")
    say()
    say("Design and validation only. Tests, arms and pass rules as scoped in calibration-log.md (2026-09-22) "
        "before running.")
    say()
    pbp = {int(p.stem.split("_")[1]): pd.read_parquet(p) for p in sorted(Path(PBP_DIR).glob("pbp_*.parquet"))}
    sched = pd.read_parquet(SCHED)
    d, missing = build(pbp, sched)
    say(f"{len(d)} games 2016-2025 with a line, both ratings and both starters' terms ({missing} dropped for a "
        f"missing starter or team). Arm U = I + S exactly: max |U - I - S| = "
        f"{(d['tU'] - d['tI'] - d['tS']).abs().max():.2e}.")
    say()
    ok = gate0(d)
    wf = walk_forward(d)
    v1 = phase1(wf)
    v2, s4 = phase2(wf)
    say("## Verdict by the pre-set rules")
    say()
    say(f"- Gate 0: {'reproduced' if ok else 'not an exact rebuild (see gate 0)'}.")
    for arm in ARMS:
        r = v2[arm]
        say(f"- Arm {ARM_NAME[arm]}: phase 1 {'PASS' if v1[arm] else 'fail'}; phase 2 "
            f"{'PASS' if r['s1'] and r['s2'] and r['s3'] else 'fail'} (S1 {r['s1']}, S2 {r['s2']}, S3 {r['s3']}).")
    say(f"- S4: {'the gain is mostly scale (rating regression), not QB identity' if s4 else 'the gain is not mostly scale'}.")
    if OUT:
        OUT.write_text("\n".join(p37.lines) + "\n", encoding="utf-8")
        print(f"\nwrote {OUT}")
