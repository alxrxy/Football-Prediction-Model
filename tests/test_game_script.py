"""Game-script play-calling in the simulator (P11 / research Stage 3).

    python -m tests.test_game_script

No network: a hand-built library with one run, one dropback and one no-play
penalty in every bucket, so the call the sampler makes can be counted.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.sim_data import (N_BUCKETS, N_PHASE, N_PUNT_BINS, N_SCRIPT, SimTables, _script_shift,
                          bucket_index, script_state)
from src.simulate import Offense, _Sampler

PASS, FAIL = 0, 0


def check(label: str, got, want, tol: float | None = None) -> None:
    global PASS, FAIL
    ok = abs(got - want) <= tol if tol is not None else got == want
    if ok:
        PASS += 1
        print(f"  ok    {label}: {got!r}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got {got!r}, want {want!r}" + (f" ± {tol}" if tol else ""))


def tables(shift: np.ndarray | None) -> SimTables:
    """Three plays per bucket: a run, a dropback, a no-play penalty."""
    n = 3 * N_BUCKETS
    kind = np.tile([0, 1, 2], N_BUCKETS)
    punts = N_PUNT_BINS
    return SimTables(
        bucket=np.repeat(np.arange(N_BUCKETS), 3), offsets=np.arange(0, n + 1, 3),
        bucket_map=np.arange(N_BUCKETS),
        yards=np.full(n, 5, np.int16), epa=np.zeros(n), duration=np.full(n, 20.0, np.float32),
        off_td=np.zeros(n, bool), def_td=np.zeros(n, bool), turnover=np.zeros(n, bool),
        fd_penalty=np.zeros(n, bool), is_penalty=kind == 2, is_rush=kind == 0,
        dropback=kind == 1, is_run=kind == 0,
        next_start=np.full(n, np.nan, np.float32), yl_orig=np.full(n, 50, np.int16),
        pass_frac=np.full(N_BUCKETS, 0.5),
        punt_offsets=np.arange(punts + 1), punt_bin_map=np.arange(punts),
        punt_start=np.full(punts, 80, np.int16), punt_ret_td=np.zeros(punts, bool),
        ko_start=np.array([70], np.int16), ko_ret_td=np.array([False]),
        fg_beta=np.array([50.0, 0.0, 0.0, 0.0]), pat_make=1.0, two_pt_rate=0.0, two_pt_success=0.0,
        fourth=np.tile([1.0, 0.0, 0.0], (punts, 5, 1)), league_epa=0.0,
        script_shift=shift,
    )


def test_script_state():
    check("kickoff, level: lead band 4, phase 0", int(script_state(0, 0)), 4 * N_PHASE + 0)
    check("up 10 with 3:00 left", int(script_state(10, 3420)), 7 * N_PHASE + 5)
    check("down 20 inside the first-half two-minute warning", int(script_state(-20, 1700)), 0 * N_PHASE + 2)
    check("down 3 in Q3", int(script_state(-3, 2000)), 3 * N_PHASE + 3)
    check("overtime counts as the last five minutes", int(script_state(0, 3700)), 4 * N_PHASE + 5)
    check("every state id in range", int(script_state(np.array([-99, 99]), np.array([0, 9999])).max()), N_SCRIPT - 1)


def test_fit_recovers_shift():
    """20% dropbacks in one state against a 50% bucket rate is a log-odds
    shift of ln(0.25) = -1.386, shrunk by n / (n + 200)."""
    rng = np.random.default_rng(0)
    n = 5000
    lead_late = rng.random(n) < 0.2
    level_early = rng.random(n) < 0.5
    p = pd.DataFrame({
        "drop": np.concatenate([lead_late, level_early]),
        "run": ~np.concatenate([lead_late, level_early]),
        "score_differential": np.concatenate([np.full(n, 10), np.zeros(n)]),
        "game_seconds_remaining": np.concatenate([np.full(n, 100), np.full(n, 3000)]),
        "qtr": np.concatenate([np.full(n, 4), np.ones(n)]),
        "bucket": np.zeros(2 * n, dtype=int),
    })
    shift = _script_shift(p, np.full(N_BUCKETS, 0.5))
    want = np.log(lead_late.mean() / (1 - lead_late.mean())) * n / (n + 200)
    check("leading late: fitted shift", round(float(shift[script_state(10, 3500)]), 4), round(float(want), 4))
    check("level early: ~no shift", float(shift[script_state(0, 600)]), 0.0, tol=0.08)
    check("unseen states: zero", float(shift[script_state(-20, 100)]), 0.0)


def _mix(sampler, t, state, n=120_000, seed=1):
    rng = np.random.default_rng(seed)
    down, togo, yl = np.ones(n, int), np.full(n, 10), np.full(n, 75)
    rows = sampler.draw(rng, down, togo, yl, np.full(n, state))
    return rows, int(t.bucket_map[int(bucket_index(1, 10, 75))])


def test_sampler_follows_the_script():
    shift = np.zeros(N_SCRIPT)
    lead = int(script_state(14, 3400))
    trail = int(script_state(-14, 3400))
    shift[lead], shift[trail] = -2.0, 2.0
    t = tables(shift)
    s = _Sampler(t, Offense(0.0), game_script=True)
    level = int(script_state(0, 0))

    rows, b = _mix(s, t, level)
    check("every draw stays in its bucket", bool((t.bucket[rows] == b).all()), True)
    live = ~t.is_penalty[rows]
    check("no-play penalties keep their bucket share", float(t.is_penalty[rows].mean()), 1 / 3, tol=0.01)
    check("no shift: the bucket's own pass rate", float(t.dropback[rows][live].mean()), 0.5, tol=0.01)

    rows, _ = _mix(s, t, trail)
    live = ~t.is_penalty[rows]
    check("trailing late: throws", float(t.dropback[rows][live].mean()), 1 / (1 + np.exp(-2.0)), tol=0.01)
    rows, _ = _mix(s, t, lead)
    live = ~t.is_penalty[rows]
    check("leading late: runs", float(t.dropback[rows][live].mean()), 1 / (1 + np.exp(2.0)), tol=0.01)

    off = _Sampler(t, Offense(0.0), game_script=False)
    rows, _ = _mix(off, t, trail)
    live = ~t.is_penalty[rows]
    check("script off ignores the state", float(t.dropback[rows][live].mean()), 0.5, tol=0.01)


def test_old_tables_have_no_script():
    s = _Sampler(tables(None), Offense(0.0), game_script=True)
    check("tables without a fitted shift run unscripted", s.script, False)


if __name__ == "__main__":
    for fn in [test_script_state, test_fit_recovers_shift, test_sampler_follows_the_script,
               test_old_tables_have_no_script]:
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    raise SystemExit(1 if FAIL else 0)
