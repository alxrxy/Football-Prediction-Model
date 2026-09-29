"""Empirical tables for the NFL game simulator, built from nflverse play-by-play.

    python -m src.sim_data             build (or load) the tables, print a summary
    python -m src.sim_data --rebuild   ignore the cache

Everything the simulator samples is an observed NFL outcome rather than a
fitted curve: a scrimmage play is drawn from the plays actually run in the same
situation (down x distance x field zone), a punt from punts actually kicked
from the same part of the field, a kickoff from real kickoffs. Three recent
seasons are pooled for the play library, which keeps the rarer situations
populated while staying close to the current game. Kickoffs use 2025 alone:
that season's rule change (touchbacks to the 35) moved the average drive start
by several yards, and pooling older kickoffs would quietly undo it.

Team identity enters later, in the simulator, as a reweighting of this shared
library. Nothing in `SimTables` is team-specific; `player_roles` and
`pass_rate_oe` are the only per-team outputs here.
"""

from __future__ import annotations

import argparse
import pickle
import warnings
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import config

warnings.filterwarnings("ignore")

POOL_SEASONS = (2023, 2024, 2025)
KICKOFF_SEASONS = (2025,)
TABLES_VERSION = 6

# --- situation buckets -----------------------------------------------------
# down: 1st, 2nd, 3rd/4th (a 4th-down attempt is drawn from the same pool as a
# 3rd down: both are must-convert snaps and 4th downs alone are too sparse).
# distance: 1-2, 3-5, 6-9, 10, 11+.
# zone (yards from the end zone): each yard line from 1 to 10 on its own, then
# 11-20 red zone, 21-50, 51-80, 81-99 backed up.
#
# Inside the 10 a drawn play must come from the spot it is applied at (P18). The
# engine scores a play on its touchdown flag or on yardage reaching the goal
# line, so a play applied away from its own spot scores if either spot would
# have: a 1-yard TD from the 1 drawn at the 2 still scores, and a 1-yard gain
# from the 2 drawn at the 1 does too. With 5-yard goal-line zones that biased
# sub-10 first-down conversion 3-5 pp high; at its own spot a drawn play matches
# real play-by-play on every one of 2,902 sub-10 first downs (2023-25).
N_DOWN, N_DIST = 3, 5
DIST_EDGES = [2.5, 5.5, 9.5, 10.5]
ZONE_EDGES = [1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 20.5, 50.5, 80.5]
N_ZONE = len(ZONE_EDGES) + 1
N_BUCKETS = N_DOWN * N_DIST * N_ZONE
GOAL_ZONES = 10           # zones 0-9 are yard lines 1-10

# A bucket with fewer plays than this borrows from its nearest populated
# neighbour instead of resampling the same handful of plays thousands of times.
# Per-yard cells inside the 10 are necessarily thinner, and borrowing there
# stays inside the 10 and changes distance before yard line (see _bucket_map).
MIN_BUCKET_PLAYS = 150
MIN_GOAL_LINE_PLAYS = 50

N_PUNT_BINS = 20          # 5-yard bins of the line of scrimmage
MIN_PUNT_BIN = 40

FOURTH_TOGO_EDGES = [1.5, 3.5, 6.5, 10.5]   # 1, 2-3, 4-6, 7-10, 11+
FOURTH_SMOOTHING = 5.0    # pseudo-attempts borrowed from the same field bin
GO, FG, PUNT = 0, 1, 2

# --- player usage ----------------------------------------------------------
# tgt_short / tgt_deep split targets outside the red zone by air yards, so a
# simulated deep throw goes to the players who actually get deep targets and a
# check-down to the backs, rather than every receiver drawing the same yards.
USAGE_CATEGORIES = ("tgt_all", "tgt_rz", "car_all", "car_rz", "car_gl", "tgt_short", "tgt_deep")
RZ_YL, GL_YL = 20, 5
DEEP_AIR_YARDS = 10
K_DEPTH = 15.0
# Red-zone and goal-line samples are small (a team runs ~30 goal-line carries a
# season), so each is shrunk toward the player's broader share by this many
# team opportunities' worth of prior. A back with 3 of 4 goal-line carries is
# not a 75% goal-line back.
K_RZ = 15.0
K_GL = 10.0
# Weighted games of history it takes for a player's own record to outweigh the
# prior for his depth-chart slot. Rookies have none and ride the prior.
PRIOR_GAMES = 4.0
CURRENT_SEASON_WEIGHT = 2.0
OFFENSE_DEPTH_POSITIONS = ("QB", "RB", "FB", "WR", "TE")
MAX_PRIOR_RANK = 6
# How many at each skill position genuinely play. Beyond these slots a
# player's own history is ignored in favour of the typical share for his depth
# slot: a veteran who started elsewhere last season and is now a backup would
# otherwise carry a starter's red-zone share onto the bench. Backup
# quarterbacks get nothing at all; they inherit the starter's share only
# through the injury chain, when the starter is actually doubtful to play.
PLAYING_SLOTS = {"QB": 1, "RB": 2, "WR": 3, "TE": 1, "FB": 1}
# Beyond the playing slots a player's own history counts at games/(games+K)
# (P25, issue 1). Inside them it is games/(games+PRIOR_GAMES). The much larger
# K keeps a demoted starter from carrying his old workload: full own history
# for backups overshot them 16-52% in the 2025 walk-forward, and none at all
# under-credited 110 real backups (2.9% of targets predicted vs 6.0% realised).
# K = 32 was chosen on 2025 weeks 3-10 and held on 11-18.
BACKUP_HISTORY_GAMES = 32.0
# Within the playing slots, history is kept but held inside this band around
# the slot's typical share, so a receiver promoted from WR4 to WR2 is pulled up
# toward a WR2's workload and a demoted one down, while a genuine target hog
# keeps most of his edge.
HISTORY_FLOOR, HISTORY_CEILING = 0.5, 3.0

