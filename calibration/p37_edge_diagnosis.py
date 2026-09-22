"""P37: why do bigger baseline edges cover less often? Diagnosis only. Read-only.

    python calibration/p37_edge_diagnosis.py <pbp_dir> calibration/2026-09-21_p37_edge_diagnosis.md

The tests and decision rules were fixed in calibration-log.md (2026-09-21, "P37
scoped") before this ran. <pbp_dir> holds pbp_<season>.parquet for 2015-2026:
pass/run plays with season, week, season_type, posteam, defteam, epa. To build it:

    import nfl_data_py as nfl
    # game_id must be requested: the loader joins participation data on it.
    cols = ["game_id", "season", "week", "season_type", "posteam", "defteam", "epa", "play_type"]
    for y in range(2015, 2027):
        d = nfl.import_pbp_data([y], columns=cols, downcast=True, cache=False)
        d[d.play_type.isin(["pass", "run"]) & d.posteam.notna()][cols[1:]].to_parquet(f"{pbp_dir}/pbp_{y}.parquet")

Part A reads the graded 2026 baseline predictions from the configured store.
Part B replays the live Layer 1 (src/ingest_nflverse.compute_ratings) as of each
week of 2016-2025, adds the live HFA / rest / travel / wind terms, and grades
the resulting edge against the training file's line. It has no injury term:
the live injury layer has no leak-free historical equivalent.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from tabulate import tabulate

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import db, features as F  # noqa: E402
from src.ingest_nflverse import PLAYS_PER_GAME, PRIOR_PLAYS_WEIGHT, PRIOR_SEASON_REGRESSION  # noqa: E402

PBP = Path(sys.argv[1])
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else None
RNG = np.random.default_rng(37)
N_PERM = 10_000
THRESHOLDS = (0.0, 2.0, 3.0, 4.0, 6.0)
# The training file uses the old codes for relocated teams, pbp the current ones.
# Without this the replay silently drops those 79 games (found 2026-09-22).
CANON = {"OAK": "LV", "SD": "LAC", "STL": "LA"}
lines: list[str] = []


def say(text=""):
    print(text)
    lines.append(text)


def table(rows, headers):
    say(tabulate(rows, headers=headers, tablefmt="github"))
    say()


# --- statistics ------------------------------------------------------------

def ats_record(edge, resid):
    """(W, L, P) on the side the edge leaned; zero edge = away, as grade.evaluate."""
    took_home = edge > 0
    push = resid == 0
    win = (~push) & (took_home == (resid > 0))
    return int(win.sum()), int((~push & ~win).sum()), int(push.sum())


def fmt_rec(w, l, p):
    return f"{w}-{l}" + (f"-{p}" if p else "") + (f" ({w / (w + l) * 100:.0f}%)" if w + l else "")


def corr_ci(x, y):
    """Pearson r, Fisher 95% CI, two-sided p (normal approximation)."""
    n = len(x)
    if n < 4:
        return float("nan"), (float("nan"), float("nan")), float("nan")
    r = float(np.corrcoef(x, y)[0, 1])
    z, se = math.atanh(max(min(r, 0.999999), -0.999999)), 1 / math.sqrt(n - 3)
    p = math.erfc(abs(z) / se / math.sqrt(2))
    return r, (math.tanh(z - 1.96 * se), math.tanh(z + 1.96 * se)), p


def slope_ci(x, y):
    """OLS y = b x (no intercept), b with a 95% CI."""
    b = float((x * y).sum() / (x * x).sum())
    resid = y - b * x
    se = math.sqrt((resid ** 2).sum() / (len(x) - 1) / (x * x).sum())
    return b, (b - 1.96 * se, b + 1.96 * se)


def binom_le(k, n, p=0.5):
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))


def perm_p(stat_fn, edge, resid):
    """One- and two-sided permutation p for stat_fn(edge, resid) < 0."""
    obs = stat_fn(edge, resid)
    null = np.array([stat_fn(edge, RNG.permutation(resid)) for _ in range(N_PERM)])
    return obs, float((null <= obs).mean()), float((np.abs(null) >= abs(obs)).mean())


def lean_slope(edge, resid):
    """Slope of the lean-direction cover margin on |edge|."""
    x, y = np.abs(edge), np.sign(edge) * resid
    x = x - x.mean()
    return float((x * (y - y.mean())).sum() / (x * x).sum())


# --- part A: 2026 -----------------------------------------------------------

def comp(p):
    c = p.get("components")
    return json.loads(c) if isinstance(c, str) else (c or {})


def qb_out(details):
    return any(d.get("position") == "QB" and abs(d.get("points") or 0) >= 2.5 for d in details or [])


def load_2026():
    s = db.get_store()
    games = {g["game_id"]: g for g in s.select("games", {"sport": "nfl"})}
    rows = []
    for p in s.select("predictions", {"sport": "nfl"}):
        g = games.get(p["game_id"])
        if p["model_version"] != "baseline-v1" or not g or g.get("season") != 2026 or not g.get("completed"):
            continue
        if p.get("edge") is None or p.get("market_spread") is None:
            continue
        c = comp(p)
        l2 = c.get("layer2", {})
        wf = l2.get("wind_factor", 1) or 1
        rows.append({
            "game_id": p["game_id"], "week": g["week"], "home": g["home_team"], "away": g["away_team"],
            "edge": float(p["edge"]), "market": float(p["market_spread"]),
            "actual": g["home_points"] - g["away_points"], "flag": bool(p["is_value"]),
            "layer1": c.get("layer1_baseline_margin"), "hfa": l2.get("home_field", 0) or 0,
            "rest": l2.get("rest", 0) or 0, "travel": l2.get("travel", 0) or 0,
            "injury": l2.get("injury", 0) or 0, "wf": wf,
            "qb": qb_out(l2.get("home_injuries")) or qb_out(l2.get("away_injuries")),
        })
    d = pd.DataFrame(rows)
    d["resid"] = d["actual"] + d["market"]           # + => home covered
    d["inj_part"] = d["injury"] * d["wf"]
    d["rating_part"] = d["edge"] - d["inj_part"]     # Layer 1 + HFA/rest/travel - line
    return d


def part_a(d):
    say("## Part A — the 30 graded 2026 baseline picks")
    say()
    e, r = d["edge"].to_numpy(), d["resid"].to_numpy()

    say("### Test 1: significance")
    say()
    slope, p1, p2 = perm_p(lean_slope, e, r)
    rr, ci, rp = corr_ci(e, r)
    _, pc1, pc2 = perm_p(lambda a, b: float(np.corrcoef(a, b)[0, 1]), e, r)
    w4, l4, _ = ats_record(e[np.abs(e) >= 4], r[np.abs(e) >= 4])
    wa, la, _ = ats_record(e, r)
    table([
        ["slope of lean-direction cover margin on |edge|", f"{slope:+.2f} pts per pt of edge", f"{p1:.3f}", f"{p2:.3f}"],
        ["corr(edge, home cover residual)", f"{rr:+.3f} (95% CI {ci[0]:+.2f} to {ci[1]:+.2f})", f"{pc1:.3f}", f"{pc2:.3f}"],
    ], ["statistic", "value", "perm p (one-sided, < 0)", "perm p (two-sided)"])
    say(f"All picks {fmt_rec(wa, la, 0)}: binomial P(<= {wa} of {wa + la} | 50%) = {binom_le(wa, wa + la):.3f} "
        f"(one-sided), {min(1, 2 * binom_le(wa, wa + la)):.3f} two-sided.")
    say(f">= 4 pts {w4}-{l4}: binomial P(<= {w4} of {w4 + l4} | 50%) = {binom_le(w4, w4 + l4):.3f} "
        f"(one-sided). **Descriptive only**: the cut-off was chosen after seeing the data.")
    say()

    say("### Test 4: scale (2026)")
    say()
    b, bci = slope_ci(e, r)
    say(f"home cover residual = b x edge: **b = {b:+.2f}** (95% CI {bci[0]:+.2f} to {bci[1]:+.2f}). "
        f"b < 0 means the edge points the wrong way; 0 < b < 1 means right way, too large.")
    say(f"Mean |edge| 2026: {np.abs(e).mean():.2f} pts (median {np.median(np.abs(e)):.2f}).")
    say()

    say("### Test 3: decomposition (2026)")
    say()
    rows = []
    for name, col in (("full edge", "edge"), ("rating + situational (no injury)", "rating_part"),
                      ("injury term only", "inj_part")):
        x = d[col].to_numpy()
        cr, cci, _ = corr_ci(x, r)
        _, pp1, _ = perm_p(lambda a, b_: float(np.corrcoef(a, b_)[0, 1]), x, r) if x.std() > 0 else (0, float("nan"), 0)
        big = np.abs(x) >= 4
        rows.append([name, f"{x.std():.2f}", f"{cr:+.3f} ({cci[0]:+.2f} to {cci[1]:+.2f})", f"{pp1:.3f}",
                     fmt_rec(*ats_record(x, r)), fmt_rec(*ats_record(x[big], r[big]))])
    table(rows, ["part of the edge", "sd", "corr with cover residual (95% CI)", "perm p (< 0)",
                 "ATS leaning on it alone", "ATS where |part| >= 4"])

    say("### Test 5: concentration (exploratory, n too small to test)")
    say()
    lean_fav = (d["edge"] > 0) == (d["market"] < 0)
    lean_home = d["edge"] > 0
    splits = [
        ("leaned the favourite", lean_fav), ("leaned the underdog", ~lean_fav),
        ("leaned home", lean_home), ("leaned away", ~lean_home),
        ("|injury adj| >= 2", d["injury"].abs() >= 2), ("|injury adj| < 2", d["injury"].abs() < 2),
        ("a starting QB charged (>= 2.5 pts)", d["qb"]), ("no QB charge", ~d["qb"]),
        ("week 1", d["week"] == 1), ("week 2", d["week"] == 2),
    ]
    rows = []
    for name, m in splits:
        sub = d[m]
        big = sub[sub["edge"].abs() >= 4]
        rows.append([name, len(sub), fmt_rec(*ats_record(sub["edge"].to_numpy(), sub["resid"].to_numpy())),
                     fmt_rec(*ats_record(big["edge"].to_numpy(), big["resid"].to_numpy())) if len(big) else "—",
                     f"{sub['edge'].abs().mean():.1f}"])
    table(rows, ["split", "n", "ATS", "ATS at |edge| >= 4", "mean |edge|"])


# --- part B: replay ---------------------------------------------------------

def load_pbp():
    return {int(p.stem.split("_")[1]): pd.read_parquet(p) for p in sorted(PBP.glob("pbp_*.parquet"))}


def blend_parts(cur, pri, team):
    """The live _blend, returned as (current share, prior share) of the value."""
    cm = float(cur.loc[team, "mean"]) if team in cur.index else None
    cn = float(cur.loc[team, "count"]) if team in cur.index else 0.0
    pm = float(pri.loc[team, "mean"]) * PRIOR_SEASON_REGRESSION if team in pri.index else None
    if cm is None:
        return 0.0, (pm or 0.0)
    if pm is None:
        return cm, 0.0
    w = cn / (cn + PRIOR_PLAYS_WEIGHT)
    return w * cm, (1 - w) * pm


def ratings(season, week, pbp):
    """Per team: power rating split into prior/current x offence/defence, in points."""
    cur = pbp[season]
    cur = cur[(cur["season_type"] == "REG") & (cur["week"] < week)]
    pri = pbp[season - 1]
    off_c, def_c = cur.groupby("posteam")["epa"].agg(["mean", "count"]), cur.groupby("defteam")["epa"].agg(["mean", "count"])
    off_p, def_p = pri.groupby("posteam")["epa"].agg(["mean", "count"]), pri.groupby("defteam")["epa"].agg(["mean", "count"])
    out = {}
    for t in sorted(set(off_c.index) | set(off_p.index)):
        oc, op = blend_parts(off_c, off_p, t)
        dc, dp = blend_parts(def_c, def_p, t)
        out[t] = {"cur_off": oc * PLAYS_PER_GAME, "pri_off": op * PLAYS_PER_GAME,
                  "cur_def": -dc * PLAYS_PER_GAME, "pri_def": -dp * PLAYS_PER_GAME}
    return out


def situational(row):
    hfa = 0.0 if row["is_neutral"] else F.HOME_FIELD_POINTS["nfl"]
    rest = max(-F.REST_CAP_POINTS, min(F.REST_CAP_POINTS, row["rest_diff"] * F.REST_POINTS_PER_DAY))
    away_mi, home_mi = row["travel_away"], row["travel_away"] - row["travel_diff"]
    pen = lambda mi: min(F.TRAVEL_CAP_POINTS, max(mi, 0) / 1000.0 * F.TRAVEL_POINTS_PER_1000MI)  # noqa: E731
    wind = row["wind"] or 0.0
    wf = 1.0 - min(F.WIND_COMPRESSION_CAP, (wind - F.WIND_THRESHOLD_MPH) * F.WIND_COMPRESSION_PER_MPH) \
        if wind > F.WIND_THRESHOLD_MPH else 1.0
    return hfa + rest + pen(away_mi) - pen(home_mi), wf


def replay(pbp):
    train = pd.read_csv(Path(__file__).resolve().parents[1] / "data" / "training_nfl.csv")
    train = train[(train["season"] >= 2016) & (train["week"] <= 18) & train["market_spread"].notna()]
    cache, rows = {}, []
    for _, g in train.iterrows():
        key = (int(g["season"]), int(g["week"]))
        if key not in cache:
            cache[key] = ratings(*key, pbp)
        rt = cache[key]
        h, a = rt.get(CANON.get(g["home_team"], g["home_team"])), rt.get(CANON.get(g["away_team"], g["away_team"]))
        if not h or not a:
            continue
        parts = {k: h[k] - a[k] for k in h}
        sit, wf = situational(g)
        margin = (sum(parts.values()) + sit) * wf
        rows.append({"season": key[0], "week": key[1], "edge": margin + g["market_spread"],
                     "resid": g["target_margin"] + g["market_spread"], "sit": sit * wf,
                     **{k: v * wf for k, v in parts.items()}})
    return pd.DataFrame(rows)


def part_b(rp, d26, pbp):
    say("## Part B — the live Layer 1 replayed, 2016-2025 (no injury term)")
    say()
    say(f"{len(rp)} regular-season games with a line. Each week's ratings use only that season's earlier weeks "
        f"plus the previous season, exactly as the live `compute_ratings` does.")
    say()

    # Does the replay reproduce the live Layer 1? (2026 weeks 1-2)
    chk = []
    for wk in (1, 2):
        rt = ratings(2026, wk, pbp)
        for _, g in d26[d26["week"] == wk].iterrows():
            if g["home"] in rt and g["away"] in rt and g["layer1"] is not None:
                chk.append(sum(rt[g["home"]].values()) - sum(rt[g["away"]].values()) - g["layer1"])
    chk = np.array(chk)
    say(f"Replay vs stored live Layer 1 on 2026 weeks 1-2: n = {len(chk)}, median |diff| {np.median(np.abs(chk)):.2f} pts, "
        f"max {np.abs(chk).max():.2f}.")
    say()

    say("### Test 2: ATS by |edge| and corr(edge, cover residual), by part of the season")
    say()
    groups = [("weeks 1-2", rp["week"] <= 2), ("weeks 1-4", rp["week"] <= 4), ("weeks 5-18", rp["week"] >= 5),
              ("all weeks", rp["week"] > 0)]
    rows = []
    for name, m in groups:
        s = rp[m]
        e, r = s["edge"].to_numpy(), s["resid"].to_numpy()
        cr, ci, cp = corr_ci(e, r)
        recs = []
        for t in THRESHOLDS:
            k = np.abs(e) >= t
            recs.append(fmt_rec(*ats_record(e[k], r[k])))
        b, bci = slope_ci(e, r)
        rows.append([name, len(s), f"{np.abs(e).mean():.2f}", *recs, f"{cr:+.3f} ({ci[0]:+.2f}, {ci[1]:+.2f}) p={cp:.3f}",
                     f"{b:+.2f} ({bci[0]:+.2f}, {bci[1]:+.2f})"])
    table(rows, ["games", "n", "mean |edge|", *[f">= {t:g}" for t in THRESHOLDS], "corr (95% CI)", "b (95% CI)"])

    say("### Test 3 on the replay: which part of the edge carries the sign? (weeks 1-4)")
    say()
    s = rp[rp["week"] <= 4]
    cols = ["pri_off", "pri_def", "cur_off", "cur_def", "sit"]
    X = np.column_stack([s[c] for c in cols] + [np.ones(len(s))])
    y = s["resid"].to_numpy()
    # resid = sum(beta_k * part_k) - (-market) ... the market enters the residual, so regress the
    # residual on each part: beta_k = 0 means the part adds nothing beyond the line, < 0 wrong way.
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ beta
    cov = np.linalg.inv(X.T @ X) * (res @ res) / (len(y) - X.shape[1])
    se = np.sqrt(np.diag(cov))
    rows = []
    for i, c in enumerate(cols):
        rows.append([c, f"{s[c].std():.2f}", f"{beta[i]:+.3f}", f"({beta[i] - 1.96 * se[i]:+.3f}, {beta[i] + 1.96 * se[i]:+.3f})"])
    table(rows, ["part (points, home minus away)", "sd", "coef on cover residual", "95% CI"])
    say("A positive coefficient means that part of the rating knows something the line does not; zero means the "
        "line already has it; negative means leaning on it loses. All five parts enter the edge with weight 1.")
    say()

    say("### Edge size: 2026 against the replay")
    say()
    e26 = d26["edge"].abs()
    early = rp[rp["week"] <= 2]["edge"].abs()
    say(f"Mean |edge|: 2026 weeks 1-2 **{e26.mean():.2f}** (with the injury term), "
        f"{d26['rating_part'].abs().mean():.2f} without it; replayed weeks 1-2 {early.mean():.2f}. "
        f"Share of picks at |edge| >= 4: 2026 {(e26 >= 4).mean() * 100:.0f}%, replay {(early >= 4).mean() * 100:.0f}%.")
    say()

    say("### Post-hoc (not in the scoped plan): home vs away leans, and the home-field term")
    say()
    rows = []
    for name, m in (("weeks 1-4", rp["week"] <= 4), ("all weeks", rp["week"] > 0)):
        s = rp[m]
        home = s["edge"] > 0
        rows.append([name, fmt_rec(*ats_record(s[home]["edge"].to_numpy(), s[home]["resid"].to_numpy())),
                     fmt_rec(*ats_record(s[~home]["edge"].to_numpy(), s[~home]["resid"].to_numpy())),
                     f"{s['resid'].mean():+.2f}"])
    table(rows, ["games", "ATS leaning home", "ATS leaning away", "mean home cover residual (pts)"])
    say("Added after seeing Test 3's situational coefficient; read as a lead, not a result.")
    say()

    say("### Per-season corr(edge, cover residual), weeks 1-4")
    say()
    rows = []
    for yr, s in rp[rp["week"] <= 4].groupby("season"):
        cr, _, _ = corr_ci(s["edge"].to_numpy(), s["resid"].to_numpy())
        rows.append([yr, len(s), f"{cr:+.3f}", fmt_rec(*ats_record(s["edge"].to_numpy(), s["resid"].to_numpy()))])
    table(rows, ["season", "n", "corr", "ATS"])


if __name__ == "__main__":
    say("# P37 — why bigger baseline edges cover less often (diagnosis only)")
    say()
    d26 = load_2026()
    part_a(d26)
    pbp = load_pbp()
    rp = replay(pbp)
    part_b(rp, d26, pbp)
    if OUT:
        OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\nwrote {OUT}")
