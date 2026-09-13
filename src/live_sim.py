"""Live-resume simulation: the pregame engine restarted from the live state.

The live tracker calls this every poll for each game in progress. It is the
same engine with the same team strengths as the pregame simulation, including
its anchor to the pregame prediction; only the starting point differs. The gap
between the two outputs is therefore purely what has happened on the field,
never a change of model:

    before kickoff  predictions / game_simulations   fixed once the game starts
    right now       live_simulations                 one row per poll

Each poll re-uses the same random seed for a given game, so successive
projections differ only because the game state changed, not because of fresh
Monte Carlo noise; the trajectory on the live page moves when something
happens and holds still when nothing does.

Scorer projections start from the pregame usage shares and are pulled toward
each player's share of his team's targets and carries so far in this game
(ESPN's box score), gaining weight as the game accumulates opportunities.
"""

from __future__ import annotations

import time
import zlib

import numpy as np
import pandas as pd

from .ingest_injuries import player_key
from .sim_data import USAGE_CATEGORIES
from .simulate import LiveStart, Offense, SimResult, allocate_scorers, simulate_game, summarize

# live-v1 (2026-09-13 22:28-22:3xZ only) misread the scoreboard's field
# position whenever the HOME side had the ball, starting those simulations at
# the mirror-image yard line. Its rows are kept but not charted.
LIVE_SIM_VERSION = "live-v2"
LIVE_SIMS = 10_000
LIVE_SEED_OFFSET = 101

# Team opportunities of pregame usage that the live game has to outweigh. A
# team runs ~30 targets and ~25 carries a game, so by halftime the game's own
# usage carries about a third of the weight, and by the 4th quarter nearly half.
LIVE_USAGE_PRIOR = 30.0
TOP_LIVE_SCORERS = 6
MIN_LIVE_SCORER_PROB = 0.02

# Plays that carry no down-and-distance of their own.
NON_SNAPS = ("timeout", "end period", "end of half", "end quarter", "two-minute", "end of game")

LIVE_SCORER_NOTE = (
    "Low confidence. Touchdowns from here are assigned by usage share: the pregame "
    "red-zone / goal-line shares, pulled toward each player's share of targets and "
    "carries so far in this game."
)


def _num(value) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _side(team: dict | None, side_by_id: dict[str, int]) -> int | None:
    return side_by_id.get(str((team or {}).get("id")))


# --- reading the live state ------------------------------------------------

def _plays(summary) -> list[dict]:
    """The current drive's plays, oldest first."""
    drives = (summary or {}).get("drives") or {}
    plays = (drives.get("current") or {}).get("plays") or []
    if not plays:
        previous = drives.get("previous") or []
        plays = (previous[-1].get("plays") or []) if previous else []
    return plays


def _is_snap(play: dict) -> bool:
    kind = str((play.get("type") or {}).get("text") or "").lower()
    return not any(k in kind for k in NON_SNAPS)


def opening_receiver(summary, side_by_id) -> int | None:
    """The side that took the opening kickoff: the first drive's offence."""
    previous = ((summary or {}).get("drives") or {}).get("previous") or []
    return _side(previous[0].get("team"), side_by_id) if previous else None


def _after_score(summary, side_by_id) -> tuple[int, int | None] | None:
    """(kickoff receiver, side whose conversion is still to come) when the
    latest real play was a score; None otherwise."""
    snaps = [p for p in _plays(summary) if _is_snap(p)]
    if not snaps or not snaps[-1].get("scoringPlay"):
        return None
    scoring = ((summary or {}).get("scoringPlays") or [{}])[-1]
    scorer = _side(scoring.get("team"), side_by_id)
    if scorer is None:
        return None
    kind = str((scoring.get("type") or {}).get("text") or "").lower()
    if "safety" in kind:
        return scorer, None          # the side that conceded free-kicks to the scorer
    # ESPN appends the try to the touchdown's text once it happens:
    # "... pass from Kirk Cousins (Matt Gay Kick)".
    pending = scorer if "touchdown" in kind and "(" not in str(scoring.get("text") or "") else None
    return 1 - scorer, pending


