"""Tests for the live tracker's parsing, clock maths and divergence flags.

    python -m tests.test_live

No network: ESPN payloads are hand-built in the shape the live endpoint
returned on 2026-09-13, and the simulated distribution is built from a
hand-made set of simulated games whose percentiles are known exactly.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np

from src import db
from src.live_tracker import (
    LiveState, Pregame, elapsed_minutes, evaluate, new_alerts, parse_scoreboard,
    parse_event, percentile, quantile, recent_scoring, scoring_path, yardline_100,
)
from src.simulate import CHECKPOINTS, SimResult, pace_distribution

PASS, FAIL = 0, 0


def check(label: str, got, want) -> None:
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got {got!r}, want {want!r}")


def event(home=("LV", "13", "17"), away=("MIA", "15", "3"), state="in", period=2, clock=51.0,
          possession="15", name="STATUS_IN_PROGRESS", wp=0.8988):
    def side(where, t):
        return {"homeAway": where, "score": t[2], "team": {"id": t[1], "abbreviation": t[0]}}
    return {
        "id": "401872928", "date": "2026-09-13T20:25Z",
        "competitions": [{
            "status": {"clock": clock, "displayClock": "0:51", "period": period,
                       "type": {"name": name, "state": state, "shortDetail": "0:51 - 2nd"}},
            "competitors": [side("home", home), side("away", away)],
            "situation": {"possession": possession, "downDistanceText": "2nd & 10 at LV 49",
                          "isRedZone": False, "lastPlay": {"probability": {"homeWinPercentage": wp}}},
        }],
    }


def test_parse_scoreboard():
    states, skipped = parse_scoreboard({"season": {"type": 2}, "events": [event(), {"id": "bad"}]})
    s = states[0]
    check("one good event, one skipped", (len(states), skipped), (1, 1))
    check("scores", (s.home, s.home_score, s.away, s.away_score), ("LV", 17, "MIA", 3))
    check("possession mapped from ESPN team id", s.possession, "MIA")
    check("ESPN win probability", s.espn_home_wp, 0.8988)
    check("kickoff parsed", s.start.isoformat(), "2026-09-13T20:25:00+00:00")


def test_team_aliases():
    states, _ = parse_scoreboard({"events": [event(home=("PHI", "21", "14"), away=("WSH", "28", "3")),
                                             event(home=("LAR", "14", "0"), away=("SF", "25", "0"))]})
    check("WSH -> WAS", states[0].away, "WAS")
    check("LAR -> LA", states[1].home, "LA")


def test_field_position():
    # Cases read off the live scoreboard on 2026-09-13.
    check("home side, own 12 (LAC 12)", yardline_100("LAC 12", "LAC", "ARI", 12, 0), 88)
    check("home side, opponent's 12 (MIA 12)", yardline_100("MIA 12", "LV", "MIA", 88, 0), 12)
    check("away side, own 47 (WSH 47)", yardline_100("WSH 47", "WSH", "PHI", 53, 1), 53)
    check("midfield", yardline_100("50", "GB", "MIN", 50, 1), 50)
    check("unknown code falls back: away at own 35", yardline_100("ARZ 35", "ARI", "LAC", 65, 1), 65)
    check("no text: home side counts from its own goal line", yardline_100(None, "LAC", "ARI", 30, 0), 70)
    check("nothing usable", yardline_100(None, "LAC", "ARI", 0, 0), None)


def test_home_possession_from_scoreboard():
    e = event(home=("LAC", "24", "14"), away=("ARI", "22", "16"), possession="24")
    e["competitions"][0]["situation"].update(
        {"down": 1, "distance": 10, "yardLine": 12, "possessionText": "LAC 12"})
    s = parse_event(e)
    check("LAC ball at its own 12 is 88 yards from scoring",
          s.situation, {"possession": 0, "down": 1, "togo": 10, "yardline_100": 88})


def test_unusable_payloads():
    check("None (failed request)", parse_scoreboard(None), ([], 0))
    check("an HTML error page parsed as text", parse_scoreboard("<html>"), ([], 0))
    check("no events key", parse_scoreboard({}), ([], 0))
    check("summary that failed", recent_scoring(None), None)


def test_elapsed_minutes():
    check("kickoff", elapsed_minutes(1, 900), 0.0)
    check("0:51 left in the 2nd", elapsed_minutes(2, 51), 29.15)
    check("halftime", elapsed_minutes(2, 0, "STATUS_HALFTIME"), 30.0)
    check("end of regulation", elapsed_minutes(4, 0), 60.0)
    check("5:00 left in regular-season OT", elapsed_minutes(5, 300), 65.0)
    check("5:00 left in playoff OT", elapsed_minutes(5, 300, postseason=True), 70.0)
    check("not started", elapsed_minutes(0, 0), 0.0)


def test_recent_scoring():
    summary = {"scoringPlays": [
        {"period": {"number": 1}, "clock": {"displayValue": "9:02"}, "team": {"abbreviation": "WSH"},
         "type": {"text": "Field Goal"}, "text": "FG", "homeScore": 0, "awayScore": 3},
        {"period": {"number": 2}, "clock": {"displayValue": "1:07"}, "team": {"abbreviation": "PHI"},
         "type": {"text": "Passing Touchdown"}, "text": "TD", "homeScore": 7, "awayScore": 3},
    ]}
    plays = recent_scoring(summary)
    check("newest first", [p["clock"] for p in plays], ["1:07", "9:02"])
    check("team codes normalized", plays[1]["team"], "WAS")


def test_scoring_path():
    summary = {"scoringPlays": [
        {"period": {"number": 1}, "clock": {"value": 542.0}, "homeScore": 0, "awayScore": 3},
        {"period": {"number": 2}, "clock": {"value": 67.0}, "homeScore": 7, "awayScore": 3},
        {"period": {"number": 2}, "clock": {}, "homeScore": 9, "awayScore": 3},   # no clock: skipped
    ]}
    path = scoring_path(summary)
    check("minutes elapsed at each score", [p["t"] for p in path], [5.97, 28.88])
    check("score after each play", [(p["away"], p["home"]) for p in path], [(3, 0), (3, 7)])
    check("failed summary", scoring_path(None), None)


def _pace():
    """100 simulated games: at 5 minutes half are 0-0 and half 7-0 home; from
    10 minutes on, totals are spread evenly over 0..29 and margins over -9..+9."""
    n, k = 100, len(CHECKPOINTS)
    cp = np.zeros((n, k, 2), dtype=np.int32)
    cp[50:, 1, 0] = 7
    for j in range(2, k):
        home = np.arange(n) % 30
        cp[:, j, 0] = np.maximum(home, cp[:, j - 1, 0])
    for j in range(2, k):
        cp[:, j, 1] = 0
    r = SimResult(points=cp[:, -1], tds=np.zeros((n, 2), int), fgs=np.zeros((n, 2), int),
                  td_events=np.zeros((n, 12), int), return_tds=np.zeros((n, 2), int),
                  overtime=np.zeros(n, bool), possessions=np.zeros((n, 2), int), tilt=(0, 0),
                  checkpoints=cp)
    return pace_distribution(r)


def test_percentiles_are_mid_ranked():
    pace = _pace()
    check("0 pts at 5 min: half the sims are lower-or-equal", percentile(pace, "total", 5, 0), 0.25)
    check("7 pts at 5 min", percentile(pace, "total", 5, 7), 0.75)
    check("3 pts at 5 min sits between the two", percentile(pace, "total", 5, 3), 0.5)
    check("14 pts at 5 min is off the top", percentile(pace, "total", 5, 14), 1.0)
    check("halfway between checkpoints interpolates", round(percentile(pace, "total", 2.5, 0), 4), 0.375)
    check("median total at 5 min", quantile(pace, "total", 5, 0.5), 0)
    check("overtime uses the end-of-regulation distribution",
          percentile(pace, "total", 64, 45), percentile(pace, "total", 60, 45))


def _pregame(margin=13.0, pace=None):
    return Pregame("2026_01_WAS_PHI", "PHI", "WAS", None, margin_home=margin,
                   sim={"pace": pace, "median_home": 27, "median_away": 14} if pace else None)


def _live(home, away, period=2, clock=300.0):
    return LiveState("1", "in", "STATUS_IN_PROGRESS", period, clock, "5:00", "5:00 - 2nd", None,
                     "PHI", "WAS", home, away)


def codes(ev):
    return sorted((f["code"], f["level"]) for f in ev["flags"])


def test_underdog_flag():
    check("underdog up 7 is not 'more than 7'", codes(evaluate(_live(7, 14), _pregame())), [])
    check("underdog up 10 in the 2nd", codes(evaluate(_live(7, 17), _pregame())), [("underdog_leading", "notable")])
    check("same lead in the 4th is extreme",
          codes(evaluate(_live(7, 17, period=4), _pregame())), [("underdog_leading", "extreme")])
    check("a two-score-plus lead is extreme at once",
          codes(evaluate(_live(3, 17), _pregame())), [("underdog_leading", "extreme")])
    check("a pick'em has no underdog", codes(evaluate(_live(0, 21), _pregame(margin=0.3))), [])
    check("the favourite leading is fine", codes(evaluate(_live(21, 0), _pregame())), [])


def test_pace_and_margin_flags():
    pace = _pace()
    ev = evaluate(_live(40, 10, period=3, clock=900.0), _pregame(pace=pace))   # 30 min, total 50
    check("50 pts where every sim had under 30 is extreme",
          [c for c in codes(ev) if c[0].startswith("pace")], [("pace_high", "extreme")])
    check("home +30 where sims topped out at +29 is extreme",
          [c for c in codes(ev) if c[0].startswith("margin")], [("margin_home", "extreme")])
    check("projection adds the typical remaining points", ev["projected_total"], 50.0)
    early = evaluate(_live(14, 0, period=1, clock=780.0), _pregame(pace=pace))  # 2 min in
    check("no pace or margin flags in the first five minutes",
          [c for c in codes(early) if not c[0].startswith("underdog")], [])
    quiet = evaluate(_live(10, 5, period=3, clock=900.0), _pregame(pace=pace))
    check("an ordinary game raises nothing", codes(quiet), [])


def test_alert_dedupe():
    seen = {}
    notable = {"code": "pace_high", "level": "notable", "message": ""}
    extreme = {"code": "pace_high", "level": "extreme", "message": ""}
    check("first appearance alerts", len(new_alerts(seen, [notable])), 1)
    check("the same flag next poll is quiet", len(new_alerts(seen, [notable])), 0)
    check("escalation alerts again", len(new_alerts(seen, [extreme])), 1)
    check("falling back to notable is quiet", len(new_alerts(seen, [notable])), 0)
    check("a different flag still alerts",
          len(new_alerts(seen, [{"code": "underdog_leading", "level": "notable", "message": ""}])), 1)


def test_startup_survives_database_errors():
    """A 504 from the database at startup is retried, and a database that
    stays down falls back to the local mirror instead of killing the run."""
    import src.live_tracker as lt

    class Hosted:
        backend = "supabase"

    calls = {"n": 0}

    def flaky(store, sport, fail_times):
        calls["n"] += 1
        if store.backend != "sqlite" and calls["n"] <= fail_times:
            raise RuntimeError("504 Gateway Timeout")
        return f"context from {store.backend}"

    saved = (lt.db.get_store, lt.FeatureContext, lt.time.sleep, lt.db.SqliteStore)
    try:
        lt.db.get_store = lambda: Hosted()
        lt.time.sleep = lambda s: None
        with tempfile.TemporaryDirectory() as tmp:
            lt.db.SqliteStore = lambda: saved[3](path=Path(tmp) / "t.db")
            lt.FeatureContext = lambda store, sport: flaky(store, sport, 2)
            t = lt.Tracker.__new__(lt.Tracker)
            t.store = Hosted()
            check("two 504s, then success on the third try", t._load_context(), "context from supabase")
            calls["n"] = 0
            lt.FeatureContext = lambda store, sport: flaky(store, sport, 99)
            t = lt.Tracker.__new__(lt.Tracker)
            t.store = Hosted()
            check("still down after every retry: local mirror", t._load_context(), "context from sqlite")
            check("and the session keeps using it", t.store.backend, "sqlite")
            t.store.close()
    finally:
        lt.db.get_store, lt.FeatureContext, lt.time.sleep, lt.db.SqliteStore = saved


def test_storage_roundtrip():
    row = {"game_id": "G", "polled_at": "2026-09-13T21:40:00+00:00", "home_score": 17, "away_score": 3,
           "is_red_zone": True, "flags": [{"code": "pace_high", "level": "notable", "message": "m"}],
           "alerted": True, "recent_scoring": [], "pregame": {"model": "baseline-v1"}}
    with tempfile.TemporaryDirectory() as tmp:
        store = db.SqliteStore(path=Path(tmp) / "t.db")
        store.upsert("live_tracking", [row, {**row, "polled_at": "2026-09-13T21:42:30+00:00", "home_score": 24}])
        got = sorted(store.select("live_tracking", {"game_id": "G"}), key=lambda r: r["polled_at"])
        store.close()
    check("every poll is its own snapshot", [r["home_score"] for r in got], [17, 24])
    check("flags survive as JSON", '"pace_high"' in got[0]["flags"], True)


if __name__ == "__main__":
    for fn in [
        test_parse_scoreboard, test_team_aliases, test_field_position, test_home_possession_from_scoreboard,
        test_unusable_payloads, test_elapsed_minutes,
        test_recent_scoring, test_scoring_path, test_percentiles_are_mid_ranked, test_underdog_flag,
        test_pace_and_margin_flags, test_alert_dedupe, test_startup_survives_database_errors,
        test_storage_roundtrip,
    ]:
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
