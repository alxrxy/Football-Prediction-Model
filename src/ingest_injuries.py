"""Injury and depth ingestion (architecture §6).

    python -m src.ingest_injuries --sport nfl
    python -m src.ingest_injuries --sport ncaaf

Sources differ sharply by sport, and so does the trust you can place in them:

NFL — nflverse's weekly report is the real thing: every team, every listed
player, with both a report status (Out/Doubtful/Questionable) and a practice
participation level (DNP/Limited/Full). That practice trend is what §4 asks for
to estimate play probability. ESPN supplements it with same-day status changes.

NCAAF — there is no mandated injury report. ESPN's league-wide feed is
editorially curated and typically lists only a handful of teams, so college
injury coverage is inherently partial. Games with no data are unaffected rather
than wrongly assumed healthy, and the run prints the coverage so the gap is
visible instead of silent.

Starter identification is the part that decides whether this layer helps or
hurts. An injury feed lists third-string players alongside starters, and
applying a starting-QB penalty to a third-string QB would be far worse than
having no injury layer at all. For the NFL each player is therefore weighted by
his actual snap share; ESPN depth charts were evaluated for this and rejected,
since the endpoint needs one request per position per team behind $ref links.
"""

from __future__ import annotations

import argparse
import re
import unicodedata
import warnings

from . import config, db
from .http import safe_get_json
from .names import similarity

warnings.filterwarnings("ignore")

ESPN_BY_SPORT = {"nfl": config.ESPN_NFL, "ncaaf": config.ESPN_CFB}

# ESPN's edge is fussy in ways that make no obvious sense: a bare "Mozilla/5.0"
# is accepted, while both the project's own UA and a full modern Chrome string
# are rejected with 403. This exact value is load-bearing; it is also precisely
# the fragility no-key-data-sources.md warns about for this endpoint, which is
# why every ESPN failure here degrades instead of stopping the pipeline.
BROWSER_UA = "Mozilla/5.0"

# Play probability given report status and practice participation (§4).
# A Questionable player who practised fully is far likelier to play than a
# Questionable player who sat out all week; that spread is the whole point.
PRACTICE_LEVELS = {
    "did not participate in practice": "dnp",
    "limited participation in practice": "limited",
    "full participation in practice": "full",
}
PLAY_PROBABILITY = {
    ("out", None):          0.00,
    ("doubtful", None):     0.10,
    ("questionable", "dnp"):     0.25,
    ("questionable", "limited"): 0.55,
    ("questionable", "full"):    0.80,
    ("questionable", None):      0.55,
    (None, "dnp"):     0.60,   # on the report but unlabelled: mild concern
    (None, "limited"): 0.85,
    (None, "full"):    1.00,
}

# College players with no snap data. ESPN only bothers listing notable names,
# so treating them as rotation regulars is defensible — but it is a guess, and
# it is deliberately below 1.0 to keep the resulting adjustment modest.
DEFAULT_SNAP_SHARE = 0.65


# Word boundaries matter here: without them this strips the "v" out of
# "Vick" and the "ii" out of "Willis".
_SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b\.?", re.IGNORECASE)


def player_key(team, name) -> tuple[str, str]:
    """Join key for a player across feeds.

    Snap counts come from Pro-Football-Reference and drop generational
    suffixes ("Michael Penix"), while both injury feeds keep them ("Michael
    Penix Jr."). Left unnormalized, exactly the star players most likely to
    carry a suffix are the ones that silently miss their snap share and get
    treated as unknown reserves.
    """
    text = unicodedata.normalize("NFKD", str(name or ""))
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = _SUFFIX.sub(" ", text)
    text = re.sub(r"[^a-z ]+", "", text)
    return (str(team or "").upper(), re.sub(r"\s+", " ", text).strip())


