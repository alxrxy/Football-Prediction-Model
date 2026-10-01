"""P62 Phase 1: shadow pull of Sportradar player props beside each Odds API pull.

    python -m src.shadow_props_sr --report     # per pull: games saved / failed, books, players

Shadow only. After `ingest_props` has written data/props_lines.json, the games
it fetched live that run are pulled from Sportradar (Odds Comparison Player
Props, one call per game), converted to the same schema and written to
data/props_lines_sr.json. Nothing in the model, sims, ranking or served
dashboard reads it; the P62 criteria (S1-S8, calibration-log.md) are measured
from the saved pull pairs.

Isolation (S6a, S8a): `shadow` never raises and never touches props_lines.json.
It runs only after that file is written, so whatever happens here, the served
outputs are what they would have been with the shadow off. Every failure is
written to the manifest and printed as one line.

KEY1 only (S7b): calls go through a KeyManager restricted to
SPORTRADAR_API_KEY1, so it cannot rotate; at the quota margin it stops and logs
(P65 covers the rotating manager P61 uses).

Saved per pull, under data/props_sr/pulls/<stamp>/: the paired Odds API file
(odds.json, a copy as it was written), the converted file (sr.json) and the raw
Sportradar responses. props_lines.json is overwritten by every pull, so without
the copy no criterion could be re-run over earlier pulls (S2/S4/S5 require it).

Conversion to the props_lines.json schema (P62 scoping, a-g):
- event -> game_id by team abbreviations (all 32 match ours) and kickoff;
- "Last, First" -> "First Last" (Sportradar drops suffixes; matching downstream
  strips them anyway);
- the four priced markets by Sportradar's market name;
- books by BOOK_MAP; `consensus` (not a book) and any unmapped book are excluded
  and counted, never silently merged;
- lines flagged `removed`, and `is_live` markets, are dropped and counted;
- a book with more than one over/under total for one player-market is dropped
  and counted as ambiguous rather than guessed at.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from . import config

OUT_DIR = config.DATA_DIR / "props_sr"
SR_LINES_JSON = config.DATA_DIR / "props_lines_sr.json"
BASE_PATH = "/oddscomparison-player-props/trial/v2/en"
SCHEDULE_PATH = f"{BASE_PATH}/competitions/sr:competition:31/schedules.json"
SCHEDULE_MAX_AGE_HOURS = 12.0
KICKOFF_TOLERANCE = timedelta(hours=3)
SHADOW_KEY = "SPORTRADAR_API_KEY1"

MARKET_MAP = {
    "total passing yards (incl. overtime)": "player_pass_yds",
    "total rushing yards (incl. overtime)": "player_rush_yds",
    "total receiving yards (incl. overtime)": "player_reception_yds",
    "total receptions (incl. overtime)": "player_receptions",
}
# Sportradar book name -> the Odds API's bookmaker key. Checked against real
# pulls from both sources before the window (S3); a book missing here is
# excluded and listed, never folded into another.
BOOK_MAP = {
    "DraftKings": "draftkings",
    "FanDuel": "fanduel",
    "MGM": "betmgm",
    "BetRivers": "betrivers",
    "WilliamHillNewJersey": "williamhill_us",
}
NOT_A_BOOK = {"consensus"}

MANIFEST_FIELDS = ["run_utc", "odds_pulled_at", "minutes_after_odds", "game_id", "sr_event_id", "result",
                   "players", "book_lines", "removed", "live_dropped", "consensus_dropped",
                   "unmapped_books", "ambiguous", "file"]


def enabled() -> bool:
    return os.getenv("P62_SHADOW", "1").strip().lower() not in ("0", "false", "off", "no")


def _parse(ts: str) -> datetime:
    dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def first_last(name: str) -> str:
    """'Pittman, Michael' -> 'Michael Pittman'; a name without a comma is kept."""
    last, sep, first = str(name or "").partition(", ")
    return f"{first.strip()} {last.strip()}".strip() if sep else str(name or "").strip()


def _american(value) -> int | None:
    try:
        return int(str(value).replace("+", ""))
    except (TypeError, ValueError):
        return None


class NameResolver:
    """Sportradar names -> the nflverse roster names the pipeline matches on (P62 S2).

    Sportradar uses legal first names ("Cameron Ward", "Jo'Quavious Marks")
    where nflverse, the sim, P49 / P53 / P51 and the books use the football name
    ("Cam Ward", "Woody Marks"). A name is changed only on a strict match within
    the player's own team: the same last name, and the Sportradar first name
    equal to that roster player's legal first name, football name or display
    first name, with exactly one such player. Anything else keeps its
    Sportradar name and is counted, so a wrong merge needs a roster player on
    the same team with the same last name and a matching first name.
    """

    def __init__(self, rows: list[dict]):
        from .props import pnorm

        self._pnorm = pnorm
        self.by_last: dict[tuple[str, str], list[dict]] = {}
        for r in rows:
            if r.get("team") and r.get("last_name") and r.get("player_name"):
                last = str(r["last_name"])
                # A hyphenated surname is also indexed under each part: Sportradar
                # writes Jacory Croskey-Merritt as "Merritt, Jacory".
                keys = {pnorm(last)} | ({pnorm(x) for x in last.split("-") if x.strip()} if "-" in last else set())
                for k in keys:
                    self.by_last.setdefault((r["team"], k), []).append(r)

    @classmethod
    def from_nflverse(cls, season: int) -> "NameResolver":
        import nfl_data_py as nfl

        df = nfl.import_weekly_rosters([season])
        latest = df[df["week"] == df["week"].max()]
        rest = df[~df["player_id"].isin(set(latest["player_id"]))]   # traded / dropped since: still resolvable
        rows = (latest.to_dict("records") + rest.drop_duplicates("player_id", keep="last").to_dict("records"))
        return cls(rows)

    def resolve(self, team: str | None, sr_name: str) -> tuple[str, str]:
        """(name to use, how): how is exact, alias, unresolved or ambiguous."""
        p = self._pnorm
        last, sep, first = str(sr_name or "").partition(", ")
        fallback = first_last(sr_name)
        if not sep or not team:
            return fallback, "unresolved"
        cands = self.by_last.get((team, p(last)), [])
        exact = [r for r in cands if p(r["player_name"]) == p(fallback)]
        if len(exact) == 1:
            return exact[0]["player_name"], "exact"
        hits = []
        for r in cands:
            firsts = {p(r.get("first_name") or ""), p(r.get("football_name") or ""),
                      p(str(r["player_name"]).split(" ")[0])}
            if p(first) in firsts:
                hits.append(r)
        ids = {r.get("player_id") for r in hits}
        if len(ids) == 1:
            return hits[0]["player_name"], "alias"
        return fallback, "ambiguous" if len(ids) > 1 else "unresolved"


def convert(payload: dict, resolver: NameResolver | None = None) -> tuple[dict, dict]:
    """(players, counts): players = name -> market -> book -> {point, over, under},
    the props_lines.json shape, from one Sportradar players_props response.
    With a resolver, names are mapped to nflverse roster names (counts["names"])."""
    ev = payload.get("sport_event_players_props") or {}
    counts = {"book_lines": 0, "removed": 0, "live_dropped": 0, "consensus_dropped": 0,
              "unmapped_books": set(), "ambiguous": 0, "names": []}
    teams = {c.get("id"): c.get("abbreviation") for c in (ev.get("sport_event") or {}).get("competitors") or []}
    players: dict = {}
    for pp in ev.get("players_props") or []:
        raw = (pp.get("player") or {}).get("name")
        if resolver is None:
            name = first_last(raw)
        else:
            team = teams.get((pp.get("player") or {}).get("competitor_id"))
            name, how = resolver.resolve(team, raw)
            counts["names"].append({"sr": raw, "name": name, "how": how, "team": team})
        for m in pp.get("markets") or []:
            key = MARKET_MAP.get(str(m.get("name") or "").strip().lower())
            if key is None:
                continue
            for b in m.get("books") or []:
                counts["book_lines"] += 1
                if m.get("is_live"):
                    counts["live_dropped"] += 1
                    continue
                book_name = b.get("name") or ""
                if book_name in NOT_A_BOOK:
                    counts["consensus_dropped"] += 1
                    continue
                book = BOOK_MAP.get(book_name)
                if book is None:
                    counts["unmapped_books"].add(book_name)
                    continue
                if b.get("removed"):
                    counts["removed"] += 1
                    continue
                live = [o for o in b.get("outcomes") or [] if not o.get("removed")]
                totals = {o.get("total") for o in live if o.get("type") in ("over", "under")}
                if len(totals) != 1:
                    if len(totals) > 1:
                        counts["ambiguous"] += 1
                    else:
                        counts["removed"] += 1
                    continue
                slot: dict = {"point": float(next(iter(totals)))}
                for o in live:
                    if o.get("type") in ("over", "under"):
                        slot[o["type"]] = _american(o.get("odds_american"))
                players.setdefault(name, {}).setdefault(key, {})[book] = slot
    counts["unmapped_books"] = sorted(counts["unmapped_books"])
    return players, counts


def map_events(events: list[dict], games: dict) -> tuple[dict, list[str]]:
    """{game_id: sr event id} by (away, home) and kickoff within KICKOFF_TOLERANCE,
    and the problems found. 1:1 or reported (S2a)."""
    out, problems = {}, []
    for gid, g in games.items():
        hits = [e for e in events
                if e["away"] == g.get("away") and e["home"] == g.get("home")
                and g.get("kickoff") and abs(_parse(e["start_time"]) - _parse(g["kickoff"])) <= KICKOFF_TOLERANCE]
        if len(hits) == 1:
            out[gid] = hits[0]["id"]
        else:
            problems.append(f"{gid}: {len(hits)} Sportradar events match")
    used = list(out.values())
    for eid in {e for e in used if used.count(e) > 1}:
        problems.append(f"event {eid} maps to more than one game")
    return out, problems


def load_schedule(out: Path, get: Callable[[str], dict], now: datetime) -> list[dict]:
    path = out / "schedule.json"
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
        if now - _parse(cached["fetched_at"]) < timedelta(hours=SCHEDULE_MAX_AGE_HOURS):
            return cached["events"]
    except (OSError, ValueError, KeyError):
        pass
    data = get(SCHEDULE_PATH)
    events = []
    for s in (data or {}).get("schedules") or []:
        se = s["sport_event"]
        teams = {c["qualifier"]: c["abbreviation"] for c in se.get("competitors") or []}
        events.append({"id": se["id"], "start_time": se["start_time"],
                       "away": teams.get("away"), "home": teams.get("home")})
    out.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"fetched_at": now.isoformat(), "events": events}, indent=1), encoding="utf-8")
    return events


def _log(out: Path, rows: list[dict]) -> None:
    path = out / "manifest.csv"
    new = not path.exists()
    out.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        if new:
            w.writeheader()
        for row in rows:
            w.writerow({k: (";".join(row[k]) if isinstance(row.get(k), list) else row.get(k, ""))
                        for k in MANIFEST_FIELDS})


def pull(odds: dict, live_games: set[str], get: Callable[[str], dict], now: datetime,
         out: Path = OUT_DIR, lines_path: Path = SR_LINES_JSON,
         odds_path: Path | None = None) -> list[dict]:
    """One shadow pull for `live_games`. Returns the manifest rows written.
    Raises only on errors in its own bookkeeping; `shadow` catches those too."""
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    pull_dir = out / "pulls" / stamp
    odds_at = odds.get("refreshed_at") or odds.get("pulled_at")
    minutes = round((now - _parse(odds_at)).total_seconds() / 60, 1) if odds_at else ""
    base = {"run_utc": now.isoformat(timespec="seconds"), "odds_pulled_at": odds_at, "minutes_after_odds": minutes}
    games = {g: v for g, v in (odds.get("games") or {}).items() if g in live_games}
    rows: list[dict] = []
    try:
        events = load_schedule(out, get, now)
    except Exception as exc:  # noqa: BLE001 - logged per game, never raised
        rows = [{**base, "game_id": g, "result": f"error (schedule): {type(exc).__name__}: {str(exc)[:120]}"}
                for g in games]
        _log(out, rows)
        return rows
    mapping, problems = map_events(events, games)
    resolver, names = _resolver(odds.get("season")), []
    prev = {}
    if lines_path.exists():
        try:
            prev = json.loads(lines_path.read_text(encoding="utf-8"))
        except ValueError:
            prev = {}
    sr = {"source": "sportradar", "pulled_at": now.isoformat(), "paired_odds_pulled_at": odds_at,
          "season": odds.get("season"), "week": odds.get("week"), "markets": odds.get("markets"),
          "games": {g: v for g, v in (prev.get("games") or {}).items()
                    if g in (odds.get("games") or {}) and g not in games}}
    for gid, g in games.items():
        row = {**base, "game_id": gid}
        eid = mapping.get(gid)
        if eid is None:
            rows.append({**row, "result": "unmapped: " + "; ".join(p for p in problems if p.startswith(gid))})
            continue
        row["sr_event_id"] = eid
        try:
            data = get(f"{BASE_PATH}/sport_events/{eid}/players_props.json")
            if not isinstance(data, dict) or "sport_event_players_props" not in data:
                raise ValueError("response has no sport_event_players_props")
        except Exception as exc:  # noqa: BLE001 - logged, never raised
            rows.append({**row, "result": f"error: {type(exc).__name__}: {str(exc)[:120]}"})
            continue
        pull_dir.mkdir(parents=True, exist_ok=True)
        raw = pull_dir / f"raw_{gid}.json"
        raw.write_text(json.dumps(data), encoding="utf-8")
        players, counts = convert(data, resolver)
        names += [{**n, "game_id": gid} for n in counts.pop("names")]
        books = {b for p in players.values() for m in p.values() for b in m}
        sr["games"][gid] = {"home": g.get("home"), "away": g.get("away"), "kickoff": g.get("kickoff"),
                            "event_id": g.get("event_id"), "sr_event_id": eid, "books": len(books),
                            "players": players, "pulled_at": now.isoformat()}
        rows.append({**row, **counts, "result": "saved" if players else "saved (no lines)",
                     "players": len(players), "file": str(raw.relative_to(out))})
    for p in problems:
        if not any(r.get("result", "").endswith(p) for r in rows):
            rows.append({**base, "game_id": "", "result": f"mapping: {p}"})
    if any(r.get("result", "").startswith("saved") for r in rows):
        pull_dir.mkdir(parents=True, exist_ok=True)
        text = json.dumps(sr)
        lines_path.write_text(text, encoding="utf-8")
        (pull_dir / "sr.json").write_text(text, encoding="utf-8")
        if odds_path is not None and odds_path.exists():
            shutil.copyfile(odds_path, pull_dir / "odds.json")
        _save_holdouts(pull_dir, set(odds.get("games") or {}))
        (pull_dir / "names.json").write_text(json.dumps(
            {"resolver": "nflverse" if resolver else "none (roster unavailable)", "names": names}), encoding="utf-8")
    _log(out, rows)
    return rows


_RESOLVERS: dict = {}


def _resolver(season) -> NameResolver | None:
    """The nflverse roster resolver, once per process; None if the roster can't
    be read (names then stay as Sportradar writes them, and names.json says so)."""
    if season is None:
        return None
    if season not in _RESOLVERS:
        try:
            _RESOLVERS[season] = NameResolver.from_nflverse(int(season))
        except Exception as exc:  # noqa: BLE001 - the shadow never raises
            print(f"  [warn] P62 shadow: nflverse roster unavailable, names unresolved ({exc})")
            _RESOLVERS[season] = None
    return _RESOLVERS[season]


def reconvert_pull(pull_dir: Path, resolver: NameResolver | None) -> dict:
    """Rebuild a saved pull's sr.json from its raw responses with the current
    converter (S2: a converter fix must pass re-run over every saved pull). The
    first version is kept as sr_v1.json. Returns {game_id: name records}."""
    sr_path = pull_dir / "sr.json"
    sr = json.loads(sr_path.read_text(encoding="utf-8"))
    if not (pull_dir / "sr_v1.json").exists():
        shutil.copyfile(sr_path, pull_dir / "sr_v1.json")
    out = {}
    for gid, g in (sr.get("games") or {}).items():
        raw = pull_dir / f"raw_{gid}.json"
        if g.get("pulled_at") != sr.get("pulled_at") or not raw.exists():
            continue
        players, counts = convert(json.loads(raw.read_text(encoding="utf-8")), resolver)
        g["players"] = players
        g["books"] = len({b for p in players.values() for m in p.values() for b in m})
        out[gid] = counts["names"]
    sr["converter"] = "v2: nflverse roster names"
    sr_path.write_text(json.dumps(sr), encoding="utf-8")
    (pull_dir / "names.json").write_text(json.dumps(
        {"resolver": "nflverse" if resolver else "none", "names": [{**n, "game_id": g} for g, ns in out.items() for n in ns]}),
        encoding="utf-8")
    return out


def _save_holdouts(pull_dir: Path, games: set[str]) -> None:
    """The PROP_HOLDOUTS / KNOWN_DEFECTS entries live at this pull, for S2(d).
    They are code and change between a pull and its comparison, so they are
    kept with the pull. A failure here leaves S2(d) unmeasured for the pull."""
    try:
        from . import props

        snap = {"prop_holdouts": [list(k) for k in props.PROP_HOLDOUTS if k[0] in games],
                "known_defects": [list(k) for k in props.KNOWN_DEFECTS if k[0] in games]}
        (pull_dir / "holdouts.json").write_text(json.dumps(snap), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] P62 shadow: hold tables not saved for this pull ({exc})")


def save_rank_snapshot(lines_bytes: bytes, sims: dict, served: dict, now: datetime | None = None,
                       out: Path = OUT_DIR) -> Path | None:
    """Called by props.run after the served props.json is written. Keeps the
    sims that ranking used, and the served list, beside the shadow pull whose
    odds.json is byte-identical to the lines just ranked (S4 ranks both files
    against the same sims, and game_simulations keeps only one row per game,
    so they cannot be rebuilt later). Returns the folder, or None when no
    pull matches (a ranking of lines the shadow never paired)."""
    pulls = sorted((out / "pulls").glob("*/odds.json"), reverse=True) if (out / "pulls").exists() else []
    match = next((p.parent for p in pulls if p.read_bytes() == lines_bytes), None)
    if match is None:
        return None
    games = set((json.loads(lines_bytes) or {}).get("games") or {})
    now = now or datetime.now(timezone.utc)
    folder = match / f"rank_{now:%Y%m%dT%H%M%SZ}"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "sims.json").write_text(json.dumps({g: v for g, v in sims.items() if g in games}, default=str),
                                      encoding="utf-8")
    (folder / "props.json").write_text(json.dumps(served, default=str), encoding="utf-8")
    return folder


def shadow(odds: dict, live_games: set[str], *, get: Callable[[str], dict] | None = None,
           now: datetime | None = None, out: Path = OUT_DIR, lines_path: Path = SR_LINES_JSON,
           odds_path: Path | None = None) -> list[dict]:
    """Entry point from ingest_props, after props_lines.json is written. Never raises."""
    if not enabled():
        print("  [P62 shadow] off (P62_SHADOW=0)")
        return []
    if not live_games:
        print("  [P62 shadow] no game fetched live this run; nothing to pair")
        return []
    now = now or datetime.now(timezone.utc)
    try:
        if get is None:
            from .sportradar import KeyManager

            km = KeyManager(names=[SHADOW_KEY], job="p62_shadow")   # KEY1 only: cannot rotate (S7b)
            get = km.get
        rows = pull(odds, live_games, get, now, out, lines_path, odds_path)
    except Exception as exc:  # noqa: BLE001 - the shadow must never break the props pull
        msg = f"{type(exc).__name__}: {str(exc)[:160]}"
        try:
            _log(out, [{"run_utc": now.isoformat(timespec="seconds"), "game_id": "", "result": f"error: {msg}"}])
        except Exception:  # noqa: BLE001
            pass
        print(f"  [warn] P62 shadow failed, nothing served changed: {msg}")
        return []
    saved = [r for r in rows if str(r.get("result", "")).startswith("saved")]
    failed = [r for r in rows if r not in saved]
    print(f"  [P62 shadow] {len(saved)}/{len(live_games)} game(s) saved from Sportradar (KEY1)"
          + (f", {len(failed)} not: " + "; ".join(f"{r.get('game_id') or '-'} {r['result']}" for r in failed[:4])
             if failed else ""))
    return rows


def report(out: Path = OUT_DIR) -> str:
    path = out / "manifest.csv"
    if not path.exists():
        return "no shadow pulls yet"
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return "\n".join(f"{r['run_utc']} {r['game_id']:16s} {r['result'][:60]:60s} players={r['players']:>3s} "
                     f"lines={r['book_lines']:>4s} removed={r['removed']:>3s} +{r['minutes_after_odds']}min"
                     for r in rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    print(report())
