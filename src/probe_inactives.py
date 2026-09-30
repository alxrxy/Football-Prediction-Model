"""Read-only probe of ESPN's gameday inactive lists (P33 refinement).

    python -m src.probe_inactives                 # one probe pass; exits at once if no game is in the window
    python -m src.probe_inactives --now 2026-09-28T23:30Z --out <dir>   # dry run at a chosen moment

P33's refinement has to choose between tightening `ingest_inactives.LOOKAHEAD_HOURS`
toward ~1.5 h and adding ruled-out coverage as a storage condition. The live store
cannot answer that: it keeps only accepted lists, each player's first-seen time,
and this week's injury report as last overwritten. This probe records, for every
team in a game from T-3 h to kickoff, the full list ESPN returns at that read and
how many of the team's ruled-out players (out / doubtful / IR on the report as it
stands at that moment) are on it.

Isolated from everything live, by construction:
- The store is wrapped read-only: any write raises (`ReadOnlyStore`).
- ESPN is read with `ingest_inactives._get` (plain `requests`, no cache). Athlete
  names go through a private cache in the probe's own folder, never the shared
  HTTP cache the live pipeline reads.
- It writes only under `data/inactives_probe/`, which nothing else reads.
- It shares no module state with `ingest_inactives`; `LOOKAHEAD_HOURS` is not read or
  changed.
The one shared resource is ESPN itself: the probe adds requests to the same host.

Run every 15 minutes by Windows Task Scheduler (`probe_inactives.cmd`); a pass
with no game in the window costs one read of a local schedule file.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config, db
from .features import latest_injury_report, parse_dt
from .ingest_inactives import CORE, _get, impossible_list
from .ingest_injuries import _resolve_team, player_key

WINDOW_HOURS = 3.0
SCHEDULE_MAX_AGE_HOURS = 6.0
RULED_OUT = ("out", "doubtful", "ir")
OUT_DIR = config.DATA_DIR / "inactives_probe"


class ReadOnlyStore:
    """A store that can only be read. Any other call raises, so the probe
    cannot write to the live database even by mistake."""

    def __init__(self, inner):
        self._inner = inner

    def select(self, table, where=None):
        return self._inner.select(table, where)

    def close(self):
        close = getattr(self._inner, "close", None)
        if close:
            close()

    def __getattr__(self, name):
        raise PermissionError(f"probe_inactives is read-only: store.{name} is not allowed")


def _schedule(store_factory, out_dir: Path, now: datetime) -> dict:
    """NFL games and team names, cached locally so an idle pass touches no database."""
    path = out_dir / "schedule.json"
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
        if now - parse_dt(cached["built_at"]) < timedelta(hours=SCHEDULE_MAX_AGE_HOURS):
            return cached
    except (OSError, ValueError, KeyError, TypeError):
        pass
    store = store_factory()
    try:
        games = [{k: g.get(k) for k in ("game_id", "season", "week", "home_team", "away_team", "kickoff_time")}
                 for g in store.select("games", {"sport": "nfl"})]
        teams = {(t.get("full_name") or t["team"]): t["team"] for t in store.select("teams", {"sport": "nfl"})}
    finally:
        store.close()
    sched = {"built_at": now.isoformat(), "games": games, "teams": teams}
    out_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sched), encoding="utf-8")
    return sched


def in_window(games: list[dict], now: datetime) -> list[dict]:
    """Games kicking off within the next WINDOW_HOURS (T-3 h up to kickoff)."""
    out = []
    for g in games:
        k = parse_dt(g.get("kickoff_time"))
        if k and now <= k <= now + timedelta(hours=WINDOW_HOURS):
            out.append(g)
    return out


class _Names:
    """ESPN athlete id -> (name, position), cached in the probe's own folder."""

    def __init__(self, path: Path, get):
        self.path, self.get = path, get
        try:
            self.data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.data = {}

    def lookup(self, entry: dict) -> tuple[str | None, str | None]:
        pid = str(entry.get("playerId") or "")
        if pid and pid in self.data:
            return tuple(self.data[pid])
        name, pos = entry.get("displayName"), None
        ref = (entry.get("athlete") or {}).get("$ref")
        if ref:
            code, a = self.get(ref)
            if a:
                name = a.get("displayName") or a.get("fullName") or name
                pos = (a.get("position") or {}).get("abbreviation")
        if pid and name:
            self.data[pid] = [name, pos]
        return name, pos

    def save(self):
        self.path.write_text(json.dumps(self.data), encoding="utf-8")