def _last_snap(summary, side_by_id) -> tuple[int, int, int, int] | None:
    """(side, yardline_100, down, distance) as the last real snap ended.

    A play's `end.yardLine` counts from a fixed end of the field;
    `yardsToEndzone` is the offence's own distance to score, which is what
    the engine calls yardline_100.
    """
    for play in reversed(_plays(summary)):
        end = play.get("end") or {}
        down, to_go_zone = end.get("down"), end.get("yardsToEndzone")
        side = _side(end.get("team"), side_by_id)
        if side is not None and down in (1, 2, 3, 4) and to_go_zone and 0 < to_go_zone < 100:
            return side, int(to_go_zone), int(down), int(end.get("distance") or 10)
    return None


def live_start(elapsed_seconds: float, halftime: bool, home_points: int, away_points: int,
               situation: dict | None, summary, side_by_id: dict[str, int]) -> tuple[LiveStart, str]:
    """Where the rest of the game starts from, and which source said so.

    In order of trust: halftime (the second-half kickoff), the scoreboard's
    live situation, a score that has just happened (a kickoff is next), then
    the end of the last real snap in the summary. With none of those the
    next event is treated as a kickoff to an unknown receiver.
    """
    first = opening_receiver(summary, side_by_id)
    second = None if first is None else 1 - first
    base = dict(home_points=int(home_points), away_points=int(away_points), second_half_receiver=second)
    if halftime:
        return LiveStart(elapsed_seconds=1800.0, kickoff_receiver=second, **base), "halftime: second-half kickoff"

    t = float(elapsed_seconds)
    sit = situation or {}
    if sit.get("possession") is not None and sit.get("down") in (1, 2, 3, 4) and sit.get("yardline_100"):
        return LiveStart(elapsed_seconds=t, possession=sit["possession"], yardline_100=sit["yardline_100"],
                         down=sit["down"], togo=sit.get("togo"), **base), "scoreboard"
    after = _after_score(summary, side_by_id)
    if after:
        receiver, pending = after
        return (LiveStart(elapsed_seconds=t, kickoff_receiver=receiver, pending_conversion=pending, **base),
                "kickoff after a score")
    last = _last_snap(summary, side_by_id)
    if last:
        side, yl, down, togo = last
        return LiveStart(elapsed_seconds=t, possession=side, yardline_100=yl, down=down, togo=togo,
                         **base), "last play"
    return LiveStart(elapsed_seconds=t, **base), "state unknown: kickoff to a coin-flip receiver"


def _ordinal(n: int) -> str:
    return {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}.get(n, f"{n}th")


def describe(start: LiveStart, home: str, away: str) -> str:
    teams = (home, away)
    if start.possession is not None and start.down:
        yl = int(start.yardline_100)
        spot = "midfield" if yl == 50 else (f"own {100 - yl}" if yl > 50 else f"{teams[1 - start.possession]} {yl}")
        togo = "goal" if (start.togo or 10) >= yl else str(start.togo)
        return f"{teams[start.possession]} ball, {_ordinal(start.down)} & {togo} at {spot}"
    text = (f"kickoff to {teams[start.kickoff_receiver]}" if start.kickoff_receiver is not None
            else "kickoff, receiver unknown (coin flip)")
    if start.pending_conversion is not None:
        text += f", {teams[start.pending_conversion]} extra point still to come"
    return text


# --- usage so far ----------------------------------------------------------

