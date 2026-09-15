"""Score finished predictions against what actually happened (architecture §8).

    python -m src.grade                      grade everything gradeable
    python -m src.grade --refresh            re-pull final scores first
    python -m src.grade --sport nfl
    python -m src.grade --model ml-v1
    python -m src.grade --since 2026-09-01

Fills predictions.actual_home_points / actual_away_points / graded_at, then
reports how the model actually did.

WHAT THIS GRADES AGAINST. Each prediction stored the market line as it was when
the prediction was made, and that is the line used here. Grading against a line
pulled later would score the model against a number it never saw — usually
flatteringly, since lines move toward the result as information arrives.

WHY IT REPORTS SO MANY CAVEATS. A weekend is roughly 90 games, which sounds
substantial and is nowhere near enough to establish a 2-point edge against the
spread. Every rate here carries its sample size and a significance test against
the break-even rate, because the entire purpose of this file is to eventually
be able to say something true about whether the model works — and the fastest
way to ruin that is to celebrate a 57% weekend.
"""

from __future__ import annotations

import argparse
import math
from datetime import date, datetime, timezone

from . import config, db
from .features import parse_dt

BREAK_EVEN = 0.524  # -110 juice
MODEL_LABELS = {"baseline-v1": "Baseline (layers 1+2+4)", "ml-v1": "ML margin model"}


# --- score refresh ---------------------------------------------------------

def refresh_scores(store: db.Store, sport: str) -> int:
    """Re-pull final scores for the weeks that have ungraded predictions."""
    predicted = {p["game_id"] for p in store.select("predictions", {"sport": sport})}
    if not predicted:
        return 0
    games = [g for g in store.select("games", {"sport": sport}) if g["game_id"] in predicted]
    weeks = sorted({(g["season"], g["week"]) for g in games if g.get("week")})
    if not weeks:
        return 0

    updated = 0
    if sport == "ncaaf":
        from .ingest_cfbd import ingest_games

        for season, week in weeks:
            # Short cache: the point of this call is to see fresh finals.
            rows = ingest_games(store, season, week, "regular", cache_minutes=5)
            updated += sum(1 for r in rows if r.get("completed"))
    else:
        from .ingest_nflverse import run as nfl_run

        nfl_run()
        updated = len(weeks)
    return updated


# --- grading ---------------------------------------------------------------

def grade(store: db.Store, sport: str | None, model: str | None,
          since: date | None) -> list[dict]:
    """Attach final scores to predictions and return the graded rows."""
    games = {g["game_id"]: g for g in store.select("games")}
    predictions = store.select("predictions")

    graded, updates = [], []
    for p in predictions:
        if sport and p.get("sport") != sport:
            continue
        if model and p.get("model_version") != model:
            continue
        game = games.get(p["game_id"])
        if not game:
            continue
        home, away = game.get("home_points"), game.get("away_points")
        if home is None or away is None or not game.get("completed"):
            continue
        kickoff = parse_dt(game.get("kickoff_time"))
        if since and kickoff and kickoff.date() < since:
            continue

        row = dict(p)
        row["actual_home_points"] = int(home)
        row["actual_away_points"] = int(away)
        row["actual_margin"] = int(home) - int(away)
        row["_game"] = game
        graded.append(row)

        # Carry the whole existing row through, not just the three graded
        # columns. An upsert is an INSERT with a conflict clause, so every
        # NOT NULL column has to be present for the insert the database
        # attempts first — a key-plus-results row fails on generated_at even
        # though the conflict path would only ever update.
        updates.append(
            {
                **{k: v for k, v in p.items() if not k.startswith("_")},
                "actual_home_points": int(home),
                "actual_away_points": int(away),
                "graded_at": db.utcnow(),
            }
        )

    if updates:
        store.upsert("predictions", updates)
    return graded


def _significance(wins: int, n: int, base: float = BREAK_EVEN) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 1.0
    se = math.sqrt(base * (1 - base) / n)
    z = (wins / n - base) / se
    return z, 0.5 * (1 - math.erf(z / math.sqrt(2)))


