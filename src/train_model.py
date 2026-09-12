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
]
MARKET_FEATURES = FUNDAMENTAL_FEATURES + ["market_spread", "market_total"]


def load(sport: str):
    import pandas as pd

    path = config.DATA_DIR / f"training_{sport}.csv"
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


def train(sport: str, holdout_season: int | None = None):
    import numpy as np
    import pandas as pd
    import xgboost as xgb

    df = load(sport)
    seasons = sorted(df["season"].unique())
    holdout_season = holdout_season or seasons[-1]
    train_df = df[df["season"] < holdout_season]
    test_df = df[df["season"] == holdout_season]

    print(f"[train] {sport}: {len(train_df)} training games "
          f"({seasons[0]}-{holdout_season - 1}), {len(test_df)} holdout ({holdout_season})")

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
            eval_set=[(sub_test[feats], sub_test["target_margin"])],
            verbose=False,
        )
        pred = model.predict(sub_test[feats])
        results[name] = {
            "mae": float(np.mean(np.abs(pred - sub_test["target_margin"]))),
            "rmse": float(np.sqrt(np.mean((pred - sub_test["target_margin"]) ** 2))),
            "n": int(len(sub_test)),
            "best_iteration": int(model.best_iteration),
        }
        models[name] = (model, feats, sub_test, pred)

    # The benchmark: how well the closing line did on those same games.
    bench = test_df.dropna(subset=["market_spread", "target_margin"])
    market_pred = -bench["market_spread"]  # implied home margin
    market_mae = float(np.mean(np.abs(market_pred - bench["target_margin"])))

    print("\n  holdout accuracy (mean absolute error, points of margin)")
    print(f"    {'closing line':<16} {market_mae:6.3f}   <- the benchmark to beat")
    for name, r in results.items():
        delta = r["mae"] - market_mae
        verdict = "beats the line" if delta < 0 else "worse than the line"
        print(f"    {name:<16} {r['mae']:6.3f}   {delta:+.3f} vs line  ({verdict})")

    ats = None
    if "fundamentals" in models:
        ats = _ats_report(models["fundamentals"], sport)

    # The fundamentals model is the one that ships: it is the only one that
    # can disagree with the market, which is what a value signal requires.
    if "fundamentals" in models:
        model, feats, _, _ = models["fundamentals"]
        _save(sport, model, feats, results, market_mae, ats, holdout_season)
    return results, market_mae, ats


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
        z, p = _significance(wins, n)
        out["buckets"].append(
            {
                "threshold": threshold,
                "n": n,
                "wins": wins,
                "pushes": pushes,
                "win_pct": win_pct,
                "z": z,
                "p_value": p,
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
              f"p={b['p_value']:.3f}  {verdict}")

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


def _save(sport, model, feats, results, market_mae, ats, holdout_season) -> None:
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
