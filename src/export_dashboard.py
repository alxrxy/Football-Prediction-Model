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
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config, db
from .features import apply_inactives, latest_injury_report, parse_dt
from .predict_baseline import SLATE_START_UTC_HOUR, slate_window

SPORTS = {"ncaaf": "College Football", "nfl": "NFL"}


def _model_meta(sport: str) -> dict | None:
    path = Path(config.ROOT) / "models" / f"{sport}_margin.meta.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _slate_for(store, sport: str) -> tuple[str, list[dict], dict]:
    """The next slate with unplayed games: (first date, games, extra labels).

    For the NFL that is the whole week containing the next game, Thursday to
    Monday, including games of that week already played, so Thursday's result
    stays on screen through Sunday. College stays one date at a time, since a
    single Saturday can be 80+ games.
    """
    now = datetime.now(timezone.utc)
    games = store.select("games", {"sport": sport})
    upcoming = [
        (k, g) for g in games
        if not g.get("completed") and (k := parse_dt(g.get("kickoff_time"))) and k >= now
    ]
    if not upcoming:
        return now.date().isoformat(), [], {}
    first, first_game = min(upcoming, key=lambda pair: pair[0])

    if sport == "nfl" and first_game.get("week") is not None:
        week = [g for g in games
                if g.get("season") == first_game.get("season") and g.get("week") == first_game.get("week")]
        days = sorted(_slate_day(g) for g in week if _slate_day(g))
        return days[0], week, {"label": f"Week {first_game['week']}", "end": days[-1]}

    # Mirror the predictors' slate window: a kickoff before 11:00Z belongs to
    # the previous calendar day's slate.
    target = (first - timedelta(hours=slate_window(first.date())[0].hour)).date()
    for candidate in (target, first.date(), first.date() - timedelta(days=1)):
        start, end = slate_window(candidate)
        selected = [g for k, g in upcoming if start <= k < end]
        if selected:
            return candidate.isoformat(), selected, {}
    return first.date().isoformat(), [], {}


# Games whose served numbers are known to be measuring a defect, labelled on
# the page rather than hidden. Remove each entry once the item is fixed or the
# game has kicked off.
KNOWN_GAME_ISSUES = {
    "2026_02_CAR_ATL": (
        "Known issue, treat with caution (P28): ATL's quarterback is unsettled and the model prices neither option. The baseline charges Penix's absence at a generic 5.6 points without asking who replaces him. Against ATL's rating, Tua starting is worth about 0 to +4 points and Cooper Rush (who started week 1, and whom the books price) about -7. So this number is roughly right if Rush starts and 6-10 points too harsh on ATL if Tua does. The simulation is pinned to the same number and splits the passing 60/40 Tua/Rush."
    ),
}