PROE_SHRINK = 0.5         # pass rate over expected is only half repeatable

# A quarterback's scramble rate (scrambles per dropback) is a stable trait:
# 2024 -> 2025 r = 0.87. Shrunk toward the league rate with this many
# pseudo-dropbacks (P24; k chosen on 2025 weeks 3-10, held on 11-18). Yards per
# scramble is not a trait (r = 0.00), so scramble yardage stays league-wide.
SCRAMBLE_PRIOR_DROPBACKS = 25.0

PBP_COLUMNS = [
    "game_id", "play_id", "season", "season_type", "week", "posteam", "defteam",
    "game_half", "qtr", "down", "ydstogo", "yardline_100", "play_type",
    "yards_gained", "epa", "pass", "rush_attempt", "pass_attempt", "sack",
    "interception", "fumble_lost", "touchdown", "td_team", "safety", "penalty",
    "first_down_penalty", "game_seconds_remaining", "half_seconds_remaining",
    "fixed_drive", "field_goal_result", "kick_distance", "extra_point_result",
    "two_point_attempt", "two_point_conv_result", "own_kickoff_recovery",
    "wind", "roof", "receiver_player_id", "rusher_player_id",
    "passer_player_id", "wp", "pass_oe", "score_differential",
    "complete_pass", "qb_scramble", "air_yards", "qb_dropback",
]


def bucket_index(down, togo, yl) -> np.ndarray:
    d = np.clip(np.asarray(down), 1, 3) - 1
    t = np.digitize(togo, DIST_EDGES)
    z = np.digitize(yl, ZONE_EDGES)
    return (d * N_DIST + t) * N_ZONE + z


# --- game script -----------------------------------------------------------
# Play-calling follows the scoreboard: trailing teams throw, leading teams run,
# more so as the clock runs down. A snap's script state is the offence's lead
# (9 bands) x the phase of the game (6), and the engine shifts each bucket's
# pass rate by that state's log-odds shift, fitted on the library.
LEAD_EDGES = [-16.5, -8.5, -3.5, -0.5, 0.5, 3.5, 8.5, 16.5]
# Elapsed seconds: Q1 | Q2 to the two-minute warning | its last two minutes |
# Q3 | Q4 to 5:00 | the last five minutes and overtime.
PHASE_EDGES = [900, 1680, 1800, 2700, 3300]
N_PHASE = len(PHASE_EDGES) + 1
N_SCRIPT = (len(LEAD_EDGES) + 1) * N_PHASE
SCRIPT_PRIOR_PLAYS = 200.0   # a thin state's shift is shrunk toward none by this many plays


def script_state(lead, elapsed) -> np.ndarray:
    """Script state id from the offence's lead and elapsed game seconds."""
    return np.digitize(lead, LEAD_EDGES) * N_PHASE + np.digitize(elapsed, PHASE_EDGES)


def segment_cdf(seg: np.ndarray, weights: np.ndarray, n_segments: int) -> np.ndarray:
    """One sorted array holding every segment's CDF, offset by segment id.

    `seg` must be sorted. Segment s occupies (s, s+1], so a single
    searchsorted on `s + u` draws from segment s for every simulated game at
    once, whatever segment each is in.
    """
    counts = np.bincount(seg, minlength=n_segments)
    offsets = np.concatenate([[0], np.cumsum(counts)])
    cs = np.cumsum(weights)
    starts, ends = offsets[:-1], offsets[1:]
    populated = ends > starts
    before = np.zeros(n_segments)
    total = np.ones(n_segments)
    before[populated] = cs[starts[populated]] - weights[starts[populated]]
    total[populated] = cs[ends[populated] - 1] - before[populated]
    norm = (cs - before[seg]) / total[seg]
    norm[ends[populated] - 1] = 1.0   # exact top edge, so rounding cannot spill
    return seg + norm


