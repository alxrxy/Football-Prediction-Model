"""Layer 3 — gradient-boosted margin model, and its honest evaluation.

    python -m src.train_model --sport nfl
    python -m src.train_model --sport ncaaf

Trains on data/training_<sport>.csv and writes models/<sport>_margin.json.

TWO MODELS ARE TRAINED, and the distinction is the point:

  fundamentals   no market feature. Free to disagree with the market, so it is
                 the only one that can generate a value signal.
  with_market    market spread included. Almost always the more accurate model
                 and almost useless for finding value, because the cheapest way
                 to predict a margin well is to copy the closing line.

Feeding the market in and then measuring "edge" against that same market is a
circular exercise that produces a model which agrees with the line and an edge
that collapses to zero. Both are reported so the gap is visible.

WHAT COUNTS AS SUCCESS: not the model's error in absolute terms, but its error
against the closing line's error on the same games. The market is a strong
forecast. A model that predicts margin to within 10 points sounds good and is
worthless if the line manages 9.8 on the same slate. The holdout is the most
recent season, kept strictly out of training.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from . import config

FUNDAMENTAL_FEATURES = [
    "elo_diff", "epa_diff", "rest_diff", "travel_away", "travel_diff",
    "is_neutral", "is_division", "is_indoor", "wind", "temp",
    # Injury features. qb_loss_diff is kept separate from the aggregate points
    # because losing a quarterback is a different kind of event, not simply a
    # larger quantity of damage, and the isolated signal is easier to use.
    "injury_diff", "qb_loss_diff",
]
MARKET_FEATURES = FUNDAMENTAL_FEATURES + ["market_spread", "market_total"]

# 5 edge thresholds x 2 models tested per run. Used to Bonferroni-correct the
# ATS p-values so a lucky bucket is not mistaken for a real edge.
N_COMPARISONS = 10


def load(sport: str, path=None):
    import pandas as pd

    path = Path(path) if path else config.DATA_DIR / f"training_{sport}.csv"
    if not path.exists():
        raise SystemExit(
            f"{path} not found. Run: python -m src.build_training --sport {sport}"
        )
    df = pd.read_csv(path)
    # Week 1 rows carry almost no rating signal in college, where Elo has not
    # seen the roster turnover; keeping them mostly adds noise.
    df = df[df["target_margin"].notna()]
    if sport == "ncaaf":
        df = df[df["both_fbs"] == 1]
    return df


def train(sport: str, holdout_season: int | None = None, path=None, save: bool = True):
    import numpy as np
    import pandas as pd
    import xgboost as xgb

    df = load(sport, path)
    seasons = sorted(df["season"].unique())
    holdout_season = holdout_season or seasons[-1]

    # Early stopping picks the number of trees, which makes the set it watches
    # part of fitting. Pointing it at the holdout would quietly tune the model
    # on the very season used to judge it and inflate every number below, so
    # the season before the holdout is carved out as a validation set and the
    # holdout is touched exactly once, at scoring time.
    valid_season = holdout_season - 1
    train_df = df[df["season"] < valid_season]
    valid_df = df[df["season"] == valid_season]
    test_df = df[df["season"] == holdout_season]

    print(f"[train] {sport}: {len(train_df)} training games "
          f"({seasons[0]}-{valid_season - 1}), {len(valid_df)} validation ({valid_season}), "
          f"{len(test_df)} holdout ({holdout_season}, never seen during fitting)")

    results = {}
    models = {}
    for name, feats in (("fundamentals", FUNDAMENTAL_FEATURES), ("with_market", MARKET_FEATURES)):
        # Only the target and any market feature are required. XGBoost handles
        # missing predictors natively, and dropping rows on them would discard
        # every college game, where wind is never populated.
        # market_total is deliberately not required: college rows never carry
        # one, and demanding it would silently drop the entire CFB training
        # set rather than let XGBoost treat it as missing.
        required = ["target_margin"] + (["market_spread"] if "market_spread" in feats else [])
        sub_train = train_df.dropna(subset=required)
        sub_valid = valid_df.dropna(subset=required)
        sub_test = test_df.dropna(subset=required)
        if len(sub_train) < 200:
            print(f"  [skip] {name}: only {len(sub_train)} usable rows")
            continue

        model = xgb.XGBRegressor(
            n_estimators=600,
            learning_rate=0.03,
            max_depth=4,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=8,
            reg_lambda=2.0,
            objective="reg:squarederror",
            early_stopping_rounds=50,
            eval_metric="mae",
        )
        model.fit(
            sub_train[feats], sub_train["target_margin"],
            eval_set=[(sub_valid[feats], sub_valid["target_margin"])],
            verbose=False,
        )
        pred = model.predict(sub_test[feats])
        # Weeks 1-4 separately: that is where the prior season carries the
        # rating, and where a stale or QB-blind prior shows up (P5, P13).
        early = (sub_test["week"] <= 4).to_numpy()
        results[name] = {
            "mae": float(np.mean(np.abs(pred - sub_test["target_margin"]))),
            "rmse": float(np.sqrt(np.mean((pred - sub_test["target_margin"]) ** 2))),
            "n": int(len(sub_test)),
            "mae_wk1_4": (float(np.mean(np.abs(pred[early] - sub_test["target_margin"].to_numpy()[early])))
                          if early.any() else None),
            "n_wk1_4": int(early.sum()),
            "best_iteration": int(model.best_iteration),
        }
        models[name] = (model, feats, sub_test, pred)

    # The benchmark: how well the closing line did on those same games.
    bench = test_df.dropna(subset=["market_spread", "target_margin"])
    market_pred = -bench["market_spread"]  # implied home margin
    market_mae = float(np.mean(np.abs(market_pred - bench["target_margin"])))

    early = bench[bench["week"] <= 4]
    market_early = float(np.mean(np.abs(-early["market_spread"] - early["target_margin"]))) if len(early) else None

    print("\n  holdout accuracy (mean absolute error, points of margin)")
    print(f"    {'closing line':<16} {market_mae:6.3f}   <- the benchmark to beat"
          + (f"   weeks 1-4: {market_early:6.3f}" if market_early is not None else ""))
    for name, r in results.items():
        delta = r["mae"] - market_mae
        verdict = "beats the line" if delta < 0 else "worse than the line"
        wk = (f"   weeks 1-4: {r['mae_wk1_4']:6.3f} (n={r['n_wk1_4']})"
              if r.get("mae_wk1_4") is not None else "")
        print(f"    {name:<16} {r['mae']:6.3f}   {delta:+.3f} vs line  ({verdict}){wk}")

    # Both models get an ATS test. The with_market model was originally
    # assumed useless for value because it merely copies the line - true while
    # it had nothing to add. Once it beats the line it is no longer copying it,
    # it is correcting it, and its disagreement becomes a candidate signal that
    # has to be measured rather than assumed away.
    ats_by_model = {}
    for name in ("fundamentals", "with_market"):
        if name in models:
            print(f"\n  [{name}]")
            ats_by_model[name] = _ats_report(models[name], sport)
    ats = ats_by_model.get("fundamentals")

    # The fundamentals model is the one that ships: it is the only one that
    # can disagree with the market, which is what a value signal requires.
    if save and "fundamentals" in models:
        model, feats, _, _ = models["fundamentals"]
        _save(sport, model, feats, results, market_mae, ats, holdout_season,
              ats_by_model)
    return results, market_mae, ats_by_model


def _ats_report(bundle, sport: str):
    """Does disagreeing with the line actually win against the spread?

    This is the only question that matters for the value flag. A model can
    have a lower MAE than the line and still pick the wrong side of it.
    """
    import numpy as np

    _model, _feats, test, pred = bundle
    mask = test["market_spread"].notna()
    test, pred = test[mask], pred[mask.values]
    if not len(test):
        return None

    market_margin = -test["market_spread"].values
    actual = test["target_margin"].values
    edge = pred - market_margin

    out = {"n": int(len(test)), "buckets": []}
    for threshold in (0.0, 2.0, 3.0, 4.0, 6.0):
        picked = np.abs(edge) >= threshold
        if picked.sum() < 10:
            continue
        # Model takes home when it sees home as undervalued.
        take_home = edge[picked] > 0
        covered = (actual[picked] - market_margin[picked]) > 0
        wins = int(np.sum(take_home == covered))
        pushes = int(np.sum((actual[picked] - market_margin[picked]) == 0))
        n = int(picked.sum())
        win_pct = wins / n if n else 0.0
        z, p_raw = _significance(wins, n)
        # Five thresholds are tried per model and two models are tried, so ten
        # chances to clear p<0.05 by luck alone -- roughly one expected false
        # positive per run. Bonferroni is conservative but it is the right
        # direction of conservative when the output is a betting signal.
        p = min(1.0, p_raw * N_COMPARISONS)
        out["buckets"].append(
            {
                "threshold": threshold,
                "n": n,
                "wins": wins,
                "pushes": pushes,
                "win_pct": win_pct,
                "z": z,
                "p_value": p,
                "p_uncorrected": p_raw,
                "significant": bool(p < 0.05),
            }
        )

    print("\n  against the spread, holdout season")
    print("    (break-even at standard -110 juice is 52.4%)")
    for b in out["buckets"]:
        # A raw win rate above break-even means nothing on a few hundred
        # games. Anything not significant is noise, and labelling it
        # "profitable" would be the single most misleading thing this
        # report could do.
        verdict = "SIGNIFICANT" if b["significant"] else "not distinguishable from chance"
        print(f"    edge >= {b['threshold']:>3.1f} pts : "
              f"{b['wins']:>4}/{b['n']:<4} = {b['win_pct'] * 100:5.1f}%   "
              f"p={b['p_uncorrected']:.3f} raw / {b['p_value']:.3f} corrected  {verdict}")

    best = max(out["buckets"], key=lambda b: b["win_pct"]) if out["buckets"] else None
    out["any_significant"] = any(b["significant"] for b in out["buckets"])
    if best and not out["any_significant"]:
        print("    -> no threshold beats the closing line by more than noise.")
    return out


def _significance(wins: int, n: int, break_even: float = 0.524):
    """One-sided test against the -110 break-even rate."""
    if n <= 0:
        return 0.0, 1.0
    se = math.sqrt(break_even * (1 - break_even) / n)
    z = (wins / n - break_even) / se
    p = 0.5 * (1 - math.erf(z / math.sqrt(2)))
    return float(z), float(p)


def _save(sport, model, feats, results, market_mae, ats, holdout_season,
          ats_by_model=None) -> None:
    models_dir = Path(config.ROOT) / "models"
    models_dir.mkdir(exist_ok=True)
    model_path = models_dir / f"{sport}_margin.json"
    model.save_model(str(model_path))

    residual_sd = results["fundamentals"]["rmse"]
    meta = {
        "sport": sport,
        "features": feats,
        "holdout_season": int(holdout_season),
        "holdout": results,
        "market_mae": market_mae,
        "residual_sd": residual_sd,
        "ats": ats,
        "ats_by_model": ats_by_model or {},
        "trained_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
    }
    (models_dir / f"{sport}_margin.meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    print(f"\n  saved {model_path.name} (+ metadata)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train the Layer 3 margin model.")
    parser.add_argument("--sport", default="nfl", choices=["nfl", "ncaaf"])
    parser.add_argument("--holdout", type=int, help="season held out (default: latest)")
    args = parser.parse_args()
    train(args.sport, args.holdout)