def _status(value) -> str | None:
    value = (str(value) or "").strip().lower()
    if value in ("out", "doubtful", "questionable", "probable"):
        return value
    # "Injured Reserve" is kept as its own status rather than folded into
    # "out": an IR player is not on the game roster at all, which is why
    # features.GAME_STATUSES leaves him alone when a list is posted (P20).
    if value == "injured reserve":
        return "ir"
    return None


def _practice(value) -> str | None:
    return PRACTICE_LEVELS.get((str(value) or "").strip().lower())


def play_probability(status: str | None, practice: str | None) -> float:
    if status in ("out", "ir"):
        return 0.0
    key = (status, practice)
    if key in PLAY_PROBABILITY:
        return PLAY_PROBABILITY[key]
    if status:
        return PLAY_PROBABILITY.get((status, None), 0.5)
    return PLAY_PROBABILITY.get((None, practice), 1.0)


# --- NFL -------------------------------------------------------------------

def _snap_shares(season: int) -> dict[tuple[str, str], float]:
    """(team, player) -> snap share, from the most recent season with data.

    Current-season snaps win where a player has them; everyone else falls back
    to the prior season, player by player. The fallback has to be per player,
    not per dataset: in week 1 the current season only covers teams that have
    already played, and a player injured before it has no current snaps at
    all, which is exactly the player the injury layer needs to price.
    """
    import nfl_data_py as nfl

    frames = []
    for year in (season, season - 1):
        try:
            df = nfl.import_snap_counts([year])
        except Exception:  # noqa: BLE001
            continue
        if len(df):
            frames.append(df)
    return merge_snap_shares(frames)


def merge_snap_shares(frames) -> dict[tuple[str, str], float]:
    """Mean snap share per (team, player), taking each player from the first
    (most recent) frame that has him."""
    shares: dict[tuple[str, str], float] = {}
    for df in frames:
        df = df.copy()
        df["share"] = df[["offense_pct", "defense_pct"]].max(axis=1)
        grouped = df.groupby(["team", "player"])["share"].mean()
        for (team, player), share in grouped.items():
            shares.setdefault(player_key(team, player), float(share))
    return shares


def ingest_nfl(store: db.Store, season: int, week: int,
               shares: dict | None = None) -> list[dict]:
    import nfl_data_py as nfl

    injuries = nfl.import_injuries([season])
    current = injuries[injuries["week"] == week]
    if not len(current):
        # Before week 1's report drops, fall back to the latest week present.
        latest = injuries["week"].max()
        current = injuries[injuries["week"] == latest]
        print(f"  [note] no week {week} report yet; using week {latest}")

    shares = shares if shares is not None else _snap_shares(season)
    rows, depth_rows = [], []
    for _, r in current.iterrows():
        status = _status(r.get("report_status"))
        practice = _practice(r.get("practice_status"))
        if status is None and practice in (None, "full"):
            continue  # on the report but fully healthy — no adjustment
        player = str(r.get("full_name"))
        team = str(r.get("team"))
        rows.append(
            {
                "player": player,
                "team": team,
                "sport": "nfl",
                "season": season,
                "week": int(r.get("week")),
                "position": str(r.get("position") or "").upper() or None,
                "status": status,
                "practice_trend": practice,
                "snap_share": shares.get(player_key(team, player)),
                "play_probability": play_probability(status, practice),
                "source": "nflverse",
            }
        )

    # Populate depth_charts from snap share: the rank of a player within his
    # team and position is exactly the "depth_order" the schema wants.
    by_slot: dict[tuple[str, str], list[tuple[float, str]]] = {}
    snap_positions = _positions_for(season)
    for key, share in shares.items():
        position = snap_positions.get(key)
        if not position:
            continue
        by_slot.setdefault((key[0], position), []).append((share, key[1]))
    for (team, position), players in by_slot.items():
        for order, (_share, player) in enumerate(sorted(players, reverse=True), start=1):
            depth_rows.append(
                {
                    "team": team, "sport": "nfl", "position": position,
                    "depth_order": order, "player": player,
                }
            )

    store.upsert("depth_charts", db.stamp(depth_rows))
    print(f"  depth_charts: {len(depth_rows)} rows from snap share")
    return rows