@dataclass
class SimTables:
    """Everything the engine samples, as flat numpy arrays."""

    # Scrimmage play library, sorted by bucket.
    bucket: np.ndarray        # bucket id per play
    offsets: np.ndarray       # len N_BUCKETS + 1; plays of bucket b are [offsets[b], offsets[b+1])
    bucket_map: np.ndarray    # requested bucket -> populated bucket actually sampled
    yards: np.ndarray         # net yards, penalties included
    epa: np.ndarray
    duration: np.ndarray      # game-clock seconds until the next snap
    off_td: np.ndarray
    def_td: np.ndarray
    turnover: np.ndarray
    fd_penalty: np.ndarray    # automatic first down by penalty
    is_penalty: np.ndarray    # a no-play penalty: yards are penalty yards
    is_rush: np.ndarray       # a TD on this play is a rushing TD
    dropback: np.ndarray      # pass or scramble, for the pass-rate reweighting
    is_run: np.ndarray        # designed run
    next_start: np.ndarray    # after a turnover: where the other side took over (nan if unknown)
    yl_orig: np.ndarray       # line of scrimmage the play was actually run from
    pass_frac: np.ndarray     # per bucket: dropbacks / (dropbacks + designed runs)

    # Special teams.
    punt_offsets: np.ndarray
    punt_bin_map: np.ndarray
    punt_start: np.ndarray    # receiving side's yardline_100 after the punt
    punt_ret_td: np.ndarray
    ko_start: np.ndarray
    ko_ret_td: np.ndarray
    fg_beta: np.ndarray       # logistic: 1, (dist-40)/10, ((dist-40)/10)^2, excess wind/10
    pat_make: float
    two_pt_rate: float
    two_pt_success: float
    fourth: np.ndarray        # (N_PUNT_BINS, 5, 3) P(go, fg, punt)

    league_epa: float         # mean EPA per play of the library, unweighted
    meta: dict = field(default_factory=dict)

    # Box-score detail per play, for crediting players (None in tables that
    # predate it). stat_yards is the official yards_gained, unlike `yards`,
    # which is the net change in field position, penalties included.
    stat_yards: np.ndarray | None = None
    complete: np.ndarray | None = None
    attempt: np.ndarray | None = None       # pass attempt; sacks and scrambles excluded
    # An attempt with an intended receiver. Throwaways (4.2% of attempts)
    # have none, are never completed, and must not be credited as targets.
    targeted: np.ndarray | None = None
    scramble: np.ndarray | None = None
    interception: np.ndarray | None = None
    deep: np.ndarray | None = None          # air yards >= DEEP_AIR_YARDS
    # Log-odds shift in pass rate per script state (script_state), relative
    # to the bucket's rate. None in tables that predate it: no game script.
    script_shift: np.ndarray | None = None

    def base_weights(self, pass_rate_oe: float, scramble_factor: float = 1.0) -> np.ndarray:
        """Resample weights that shift the run/pass mix by a team's tendency.

        Each bucket's pass fraction is moved by the team's pass rate over
        expected, so a run-heavy team draws more of its red-zone snaps from
        runs, and therefore scores more of its touchdowns on the ground.

        `scramble_factor` (the team's expected QB scramble rate over the
        league's, P24) then reweights scrambles within the dropbacks. Each
        bucket's other dropbacks are rescaled so its total dropback mass is
        unchanged: a scrambling QB turns passes into scrambles without his
        team dropping back more or less often.
        """
        w = np.ones(len(self.epa))
        if pass_rate_oe:
            pf = self.pass_frac
            target = np.clip(pf + pass_rate_oe, 0.03, 0.97)
            w[self.dropback] = (target / pf)[self.bucket[self.dropback]]
            w[self.is_run] = ((1 - target) / (1 - pf))[self.bucket[self.is_run]]
        if scramble_factor != 1.0 and self.scramble is not None:
            db = self.dropback
            before = np.bincount(self.bucket[db], weights=w[db], minlength=N_BUCKETS)
            w[self.scramble] *= scramble_factor
            after = np.bincount(self.bucket[db], weights=w[db], minlength=N_BUCKETS)
            w[db] *= (before / np.maximum(after, 1e-12))[self.bucket[db]]
        return w

    def segment_cdf(self, weights: np.ndarray) -> np.ndarray:
        """Every bucket's CDF in one array (see the module-level segment_cdf)."""
        return segment_cdf(self.bucket, weights, N_BUCKETS)

    def fg_prob(self, distance: np.ndarray, wind_mph: float) -> np.ndarray:
        x = (np.asarray(distance, dtype=float) - 40.0) / 10.0
        wind = max(wind_mph - 10.0, 0.0) / 10.0
        z = self.fg_beta[0] + self.fg_beta[1] * x + self.fg_beta[2] * x * x + self.fg_beta[3] * wind
        p = 1.0 / (1.0 + np.exp(-z))
        return np.where(np.asarray(distance) > 68, 0.0, np.clip(p, 0.0, 0.995))


# --- loading ---------------------------------------------------------------

def _final_season() -> int:
    """The latest season that is over, and so safe to cache forever."""
    now = datetime.now(timezone.utc)
    return now.year - 1 if now.month >= 3 else now.year - 2


def load_pbp(seasons, refresh: bool = False) -> pd.DataFrame:
    import nfl_data_py as nfl

    config.ensure_dirs()
    frames = []
    for season in seasons:
        path = config.CACHE_DIR / f"sim_pbp_{season}.parquet"
        final = season <= _final_season()
        if final and path.exists() and not refresh:
            cached = pd.read_parquet(path)
            # A cache written before a column joined PBP_COLUMNS lacks it;
            # re-download rather than hand back a frame that is silently short.
            if set(PBP_COLUMNS) <= set(cached.columns):
                frames.append(cached)
                continue
        try:
            df = nfl.import_pbp_data([season], columns=PBP_COLUMNS, downcast=True, cache=False)
        except Exception as exc:  # noqa: BLE001
            print(f"  [warn] play-by-play {season} unavailable ({exc})")
            continue
        if final:
            df.to_parquet(path)
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=PBP_COLUMNS)
    return pd.concat(frames, ignore_index=True)


def _snaps(pbp: pd.DataFrame) -> pd.DataFrame:
    """Every snap in game order, each carrying the state of the snap after it.

    The next snap is what makes the library honest: a play's net yardage is
    read off the change in field position rather than `yards_gained`, so
    penalties, pass interference and half-distance calls are all in it.
    """
    pt = pbp["play_type"]
    keep = pt.isin(["pass", "run", "punt", "field_goal", "kickoff", "qb_kneel", "qb_spike"]) \
        | ((pt == "no_play") & (pbp["penalty"] == 1))
    s = pbp[keep & pbp["posteam"].notna()].sort_values(["game_id", "play_id"]).reset_index(drop=True)
    grouped = s.groupby("game_id")
    for col in ("posteam", "yardline_100", "down", "game_seconds_remaining",
                "fixed_drive", "game_half", "play_type"):
        s["next_" + col] = grouped[col].shift(-1)
    return s


# --- scrimmage library -----------------------------------------------------

