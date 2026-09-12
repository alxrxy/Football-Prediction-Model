"""Export the current slates as a single JSON payload for the dashboard.

    python -m src.export_dashboard

Writes data/dashboard.json and dashboard/public/data.json.

The dashboard reads a snapshot rather than querying the database directly. That
keeps the front end free of credentials, makes it deployable as static files,
and means a dashboard open in a browser can never be the reason an API quota is
spent. Re-run this after a pipeline run to refresh it.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from . import config, db
from .features import parse_dt
from .predict_baseline import slate_window

SPORTS = {"ncaaf": "College Football", "nfl": "NFL"}


def _model_meta(sport: str) -> dict | None:
    path = Path(config.ROOT) / "models" / f"{sport}_margin.meta.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _slate_for(store, sport: str) -> tuple[str, list[dict]]:
    """The next date with unplayed games, and that date's games."""
    now = datetime.now(timezone.utc)
    games = store.select("games", {"sport": sport})
    upcoming = [
        (k, g) for g in games
        if not g.get("completed") and (k := parse_dt(g.get("kickoff_time"))) and k >= now
    ]
    if not upcoming:
        return now.date().isoformat(), []
    first = min(upcoming, key=lambda pair: pair[0])[0]
    # Mirror the predictors' slate window: a kickoff before 11:00Z belongs to
    # the previous calendar day's slate.
    from datetime import timedelta

    target = (first - timedelta(hours=slate_window(first.date())[0].hour)).date()
    for candidate in (target, first.date(), first.date() - timedelta(days=1)):
        start, end = slate_window(candidate)
        selected = [g for k, g in upcoming if start <= k < end]
        if selected:
            return candidate.isoformat(), selected
    return first.date().isoformat(), []


def build(sport: str) -> dict:
    store = db.get_store()

    slate_date, games = _slate_for(store, sport)
    by_id = {g["game_id"]: g for g in games}
    ids = set(by_id)

    predictions: dict[str, dict[str, dict]] = {}
    for row in store.select("predictions"):
        if row["game_id"] not in ids:
            continue
        components = row.get("components")
        if isinstance(components, str):
            try:
                components = json.loads(components)
            except json.JSONDecodeError:
                components = None
        row = dict(row)
        row["components"] = components
        predictions.setdefault(row["game_id"], {})[row["model_version"]] = row

    weather = {w["game_id"]: w for w in store.select("weather") if w["game_id"] in ids}
    odds_rows: dict[str, list[dict]] = {}
    for row in store.select("odds"):
        if row["game_id"] in ids:
            odds_rows.setdefault(row["game_id"], []).append(row)

    injuries: dict[str, list[dict]] = {}
    for row in store.select("injuries", {"sport": sport}):
        injuries.setdefault(row["team"], []).append(row)

    out_games = []
    for game in sorted(games, key=lambda g: g.get("kickoff_time") or ""):
        gid = game["game_id"]
        preds = predictions.get(gid, {})
        baseline = preds.get(config.MODEL_VERSION)
        ml = preds.get("ml-v1")
        books = [
            {"book": r["book"], "spread": r["spread"], "total": r["total"]}
            for r in sorted(odds_rows.get(gid, []), key=lambda r: r["book"])
            if not r["book"].endswith("_consensus") and r.get("spread") is not None
        ]
        out_games.append(
            {
                "game_id": gid,
                "kickoff": game.get("kickoff_time"),
                "home": game["home_team"],
                "away": game["away_team"],
                "home_conference": game.get("home_conference"),
                "away_conference": game.get("away_conference"),
                "venue": game.get("venue"),
                "neutral": bool(game.get("is_neutral_site")),
                "weather": _clean(weather.get(gid)),
                "books": books[:12],
                "baseline": _pred(baseline),
                "ml": _pred(ml),
                "injuries": {
                    "home": _injury_list(baseline, "home_injuries"),
                    "away": _injury_list(baseline, "away_injuries"),
                },
            }
        )

    results = _results(store, sport)

    store.close()
    meta = _model_meta(sport)
    return {
        "sport": sport,
        "label": SPORTS[sport],
        "slate_date": slate_date,
        "games": out_games,
        "results": results,
        "backtest": _backtest_summary(meta),
        "calibration": _calibration(out_games),
        "injury_coverage": {
            "teams_with_data": len(injuries),
            "total_rows": sum(len(v) for v in injuries.values()),
        },
    }


