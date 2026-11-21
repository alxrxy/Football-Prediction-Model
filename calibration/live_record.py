"""Live record of stored pregame predictions: winner accuracy, Brier, log loss, margin MAE, calibration.

    python calibration/live_record.py               # current season, both models
    python calibration/live_record.py --season 2026 --json out.json

READ-ONLY. The store is wrapped so that any write raises; nothing is graded, refreshed or stored
(unlike `python -m src.grade`, which writes final scores and grades).

What counts:
- a game with a final score in the store (`completed`) that did not end in a tie;
- its stored prediction for the model, only if `generated_at` is before the stored kickoff.
  Each (game, model) has one stored row, the last pregame run; earlier runs were overwritten.
- the market comparison uses the line stored with the prediction (the line at prediction time,
  not the close).

Finals come from the store as it stands: a game whose score has not been pulled yet is not counted.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import db  # noqa: E402
from src.features import parse_dt  # noqa: E402
from src.probe_inactives import ReadOnlyStore  # noqa: E402

BINS = ((0.50, 0.55), (0.55, 0.60), (0.60, 0.65), (0.65, 0.70), (0.70, 0.80), (0.80, 1.01))
MODELS = ("baseline-v1", "ml-v1")


def metrics(rows: list[dict]) -> dict:
    """rows: {p_home, home_won (0/1), margin_pred, margin_actual, market_spread (home line or None)}."""
    n = len(rows)
    if not n:
        return {"n": 0}
    acc = sum((r["p_home"] > 0.5) == (r["home_won"] == 1) for r in rows) / n
    brier = sum((r["p_home"] - r["home_won"]) ** 2 for r in rows) / n
    eps = 1e-6
    ll = -sum(r["home_won"] * math.log(max(r["p_home"], eps)) + (1 - r["home_won"]) * math.log(max(1 - r["p_home"], eps))
              for r in rows) / n
    mae = sum(abs(r["margin_pred"] - r["margin_actual"]) for r in rows) / n
    lined = [r for r in rows if r["market_spread"] is not None]
    fav = [r for r in lined if r["market_spread"] != 0]
    bins = []
    for lo, hi in BINS:
        b = [(max(r["p_home"], 1 - r["p_home"]), (r["home_won"] == 1) == (r["p_home"] > 0.5)) for r in rows
             if lo <= max(r["p_home"], 1 - r["p_home"]) < hi]
        if b:
            bins.append({"bin": f"{lo:.2f}-{min(hi, 1.0):.2f}", "n": len(b),
                         "mean_predicted": sum(x for x, _ in b) / len(b), "actual": sum(w for _, w in b) / len(b)})
    return {"n": n, "winner_accuracy": acc, "brier": brier, "log_loss": ll, "margin_mae": mae,
            "home_win_rate": sum(r["home_won"] for r in rows) / n,
            "n_with_line": len(lined),
            "market_margin_mae": sum(abs(-r["market_spread"] - r["margin_actual"]) for r in lined) / len(lined) if lined else None,
            "market_favourite_accuracy": (sum((-r["market_spread"] > 0) == (r["home_won"] == 1) for r in fav) / len(fav)) if fav else None,
            "calibration": bins}


def collect(store, season: int) -> tuple[dict[str, list[dict]], dict]:
    games = {g["game_id"]: g for g in store.select("games", {"sport": "nfl", "season": season})}
    preds = [p for p in store.select("predictions", {"sport": "nfl"}) if p["game_id"] in games]
    out: dict[str, list[dict]] = {m: [] for m in MODELS}
    info = {"games": len(games), "finals": sum(1 for g in games.values() if g.get("completed")),
            "stored_predictions": len(preds), "after_kickoff": 0, "ties": 0}
    predicted = set()
    for p in preds:
        g = games[p["game_id"]]
        if parse_dt(p["generated_at"]) >= parse_dt(g["kickoff_time"]):
            info["after_kickoff"] += 1
            continue
        predicted.add(p["game_id"])
        if p["model_version"] not in out or not g.get("completed") or g.get("home_points") is None:
            continue
        margin = g["home_points"] - g["away_points"]
        if margin == 0:
            info["ties"] += 1
            continue
        out[p["model_version"]].append({"p_home": p["model_win_prob_home"], "home_won": 1 if margin > 0 else 0,
                                        "margin_pred": p["model_margin_home"], "margin_actual": margin,
                                        "market_spread": p.get("market_spread")})
    info["finished_without_pregame_prediction"] = sorted(
        g["game_id"] for g in games.values() if g.get("completed") and g["game_id"] not in predicted)
    return out, info


def report(season: int, rows: dict[str, list[dict]], info: dict) -> str:
    lines = [f"Live record, NFL {season}: predictions stored before kickoff, graded on stored finals (read-only)",
             f"  games {info['games']}, finals in the store {info['finals']}, stored predictions {info['stored_predictions']} "
             f"({info['after_kickoff']} stamped after kickoff and excluded)",
             f"  finished games with no pregame prediction: {len(info['finished_without_pregame_prediction'])} "
             f"{info['finished_without_pregame_prediction']}", ""]
    for model, r in rows.items():
        m = metrics(r)
        if not m["n"]:
            lines.append(f"{model}: no graded pregame predictions")
            continue
        lines += [f"{model}: n = {m['n']}",
                  f"  winner accuracy  {m['winner_accuracy']:.3f}   (market favourite {m['market_favourite_accuracy']:.3f})",
                  f"  Brier score      {m['brier']:.4f}  (a constant 50% scores 0.2500)",
                  f"  log loss         {m['log_loss']:.4f}  (a constant 50% scores 0.6931)",
                  f"  margin MAE       {m['margin_mae']:.2f}    (the line stored with the prediction: {m['market_margin_mae']:.2f}, n = {m['n_with_line']})",
                  "  calibration, by confidence in the picked side:",
                  "    bin          n   predicted   actual"]
        lines += [f"    {b['bin']}  {b['n']:>4}      {b['mean_predicted']:.3f}    {b['actual']:.3f}" for b in m["calibration"]]
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Live record of stored pregame predictions (read-only).")
    ap.add_argument("--season", type=int, default=datetime.now(timezone.utc).year)
    ap.add_argument("--json", help="also write the numbers to this file")
    args = ap.parse_args()
    store = ReadOnlyStore(db.get_store())
    try:
        rows, info = collect(store, args.season)
    finally:
        store.close()
    print(report(args.season, rows, info))
    if args.json:
        Path(args.json).write_text(json.dumps({"season": args.season, "info": info,
                                               "models": {m: metrics(r) for m, r in rows.items()}}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
