"""P37 part 2: why are 2026's baseline edges bigger, and is the market ahead of them?
Diagnosis only. Read-only.

    python calibration/p37b_edge_size_market.py <pbp_dir> calibration/2026-09-22_p37b_edge_size_market.md

The tests and decision rules were fixed in calibration-log.md (2026-09-22, "P37
part 2 scoped") before this ran. <pbp_dir> is part 1's directory (see
p37_edge_diagnosis.py; note the pull needs "game_id" in its columns) plus
schedules.parquet from nfl.import_schedules(range(2015, 2027)).

The replay reuses part 1's ratings() and situational() unchanged, so the edges
here are the same exact rebuild of the live Layer 1, now carrying team names.
"""
import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PBP_DIR = sys.argv[1]
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else None

# Load part 1 as a module; it reads its pbp dir from argv at import.
_argv, sys.argv = sys.argv, [str(HERE / "p37_edge_diagnosis.py"), PBP_DIR]
_spec = importlib.util.spec_from_file_location("p37", HERE / "p37_edge_diagnosis.py")
p37 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p37)
sys.argv = _argv

say, table, fmt_rec, ats_record, corr_ci, binom_le = (p37.say, p37.table, p37.fmt_rec, p37.ats_record,
                                                      p37.corr_ci, p37.binom_le)
RNG = np.random.default_rng(3702)
N_PERM = 10_000
CANON = {"OAK": "LV", "SD": "LAC", "STL": "LA"}   # schedules use the old codes; pbp the current ones
canon = lambda t: CANON.get(t, t)  # noqa: E731


def rec(e, r):
    return fmt_rec(*ats_record(np.asarray(e), np.asarray(r)))


def binom_ge(k, n, p=0.5):
    return 1 - binom_le(k - 1, n, p) if k > 0 else 1.0


# --- data ------------------------------------------------------------------

def replay(pbp):
    """Part 1's replay loop, keeping game identity."""
    train = pd.read_csv(HERE.parent / "data" / "training_nfl.csv")
    train = train[(train["season"] >= 2016) & (train["week"] <= 18) & train["market_spread"].notna()]
    cache, rows = {}, []
    for _, g in train.iterrows():
        key = (int(g["season"]), int(g["week"]))
        if key not in cache:
            cache[key] = p37.ratings(*key, pbp)
        rt = cache[key]
        home, away = canon(g["home_team"]), canon(g["away_team"])
        h, a = rt.get(home), rt.get(away)
        if not h or not a:
            continue
        parts = {k: (h[k] - a[k]) for k in h}
        sit, wf = p37.situational(g)
        margin = (sum(parts.values()) + sit) * wf
        rows.append({"game_id": g["game_id"], "season": key[0], "week": key[1], "home": home, "away": away,
                     "edge": margin + g["market_spread"], "resid": g["target_margin"] + g["market_spread"],
                     "cur": (parts["cur_off"] + parts["cur_def"]) * wf})
    rp = pd.DataFrame(rows)
    rp["prior_gap"] = rp["edge"] - rp["cur"]          # the edge if only last season's form counted
    return rp


def qb_changes(sched):
    """{(season, team): True if the week-1 starter is not last season's most frequent starter}."""
    s = sched[sched["game_type"] == "REG"].copy()
    long = pd.concat([
        s[["season", "week", "home_team", "home_qb_id"]].set_axis(["season", "week", "team", "qb"], axis=1),
        s[["season", "week", "away_team", "away_qb_id"]].set_axis(["season", "week", "team", "qb"], axis=1),
    ])
    long["team"] = long["team"].map(canon)
    long = long.dropna(subset=["qb"])
    usual = long.groupby(["season", "team"])["qb"].agg(lambda q: q.value_counts().index[0]).to_dict()
    first = long.sort_values("week").groupby(["season", "team"])["qb"].first().to_dict()
    return {(y, t): qb != usual.get((y - 1, t)) for (y, t), qb in first.items() if (y - 1, t) in usual}


