"""Tests for player stat tracking and projected box scores.

    python -m tests.test_box_score

No network. The engine runs on the hand-built play libraries from
tests.test_simulate, turned into all-pass or all-run libraries so every
stat's total is known exactly.
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from src.box_score import POOL_CATEGORIES, box_score, passer_weights
from src.export_sims import attach_actuals
from src.sim_data import N_ZONE
from src.simulate import STAT_NAMES, Offense, PlayerPool, simulate_game
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


def stat_tables(passing: bool):
    """Every snap gains 15 official yards: all completions, or all runs."""
    t = tables()
    n = len(t.yards)
    t.stat_yards = np.full(n, 15, np.int16)
    t.is_rush = np.full(n, not passing)
    t.is_run = np.full(n, not passing)
    t.dropback = np.full(n, passing)
    t.complete = np.full(n, passing)
    t.attempt = np.full(n, passing)
    t.scramble = np.zeros(n, bool)
    t.interception = np.zeros(n, bool)
    t.deep = np.zeros(n, bool)
    return t


def pool():
    """QB (no carries or targets), then two players splitting everything."""
    return PlayerPool(names=["QB", "RB", "WR"], cum={c: np.cumsum([0.0, 0.5, 0.5]) for c in POOL_CATEGORIES},
                      passer_weights=np.array([1.0, 0.0, 0.0]))


def test_passing_game():
    r = simulate_game(stat_tables(True), Offense(0.0), Offense(0.0), n=300, seed=1, pools=(pool(), pool()))
    for side in (0, 1):
        st, tds = r.players[side], r.tds[:, side]
        check(f"side {side}: the quarterback throws every pass", int(st["pass_att"][:, 1:].sum()), 0)
        check(f"side {side}: one target per attempt", bool((st["tgt"].sum(1) == st["pass_att"].sum(1)).all()), True)
        check(f"side {side}: receiving yards equal passing yards",
              bool((st["rec_yds"].sum(1) == st["pass_yds"].sum(1)).all()), True)
        check(f"side {side}: every TD is a TD pass to one receiver",
              bool((st["pass_td"].sum(1) == tds).all() and (st["rec_td"].sum(1) == tds).all()), True)
        check(f"side {side}: no targets for a player with no target share", int(st["tgt"][:, 0].sum()), 0)
        yds = st["pass_yds"].sum(1)
        check(f"side {side}: a TD drive from the 30 is exactly 70 yards (+ unfinished drives)",
              bool((yds >= 70 * tds).all() and (yds < 70 * (tds + 3)).all()), True)


def test_throwaways_are_not_targets():
    """P27: an attempt with no intended receiver stays on the QB's line and is
    nobody's target. Every other attempt is still exactly one target, and the
    game itself does not change at all."""
    t = stat_tables(True)
    n = len(t.yards)
    # The fixture's drives live on 1st & 10; throw away every snap in one field zone.
    throwaway = np.arange(n) % N_ZONE == 3
    t.complete = ~throwaway            # throwaways are never completed
    base = simulate_game(t, Offense(0.0), Offense(0.0), n=300, seed=5, pools=(pool(), pool()))
    t.targeted = ~throwaway
    r = simulate_game(t, Offense(0.0), Offense(0.0), n=300, seed=5, pools=(pool(), pool()))
    for side in (0, 1):
        st, st0 = r.players[side], base.players[side]
        check(f"side {side}: fewer targets than attempts", int(st["tgt"].sum()) < int(st["pass_att"].sum()), True)
        check(f"side {side}: targets = attempts minus throwaways", int(st["tgt"].sum()),
              int(st0["tgt"].sum()) - (int(st0["pass_att"].sum()) - int(st0["pass_cmp"].sum())))
        check(f"side {side}: receptions and receiving yards unchanged",
              bool((st["rec"] == st0["rec"]).all() and (st["rec_yds"] == st0["rec_yds"]).all()), True)
        check(f"side {side}: passing line unchanged",
              all(bool((st[k] == st0[k]).all()) for k in ("pass_att", "pass_cmp", "pass_yds", "pass_td")), True)
    check("scores unchanged", bool((r.points == base.points).all()), True)


def test_running_game():
    r = simulate_game(stat_tables(False), Offense(0.0), Offense(0.0), n=300, seed=2, pools=(pool(), pool()))
    st = r.players[0]
    check("no passing in an all-run library", int(st["pass_att"].sum()), 0)
    check("every rushing TD credited to a runner", bool((st["rush_td"].sum(1) == r.tds[:, 0]).all()), True)
    check("no carries for a player with no carry share", int(st["rush_att"][:, 0].sum()), 0)
    split = st["rush_att"][:, 1].sum() / st["rush_att"].sum()
    check("carries split by share (50/50 here)", 0.45 < split < 0.55, True)


def test_passer_weights():
    squad = pd.DataFrame({"player": ["Starter", "Backup", "Back"], "position": ["QB", "QB", "RB"],
                          "rank": [1, 2, 1], "play_prob": [0.5, 1.0, 1.0]})
    check("questionable starter: half the games each", list(passer_weights(squad)), [0.5, 0.5, 0.0])
    squad.loc[0, "play_prob"] = 0.0
    check("starter out: the backup plays every game", list(passer_weights(squad)), [0.0, 1.0, 0.0])


def test_box_score_summary():
    n, rng = 1000, np.random.default_rng(0)
    stats = {k: np.zeros((n, 3), np.int32) for k in STAT_NAMES}
    stats["pass_att"][:, 0], stats["pass_cmp"][:, 0] = 30, 20
    stats["pass_yds"][:, 0] = rng.integers(150, 300, n)
    stats["rush_att"][:, 1] = 15
    stats["rush_yds"][:, 1] = rng.integers(40, 100, n)
    stats["rush_td"][:500, 1] = 1
    squad = pd.DataFrame({"player": ["QB", "RB", "Bench"], "position": ["QB", "RB", "WR"], "rank": [1, 1, 6]})
    box = box_score(stats, squad)
    check("players without meaningful usage are left out", [p["player"] for p in box["players"]], ["QB", "RB"])
    qb = box["players"][0]
    check("passing: most likely attempts", qb["passing"]["att"]["mode"], 30)
    q = qb["passing"]["yds"]
    check("quantiles ordered", q["p10"] <= q["p25"] <= q["median"] <= q["p75"] <= q["p90"], True)
    check("anytime TD", box["players"][1]["anytime_td"], 0.5)
    check("team passing yards summed", round(box["team"]["pass_yds"]["mean"]), round(stats["pass_yds"][:, 0].mean()))

    so_far = {k: np.zeros(3, np.int32) for k in STAT_NAMES}
    so_far["rush_att"][1], so_far["rush_yds"][1] = 8, 50
    rb = [p for p in box_score(stats, squad, so_far)["players"] if p["player"] == "RB"][0]
    check("live lines add what has already happened", rb["rushing"]["att"]["median"], 23.0)
    check("and record it", rb["so_far"], {"rush_att": 8, "rush_yds": 50})


def _actual(name, **kw):
    base = dict.fromkeys(("car", "tgt", "td", "rush_yds", "rush_td", "rec", "rec_yds", "rec_td",
                          "pass_att", "pass_cmp", "pass_yds", "pass_td", "pass_int"), 0)
    return {"name": name, **base, **kw}


def test_attach_actuals():
    pregame = {
        "box_score": {"home": {"players": [{"player": "Kenneth Walker III"}, {"player": "Inactive Guy"}]},
                      "away": {"players": []}},
        "scorers": {"home": [{"player": "Kenneth Walker III"}], "away": []},
    }
    actual = {"players": {
        "home": [_actual("Kenneth Walker", car=18, rush_yds=90, rush_td=1, td=1, tgt=2, rec=2, rec_yds=11),
                 _actual("Surprise Back", car=4, rush_yds=12)],
        "away": [],
    }}
    attach_actuals(pregame, actual, "KC", "DEN")
    walker, inactive = pregame["box_score"]["home"]["players"]
    check("suffix-insensitive match onto the projection", walker["actual"]["rushing"], {"att": 18, "yds": 90, "td": 1})
    check("receiving line too", walker["actual"]["receiving"], {"tgt": 2, "rec": 2, "yds": 11, "td": 0})
    check("a projected player with no stats is marked", inactive["actual"], {"td": 0, "no_stats": True})
    check("projected scorer marked as scoring", pregame["scorers"]["home"][0]["actual_tds"], 1)
    check("actual scorers listed", actual["scorers"]["home"], ["Kenneth Walker"])
    check("unprojected player surfaced", [u["name"] for u in actual["unprojected"]["home"]], ["Surprise Back"])


def test_export_keeps_the_weeks_earlier_slates():
    from datetime import datetime, timezone
    from src.export_sims import default_dates

    g = lambda gid, kick, week: {"game_id": gid, "kickoff_time": kick, "season": 2026, "week": week}  # noqa: E731
    games = [g("w1", "2026-09-14T00:20:00+00:00", 1), g("tnf", "2026-09-18T00:15:00+00:00", 2),
             g("sun", "2026-09-20T17:00:00+00:00", 2), g("mnf", "2026-09-22T00:15:00+00:00", 2),
             g("w3", "2026-09-25T00:15:00+00:00", 3)]
    friday = datetime(2026, 9, 19, 0, 30, tzinfo=timezone.utc)
    dates = default_dates(games, friday)
    check("Thursday's finished slate stays on the page", "2026-09-17" in dates, True)
    check("last week's slate does not", "2026-09-13" in dates, False)
    check("today and what is ahead are still there", dates[1:3], ["2026-09-18", "2026-09-20"])
    wednesday = datetime(2026, 9, 23, 18, tzinfo=timezone.utc)
    check("once the week is over it rolls to the next", "2026-09-17" in default_dates(games, wednesday), False)


def test_finished_weeks_are_archived():
    from datetime import datetime, timezone
    from src.export_sims import finished_weeks

    g = lambda gid, kick, week: {"game_id": gid, "kickoff_time": kick, "season": 2026, "week": week}  # noqa: E731
    games = [g("w1a", "2026-09-11T00:20:00+00:00", 1), g("w1b", "2026-09-15T00:15:00+00:00", 1),
             g("tnf", "2026-09-18T00:15:00+00:00", 2), g("mnf", "2026-09-22T00:15:00+00:00", 2),
             g("w0", "2026-09-01T00:15:00+00:00", 0)]
    friday = datetime(2026, 9, 19, 0, 30, tzinfo=timezone.utc)
    weeks = finished_weeks(games, {"w1a", "tnf", "mnf"}, friday)
    check("a week whose last game is over is archived", sorted(weeks), [(2026, 1)])
    check("with every game in it, simulated or not", sorted(x["game_id"] for x in weeks[(2026, 1)]), ["w1a", "w1b"])
    tuesday = datetime(2026, 9, 22, 12, tzinfo=timezone.utc)
    check("the week in progress joins once Monday night is over",
          sorted(finished_weeks(games, {"w1a", "tnf", "mnf"}, tuesday)), [(2026, 1), (2026, 2)])
    check("a week with no stored simulation is not archived", (2026, 0) in weeks, False)


if __name__ == "__main__":
    for fn in [test_passing_game, test_throwaways_are_not_targets, test_running_game, test_passer_weights, test_box_score_summary,
               test_attach_actuals, test_export_keeps_the_weeks_earlier_slates,
               test_finished_weeks_are_archived]:
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
