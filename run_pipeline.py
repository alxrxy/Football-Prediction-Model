"""End-to-end pipeline for a slate.

    python run_pipeline.py                      today's CFB slate
    python run_pipeline.py --sport nfl          NFL, next slate with games
    python run_pipeline.py --sport both
    python run_pipeline.py --date 2026-09-13
    python run_pipeline.py --fresh-odds         bypass odds cache (costs quota)
    python run_pipeline.py --skip-ingest        re-predict from stored data

Steps 2-5 of the architecture build order.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from datetime import date, datetime, timedelta, timezone

from src import (
    config,
    db,
    grade,
    ingest_cfbd,
    ingest_injuries,
    ingest_nflverse,
    ingest_odds,
    ingest_weather,
    predict_baseline,
    predict_ml,
)
from src.features import parse_dt

SPORTS = {"ncaaf": "College football", "nfl": "NFL"}


def next_slate_date(sport: str) -> date:
    """The next date that actually has unplayed games for this sport.

    Beats defaulting to today: the NFL plays on a handful of days a week, so
    "today" is usually empty and would print an empty slate rather than the
    thing the user wants to see.
    """
    store = db.get_store()
    now = datetime.now(timezone.utc)
    upcoming = [
        k for g in store.select("games", {"sport": sport})
        if not g.get("completed") and (k := parse_dt(g.get("kickoff_time"))) and k >= now
    ]
    store.close()
    if not upcoming:
        return now.date()
    first = min(upcoming)
    # Mirror the slate window: a game before 11:00Z belongs to the previous day.
    return (first - timedelta(hours=predict_baseline.SLATE_START_UTC_HOUR)).date()


def run_sport(sport: str, target: date | None, args) -> list[dict]:
    print()
    print("=" * 78)
    print(f"{SPORTS[sport]} | storage: {config.STORAGE_BACKEND} | model: {config.MODEL_VERSION}")
    print("=" * 78)

    if not args.skip_ingest:
        if sport == "ncaaf":
            ingest_cfbd.run()
        else:
            ingest_nflverse.run()
        print()

        # Weather and odds are independent; failure in either degrades the
        # prediction rather than stopping the run.
        for name, fn in (
            ("weather", lambda: ingest_weather.run(sport=sport)),
            ("odds", lambda: ingest_odds.run(sport, cache_minutes=0 if args.fresh_odds else None)),
            ("injuries", lambda: ingest_injuries.run(sport=sport)),
        ):
            try:
                fn()
            except Exception:  # noqa: BLE001
                print(f"  [warn] {name} ingestion failed; continuing without it")
                traceback.print_exc(limit=2)
            print()

    if args.grade:
        # Grade before predicting: finished games are scored while their stored
        # pre-kickoff line is still the one they were predicted against.
        grade.run(sport=sport, refresh=True)
        print()

    slate = target or next_slate_date(sport)
    predictions = []

    if args.model in ("baseline", "both"):
        predictions = predict_baseline.run(slate, sport)
        if not predictions:
            print(f"No {SPORTS[sport]} games on {slate}.")
            return []
        print()
        print(predict_baseline.format_report(predictions))

    if args.model in ("ml", "both"):
        try:
            ml = predict_ml.run(sport, slate)
        except SystemExit as exc:
            print(f"  [warn] ML layer unavailable: {exc}")
            ml = []
        if ml:
            print()
            print("LAYER 3 - trained margin model")
            print(predict_ml.format_report(ml))
            predictions = predictions or ml

    return predictions


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the prediction pipeline.")
    parser.add_argument("--sport", default="ncaaf", choices=["ncaaf", "nfl", "both"])
    parser.add_argument("--date", help="slate date, YYYY-MM-DD (default: next slate with games)")
    parser.add_argument("--fresh-odds", action="store_true", help="bypass odds cache")
    parser.add_argument("--skip-ingest", action="store_true", help="predict from stored data only")
    parser.add_argument("--grade", action="store_true",
                        help="score finished games before predicting the next slate")
    parser.add_argument("--model", default="baseline", choices=["baseline", "ml", "both"],
                        help="which modeling layer to run")
    args = parser.parse_args()

    target = date.fromisoformat(args.date) if args.date else None
    sports = ["ncaaf", "nfl"] if args.sport == "both" else [args.sport]

    total = 0
    for sport in sports:
        total += len(run_sport(sport, target, args))
    return 0 if total else 1


if __name__ == "__main__":
    sys.exit(main())