def load_2026(pbp, sched):
    d = p37.load_2026()
    s26 = sched[(sched["season"] == 2026) & (sched["game_type"] == "REG")].set_index("game_id")
    cur = []
    for _, g in d.iterrows():
        rt = p37.ratings(2026, int(g["week"]), pbp)
        h, a = rt[g["home"]], rt[g["away"]]
        cur.append((h["cur_off"] + h["cur_def"] - a["cur_off"] - a["cur_def"]) * g["wf"])
    d["cur"] = cur
    d["noinj"] = d["rating_part"]                    # the live edge without the injury term, at the stored line
    d["prior_gap"] = d["noinj"] - d["cur"]
    close = -s26.reindex(d["game_id"])["spread_line"].to_numpy()   # home-spread convention
    d["close_nfl"] = close
    d["noinj_close"] = d["noinj"] - d["market"] + close           # same margin, against nflverse's close
    return d


def load_clv():
    from src import db
    rows = [r for r in db.get_store().select("clv_log")
            if r.get("sport") == "nfl" and r.get("model_version") == "baseline-v1" and r.get("clv_pp") is not None]
    return pd.DataFrame(rows)


# --- tests -----------------------------------------------------------------

def test1(rp, d):
    say("### Test 1: edge size by season, weeks 1-2")
    say()
    say("The live edge without its injury term, and the same edge counting last season's form only "
        "(the gap between the line and a 2025-only rating). 2026 is shown against both the stored line it "
        "was graded on and nflverse's close, which is the line the replay uses.")
    say()
    early = rp[rp["week"] <= 2]
    rows = []
    for yr, s in early.groupby("season"):
        rows.append([yr, len(s), f"{s['edge'].abs().mean():.2f}", f"{(s['edge'].abs() >= 4).mean() * 100:.0f}%",
                     f"{s['prior_gap'].abs().mean():.2f}"])
    rows.append(["2026 (stored line)", len(d), f"{d['noinj'].abs().mean():.2f}",
                 f"{(d['noinj'].abs() >= 4).mean() * 100:.0f}%", f"{d['prior_gap'].abs().mean():.2f}"])
    pg_close = d["prior_gap"] - d["market"] + d["close_nfl"]
    rows.append(["2026 (nflverse close)", len(d), f"{d['noinj_close'].abs().mean():.2f}",
                 f"{(d['noinj_close'].abs() >= 4).mean() * 100:.0f}%", f"{pg_close.abs().mean():.2f}"])
    table(rows, ["season", "n", "mean |edge|", "share >= 4", "mean |prior-only gap|"])
    by_season = early.groupby("season")["edge"].apply(lambda e: e.abs().mean())
    m26 = d["noinj"].abs().mean()
    top = bool(m26 > by_season.max())
    say(f"2026's mean |edge| (stored line, no injury term) {m26:.2f} against the replay's highest season "
        f"{by_season.max():.2f} ({by_season.idxmax()}): **{'above all ten' if top else 'not above all ten'}**.")
    say()
    return top


