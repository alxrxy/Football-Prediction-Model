"""Vectorised drive-by-drive NFL game engine.

Every simulated game advances in lockstep: one pass through the main loop is
one snap in each game still in progress. A 10,000-game run is therefore a few
hundred numpy operations over 10,000-element arrays rather than millions of
Python-level plays, which is what makes 10,000 simulations per game cheap.

A drive is a sequence of snaps. Each snap is one of:

  scrimmage play  drawn from the real plays run in the same down / distance /
                  field-zone bucket, reweighted toward this offence (below)
  punt / FG       chosen on 4th down from how often NFL teams actually go,
                  kick or punt from that spot, with score-aware overrides late
  kneel           the leading side runs out the clock

Scores, turnovers, punts and turns-on-downs hand the ball over, and drives
chain until the clock runs out, including overtime under the current
both-teams-possess rule.

Team strength is exponential tilting: each library play is weighted by
exp(lambda * its EPA), with lambda solved so the reweighted library averages
exactly the EPA per play this offence is expected to produce against this
defence. A strong offence therefore draws more of the plays that actually
worked, in every situation, with no invented yardage curve.

Game script: before a scrimmage play is drawn, the call is made, run or
dropback, at the bucket's pass rate shifted by the scoreboard and the clock
(sim_data.script_state). A simulated team that goes ahead starts running and
one that falls behind starts throwing, so volume follows each simulated game
rather than an average one.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import config
from .sim_data import DIST_EDGES, FG, GO, N_BUCKETS, N_DIST, N_PUNT_BINS, PUNT
from .sim_data import SimTables, bucket_index
from .sim_data import FOURTH_TOGO_EDGES, script_state, segment_cdf

PERIOD_END = np.array([0.0, 1800.0, 3600.0, 4200.0])   # indexed by period; 3 = overtime
MAX_SNAPS = 700

KNEEL_SECONDS = 100       # leading, ball in hand, this little left: game over
LATE_FG_SECONDS = 20      # end of a half: kick if in range rather than run a play
LATE_FG_YL = 40
LATE_GAME_SECONDS = 300   # final five minutes: 4th-down calls follow the score
FG_RANGE_YL = 37          # ~55-yard attempt
KICK_SPOT = 8             # holder's spot behind the line of scrimmage
FG_EXTRA = 18             # end zone + holder: attempt distance = yardline + 18

# The score is recorded every five minutes of game clock, so a live game can be
# compared with where the simulations stood at the same point (live_tracker).
# The 60-minute checkpoint is the end of regulation, before any overtime.
CHECKPOINT_SECONDS = 300
CHECKPOINTS = np.arange(0, 3601, CHECKPOINT_SECONDS)
PACE_TOTAL_CAP = 90       # CDF support: totals 0..90, margins -50..+50 (tails folded in)
PACE_MARGIN_CAP = 50

# Touchdown event columns: side * 6 + kind * 3 + zone.
RUSH, PASS = 0, 1
GOAL_LINE, RED_ZONE, OPEN_FIELD = 0, 1, 2


@dataclass
class Offense:
    """How one side's offence is drawn from the shared library."""

    target_epa: float
    pass_rate_oe: float = 0.0


@dataclass
class LiveStart:
    """A game already under way, for resuming the simulation mid-game.

    Every simulated game starts from this one state. With `possession` and a
    down set, the first event is that snap; otherwise it is a kickoff to
    `kickoff_receiver` (a coin flip if unknown). Scoring counted in the
    result (TDs, FGs, TD events) is only what happens from here on; `points`
    carry the real score forward.
    """

    elapsed_seconds: float
    home_points: int
    away_points: int
    possession: int | None = None        # 0 home, 1 away
    yardline_100: int | None = None
    down: int | None = None
    togo: int | None = None
    kickoff_receiver: int | None = None
    second_half_receiver: int | None = None
    pending_conversion: int | None = None   # side whose PAT / two-point try is still to come


STAT_NAMES = ("pass_att", "pass_cmp", "pass_yds", "pass_td", "pass_int",
              "rush_att", "rush_yds", "rush_td", "tgt", "rec", "rec_yds", "rec_td")

# Why each simulated drive ended, for the engine diagnostic in
# simulate_nfl.calibrate. The labels match how the same thing is derived from
# real play-by-play, so the two distributions line up column for column.
# Tracked only when _Game is built with track_drives=True: the counters are a
# few integer adds per drive, but the default stays off so an ordinary
# 10,000-game run does no extra work in the hot loop.
DRIVE_OUTCOMES = ("TD", "FG made", "FG miss", "punt", "turnover", "downs",
                  "def TD", "safety", "end of half/game")
(DR_TD, DR_FG_MADE, DR_FG_MISS, DR_PUNT, DR_TURNOVER, DR_DOWNS,
 DR_DEF_TD, DR_SAFETY, DR_CLOCK) = range(len(DRIVE_OUTCOMES))

# First downs per drive are histogrammed 0..9 and then 10+. A drive's length
# is close to a function of this: real drives with no first down average 2.8
# snaps, one 4.8, two 6.7. Two engines can agree on conversions per play and
# still disagree here if one clusters them onto fewer drives.
FD_HIST_MAX = 10