def _scrimmage(s: pd.DataFrame) -> pd.DataFrame:
    p = s[s["play_type"].isin(["pass", "run", "no_play"])
          & s["down"].between(1, 4) & s["yardline_100"].between(1, 99)
          & (s["ydstogo"] >= 1) & s["epa"].notna()].copy()
    yl = p["yardline_100"].astype(int)

    same_series = ((p["next_posteam"] == p["posteam"])
                   & (p["next_fixed_drive"] == p["fixed_drive"])
                   & (p["next_game_half"] == p["game_half"])
                   & (p["next_play_type"] != "kickoff"))
    yards = np.where(same_series, yl - p["next_yardline_100"], p["yards_gained"].fillna(0))
    p["net_yards"] = np.clip(np.nan_to_num(yards), -40, 99).astype(np.int16)

    same_half = p["next_game_half"] == p["game_half"]
    dur = np.where(same_half, p["game_seconds_remaining"] - p["next_game_seconds_remaining"], 6.0)
    p["dur"] = np.clip(np.nan_to_num(dur, nan=6.0), 0, 45).astype(np.float32)

    p["o_td"] = (p["touchdown"] == 1) & (p["td_team"] == p["posteam"])
    p["d_td"] = (p["touchdown"] == 1) & (p["td_team"] == p["defteam"])
    p["to"] = ((p["interception"] == 1) | (p["fumble_lost"] == 1)) & ~p["o_td"]
    p["nstart"] = np.where(p["next_posteam"] == p["defteam"], p["next_yardline_100"], np.nan)
    p["pen"] = p["play_type"] == "no_play"
    p["drop"] = (p["pass"] == 1) & ~p["pen"]
    p["run"] = ~p["drop"] & ~p["pen"]
    # nflverse records a scramble as a run (rush_attempt, not pass_attempt)
    # and a sack as a pass attempt; the box score counts neither as a pass.
    p["stat_y"] = p["yards_gained"].fillna(0).clip(-40, 99).astype(np.int16)
    p["scr"] = (p["qb_scramble"] == 1) & ~p["pen"]
    p["cmp"] = (p["complete_pass"] == 1) & ~p["pen"]
    p["att"] = (p["pass_attempt"] == 1) & (p["sack"] != 1) & ~p["scr"] & ~p["pen"]
    p["int"] = (p["interception"] == 1) & p["att"]
    p["tgt"] = p["att"] & p["receiver_player_id"].notna()
    p["deep"] = p["air_yards"].fillna(0) >= DEEP_AIR_YARDS
    p["bucket"] = bucket_index(p["down"].astype(int), p["ydstogo"].astype(int), yl)
    return p.sort_values("bucket", kind="stable").reset_index(drop=True)


def _min_plays(zone: np.ndarray) -> np.ndarray:
    return np.where(zone < GOAL_ZONES, MIN_GOAL_LINE_PLAYS, MIN_BUCKET_PLAYS)


def _bucket_map(counts: np.ndarray) -> np.ndarray:
    ids = np.arange(N_BUCKETS)
    d, t, z = ids // (N_DIST * N_ZONE), (ids // N_ZONE) % N_DIST, ids % N_ZONE
    enough = counts >= _min_plays(z)
    goal = z < GOAL_ZONES
    out = ids.copy()
    for b in ids:
        if enough[b]:
            continue
        # A spot inside the 10 borrows only from inside the 10, and the yard
        # line is what must match there: whether a drawn play converts is
        # tested against the real to-go, but its yardage and touchdown come
        # from the spot it was run from (P18). So: relax distance first, then
        # yard line or field zone, then down.
        populated = np.flatnonzero(enough & (goal == goal[b]))
        cost = 3 * abs(d[populated] - d[b]) + abs(t[populated] - t[b]) + 2 * abs(z[populated] - z[b])
        out[b] = populated[np.argmin(cost)]
    return out


# --- special teams ---------------------------------------------------------

def _punts(s: pd.DataFrame):
    pu = s[(s["play_type"] == "punt") & s["yardline_100"].between(1, 99)].copy()
    pu["ret_td"] = (pu["touchdown"] == 1) & (pu["td_team"] == pu["defteam"])
    pu["start"] = np.where(pu["next_posteam"] == pu["defteam"], pu["next_yardline_100"], np.nan)
    pu = pu[pu["ret_td"] | pu["start"].notna()]
    pu["bin"] = ((pu["yardline_100"].astype(int) - 1) // 5).clip(0, N_PUNT_BINS - 1)
    pu = pu.sort_values("bin", kind="stable")
    counts = np.bincount(pu["bin"], minlength=N_PUNT_BINS)
    offsets = np.concatenate([[0], np.cumsum(counts)])
    populated = np.flatnonzero(counts >= MIN_PUNT_BIN)
    bin_map = np.array([b if counts[b] >= MIN_PUNT_BIN
                        else populated[np.argmin(abs(populated - b))] for b in range(N_PUNT_BINS)])
    return offsets, bin_map, pu["start"].fillna(0).to_numpy(np.int16), pu["ret_td"].to_numpy(bool)


def _kickoffs(s: pd.DataFrame):
    """Kickoffs from the current rules era. On a kickoff row nflverse's
    posteam is the receiving side."""
    ko = s[(s["play_type"] == "kickoff") & s["season"].isin(KICKOFF_SEASONS)
           & (s["own_kickoff_recovery"] != 1)].copy()
    ko["ret_td"] = (ko["touchdown"] == 1) & (ko["td_team"] == ko["posteam"])
    ko["start"] = np.where(ko["next_posteam"] == ko["posteam"], ko["next_yardline_100"], np.nan)
    ko = ko[ko["ret_td"] | ko["start"].between(1, 99)]
    return ko["start"].fillna(0).to_numpy(np.int16), ko["ret_td"].to_numpy(bool)


def _logistic(X: np.ndarray, y: np.ndarray, iters: int = 30) -> np.ndarray:
    beta = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-X @ beta))
        hess = X.T @ (X * (p * (1 - p))[:, None]) + 1e-6 * np.eye(X.shape[1])
        step = np.linalg.solve(hess, X.T @ (y - p))
        beta += step
        if np.abs(step).max() < 1e-8:
            break
    return beta


