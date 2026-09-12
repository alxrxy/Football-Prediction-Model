"""End-to-end CFB pipeline for a single slate.

    python run_cfb_today.py                 today's slate
    python run_cfb_today.py --date 2026-09-19
    python run_cfb_today.py --fresh-odds    bypass the odds cache (costs quota)
    python run_cfb_today.py --skip-ingest   re-run predictions on stored data

Steps 2-4 of the architecture build order: CFBD ingestion -> odds + weather ->
baseline prediction (Layers 1+2+4).
"""

from __future__ import annotations

import argparse
import sys
import traceback
from datetime import date

from src import config, ingest_cfbd, ingest_odds, ingest_weather, predict_baseline


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the CFB prediction pipeline.")
    parser.add_argument("--date", help="slate date, YYYY-MM-DD (default: today UTC)")
    parser.add_argument("--fresh-odds", action="store_true", help="bypass odds cache")
    parser.add_argument("--skip-ingest", action="store_true", help="predict from stored data only")
    args = parser.parse_args()

    target = date.fromisoformat(args.date) if args.date else None

    print("=" * 78)
    print(f"FOOTBALL PREDICTOR - CFB pipeline | storage: {config.STORAGE_BACKEND} | model: {config.MODEL_VERSION}")
    print("=" * 78)

    if not args.skip_ingest:
        ingest_cfbd.run()
        print()

        # Weather and odds are independent of each other; a failure in either
        # degrades the prediction rather than stopping the run.
        for name, fn in (
            ("weather", lambda: ingest_weather.run(sport="ncaaf")),
            ("odds", lambda: ingest_odds.run("ncaaf", cache_minutes=0 if args.fresh_odds else None)),
        ):
            try:
                fn()
            except Exception:  # noqa: BLE001
                print(f"  [warn] {name} ingestion failed; continuing without it")
                traceback.print_exc(limit=2)
            print()

    predictions = predict_baseline.run(target)
    if not predictions:
        print("No predictions generated - check that the slate date has games loaded.")
        return 1

    print()
    print(predict_baseline.format_report(predictions))
    return 0


if __name__ == "__main__":
    sys.exit(main())
