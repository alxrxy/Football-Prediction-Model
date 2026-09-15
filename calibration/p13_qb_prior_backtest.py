"""P13 adoption test: QB-conditional prior season, before vs after.

    python calibration/p13_qb_prior_backtest.py calibration/<date>_p13_qb_prior.md

Two parts, both with the prior off and on and nothing else changed:

1. Baseline Layer 1 (power-rating difference + home field) in weeks 1-4 of
   2016-2025, rebuilt exactly as ingest_nflverse does before each week: the
   prior season regressed and blended with the current season's plays so far.
   The expected starter is the one who started that week's game, which is
   known at kickoff. Other baseline layers are left out so the change is
   isolated.
2. ML: the training set rebuilt both ways, the model retrained without
   saving, and scored on the 2025 holdout, overall and in weeks 1-4.

Adoption test (calibration-log.md, P13): holdout MAE vs the line must not get
worse, and weeks 1-4 MAE should improve. MIN_STARTS is fixed in advance, not
tuned here.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from tabulate import tabulate  # noqa: E402

from src import build_training, qb_prior, train_model  # noqa: E402
from src.features import HOME_FIELD_POINTS  # noqa: E402
from src.ingest_nflverse import (  # noqa: E402
    PLAYS_PER_GAME, _blend, _epa_by_team, condition_prior_offense,
)

SEASONS = list(range(2016, 2026))
HOLDOUT = 2025
HFA = HOME_FIELD_POINTS["nfl"]


def baseline_backtest() -> pd.DataFrame:
    import nfl_data_py as nfl

    cols = ["season", "week", "posteam", "defteam", "epa", "play_type", "game_id"]
    pbp = nfl.import_pbp_data(list(range(SEASONS[0] - 1, SEASONS[-1] + 1)), columns=cols,
                              downcast=True, cache=False)
    pbp = pbp[pbp["play_type"].isin(["pass", "run"]) & pbp["posteam"].notna()]
    sched = nfl.import_schedules(list(range(SEASONS[0] - 1, SEASONS[-1] + 1)))
    sched = sched[sched["home_score"].notna()]
    starters = qb_prior.game_starters(sched)

    out = []
    for season in SEASONS:
        prior = pbp[pbp["season"] == season - 1]
        off_p, def_p = _epa_by_team(prior)
        prior_starters = {k: v for k, v in starters.items() if k[0].startswith(f"{season - 1}_")}
        reg = sched[(sched["season"] == season) & (sched["game_type"] == "REG")]
        for week in range(1, 5):
            games = reg[reg["week"] == week]
            off_c, def_c = _epa_by_team(pbp[(pbp["season"] == season) & (pbp["week"] < week)])
            expected = {}
            for g in games.itertuples(index=False):
                for team, qb in ((g.home_team, g.home_qb_id), (g.away_team, g.away_qb_id)):
                    if (qb := qb_prior.qb_id(qb)) is not None:
                        expected[str(team)] = qb
            off_q = condition_prior_offense(off_p, prior, prior_starters, expected, verbose=False)

            ratings = {}
            for variant, offp in (("before", off_p), ("after", off_q)):
                pr = {}
                for team in set(off_c.index) | set(offp.index):
                    o, d = _blend(off_c, offp, team), _blend(def_c, def_p, team)
                    if o is not None and d is not None:
                        pr[team] = (o - d) * PLAYS_PER_GAME
                ratings[variant] = pr

            for g in games.itertuples(index=False):
                home, away = str(g.home_team), str(g.away_team)
                if any(t not in ratings[v] for v in ratings for t in (home, away)):
                    continue
                hfa = 0.0 if str(g.location) == "Neutral" else HFA
                row = {"season": season, "week": week, "game": f"{away} @ {home}",
                       "actual": float(g.home_score) - float(g.away_score),
                       "market": float(g.spread_line) if g.spread_line == g.spread_line else np.nan}
                for v, pr in ratings.items():
                    row[v] = pr[home] - pr[away] + hfa
                out.append(row)
    return pd.DataFrame(out)


def ats(df: pd.DataFrame, col: str, min_edge: float = 0.0) -> str:
    d = df.dropna(subset=["market"])
    edge = d[col] - d["market"]              # + => model likes home vs the line
    cover = d["actual"] - d["market"]         # + => home covered
    pick = (edge.abs() >= min_edge) & (cover != 0) & (edge != 0)
    wins = int(((edge[pick] > 0) == (cover[pick] > 0)).sum())
    n = int(pick.sum())
    return f"{wins}-{n - wins} ({wins / n * 100:.1f}%)" if n else "—"


def baseline_tables(df: pd.DataFrame) -> str:
    df = df.copy()
    df["shift"] = df["after"] - df["before"]
    changed = df[df["shift"].abs() >= 1.0]
    mk = df.dropna(subset=["market"])

    def mae(d, col):
        return f"{np.mean(np.abs(d[col] - d['actual'])):.3f}" if len(d) else "—"

    rows = []
    for label, d in (("All weeks 1-4", df), ("Games the prior moved ≥ 1 pt", changed)):
        dm = d.dropna(subset=["market"])
        rows.append([label, len(d), mae(d, "before"), mae(d, "after"), mae(dm, "market"),
                     ats(d, "before"), ats(d, "after"), ats(d, "before", 2.0), ats(d, "after", 2.0)])
    by_week = []
    for w in range(1, 5):
        d = df[df["week"] == w]
        by_week.append([w, len(d), mae(d, "before"), mae(d, "after"),
                        int((d["shift"].abs() >= 1.0).sum())])
    by_season = []
    for s in SEASONS:
        d = df[df["season"] == s]
        by_season.append([s, len(d), mae(d, "before"), mae(d, "after"),
                          int((d["shift"].abs() >= 1.0).sum())])

    # Is the shift pointing the right way? Positive = the conditioned prior
    # moved the margin toward what happened.
    toward = np.sign(df["shift"]) == np.sign(df["actual"] - df["before"])
    moved = df["shift"].abs() >= 1.0

    return "\n".join([
        f"Weeks 1-4, {SEASONS[0]}-{SEASONS[-1]}, regular season. Margin = power-rating difference + "
        f"{HFA} home field; market = nflverse closing line. {len(mk)} of {len(df)} games have a line.",
        "",
        tabulate(rows, headers=["Games", "n", "MAE before", "MAE after", "MAE line",
                                "ATS before", "ATS after", "ATS ≥2 before", "ATS ≥2 after"],
                 tablefmt="github"),
        "",
        f"Of the {int(moved.sum())} games the prior moved by ≥ 1 pt, it moved toward the result in "
        f"{int((toward & moved).sum())} ({(toward & moved).sum() / max(moved.sum(), 1) * 100:.0f}%). "
        f"Mean |shift| on those games {changed['shift'].abs().mean():.2f} pts.",
        "",
        tabulate(by_week, headers=["Week", "n", "MAE before", "MAE after", "moved ≥1"], tablefmt="github"),
        "",
        tabulate(by_season, headers=["Season", "n", "MAE before", "MAE after", "moved ≥1"], tablefmt="github"),
    ])


def ml_tables(tmp: Path) -> str:
    rows = []
    for flag in (False, True):
        path = tmp / f"training_nfl_qb{int(flag)}.csv"
        build_training.run("nfl", 2015, HOLDOUT, path=path, qb_conditional=flag)
        results, market_mae, ats_by_model = train_model.train("nfl", HOLDOUT, path=path, save=False)
        test = pd.read_csv(path)
        test = test[(test["season"] == HOLDOUT) & test["market_spread"].notna() & (test["week"] <= 4)]
        market_early = float(np.mean(np.abs(-test["market_spread"] - test["target_margin"])))
        f = results["fundamentals"]
        b = {x["threshold"]: x for x in (ats_by_model.get("fundamentals") or {}).get("buckets", [])}
        ats0, ats2 = b.get(0.0), b.get(2.0)
        rows.append([
            "on" if flag else "off", f["n"], f"{f['mae']:.3f}", f"{f['mae'] - market_mae:+.3f}",
            f"{f['mae_wk1_4']:.3f}", f"{f['mae_wk1_4'] - market_early:+.3f}",
            f"{ats0['wins']}/{ats0['n']}" if ats0 else "—", f"{ats2['wins']}/{ats2['n']}" if ats2 else "—",
        ])
    # Guard against a no-op: if the prior changed nothing, identical rows
    # would read as "no effect" rather than as a bug.
    a, b = (pd.read_csv(tmp / f"training_nfl_qb{i}.csv") for i in (0, 1))
    shift = (b["epa_diff"] - a["epa_diff"]).abs()
    early = (b["week"] <= 4)
    note = (f"Training rows whose epa_diff the prior moved by ≥ 0.5 pts: {int((shift >= 0.5).sum())} of "
            f"{len(b)} ({int((shift[early] >= 0.5).sum())} in weeks 1-4).")
    return note + "\n\n" + tabulate(rows, headers=["QB prior", "n", "MAE", "vs line", "MAE wk 1-4",
                                                   "vs line wk 1-4", "ATS all", "ATS ≥2"], tablefmt="github")


def main(out: str) -> None:
    print("[p13] baseline, weeks 1-4 ...")
    base = baseline_backtest()
    base_md = baseline_tables(base)
    print(base_md)
    print("\n[p13] ML rebuild and retrain, both ways (not saved) ...")
    with tempfile.TemporaryDirectory() as tmp:
        ml_md = ml_tables(Path(tmp))
    print(ml_md)
    Path(out).write_text("\n".join([
        "# P13 before/after: QB-conditional prior season",
        "",
        "Generated by calibration/p13_qb_prior_backtest.py. The prior-season offense is taken "
        f"from the expected starter's games when he started ≥ {qb_prior.MIN_STARTS} for that team; "
        "otherwise the whole season, as before.",
        "",
        "## Baseline (Layer 1 only)",
        "",
        base_md,
        "",
        f"## ML (holdout {HOLDOUT}, retrained both ways, nothing saved)",
        "",
        ml_md,
        "",
    ]), encoding="utf-8")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "calibration/p13_qb_prior_before_after.md")
