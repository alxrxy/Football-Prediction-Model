"""Baseline prediction — Layers 1 + 2 + 4 (no ML).

    Layer 1  power rating differential (SP+, Elo fallback)
    Layer 2  situational adjustment: home field, rest, travel, weather,
             and injuries once step 6 populates them
    Layer 4  comparison against the market line -> value flag

Run:  python -m src.predict_baseline            (today's slate)
      python -m src.predict_baseline --date 2026-09-13
      python -m src.predict_baseline --all      (every loaded upcoming game)
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, time, timedelta, timezone

from . import config, db
from .features import MARGIN_SIGMA, FeatureContext, normal_cdf, parse_dt

# A college football "slate day" runs from late morning ET through the small
# hours of the next morning, so the UTC window is offset rather than midnight.
SLATE_START_UTC_HOUR = 11


def slate_window(target: date) -> tuple[datetime, datetime]:
    start = datetime.combine(target, time(SLATE_START_UTC_HOUR), tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def predict_game(features: dict) -> dict | None:
    """Apply Layers 1, 2 and 4 to one game's features."""
    baseline = features["baseline_margin"]
    if baseline is None:
        return None

    # Layer 2: additive situational shifts, then weather compression.
    adjusted = baseline + features["hfa"] + features["rest_adj"] \
        + features["travel_adj"] + features["injury_adj"]
    margin = adjusted * features["wind_factor"]

    sigma = MARGIN_SIGMA.get(features["sport"], 16.0)
    win_prob = normal_cdf(margin / sigma)

    # Market convention: the home team's line. Negative means home favored.
    model_spread = -margin
    market_spread = features["market_spread"]

    edge = None
    is_value = False
    if market_spread is not None:
        # Positive edge => model likes the HOME side relative to the market.
        edge = margin + market_spread
        # A game where one side's rating is a flat replacement-level proxy
        # cannot produce a real edge — the "disagreement" with the market is
        # mostly the proxy's own error. Log the edge, never flag it as value.
        if features["baseline_source"] not in ("sp_plus_fcs_proxy", "elo"):
            is_value = abs(edge) >= config.VALUE_EDGE_THRESHOLD

    return {
        "game_id": features["game_id"],
        "model_version": config.MODEL_VERSION,
        "sport": features["sport"],
        "model_win_prob_home": round(win_prob, 4),
        "model_margin_home": round(margin, 2),
        "model_spread": round(model_spread, 2),
        "market_spread": market_spread,
        "market_source": features["market_source"],
        "edge": round(edge, 2) if edge is not None else None,
        "is_value": is_value,
        "confidence": _confidence(features),
        "baseline_source": features["baseline_source"],
        "components": _components(features, baseline, margin),
        "generated_at": db.utcnow(),
    }


def _components(features: dict, baseline: float, margin: float) -> dict:
    """Full auditable breakdown — every term that moved the number."""
    return {
        "layer1_baseline_margin": round(baseline, 2),
        "layer1_source": features["baseline_source"],
        "ratings": features["rating_detail"],
        "layer2": {
            "home_field": round(features["hfa"], 2),
            "rest": round(features["rest_adj"], 2),
            "home_rest_days": features["home_rest_days"],
            "away_rest_days": features["away_rest_days"],
            "travel": round(features["travel_adj"], 2),
            "away_travel_miles": round(features["away_travel_miles"], 1)
            if features["away_travel_miles"] is not None else None,
            "injury": round(features["injury_adj"], 2),
            "injury_data_available": features["injury_data_available"],
            "injury_coverage": features["injury_coverage"],
            "home_injury_points": features["home_injury_points"],
            "away_injury_points": features["away_injury_points"],
            "home_injuries": features["home_injury_detail"][:6],
            "away_injuries": features["away_injury_detail"][:6],
            "wind_factor": round(features["wind_factor"], 4),
            "wind_mph": features["wind_mph"],
            "temp_f": features["temp_f"],
            "precip_pct": features["precip_pct"],
            "is_dome": features["is_dome"],
        },
        "final_margin_home": round(margin, 2),
        "market": {
            "spread": features["market_spread"],
            "total": features["market_total"],
            "source": features["market_source"],
            "books": features["market_books"],
        },
    }