def game_usage(summary, side_by_id: dict[str, int]) -> dict[int, dict[str, dict]]:
    """Each side's carries, targets and touchdowns so far, by player."""
    out: dict[int, dict[str, dict]] = {0: {}, 1: {}}
    for block in ((summary or {}).get("boxscore") or {}).get("players") or []:
        side = _side(block.get("team"), side_by_id)
        if side is None:
            continue
        for stat in block.get("statistics") or []:
            kind = stat.get("name")
            if kind not in ("rushing", "receiving"):
                continue
            keys = stat.get("keys") or []
            for athlete in stat.get("athletes") or []:
                name = (athlete.get("athlete") or {}).get("displayName")
                if not name:
                    continue
                values = dict(zip(keys, athlete.get("stats") or []))
                rec = out[side].setdefault(name, {"name": name, "car": 0, "tgt": 0, "td": 0})
                if kind == "rushing":
                    rec["car"] += _num(values.get("rushingAttempts"))
                    rec["td"] += _num(values.get("rushingTouchdowns"))
                else:
                    rec["tgt"] += _num(values.get("receivingTargets"))
                    rec["td"] += _num(values.get("receivingTouchdowns"))
    return out


def blend_usage(squad: pd.DataFrame, shares: dict[str, np.ndarray], usage: dict[str, dict],
                team: str) -> tuple[pd.DataFrame, dict[str, np.ndarray], dict]:
    """Pregame shares pulled toward this game's usage.

    For targets and carries separately, each player's broad share becomes
        w * share of the team's opportunities so far + (1 - w) * pregame share,
        w = opportunities so far / (opportunities so far + LIVE_USAGE_PRIOR),
    and his red-zone / goal-line shares are scaled by the same factor, since
    the box score does not break usage down by field position. A player the
    depth chart did not have (a backup pressed into service) joins with his
    live share in every category.
    """
    known = {player_key(team, p) for p in squad["player"]}
    extra = [u for u in usage.values()
             if player_key(team, u["name"]) not in known and u["car"] + u["tgt"] > 0]
    if extra:
        add = pd.DataFrame({"player": [u["name"] for u in extra], "position": "", "rank": 99, "play_prob": 1.0})
        squad = pd.concat([squad, add], ignore_index=True)
    else:
        squad = squad.reset_index(drop=True).copy()
    n = len(squad)

    index: dict[tuple, int] = {}
    for i, p in enumerate(squad["player"]):
        index.setdefault(player_key(team, p), i)
    game = {g: np.zeros(n) for g in ("car", "tgt", "td")}
    for u in usage.values():
        i = index.get(player_key(team, u["name"]))
        if i is not None:
            for g in game:
                game[g][i] += u[g]

    def pad(v):
        v = np.asarray(v, dtype=float)
        return np.concatenate([v, np.zeros(n - len(v))])

    base = {c: pad(shares[c]) for c in USAGE_CATEGORIES}
    out, info = {}, {}
    for group, broad, narrow in (("tgt", "tgt_all", ("tgt_rz",)), ("car", "car_all", ("car_rz", "car_gl"))):
        counts, total = game[group], float(game[group].sum())
        weight = total / (total + LIVE_USAGE_PRIOR)
        pre = base[broad] / base[broad].sum() if base[broad].sum() > 0 else base[broad]
        now = counts / total if total > 0 else np.zeros(n)
        blended = weight * now + (1 - weight) * pre
        out[broad] = blended
        factor = np.divide(blended, pre, out=np.zeros(n), where=pre > 0)
        for c in narrow:
            v = np.where(pre > 0, base[c] * factor, blended)
            out[c] = v / v.sum() if v.sum() > 0 else v
        info[group] = {"opportunities": int(total), "live_weight": round(weight, 3)}
    squad = squad.assign(game_car=game["car"], game_tgt=game["tgt"], game_td=game["td"])
    return squad, out, info