def test2(rp, d, qbc):
    say("### Test 2: QB change since last season")
    say()
    say("A team has changed QB when its week-1 starter is not its most frequent starter the season before "
        "(nflverse schedules).")
    say()
    rp = rp.copy()
    rp["qbc"] = [qbc.get((y, h), False) or qbc.get((y, a), False)
                 for y, h, a in zip(rp["season"], rp["home"], rp["away"])]
    s = rp[rp["week"] <= 4]
    yes, no = s[s["qbc"]], s[~s["qbc"]]
    wy, ly, _ = ats_record(yes["edge"].to_numpy(), yes["resid"].to_numpy())
    wn, ln, _ = ats_record(no["edge"].to_numpy(), no["resid"].to_numpy())
    p_a = binom_le(wy, wy + ly)
    table([["either team changed QB", len(yes), rec(yes["edge"], yes["resid"]), f"{p_a:.3f}"],
           ["neither changed", len(no), rec(no["edge"], no["resid"]), f"{binom_le(wn, wn + ln):.3f}"]],
          ["replay, weeks 1-4", "n", "ATS on the lean", "binomial p (one-sided, < 50%)"])
    part_a = p_a < 0.05

    say("Share of |edge| >= 4 picks in QB-change games, weeks 1-2:")
    say()
    rows, shares = [], {}
    for yr, g in rp[rp["week"] <= 2].groupby("season"):
        big = g[g["edge"].abs() >= 4]
        shares[yr] = big["qbc"].mean() if len(big) else float("nan")
        rows.append([yr, len(big), f"{shares[yr] * 100:.0f}%", f"{g['qbc'].mean() * 100:.0f}%"])
    d = d.copy()
    d["qbc"] = [qbc.get((2026, h), False) or qbc.get((2026, a), False) for h, a in zip(d["home"], d["away"])]
    big26 = d[d["edge"].abs() >= 4]
    s26 = big26["qbc"].mean()
    rows.append(["2026", len(big26), f"{s26 * 100:.0f}%", f"{d['qbc'].mean() * 100:.0f}%"])
    table(rows, ["season", "picks at |edge| >= 4", "share in QB-change games", "share of all games"])
    part_b = bool(s26 > max(shares.values()))
    say(f"(a) QB-change leans below 50% at p < 0.05 in the replay: **{'yes' if part_a else 'no'}** (p {p_a:.3f}). "
        f"(b) 2026's big-edge share above every replay season: **{'yes' if part_b else 'no'}** "
        f"({s26 * 100:.0f}% vs max {max(shares.values()) * 100:.0f}%).")
    say()
    say("2026 by QB change (descriptive, n small):")
    say()
    table([[name, int(m.sum()), rec(d[m]["edge"], d[m]["resid"]), f"{d[m]['edge'].abs().mean():.2f}"]
           for name, m in (("QB-change game", d["qbc"]), ("no change", ~d["qbc"]))],
          ["2026", "n", "ATS", "mean |edge|"])
    return part_a and part_b


def test3(d, clv):
    say("### Test 3: closing line value on the 2026 leans")
    say()
    c = clv.merge(d[["game_id", "edge", "actual"]], on="game_id")
    x, e = c["clv_pp"].to_numpy(), c["edge"].abs().to_numpy()
    mean = x.mean()
    null = np.array([(x * RNG.choice([-1, 1], len(x))).mean() for _ in range(N_PERM)])
    p_mean = float((null <= mean).mean())
    r = float(np.corrcoef(e, x)[0, 1])
    null_r = np.array([np.corrcoef(e, RNG.permutation(x))[0, 1] for _ in range(N_PERM)])
    p_r = float((null_r <= r).mean())
    moved_toward = int((x > 0.001).sum()); moved_away = int((x < -0.001).sum())
    table([["mean CLV on the lean (pp of cover probability)", f"{mean * 100:+.2f}", f"{p_mean:.3f}"],
           ["corr(|edge|, CLV)", f"{r:+.3f}", f"{p_r:.3f}"]],
          ["statistic", "value", "perm p (one-sided, < 0)"])
    say(f"n = {len(c)}; the line moved toward the lean in {moved_toward}, away in {moved_away}, "
        f"about unchanged in {len(c) - moved_toward - moved_away}. Basis: "
        f"{', '.join(f'{k} {v}' for k, v in c['clv_basis'].value_counts().items())}.")
    say()
    big = c[c["edge"].abs() >= 4]
    say(f"Mean CLV at |edge| >= 4: {big['clv_pp'].mean() * 100:+.2f} pp (n {len(big)}); "
        f"below 4: {c[c['edge'].abs() < 4]['clv_pp'].mean() * 100:+.2f} pp.")
    say()
    close_resid = c["actual"] + c["close_line"].astype(float)
    stored = d.set_index("game_id").loc[c["game_id"]]
    say(f"Descriptive: graded at the logged close instead of the stored line, the same {len(c)} leans go "
        f"{rec(c['edge'], close_resid)} (stored line: {rec(stored['edge'], stored['resid'])}).")
    say()
    h2 = mean < 0 and p_mean < 0.05 and r < 0 and p_r < 0.05
    general = mean < 0 and p_mean < 0.05
    return h2, general