def _confidence(features: dict) -> str:
    """Data-completeness tier.

    This describes how much the model had to work with, NOT how likely the
    pick is to win. A 'high' game is one where every input was present.
    """
    if features["baseline_source"] in ("none", "elo"):
        return "low"
    if features["baseline_source"] == "sp_plus_fcs_proxy":
        return "low"
    if features["market_spread"] is None:
        return "low"
    if features["market_books"] >= 3 and (features["has_weather"] or features["is_dome"]):
        return "high"
    return "medium"


def run(target: date | None = None, sport: str = "ncaaf", all_upcoming: bool = False) -> list[dict]:
    store = db.get_store()
    ctx = FeatureContext(store, sport)

    now = datetime.now(timezone.utc)
    if all_upcoming:
        games = [g for g in ctx.games if (parse_dt(g.get("kickoff_time")) or now) >= now]
        label = "all upcoming"
    else:
        target = target or now.date()
        start, end = slate_window(target)
        games = [
            g for g in ctx.games
            if (k := parse_dt(g.get("kickoff_time"))) is not None and start <= k < end
        ]
        label = f"slate {target.isoformat()}"

    games.sort(key=lambda g: (parse_dt(g.get("kickoff_time")) or now))

    predictions, skipped = [], []
    for game in games:
        features = ctx.build(game)
        prediction = predict_game(features)
        if prediction is None:
            skipped.append(f"{game['away_team']} @ {game['home_team']} (no power rating for either side)")
            continue
        prediction["_features"] = features
        predictions.append(prediction)

    rows = [{k: v for k, v in p.items() if not k.startswith("_")} for p in predictions]
    store.upsert("predictions", rows)
    store.close()

    print(f"[predict] {label}: {len(predictions)} predictions written ({store.backend})")
    if skipped:
        print(f"  skipped {len(skipped)}:")
        for line in skipped[:5]:
            print(f"    - {line}")
    return predictions


def format_report(predictions: list[dict]) -> str:
    """Full slate, no cherry-picking (architecture §8)."""
    from tabulate import tabulate

    def sort_key(p):
        # Flagged value games first, then by edge size. Proxy-rated games sink
        # to the bottom, where their inflated edges cannot mislead.
        magnitude = abs(p["edge"]) if p["edge"] is not None else -1
        return (not p["is_value"], p["baseline_source"] == "sp_plus_fcs_proxy", -magnitude)

    rows = []
    for p in sorted(predictions, key=sort_key):
        f = p["_features"]
        kickoff = parse_dt(f["kickoff_time"])
        market = p["market_spread"]
        edge = p["edge"]
        side = ""
        if edge is not None and p["is_value"]:
            side = f["home_team"] if edge > 0 else f["away_team"]
        rows.append([
            kickoff.strftime("%H:%MZ") if kickoff else "—",
            f"{f['away_team']} @ {f['home_team']}" + (" (N)" if f["is_neutral_site"] else ""),
            f"{p['model_spread']:+.1f}",
            f"{market:+.1f}" if market is not None else "—",
            f"{edge:+.1f}" if edge is not None else "—",
            f"{p['model_win_prob_home'] * 100:.0f}%",
            side or "—",
            p["confidence"],
        ])

    table = tabulate(
        rows,
        headers=["Kick", "Matchup (away @ home)", "Model", "Market", "Edge", "Home WP", "Value side", "Conf"],
        tablefmt="simple",
    )

    with_market = [p for p in predictions if p["market_spread"] is not None]
    values = [p for p in predictions if p["is_value"]]
    proxy = [p for p in predictions if p["baseline_source"] == "sp_plus_fcs_proxy"]
    rated = [p for p in with_market if p["baseline_source"] == "power_rating"]
    errors = [abs(p["edge"]) for p in rated]
    mean_gap = sum(errors) / len(errors) if errors else 0.0

    summary = (
        f"\n{len(predictions)} games predicted | {len(with_market)} with a market line | "
        f"{len(values)} flagged as value (|edge| >= {config.VALUE_EDGE_THRESHOLD})"
        f"\nAcross the {len(rated)} fully-rated games: "
        f"mean |model - market| = {mean_gap:.2f} pts"
    )
    if proxy:
        summary += (
            f"\n{len(proxy)} game(s) had an unrated (FCS) side filled with a flat "
            "replacement-level proxy: predicted and logged, but never value-flagged."
        )
    note = (
        "\n\nSpreads are home-team lines (negative = home favored). Edge is positive "
        "when the model prefers the home side."
        f"\nInjury adjustment: {_injury_note(predictions)}"
        "\nPAPER TRADING ONLY — one slate is not enough signal to trust the value flags."
    )
    return table + "\n" + summary + "\n" + calibration_block(rated) + note