def _positions_for(season: int) -> dict[tuple[str, str], str]:
    import nfl_data_py as nfl

    out: dict[tuple[str, str], str] = {}
    for year in (season, season - 1):
        try:
            df = nfl.import_snap_counts([year])
        except Exception:  # noqa: BLE001
            continue
        for _, r in df[["team", "player", "position"]].drop_duplicates().iterrows():
            out.setdefault(player_key(r["team"], r["player"]), str(r["position"]).upper())
    return out


# --- ESPN (both sports) ----------------------------------------------------

def ingest_espn(store: db.Store, sport: str, season: int, week: int,
                shares: dict | None = None) -> list[dict]:
    """One league-wide call. Unofficial, so failure is non-fatal by design."""
    base = ESPN_BY_SPORT[sport]
    payload = safe_get_json(
        f"{base}/injuries",
        # ESPN 403s anything issued through requests; see http._get_urllib.
        headers={"User-Agent": BROWSER_UA},
        transport="urllib",
        cache_minutes=30,
        cache_tag=f"espn_inj_{sport}",
    )
    if not payload or not isinstance(payload, dict):
        print("  [warn] ESPN injuries unavailable; skipping this source")
        return []

    known = {
        (t.get("full_name") or t["team"]): t["team"]
        for t in store.select("teams", {"sport": sport})
    }
    rows, unmatched = [], set()

    for team_block in payload.get("injuries") or []:
        espn_name = team_block.get("displayName") or ""
        team = _resolve_team(espn_name, known)
        if team is None:
            unmatched.add(espn_name)
            continue
        for item in team_block.get("injuries") or []:
            athlete = item.get("athlete") or {}
            position = ((athlete.get("position") or {}).get("abbreviation") or "").upper()
            status = _status(item.get("status"))
            if status is None:
                continue
            share = (shares or {}).get(player_key(team, athlete.get("displayName")))
            if status == "ir" and share is None:
                # No snaps for this team means he is not inside the rating the
                # charge is deducted from, so there is nothing to deduct. Without
                # this the 0.65 college fallback would price a camp body like a
                # rotation regular (P20). A starter traded in and hurt before he
                # played is uncharged too; that is the known cost of the rule.
                continue
            rows.append(
                {
                    "player": athlete.get("displayName") or "unknown",
                    "team": team,
                    "sport": sport,
                    "season": season,
                    "week": week,
                    "position": position or None,
                    "status": status,
                    "practice_trend": None,
                    # ESPN carries no usage data, so the snap table is consulted
                    # by name. Without this every ESPN row would fall back to a
                    # single default and a third-stringer would be priced like
                    # a starter, which is the failure this layer must avoid.
                    "snap_share": share,
                    "play_probability": play_probability(status, None),
                    "source": "espn",
                }
            )
    if unmatched:
        print(f"  [warn] {len(unmatched)} ESPN team name(s) unmatched: {', '.join(sorted(unmatched)[:4])}")
    return rows


def _resolve_team(espn_name: str, known: dict[str, str]) -> str | None:
    best, best_score = None, 0.0
    for full_name, canonical in known.items():
        score = similarity(espn_name, full_name)
        if score > best_score:
            best, best_score = canonical, score
    return best if best_score >= 0.80 else None


# --- entrypoint ------------------------------------------------------------