def test4(rp, d):
    say("### Test 4: how accurate were the lines? Weeks 1-2")
    say()
    rows = []
    maes = {}
    for yr, s in rp[rp["week"] <= 2].groupby("season"):
        maes[yr] = s["resid"].abs().mean()
        rows.append([yr, len(s), f"{maes[yr]:.2f}"])
    close26 = (d["actual"] + d["close_nfl"]).abs().mean()
    rows.append(["2026 (nflverse close)", len(d), f"{close26:.2f}"])
    rows.append(["2026 (stored line)", len(d), f"{d['resid'].abs().mean():.2f}"])
    table(rows, ["season", "n", "line MAE vs final margin (pts)"])
    sharp = close26 < min(maes.values())
    rank = 1 + sum(v < close26 for v in maes.values())
    say(f"2026's closing MAE ranks {rank} of 11 (1 = most accurate). "
        f"Below all ten: **{'yes' if sharp else 'no'}**. Descriptive only at n = {len(d)}.")
    say()
    return sharp


def test5(rp, d):
    say("### Test 5: how unusual is 9-20? (noise reference)")
    say()
    w, l, p = ats_record(d["edge"].to_numpy(), d["resid"].to_numpy())
    say(f"2026 leans {fmt_rec(w, l, p)}: binomial p {min(1, 2 * binom_le(w, w + l)):.3f} two-sided at 50%.")
    say()
    rows = []
    for yr, s in rp[rp["week"] <= 2].groupby("season"):
        rows.append([yr, rec(s["edge"], s["resid"])])
    table(rows, ["replay season", "weeks 1-2 ATS"])


if __name__ == "__main__":
    say("# P37 part 2 — why 2026's baseline edges are bigger, and whether the market is ahead of them")
    say()
    say("Diagnosis only. Tests and rules as scoped in calibration-log.md (2026-09-22) before running.")
    say()
    pbp = p37.load_pbp()
    sched = pd.read_parquet(Path(PBP_DIR) / "schedules.parquet")
    rp = replay(pbp)
    d = load_2026(pbp, sched)
    say(f"Replay: {len(rp)} games, 2016-2025. 2026: {len(d)} graded baseline picks.")
    say()
    h1_size = test1(rp, d)
    h1_qb = test2(rp, d, qb_changes(sched))
    h2, general = test3(d, load_clv())
    sharp = test4(rp, d)
    test5(rp, d)
    say("## Verdict by the pre-set rules")
    say()
    say(f"- **H1, 2026 rating miscalibration:** {'met' if h1_size and h1_qb else 'not met'} "
        f"(size above all ten: {'yes' if h1_size else 'no'}; QB-change test: {'yes' if h1_qb else 'no'}).")
    say(f"- **H2, market ahead and more so on big edges:** {'met' if h2 else 'not met'}"
        f"{'; the market is ahead in general (mean CLV < 0), with no effect by edge size' if general and not h2 else ''}.")
    say(f"- **H2b, sharper line:** {'below all ten seasons' if sharp else 'no'} (descriptive).")
    say(f"- **H3, noise:** {'stands' if not (h2 or (h1_size and h1_qb)) else 'displaced'}.")
    if OUT:
        OUT.write_text("\n".join(p37.lines) + "\n", encoding="utf-8")
        print(f"\nwrote {OUT}")
