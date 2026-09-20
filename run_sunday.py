"""A Sunday's inactives windows, in one command.

    python run_sunday.py                  refresh once, now
    python run_sunday.py --watch          wait for each window, refresh, repeat
    python run_sunday.py --plan           print the schedule and exit
    python run_sunday.py --date 2026-09-21
    python run_sunday.py --watch --no-explain --fresh-odds

P10: each team posts its inactive list about 90 minutes before its own
kickoff, so one refresh a day is not enough - a Sunday needs one per kickoff
window (early, late, night), each run after that window's lists post and
before its games start. Running earlier than that gets HTTP 404 and stores
nothing, which is a wasted refresh rather than a harmful one.

The windows are read from the day's actual kickoff times rather than
hardcoded, so a London morning game or a flexed start schedules itself.

Each window runs: grade finished games -> injuries (which pulls inactives)
-> weather -> odds -> re-predict -> re-simulate the games still to kick off
-> props -> dashboard. nflverse is deliberately not re-ingested: its play data
only changes after games finish, and it is the slowest step in the pipeline.
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from src import (
    config,
    db,
    export_dashboard,
    export_sims,
    grade,
    ingest_injuries,
    ingest_odds,
    ingest_props,
    ingest_weather,
    predict_baseline,
    predict_ml,
    props,
    simulate_nfl,
)
from src.features import parse_dt
from src.predict_baseline import slate_window

# The NFL deadline is 90 minutes before kickoff. Triggering at 75 leaves the
# list time to appear and the refresh time to finish before the games start.
LEAD_MINUTES = 75

# Two kickoffs further apart than this belong to different windows. The early
# and late slates are about three hours apart; games inside a slate differ by
# 20 minutes at most.
WINDOW_GAP_MINUTES = 75


@dataclass
class Window:
    """One kickoff cluster and the moment to refresh for it."""

    kickoff: datetime
    games: list[dict]

    @property
    def trigger(self) -> datetime:
        return self.kickoff - timedelta(minutes=LEAD_MINUTES)

    @property
    def label(self) -> str:
        n = len(self.games)
        return f"{_local(self.kickoff)} {_tz()} ({n} game{'s' if n != 1 else ''})"


def _tz() -> str:
    """CDT, rather than the "Central Daylight Time" Windows hands back."""
    name = datetime.now().astimezone().strftime("%Z")
    initials = "".join(w[0] for w in name.split() if w)
    return initials if len(name.split()) > 1 else name


def _local(when: datetime) -> str:
    return when.astimezone().strftime("%H:%M")


def _fmt(when: datetime) -> str:
    return f"{_local(when)} {_tz()} / {when.strftime('%H:%MZ')}"


def days_games(store: db.Store, target: date) -> list[dict]:
    """Every NFL game on this slate date, in kickoff order."""
    start, end = slate_window(target)
    games = [g for g in store.select("games", {"sport": "nfl"})
             if (k := parse_dt(g.get("kickoff_time"))) and start <= k < end]
    games.sort(key=lambda g: g["kickoff_time"])
    return games


def windows(games: list[dict]) -> list[Window]:
    """Cluster the day's kickoffs into windows."""
    out: list[Window] = []
    for game in games:
        kick = parse_dt(game.get("kickoff_time"))
        if kick is None:
            continue
        if out and kick - out[-1].kickoff <= timedelta(minutes=WINDOW_GAP_MINUTES):
            out[-1].games.append(game)
        else:
            out.append(Window(kick, [game]))
    return out


def lists_posted(store: db.Store, window: Window) -> tuple[int, int]:
    """(teams with a posted inactive list, teams in this window)."""
    ids = {g["game_id"] for g in window.games}
    rows = db.select_merged(store, "inactives", {"game_id": sorted(ids)})
    return len({(r["game_id"], r["team"]) for r in rows}), 2 * len(ids)


def step(name: str, fn, critical: bool = False) -> bool:
    """Run one step. A non-critical failure degrades the refresh, not stops it."""
    print()
    print("-" * 78)
    print(f"[{name}]")
    print("-" * 78)
    try:
        fn()
        return True
    except Exception:  # noqa: BLE001
        print(f"  [warn] {name} failed")
        traceback.print_exc(limit=3)
        if critical:
            print(f"  [stop] {name} is needed by the steps after it; skipping the rest")
        return False


