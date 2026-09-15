"""Layer 3 in production — the trained margin model applied to a live slate.

    python -m src.predict_ml --sport nfl
    python -m src.predict_ml --sport ncaaf --date 2026-09-12

Two things govern this module.

TRAIN/SERVE SKEW. Every feature must be built exactly as it was at training
time. The ratings come from replaying the same walk-forward history via
build_training.replay_state rather than from the team_ratings table, because
that table holds SP+ for college and a differently-shrunk EPA for the NFL —
neither of which the model ever saw. Where a training column was a constant
(college has no rest or EPA history), the live column is held at that same
constant. Feeding a real value into a column the model only ever saw as zero
would be a silent skew, not an improvement.

THE VALUE GATE. The model's own backtest decides whether it is allowed to call
anything a value pick. If no edge threshold beat the closing line by more than
noise on the holdout season, edges are still computed, stored and displayed —
but nothing is labelled value. The point of a backtest is to be allowed to
change the answer.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path

from . import build_training, clv, config, db, market
from .features import (
    FeatureContext, MARGIN_SIGMA, normal_cdf, parse_dt, qb_availability_loss,
)
from .predict_baseline import slate_window

MODEL_VERSION = "ml-v1"


def _paths(sport: str) -> tuple[Path, Path]:
    models = Path(config.ROOT) / "models"
    return models / f"{sport}_margin.json", models / f"{sport}_margin.meta.json"


def load_model(sport: str):
    model_path, meta_path = _paths(sport)
    if not model_path.exists():
        raise SystemExit(
            f"No trained model at {model_path}.\n"
            f"Run: python -m src.build_training --sport {sport} "
            f"&& python -m src.train_model --sport {sport}"
        )
    import xgboost as xgb

    model = xgb.XGBRegressor()
    model.load_model(str(model_path))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return model, meta


def build_live_features(sport: str, games: list[dict], ctx: FeatureContext,
                        elo, epa) -> list[dict]:
    """Reproduce the training feature construction for upcoming games."""
    rows = []
    for g in games:
        home, away = g["home_team"], g["away_team"]
        neutral = bool(g.get("is_neutral_site"))
        weather = ctx.weather.get(g["game_id"]) or {}

        travel_away = ctx.travel_miles(away, g) or 0.0
        travel_home = ctx.travel_miles(home, g) or 0.0

        if sport == "nfl":
            rest_diff = (g.get("home_rest_days") or 0.0) - (g.get("away_rest_days") or 0.0)
            epa_diff = (epa.rating(home) - epa.rating(away)) * build_training.PLAYS_PER_GAME
            wind = weather.get("wind_mph")
            temp = weather.get("temp_f") if weather.get("temp_f") is not None else 60.0
            # Scored by the same features.score_injuries the training set used.
            home_inj, _, _ = ctx.injury_adjustment(home)
            away_inj, _, _ = ctx.injury_adjustment(away)
            injury_diff = home_inj - away_inj
            qb_loss_diff = (
                qb_availability_loss([i for i in ctx.injuries if i.get("team") == away])
                - qb_availability_loss([i for i in ctx.injuries if i.get("team") == home])
            )
        else:
            # Held at the training-time constants. College training rows carry
            # no rest, no EPA and no weather, so supplying them live would feed
            # the model columns it has never seen vary.
            rest_diff = 0.0
            epa_diff = 0.0
            wind = float("nan")
            temp = 60.0
            # College training rows have no injury history to score, so these
            # stay at the constant the model was trained on.
            injury_diff = 0.0
            qb_loss_diff = 0.0

        rows.append(
            {
                "game_id": g["game_id"],
                "home_team": home,
                "away_team": away,
                "kickoff_time": g.get("kickoff_time"),
                "is_neutral_site": neutral,
                "elo_diff": elo.pre(home) - elo.pre(away),
                "epa_diff": epa_diff,
                "rest_diff": rest_diff,
                "travel_away": travel_away,
                "travel_diff": travel_away - travel_home,
                "is_neutral": int(neutral),
                "is_division": int(bool(g.get("is_conference"))),
                "is_indoor": int(bool(weather.get("is_dome"))),
                "injury_diff": injury_diff,
                "qb_loss_diff": qb_loss_diff,
                "wind": wind if wind is not None else float("nan"),
                "temp": temp,
            }
        )
    return rows


def run(sport: str = "nfl", target: date | None = None,
        dates: list[date] | None = None) -> list[dict]:
    import pandas as pd

    from .predict_baseline import slate_games

    model, meta = load_model(sport)
    gate = _value_gate(meta)

    store = db.get_store()
    ctx = FeatureContext(store, sport)
    now = datetime.now(timezone.utc)

    # Several slates share one history replay, which is the slow part.
    dates = dates or [target or now.date()]
    label = ", ".join(d.isoformat() for d in dates)
    games, started = slate_games(ctx.games, dates, now)
    if started:
        print(f"[predict-ml] {len(started)} game(s) already kicked off; "
              "keeping their stored pregame predictions")
    if not games:
        print(f"[predict-ml] no {sport} games still to kick off on {label}")
        store.close()
        return []
    ctx.load_prices(g["game_id"] for g in games)

    print(f"[predict-ml] replaying history to rebuild ratings the model was trained on...")
    elo, epa = build_training.replay_state(sport)

    feature_rows = build_live_features(sport, games, ctx, elo, epa)
    frame = pd.DataFrame(feature_rows)[meta["features"]]
    margins = model.predict(frame)

    sigma = meta.get("residual_sd") or MARGIN_SIGMA.get(sport, 14.0)
    predictions = []
    for row, margin in zip(feature_rows, margins):
        margin = float(margin)
        market_spread, market_total, market_source, n_books = ctx.market(row["game_id"])
        edge = margin + market_spread if market_spread is not None else None
        prices = ctx.prices.get(row["game_id"], [])
        market_edge = (market.spread_edge(margin, sigma, market_spread, prices, sport)
                       if market_spread is not None else None)
        # The holdout gate must be open, and then the same blended test as
        # the baseline decides (src/market.py).
        is_value = bool(gate["allowed"] and market_edge and market_edge["flag"])
        predictions.append(
            {
                "game_id": row["game_id"],
                "model_version": MODEL_VERSION,
                "sport": sport,
                "model_win_prob_home": round(normal_cdf(margin / sigma), 4),
                "model_margin_home": round(margin, 2),
                "model_spread": round(-margin, 2),
                "market_spread": market_spread,
                "market_source": market_source,
                "edge": round(edge, 2) if edge is not None else None,
                "is_value": is_value,
                "confidence": "high" if n_books >= 3 else "medium",
                "baseline_source": "xgboost_fundamentals",
                "components": {
                    "features": {k: _clean(v) for k, v in row.items()
                                 if k in meta["features"]},
                    "residual_sd": sigma,
                    "value_gate": gate,
                    "market_edge": market_edge,
                    "market_win_prob_home": market.market_win_prob(ctx.ml_books(row["game_id"])),
                    "market": {"spread": market_spread, "total": market_total,
                               "books": n_books, "source": market_source},
                },
                "generated_at": db.utcnow(),
                "_features": row,
            }
        )

    rows = [{k: v for k, v in p.items() if not k.startswith("_")} for p in predictions]
    store.upsert("predictions", rows)
    clv.log_leans(store, [
        clv.lean_row(p, p["_features"]["home_team"], p["_features"]["away_team"],
                     p["_features"]["kickoff_time"], ctx.prices.get(p["game_id"], []))
        for p in predictions
    ])
    store.close()

    print(f"[predict-ml] {len(predictions)} predictions written (model {MODEL_VERSION})")
    print(_gate_note(gate, meta, sport))
    return predictions


def _clean(value):
    import math as _m

    if isinstance(value, float) and _m.isnan(value):
        return None
    return round(value, 4) if isinstance(value, float) else value


def _value_gate(meta: dict) -> dict:
    """Decide whether this model has earned the right to flag value.

    Permission comes from the holdout ATS result, not from the configured
    threshold. If nothing beat the line significantly, nothing is flagged.
    """
    ats = meta.get("ats") or {}
    buckets = [b for b in ats.get("buckets", []) if b.get("significant")]
    if not buckets:
        return {
            "allowed": False,
            "threshold": config.VALUE_EDGE_THRESHOLD,
            "reason": (
                "no edge threshold beat the closing line by more than noise on the "
                f"{meta.get('holdout_season')} holdout"
            ),
        }
    best = max(buckets, key=lambda b: b["win_pct"])
    return {
        "allowed": True,
        "threshold": best["threshold"],
        "reason": (
            f"holdout ATS {best['wins']}/{best['n']} = {best['win_pct'] * 100:.1f}% "
            f"at edge >= {best['threshold']} (p={best['p_value']:.3f})"
        ),
    }


def _gate_note(gate: dict, meta: dict, sport: str) -> str:
    holdout = meta.get("holdout", {}).get("fundamentals", {})
    lines = [
        f"  holdout MAE {holdout.get('mae', float('nan')):.2f} pts vs closing line "
        f"{meta.get('market_mae', float('nan')):.2f} pts",
    ]
    if gate["allowed"]:
        lines.append(f"  VALUE FLAGS ON at edge >= {gate['threshold']}: {gate['reason']}")
    else:
        lines.append(f"  VALUE FLAGS OFF: {gate['reason']}.")
        lines.append("  Edges are still computed and logged, but none is called a value pick.")
    return "\n".join(lines)


def format_report(predictions: list[dict]) -> str:
    from tabulate import tabulate

    rows = []
    for p in sorted(predictions, key=lambda x: -(abs(x["edge"]) if x["edge"] is not None else -1)):
        f = p["_features"]
        kickoff = parse_dt(f["kickoff_time"])
        rows.append([
            kickoff.strftime("%H:%MZ") if kickoff else "—",
            f"{f['away_team']} @ {f['home_team']}",
            f"{p['model_spread']:+.1f}",
            f"{p['market_spread']:+.1f}" if p["market_spread"] is not None else "—",
            f"{p['edge']:+.1f}" if p["edge"] is not None else "—",
            f"{p['model_win_prob_home'] * 100:.0f}%",
            "yes" if p["is_value"] else "—",
        ])
    return tabulate(
        rows,
        headers=["Kick", "Matchup (away @ home)", "ML model", "Market", "Edge", "Home WP", "Value"],
        tablefmt="simple",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Layer 3 ML model on a slate.")
    parser.add_argument("--sport", default="nfl", choices=["nfl", "ncaaf"])
    parser.add_argument("--date", help="slate date, YYYY-MM-DD")
    args = parser.parse_args()
    target = date.fromisoformat(args.date) if args.date else None
    preds = run(args.sport, target)
    if preds:
        print()
        print(format_report(preds))