@dataclass
class PlayerPool:
    """One side's skill players, for crediting each simulated play.

    `cum` holds cumulative usage shares per category (car_gl / car_rz /
    car_all by field zone; tgt_rz, tgt_short, tgt_deep for targets), and
    `passer_weights` how likely each player is to be a simulated game's
    quarterback. Built by box_score.player_pool.
    """

    names: list[str]
    cum: dict[str, np.ndarray]
    passer_weights: np.ndarray

    def pick(self, category: str, u: np.ndarray) -> np.ndarray:
        c = self.cum[category]
        if c[-1] <= 0:
            return np.full(len(u), -1)
        return np.minimum(np.searchsorted(c, u * c[-1], side="right"), len(c) - 1)


@dataclass
class SimResult:
    points: np.ndarray        # (n, 2) home, away
    tds: np.ndarray           # (n, 2) all touchdowns
    fgs: np.ndarray           # (n, 2)
    td_events: np.ndarray     # (n, 12) offensive TDs by side, kind, zone
    return_tds: np.ndarray    # (n, 2) defensive and special-teams TDs
    overtime: np.ndarray      # (n,) bool
    possessions: np.ndarray   # (n, 2)
    tilt: tuple[float, float]
    checkpoints: np.ndarray   # (n, len(CHECKPOINTS), 2) score at each checkpoint
    players: tuple | None = None   # per side {stat: (n, players)}, when pools were given
    # {"counts": (len(DRIVE_OUTCOMES),), "plays": (len(DRIVE_OUTCOMES),)} —
    # drives ending each way and the scrimmage plays they took, summed over
    # every simulated game. None unless track_drives was set.
    drives: dict | None = None


def solve_tilt(epa: np.ndarray, base: np.ndarray, target: float) -> float:
    """lambda such that sum(w * epa) / sum(w) = target, w = base * exp(lambda * epa).

    The reweighted mean is strictly increasing in lambda (its derivative is the
    reweighted variance), so Newton converges in a handful of steps.
    """
    lam = 0.0
    for _ in range(60):
        w = base * np.exp(lam * epa)
        total = w.sum()
        mean = (w * epa).sum() / total
        var = (w * epa * epa).sum() / total - mean * mean
        step = (target - mean) / max(var, 1e-9)
        lam = float(np.clip(lam + step, -3.0, 3.0))
        if abs(step) < 1e-9:
            break
    return lam


_SAMPLER_CACHE: dict = {}


def _sampler(tables: SimTables, offense: Offense, game_script: bool = True) -> "_Sampler":
    """Samplers are pure functions of the library and the offence, and cost
    a tilt solve over 112k plays to build. The live tracker re-simulates the
    same matchups every poll, so they are kept rather than rebuilt."""
    key = (id(tables), round(offense.target_epa, 7), round(offense.pass_rate_oe, 7), game_script)
    sampler = _SAMPLER_CACHE.get(key)
    if sampler is None:
        if len(_SAMPLER_CACHE) >= 64:
            _SAMPLER_CACHE.clear()
        sampler = _SAMPLER_CACHE[key] = _Sampler(tables, offense, game_script)
    return sampler


KIND_RUN, KIND_DROPBACK, KIND_OTHER = 0, 1, 2   # OTHER: no-play penalties


class _Sampler:
    """Draws scrimmage plays for one offence.

    Without a game script a play comes straight from its bucket as the
    tilted library has it. With one, the call is made first: dropback at the
    bucket's tilted pass rate shifted in log-odds by the script state, else a
    run, and then a real play of that kind is drawn from the bucket. No-play
    penalties keep their bucket share either way, and in a state with no
    shift the mix is exactly the bucket's, so strength and team tendency
    (PROE) carry through unchanged.
    """

    def __init__(self, tables: SimTables, offense: Offense, game_script: bool = True):
        base = tables.base_weights(offense.pass_rate_oe)
        self.lam = solve_tilt(tables.epa, base, offense.target_epa)
        w = base * np.exp(self.lam * tables.epa)
        self.tables = tables
        self.script = game_script and tables.script_shift is not None
        if not self.script:
            self.cdf = tables.segment_cdf(w)
            return
        kind = np.where(tables.dropback, KIND_DROPBACK, np.where(tables.is_run, KIND_RUN, KIND_OTHER))
        seg = tables.bucket * 3 + kind
        self.order = np.argsort(seg, kind="stable")
        self.cdf = segment_cdf(seg[self.order], w[self.order], N_BUCKETS * 3)
        mass = np.zeros((N_BUCKETS, 3))
        np.add.at(mass, (tables.bucket, kind), w)
        self.has = mass > 0
        self.p_other = mass[:, KIND_OTHER] / np.maximum(mass.sum(axis=1), 1e-12)
        pf = mass[:, KIND_DROPBACK] / np.maximum(mass[:, KIND_DROPBACK] + mass[:, KIND_RUN], 1e-12)
        pf = np.clip(pf, 0.01, 0.99)
        self.logit_pass = np.log(pf / (1 - pf))

    def draw(self, rng: np.random.Generator, down, togo, yl, state=None) -> np.ndarray:
        b = self.tables.bucket_map[bucket_index(down, togo, yl)]
        if not self.script:
            return np.searchsorted(self.cdf, b + rng.random(len(b)), side="right")
        shift = self.tables.script_shift[state] if state is not None else 0.0
        p_pass = 1.0 / (1.0 + np.exp(-(self.logit_pass[b] + shift)))
        u = rng.random((3, len(b)))
        kind = np.where(u[0] < self.p_other[b], KIND_OTHER,
                        np.where(u[1] < p_pass, KIND_DROPBACK, KIND_RUN))
        # A populated bucket with no play of the chosen kind is vanishingly
        # rare; draw whatever kind it does have rather than spill into the next.
        gap = ~self.has[b, kind]
        if gap.any():
            kind[gap] = np.argmax(self.has[b[gap]], axis=1)
        idx = np.searchsorted(self.cdf, b * 3 + kind + u[2], side="right")
        return self.order[idx]


