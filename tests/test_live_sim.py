"""Tests for the live-resume simulation.

    python -m tests.test_live_sim

No network. The engine runs on the hand-built play libraries from
tests.test_simulate, where every outcome is known in advance, and the ESPN
summaries are hand-built in the shape the live endpoint returned on
2026-09-13.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from src import db
from src.live_sim import ScoreMemory, blend_usage, describe, game_usage, kickoff_guard, live_start
from src.simulate import LiveStart, Offense, simulate_game
from tests.test_simulate import tables

PASS, FAIL = 0, 0


def check(label: str, got, want) -> None:
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got {got!r}, want {want!r}")


# --- the engine, resumed ---------------------------------------------------

def test_resume_carries_the_score_and_clock():
    """15 yards a snap: from here on each TD is exactly 7 and each FG 3 (a
    side in range with the clock nearly out kicks rather than snaps)."""
    start = LiveStart(elapsed_seconds=3000, home_points=21, away_points=14,
                      possession=1, yardline_100=75, down=1, togo=10)
    r = simulate_game(tables(), Offense(0.0), Offense(0.0), n=300, seed=1, start=start)
    check("nobody ends below the live score",
          bool((r.points[:, 0] >= 21).all() and (r.points[:, 1] >= 14).all()), True)
    check("only scoring from here is counted",
          bool(((r.points - [21, 14]) == 7 * r.tds + 3 * r.fgs).all()), True)
    check("checkpoints already passed hold the live score",
          bool((r.checkpoints[:, :11] == [21, 14]).all()), True)


def test_pending_extra_point_is_tried_first():
    """Nobody can score afterwards (every snap is a turnover), so the final
    score is the live score plus the try that was still to come."""
    start = LiveStart(elapsed_seconds=2400, home_points=20, away_points=14,
                      kickoff_receiver=1, pending_conversion=0)
    r = simulate_game(tables(turnover=True), Offense(0.0), Offense(0.0), n=200, seed=2, start=start)
    check("the PAT lands (always good in this library)", sorted({tuple(p) for p in r.points}), [(21, 14)])


def test_second_half_kickoff_goes_to_the_right_side():
    for receiver in (0, 1):
        start = LiveStart(elapsed_seconds=1800, home_points=13, away_points=10, second_half_receiver=receiver)
        r = simulate_game(tables(turnover=True), Offense(0.0), Offense(0.0), n=100, seed=3, start=start)
        lead = r.possessions[:, receiver] - r.possessions[:, 1 - receiver]
        check(f"side {receiver} receives, so never trails in possessions", bool(np.isin(lead, [0, 1]).all()), True)


def test_last_snap_decides_it():
    """Ten seconds left, down four, ball at the 10, 15 yards a snap: the
    trailing side scores on the only snap left, every time."""
    start = LiveStart(elapsed_seconds=3590, home_points=24, away_points=20,
                      possession=1, yardline_100=10, down=1, togo=10)
    r = simulate_game(tables(), Offense(0.0), Offense(0.0), n=200, seed=4, start=start)
    check("away wins every simulation", float((r.points[:, 1] > r.points[:, 0]).mean()), 1.0)
    check("and no game goes to overtime", bool(r.overtime.any()), False)


# --- reading the live state ------------------------------------------------

SIDES = {"13": 0, "15": 1}     # LV home, MIA away


def play(team, down, dist, to_endzone, kind="Rush", scoring=False):
    return {"type": {"text": kind}, "scoringPlay": scoring,
            "end": {"team": {"id": team}, "down": down, "distance": dist, "yardsToEndzone": to_endzone}}


def summary(plays=(), scoring=(), first_drive="15"):
    return {"drives": {"previous": [{"team": {"id": first_drive}}], "current": {"plays": list(plays)}},
            "scoringPlays": list(scoring)}


def test_scoreboard_situation_wins():
    start, source = live_start(1500, False, 17, 6,
                               {"possession": 1, "down": 2, "togo": 10, "yardline_100": 49}, summary(), SIDES)
    check("source", source, "scoreboard")
    check("state", (start.possession, start.yardline_100, start.down, start.togo), (1, 49, 2, 10))
    check("MIA took the opening kickoff, so LV gets the second half", start.second_half_receiver, 0)


def test_timeout_falls_back_to_the_last_snap():
    s = summary([play("13", 3, 7, 15, "Pass Reception"), play("13", -1, 0, 0, "Official Timeout")])
    start, source = live_start(2000, False, 23, 13, {}, s, SIDES)
    check("source", source, "last play")
    check("state after the last real snap", (start.possession, start.yardline_100, start.down, start.togo),
          (0, 15, 3, 7))


def test_touchdown_with_the_try_to_come():
    s = summary([play("13", -1, 0, 0, "Passing Touchdown", scoring=True), play("13", -1, 0, 0, "Timeout")],
                [{"team": {"id": "13"}, "type": {"text": "Passing Touchdown"},
                  "text": "Ashton Jeanty 13 Yd pass from Kirk Cousins"}])
    start, source = live_start(1700, False, 16, 3, {}, s, SIDES)
    check("source", source, "kickoff after a score")
    check("MIA receives; LV's try still to come", (start.kickoff_receiver, start.pending_conversion), (1, 0))


def test_touchdown_with_the_try_done():
    s = summary([play("13", -1, 0, 0, "Passing Touchdown", scoring=True)],
                [{"team": {"id": "13"}, "type": {"text": "Passing Touchdown"},
                  "text": "Ashton Jeanty 13 Yd pass from Kirk Cousins (Matt Gay Kick)"}])
    start, _ = live_start(1700, False, 17, 3, {}, s, SIDES)
    check("no conversion pending", (start.kickoff_receiver, start.pending_conversion), (1, None))


def test_safety_free_kick_goes_to_the_scorer():
    s = summary([play("13", -1, 0, 0, "Safety", scoring=True)],
                [{"team": {"id": "15"}, "type": {"text": "Safety"}, "text": "safety"}])
    start, _ = live_start(2500, False, 10, 12, {}, s, SIDES)
    check("MIA scored the safety and receives the free kick", (start.kickoff_receiver, start.pending_conversion), (1, None))


def test_halftime():
    start, source = live_start(1800, True, 13, 6, {}, summary(), SIDES)
    check("second-half kickoff to LV", (start.elapsed_seconds, start.kickoff_receiver), (1800.0, 0))
    check("source", source.startswith("halftime"), True)


def test_nothing_known():
    start, source = live_start(900, False, 0, 0, {}, None, SIDES)
    check("kickoff to a coin-flip receiver", (start.possession, start.kickoff_receiver), (None, None))
    check("says so", "unknown" in source, True)


def test_describe():
    check("own territory", describe(LiveStart(0, 0, 0, possession=0, yardline_100=75, down=1, togo=10), "LV", "MIA"),
          "LV ball, 1st & 10 at own 25")
    check("opponent territory", describe(LiveStart(0, 0, 0, possession=0, yardline_100=15, down=3, togo=7), "LV", "MIA"),
          "LV ball, 3rd & 7 at MIA 15")
    check("goal to go", describe(LiveStart(0, 0, 0, possession=1, yardline_100=5, down=1, togo=5), "LV", "MIA"),
          "MIA ball, 1st & goal at LV 5")
    check("kickoff with a try pending", describe(LiveStart(0, 0, 0, kickoff_receiver=1, pending_conversion=0), "LV", "MIA"),
          "kickoff to MIA, LV extra point still to come")


# --- P73: the kickoff guard --------------------------------------------------
# Cases rebuilt from stored live polls (live_simulations, live-v2): the start
# state each poll used, and the score at the poll before. Side 0 home, 1 away.

def snap(t, h, a, pos, yl, down, togo=10):
    return LiveStart(elapsed_seconds=t, home_points=h, away_points=a, possession=pos, yardline_100=yl,
                     down=down, togo=togo, second_half_receiver=0)


def guarded(start, memory, source="scoreboard"):
    out, src, mem = kickoff_guard(start, source, memory)
    return out, src, mem


def kicked(out):
    return (out.possession, out.down, out.kickoff_receiver, out.pending_conversion,
            out.home_points, out.away_points, out.elapsed_seconds)


def test_guard_kickoff_placeholder_after_a_score():
    # HOU @ IND wk3, 1:48 Q4: HOU (away) kicks a FG to lead 17-16; the scoreboard
    # shows HOU "1st & 10 at own 35" while it lines up to kick off.
    out, src, mem = guarded(snap(3492.0, 16, 17, 1, 65, 1), ScoreMemory(16, 10))
    check("HOU @ IND: kickoff to IND, no try pending", kicked(out), (None, None, 0, None, 16, 17, 3492.0))
    check("rule a named in the source", "P73 guard a" in src, True)
    check("memory: HOU scored 7 at 3492", (mem.scorer, mem.scored_at, mem.gained), (1, 3492.0, 7))
    # LA @ DEN wk3, 0:47 Q4: DEN (home) TD to 30-26, kicking from its own 40 after a penalty.
    out, _, _ = guarded(snap(3553.2, 30, 26, 0, 60, 1, 5), ScoreMemory(23, 26))
    check("LA @ DEN: own-40 placeholder becomes a kickoff to LA", kicked(out), (None, None, 1, None, 30, 26, 3553.2))


def test_guard_stale_scoring_snap():
    # WAS @ PHI wk1, 1:01 Q4: the score shows WAS's TD (16 -> 22), the situation is still the 3rd & goal at the 1.
    out, _, mem = guarded(snap(3538.8, 24, 22, 1, 1, 3, 1), ScoreMemory(24, 16))
    check("WAS @ PHI: kickoff to PHI, WAS try still to come", kicked(out), (None, None, 0, 1, 24, 22, 3538.8))
    # SEA @ WAS wk3, 2:55 Q4: SEA's TD (24 -> 30) on the board, still 1st & goal at the 7.
    out, _, _ = guarded(snap(3424.8, 33, 30, 1, 7, 1, 7), ScoreMemory(33, 24, 0, 3363.0, 6))
    check("SEA @ WAS: kickoff to WAS, SEA try still to come", kicked(out), (None, None, 0, 1, 33, 30, 3424.8))
    # DAL @ NYG wk1, 5:44 Q2: the summary lags; `last play` still shows DAL 2nd & goal at the 1.
    out, src, _ = guarded(snap(1456.2, 7, 6, 1, 1, 2, 1), ScoreMemory(7, 0), source="last play")
    check("DAL @ NYG: kickoff to NYG, DAL try still to come", kicked(out), (None, None, 0, 1, 7, 6, 1456.2))
    check("the original source is named", "last play showed the scorer" in src, True)


def test_guard_placeholder_repeated_at_the_same_clock():
    # WAS @ PHI wk1 (row 3): the poll after the stale snap, same clock, WAS at its own 35.
    out, _, mem = guarded(snap(3538.8, 24, 22, 1, 1, 3, 1), ScoreMemory(24, 16))
    out2, src2, _ = guarded(snap(3538.7999999999997, 24, 22, 1, 65, 1), mem)
    check("WAS @ PHI own 35, same clock: rule b, kickoff to PHI", kicked(out2),
          (None, None, 0, None, 24, 22, 3538.7999999999997))
    check("rule b named", "P73 guard b" in src2, True)
    # BAL @ ATL wk5 (row 1): BAL FG to 15-17 at 6:53 Q3, shown at its own 35 on two polls.
    _, _, mem = guarded(snap(2287.2, 17, 15, 1, 65, 1), ScoreMemory(17, 9))
    out, _, _ = guarded(snap(2287.2, 17, 15, 1, 65, 1), mem)
    check("BAL @ ATL 6:53 repeat: kickoff to ATL", kicked(out), (None, None, 0, None, 17, 15, 2287.2))


def test_guard_leaves_genuine_possessions_alone():
    # SF @ SEA wk5 (row 6): SEA TD at 556.8, then SEA ball at own 18 at 619.8 (SF's possession came between polls).
    _, _, mem = guarded(snap(556.8, 7, 7, 0, 65, 1), ScoreMemory(0, 7))
    start = snap(619.8, 7, 7, 0, 82, 1)
    out, src, _ = guarded(start, mem)
    check("SF @ SEA own 18 after the clock moved: unchanged", (out is start, src), (True, "scoreboard"))
    # DET @ ARI wk5 (row 8): DET TD, a kickoff to ARI, then DET ball at its own 24 a minute later.
    mem = ScoreMemory(7, 14, 1, 1230.0, 7)
    start = snap(1291.2, 7, 14, 1, 76, 1)
    check("DET @ ARI own 24: unchanged", guarded(start, mem)[0] is start, True)
    # BAL @ ATL wk5 OT (row 10): BAL TD at 4023.0, then BAL ball at its own 42 at 4075.2.
    mem = ScoreMemory(23, 30, 1, 4023.0, 7)
    start = snap(4075.2, 23, 30, 1, 58, 1)
    check("BAL @ ATL OT own 42: unchanged", guarded(start, mem)[0] is start, True)
    # A placeholder spot after the clock has moved is a real possession too.
    start = snap(2400.0, 17, 15, 1, 65, 1)
    check("own 35 after the clock moved: unchanged", guarded(start, ScoreMemory(17, 15, 1, 2287.2, 6))[0] is start, True)


def test_guard_second_half_and_overtime_starts():
    # DET @ BUF wk2 (row 11): DET receives the second half; DET scored last, before halftime.
    start = snap(1800.0, 27, 10, 1, 72, 2, 8)
    check("DET @ BUF Q3 15:00: unchanged", guarded(start, ScoreMemory(27, 10, 1, 1500.0, 7))[0] is start, True)
    # A score first seen at the start of the half, its scorer receiving: never guarded at 30:00 or 60:00.
    for t in (1800.0, 3600.0):
        start = snap(t, 10, 3, 0, 65, 1)
        check(f"score first seen at {t:.0f}s: unchanged", guarded(start, ScoreMemory(7, 3))[0] is start, True)


def test_guard_needs_memory_and_a_single_scorer():
    start = snap(3492.0, 16, 17, 1, 65, 1)
    out, src, mem = guarded(start, None)
    check("first poll, no memory: unchanged", (out is start, src), (True, "scoreboard"))
    check("and memory starts from this score", (mem.home_points, mem.away_points, mem.scorer), (16, 17, None))
    out, _, mem = guarded(start, ScoreMemory(13, 10))
    check("both sides scored between polls: unchanged", out is start, True)
    check("and no scorer is remembered", mem.scorer, None)
    kick = LiveStart(elapsed_seconds=1800.0, home_points=13, away_points=6, kickoff_receiver=0, second_half_receiver=0)
    check("halftime start: unchanged", guarded(kick, ScoreMemory(13, 6, 0, 1700.0, 3), "halftime")[0] is kick, True)
    after = LiveStart(elapsed_seconds=1700.0, home_points=16, away_points=3, kickoff_receiver=1, pending_conversion=0)
    check("kickoff after a score: unchanged", guarded(after, ScoreMemory(10, 3), "kickoff after a score")[0] is after, True)


def test_guard_memory_is_per_game():
    memory: dict = {}
    for gid, start in (("A", snap(3000.0, 7, 0, 0, 30, 2)), ("B", snap(3000.0, 0, 0, 1, 40, 1))):
        _, _, memory[gid] = kickoff_guard(start, "scoreboard", memory.get(gid))
    # Game B's next poll: a placeholder for side 0 with A's score would fire if memory leaked across games.
    start = snap(3000.0, 0, 0, 0, 65, 1)
    out, _, _ = kickoff_guard(start, "scoreboard", memory.get("B"))
    check("game B never saw a score: unchanged", out is start, True)
    check("game A remembers only its own score", (memory["A"].home_points, memory["A"].away_points), (7, 0))


# --- usage so far ----------------------------------------------------------

RUSH_KEYS = ["rushingAttempts", "rushingYards", "yardsPerRushAttempt", "rushingTouchdowns", "longRushing"]
REC_KEYS = ["receptions", "receivingYards", "yardsPerReception", "receivingTouchdowns", "longReception", "receivingTargets"]


def box(rushers, receivers=()):
    ath = lambda name, stats: {"athlete": {"displayName": name}, "stats": stats}  # noqa: E731
    return {"boxscore": {"players": [{"team": {"id": "13"}, "statistics": [
        {"name": "rushing", "keys": RUSH_KEYS, "athletes": [ath(n, s) for n, s in rushers]},
        {"name": "receiving", "keys": REC_KEYS, "athletes": [ath(n, s) for n, s in receivers]},
    ]}]}}


def squad_and_shares():
    squad = pd.DataFrame({"player": ["Starter Back", "Backup Back"], "position": ["RB", "RB"],
                          "rank": [1, 2], "play_prob": [1.0, 1.0]})
    shares = {"car_all": np.array([0.6, 0.4]), "car_rz": np.array([0.6, 0.4]), "car_gl": np.array([0.7, 0.3]),
              "tgt_all": np.array([0.5, 0.5]), "tgt_rz": np.array([0.5, 0.5]),
              "tgt_short": np.array([0.5, 0.5]), "tgt_deep": np.array([0.5, 0.5])}
    return squad, shares


def test_game_usage():
    usage = game_usage(box([("Backup Back", ["12", "70", "5.8", "1", "20"])],
                           [("Backup Back", ["1", "5", "5", "0", "5", "2"])]), SIDES)
    got = {k: usage[0]["Backup Back"][k] for k in ("car", "rush_yds", "tgt", "rec", "rec_yds", "td")}
    check("rushing and receiving merged per player",
          got, {"car": 12, "rush_yds": 70, "tgt": 2, "rec": 1, "rec_yds": 5, "td": 1})
    check("the other side is empty", usage[1], {})


def test_blend_leans_toward_who_is_getting_the_ball():
    squad, shares = squad_and_shares()
    usage = game_usage(box([("Starter Back", ["3", "10", "3.3", "0", "6"]),
                            ("Backup Back", ["12", "70", "5.8", "1", "20"])]), SIDES)[0]
    out_squad, out, info = blend_usage(squad, shares, usage, "LV")
    # 15 carries so far: the game's share carries 15 / (15 + 30) = 1/3 of the weight.
    check("live weight", info["car"]["live_weight"], 0.333)
    check("broad carry shares", [round(x, 4) for x in out["car_all"]], [0.4667, 0.5333])
    check("goal-line shares follow the same shift", [round(x, 4) for x in out["car_gl"]], [0.5765, 0.4235])
    check("no targets yet: receiving shares unchanged", [round(x, 4) for x in out["tgt_all"]], [0.5, 0.5])
    check("TDs so far recorded", list(out_squad["game_td"]), [0.0, 1.0])


def test_blend_adds_a_player_the_depth_chart_missed():
    squad, shares = squad_and_shares()
    usage = game_usage(box([("Starter Back", ["10", "40", "4", "0", "9"]),
                            ("Surprise Back", ["10", "50", "5", "0", "15"])]), SIDES)[0]
    out_squad, out, _ = blend_usage(squad, shares, usage, "LV")
    check("joins the squad", list(out_squad["player"]), ["Starter Back", "Backup Back", "Surprise Back"])
    # 20 carries: weight 0.4, his game share 0.5, pregame share 0.
    check("his carry share is all live", round(float(out["car_all"][2]), 4), 0.2)
    check("every category still sums to 1", all(abs(out[c].sum() - 1) < 1e-9 for c in out), True)


def test_storage_roundtrip():
    row = {"game_id": "G", "polled_at": "2026-09-13T22:20:00+00:00", "n_sims": 10000,
           "home_win_prob": 0.88, "start_state": {"description": "LV ball, 1st & 10 at own 25"},
           "scorers": {"confidence": "low", "home": []}}
    with tempfile.TemporaryDirectory() as tmp:
        store = db.SqliteStore(path=Path(tmp) / "t.db")
        store.upsert("live_simulations", [row, {**row, "polled_at": "2026-09-13T22:22:30+00:00", "home_win_prob": 0.9}])
        got = sorted(store.select("live_simulations", {"game_id": "G"}), key=lambda r: r["polled_at"])
        store.close()
    check("one projection per poll", [r["home_win_prob"] for r in got], [0.88, 0.9])
    check("start state survives as JSON", "own 25" in got[0]["start_state"], True)


if __name__ == "__main__":
    for fn in [
        test_resume_carries_the_score_and_clock, test_pending_extra_point_is_tried_first,
        test_second_half_kickoff_goes_to_the_right_side, test_last_snap_decides_it,
        test_scoreboard_situation_wins, test_timeout_falls_back_to_the_last_snap,
        test_touchdown_with_the_try_to_come, test_touchdown_with_the_try_done,
        test_safety_free_kick_goes_to_the_scorer, test_halftime, test_nothing_known, test_describe,
        test_guard_kickoff_placeholder_after_a_score, test_guard_stale_scoring_snap,
        test_guard_placeholder_repeated_at_the_same_clock, test_guard_leaves_genuine_possessions_alone,
        test_guard_second_half_and_overtime_starts, test_guard_needs_memory_and_a_single_scorer,
        test_guard_memory_is_per_game,
        test_game_usage, test_blend_leans_toward_who_is_getting_the_ball,
        test_blend_adds_a_player_the_depth_chart_missed, test_storage_roundtrip,
    ]:
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
