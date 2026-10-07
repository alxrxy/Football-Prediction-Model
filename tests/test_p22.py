"""P22: the opponent-adjusted NFL rating, frozen from the 2026-09-30 phase-1
walk-forward. These pin the settings so they cannot drift silently.

    python -m tests.test_p22
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from src import config, ingest_nflverse as ING

PASS, FAIL = 0, 0


def check(label: str, got, want, tol: float | None = None) -> None:
    global PASS, FAIL
    ok = abs(got - want) <= tol if tol is not None else got == want
    if ok:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got {got!r}, want {want!r}")


def test_frozen_settings():
    check("ridge penalty 300", ING.RIDGE_PENALTY, 300.0)
    check("offense carry 0.459", ING.PRIOR_REGRESSION_OFF, 0.459)
    check("defense carry 0.394", ING.PRIOR_REGRESSION_DEF, 0.394)
    check("900-play weight unchanged", ING.PRIOR_PLAYS_WEIGHT, 900.0)
    check("old carry kept for the flag-off path", ING.PRIOR_SEASON_REGRESSION, 0.75)
    src = Path(config.__file__).read_text(encoding="utf-8")
    check("flag defaults on", bool(re.search(r'getenv\("RATING_OPPONENT_ADJUST", "1"\)', src)), True)


def plays(rows):
    """rows: (game_id, offense, defense, epa, n)."""
    out = []
    for gid, o, d, e, n in rows:
        out += [{"game_id": gid, "play_type": "pass", "posteam": o, "defteam": d, "epa": e}] * n
    return pd.DataFrame(out)


# A and B post the same raw EPA, but A did it against the defense that
# holds everyone else down (X), B against the one everyone scores on (Y).
SAMPLE = plays([
    ("2026_01_A_X", "A", "X", 0.00, 200), ("2026_01_B_Y", "B", "Y", 0.00, 200),
    ("2026_02_C_X", "C", "X", -0.20, 200), ("2026_02_C_Y", "C", "Y", 0.20, 200),
])
ALL_NEUTRAL = set(SAMPLE["game_id"])


def test_opponent_adjustment_credits_the_harder_schedule():
    off, _ = ING._epa_by_team(SAMPLE)
    check("raw means equal", float(off.loc["A", "mean"]), float(off.loc["B", "mean"]))
    adj, dfn = ING._adjusted_by_team(SAMPLE, ALL_NEUTRAL)
    check("A (vs the strong defense) rated above B", float(adj.loc["A", "mean"]) > float(adj.loc["B", "mean"]), True)
    check("X's defense rated stronger than Y's", float(dfn.loc["X", "mean"]) < float(dfn.loc["Y", "mean"]), True)
    check("play counts stay raw", int(adj.loc["A", "count"]), 200)


def test_neutral_site_coding():
    sched = pd.DataFrame({"game_id": ["g1", "g2"], "location": ["Neutral", "Home"]})
    check("neutral games read from the schedule", ING._neutral_games(sched), {"g1"})
    check("no schedule: no neutral games", ING._neutral_games(None), set())
    # At a neutral site the game_id's home/away order must not matter.
    swapped = SAMPLE.assign(game_id=SAMPLE["game_id"].str.replace(r"_(\w+)_(\w+)$", r"_\2_\1", regex=True))
    a, _ = ING._adjusted_by_team(SAMPLE, ALL_NEUTRAL)
    b, _ = ING._adjusted_by_team(swapped, set(swapped["game_id"]))
    check("neutral: home/away order irrelevant", float((a["mean"] - b["mean"]).abs().max()), 0.0, 1e-12)


def _ratings(flag: bool, cur: pd.DataFrame, pri: pd.DataFrame):
    frames = {2026: cur.assign(season=2026), 2025: pri.assign(season=2025)}
    real_import, real_flag = ING._import, config.RATING_OPPONENT_ADJUST
    ING._import = lambda: SimpleNamespace(import_pbp_data=lambda years, **k: frames[years[0]])
    config.RATING_OPPONENT_ADJUST = flag
    try:
        return {r["team"]: r for r in ING.compute_ratings(2026, 3, None)}
    finally:
        ING._import, config.RATING_OPPONENT_ADJUST = real_import, real_flag


def test_flag_off_reproduces_the_old_rating():
    # compute_ratings rates only teams seen on both sides of the ball.
    both = pd.concat([SAMPLE, SAMPLE.assign(posteam=SAMPLE["defteam"], defteam=SAMPLE["posteam"], epa=0.05)],
                     ignore_index=True)
    cur = both.iloc[::2].reset_index(drop=True)
    pri = both
    got = _ratings(False, cur, pri)
    off_c, def_c = ING._epa_by_team(cur)
    off_p, def_p = ING._epa_by_team(pri)
    for t in ("A", "C"):
        want = ING._blend(off_c, off_p, t, 0.75)
        check(f"flag off: {t} offense is the old blend", got[t]["off_epa"], round(want, 5))
    on = _ratings(True, cur, pri)
    check("flag on changes the rating", on["A"]["off_epa"] != got["A"]["off_epa"], True)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(name)
            fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