def _injury_note(predictions: list[dict]) -> str:
    """State plainly how much of the slate the injury layer actually touched."""
    covered = sum(1 for p in predictions if p["_features"]["injury_coverage"] == "both")
    partial = sum(1 for p in predictions if p["_features"]["injury_coverage"] in ("home", "away"))
    moved = sum(1 for p in predictions if abs(p["_features"]["injury_adj"]) >= 0.5)
    if not covered and not partial:
        return "NO DATA for this slate - contributed 0 to every game."
    return (
        f"{covered} game(s) with both sides reported, {partial} with one side only; "
        f"moved the line by 0.5+ pts in {moved}."
    )


def calibration_block(rated: list[dict]) -> str:
    """How far the model sits from the market, and what that means for the
    value threshold.

    The threshold is only meaningful relative to the model's own dispersion.
    If the typical disagreement with the market is 4 points, a 2-point
    threshold flags most of the slate and signals nothing — so the sensitivity
    table is printed every run rather than left for someone to discover.
    """
    edges = [p["edge"] for p in rated if p["edge"] is not None]
    if len(edges) < 5:
        return ""

    n = len(edges)
    mean_signed = sum(edges) / n
    mean_abs = sum(abs(e) for e in edges) / n
    variance = sum((e - mean_signed) ** 2 for e in edges) / n
    stdev = variance ** 0.5

    lines = [
        "",
        "CALIBRATION (fully-rated games only)",
        f"  mean |model - market| : {mean_abs:.2f} pts      stdev: {stdev:.2f}",
        f"  mean signed edge      : {mean_signed:+.2f} pts "
        f"({'leans away' if mean_signed < 0 else 'leans home'})",
        "  value flags by threshold:",
    ]
    for t in (2.0, 3.0, 4.0, 5.0, 6.0, 7.0):
        hits = sum(1 for e in edges if abs(e) >= t)
        marker = "  <- current" if abs(t - config.VALUE_EDGE_THRESHOLD) < 1e-9 else ""
        lines.append(f"    >= {t:>3.1f} pts : {hits:>3} / {n} ({hits / n * 100:>3.0f}%){marker}")

    flagged_now = sum(1 for e in edges if abs(e) >= config.VALUE_EDGE_THRESHOLD)
    if flagged_now / n > 0.40:
        lines.append(
            f"  WARNING: {config.VALUE_EDGE_THRESHOLD} pts flags {flagged_now / n * 100:.0f}% of "
            "rated games. A flag that fires on most of the slate carries no"
        )
        lines.append(
            "  information. The baseline's spread against the market is wider than the "
            "threshold assumes — raise VALUE_EDGE_THRESHOLD in .env, or wait for the"
        )
        lines.append(
            "  ML layer to tighten the model, before treating these as real edges."
        )
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate baseline predictions.")
    parser.add_argument("--date", help="slate date, YYYY-MM-DD (default: today UTC)")
    parser.add_argument("--sport", default="ncaaf")
    parser.add_argument("--all", action="store_true", help="every loaded upcoming game")
    parser.add_argument("--json", action="store_true", help="dump full component breakdown")
    args = parser.parse_args()

    target = date.fromisoformat(args.date) if args.date else None
    preds = run(target, args.sport, args.all)
    if preds:
        print()
        print(format_report(preds))
        if args.json:
            print(json.dumps([p["components"] for p in preds], indent=2))
