"""Projected box scores from the simulator.

The engine credits every simulated play to a player (simulate._Game._credit):
a designed run to a ball carrier chosen by carry share for that part of the
field, a scramble and every pass to that simulated game's quarterback, and a
target to a receiver chosen by red-zone, short or deep target share. The
shares are the same injury- and depth-chart-adjusted usage shares the TD
scorer projections use. This module builds those player pools and turns the
per-simulation stat lines into projections, summarised the way the score is:
median, mean, the mode for counts, and the middle 50% / 80% of simulations.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .simulate import STAT_NAMES, PlayerPool

POOL_CATEGORIES = ("car_all", "car_rz", "car_gl", "tgt_short", "tgt_deep", "tgt_rz")

# A player makes the box score with at least this much projected work.
MIN_TOUCHES = 1.0          # carries + targets, on average
MIN_PASS_ATT = 3.0
MIN_GROUP = 0.5            # a rushing / receiving line needs this many on average

COUNT_KEYS = {"att", "cmp", "td", "int", "tgt", "rec"}
GROUPS = {
    "passing": (("att", "pass_att"), ("cmp", "pass_cmp"), ("yds", "pass_yds"),
                ("td", "pass_td"), ("int", "pass_int")),
    "rushing": (("att", "rush_att"), ("yds", "rush_yds"), ("td", "rush_td")),
    "receiving": (("tgt", "tgt"), ("rec", "rec"), ("yds", "rec_yds"), ("td", "rec_td")),
}

BOX_CONFIDENCE = "low"
BOX_NOTE = (
    "Lower confidence than the score and win projections. Each player's volume comes from "
    "his historical usage shares, adjusted for injuries and the current depth chart, and his "
    "yards per touch from league plays in the same situation rather than his own efficiency. "
    "Usage shifts week to week in ways past shares don't capture."
)


def passer_weights(squad: pd.DataFrame) -> np.ndarray:
    """How likely each player is to be a simulated game's quarterback: the
    starter at his play probability, the next man with what is left."""
    squad = squad.reset_index(drop=True)
    weights = np.zeros(len(squad))
    remaining = 1.0
    qbs = squad[squad["position"] == "QB"].sort_values("rank")
    for i, row in qbs.iterrows():
        q = row.get("play_prob", 1.0)
        q = 1.0 if q is None or pd.isna(q) else float(q)
        weights[i] = remaining * q
        remaining *= 1.0 - q
    if weights.sum() <= 0 and len(qbs):
        weights[qbs.index[0]] = 1.0
    return weights


def player_pool(squad: pd.DataFrame, shares: dict[str, np.ndarray],
                passer: np.ndarray | None = None) -> PlayerPool:
    squad = squad.reset_index(drop=True)
    return PlayerPool(
        names=list(squad["player"]),
        cum={c: np.cumsum(np.asarray(shares[c], dtype=float)) for c in POOL_CATEGORIES},
        passer_weights=passer_weights(squad) if passer is None else np.asarray(passer, dtype=float),
    )


def _quantiles(x: np.ndarray, count: bool) -> dict:
    q = np.percentile(x, [10, 25, 50, 75, 90])
    out = {"median": round(float(q[2]), 1), "mean": round(float(x.mean()), 2),
           "p10": round(float(q[0]), 1), "p25": round(float(q[1]), 1),
           "p75": round(float(q[3]), 1), "p90": round(float(q[4]), 1)}
    if count:
        out["mode"] = int(np.bincount(np.clip(x, 0, None).astype(np.int64)).argmax())
    return out


def td_counts(stats: dict[str, np.ndarray]) -> np.ndarray:
    """(n, players) touchdowns scored (rushing + receiving) per simulation."""
    return stats["rush_td"] + stats["rec_td"]


def box_score(stats: dict[str, np.ndarray], squad: pd.DataFrame,
              so_far: dict[str, np.ndarray] | None = None) -> dict:
    """Projected stat lines for one side.

    `stats` holds (n, players) arrays from the engine. `so_far` (live only)
    holds each player's line in the game so far, added to every simulation
    so the result is a projected *final* line.
    """
    squad = squad.reset_index(drop=True)
    final = {k: stats[k] + (so_far[k][None, :] if so_far is not None else 0) for k in STAT_NAMES}
    players = []
    for i in range(len(squad)):
        volume = {
            "passing": float(final["pass_att"][:, i].mean()),
            "rushing": float(final["rush_att"][:, i].mean()),
            "receiving": float(final["tgt"][:, i].mean()),
        }
        touches = volume["rushing"] + volume["receiving"]
        if touches < MIN_TOUCHES and volume["passing"] < MIN_PASS_ATT:
            continue
        rank = squad.at[i, "rank"]
        entry = {
            "player": squad.at[i, "player"],
            "position": squad.at[i, "position"] or None,
            "depth_rank": int(rank) if pd.notna(rank) and int(rank) < 99 else None,
            "touches": round(touches, 1),
        }
        for group, keys in GROUPS.items():
            if volume[group] >= (MIN_PASS_ATT if group == "passing" else MIN_GROUP):
                entry[group] = {name: _quantiles(final[key][:, i], name in COUNT_KEYS) for name, key in keys}
        tds = final["rush_td"][:, i] + final["rec_td"][:, i]
        entry["anytime_td"] = round(float((tds >= 1).mean()), 4)
        entry["two_plus_td"] = round(float((tds >= 2).mean()), 4)
        if so_far is not None:
            entry["so_far"] = {k: int(so_far[k][i]) for k in STAT_NAMES if so_far[k][i]}
        players.append(entry)
    players.sort(key=lambda p: ("passing" not in p, -p["touches"]))
    team = {name: _quantiles(final[name].sum(axis=1), name.endswith("att"))
            for name in ("pass_att", "pass_yds", "rush_att", "rush_yds")}
    return {"players": players, "team": team}
