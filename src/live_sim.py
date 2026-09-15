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

Players are tracked through the rest of the game exactly as pregame, and each
projected line is the player's box score so far (ESPN) plus his simulated
remainder. Usage shares start from pregame and are pulled toward each
player's share of his team's targets and carries so far in this game, gaining
weight as the game accumulates opportunities.
"""

from __future__ import annotations

import time
import zlib

import numpy as np
import pandas as pd

from .box_score import BOX_CONFIDENCE, BOX_NOTE, box_score, player_pool, td_counts
from .ingest_injuries import player_key
from .sim_data import USAGE_CATEGORIES
from .simulate import (
    STAT_NAMES, LiveStart, Offense, SimResult, _count_dist, allocate_scorers, simulate_game, summarize,
)

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

# The box-score fields read from ESPN, and the engine stat each one feeds.
_BLANK = dict.fromkeys(("car", "tgt", "td", "rush_yds", "rush_td", "rec", "rec_yds", "rec_td",
                        "pass_att", "pass_cmp", "pass_yds", "pass_td", "pass_int"), 0)
SO_FAR = {
    "pass_att": "pass_att", "pass_cmp": "pass_cmp", "pass_yds": "pass_yds", "pass_td": "pass_td",
    "pass_int": "pass_int", "rush_att": "car", "rush_yds": "rush_yds", "rush_td": "rush_td",
    "tgt": "tgt", "rec": "rec", "rec_yds": "rec_yds", "rec_td": "rec_td",
}


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


# --- the box score so far --------------------------------------------------

def game_usage(summary, side_by_id: dict[str, int]) -> dict[int, dict[str, dict]]:
    """Each side's box score so far, by player: passing, carries, targets,
    receptions, yards and touchdowns, from ESPN's summary."""
    out: dict[int, dict[str, dict]] = {0: {}, 1: {}}
    for block in ((summary or {}).get("boxscore") or {}).get("players") or []:
        side = _side(block.get("team"), side_by_id)
        if side is None:
            continue
        for stat in block.get("statistics") or []:
            kind = stat.get("name")
            if kind not in ("passing", "rushing", "receiving"):
                continue
            keys = stat.get("keys") or []
            for athlete in stat.get("athletes") or []:
                name = (athlete.get("athlete") or {}).get("displayName")
                if not name:
                    continue
                v = dict(zip(keys, athlete.get("stats") or []))
                rec = out[side].setdefault(name, {"name": name, **_BLANK})
                if kind == "passing":
                    done, tried = (str(v.get("completions/passingAttempts") or "0/0").split("/") + ["0"])[:2]
                    rec["pass_cmp"] += _num(done)
                    rec["pass_att"] += _num(tried)
                    rec["pass_yds"] += _num(v.get("passingYards"))
                    rec["pass_td"] += _num(v.get("passingTouchdowns"))
                    rec["pass_int"] += _num(v.get("interceptions"))
                elif kind == "rushing":
                    td = _num(v.get("rushingTouchdowns"))
                    rec["car"] += _num(v.get("rushingAttempts"))
                    rec["rush_yds"] += _num(v.get("rushingYards"))
                    rec["rush_td"] += td
                    rec["td"] += td
                else:
                    td = _num(v.get("receivingTouchdowns"))
                    rec["tgt"] += _num(v.get("receivingTargets"))
                    rec["rec"] += _num(v.get("receptions"))
                    rec["rec_yds"] += _num(v.get("receivingYards"))
                    rec["rec_td"] += td
                    rec["td"] += td
    return out


def scoring_so_far(summary, side_by_id) -> tuple[list[int], list[int]]:
    """(touchdowns, field goals) per side, from the scoring plays."""
    tds, fgs = [0, 0], [0, 0]
    for p in (summary or {}).get("scoringPlays") or []:
        side = _side(p.get("team"), side_by_id)
        kind = str((p.get("type") or {}).get("text") or "").lower()
        if side is None:
            continue
        if "touchdown" in kind:
            tds[side] += 1
        elif "field goal" in kind:
            fgs[side] += 1
    return tds, fgs


def so_far_lines(squad: pd.DataFrame, usage: dict[str, dict], team: str) -> dict[str, np.ndarray]:
    """Each squad row's line so far, in the engine's stat names."""
    by_key = {player_key(team, u["name"]): u for u in usage.values()}
    out = {k: np.zeros(len(squad), dtype=np.int32) for k in STAT_NAMES}
    for i, name in enumerate(squad["player"]):
        u = by_key.get(player_key(team, name))
        if u:
            for k, src in SO_FAR.items():
                out[k][i] = u[src]
    return out