class _Game:
    def __init__(self, tables: SimTables, home: Offense, away: Offense,
                 n: int, seed: int, wind_mph: float, pools: tuple | None = None,
                 game_script: bool = True, track_drives: bool = False,
                 penalty_replay: bool | None = None):
        self.t = tables
        self.rng = np.random.default_rng(seed)
        self.samplers = (_sampler(tables, home, game_script), _sampler(tables, away, game_script))
        self.wind = wind_mph
        # Explicit argument wins, so one process can run the comparison both
        # ways; otherwise the config flag decides.
        self.penalty_replay = config.PENALTY_REPLAY if penalty_replay is None else penalty_replay
        self.n = n
        z = lambda *shape: np.zeros(shape, dtype=np.int32)  # noqa: E731
        self.off, self.yl, self.down, self.togo = z(n), z(n), z(n), z(n)
        self.clock = np.zeros(n)
        self.period = np.ones(n, dtype=np.int32)
        self.points, self.tds, self.fgs, self.ret_tds = z(n, 2), z(n, 2), z(n, 2), z(n, 2)
        self.possessions, self.ot_poss = z(n, 2), z(n, 2)
        self.td_events = z(n, 12)
        self.done = np.zeros(n, dtype=bool)
        self.overtime = np.zeros(n, dtype=bool)
        self.second_half_receiver = np.zeros(n, dtype=np.int32)
        self.cp_points = z(n, len(CHECKPOINTS), 2)
        self.cp_next = np.ones(n, dtype=np.int32)   # checkpoint 0 is 0-0 by definition

        # Drive diagnostic (off by default). `in_drive` marks games whose drive
        # is still open, so the two paths that end one without calling _end --
        # a kneel-out and the clock expiring -- are counted exactly once.
        self.track_drives = track_drives
        if track_drives:
            self.in_drive = np.zeros(n, dtype=bool)
            self.drive_plays = z(n)
            self.drive_fd = z(n)
            self.fd_hist = np.zeros(FD_HIST_MAX + 1, dtype=np.int64)
            # Series = one set of downs. A series is earned by a first down,
            # which includes one awarded by penalty -- those never show up in
            # down_conv, because a penalty is a no-play and is not counted as
            # a snap at all. Counted here where the engine actually decides it.
            self.series_started = 0
            self.series_converted = 0
            self.fd_by_penalty = 0
            # Where each drive started, summed per outcome. Scoring drives
            # begin nearer the end zone, so a drive that runs short may simply
            # have had less field to cover.
            self.drive_start_yl = z(n)
            self.drive_start_sum = np.zeros(len(DRIVE_OUTCOMES), dtype=np.int64)
            # Drives closed without a single counted snap -- a kickoff as the
            # half expires, say. Needed to split `series_started - series with
            # a snap` into its two causes, which is the only way to state a
            # series conversion rate comparable with the real one.
            self.zero_snap_drives = 0
            self.drive_counts = np.zeros(len(DRIVE_OUTCOMES), dtype=np.int64)
            self.drive_play_sums = np.zeros(len(DRIVE_OUTCOMES), dtype=np.int64)
            # Down-state progression, [down 1-4] x [distance bin]. A play is
            # drawn from a pooled bucket and then tested against the actual
            # to-go, so togo is summed too: it shows whether the engine sits
            # at the same place inside a bin as real football does, which a
            # wide bin like 10.5+ (real to-go 11 to 25) makes matter.
            shape = (4, N_DIST)
            self.down_plays = np.zeros(shape, dtype=np.int64)
            self.down_conv = np.zeros(shape, dtype=np.int64)
            self.down_yards = np.zeros(shape, dtype=np.int64)
            self.down_togo = np.zeros(shape, dtype=np.int64)

        self.pools = pools
        self.pstats = self.passer = None
        if pools is not None:
            if tables.stat_yards is None:
                raise ValueError("these tables carry no per-play stats; rebuild them to track players")
            self.pstats = tuple({k: np.zeros((n, len(p.names)), dtype=np.int32) for k in STAT_NAMES}
                                for p in pools)
            self.passer = tuple(self._passers(p) for p in pools)

    def _passers(self, pool: PlayerPool) -> np.ndarray:
        """Each simulated game's quarterback, drawn once per game: if the
        starter is doubtful, some simulations are played by his backup."""
        w = np.asarray(pool.passer_weights, dtype=float)
        if w.sum() <= 0:
            return np.full(self.n, -1)
        return self.rng.choice(len(w), self.n, p=w / w.sum())

    def _record_checkpoints(self):
        last = len(CHECKPOINTS) - 1
        while True:
            due = np.flatnonzero((self.cp_next <= last)
                                 & (self.clock >= CHECKPOINTS[np.minimum(self.cp_next, last)]))
            if not len(due):
                return
            self.cp_points[due, self.cp_next[due]] = self.points[due]
            self.cp_next[due] += 1

    # --- possession bookkeeping -------------------------------------------

    def _start(self, ix, side, yl):
        self.off[ix] = side
        self.yl[ix] = np.clip(yl, 1, 99)
        self.down[ix] = 1
        self.togo[ix] = np.minimum(10, self.yl[ix])
        self.possessions[ix, side] += 1
        if self.track_drives and len(ix):
            self.in_drive[ix] = True
            self.drive_plays[ix] = 0
            self.drive_fd[ix] = 0
            self.drive_start_yl[ix] = self.yl[ix]
            self.series_started += len(ix)     # a new drive opens a series

    def _end(self, ix, outcome=None):
        """The side with the ball has finished a possession. Overtime cares,
        since both sides must have had the ball before it can end; the drive
        diagnostic cares about `outcome`, which says how it finished."""
        ot = ix[self.period[ix] == 3]
        self.ot_poss[ot, self.off[ot]] += 1
        if outcome is not None:
            self._close_drives(ix, outcome)

    def _close_drives(self, ix, outcome):
        """Record finished drives. Only games whose drive is still open are
        counted, so nothing is tallied twice however the drive ended."""
        if not self.track_drives or not len(ix):
            return
        open_ = ix[self.in_drive[ix]]
        if not len(open_):
            return
        self.drive_counts[outcome] += len(open_)
        self.drive_play_sums[outcome] += int(self.drive_plays[open_].sum())
        self.zero_snap_drives += int((self.drive_plays[open_] == 0).sum())
        played = open_[self.drive_plays[open_] > 0]
        if len(played):
            # Only drives that ran a snap, which is how real drive starts are
            # read (off the first scrimmage play) and what the adjusted drive
            # counts in the report divide by.
            self.drive_start_sum[outcome] += int(self.drive_start_yl[played].sum())
        np.add.at(self.fd_hist, np.minimum(self.drive_fd[open_], FD_HIST_MAX), 1)
        self.in_drive[open_] = False

    def _touchdown(self, ix, side):
        self.points[ix, side] += 6
        self.tds[ix, side] += 1
        self._convert(ix, side)

    def _convert(self, ix, side):
        """The PAT or two-point try after a touchdown."""
        rng = self.rng
        k = len(ix)
        go_for_two = rng.random(k) < self.t.two_pt_rate
        extra = np.where(go_for_two,
                         2 * (rng.random(k) < self.t.two_pt_success),
                         1 * (rng.random(k) < self.t.pat_make))
        self.points[ix, side] += extra

    def _kickoff(self, ix, receiver, allow_return_td=True):
        if not len(ix):
            return
        self.clock[ix] += 5
        draw = self.rng.integers(0, len(self.t.ko_start), len(ix))
        ret = self.t.ko_ret_td[draw] & allow_return_td
        fine = ~ret
        # A return TD is re-drawn from the non-TD kickoffs for the ensuing kick.
        start = self.t.ko_start[draw]
        if ret.any():
            normal = np.flatnonzero(~self.t.ko_ret_td)
            start = start.copy()
            start[ret] = self.t.ko_start[normal[self.rng.integers(0, len(normal), ret.sum())]]
            rix, rside = ix[ret], receiver[ret]
            self._touchdown(rix, rside)
            self.ret_tds[rix, rside] += 1
            self._start(rix, 1 - rside, start[ret])
        self._start(ix[fine], receiver[fine], start[fine])

    # --- the snap ---------------------------------------------------------

    def _transitions(self):
        live = ~self.done
        half = np.flatnonzero(live & (self.period == 1) & (self.clock >= 1800))
        if len(half):
            self._end(half, DR_CLOCK)      # the first-half drive is abandoned here
            self.period[half] = 2
            self.clock[half] = 1800
            self._kickoff(half, self.second_half_receiver[half])

        end = live & (self.period == 2) & (self.clock >= 3600)
        tied = self.points[:, 0] == self.points[:, 1]
        self.done |= end & ~tied
        ot = np.flatnonzero(end & tied)
        if len(ot):
            # Regulation's last drive is abandoned when overtime kicks off.
            # Counted before the period moves to 3, so it is not also recorded
            # as an overtime possession.
            self._end(ot, DR_CLOCK)
            self.period[ot] = 3
            self.clock[ot] = 3600
            self.overtime[ot] = True
            self._kickoff(ot, self.rng.integers(0, 2, len(ot)).astype(np.int32))

        self.done |= ~self.done & (self.period == 3) & (self.clock >= 4200)

    def _snap(self, ix):
        off, yl, down = self.off[ix], self.yl[ix], self.down[ix]
        remaining = PERIOD_END[self.period[ix]] - self.clock[ix]
        lead = self.points[ix, off] - self.points[ix, 1 - off]
        period = self.period[ix]

        kneel = (period == 2) & (lead > 0) & (remaining <= KNEEL_SECONDS)
        if kneel.any():
            self._end(ix[kneel], DR_CLOCK)
        self.done[ix[kneel]] = True

        late_fg = ~kneel & (remaining <= LATE_FG_SECONDS) & (yl <= LATE_FG_YL) \
            & ((period == 1) | (lead >= -3))
        fourth = ~kneel & ~late_fg & (down == 4)

        choice = np.full(len(ix), GO)
        if fourth.any():
            f = np.flatnonzero(fourth)
            yb = np.clip((yl[f] - 1) // 5, 0, N_PUNT_BINS - 1)
            tb = np.digitize(self.togo[ix[f]], FOURTH_TOGO_EDGES)
            probs = self.t.fourth[yb, tb]
            u = self.rng.random(len(f))
            choice[f] = np.where(u < probs[:, 0], GO, np.where(u < probs[:, 0] + probs[:, 1], FG, PUNT))
            # Late and behind, a punt is a surrender: kick only when a field
            # goal ties or wins, otherwise go.
            late = ((period[f] == 2) & (remaining[f] <= LATE_GAME_SECONDS)) | (period[f] == 3)
            behind = lead[f] < 0
            need_fg = late & behind & (lead[f] >= -3) & (yl[f] <= FG_RANGE_YL)
            choice[f] = np.where(late & behind, np.where(need_fg, FG, GO), choice[f])
            # Level in overtime, any field goal in range is taken: the generic
            # table would punt some of them away and manufacture ties.
            ot_level = (period[f] == 3) & (lead[f] == 0) & (yl[f] <= FG_RANGE_YL)
            choice[f] = np.where(ot_level, FG, choice[f])

        kick = late_fg | (fourth & (choice == FG))
        punt = fourth & (choice == PUNT)
        play = ~kneel & ~kick & ~punt
        self._field_goal(ix[kick])
        self._punt(ix[punt])
        self._scrimmage(ix[play])

    def _field_goal(self, ix):
        if not len(ix):
            return
        kicker = self.off[ix]
        made = self.rng.random(len(ix)) < self.t.fg_prob(self.yl[ix] + FG_EXTRA, self.wind)
        spot = self.yl[ix] + KICK_SPOT
        self.clock[ix] += 5
        good, miss = ix[made], ix[~made]
        # Split the possession-end so the diagnostic can tell a made kick from a
        # miss; both run before _start below moves the ball.
        self._end(good, DR_FG_MADE)
        self._end(miss, DR_FG_MISS)
        self.points[good, kicker[made]] += 3
        self.fgs[good, kicker[made]] += 1
        self._kickoff(good, 1 - kicker[made])
        self._start(miss, 1 - kicker[~made], np.where(spot[~made] <= 20, 80, 100 - spot[~made]))

    def _punt(self, ix):
        if not len(ix):
            return
        t = self.t
        b = t.punt_bin_map[np.clip((self.yl[ix] - 1) // 5, 0, N_PUNT_BINS - 1)]
        lo, hi = t.punt_offsets[b], t.punt_offsets[b + 1]
        row = lo + (self.rng.random(len(ix)) * (hi - lo)).astype(np.int64)
        receiver = 1 - self.off[ix]
        ret = t.punt_ret_td[row]
        self.clock[ix] += 6
        self._end(ix, DR_PUNT)
        self._start(ix[~ret], receiver[~ret], t.punt_start[row[~ret]])
        if ret.any():
            rix, rside = ix[ret], receiver[ret]
            self._touchdown(rix, rside)
            self.ret_tds[rix, rside] += 1
            self._kickoff(rix, 1 - rside)

    def _scrimmage(self, ix):
        if not len(ix):
            return
        t = self.t
        rows = np.empty(len(ix), dtype=np.int64)
        off = self.off[ix]
        state = script_state(self.points[ix, off] - self.points[ix, 1 - off], self.clock[ix])
        for side in (0, 1):
            m = off == side
            if m.any():
                s = ix[m]
                rows[m] = self.samplers[side].draw(self.rng, self.down[s], self.togo[s], self.yl[s], state[m])

        yl, togo = self.yl[ix], self.togo[ix]
        y = t.yards[rows].astype(np.int32)
        pen = t.is_penalty[rows]
        if self.track_drives:
            # Count what play-by-play counts: a penalty no-play is not a snap.
            run_ = ~pen
            self.drive_plays[ix[run_]] += 1
            # Conversion is measured the way the engine itself decides a first
            # down below (net yards against the real to-go), so this reports
            # actual behaviour rather than a second opinion on it.
            dn = np.clip(self.down[ix][run_], 1, 4) - 1
            db = np.digitize(togo[run_], DIST_EDGES)
            np.add.at(self.down_plays, (dn, db), 1)
            np.add.at(self.down_conv, (dn, db), (y[run_] >= togo[run_]).astype(np.int64))
            np.add.at(self.down_yards, (dn, db), y[run_].astype(np.int64))
            np.add.at(self.down_togo, (dn, db), togo[run_].astype(np.int64))
            self.drive_fd[ix[run_]] += (y[run_] >= togo[run_])
        # Half the distance to the goal caps any penalty.
        y = np.where(pen & (y < 0), np.maximum(y, -((100 - yl) // 2)), y)
        y = np.where(pen & (y > 0), np.minimum(y, yl // 2), y)
        new = yl - y
        self.clock[ix] += t.duration[rows]

        dtd = t.def_td[rows]
        lost = t.turnover[rows] & ~dtd
        otd = ~dtd & ~lost & (t.off_td[rows] | (new <= 0))
        safety = ~dtd & ~lost & ~otd & (new >= 100)
        cont = ~dtd & ~lost & ~otd & ~safety
        if self.pools is not None:
            self._credit(ix, rows, off, yl, otd)

        if dtd.any():
            i, side = ix[dtd], 1 - off[dtd]
            self._end(i, DR_DEF_TD)
            self._touchdown(i, side)
            self.ret_tds[i, side] += 1
            self._kickoff(i, off[dtd])

        if lost.any():
            r = rows[lost]
            shifted = t.next_start[r] - (yl[lost] - t.yl_orig[r])
            spot = 100 - np.clip(new[lost], 1, 99)
            opp = np.where(np.isnan(shifted), spot, shifted).astype(np.int32)
            self._end(ix[lost], DR_TURNOVER)
            self._start(ix[lost], 1 - off[lost], opp)

        if otd.any():
            i, side = ix[otd], off[otd]
            kind = np.where(t.is_rush[rows[otd]], RUSH, PASS)
            zone = np.where(yl[otd] <= 5, GOAL_LINE, np.where(yl[otd] <= 20, RED_ZONE, OPEN_FIELD))
            self.td_events[i, side * 6 + kind * 3 + zone] += 1
            if self.track_drives:
                # A series that ends in a touchdown converted; it just does not
                # open another one.
                self.series_converted += len(i)
            self._end(i, DR_TD)
            self._touchdown(i, side)
            self._kickoff(i, 1 - side)

        if safety.any():
            i, side = ix[safety], off[safety]
            self.points[i, 1 - side] += 2
            self._end(i, DR_SAFETY)
            self._kickoff(i, 1 - side)

        if cont.any():
            i = ix[cont]
            yc, nc, tc = y[cont], new[cont], togo[cont]
            first = (yc >= tc) | t.fd_penalty[rows[cont]]
            if self.track_drives:
                earned = int(first.sum())
                self.series_converted += earned      # this set of downs succeeded
                self.series_started += earned        # and the next one begins
                self.fd_by_penalty += int((first & ~(yc >= tc)).sum())
            # A nullified penalty replays the down in real football -- 69.8% of
            # them do, and almost none consume one -- while this engine has
            # always advanced the down regardless, which shortens every drive.
            # Distance needs no special case: togo below is tc - yc, and yc is
            # the net change in field position with the penalty yardage in it.
            if self.penalty_replay:
                repeat = t.is_penalty[rows[cont]] & ~first
                down = np.where(first, 1, np.where(repeat, self.down[i], self.down[i] + 1))
            else:
                down = np.where(first, 1, self.down[i] + 1)
            self.yl[i] = nc
            self.down[i] = down
            self.togo[i] = np.maximum(np.where(first, np.minimum(10, nc), tc - yc), 1)
            downs = down > 4
            if downs.any():
                j = i[downs]
                self._end(j, DR_DOWNS)
                self._start(j, 1 - self.off[j], 100 - nc[downs])

    # --- player stats -----------------------------------------------------

    @staticmethod
    def _add(stats, key, sims, who, value):
        # Each simulated game contributes at most one play per snap, so the
        # (game, player) pairs here are unique and plain fancy-index += is exact.
        ok = who >= 0
        if ok.any():
            stats[key][sims[ok], who[ok]] += np.broadcast_to(value, who.shape)[ok]

    def _pick(self, pool: PlayerPool, cats: tuple, masks: tuple) -> np.ndarray:
        who = np.full(len(masks[0]), -1)
        u = self.rng.random(len(who))
        for cat, sel in zip(cats, masks):
            if sel.any():
                who[sel] = pool.pick(cat, u[sel])
        return who

    def _credit(self, ix, rows, off, yl, otd):
        """Credit each snap to players.

        A designed run goes to a ball carrier by carry share for its field
        zone (goal line, red zone, open field); a scramble and every pass
        attempt to that simulated game's quarterback; a target to a receiver
        by red-zone, short or deep target share, unless the attempt was a
        throwaway with no intended receiver. Yards are the play's
        official yards, capped short of the goal line, and exactly the
        distance to it on a touchdown, which is credited on the play itself.
        """
        t = self.t
        yards = np.where(otd, yl, np.minimum(t.stat_yards[rows].astype(np.int32), yl - 1))
        live = ~t.is_penalty[rows]
        for side in (0, 1):
            pool, st, passer = self.pools[side], self.pstats[side], self.passer[side]
            m = live & (off == side)
            if not m.any():
                continue
            sims, r, yds, td, z = ix[m], rows[m], yards[m], otd[m].astype(np.int32), yl[m]

            run = t.is_rush[r] & ~t.scramble[r]
            if run.any():
                zr = z[run]
                who = self._pick(pool, ("car_gl", "car_rz", "car_all"),
                                 (zr <= 5, (zr > 5) & (zr <= 20), zr > 20))
                for key, v in (("rush_att", 1), ("rush_yds", yds[run]), ("rush_td", td[run])):
                    self._add(st, key, sims[run], who, v)

            scr = t.scramble[r]
            if scr.any():
                who = passer[sims[scr]]
                for key, v in (("rush_att", 1), ("rush_yds", yds[scr]), ("rush_td", td[scr])):
                    self._add(st, key, sims[scr], who, v)

            att = t.attempt[r]
            if att.any():
                s_, ra, za = sims[att], r[att], z[att]
                comp = t.complete[ra].astype(np.int32)
                gained, scored = yds[att] * comp, td[att] * comp
                qb = passer[s_]
                for key, v in (("pass_att", 1), ("pass_cmp", comp), ("pass_yds", gained),
                               ("pass_td", scored), ("pass_int", t.interception[ra].astype(np.int32))):
                    self._add(st, key, s_, qb, v)
                rz, deep = za <= 20, t.deep[ra]
                who = self._pick(pool, ("tgt_rz", "tgt_deep", "tgt_short"), (rz, ~rz & deep, ~rz & ~deep))
                # A throwaway has no intended receiver: the QB keeps the
                # attempt, nobody gets a target. The draw above still happens
                # so the random stream, and every game outcome, is unchanged.
                if t.targeted is not None:
                    who = np.where(t.targeted[ra], who, -1)
                for key, v in (("tgt", 1), ("rec", comp), ("rec_yds", gained), ("rec_td", scored)):
                    self._add(st, key, s_, who, v)

    def _overtime_over(self):
        """Both sides have had the ball and someone is ahead."""
        m = ~self.done & (self.period == 3) & (self.ot_poss[:, 0] >= 1) & (self.ot_poss[:, 1] >= 1) \
            & (self.points[:, 0] != self.points[:, 1])
        self.done |= m

    def _resume(self, s: LiveStart) -> None:
        """Put every simulated game at the live state instead of kickoff."""
        n, everyone, rng = self.n, np.arange(self.n), self.rng
        t = float(s.elapsed_seconds)
        self.clock[:] = t
        self.period[:] = 1 if t < 1800 else (2 if t < 3600 else 3)
        self.overtime[:] = t >= 3600
        self.points[:, 0], self.points[:, 1] = s.home_points, s.away_points
        if s.second_half_receiver is None:
            self.second_half_receiver = rng.integers(0, 2, n).astype(np.int32)
        else:
            self.second_half_receiver[:] = s.second_half_receiver
        # Checkpoints already passed hold the real score.
        past = CHECKPOINTS <= t
        self.cp_points[:, past] = self.points[:, None, :]
        self.cp_next[:] = int(past.sum())

        if s.pending_conversion is not None:
            self._convert(everyone, s.pending_conversion)
        if s.possession is not None and s.yardline_100 and s.down in (1, 2, 3, 4):
            yl = int(np.clip(s.yardline_100, 1, 99))
            self.off[:] = s.possession
            self.yl[:] = yl
            self.down[:] = s.down
            self.togo[:] = int(np.clip(s.togo or 10, 1, yl))
            self.possessions[:, s.possession] += 1
            if self.track_drives:
                # This path opens a drive without going through _start.
                self.in_drive[:] = True
                self.drive_plays[:] = 0
            return
        if s.kickoff_receiver is not None:
            receiver = np.full(n, s.kickoff_receiver, dtype=np.int32)
        elif self.period[0] == 2 and t == 1800:
            receiver = self.second_half_receiver.copy()
        else:
            receiver = rng.integers(0, 2, n).astype(np.int32)
        self._kickoff(everyone, receiver)

    def run(self, start: LiveStart | None = None) -> SimResult:
        if start is not None:
            self._resume(start)
        else:
            receiver = self.rng.integers(0, 2, self.n).astype(np.int32)
            self.second_half_receiver = 1 - receiver
            self._kickoff(np.arange(self.n), receiver)
        for _ in range(MAX_SNAPS):
            self._transitions()
            live = np.flatnonzero(~self.done)
            if not len(live):
                break
            self._snap(live)
            self._record_checkpoints()
            self._overtime_over()
        else:
            raise RuntimeError(f"{int((~self.done).sum())} simulated games never finished")
        # A game run out by kneeling ends before the clock reaches the last
        # checkpoints; its final score stands at every one of them.
        for k in range(len(CHECKPOINTS)):
            early = self.cp_next <= k
            self.cp_points[early, k] = self.points[early]
        drives = None
        if self.track_drives:
            # Whatever is still open ran out of clock: end of regulation, or the
            # end of overtime. Halftime and kneel-outs were closed as they hap-
            # pened, and in_drive guarantees nothing is counted twice.
            self._close_drives(np.flatnonzero(self.in_drive), DR_CLOCK)
            drives = {"counts": self.drive_counts, "plays": self.drive_play_sums,
                      "fd_hist": self.fd_hist,
                      "down_plays": self.down_plays, "down_conv": self.down_conv,
                      "down_yards": self.down_yards, "down_togo": self.down_togo,
                      "series_started": self.series_started,
                      "series_converted": self.series_converted,
                      "fd_by_penalty": self.fd_by_penalty,
                      "zero_snap_drives": self.zero_snap_drives,
                      "drive_start_sum": self.drive_start_sum}
        return SimResult(
            points=self.points, tds=self.tds, fgs=self.fgs, td_events=self.td_events,
            return_tds=self.ret_tds, overtime=self.overtime, possessions=self.possessions,
            tilt=(self.samplers[0].lam, self.samplers[1].lam), checkpoints=self.cp_points,
            players=self.pstats, drives=drives,
        )


def simulate_game(tables: SimTables, home: Offense, away: Offense,
                  n: int = 10_000, seed: int = 0, wind_mph: float = 0.0,
                  start: LiveStart | None = None, pools: tuple | None = None,
                  game_script: bool = True, track_drives: bool = False,
                  penalty_replay: bool | None = None) -> SimResult:
    """Simulate from kickoff, or with `start` from a game already under way
    (same engine, same team strengths; only the initial state differs).
    With `pools` (home, away), every play is also credited to players.
    `game_script=False` draws plays as if the score never mattered (for
    before/after comparisons). `track_drives` adds the drive-outcome counters
    used by the engine diagnostic; it is off by default so ordinary runs pay
    nothing for it."""
    return _Game(tables, home, away, n, seed, wind_mph, pools,
                 game_script, track_drives, penalty_replay).run(start)


# --- summaries -------------------------------------------------------------

def _quantiles(x: np.ndarray) -> dict:
    q = np.percentile(x, [10, 25, 50, 75, 90])
    return {f"p{p}": float(v) for p, v in zip((10, 25, 50, 75, 90), q)}


def _count_dist(x: np.ndarray, cap: int = 7) -> dict:
    counts = np.bincount(np.minimum(x, cap), minlength=cap + 1) / len(x)
    return {(str(k) if k < cap else f"{cap}+"): round(float(v), 4) for k, v in enumerate(counts)}


def pace_distribution(r: SimResult) -> dict:
    """Cumulative distribution of the total and the home margin at every
    checkpoint. Full CDFs rather than a few quantiles, because early-game
    scores are lumpy (most games are 0-0 after five minutes) and a percentile
    read off a handful of quantiles would mis-rank exactly those states."""
    n = len(r.points)
    totals = np.clip(r.checkpoints.sum(axis=2), 0, PACE_TOTAL_CAP)
    margins = np.clip(r.checkpoints[:, :, 0] - r.checkpoints[:, :, 1], -PACE_MARGIN_CAP, PACE_MARGIN_CAP)
    cdf = lambda x, size: (np.bincount(x, minlength=size).cumsum() / n).round(4).tolist()  # noqa: E731
    return {
        "minutes": (CHECKPOINTS // 60).tolist(),
        "total_min": 0,
        "margin_min": -PACE_MARGIN_CAP,
        "total_cdf": [cdf(totals[:, k], PACE_TOTAL_CAP + 1) for k in range(len(CHECKPOINTS))],
        "margin_cdf": [cdf(margins[:, k] + PACE_MARGIN_CAP, 2 * PACE_MARGIN_CAP + 1)
                       for k in range(len(CHECKPOINTS))],
    }


def summarize(r: SimResult) -> dict:
    home, away = r.points[:, 0], r.points[:, 1]
    margin, total = home - away, home + away
    pairs, freq = np.unique(r.points, axis=0, return_counts=True)
    order = np.argsort(-freq)
    n = len(home)
    # The single most frequent exact score carries well under 1% even in a
    # well-defined game, and its lead over the runner-up is often inside
    # Monte Carlo noise. Count how many scores it cannot be told apart from
    # (two standard errors of the difference) so the report can say so.
    p = freq[order] / n
    se = np.sqrt((p[0] * (1 - p[0]) + p * (1 - p)) / n)
    return {
        "n": n,
        "top_scores": [
            {"home": int(pairs[i, 0]), "away": int(pairs[i, 1]), "prob": round(freq[i] / n, 4)}
            for i in order[:5]
        ],
        "scores_tied_with_mode": int(((p[0] - p[1:]) < 2 * se[1:]).sum()),
        "home_points": _quantiles(home),
        "away_points": _quantiles(away),
        "margin": _quantiles(margin),
        "total": _quantiles(total),
        "mean_home": float(home.mean()),
        "mean_away": float(away.mean()),
        "home_win": float((margin > 0).mean()),
        "away_win": float((margin < 0).mean()),
        "tie": float((margin == 0).mean()),
        "overtime": float(r.overtime.mean()),
        "td": [_count_dist(r.tds[:, s]) for s in (0, 1)],
        "fg": [_count_dist(r.fgs[:, s]) for s in (0, 1)],
        "td_mode": [int(np.bincount(r.tds[:, s]).argmax()) for s in (0, 1)],
        "fg_mode": [int(np.bincount(r.fgs[:, s]).argmax()) for s in (0, 1)],
        "td_mean": [float(r.tds[:, s].mean()) for s in (0, 1)],
        "fg_mean": [float(r.fgs[:, s].mean()) for s in (0, 1)],
        "return_td": [float((r.return_tds[:, s] >= 1).mean()) for s in (0, 1)],
        "possessions": [float(r.possessions[:, s].mean()) for s in (0, 1)],
        "pace": pace_distribution(r),
    }


# Which usage share decides who scores a touchdown of each kind and zone.
SHARE_FOR = {
    (RUSH, GOAL_LINE): "car_gl", (RUSH, RED_ZONE): "car_rz", (RUSH, OPEN_FIELD): "car_all",
    (PASS, GOAL_LINE): "tgt_rz", (PASS, RED_ZONE): "tgt_rz", (PASS, OPEN_FIELD): "tgt_all",
}


def allocate_scorers(r: SimResult, side: int, shares: dict[str, np.ndarray],
                     seed: int = 0) -> np.ndarray:
    """(n, players) touchdown counts, by handing each simulated offensive TD
    to a player in proportion to his share of that kind of opportunity.

    A goal-line rushing TD is assigned by goal-line carry share, a red-zone
    passing TD by red-zone target share, and so on. This is where the output
    turns from game simulation into usage extrapolation, and it is why the
    scorer list is the lowest-confidence thing the simulator reports.
    """
    rng = np.random.default_rng(seed)
    k = len(next(iter(shares.values())))
    counts = np.zeros((len(r.tds), k), dtype=np.int32)
    for (kind, zone), cat in SHARE_FOR.items():
        events = r.td_events[:, side * 6 + kind * 3 + zone]
        p = np.asarray(shares[cat], dtype=float)
        if events.any() and p.sum() > 0:
            counts += rng.multinomial(events, p / p.sum())
    return counts
