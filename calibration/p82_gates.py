"""P82 replacement-starter credit: gates G1-G7. Walk-forward, read-only.

Design and gates: calibration-log 2026-11-15 (G1-G6) and 2026-11-19 (test design, G7).

    python calibration/p82_gates.py > calibration/2026-11-19_p82_gates.txt
"""
from __future__ import annotations

import collections
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import db  # noqa: E402
from src.build_training import _nfl_injury_features  # noqa: E402
from src.features import INJURY_POINTS_SCALE  # noqa: E402

spec = importlib.util.spec_from_file_location("p22", ROOT / "research/p22/p22_phase1.py")
p22 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p22)

ARM = {"adj": True, "filt": False, "lam": 300, "r_off": 0.459, "r_def": 0.394}   # live P22 rating (A+B)
KS = (100, 250, 500, 1000)
POOLS = (200, 300, 500)
SCALE = INJURY_POINTS_SCALE["nfl"]
CANON = p22.CANON
RNG = np.random.default_rng(82)
N_BOOT = 10_000
canon = lambda t: CANON.get(t, t)  # noqa: E731


def load_dropbacks() -> pd.DataFrame:
    frames = []
    cols = ["game_id", "season", "season_type", "week", "posteam", "defteam", "epa", "qb_dropback",
            "passer_player_id", "rusher_player_id"]
    for y in range(2015, 2026):
        d = pd.read_parquet(ROOT / f"data/cache/sim_pbp_{y}.parquet")
        if "play_id" in d.columns:
            d = d.sort_values(["game_id", "play_id"])
        d = d[d.qb_dropback == 1][cols]
        frames.append(d)
    c = pd.read_parquet(ROOT / "data/cache/p82_dropbacks_2024_2026.parquet")
    if "play_id" in c.columns:
        c = c.sort_values(["game_id", "play_id"])
    c = c[c.season == 2026]
    frames.append(c[[x for x in cols if x in c.columns]].assign(qb_dropback=1))
    d = pd.concat(frames, ignore_index=True)
    d["qb"] = d.passer_player_id.fillna(d.rusher_player_id)
    d = d.dropna(subset=["qb", "epa", "posteam", "defteam"])
    d["posteam"] = d.posteam.map(canon)
    d["defteam"] = d.defteam.map(canon)
    d["season"] = d.season.astype(int)
    d["week"] = d.week.astype(int)
    d["seq"] = np.arange(len(d))
    return d


DB = load_dropbacks()
REG = DB[DB.season_type == "REG"]
_win: dict = {}


def window(season: int, week: int):
    """Per-QB (n, mean opponent-adjusted EPA/db) and replacement level per pool, from data before the game."""
    key = (season, week)
    if key in _win:
        return _win[key]
    w = DB[(DB.season == season - 1) | ((DB.season == season) & (DB.season_type == "REG") & (DB.week < week))]
    lg = w.groupby("season").epa.mean()
    dfa = w.groupby(["season", "defteam"]).epa.mean()
    adj_def = dfa - lg.reindex(dfa.index.get_level_values(0)).to_numpy()
    adj = w.epa.to_numpy() - adj_def.reindex(pd.MultiIndex.from_arrays([w.season, w.defteam])).to_numpy()
    w = w.assign(adj=adj)
    per = w.groupby("qb").adj.agg(["size", "mean"])
    repl = {}
    for p in POOLS:
        ids = per.index[per["size"] < p]
        pool = w[w.qb.isin(ids)]
        repl[p] = float(pool.adj.mean()) if len(pool) else float(w.adj.mean())
    prev = REG[REG.season == season - 1]
    dbpg = len(prev) / max(1, prev.groupby(["game_id", "posteam"]).ngroups)
    _win[key] = (per, repl, dbpg)
    return _win[key]