def evaluate(rows: list[dict]) -> dict:
    """Straight-up, against-the-spread, margin error and probability calibration."""
    su_right = su_n = 0
    mkt_su_right = mkt_su_n = 0
    ats_win = ats_loss = ats_push = 0
    abs_err = market_abs_err = 0.0
    err_n = 0
    brier = 0.0
    brier_n = 0
    by_edge: dict[float, list[int]] = {t: [0, 0] for t in (0.0, 2.0, 3.0, 4.0, 6.0)}
    by_conf: dict[str, list[int]] = {}

    for r in rows:
        actual = r["actual_margin"]

        # Straight up: the side the model made the favourite.
        prob = r.get("model_win_prob_home")
        if prob is not None and actual != 0:
            picked_home = prob > 0.5
            if picked_home == (actual > 0):
                su_right += 1
            su_n += 1
        if prob is not None:
            outcome = 1.0 if actual > 0 else (0.5 if actual == 0 else 0.0)
            brier += (float(prob) - outcome) ** 2
            brier_n += 1

        margin = r.get("model_margin_home")
        market = r.get("market_spread")
        if margin is not None:
            abs_err += abs(float(margin) - actual)
            err_n += 1
            if market is not None:
                market_abs_err += abs(-float(market) - actual)

        # The market's straight-up record: the favourite by the stored line.
        # This is the benchmark for the model's own straight-up rate, which on
        # its own flatters any model that mostly agrees with the favourite.
        if market is not None and float(market) != 0 and actual != 0:
            mkt_su_right += int((float(market) < 0) == (actual > 0))
            mkt_su_n += 1

        edge = r.get("edge")
        if edge is None or market is None:
            continue
        cover_margin = actual - (-float(market))  # + => home covered
        if cover_margin == 0:
            ats_push += 1
            continue
        took_home = float(edge) > 0
        won = took_home == (cover_margin > 0)
        ats_win += int(won)
        ats_loss += int(not won)

        for threshold, bucket in by_edge.items():
            if abs(float(edge)) >= threshold:
                bucket[0] += int(won)
                bucket[1] += 1
        conf = r.get("confidence") or "unknown"
        slot = by_conf.setdefault(conf, [0, 0])
        slot[0] += int(won)
        slot[1] += 1

    decided = ats_win + ats_loss
    return {
        "n": len(rows),
        "su": {"right": su_right, "n": su_n},
        "ats": {"win": ats_win, "loss": ats_loss, "push": ats_push, "decided": decided},
        "mae": abs_err / err_n if err_n else None,
        "market_mae": market_abs_err / err_n if err_n else None,
        "brier": brier / brier_n if brier_n else None,
        "by_edge": by_edge,
        "by_conf": by_conf,
        "market_su": {"right": mkt_su_right, "n": mkt_su_n},
    }


def correctness_score(stats: dict) -> dict | None:
    """One 0-100 number for how the model is doing, where 50 = the market.

    Scored against the market rather than against zero, because a raw hit rate
    flatters: picking every betting favourite wins most games, so a model can
    be "80% correct" and still worse than doing nothing. Each part is the
    model's result as a share of its benchmark, times 50, clamped to 0-100:

        winners  model straight-up rate / market favourite's straight-up rate
        margin   market MAE / model MAE        (lower error is better)
        spread   ATS win rate / break-even at -110

    The score is the mean of whichever parts have data. It is a summary for a
    dashboard, not a significance test: it carries the same sample-size
    problem as every number it is built from.
    """
    parts: dict[str, dict] = {}

    su, market_su = stats.get("su") or {}, stats.get("market_su") or {}
    if su.get("n") and market_su.get("n") and market_su.get("right"):
        model_rate = su["right"] / su["n"]
        market_rate = market_su["right"] / market_su["n"]
        parts["winners"] = {
            "value": 50 * model_rate / market_rate,
            "detail": f"picked {model_rate:.0%} of winners; the betting favourite won {market_rate:.0%}",
        }

    mae, market_mae = stats.get("mae"), stats.get("market_mae")
    if mae and market_mae:
        parts["margin"] = {
            "value": 50 * market_mae / mae,
            "detail": f"missed the final margin by {mae:.1f} pts on average; the line missed by {market_mae:.1f}",
        }

    ats = stats.get("ats") or {}
    if ats.get("decided"):
        rate = ats["win"] / ats["decided"]
        parts["spread"] = {
            "value": 50 * rate / BREAK_EVEN,
            "detail": f"covered {rate:.1%}; {BREAK_EVEN:.1%} breaks even at -110",
        }

    if not parts:
        return None
    for part in parts.values():
        part["value"] = round(max(0.0, min(100.0, part["value"])), 1)
    score = round(sum(p["value"] for p in parts.values()) / len(parts), 1)
    verdict = (
        "ahead of the market" if score >= 53
        else "roughly even with the market" if score >= 47
        else "behind the market"
    )
    return {"score": score, "verdict": verdict, "parts": parts}