def _ruled_out(report: list[dict], team: str) -> dict[tuple[str, str], dict]:
    """The team's ruled-out players on the report as it stands now, one per player."""
    out = {}
    for r in report:
        if r.get("team") != team:
            continue
        status = (r.get("status") or "").lower()
        if status in RULED_OUT:
            out.setdefault(player_key(team, r.get("player")), {"player": r.get("player"), "status": status,
                                                              "source": r.get("source")})
    return out


def probe(store_factory, now: datetime, out_dir: Path = OUT_DIR, get=_get) -> list[dict]:
    """One pass: a record per team read, appended to out_dir/<UTC date>/reads.jsonl."""
    sched = _schedule(store_factory, out_dir, now)
    window = in_window(sched["games"], now)
    if not window:
        return []

    store = store_factory()
    try:
        report = latest_injury_report(store.select("injuries", {"sport": "nfl"}))
    finally:
        store.close()

    names = _Names(out_dir / "athletes.json", get)
    records = []
    for season, week in sorted({(g["season"], g["week"]) for g in window}):
        wanted = {(g["home_team"], g["away_team"]): g for g in window if (g["season"], g["week"]) == (season, week)}
        code, sb = get(f"{config.ESPN_NFL}/scoreboard", params={"week": week, "seasontype": 2, "dates": season})
        if not sb:
            records.append({"read_at": now.isoformat(), "season": season, "week": week,
                            "result": f"scoreboard unavailable (HTTP {code})"})
            continue
        for event in sb.get("events") or []:
            comp = (event.get("competitions") or [{}])[0]
            sides = {c.get("homeAway"): (c["team"]["id"], _resolve_team(c["team"].get("displayName") or "", sched["teams"]))
                     for c in comp.get("competitors") or []}
            home, away = sides.get("home", (None, None)), sides.get("away", (None, None))
            game = wanted.get((home[1], away[1]))
            if game is None:
                continue
            kickoff = parse_dt(game["kickoff_time"])
            for team_id, team in (home, away):
                code, data = get(f"{CORE}/events/{event['id']}/competitions/{event['id']}/competitors/{team_id}/roster")
                entries = (data or {}).get("entries") or []
                flagged = []
                for x in entries:
                    if x.get("didNotPlay"):
                        name, pos = names.lookup(x)
                        flagged.append({"espn_id": str(x.get("playerId") or ""), "player": name, "position": pos})
                listed = {player_key(team, f["player"]) for f in flagged if f["player"]}
                ruled = _ruled_out(report, team)
                ruled_rows = [{**v, "on_list": k in listed} for k, v in ruled.items()]
                non_ir = [r for r in ruled_rows if r["status"] != "ir"]
                records.append({
                    "read_at": now.isoformat(), "game_id": game["game_id"], "team": team,
                    "kickoff": kickoff.isoformat() if kickoff else None,
                    "lead_hours": round((kickoff - now).total_seconds() / 3600, 3) if kickoff else None,
                    "http": code, "roster_entries": len(entries), "list_size": len(flagged),
                    "impossible": impossible_list(entries) if flagged else None,
                    "flagged": flagged, "ruled_out": ruled_rows,
                    "coverage": {"ruled": len(ruled_rows), "listed": sum(r["on_list"] for r in ruled_rows),
                                 "ruled_excl_ir": len(non_ir), "listed_excl_ir": sum(r["on_list"] for r in non_ir)},
                })
    names.save()

    day_dir = out_dir / now.strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    with (day_dir / "reads.jsonl").open("a", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only P33 probe of ESPN inactive lists.")
    parser.add_argument("--now", help="pretend it is this UTC time (dry runs)")
    parser.add_argument("--out", help="output folder (default data/inactives_probe)")
    args = parser.parse_args()
    now = parse_dt(args.now) if args.now else datetime.now(timezone.utc)
    out_dir = Path(args.out) if args.out else OUT_DIR
    try:
        records = probe(lambda: ReadOnlyStore(db.get_store()), now, out_dir)
    except Exception as exc:  # noqa: BLE001 - logged to the probe's own file; nothing live depends on it
        out_dir.mkdir(parents=True, exist_ok=True)
        with (out_dir / "errors.log").open("a", encoding="utf-8") as fh:
            fh.write(f"{now.isoformat()} {type(exc).__name__}: {exc}\n")
        print(f"[probe] {now.isoformat()} error: {exc}")
        return 1
    teams = [r for r in records if "team" in r]
    if records:
        print(f"[probe] {now.isoformat()}: {len(teams)} team reads, "
              f"{sum(r['list_size'] > 0 for r in teams)} with a list")
    return 0


if __name__ == "__main__":
    sys.exit(main())
