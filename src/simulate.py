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
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .sim_data import FG, GO, N_PUNT_BINS, PUNT, SimTables, bucket_index
from .sim_data import FOURTH_TOGO_EDGES

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


class _Sampler:
    def __init__(self, tables: SimTables, offense: Offense):
        base = tables.base_weights(offense.pass_rate_oe)
        self.lam = solve_tilt(tables.epa, base, offense.target_epa)
        self.cdf = tables.segment_cdf(base * np.exp(self.lam * tables.epa))
        self.tables = tables

    def draw(self, rng: np.random.Generator, down, togo, yl) -> np.ndarray:
        b = self.tables.bucket_map[bucket_index(down, togo, yl)]
        return np.searchsorted(self.cdf, b + rng.random(len(b)), side="right")


class _Game:
    def __init__(self, tables: SimTables, home: Offense, away: Offense,
                 n: int, seed: int, wind_mph: float):
        self.t = tables
        self.rng = np.random.default_rng(seed)
        self.samplers = (_Sampler(tables, home), _Sampler(tables, away))
        self.wind = wind_mph
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

    def _end(self, ix):
        """The side with the ball has finished a possession. Only overtime
        cares, since both sides must have had the ball before it can end."""
        ot = ix[self.period[ix] == 3]
        self.ot_poss[ot, self.off[ot]] += 1

    def _touchdown(self, ix, side):
        rng = self.rng
        self.points[ix, side] += 6
        self.tds[ix, side] += 1
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
            self.period[half] = 2
            self.clock[half] = 1800
            self._kickoff(half, self.second_half_receiver[half])

        end = live & (self.period == 2) & (self.clock >= 3600)
        tied = self.points[:, 0] == self.points[:, 1]
        self.done |= end & ~tied
        ot = np.flatnonzero(end & tied)
        if len(ot):
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
        self._end(ix)
        good, miss = ix[made], ix[~made]
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
        self._end(ix)
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
        for side in (0, 1):
            m = off == side
            if m.any():
                s = ix[m]
                rows[m] = self.samplers[side].draw(self.rng, self.down[s], self.togo[s], self.yl[s])

        yl, togo = self.yl[ix], self.togo[ix]
        y = t.yards[rows].astype(np.int32)
        pen = t.is_penalty[rows]
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

        if dtd.any():
            i, side = ix[dtd], 1 - off[dtd]
            self._end(i)
            self._touchdown(i, side)
            self.ret_tds[i, side] += 1
            self._kickoff(i, off[dtd])

        if lost.any():
            r = rows[lost]
            shifted = t.next_start[r] - (yl[lost] - t.yl_orig[r])
            spot = 100 - np.clip(new[lost], 1, 99)
            opp = np.where(np.isnan(shifted), spot, shifted).astype(np.int32)
            self._end(ix[lost])
            self._start(ix[lost], 1 - off[lost], opp)

        if otd.any():
            i, side = ix[otd], off[otd]
            kind = np.where(t.is_rush[rows[otd]], RUSH, PASS)
            zone = np.where(yl[otd] <= 5, GOAL_LINE, np.where(yl[otd] <= 20, RED_ZONE, OPEN_FIELD))
            self.td_events[i, side * 6 + kind * 3 + zone] += 1
            self._end(i)
            self._touchdown(i, side)
            self._kickoff(i, 1 - side)

        if safety.any():
            i, side = ix[safety], off[safety]
            self.points[i, 1 - side] += 2
            self._end(i)
            self._kickoff(i, 1 - side)

        if cont.any():
            i = ix[cont]
            yc, nc, tc = y[cont], new[cont], togo[cont]
            first = (yc >= tc) | t.fd_penalty[rows[cont]]
            down = np.where(first, 1, self.down[i] + 1)
            self.yl[i] = nc
            self.down[i] = down
            self.togo[i] = np.maximum(np.where(first, np.minimum(10, nc), tc - yc), 1)
            downs = down > 4
            if downs.any():
                j = i[downs]
                self._end(j)
                self._start(j, 1 - self.off[j], 100 - nc[downs])

    def _overtime_over(self):
        """Both sides have had the ball and someone is ahead."""
        m = ~self.done & (self.period == 3) & (self.ot_poss[:, 0] >= 1) & (self.ot_poss[:, 1] >= 1) \
            & (self.points[:, 0] != self.points[:, 1])
        self.done |= m

    def run(self) -> SimResult:
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
        return SimResult(
            points=self.points, tds=self.tds, fgs=self.fgs, td_events=self.td_events,
            return_tds=self.ret_tds, overtime=self.overtime, possessions=self.possessions,
            tilt=(self.samplers[0].lam, self.samplers[1].lam), checkpoints=self.cp_points,
        )


def simulate_game(tables: SimTables, home: Offense, away: Offense,
                  n: int = 10_000, seed: int = 0, wind_mph: float = 0.0) -> SimResult:
    return _Game(tables, home, away, n, seed, wind_mph).run()


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