def _pred(row: dict | None) -> dict | None:
    if not row:
        return None
    components = row.get("components") or {}
    return {
        "model_version": row["model_version"],
        "win_prob_home": row.get("model_win_prob_home"),
        "margin_home": row.get("model_margin_home"),
        "model_spread": row.get("model_spread"),
        "market_spread": row.get("market_spread"),
        "market_source": row.get("market_source"),
        "edge": row.get("edge"),
        "is_value": bool(row.get("is_value")),
        "confidence": row.get("confidence"),
        "baseline_source": row.get("baseline_source"),
        "layers": components.get("layer2"),
        "layer1": {
            "baseline_margin": components.get("layer1_baseline_margin"),
            "source": components.get("layer1_source"),
            "ratings": components.get("ratings"),
        } if components.get("layer1_source") else None,
        "features": components.get("features"),
        "value_gate": components.get("value_gate"),
        "generated_at": row.get("generated_at"),
    }


def _injury_list(baseline: dict | None, key: str) -> list[dict]:
    if not baseline:
        return []
    layer2 = (baseline.get("components") or {}).get("layer2") or {}
    return layer2.get(key) or []


def _clean(row):
    if not row:
        return None
    return {k: v for k, v in row.items() if k != "pulled_at"}


def _backtest_summary(meta: dict | None) -> dict | None:
    if not meta:
        return None
    return {
        "holdout_season": meta.get("holdout_season"),
        "market_mae": meta.get("market_mae"),
        "models": {
            name: {"mae": r.get("mae"), "n": r.get("n")}
            for name, r in (meta.get("holdout") or {}).items()
        },
        "ats": {
            name: (payload or {}).get("buckets", [])
            for name, payload in (meta.get("ats_by_model") or {}).items()
        },
        "trained_at": meta.get("trained_at"),
    }


def _results(store, sport: str) -> dict:
    """The accumulated track record: every prediction that has been graded.

    Covers all graded games, not just the slate on screen — a record is only
    worth anything cumulatively, and showing one weekend of it would invite
    exactly the over-reading this project keeps trying to avoid.
    """
    from .grade import evaluate

    graded = []
    for row in store.select("predictions", {"sport": sport}):
        if row.get("actual_home_points") is None or row.get("actual_away_points") is None:
            continue
        row = dict(row)
        row["actual_margin"] = int(row["actual_home_points"]) - int(row["actual_away_points"])
        graded.append(row)

    by_model: dict[str, list] = {}
    for row in graded:
        by_model.setdefault(row["model_version"], []).append(row)

    out = {}
    for version, rows in sorted(by_model.items()):
        stats = evaluate(rows)
        out[version] = {
            "n": stats["n"],
            "su": stats["su"],
            "ats": stats["ats"],
            "mae": stats["mae"],
            "market_mae": stats["market_mae"],
            "brier": stats["brier"],
            "by_edge": {str(k): v for k, v in stats["by_edge"].items()},
            "by_conf": stats["by_conf"],
        }
    return {"total_graded": len(graded), "models": out}


def _calibration(games: list[dict]) -> dict:
    """Spread of the baseline model against the market, for the slate."""
    edges = [
        g["baseline"]["edge"] for g in games
        if g.get("baseline") and g["baseline"].get("edge") is not None
        and g["baseline"].get("baseline_source") == "power_rating"
    ]
    if not edges:
        return {"n": 0}
    n = len(edges)
    mean_signed = sum(edges) / n
    mean_abs = sum(abs(e) for e in edges) / n
    thresholds = {}
    for t in (2.0, 3.0, 4.0, 5.0, 6.0, 7.0):
        thresholds[str(t)] = sum(1 for e in edges if abs(e) >= t)
    return {
        "n": n,
        "mean_signed": round(mean_signed, 3),
        "mean_abs": round(mean_abs, 3),
        "threshold_counts": thresholds,
        "current_threshold": config.VALUE_EDGE_THRESHOLD,
    }


def run(sports: list[str] | None = None) -> str:
    sports = sports or ["ncaaf", "nfl"]
    payload = {
        "generated_at": db.utcnow(),
        "model_version_baseline": config.MODEL_VERSION,
        "storage_backend": config.STORAGE_BACKEND,
        "sports": [build(s) for s in sports],
    }

    config.ensure_dirs()
    path = config.DATA_DIR / "dashboard.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    public = Path(config.ROOT) / "dashboard" / "public"
    if public.exists():
        shutil.copy(path, public / "data.json")
        print(f"  also copied to {public / 'data.json'}")

    for sport in payload["sports"]:
        print(f"  {sport['label']}: {len(sport['games'])} games on {sport['slate_date']}")
    print(f"  wrote {path}")
    return str(path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export dashboard JSON.")
    parser.add_argument("--sport", action="append", choices=["ncaaf", "nfl"])
    args = parser.parse_args()
    run(args.sport)