def leaders_and_starters():
    """{(season, week, team): (leader, starter)} for regular-season games."""
    out = {}
    first = REG.sort_values("seq").groupby(["game_id", "posteam"]).qb.first()
    counts = REG.groupby(["season", "week", "posteam", "qb"]).size().reset_index(name="n")
    season_leader = (REG.groupby(["season", "posteam", "qb"]).size().reset_index(name="n")
                     .sort_values("n").groupby(["season", "posteam"]).qb.last().to_dict())
    for (season, team), grp in counts.groupby(["season", "posteam"]):
        grp = grp.sort_values("week")
        run: collections.Counter = collections.Counter()
        for wk in sorted(grp.week.unique()):
            leader = max(run, key=run.get) if run else season_leader.get((season - 1, team))
            out[(season, int(wk), team)] = leader
            for r in grp[grp.week == wk].itertuples():
                run[r.qb] += r.n
    games = REG.drop_duplicates(["game_id", "posteam"])[["game_id", "season", "week", "posteam"]]
    res = {}
    for r in games.itertuples():
        res[(r.game_id, r.posteam)] = (out.get((r.season, r.week, r.posteam)), first.get((r.game_id, r.posteam)))
    return res


def credit(season, week, qb, charge, k, pool):
    if not charge or qb is None:
        return 0.0
    per, repl, dbpg = window(season, week)
    n, m = (per.loc[qb, "size"], per.loc[qb, "mean"]) if qb in per.index else (0, 0.0)
    shrunk = (n * m + k * repl[pool]) / (n + k)
    return float(min(max((shrunk - repl[pool]) * dbpg, 0.0), charge))


