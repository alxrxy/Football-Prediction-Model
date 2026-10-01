"""Hand-transcribed injury/practice report (P64).

The user reads official team injury reports from screenshots and types them
into one CSV per week, dropped in before a refresh:

    data/manual_injuries/<season>-wk<NN>.csv      e.g. 2026-wk04.csv

    # season=2026 week=4
    team,player,pos,injury,d1,d2,d3,game
    PIT,Jalen Ramsey,CB,Hamstring,DNP,LP,LP,Questionable
    NO,Kendre Miller,RB,Knee,LP,FP,FP,

- `team`: store codes (the Rams are LA). `pos`: a key of features.STARTER_SLOTS.
- `d1 d2 d3`: DNP / LP / FP / - (also Limit, Full). Only the last day that is
  not `-` is used; days 1-2 are kept in the file for P47 and change nothing.
- `game`: Out / Doubtful / Questionable / IR / blank. No Probable: the play
  probability table has no entry for it and would fall back to 0.50.

Play probability is `ingest_injuries.play_probability(game, practice)`, the
same table the feeds go through. The whole file is validated before any of it
is used, and every error is reported at once with its line number: a skipped
row cannot be told apart from a healthy player, so nothing is skipped quietly.
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

from . import config
from .features import MANUAL_SOURCE

MANUAL_DIR = config.DATA_DIR / "manual_injuries"
SOURCE = MANUAL_SOURCE
COLUMNS = ["team", "player", "pos", "injury", "d1", "d2", "d3", "game"]

PRACTICE = {
    "dnp": "dnp", "lp": "limited", "limit": "limited", "limited": "limited",
    "fp": "full", "full": "full", "-": None,
}
STATUS = {"out": "out", "doubtful": "doubtful", "questionable": "questionable",
          "ir": "ir", "": None}

_SEASON = re.compile(r"\bseason\s*=\s*(\d{4})\b", re.IGNORECASE)
_WEEK = re.compile(r"\bweek\s*=\s*(\d{1,2})\b", re.IGNORECASE)


class ManualFileError(ValueError):
    """The file is invalid; the message lists every error found."""


def path_for(season: int, week: int) -> Path:
    return MANUAL_DIR / f"{season}-wk{week:02d}.csv"


def is_healthy(status: str | None, practice: str | None) -> bool:
    """A row the nflverse ingest would skip: no game status and a full (or no)
    practice. It carries no charge; in the merge it clears the player."""
    return status is None and practice in (None, "full")


def parse(text: str, season: int, week: int, teams: set[str], positions: set[str],
          name: str = "manual file") -> list[dict]:
    """Every row of the file, or ManualFileError listing all problems."""
    from .ingest_injuries import player_key

    errors: list[str] = []
    header_season = header_week = None
    body: list[tuple[int, str]] = []
    for n, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            if (m := _SEASON.search(stripped)):
                header_season = int(m.group(1))
            if (m := _WEEK.search(stripped)):
                header_week = int(m.group(1))
            continue
        if stripped:
            body.append((n, line))

    if header_season is None or header_week is None:
        errors.append("missing '# season=<yyyy> week=<n>' comment line")
    elif (header_season, header_week) != (season, week):
        errors.append(f"file is for season {header_season} week {header_week}; "
                      f"this run is season {season} week {week}")

    if not body:
        errors.append("no column header and no rows")
    else:
        n, first = body[0]
        got = [c.strip().lower() for c in next(csv.reader([first]))]
        if got != COLUMNS:
            errors.append(f"line {n}: column header must be '{','.join(COLUMNS)}', got '{first.strip()}'")
        body = body[1:]

    rows: list[dict] = []
    seen: dict[tuple[str, str], int] = {}
    for n, line in body:
        cells = [c.strip() for c in next(csv.reader(io.StringIO(line)))]
        if len(cells) != len(COLUMNS):
            errors.append(f"line {n}: {len(cells)} columns, expected {len(COLUMNS)}")
            continue
        team, player, pos, injury, d1, d2, d3, game = cells
        team, pos = team.upper(), pos.upper()
        line_errors = []
        if team not in teams:
            line_errors.append(f"unknown team '{team}'")
        if not player:
            line_errors.append("empty player")
        if pos not in positions:
            line_errors.append(f"unknown position '{pos}'")
        days = []
        for label, value in (("d1", d1), ("d2", d2), ("d3", d3)):
            key = value.lower() or "-"
            if key not in PRACTICE:
                line_errors.append(f"{label} '{value}' is not DNP / LP / FP / -")
            days.append(PRACTICE.get(key))
        if game.lower() not in STATUS:
            hint = " (Probable is not accepted)" if game.lower() == "probable" else ""
            line_errors.append(f"game status '{game}' is not Out / Doubtful / Questionable / IR / blank{hint}")
        key = player_key(team, player)
        if player and key in seen:
            line_errors.append(f"{team} {player} is already listed on line {seen[key]}")
        if line_errors:
            errors.extend(f"line {n}: {e}" for e in line_errors)
            continue
        seen[key] = n
        practice = next((d for d in reversed(days) if d is not None), None)
        rows.append({
            "line": n, "team": team, "player": player, "position": pos,
            "injury": injury, "days": days, "status": STATUS[game.lower()],
            "practice": practice,
        })

    if errors:
        raise ManualFileError(f"{name}: {len(errors)} error(s); nothing was used\n  "
                              + "\n  ".join(errors))
    return rows


def load(season: int, week: int, teams: set[str], positions: set[str],
         path: Path | None = None) -> list[dict] | None:
    """The week's rows, None when there is no file. Raises on an invalid file."""
    path = path or path_for(season, week)
    if not path.exists():
        return None
    return parse(path.read_text(encoding="utf-8-sig"), season, week, teams, positions,
                 name=path.name)


