"""Quarterback-conditional prior-season offense (P13).

Early in a season an NFL rating is mostly last season's, and last season's
offense is an average over whoever played quarterback. KC's 2025 offense was
+0.097 EPA/play in Mahomes' 14 starts and -0.347 in the three backup starts
after his injury; averaging both cost KC ~2.9 points of rating in week 1 of
2026, with Mahomes starting.

So the prior-season offense is taken from the games started by the
quarterback expected to start now, when he started enough of them for the
same team to be a real sample. A starter who is new to the team (traded,
signed, drafted) falls back to the team's whole season: his number elsewhere
came with a different offense around him, and that is a bigger model than
this. Defense is untouched; a team's own quarterback doesn't play it.

Starters come from nflverse schedules, which carry each game's starting
quarterback (home_qb_id / away_qb_id) for completed games and list the
expected starter for the next week's games. A game's starter is known at
kickoff, so conditioning on it adds no lookahead.
"""

from __future__ import annotations

import math

MIN_STARTS = 4  # fewer starts for the team than this and the prior isn't conditioned


def qb_id(value) -> str | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    text = str(value).strip()
    return text or None


def game_starters(schedules) -> dict[tuple[str, str], str]:
    """(game_id, team) -> starting quarterback's gsis id."""
    out: dict[tuple[str, str], str] = {}
    for g in schedules.itertuples(index=False):
        for team, qb in ((g.home_team, getattr(g, "home_qb_id", None)),
                         (g.away_team, getattr(g, "away_qb_id", None))):
            if (qb := qb_id(qb)) is not None:
                out[(str(g.game_id), str(team))] = qb
    return out


def expected_starters(schedules, season: int) -> dict[str, str]:
    """team -> the quarterback expected to start its next game this season.

    The next unplayed game's listed starter where nflverse has one, otherwise
    whoever started the team's most recent game this season.
    """
    games = schedules[schedules["season"] == season].sort_values(["week", "gameday"])
    listed: dict[str, str] = {}
    latest: dict[str, str] = {}
    for g in games.itertuples(index=False):
        played = g.home_score == g.home_score  # not NaN
        for team, qb in ((g.home_team, g.home_qb_id), (g.away_team, g.away_qb_id)):
            if (qb := qb_id(qb)) is None:
                continue
            if played:
                latest[str(team)] = qb
            else:
                listed.setdefault(str(team), qb)
    return {**latest, **listed}


def conditional_offense(plays, starters: dict[tuple[str, str], str],
                        team: str, qb: str | None) -> tuple[float, int, int] | None:
    """Offensive EPA/play over the games `qb` started for `team` in `plays`.

    `plays` are one season's scrimmage plays (posteam, game_id, epa). Returns
    (mean, plays, starts), or None when he started fewer than MIN_STARTS of
    them, in which case the caller keeps the whole-season number.
    """
    if qb is None:
        return None
    team_plays = plays[plays["posteam"] == team]
    started = {gid for gid in team_plays["game_id"].astype(str).unique()
               if starters.get((gid, team)) == qb}
    if len(started) < MIN_STARTS:
        return None
    mine = team_plays[team_plays["game_id"].astype(str).isin(started)]["epa"]
    if not len(mine):
        return None
    return float(mine.mean()), int(len(mine)), len(started)