def live_scorers(result: SimResult, side: int, squad: pd.DataFrame,
                 shares: dict[str, np.ndarray], seed: int) -> list[dict]:
    """Players most likely to score a touchdown from here, plus anyone who
    already has one."""
    counts = allocate_scorers(result, side, shares, seed)
    more = (counts >= 1).mean(axis=0)
    picked = [i for i in np.argsort(-more)[:TOP_LIVE_SCORERS] if more[i] >= MIN_LIVE_SCORER_PROB]
    picked += [i for i in np.flatnonzero(squad["game_td"].to_numpy() > 0) if i not in picked]
    out = []
    for i in picked:
        rank = int(squad.at[i, "rank"])
        out.append({
            "player": squad.at[i, "player"],
            "position": squad.at[i, "position"] or None,
            "depth_rank": rank if rank < 99 else None,
            "td_from_here": round(float(more[i]), 4),
            "expected_more": round(float(counts[:, i].mean()), 3),
            "tds_so_far": int(squad.at[i, "game_td"]),
            "game_carries": int(squad.at[i, "game_car"]),
            "game_targets": int(squad.at[i, "game_tgt"]),
        })
    return out


# --- the simulator ---------------------------------------------------------

class LiveSimulator:
    def __init__(self, tables, roles: pd.DataFrame, injuries: list[dict], n: int | None = None):
        self.tables, self.roles, self.injuries = tables, roles, injuries
        self.n = n or LIVE_SIMS
        self._bases: dict[str, tuple] = {}

    def _base(self, team: str):
        """Pregame depth-chart shares with injuries applied, once per team."""
        if team not in self._bases:
            from .simulate_nfl import team_shares

            squad, shares, _shifts = team_shares(self.roles, team, self.injuries)
            self._bases[team] = (squad, shares)
        return self._bases[team]

    def run(self, *, game_id: str, home: str, away: str, offense: dict, start: LiveStart,
            summary, side_by_id: dict[str, int]) -> tuple[dict, dict]:
        """(live_simulations column values, extra detail for the live page)."""
        t0 = time.perf_counter()
        seed = zlib.crc32(game_id.encode()) + LIVE_SEED_OFFSET
        result = simulate_game(
            self.tables,
            Offense(offense["home"]["target_epa"], offense["home"].get("pass_rate_oe") or 0.0),
            Offense(offense["away"]["target_epa"], offense["away"].get("pass_rate_oe") or 0.0),
            n=self.n, seed=seed, wind_mph=offense.get("wind_mph") or 0.0, start=start,
        )
        s = summarize(result)

        usage = game_usage(summary, side_by_id)
        scorers, usage_weight = {}, {}
        for side, key, team in ((0, "home", home), (1, "away", away)):
            squad, shares = self._base(team)
            blended_squad, blended, info = blend_usage(squad, shares, usage[side], team)
            scorers[key] = live_scorers(result, side, blended_squad, blended, seed + 11 + side)
            usage_weight[team] = info

        top = s["top_scores"][0]
        r4 = lambda v: round(float(v), 4)  # noqa: E731
        fields = {
            "n_sims": self.n,
            "home_win_prob": r4(s["home_win"]),
            "away_win_prob": r4(s["away_win"]),
            "tie_prob": r4(s["tie"]),
            "modal_home_points": top["home"],
            "modal_away_points": top["away"],
            "modal_score_prob": top["prob"],
            "median_home_points": s["home_points"]["p50"],
            "median_away_points": s["away_points"]["p50"],
            "mean_margin_home": r4(s["mean_home"] - s["mean_away"]),
            "margin_80_low": s["margin"]["p10"],
            "margin_80_high": s["margin"]["p90"],
            "total_median": s["total"]["p50"],
            "total_80_low": s["total"]["p10"],
            "total_80_high": s["total"]["p90"],
            "scorers": {"confidence": "low", "note": LIVE_SCORER_NOTE,
                        "home": scorers["home"], "away": scorers["away"], "live_usage": usage_weight},
            "runtime_ms": int((time.perf_counter() - t0) * 1000),
        }
        extra = {
            "top_scores": s["top_scores"],
            "scores_tied_with_mode": s["scores_tied_with_mode"],
            "mean_home_points": r4(s["mean_home"]),
            "mean_away_points": r4(s["mean_away"]),
        }
        return fields, extra