def build(sport: str) -> dict:
    store = db.get_store()

    slate_date, games, slate_extra = _slate_for(store, sport)
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
    report = latest_injury_report(store.select("injuries", {"sport": sport}))
    if sport == "nfl":
        report = apply_inactives(report, db.select_merged(store, "inactives"))
    for row in report:
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
                "market": _market(odds_rows.get(gid, [])),
                "baseline": _pred(baseline),
                "ml": _pred(ml),
                "injuries": {
                    "home": _injury_list(baseline, "home_injuries"),
                    "away": _injury_list(baseline, "away_injuries"),
                },
                "known_issue": KNOWN_GAME_ISSUES.get(gid),
            }
        )

    results = _results(store, sport)

    store.close()
    meta = _model_meta(sport)
    return {
        "sport": sport,
        "label": SPORTS[sport],
        "slate_date": slate_date,
        "slate_label": slate_extra.get("label"),
        "slate_end": slate_extra.get("end"),
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
        "market_edge": components.get("market_edge"),
        "market_win_prob_home": components.get("market_win_prob_home"),
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


def _market(rows: list[dict]) -> dict | None:
    """The game's current line, independent of any prediction.

    A prediction carries the line it was made against, but a game that hasn't
    been predicted yet still has odds, and the slate row should show them
    rather than a dash. Latest consensus row first; otherwise the median of
    the books.
    """
    priced = [r for r in rows if r.get("spread") is not None]
    if not priced:
        return None
    consensus = [r for r in priced if r["book"].endswith("_consensus")]
    if consensus:
        r = max(consensus, key=lambda r: str(r.get("pulled_at") or ""))
        return {"spread": r["spread"], "total": r.get("total"), "source": r["book"],
                "pulled_at": r.get("pulled_at")}
    totals = [float(r["total"]) for r in priced if r.get("total") is not None]
    return {
        "spread": statistics.median(float(r["spread"]) for r in priced),
        "total": statistics.median(totals) if totals else None,
        "source": f"median of {len(priced)} books",
        "pulled_at": max(str(r.get("pulled_at") or "") for r in priced) or None,
    }


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
    from .grade import correctness_score, evaluate

    games = {g["game_id"]: g for g in store.select("games", {"sport": sport})}

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

        # Per-slate breakdown, newest first, so the score can be watched week
        # over week. Same slate-day convention as the predictors: a kickoff
        # before 11:00Z belongs to the previous day's slate.
        slates: dict[str, list] = {}
        for row in rows:
            day = _slate_day(games.get(row["game_id"]))
            if day:
                slates.setdefault(day, []).append(row)
        by_slate = []
        for day, day_rows in sorted(slates.items(), reverse=True):
            day_stats = evaluate(day_rows)
            day_score = correctness_score(day_stats)
            by_slate.append({
                "date": day,
                "n": day_stats["n"],
                "score": day_score["score"] if day_score else None,
                "su": day_stats["su"],
                "ats": day_stats["ats"],
            })

        out[version] = {
            "n": stats["n"],
            "su": stats["su"],
            "market_su": stats["market_su"],
            "ats": stats["ats"],
            "mae": stats["mae"],
            "market_mae": stats["market_mae"],
            "brier": stats["brier"],
            "score": correctness_score(stats),
            "by_slate": by_slate,
            "by_edge": {str(k): v for k, v in stats["by_edge"].items()},
            "by_conf": stats["by_conf"],
            "edges": _edge_record(rows, games),
        }
    return {
        "total_graded": len(graded),
        "models": out,
        "last_slate": _last_slate(graded, games),
        "weeks": _weeks(graded, games),
    }


def _slate_day(game: dict | None) -> str | None:
    """Same slate-day convention as the predictors: a kickoff before 11:00Z
    belongs to the previous day's slate."""
    kickoff = parse_dt((game or {}).get("kickoff_time"))
    if kickoff is None:
        return None
    return (kickoff - timedelta(hours=SLATE_START_UTC_HOUR)).date().isoformat()


def _last_slate(graded: list[dict], games: dict[str, dict]) -> dict | None:
    """Every game of the most recent graded slate, both models side by side.

    The full slate rather than a summary, so a bad week is on screen game by
    game instead of disappearing into the cumulative numbers.
    """
    by_day: dict[str, dict[str, dict]] = {}
    for row in graded:
        day = _slate_day(games.get(row["game_id"]))
        if day:
            by_day.setdefault(day, {}).setdefault(row["game_id"], {})[row["model_version"]] = row
    if not by_day:
        return None

    day = max(by_day)
    out = [_game_row(games[gid], models) for gid, models in by_day[day].items()]
    out.sort(key=lambda g: g["kickoff"] or "")
    return {"date": day, "games": out}


def _game_row(game: dict, models: dict[str, dict]) -> dict:
    """One game with both models' results, as the tables render it.

    `models` is empty for a game that was never predicted -- the pipeline only
    ever predicts unplayed games, so anything that kicked off before its first
    run has a final score and no pick. Those rows still belong in the week:
    dropping them silently makes a 16-game week look like a 14-game one, and
    the honest reason is worth showing. They are never back-filled, because a
    "prediction" made after the result is known, from ratings that already
    contain it, is lookahead rather than a record.
    """
    any_row = models.get(config.MODEL_VERSION) or next(iter(models.values()), None)
    home_pts = any_row["actual_home_points"] if any_row else game.get("home_points")
    away_pts = any_row["actual_away_points"] if any_row else game.get("away_points")
    actual = (
        any_row["actual_margin"] if any_row
        else int(home_pts) - int(away_pts) if home_pts is not None and away_pts is not None
        else None
    )
    market = any_row.get("market_spread") if any_row else None
    return {
        "game_id": game["game_id"],
        "kickoff": game.get("kickoff_time"),
        "home": game["home_team"],
        "away": game["away_team"],
        "neutral": bool(game.get("is_neutral_site")),
        "predicted": bool(models),
        "home_points": home_pts,
        "away_points": away_pts,
        "actual_margin": actual,
        "market_spread": market,
        "market_error": (
            round(-float(market) - actual, 1) if market is not None and actual is not None else None
        ),
        "baseline": _graded_pick(models.get(config.MODEL_VERSION), actual) if actual is not None else None,
        "ml": _graded_pick(models.get("ml-v1"), actual) if actual is not None else None,
    }


def _weeks(graded: list[dict], games: dict[str, dict]) -> list[dict]:
    """Every graded week, newest first: each model's record plus every game.

    `by_slate` is one row per slate day, which splits a single NFL week across
    Thursday, Sunday and Monday and never carries the games themselves. A week
    is the unit a season is actually read in, so it is grouped that way here
    and keeps the game rows, letting the page show the misses next to the
    hits without the reader opening anything.
    """
    from .grade import correctness_score, evaluate

    buckets: dict[tuple, dict[str, dict[str, dict]]] = {}
    for row in graded:
        game = games.get(row["game_id"])
        if not game or game.get("week") is None:
            continue
        key = (game.get("season"), game.get("week"))
        buckets.setdefault(key, {}).setdefault(row["game_id"], {})[row["model_version"]] = row

    out = []
    for (season, week), by_game in sorted(buckets.items(), reverse=True):
        rows_by_model: dict[str, list] = {}
        for versions in by_game.values():
            for version, row in versions.items():
                rows_by_model.setdefault(version, []).append(row)

        model_stats = {}
        for version, rows in sorted(rows_by_model.items()):
            stats = evaluate(rows)
            model_stats[version] = {
                "n": stats["n"],
                "su": stats["su"],
                "ats": stats["ats"],
                "mae": stats["mae"],
                "market_mae": stats["market_mae"],
                "brier": stats["brier"],
                "score": correctness_score(stats),
                "edges": _edge_record(rows, games),
            }

        # Every game of the week, not only the graded ones, so the week's real
        # size is on screen and a missing pick has to explain itself.
        all_ids = [
            gid for gid, g in games.items()
            if g.get("season") == season and g.get("week") == week
        ]
        rows = [_game_row(games[gid], by_game.get(gid, {})) for gid in all_ids]
        rows.sort(key=lambda g: g["kickoff"] or "")
        days = sorted(d for gid in all_ids if (d := _slate_day(games[gid])))
        out.append({
            "season": season,
            "week": week,
            "start": days[0] if days else None,
            "end": days[-1] if days else None,
            "n_games": len(rows),
            "n_predicted": sum(1 for r in rows if r["predicted"]),
            "n_graded": len(by_game),
            "models": model_stats,
            "games": rows,
        })
    return out


EDGE_THRESHOLDS = (0.0, 2.0, 3.0, 4.0, 6.0)   # the same cut-offs grade.evaluate reports


def _ats(row: dict) -> str | None:
    """W / L / P on the side the edge leaned, against the stored line. A zero
    edge counts as the away side, exactly as grade.evaluate grades it, so these
    records add up to the headline ATS on the same page."""
    edge, market = row.get("edge"), row.get("market_spread")
    if edge is None or market is None:
        return None
    cover = row["actual_margin"] + float(market)   # + => home covered
    return "P" if cover == 0 else ("W" if (float(edge) > 0) == (cover > 0) else "L")


def _edge_record(rows: list[dict], games: dict[str, dict]) -> dict:
    """ATS split by whether the pick was flagged and by the size of its edge.

    The question this answers every week is whether disagreeing with the line
    pays: on weeks 1 and 2 of 2026 the baseline did worse the more it disagreed.
    Unlike grade.evaluate's by_edge, pushes are counted rather than dropped, so
    each bucket's record adds up to the games in it. The flagged games are
    listed one by one, since there are rarely more than a handful.
    """
    def tally(rs):
        out = {"win": 0, "loss": 0, "push": 0}
        for r in rs:
            result = _ats(r)
            if result:
                out[{"W": "win", "L": "loss", "P": "push"}[result]] += 1
        return out

    graded = [r for r in rows if _ats(r)]
    flagged = [r for r in graded if r.get("is_value")]
    listed = []
    for r in sorted(flagged, key=lambda r: (games.get(r["game_id"]) or {}).get("kickoff_time") or ""):
        g = games.get(r["game_id"]) or {}
        edge = float(r["edge"])
        listed.append({
            "game_id": r["game_id"], "week": g.get("week"),
            "home": g.get("home_team"), "away": g.get("away_team"),
            "lean": g.get("home_team") if edge > 0 else g.get("away_team"),
            "edge": round(edge, 2), "market_spread": r.get("market_spread"),
            "ats": _ats(r),
        })
    return {
        "flagged": tally(flagged),
        "unflagged": tally([r for r in graded if not r.get("is_value")]),
        "by_edge": [{"min": t, **tally([r for r in graded if abs(float(r["edge"])) >= t])}
                    for t in EDGE_THRESHOLDS],
        "flagged_games": listed,
    }


def _graded_pick(row: dict | None, actual: int) -> dict | None:
    """One model's result on one game, graded exactly as grade.evaluate does."""
    if not row:
        return None
    edge, market = row.get("edge"), row.get("market_spread")
    margin, prob = row.get("model_margin_home"), row.get("model_win_prob_home")

    ats = None
    if edge is not None and market is not None:
        cover = actual + float(market)  # + => home covered
        ats = "P" if cover == 0 else ("W" if (float(edge) > 0) == (cover > 0) else "L")
    return {
        "model_spread": row.get("model_spread"),
        "edge": edge,
        "lean": None if edge is None else ("home" if float(edge) > 0 else "away"),
        "ats": ats,
        "su": None if prob is None or actual == 0 else (float(prob) > 0.5) == (actual > 0),
        "error": round(float(margin) - actual, 1) if margin is not None else None,
        "confidence": row.get("confidence"),
        "baseline_source": row.get("baseline_source"),
        "is_value": bool(row.get("is_value")),
    }


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