def refresh(window: Window, target: date, args) -> None:
    print()
    print("=" * 78)
    print(f"REFRESH for kickoff {_fmt(window.kickoff)} | {len(window.games)} game(s)")
    for game in window.games:
        print(f"    {game['away_team']} @ {game['home_team']}")
    print(f"storage: {config.STORAGE_BACKEND} | model: {config.MODEL_VERSION}")
    print("=" * 78)

    step("grade", lambda: grade.run(sport="nfl", refresh=True))

    if step("injuries + inactives", lambda: ingest_injuries.run(sport="nfl")):
        store = db.get_store()
        try:
            posted, expected = lists_posted(store, window)
            if posted:
                print(f"\n  {posted}/{expected} team lists posted for this window")
            else:
                print("\n  [warn] no inactive list has posted for this window yet. The refresh "
                      "still runs, but questionable players keep the flat 0.55 play probability. "
                      "Re-run closer to kickoff.")
        finally:
            store.close()

    step("weather", lambda: ingest_weather.run(sport="nfl"))
    step("odds", lambda: ingest_odds.run("nfl", cache_minutes=0 if args.fresh_odds else None))

    if not step("predict", lambda: _predict(target), critical=True):
        return

    step("simulate", lambda: simulate_nfl.run(
        dates=[target], n=args.sims, quiet=True, upcoming_only=True))

    if not args.skip_props:
        step("props: pull lines", lambda: ingest_props.run(
            cache_minutes=0 if args.fresh_odds else None,
            only_games={g["game_id"] for g in window.games}))
        step("props: rank", lambda: props.run(with_explanations=not args.no_explain))

    step("export sims", lambda: export_sims.run(dates=[target.isoformat()], quiet=True))
    step("export dashboard", lambda: export_dashboard.run())

    print()
    print("=" * 78)
    print(f"REFRESH DONE  {_fmt(datetime.now(timezone.utc))}")
    print("=" * 78)


def _predict(target: date) -> None:
    baseline = predict_baseline.run(sport="nfl", dates=[target])
    if baseline:
        print()
        print(predict_baseline.format_report(baseline))
    try:
        ml = predict_ml.run("nfl", dates=[target])
    except SystemExit as exc:
        print(f"  [warn] ML layer unavailable: {exc}")
        return
    if ml:
        print()
        print("LAYER 3 - trained margin model")
        print(predict_ml.format_report(ml))


def sleep_until(when: datetime, label: str) -> None:
    """Wait, printing a countdown once a minute. Ctrl+C stops the watch."""
    while True:
        left = (when - datetime.now(timezone.utc)).total_seconds()
        if left <= 0:
            return
        if left > 3600:
            print(f"  waiting for {label}: {left / 3600:.1f} h (refresh at {_fmt(when)})")
        else:
            print(f"  waiting for {label}: {left / 60:.0f} min (refresh at {_fmt(when)})")
        time.sleep(min(left, 60))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the inactives refresh for each of a Sunday's kickoff windows.")
    parser.add_argument("--date", help="slate date, YYYY-MM-DD (default: today)")
    parser.add_argument("--watch", action="store_true",
                        help="wait for each remaining window and refresh automatically")
    parser.add_argument("--plan", action="store_true", help="print the schedule and exit")
    parser.add_argument("--sims", type=int, default=simulate_nfl.N_SIMS)
    parser.add_argument("--fresh-odds", action="store_true",
                        help="bypass the odds and props cache (costs quota)")
    parser.add_argument("--no-explain", action="store_true",
                        help="skip the Claude prop explanations (they cost a call per window)")
    parser.add_argument("--skip-props", action="store_true", help="no prop pull or ranking")
    args = parser.parse_args()

    target = date.fromisoformat(args.date) if args.date else datetime.now().date()

    store = db.get_store()
    try:
        games = days_games(store, target)
    finally:
        store.close()
    if not games:
        print(f"No NFL games on {target}.")
        return 1

    now = datetime.now(timezone.utc)
    all_windows = windows(games)
    live = [w for w in all_windows if w.kickoff > now]

    print(f"NFL {target}: {len(games)} game(s) in {len(all_windows)} kickoff window(s)")
    for w in all_windows:
        if w.kickoff <= now:
            state = "kicked off"
        elif w.trigger <= now:
            state = "READY NOW"
        else:
            state = f"refresh at {_fmt(w.trigger)}"
        print(f"  {w.label:<22} kickoff {_fmt(w.kickoff):<22} {state}")

    if args.plan:
        return 0
    if not live:
        print("\nEvery window has kicked off; nothing left to refresh.")
        return 1

    if not args.watch:
        # One pass, for the next window still to start.
        window = live[0]
        if window.trigger > now:
            mins = (window.trigger - now).total_seconds() / 60
            print(f"\n[note] {mins:.0f} min early for this window - lists may not have posted. "
                  f"Use --watch to run at {_fmt(window.trigger)} instead.")
        refresh(window, target, args)
        return 0

    print(f"\nWatching {len(live)} window(s). Ctrl+C to stop.")
    for window in live:
        try:
            if window.trigger > datetime.now(timezone.utc):
                sleep_until(window.trigger, window.label)
            if window.kickoff <= datetime.now(timezone.utc):
                print(f"\n[skip] {window.label} kicked off while an earlier refresh was running")
                continue
            refresh(window, target, args)
        except KeyboardInterrupt:
            print("\n[stopped] watch cancelled")
            return 1
    print("\nAll windows done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
