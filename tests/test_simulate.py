"""Tests for the game simulator's mechanics.

    python -m tests.test_simulate

No network: the engine runs on small hand-built play libraries whose outcomes
are known in advance, so every scoring rule can be checked exactly.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from src import db
from src.sim_data import N_BUCKETS, N_PUNT_BINS, USAGE_CATEGORIES, SimTables, bucket_index
from src.simulate import Offense, allocate_scorers, simulate_game, solve_tilt, summarize
from src.simulate_nfl import injury_split, team_shares

PASS, FAIL = 0, 0


def check(label: str, got, want) -> None:
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got {got!r}, want {want!r}")


def tables(yards=15, turnover=False, epa=None) -> SimTables:
    """One play per bucket, every one identical: gains `yards`, takes 20s."""
    n = N_BUCKETS
    bucket = np.arange(n)
    punts = N_PUNT_BINS
    return SimTables(
        bucket=bucket, offsets=np.arange(n + 1), bucket_map=np.arange(n),
        yards=np.full(n, yards, np.int16),
        epa=np.zeros(n) if epa is None else epa,
        duration=np.full(n, 20.0, np.float32),
        off_td=np.zeros(n, bool), def_td=np.zeros(n, bool),
        turnover=np.full(n, turnover), fd_penalty=np.zeros(n, bool),
        is_penalty=np.zeros(n, bool), is_rush=np.ones(n, bool),
        dropback=np.zeros(n, bool), is_run=np.ones(n, bool),
        next_start=np.full(n, np.nan, np.float32), yl_orig=np.full(n, 50, np.int16),
        pass_frac=np.full(n, 0.5),
        punt_offsets=np.arange(punts + 1), punt_bin_map=np.arange(punts),
        punt_start=np.full(punts, 80, np.int16), punt_ret_td=np.zeros(punts, bool),
        ko_start=np.array([70], np.int16), ko_ret_td=np.array([False]),
        fg_beta=np.array([50.0, 0.0, 0.0, 0.0]),   # every kick good
        pat_make=1.0, two_pt_rate=0.0, two_pt_success=0.0,
        fourth=np.tile([1.0, 0.0, 0.0], (punts, 5, 1)),   # always go
        league_epa=0.0,
    )


def test_every_drive_scores():
    """15 yards a snap from the 30 always reaches the end zone."""
    r = simulate_game(tables(), Offense(0.0), Offense(0.0), n=500, seed=3)
    check("points are exactly 7 per TD", bool((r.points == 7 * r.tds).all()), True)
    check("no field goals", int(r.fgs.sum()), 0)
    check("every TD is a goal-line/red-zone/open rushing TD",
          bool((r.td_events.sum(axis=1) == r.tds.sum(axis=1)).all()), True)
    both = r.possessions.sum(axis=1)
    check("possessions alternate", bool((np.abs(r.possessions[:, 0] - r.possessions[:, 1]) <= 1).all()), True)
    check("games are finite", bool((both > 5).all() and (both < 60).all()), True)


def test_turnover_every_snap():
    """Nobody can score; every regulation game ends 0-0 and goes to OT."""
    r = simulate_game(tables(turnover=True), Offense(0.0), Offense(0.0), n=200, seed=4)
    check("nobody scores", int(r.points.sum()), 0)
    check("every game reaches overtime", bool(r.overtime.all()), True)


def test_overtime_both_possess():
    """With every drive a TD, OT can only end after both sides have scored
    once, so no OT game may finish 7 points apart with one OT possession each."""
    r = simulate_game(tables(), Offense(0.0), Offense(0.0), n=2000, seed=5)
    ot = r.overtime
    check("overtime happened", bool(ot.any()), True)
    check("an OT game is never decided by the opening possession alone",
          bool((r.points[ot, 0] != r.points[ot, 1]).all()), True)


def test_field_goals_when_stalled():
    """2 yards a snap with a 4th-down table that always kicks from range."""
    t = tables(yards=2)
    t.fourth = np.tile([0.0, 1.0, 0.0], (N_PUNT_BINS, 5, 1))
    r = simulate_game(t, Offense(0.0), Offense(0.0), n=300, seed=6)
    check("points are exactly 3 per FG plus 7 per TD",
          bool((r.points == 3 * r.fgs + 7 * r.tds).all()), True)
    check("field goals happen", bool(r.fgs.sum() > 0), True)


def test_checkpoints_track_the_score():
    r = simulate_game(tables(), Offense(0.0), Offense(0.0), n=300, seed=9)
    cp = r.checkpoints
    check("checkpoint 0 is 0-0", int(cp[:, 0].sum()), 0)
    check("scores never fall between checkpoints", bool((np.diff(cp, axis=1) >= 0).all()), True)
    reg = ~r.overtime
    check("the 60-minute checkpoint is the final score without OT",
          bool((cp[reg, -1] == r.points[reg]).all()), True)
    pace = summarize(r)["pace"]
    check("every pace CDF ends at 1", all(abs(c[-1] - 1) < 1e-9 for c in pace["total_cdf"] + pace["margin_cdf"]), True)


def test_tilt_hits_target():
    rng = np.random.default_rng(0)
    epa = rng.normal(0, 1.3, 20_000)
    base = np.ones_like(epa)
    for target in (-0.10, 0.0, 0.08):
        lam = solve_tilt(epa, base, target)
        w = np.exp(lam * epa)
        check(f"tilted mean hits {target:+.2f}", round(float((w * epa).sum() / w.sum()), 6), target)


def test_segment_cdf_stays_in_bucket():
    t = tables()
    rng = np.random.default_rng(1)
    t.epa = rng.normal(0, 1, N_BUCKETS)
    cdf = t.segment_cdf(np.exp(0.3 * t.epa))
    b = rng.integers(0, N_BUCKETS, 50_000)
    rows = np.searchsorted(cdf, b + rng.random(len(b)), side="right")
    check("every draw lands in its own bucket", bool((t.bucket[rows] == b).all()), True)


def test_bucket_index():
    check("1st & 10 at own 25", int(bucket_index(1, 10, 75)), (0 * 5 + 3) * 6 + 4)
    check("4th & 1 at the 3 shares 3rd-down pool", int(bucket_index(4, 1, 3)), int(bucket_index(3, 1, 3)))


def test_scorer_allocation_conserves_tds():
    r = simulate_game(tables(), Offense(0.0), Offense(0.0), n=400, seed=7)
    shares = {c: np.array([0.6, 0.3, 0.1]) for c in ("tgt_all", "tgt_rz", "car_all", "car_rz", "car_gl")}
    counts = allocate_scorers(r, 0, shares, seed=1)
    check("every home offensive TD goes to exactly one player",
          bool((counts.sum(axis=1) == r.td_events[:, :6].sum(axis=1)).all()), True)


def test_summary_shapes():
    s = summarize(simulate_game(tables(), Offense(0.0), Offense(0.0), n=300, seed=8))
    check("win + loss + tie = 1", round(s["home_win"] + s["away_win"] + s["tie"], 9), 1.0)
    check("quantiles are ordered", s["total"]["p10"] <= s["total"]["p50"] <= s["total"]["p90"], True)


def _roles():
    cats = {c: 0.0 for c in USAGE_CATEGORIES}
    rows = [
        dict(team="KC", player="Starter Back", position="RB", rank=1, **{**cats, "car_all": 0.6, "car_gl": 0.7}),
        dict(team="KC", player="Backup Back", position="RB", rank=2, **{**cats, "car_all": 0.2, "car_gl": 0.1}),
        dict(team="KC", player="Third Back", position="RB", rank=3, **{**cats, "car_all": 0.2, "car_gl": 0.2}),
    ]
    return pd.DataFrame(rows)


def test_injured_starter_shifts_to_next_man():
    injuries = [{"team": "KC", "player": "Starter Back", "status": "out", "play_probability": 0.0}]
    squad, shares, shifts = team_shares(_roles(), "KC", injuries)
    gl = dict(zip(squad["player"], shares["car_gl"]))
    check("ruled-out starter keeps nothing", round(gl["Starter Back"], 6), 0.0)
    check("backup inherits the starter's goal-line work", round(gl["Backup Back"], 6), 0.8)
    check("third back is untouched", round(gl["Third Back"], 6), 0.2)
    check("shift is reported", [s["to"] for s in shifts], ["Backup Back"])


def test_questionable_starter_splits():
    injuries = [{"team": "KC", "player": "Starter Back", "status": "questionable", "play_probability": 0.5}]
    _squad, shares, _ = team_shares(_roles(), "KC", injuries)
    check("half the starter's share moves down one slot",
          [round(x, 6) for x in shares["car_gl"]], [0.35, 0.45, 0.2])


def test_suffix_names_match_injury_report():
    roles = _roles()
    roles.loc[0, "player"] = "Kenneth Walker III"
    injuries = [{"team": "KC", "player": "Kenneth Walker", "status": "out", "play_probability": 0.0}]
    _squad, shares, _ = team_shares(roles, "KC", injuries)
    check("'Walker III' on the chart matches 'Walker' on the report", round(float(shares["car_gl"][0]), 6), 0.0)


def test_depth_slot_governs_volume():
    from src.sim_data import USAGE_CATEGORIES, blend_roles

    depth = pd.DataFrame([
        dict(team="KC", player_id="qb1", player="Starter QB", position="QB", rank=1),
        dict(team="KC", player_id="qb2", player="Ex-Starter QB", position="QB", rank=2),
        dict(team="KC", player_id="wr1", player="Vet WR", position="WR", rank=1),
        dict(team="KC", player_id="wr2", player="Promoted WR", position="WR", rank=2),
        dict(team="KC", player_id="wr5", player="Demoted WR", position="WR", rank=5),
        dict(team="KC", player_id="rb1", player="Rookie RB", position="RB", rank=1),
        dict(team="KC", player_id="fb1", player="Fullback", position="FB", rank=1),
    ])

    def rate(v):
        return {**{c: v for c in USAGE_CATEGORIES}, "games": 17.0, "rz_targets": 0.0, "gl_carries": 0.0}

    rates = pd.DataFrame.from_dict(
        {"qb1": rate(0.10), "qb2": rate(0.25), "wr1": rate(0.25), "wr2": rate(0.05), "wr5": rate(0.15),
         "fb1": rate(0.04)},
        orient="index",
    )
    prior = lambda v: {c: v for c in USAGE_CATEGORIES}  # noqa: E731
    priors = {("QB", 1): prior(0.10), ("QB", 2): prior(0.01), ("WR", 1): prior(0.20),
              ("WR", 2): prior(0.18), ("WR", 5): prior(0.03), ("RB", 1): prior(0.50)}
    roles = blend_roles(depth, rates, priors).set_index("player_id")
    blend = lambda hist, pri: round((17 * hist + 4 * pri) / 21, 6)  # noqa: E731

    check("a backup QB who started elsewhere gets nothing", float(roles.loc["qb2", "car_gl"]), 0.0)
    # Beyond the slots own history counts at games/(games+32), still held
    # within 3x the slot norm: 0.15 is clipped to 0.09 (P25, k32+fb).
    check("beyond the playing slots, a small weight on own history",
          round(float(roles.loc["wr5", "tgt_rz"]), 6), round((17 * 0.09 + 32 * 0.03) / 49, 6))
    check("a fullback with no slot norm keeps his own history, not zero",
          round(float(roles.loc["fb1", "car_gl"]), 6), blend(0.04, 0.0))
    check("a starter keeps most of his own history",
          round(float(roles.loc["wr1", "tgt_rz"]), 6), blend(0.25, 0.20))
    check("a promoted receiver is lifted toward his new slot",
          round(float(roles.loc["wr2", "tgt_rz"]), 6), blend(0.09, 0.18))
    check("a rookie rides the slot norm", round(float(roles.loc["rb1", "car_gl"]), 6), 0.5)


def test_carry_shares_are_designed_runs_only():
    from src.sim_data import usage_rates

    def play(pid, **kw):
        base = dict(season=2025, game_id="g1", posteam="KC", yardline_100=50, air_yards=None,
                    pass_attempt=0, sack=0, receiver_player_id=None, passer_player_id=None,
                    rush_attempt=1, rusher_player_id=pid, qb_scramble=0, play_type="run")
        return {**base, **kw}

    pbp = pd.DataFrame(
        [play("rb")] * 3 + [play("qb")]
        + [play("qb", qb_scramble=1)] * 4 + [play("qb", play_type="qb_kneel")] * 2
    )
    rates = usage_rates(pbp, 2025)
    check("scrambles and kneels are not designed carries", round(float(rates.loc["qb", "car_all"]), 6), 0.25)
    check("the back's share is over designed runs", round(float(rates.loc["rb", "car_all"]), 6), 0.75)


def test_injury_split():
    detail = [{"position": "QB", "points": 4.0}, {"position": "CB", "points": 1.0},
              {"position": "K", "points": 1.0}]
    off, deff = injury_split(detail, -3.0)   # capped from 6.0 to 3.0
    check("offence share, scaled to the cap", round(off, 6), 2.0)
    check("defence share, scaled to the cap", round(deff, 6), 0.5)


def test_storage_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        store = db.SqliteStore(path=Path(tmp) / "t.db")
        row = {"game_id": "G", "sim_version": "sim-v1", "n_sims": 10,
               "td_scorers": {"confidence": "low", "home": []},
               "distributions": {"top_scores": []}, "components": {}, "generated_at": db.utcnow()}
        store.upsert("game_simulations", [row])
        store.upsert("game_simulations", [{**row, "n_sims": 20}])
        got = store.select("game_simulations")
        store.close()
    check("one row per (game, version)", len(got), 1)
    check("re-run overwrites", got[0]["n_sims"], 20)
    check("scorer confidence survives", '"low"' in got[0]["td_scorers"], True)


if __name__ == "__main__":
    for fn in [
        test_every_drive_scores, test_turnover_every_snap, test_overtime_both_possess,
        test_field_goals_when_stalled, test_checkpoints_track_the_score,
        test_tilt_hits_target, test_segment_cdf_stays_in_bucket,
        test_bucket_index, test_scorer_allocation_conserves_tds, test_summary_shapes,
        test_injured_starter_shifts_to_next_man, test_questionable_starter_splits,
        test_suffix_names_match_injury_report, test_depth_slot_governs_volume,
        test_carry_shares_are_designed_runs_only, test_injury_split, test_storage_roundtrip,
    ]:
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