def blend_usage(squad: pd.DataFrame, shares: dict[str, np.ndarray], usage: dict[str, dict],
                team: str) -> tuple[pd.DataFrame, dict[str, np.ndarray], dict]:
    """Pregame shares pulled toward this game's usage.

    For targets and carries separately, each player's broad share becomes
        w * share of the team's opportunities so far + (1 - w) * pregame share,
        w = opportunities so far / (opportunities so far + LIVE_USAGE_PRIOR),
    and his red-zone / goal-line / short / deep shares are scaled by the same
    factor, since the box score does not break usage down that finely. A
    player the depth chart did not have (a backup pressed into service) joins
    with his live share in every category.
    """
    known = {player_key(team, p) for p in squad["player"]}
    extra = [u for u in usage.values()
             if player_key(team, u["name"]) not in known
             and u["car"] + u["tgt"] + u.get("pass_att", 0) > 0]
    if extra:
        add = pd.DataFrame({
            "player": [u["name"] for u in extra],
            "position": ["QB" if u.get("pass_att", 0) > u["car"] + u["tgt"] else "" for u in extra],
            "rank": 99, "play_prob": 1.0,
        })
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
    for group, broad, narrow in (("tgt", "tgt_all", ("tgt_rz", "tgt_short", "tgt_deep")),
                                 ("car", "car_all", ("car_rz", "car_gl"))):
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
    counts = (td_counts(result.players[side]) if result.players is not None
              else allocate_scorers(result, side, shares, seed))
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
        """(live_simulations column values, extra detail for the live views)."""
        t0 = time.perf_counter()
        seed = zlib.crc32(game_id.encode()) + LIVE_SEED_OFFSET
        usage = game_usage(summary, side_by_id)

        sides = []
        for side, team in ((0, home), (1, away)):
            squad, shares = self._base(team)
            blended_squad, blended, info = blend_usage(squad, shares, usage[side], team)
            so_far = so_far_lines(blended_squad, usage[side], team)
            passer = None
            if so_far["pass_att"].max() > 0:
                # Whoever has been throwing today throws the rest of the game.
                passer = np.zeros(len(blended_squad))
                passer[int(so_far["pass_att"].argmax())] = 1.0
            sides.append((team, blended_squad, blended, info, so_far,
                          player_pool(blended_squad, blended, passer)))

        result = simulate_game(
            self.tables,
            Offense(offense["home"]["target_epa"], offense["home"].get("pass_rate_oe") or 0.0),
            Offense(offense["away"]["target_epa"], offense["away"].get("pass_rate_oe") or 0.0),
            n=self.n, seed=seed, wind_mph=offense.get("wind_mph") or 0.0, start=start,
            pools=(sides[0][5], sides[1][5]),
        )
        s = summarize(result)
        tds_so_far, fgs_so_far = scoring_so_far(summary, side_by_id)

        scorers, usage_weight, boxes = {}, {}, {}
        for side, (team, squad, shares, info, so_far, _pool) in enumerate(sides):
            key = ("home", "away")[side]
            scorers[key] = live_scorers(result, side, squad, shares, seed + 11 + side)
            usage_weight[team] = info
            boxes[key] = box_score(result.players[side], squad, so_far)
        final_td = [result.tds[:, i] + tds_so_far[i] for i in (0, 1)]
        final_fg = [result.fgs[:, i] + fgs_so_far[i] for i in (0, 1)]

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
            "box_score": {"confidence": BOX_CONFIDENCE, "note": BOX_NOTE, **boxes},
            "runtime_ms": int((time.perf_counter() - t0) * 1000),
        }
        extra = {
            "top_scores": s["top_scores"],
            "scores_tied_with_mode": s["scores_tied_with_mode"],
            "mean_home_points": r4(s["mean_home"]),
            "mean_away_points": r4(s["mean_away"]),
            "home_points": s["home_points"], "away_points": s["away_points"],
            "margin": s["margin"], "total": s["total"],
            "td": [_count_dist(x) for x in final_td], "fg": [_count_dist(x) for x in final_fg],
            "td_mode": [int(np.bincount(x).argmax()) for x in final_td],
            "fg_mode": [int(np.bincount(x).argmax()) for x in final_fg],
            "td_so_far": tds_so_far, "fg_so_far": fgs_so_far,
        }
        return fields, extra