def merge_feeds(nfl_rows: list[dict], espn_rows: list[dict]) -> tuple[list[dict], dict]:
    """nflverse and ESPN rows as one report, with what the merge did.

    nflverse (the official report) is the authority where both cover a
    player, and ESPN fills gaps. Matched on player_key, not the raw name: the
    feeds disagree about generational suffixes, and an unmatched duplicate is
    charged twice (P20).

    One field is the exception (P40): Injured Reserve is a roster fact the
    weekly report doesn't carry, so an ESPN `ir` replaces the status of an
    nflverse row with no game status. The row keeps nflverse's practice,
    position and snap share. Where the official report does give a status, it
    is newer evidence than an ESPN IR flag, which can be stale after an
    activation; that row is kept and returned as a conflict.
    """
    rows = [dict(r) for r in nfl_rows]
    by_key = {player_key(r["team"], r["player"]): r for r in rows}
    added, covered, ir_applied, ir_conflicts = [], 0, [], []
    for e in espn_rows:
        k = player_key(e["team"], e["player"])
        n = by_key.get(k)
        if n is None:
            added.append(e)
            continue
        covered += 1
        if e.get("status") != "ir":
            continue
        if n.get("status") is None:
            n["status"] = "ir"
            n["play_probability"] = play_probability("ir", n.get("practice_trend"))
            ir_applied.append({"team": n["team"], "player": n["player"]})
        elif n.get("status") != "ir":
            ir_conflicts.append({"team": n["team"], "player": n["player"], "nflverse_status": n.get("status")})
    return rows + added, {"added": len(added), "covered": covered,
                          "ir_applied": ir_applied, "ir_conflicts": ir_conflicts}


def run(sport: str = "nfl", season: int | None = None, week: int | None = None) -> int:
    from datetime import datetime, timezone

    store = db.get_store()
    season = season or datetime.now(timezone.utc).year
    if week is None:
        week = _infer_week(store, sport, season)

    print(f"[injuries] {sport} season {season} week {week} -> {store.backend}")

    rows: list[dict] = []
    shares: dict = {}
    if sport == "nfl":
        try:
            shares = _snap_shares(season)
            rows += ingest_nfl(store, season, week, shares)
        except Exception as exc:  # noqa: BLE001
            print(f"  [warn] nflverse injuries failed: {exc}")

    espn_rows = ingest_espn(store, sport, season, week, shares)
    rows, merge = merge_feeds(rows, espn_rows)
    if espn_rows:
        print(f"  espn: {len(espn_rows)} rows ({merge['added']} new, {merge['covered']} already covered, "
              f"{len(merge['ir_applied'])} IR applied over nflverse)")
    for c in merge["ir_conflicts"]:
        print(f"  [conflict] {c['team']} {c['player']}: ESPN says Injured Reserve, the official report says "
              f"{c['nflverse_status']}; the official report is kept")

    store.upsert("injuries", db.stamp(rows))

    teams_covered = len({r["team"] for r in rows})
    total_teams = len(store.select("teams", {"sport": sport}))
    out_count = sum(1 for r in rows if r["status"] == "out")
    print(
        f"  {len(rows)} injury rows | {out_count} ruled out | "
        f"{teams_covered}/{total_teams} teams have data"
    )
    if total_teams and teams_covered / total_teams < 0.5:
        print(
            "  [note] coverage is partial. Games involving teams with no data get "
            "no injury adjustment rather than being assumed healthy."
        )
    store.close()
    if sport == "nfl":
        # Gameday inactives (P10): only games near kickoff are asked, and a list
        # not posted yet writes nothing, so this is cheap on any other day.
        from .ingest_inactives import run as ingest_inactives

        try:
            ingest_inactives(season, week)
        except Exception as exc:  # noqa: BLE001 - the injury report stands without it
            print(f"  [warn] inactives skipped: {exc}")
    return len(rows)


def _infer_week(store: db.Store, sport: str, season: int) -> int:
    from .features import parse_dt
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    upcoming = [
        g for g in store.select("games", {"sport": sport})
        if not g.get("completed") and (k := parse_dt(g.get("kickoff_time"))) and k >= now
    ]
    if not upcoming:
        return 1
    return int(min(upcoming, key=lambda g: parse_dt(g["kickoff_time"]))["week"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest injury reports.")
    parser.add_argument("--sport", default="nfl", choices=["nfl", "ncaaf"])
    parser.add_argument("--season", type=int)
    parser.add_argument("--week", type=int)
    args = parser.parse_args()
    run(args.sport, args.season, args.week)