def _script_shift(p: pd.DataFrame, pass_frac: np.ndarray) -> np.ndarray:
    """Log-odds shift in pass rate per script state, relative to each bucket.

    For each state, the one f with sum(sigmoid(logit pf_bucket + f)) equal to
    the dropbacks actually called in that state. That is the maximum-likelihood
    fit of a logistic model with the bucket rate as an offset and one term per
    state, so across the library it hands back every state's real pass rate
    while the bucket still sets down, distance and field position.
    """
    q = p[p["drop"] | p["run"]]
    remaining = q["game_seconds_remaining"].astype(float).fillna(1800.0).to_numpy()
    elapsed = np.where(q["qtr"].to_numpy() >= 5, 3600.0, 3600.0 - remaining)
    state = script_state(q["score_differential"].astype(float).fillna(0.0).to_numpy(), elapsed)
    pf = pass_frac[q["bucket"].to_numpy()]
    offset = np.log(pf / (1 - pf))
    y = q["drop"].to_numpy(float)
    shift = np.zeros(N_SCRIPT)
    for s in range(N_SCRIPT):
        m = state == s
        n = int(m.sum())
        if not n:
            continue
        o, target, f = offset[m], y[m].sum(), 0.0
        for _ in range(60):
            pr = 1.0 / (1.0 + np.exp(-(o + f)))
            step = (target - pr.sum()) / max(float((pr * (1 - pr)).sum()), 1e-9)
            f = float(np.clip(f + step, -6.0, 6.0))
            if abs(step) < 1e-10:
                break
        shift[s] = f * n / (n + SCRIPT_PRIOR_PLAYS)
    return shift


def _field_goals(pbp: pd.DataFrame) -> np.ndarray:
    """Make probability by distance, with wind, from real attempts. The wind
    term is what lets a forecast gale cost a kicker rather than being ignored."""
    k = pbp[(pbp["play_type"] == "field_goal") & pbp["kick_distance"].notna()]
    indoor = k["roof"].isin(["dome", "closed"])
    wind = np.where(indoor, 0.0, k["wind"].fillna(0).astype(float))
    x = (k["kick_distance"].astype(float) - 40.0) / 10.0
    X = np.column_stack([np.ones(len(k)), x, x * x, np.maximum(wind - 10.0, 0.0) / 10.0])
    return _logistic(X, (k["field_goal_result"] == "made").astype(float).to_numpy())


