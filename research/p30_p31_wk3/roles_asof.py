"""Point-in-time production roles vectors for the P30 diagnosis and the P31
partial-trim walk-forward (criteria: calibration-log 2026-09-29). Read-only.

Each build replays `sim_data.player_roles` as it would have run at CUTOFF:
pbp and snap counts cut to games that kicked off before it, depth chart to
snapshots dated before it. Writes the full vector (all usage categories,
participation, trim OFF shares) to roles/<season>_w<week>_<tag>.parquet.

  python roles_asof.py        # builds every cutoff the two studies need
"""
import os, sys
os.environ["USAGE_PARTICIPATION_TRIM"] = "1"   # so participation is attached
sys.path.insert(0, r"C:\Users\alexr\OneDrive\Desktop\Football Predictor")
import pandas as pd, nfl_data_py as nfl
from src import sim_data

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "roles")
os.makedirs(OUT, exist_ok=True)

SCH = nfl.import_schedules([2024, 2025, 2026])
SCH["ko"] = pd.to_datetime(SCH["gameday"] + " " + SCH["gametime"]).dt.tz_localize("America/New_York").dt.tz_convert("UTC")
REG = SCH[SCH["game_type"] == "REG"]

_raw_snaps = {}
_raw_depth = {}
_cut = {"t": None, "before": set(), "season": None}


def _snaps(yrs):
    key = tuple(yrs)
    if key not in _raw_snaps:
        _raw_snaps[key] = _orig_snaps(list(yrs))
    s = _raw_snaps[key]
    return s[(s["season"] < _cut["season"]) | s["game_id"].isin(_cut["before"])].copy()


def _depth(yrs):
    key = tuple(yrs)
    if key not in _raw_depth:
        _raw_depth[key] = _orig_depth(list(yrs))
    d = _raw_depth[key]
    return d[pd.to_datetime(d["dt"], utc=True) < _cut["t"]].copy()


_orig_snaps, _orig_depth = nfl.import_snap_counts, nfl.import_depth_charts
nfl.import_snap_counts, nfl.import_depth_charts = _snaps, _depth

_pbp = {}


def build(season, week, cutoff, tag):
    path = os.path.join(OUT, f"{season}_w{week:02d}_{tag}.parquet")
    if os.path.exists(path):
        return path
    cutoff = pd.Timestamp(cutoff)
    before = set(SCH.loc[SCH["ko"] < cutoff, "game_id"])
    _cut.update(t=cutoff, before=before, season=season)
    if season not in _pbp:
        _pbp[season] = sim_data.load_pbp((season - 1, season))
    p = _pbp[season]
    pbp = p[(p["season"] < season) | p["game_id"].isin(before)]
    roles, as_of = sim_data.player_roles(season, pbp)
    roles = roles.reset_index(drop=True)
    keep = ["team", "player_id", "player", "position", "rank", "participation", *sim_data.USAGE_CATEGORIES]
    r = roles[keep].copy()
    r["season"], r["week"], r["cutoff"], r["depth_as_of"] = season, week, str(cutoff), as_of
    r.to_parquet(path)
    print(f"{season} wk{week:>2} {tag:<5} cutoff {cutoff}  depth {as_of}  rows {len(r)}  "
          f"part known {r['participation'].notna().mean():.2f}", flush=True)
    return path


def week_start(season, week):
    return REG.loc[(REG["season"] == season) & (REG["week"] == week), "ko"].min()


if __name__ == "__main__":
    for wk in range(3, 19):
        build(2025, wk, week_start(2025, wk), "pre")
    for wk in (1, 2, 3):
        build(2026, wk, week_start(2026, wk), "pre")
    # the 9/29 part-A production cutoffs (Sunday noon windows)
    build(2026, 2, "2026-09-20T15:48:41Z", "prod")
    build(2026, 3, "2026-09-27T15:45:00Z", "prod")