def format_report(by_model: dict[str, dict], rows_by_model: dict[str, list]) -> str:
    from tabulate import tabulate

    out = []
    for version, stats in by_model.items():
        label = MODEL_LABELS.get(version, version)
        out.append(f"\n{'=' * 74}\n{label}  ({version})\n{'=' * 74}")
        if not stats["n"]:
            out.append("  nothing graded yet")
            continue

        su, ats = stats["su"], stats["ats"]
        out.append(f"  games graded            {stats['n']}")
        if su["n"]:
            out.append(
                f"  straight up             {su['right']}/{su['n']} = "
                f"{su['right'] / su['n'] * 100:.1f}%"
            )
        if ats["decided"]:
            z, p = _significance(ats["win"], ats["decided"])
            verdict = "SIGNIFICANT" if p < 0.05 else "not distinguishable from chance"
            out.append(
                f"  against the spread      {ats['win']}-{ats['loss']}"
                + (f"-{ats['push']} push" if ats["push"] else "")
                + f" = {ats['win'] / ats['decided'] * 100:.1f}%"
                f"   p={p:.3f}  {verdict}"
            )
        if stats["mae"] is not None:
            delta = stats["mae"] - (stats["market_mae"] or 0)
            out.append(
                f"  margin error (MAE)      {stats['mae']:.2f} pts"
                + (
                    f"   vs closing line {stats['market_mae']:.2f}"
                    f"  ({delta:+.2f}, {'better' if delta < 0 else 'worse'})"
                    if stats["market_mae"] is not None else ""
                )
            )
        if stats["brier"] is not None:
            out.append(
                f"  Brier score             {stats['brier']:.4f}"
                "   (0 = perfect, 0.25 = a coin flip)"
            )
        score = correctness_score(stats)
        if score:
            out.append(
                f"  correctness score       {score['score']:.0f}/100   "
                f"{score['verdict']} (50 = as good as the market)"
            )

        buckets = [(t, w, n) for t, (w, n) in sorted(stats["by_edge"].items()) if n]
        if buckets:
            table = []
            for threshold, wins, n in buckets:
                _z, p = _significance(wins, n)
                table.append([
                    f">= {threshold:.1f}", f"{wins}/{n}", f"{wins / n * 100:.1f}%",
                    f"{p:.3f}", "yes" if p < 0.05 else "no",
                ])
            out.append("\n  by edge size")
            out.append(
                "    " + tabulate(
                    table, headers=["Edge", "Record", "Win%", "p", "Beats -110?"],
                    tablefmt="simple",
                ).replace("\n", "\n    ")
            )

        if stats["by_conf"]:
            table = [
                [conf, f"{w}/{n}", f"{w / n * 100:.1f}%"]
                for conf, (w, n) in sorted(stats["by_conf"].items()) if n
            ]
            out.append("\n  by confidence tier")
            out.append(
                "    " + tabulate(
                    table, headers=["Tier", "Record", "Win%"], tablefmt="simple",
                ).replace("\n", "\n    ")
            )

    total = sum(s["ats"]["decided"] for s in by_model.values())
    out.append(f"\n{'-' * 74}")
    if total < 200:
        out.append(
            f"  {total} graded spread results is far too few to conclude anything. "
            "Distinguishing a\n  genuine 55% edge from a 50% coin flip takes several "
            "hundred games; a good weekend\n  and a lucky weekend look identical at "
            "this sample size."
        )
    else:
        out.append(
            f"  {total} graded spread results. Still treat a single season as "
            "provisional evidence."
        )
    return "\n".join(out)


def run(sport: str | None = None, model: str | None = None,
        since: date | None = None, refresh: bool = False) -> dict:
    store = db.get_store()

    if refresh:
        for target in ([sport] if sport else ["ncaaf", "nfl"]):
            try:
                n = refresh_scores(store, target)
                print(f"[grade] refreshed scores for {target} ({n} completed games seen)")
            except Exception as exc:  # noqa: BLE001
                print(f"  [warn] could not refresh {target} scores: {exc}")

    rows = grade(store, sport, model, since)
    print(f"[grade] {len(rows)} prediction(s) graded -> {store.backend}")

    rows_by_model: dict[str, list] = {}
    for row in rows:
        rows_by_model.setdefault(row["model_version"], []).append(row)
    by_model = {v: evaluate(rs) for v, rs in sorted(rows_by_model.items())}

    # Closing line value for every logged lean: the metric that becomes
    # readable long before the ATS record does (src/clv.py).
    clv_text = ""
    try:
        from . import clv

        clv_text = clv.report(clv.capture(sport, store))
    except Exception as exc:  # noqa: BLE001 - CLV must never block grading
        print(f"  [warn] CLV capture failed: {type(exc).__name__}: {exc}")

    store.close()
    if rows:
        print(format_report(by_model, rows_by_model))
    if clv_text:
        print(clv_text)
    else:
        print(
            "  No completed games with stored predictions yet. Run this after a "
            "slate finishes;\n  --refresh re-pulls final scores first."
        )
    return by_model


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Grade predictions against results.")
    parser.add_argument("--sport", choices=["ncaaf", "nfl"])
    parser.add_argument("--model", help="e.g. baseline-v1 or ml-v1")
    parser.add_argument("--since", help="only grade games on/after YYYY-MM-DD")
    parser.add_argument("--refresh", action="store_true", help="re-pull final scores first")
    args = parser.parse_args()
    run(
        args.sport,
        args.model,
        date.fromisoformat(args.since) if args.since else None,
        args.refresh,
    )