def _fourth_downs(s: pd.DataFrame) -> np.ndarray:
    """P(go / kick / punt) by field position and distance.

    End-of-half and late-game 4th downs are excluded: the engine decides those
    by rule from the score, so leaving them in would count desperation twice.
    """
    f = s[(s["down"] == 4) & s["play_type"].isin(["pass", "run", "punt", "field_goal"])
          & s["yardline_100"].between(1, 99) & (s["qtr"] <= 4)]
    late = ((f["qtr"] == 4) & (f["game_seconds_remaining"] < 300)) \
        | ((f["qtr"] == 2) & (f["half_seconds_remaining"] < 30))
    f = f[~late]
    choice = np.select([f["play_type"].isin(["pass", "run"]), f["play_type"] == "field_goal"],
                       [GO, FG], PUNT)
    yb = ((f["yardline_100"].astype(int) - 1) // 5).clip(0, N_PUNT_BINS - 1).to_numpy()
    tb = np.digitize(f["ydstogo"], FOURTH_TOGO_EDGES)
    counts = np.zeros((N_PUNT_BINS, len(FOURTH_TOGO_EDGES) + 1, 3))
    np.add.at(counts, (yb, tb, choice), 1)
    by_field = counts.sum(axis=1, keepdims=True)
    prior = by_field / np.maximum(by_field.sum(-1, keepdims=True), 1)
    return (counts + FOURTH_SMOOTHING * prior) / (counts.sum(-1, keepdims=True) + FOURTH_SMOOTHING)


# --- assembly --------------------------------------------------------------

def build_tables(refresh: bool = False) -> SimTables:
    config.ensure_dirs()
    tag = "_".join(str(s) for s in POOL_SEASONS)
    path = config.CACHE_DIR / f"sim_tables_v{TABLES_VERSION}_{tag}.pkl"
    if path.exists() and not refresh:
        with open(path, "rb") as fh:
            return SimTables(**pickle.load(fh))

    pbp = load_pbp(POOL_SEASONS, refresh=refresh)
    s = _snaps(pbp)
    p = _scrimmage(s)

    counts = np.bincount(p["bucket"], minlength=N_BUCKETS)
    drop_n = np.bincount(p["bucket"], weights=p["drop"], minlength=N_BUCKETS)
    run_n = np.bincount(p["bucket"], weights=p["run"], minlength=N_BUCKETS)
    pass_frac = np.clip(drop_n / np.maximum(drop_n + run_n, 1), 0.02, 0.98)

    punt_offsets, punt_bin_map, punt_start, punt_ret_td = _punts(s)
    ko_start, ko_ret_td = _kickoffs(s)

    xp = pbp[pbp["play_type"] == "extra_point"]
    two = pbp[pbp["two_point_attempt"] == 1]

    tables = SimTables(
        bucket=p["bucket"].to_numpy(np.int64),
        offsets=np.concatenate([[0], np.cumsum(counts)]).astype(np.int64),
        bucket_map=_bucket_map(counts),
        yards=p["net_yards"].to_numpy(np.int16),
        epa=p["epa"].to_numpy(np.float64),
        duration=p["dur"].to_numpy(np.float32),
        off_td=p["o_td"].to_numpy(bool),
        def_td=p["d_td"].to_numpy(bool),
        turnover=p["to"].to_numpy(bool),
        fd_penalty=(p["first_down_penalty"] == 1).to_numpy(bool),
        is_penalty=p["pen"].to_numpy(bool),
        is_rush=(p["rush_attempt"] == 1).to_numpy(bool),
        dropback=p["drop"].to_numpy(bool),
        is_run=p["run"].to_numpy(bool),
        next_start=p["nstart"].to_numpy(np.float32),
        yl_orig=p["yardline_100"].to_numpy(np.int16),
        pass_frac=pass_frac,
        punt_offsets=punt_offsets,
        punt_bin_map=punt_bin_map,
        punt_start=punt_start,
        punt_ret_td=punt_ret_td,
        ko_start=ko_start,
        ko_ret_td=ko_ret_td,
        fg_beta=_field_goals(pbp),
        pat_make=float((xp["extra_point_result"] == "good").mean()),
        two_pt_rate=float(len(two) / max(len(two) + len(xp), 1)),
        two_pt_success=float((two["two_point_conv_result"] == "success").mean()),
        fourth=_fourth_downs(s),
        league_epa=float(p["epa"].mean()),
        stat_yards=p["stat_y"].to_numpy(np.int16),
        complete=p["cmp"].to_numpy(bool),
        attempt=p["att"].to_numpy(bool),
        targeted=p["tgt"].to_numpy(bool),
        scramble=p["scr"].to_numpy(bool),
        interception=p["int"].to_numpy(bool),
        deep=p["deep"].to_numpy(bool),
        script_shift=_script_shift(p, pass_frac),
        meta={
            "pool_seasons": list(POOL_SEASONS),
            "kickoff_seasons": list(KICKOFF_SEASONS),
            "plays": int(len(p)),
            "sparse_buckets": int((counts < _min_plays(np.arange(N_BUCKETS) % N_ZONE)).sum()),
            "punts": int(len(punt_start)),
            "kickoffs": int(len(ko_start)),
            "built_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    with open(path, "wb") as fh:
        # Plain fields rather than the dataclass: pickle records a class under
        # the module that defined it at dump time, which is `__main__` when this
        # file is run directly, and every other entrypoint then cannot load it.
        pickle.dump({f.name: getattr(tables, f.name) for f in fields(tables)}, fh)
    return tables


# --- per-team inputs -------------------------------------------------------

def _usage_events(pbp: pd.DataFrame) -> pd.DataFrame:
    tg = pbp[(pbp["pass_attempt"] == 1) & (pbp["sack"] != 1) & pbp["receiver_player_id"].notna()]
    # Carry shares are for designed runs only. The engine credits every
    # scramble to the quarterback separately, and kneels are not in the play
    # library, so counting either here inflates the QB's share of designed
    # runs and dilutes every back's.
    ru = pbp[(pbp["rush_attempt"] == 1) & pbp["rusher_player_id"].notna()
             & (pbp["qb_scramble"] != 1) & (pbp["play_type"] != "qb_kneel")]
    ev = pd.concat([
        pd.DataFrame({"season": tg["season"], "game_id": tg["game_id"], "team": tg["posteam"],
                      "pid": tg["receiver_player_id"], "tgt": 1, "yl": tg["yardline_100"],
                      "air": tg["air_yards"]}),
        pd.DataFrame({"season": ru["season"], "game_id": ru["game_id"], "team": ru["posteam"],
                      "pid": ru["rusher_player_id"], "tgt": 0, "yl": ru["yardline_100"], "air": 0.0}),
    ], ignore_index=True)
    deep = ev["air"].fillna(0) >= DEEP_AIR_YARDS
    ev["tgt_short"] = ev["tgt"] * ~deep
    ev["tgt_deep"] = ev["tgt"] * deep
    car = 1 - ev["tgt"]
    ev["tgt_all"] = ev["tgt"]
    ev["tgt_rz"] = ev["tgt"] * (ev["yl"] <= RZ_YL)
    ev["car_all"] = car
    ev["car_rz"] = car * (ev["yl"] <= RZ_YL)
    ev["car_gl"] = car * (ev["yl"] <= GL_YL)
    return ev


def usage_rates(pbp: pd.DataFrame, current_season: int) -> pd.DataFrame:
    """Each player's share of his team's opportunities, per category.

    Shares are taken over the games the player actually appeared in, so a
    receiver who missed half a season is not mistaken for a part-timer, and
    they follow the player rather than the team: a back who changed teams in
    the offseason brings his workload profile with him.
    """
    cats = list(USAGE_CATEGORIES)
    ev = _usage_events(pbp)
    team_game = ev.groupby(["game_id", "team"])[cats].sum()
    player_game = ev.groupby(["season", "game_id", "team", "pid"])[cats].sum().reset_index()

    # A quarterback who threw but never ran still appeared.
    qb = pbp[pbp["passer_player_id"].notna()][["season", "game_id", "posteam", "passer_player_id"]] \
        .drop_duplicates().rename(columns={"posteam": "team", "passer_player_id": "pid"})
    player_game = pd.concat([player_game, qb], ignore_index=True) \
        .groupby(["season", "game_id", "team", "pid"])[cats].sum(min_count=0).fillna(0).reset_index()

    pg = player_game.merge(team_game.reset_index(), on=["game_id", "team"], suffixes=("", "_team"))
    w = np.where(pg["season"] == current_season, CURRENT_SEASON_WEIGHT, 1.0)
    num = pd.DataFrame({c: w * pg[c] for c in cats}).groupby(pg["pid"]).sum()
    den = pd.DataFrame({c: w * pg[c + "_team"] for c in cats}).groupby(pg["pid"]).sum()
    games = pd.Series(w).groupby(pg["pid"].to_numpy()).sum()

    out = pd.DataFrame(index=num.index)
    out["tgt_all"] = num["tgt_all"] / den["tgt_all"].where(den["tgt_all"] > 0)
    out["car_all"] = num["car_all"] / den["car_all"].where(den["car_all"] > 0)
    out = out.fillna(0.0)
    out["tgt_rz"] = (num["tgt_rz"] + K_RZ * out["tgt_all"]) / (den["tgt_rz"] + K_RZ)
    out["car_rz"] = (num["car_rz"] + K_RZ * out["car_all"]) / (den["car_rz"] + K_RZ)
    out["car_gl"] = (num["car_gl"] + K_GL * out["car_rz"]) / (den["car_gl"] + K_GL)
    for c in ("tgt_short", "tgt_deep"):
        out[c] = (num[c] + K_DEPTH * out["tgt_all"]) / (den[c] + K_DEPTH)
    out["games"] = games.reindex(out.index).fillna(0.0)
    out["rz_targets"] = num["tgt_rz"]
    out["gl_carries"] = num["car_gl"]
    return out


def rank_priors(pbp_season: pd.DataFrame, season: int) -> dict[tuple[str, int], dict]:
    """Typical share for each depth-chart slot (RB1, WR3, ...) in one season.

    Used for players with no history of their own, chiefly rookies. Slot is
    approximated by rank within team and position by total opportunities.
    """
    import nfl_data_py as nfl

    cats = list(USAGE_CATEGORIES)
    ev = _usage_events(pbp_season)
    team_tot = ev.groupby("team")[cats].sum()
    player = ev.groupby(["team", "pid"])[cats].sum().reset_index()
    rosters = nfl.import_seasonal_rosters([season])[["player_id", "position"]].drop_duplicates("player_id")
    player = player.merge(rosters, left_on="pid", right_on="player_id", how="inner")
    for c in cats:
        player[c] = player[c] / player["team"].map(team_tot[c]).replace(0, np.nan)
    player["opps"] = player["tgt_all"].fillna(0) + player["car_all"].fillna(0)
    player["rank"] = player.groupby(["team", "position"])["opps"].rank(ascending=False, method="first")
    priors = {}
    for (pos, rank), grp in player.groupby(["position", "rank"]):
        if rank <= MAX_PRIOR_RANK:
            priors[(pos, int(rank))] = grp[cats].fillna(0).mean().to_dict()
    return priors


def current_depth(season: int) -> tuple[pd.DataFrame, str]:
    """Latest nflverse depth chart for every team's skill positions.

    nflverse republishes ESPN's charts daily with gsis ids attached, so this
    reflects offseason moves and rookies, which last season's usage cannot.
    """
    import nfl_data_py as nfl

    df = nfl.import_depth_charts([season])
    if "dt" not in df.columns:
        raise SystemExit(f"nflverse depth charts for {season} are not in the daily format this expects")
    latest = df.groupby("team")["dt"].transform("max")
    cur = df[(df["dt"] == latest) & df["pos_abb"].isin(OFFENSE_DEPTH_POSITIONS) & df["gsis_id"].notna()]
    cur = cur.sort_values("pos_rank").drop_duplicates(["team", "gsis_id"])
    out = pd.DataFrame({
        "team": cur["team"], "player_id": cur["gsis_id"], "player": cur["player_name"],
        "position": cur["pos_abb"], "rank": cur["pos_rank"].astype(int),
    }).reset_index(drop=True)
    return out, str(cur["dt"].max())


def blend_roles(depth: pd.DataFrame, rates: pd.DataFrame,
                priors: dict[tuple[str, int], dict]) -> pd.DataFrame:
    """Each depth-chart player's expected share of every opportunity type.

    The depth slot sets the volume and the player's own history refines it:
    inside the playing slots history is blended with the slot norm (held
    within HISTORY_FLOOR..HISTORY_CEILING of it); beyond them the same blend
    at the much smaller weight games/(games+BACKUP_HISTORY_GAMES); backup
    quarterbacks get zero. Fullbacks have no slot norm (nflverse rosters label
    no one FB), so the clip would force them to zero: an FB with no prior
    keeps his own history instead.
    """
    roles = depth.merge(rates, left_on="player_id", right_index=True, how="left")
    g = roles["games"].fillna(0.0).to_numpy()
    playing = roles["rank"].to_numpy() <= roles["position"].map(PLAYING_SLOTS).fillna(1).to_numpy()
    backup_qb = (roles["position"] == "QB").to_numpy() & ~playing
    weight = np.where(playing, g / (g + PRIOR_GAMES), g / (g + BACKUP_HISTORY_GAMES))
    is_fb = (roles["position"] == "FB").to_numpy()
    for c in USAGE_CATEGORIES:
        prior = np.array([
            priors.get((pos, min(int(rank), MAX_PRIOR_RANK)), {}).get(c, 0.0)
            for pos, rank in zip(roles["position"], roles["rank"])
        ])
        own = roles[c].fillna(0.0).to_numpy()
        hist = np.clip(own, HISTORY_FLOOR * prior, HISTORY_CEILING * prior)
        hist = np.where(is_fb & (prior == 0), own, hist)
        roles[c] = np.where(backup_qb, 0.0, weight * hist + (1 - weight) * prior)
    roles["games"] = g
    for col in ("rz_targets", "gl_carries"):
        roles[col] = roles[col].fillna(0.0) if col in roles else 0.0
    return roles


def snap_participation(season: int) -> tuple[dict[tuple[str, str], float], set[str]]:
    """({(team, player_key): offensive snaps per team game}, teams covered).

    The denominator runs from the player's first appearance for that team, not
    from the start of the window: a rookie who has played every snap of two
    games is at 1.0, not at 2/19. Used by the P31 pool trim, where a player
    carrying target share he will never use dilutes everyone who does.

    The second return value is the teams the feed covers. A player missing from
    a covered team has taken no offensive snap, which is the case the trim
    exists for, so he reads as 0; a team missing altogether reads as unknown,
    so a broken pull cannot empty a whole pool.
    """
    import nfl_data_py as nfl

    from .ingest_injuries import player_key

    try:
        sn = nfl.import_snap_counts([season - 1, season])
    except Exception:  # noqa: BLE001 - the trim is optional; no data means no trim
        return {}, set()
    if sn.empty:
        return {}, set()
    sn = sn[["season", "week", "team", "player", "offense_pct"]].copy()
    sn["pct"] = sn["offense_pct"].fillna(0.0).clip(0.0, 1.0)
    sn["t"] = sn["season"] * 100 + sn["week"]
    team_weeks = sn.groupby("team")["t"].apply(lambda s: np.sort(s.unique()))
    out = {}
    for (team, player), g in sn.groupby(["team", "player"]):
        weeks = team_weeks.get(team)
        if weeks is None or not len(weeks):
            continue
        since = int((weeks >= g["t"].min()).sum())
        if since <= 0:
            continue
        out[(team, player_key(team, player))] = float(g["pct"].sum() / since)
    return out, set(team_weeks.index)


def expected_starters(season: int) -> dict[tuple[int, str], str]:
    """{(week, team): gsis id} of the quarterback expected to start (P28).

    nflverse schedules carry `home_qb_id` / `away_qb_id`: the actual starter for
    a completed game and the expected one for a game still to play, so reading
    it before kickoff adds no lookahead. The depth chart names the wrong starter
    in 9.6% of team-games and the misses are the injury cases, which is exactly
    when the passing props matter.
    """
    import nfl_data_py as nfl

    try:
        sch = nfl.import_schedules([season])
    except Exception:  # noqa: BLE001 - fall back to the depth chart
        return {}
    out = {}
    for _, r in sch.iterrows():
        try:
            week = int(r["week"])
        except (TypeError, ValueError):
            continue
        for side in ("home", "away"):
            qb, team = r.get(f"{side}_qb_id"), r.get(f"{side}_team")
            if isinstance(qb, str) and isinstance(team, str):
                out[(week, team)] = qb
    return out


def player_roles(season: int, pbp: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Every current skill player's expected share of each opportunity type,
    before injuries."""
    from .ingest_injuries import player_key

    depth, as_of = current_depth(season)
    rates = usage_rates(pbp, season)
    priors = rank_priors(pbp[pbp["season"] == season - 1], season - 1)
    roles = blend_roles(depth, rates, priors)
    if config.USAGE_PARTICIPATION_TRIM:
        part, covered = snap_participation(season)
        roles["participation"] = [
            part.get((t, player_key(t, n)), 0.0 if t in covered else np.nan)
            for t, n in zip(roles["team"], roles["player"])
        ]
    else:
        roles["participation"] = np.nan
    return roles, as_of


def qb_scramble_rates(pbp: pd.DataFrame, current_season: int) -> tuple[dict[str, float], float]:
    """({player_id: scramble rate}, league rate). Each QB's scrambles per
    dropback over the pbp given (prior and current season), shrunk toward the
    prior season's league rate by SCRAMBLE_PRIOR_DROPBACKS."""
    d = pbp[pbp["play_type"].isin(["pass", "run"]) & (pbp["qb_dropback"] == 1)]
    if "season_type" in d:
        d = d[d["season_type"] == "REG"]
    qb = d["passer_player_id"].fillna(d["rusher_player_id"])
    scr = (d["qb_scramble"] == 1).astype(float)
    prior = scr[d["season"] == current_season - 1]
    league = float(prior.mean()) if len(prior) else float(scr.mean())
    g = scr.groupby(qb).agg(["size", "sum"])
    k = SCRAMBLE_PRIOR_DROPBACKS
    return ((g["sum"] + k * league) / (g["size"] + k)).to_dict(), league


def scramble_factor(squad: pd.DataFrame, passer_weights: np.ndarray, rates: dict[str, float],
                    league: float) -> float:
    """The offence's expected QB scramble rate over the league's: each QB's
    rate weighted by his chance of being the simulated game's passer. A QB with
    no dropbacks on record counts at the league rate."""
    w = np.asarray(passer_weights, dtype=float)
    if not rates or not league or w.sum() <= 0 or "player_id" not in squad:
        return 1.0
    ids = squad.reset_index(drop=True)["player_id"]
    rate = sum(wt * rates.get(pid, league) for pid, wt in zip(ids, w) if wt > 0) / w.sum()
    return float(rate / league)


def pass_rate_oe(pbp: pd.DataFrame, current_season: int) -> dict[str, float]:
    """Neutral-situation pass rate over expected per offence, as a fraction."""
    n = pbp[pbp["down"].between(1, 3) & pbp["wp"].between(0.2, 0.8)
            & (pbp["half_seconds_remaining"] > 120) & pbp["pass_oe"].notna() & pbp["posteam"].notna()]
    w = pd.Series(np.where(n["season"] == current_season, CURRENT_SEASON_WEIGHT, 1.0), index=n.index)
    proe = (w * n["pass_oe"]).groupby(n["posteam"]).sum() / w.groupby(n["posteam"]).sum()
    return (proe / 100.0 * PROE_SHRINK).to_dict()


def summary(t: SimTables) -> str:
    ko_tb = float(np.mean(t.ko_start == 65))
    lines = [
        f"play library    {t.meta['plays']:,} scrimmage plays from {t.meta['pool_seasons']}"
        f" | {t.meta['sparse_buckets']}/{N_BUCKETS} sparse buckets borrow a neighbour",
        f"league EPA/play {t.league_epa:+.4f}",
        f"kickoffs        {t.meta['kickoffs']:,} ({t.meta['kickoff_seasons']}) | mean start "
        f"own {100 - t.ko_start[~t.ko_ret_td].mean():.1f} | at the 35: {ko_tb:.0%}"
        f" | return TD {t.ko_ret_td.mean():.2%}",
        f"punts           {t.meta['punts']:,} | return TD {t.punt_ret_td.mean():.2%}",
        f"PAT make        {t.pat_make:.3f} | 2-pt tried {t.two_pt_rate:.3f}, "
        f"converted {t.two_pt_success:.3f}",
        "FG make         " + "  ".join(
            f"{d}yd {float(t.fg_prob(np.array([d]), 0.0)[0]):.2f}" for d in (30, 40, 50, 55, 60)
        ) + f" | 50yd in 25mph wind {float(t.fg_prob(np.array([50]), 25.0)[0]):.2f}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the simulator's empirical tables.")
    parser.add_argument("--rebuild", action="store_true", help="ignore the cache")
    args = parser.parse_args()
    print(summary(build_tables(refresh=args.rebuild)))