def boot_ci(x):
    x = np.asarray(x, dtype=float)
    if len(x) == 0:
        return (float("nan"),) * 3
    idx = RNG.integers(0, len(x), (N_BOOT, len(x)))
    means = x[idx].mean(axis=1)
    return float(x.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def ats_win(margin, actual, spread):
    edge, resid = margin + spread, actual + spread
    if resid == 0 or edge == 0:
        return None
    return 1.0 if (edge > 0) == (resid > 0) else 0.0


def main():
    pbp, totals, league_ppg = p22.load()
    games = pd.read_csv(ROOT / "data/training_nfl.csv")
    games = games[(games.season >= 2016) & (games.season <= 2025) & (games.week <= 18) & games.market_spread.notna()]
    r = p22.evaluate(pbp, games, totals, league_ppg, ARM)
    g = games.merge(r[["game_id", "margin"]], on="game_id")
    inj = _nfl_injury_features(list(range(2016, 2026)))
    ls = leaders_and_starters()

    rows = []
    for x in g.itertuples():
        home, away = canon(x.home_team), canon(x.away_team)
        rec = {"game_id": x.game_id, "season": int(x.season), "week": int(x.week), "actual": x.target_margin,
               "spread": x.market_spread, "flat": x.margin + x.injury_diff}
        for side, team, raw in (("h", home, x.home_team), ("a", away, x.away_team)):
            leader, starter = ls.get((x.game_id, team), (None, None))
            _, qb_loss = inj.get((int(x.season), int(x.week), raw), inj.get((int(x.season), int(x.week), team), (0.0, 0.0)))
            rec[f"{side}_leader"], rec[f"{side}_starter"] = leader, starter
            rec[f"{side}_backup"] = bool(leader and starter and leader != starter)
            rec[f"{side}_charge"] = SCALE * qb_loss if rec[f"{side}_backup"] else 0.0
        rows.append(rec)
    d = pd.DataFrame(rows)
    d["backup"] = d.h_backup | d.a_backup
    bq = d[d.backup].copy()
    print(f"games 2016-2025 with a line and a rating: {len(d)}; backup-QB games: {len(bq)}; "
          f"with a starter-absence charge on the backup's team: {int(((bq.h_charge > 0) | (bq.a_charge > 0)).sum())}")
    print(f"G1 (n >= 150 backup-QB games): {'PASS' if len(bq) >= 150 else 'FAIL'} (n = {len(bq)})")
    print(f"flat-charge baseline MAE, all games {np.abs(d.flat - d.actual).mean():.3f}; backup-QB games {np.abs(bq.flat - bq.actual).mean():.3f}")

    def p82(frame, k, pool):
        ch = np.array([credit(x.season, x.week, x.h_starter, x.h_charge, k, pool) for x in frame.itertuples()])
        ca = np.array([credit(x.season, x.week, x.a_starter, x.a_charge, k, pool) for x in frame.itertuples()])
        return frame.flat.to_numpy() + ch - ca, ch, ca

    train = bq[bq.season <= 2021]
    test = bq[bq.season >= 2022]
    print("\nG6 grid on 2016-21 backup-QB games (MAE; flat = "
          f"{np.abs(train.flat - train.actual).mean():.4f}, n = {len(train)}):")
    best = None
    for k in KS:
        for pool in POOLS:
            m, _, _ = p82(train, k, pool)
            mae = float(np.abs(m - train.actual).mean())
            print(f"  k={k:<5} pool<{pool:<4} MAE {mae:.4f}")
            if best is None or mae < best[0]:
                best = (mae, k, pool)
    _, k, pool = best
    print(f"frozen cell: k = {k}, replacement pool < {pool} dropbacks")

    def report(frame, label):
        m, ch, ca = p82(frame, k, pool)
        e0 = np.abs(frame.flat - frame.actual).to_numpy()
        e1 = np.abs(m - frame.actual.to_numpy())
        diff = e1 - e0                                           # negative = P82 better
        mean, lo, hi = boot_ci(diff)
        nz = (ch + ca) > 0
        print(f"{label}: n {len(frame)} | MAE flat {e0.mean():.3f} -> P82 {e1.mean():.3f} | diff {mean:+.4f} "
              f"(95% CI {lo:+.4f} to {hi:+.4f}) | credit non-zero in {int(nz.sum())} games"
              + (f", there: {e0[nz].mean():.3f} -> {e1[nz].mean():.3f} (diff {diff[nz].mean():+.4f}, mean credit {(ch + ca)[nz].mean():.2f})" if nz.any() else ""))
        a0 = [ats_win(a, b, c) for a, b, c in zip(frame.flat, frame.actual, frame.spread)]
        a1 = [ats_win(a, b, c) for a, b, c in zip(m, frame.actual, frame.spread)]
        pairs = [(u, v) for u, v in zip(a0, a1) if u is not None and v is not None]
        if pairs:
            u = np.array([p[0] for p in pairs])
            v = np.array([p[1] for p in pairs])
            dm, dlo, dhi = boot_ci(v - u)
            print(f"    ATS flat {int(u.sum())}-{int(len(u) - u.sum())} ({u.mean():.3f}) -> P82 {int(v.sum())}-{int(len(v) - v.sum())} "
                  f"({v.mean():.3f}); diff {dm:+.4f} (95% CI {dlo:+.4f} to {dhi:+.4f}); picks changed {int((u != v).sum())}")
            return (mean, lo, hi), (dm, dlo, dhi), diff
        return (mean, lo, hi), None, diff

    print()
    g2, g3, _ = report(test, "G2/G3, 2022-2025 (out of sample)")
    print(f"G2 (MAE improves, CI excludes 0): {'PASS' if g2[2] < 0 else 'FAIL'}")
    print(f"G3 (ATS not worse: diff CI includes or exceeds 0): {'PASS' if g3 and g3[2] >= 0 else 'FAIL'}")
    report(bq, "reported, all ten seasons")
    report(train, "reported, 2016-2021 (in sample for the cell)")
    wins = 0
    print("G4 by season (frozen cell):")
    for s in range(2016, 2026):
        f = bq[bq.season == s]
        m, _, _ = p82(f, k, pool)
        dd = float((np.abs(m - f.actual) - np.abs(f.flat - f.actual)).mean())
        wins += dd < 0
        print(f"  {s}: n {len(f):>3} MAE diff {dd:+.4f} {'improves' if dd < 0 else 'no improvement'}")
    print(f"G4 (sign in >= 6 of 10 seasons): {'PASS' if wins >= 6 else 'FAIL'} ({wins}/10)")
    non = d[~d.backup]
    m, ch, ca = p82(non, k, pool)
    print(f"G5 (no-QB-change games identical): {'PASS' if np.array_equal(m, non.flat.to_numpy()) else 'FAIL'} "
          f"({len(non)} games, max |change| {np.abs(m - non.flat).max():.6f})")

    # ---- G7: 2026 weeks 1-10, served headline ---------------------------------------------
    print("\nG7, 2026 weeks 1-10 (served baseline headline vs headline + credit; frozen cell):")
    store = db.get_store()
    g26 = {x["game_id"]: x for x in store.select("games", {"sport": "nfl", "season": 2026})
           if x.get("completed") and int(x["week"]) <= 10}
    preds = {p["game_id"]: p for p in store.select("predictions", {"sport": "nfl"})
             if p["model_version"] == "baseline-v1" and p["game_id"] in g26}
    names = pd.read_parquet(ROOT / "data/cache/p82_dropbacks_2024_2026.parquet", columns=["passer_player_id", "passer_player_name"]).dropna()
    short = names.groupby("passer_player_id").passer_player_name.agg(lambda s: s.mode().iat[0]).to_dict()

    def same(player_full: str, qb_id) -> bool:
        s = short.get(qb_id)
        if not s or not player_full:
            return False
        first, last = player_full.split()[0], player_full.split()[1] if len(player_full.split()) > 1 else ""
        return s.split(".")[0][:1].lower() == first[:1].lower() and s.split(".")[-1].lower().startswith(last.lower()[:5])

    out = []
    for gid, p in sorted(preds.items()):
        x = g26[gid]
        wk = int(x["week"])
        c = p["components"] if isinstance(p["components"], dict) else json.loads(p["components"])
        rec = {"gid": gid, "wk": wk, "head": p["model_margin_home"], "actual": x["home_points"] - x["away_points"], "cr": 0.0, "who": []}
        any_backup = False
        for side, sign in (("home", 1), ("away", -1)):
            team = x[f"{side}_team"]
            leader, starter = ls.get((gid, team), (None, None))
            if not (leader and starter and leader != starter):
                continue
            any_backup = True
            charge = sum(b["points"] for b in c["layer2"].get(f"{side}_injuries") or []
                         if (b.get("position") or "").upper() == "QB" and same(b["player"], leader))
            cr = credit(2026, wk, starter, charge, k, pool)
            rec["cr"] += sign * cr
            rec["who"].append(f"{team} {short.get(starter)} for {short.get(leader)} charge {charge:.2f} credit {cr:.2f}")
        if any_backup:
            out.append(rec)
    e0 = np.array([abs(o["head"] - o["actual"]) for o in out])
    e1 = np.array([abs(o["head"] + o["cr"] - o["actual"]) for o in out])
    for o in out:
        print(f"  wk{o['wk']:<2} {o['gid']:<17} head {o['head']:+6.2f} p82 {o['head'] + o['cr']:+6.2f} actual {o['actual']:+4d} | {'; '.join(o['who'])}")
    if len(out):
        mean, lo, hi = boot_ci(e1 - e0)
        nz = np.array([o["cr"] != 0 for o in out])
        print(f"G7: n {len(out)} backup-QB games ({int(nz.sum())} with a non-zero credit) | MAE headline {e0.mean():.3f} -> P82 {e1.mean():.3f} "
              f"| diff {mean:+.4f} (95% CI {lo:+.4f} to {hi:+.4f})")
        print(f"G7 (MAE lower with the credit): {'PASS' if e1.mean() < e0.mean() else 'FAIL'}")
    else:
        print("G7: no backup-QB games found: FAIL (not testable)")


if __name__ == "__main__":
    main()