def merge(rows: list[dict], manual: list[dict], shares: dict, season: int,
          week: int) -> tuple[list[dict], list[dict]]:
    """Feed rows with the manual rows applied, and one record per manual row.

    A manual row replaces every feed row for the same player_key, so no player
    appears twice. Healthy manual rows are kept as play probability 1.0 rows;
    `features.latest_injury_report` uses them to clear the player and then
    drops them, so they never take a starter slot. An unmatched IR player with
    no snaps for his team is not added (P20: nothing to deduct him from) and is
    reported as such.
    """
    from .ingest_injuries import play_probability, player_key

    by_key: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        by_key.setdefault(player_key(r["team"], r["player"]), []).append(r)

    replaced: set[int] = set()
    added: list[dict] = []
    report: list[dict] = []
    for m in manual:
        key = player_key(m["team"], m["player"])
        matched = by_key.get(key, [])
        share = shares.get(key)
        if share is None:
            share = next((r.get("snap_share") for r in matched if r.get("snap_share") is not None), None)
        prob = play_probability(m["status"], m["practice"])
        old = min((r.get("play_probability", 1.0) for r in matched), default=None)
        healthy = is_healthy(m["status"], m["practice"])
        if not matched and m["status"] == "ir" and share is None:
            report.append({**m, "action": "not added (IR, no snaps for this team; P20)",
                           "old": None, "new": None})
            continue
        replaced.update(id(r) for r in matched)
        base = matched[0] if matched else {}
        added.append({
            "player": base.get("player") or m["player"],
            "team": m["team"],
            "sport": "nfl",
            "season": season,
            "week": week,
            "position": base.get("position") or m["position"],
            "status": m["status"],
            "practice_trend": m["practice"],
            "snap_share": share,
            "play_probability": 1.0 if healthy else prob,
            "source": SOURCE,
        })
        if matched:
            action = "cleared" if healthy else "override"
        else:
            action = "listed healthy (no feed row)" if healthy else "added"
        report.append({**m, "action": action, "old": old, "new": 1.0 if healthy else prob})

    kept = [r for r in rows if id(r) not in replaced]
    return kept + added, report


def print_report(report: list[dict], path_name: str) -> None:
    counts: dict[str, int] = {}
    for r in report:
        counts[r["action"]] = counts.get(r["action"], 0) + 1
    print(f"  manual ({path_name}): {len(report)} rows read | "
          + ", ".join(f"{v} {k}" for k, v in counts.items()))
    for r in report:
        old = "-" if r["old"] is None else f"{r['old']:.2f}"
        new = "-" if r["new"] is None else f"{r['new']:.2f}"
        flag = "" if r["old"] != r["new"] else "  (unchanged)"
        print(f"    {r['team']:<3} {r['player']:<26} {old} -> {new}  {r['action']}{flag}")
