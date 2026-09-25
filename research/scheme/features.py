"""P46 research layer: team-level scheme features from nflverse participation
and FTN charting. NOT LIVE: nothing in src/ imports this package, and
tests/test_research_isolation.py enforces that.

Sources are read straight from the nflverse release files (the same files
nflreadpy.load_participation / load_ftn_charting read) and cached in
data/cache/research/.

  participation  2016-2025 only; no current-season file (post-season release)
  FTN charting   2022-2026, ~48 h lag; the only live-capable scheme source

Every feature is a per-team rate built the way Layer 1 builds a rating as of
week w: that season's REG snaps before week w, blended with the prior season
at weight n / (n + PRIOR_PLAYS_WEIGHT). One deliberate difference: a rate is
regressed toward the league mean (EPA is regressed toward 0, which is its
league mean). See calibration-log.md, "P46 scoped".
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.ingest_nflverse import PRIOR_PLAYS_WEIGHT, PRIOR_SEASON_REGRESSION  # noqa: E402
from src.sim_data import load_pbp  # noqa: E402

RELEASES = "https://github.com/nflverse/nflverse-data/releases/download"
CACHE = ROOT / "data" / "cache" / "research"
PARTICIPATION_SEASONS = range(2016, 2026)
FTN_SEASONS = range(2022, 2026)      # 2026 exists (weeks 1-2); used only for tracking, never here

SET_A = ("A1_off_heavy", "A2_off_pressure_allowed", "A3_def_pressure", "A4_off_box_on_runs")
SET_B = ("B1_off_play_action", "B2_off_motion", "B3_def_blitz", "B4_def_box_on_runs")


def _release(tag: str, name: str, refresh: bool = False) -> pd.DataFrame | None:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / name
    if refresh or not path.exists():
        r = requests.get(f"{RELEASES}/{tag}/{name}", timeout=180)
        if r.status_code != 200:
            return None
        path.write_bytes(r.content)
    return pd.read_parquet(path)


CANON = {"OAK": "LV", "SD": "LAC", "STL": "LA"}   # as in calibration/p37_edge_diagnosis.py


def _snaps(season: int) -> pd.DataFrame:
    p = load_pbp([season])
    p = p[p["play_type"].isin(["pass", "run"]) & p["posteam"].notna() & (p["season_type"] == "REG")]
    p = p[["game_id", "play_id", "week", "posteam", "defteam", "pass"]].assign(season=season)
    # Relocated franchises keep one code, so a team's prior season is found.
    return p.assign(posteam=p["posteam"].replace(CANON), defteam=p["defteam"].replace(CANON))


def _count(personnel, pos: str) -> float:
    m = re.search(rf"(\d+) {pos}\b", str(personnel or ""))
    return float(m.group(1)) if m else np.nan


def participation_snaps(season: int) -> pd.DataFrame:
    """One row per REG pass/run snap, with the set-A indicators (NaN = not measured)."""
    part = _release("pbp_participation", f"pbp_participation_{season}.parquet")
    s = _snaps(season).merge(part, left_on=["game_id", "play_id"], right_on=["nflverse_game_id", "play_id"], how="left")
    rb, te = s["offense_personnel"].map(lambda v: _count(v, "RB")), s["offense_personnel"].map(lambda v: _count(v, "TE"))
    s["heavy"] = np.where(rb.isna() | te.isna(), np.nan, ((rb >= 2) | (te >= 2)).astype(float))
    pr = s["was_pressure"].astype(str).str.lower().map({"true": 1.0, "false": 0.0})
    s["pressure"] = np.where(s["pass"] == 1, pr, np.nan)
    s["box_run"] = np.where(s["pass"] != 1, pd.to_numeric(s["defenders_in_box"], errors="coerce"), np.nan)
    return s[["season", "week", "posteam", "defteam", "heavy", "pressure", "box_run"]]


def ftn_snaps(season: int, refresh: bool = False) -> pd.DataFrame | None:
    """One row per REG pass/run snap, with the set-B indicators."""
    f = _release("ftn_charting", f"ftn_charting_{season}.parquet", refresh=refresh)
    if f is None:
        return None
    s = _snaps(season).merge(f, left_on=["game_id", "play_id"], right_on=["nflverse_game_id", "nflverse_play_id"],
                             how="inner", suffixes=("", "_ftn"))
    drop = s["pass"] == 1
    s["play_action"] = np.where(drop, s["is_play_action"].astype(float), np.nan)
    s["motion"] = s["is_motion"].astype(float)
    s["blitz"] = np.where(drop, (pd.to_numeric(s["n_blitzers"], errors="coerce") > 0).astype(float), np.nan)
    s["box_run"] = np.where(~drop, pd.to_numeric(s["n_defense_box"], errors="coerce"), np.nan)
    return s[["season", "week", "posteam", "defteam", "play_action", "motion", "blitz", "box_run"]]


# feature name -> (snap column, grouping side)
SPEC = {
    "A1_off_heavy": ("heavy", "posteam"),
    "A2_off_pressure_allowed": ("pressure", "posteam"),
    "A3_def_pressure": ("pressure", "defteam"),
    "A4_off_box_on_runs": ("box_run", "posteam"),
    "B1_off_play_action": ("play_action", "posteam"),
    "B2_off_motion": ("motion", "posteam"),
    "B3_def_blitz": ("blitz", "defteam"),
    "B4_def_box_on_runs": ("box_run", "defteam"),
}


def weekly_features(snaps: dict[int, pd.DataFrame], names: tuple[str, ...]) -> pd.DataFrame:
    """(season, week, team) -> each feature as of that week, leak-free."""
    out = []
    for season, cur_all in snaps.items():
        prior = snaps.get(season - 1)
        for week in range(1, 19):
            cur = cur_all[cur_all["week"] < week]
            cols = {}
            for name in names:
                col, side = SPEC[name]
                c = cur.dropna(subset=[col]).groupby(side)[col].agg(["mean", "count"])
                if prior is not None:
                    pdf = prior.dropna(subset=[col])
                    league = float(pdf[col].mean())
                    pm = pdf.groupby(side)[col].mean()
                    pm = league + PRIOR_SEASON_REGRESSION * (pm - league)
                else:
                    pm = pd.Series(dtype=float)
                teams = sorted(set(c.index) | set(pm.index))
                vals = {}
                for t in teams:
                    cm, n = (float(c.loc[t, "mean"]), float(c.loc[t, "count"])) if t in c.index else (None, 0.0)
                    p_ = float(pm[t]) if t in pm.index else None
                    if cm is None and p_ is None:
                        continue
                    if cm is None:
                        vals[t] = p_
                    elif p_ is None:
                        vals[t] = cm
                    else:
                        w = n / (n + PRIOR_PLAYS_WEIGHT)
                        vals[t] = w * cm + (1 - w) * p_
                cols[name] = vals
            teams = sorted(set().union(*[set(v) for v in cols.values()]))
            for t in teams:
                out.append({"season": season, "week": week, "team": t, **{n: cols[n].get(t, np.nan) for n in names}})
    return pd.DataFrame(out)


def build(set_name: str) -> pd.DataFrame:
    if set_name == "A":
        snaps = {y: participation_snaps(y) for y in PARTICIPATION_SEASONS}
        return weekly_features(snaps, SET_A)
    snaps = {y: s for y in FTN_SEASONS if (s := ftn_snaps(y)) is not None}
    return weekly_features(snaps, SET_B)
