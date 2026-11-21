"""Store an OFFICIAL gameday inactive list by hand (team site, or NFL.com as backup; never ESPN's list).

    python calibration/store_official_inactives.py 2026_11_IND_HOU official_team_article \
        "IND=Sauce Gardner;Charvarius Ward" "HOU=Danielle Hunter;Woody Marks" [--dry-run]

Writes one row per player to the `inactives` table with the given source, the same shape the
window refreshes of weeks 8-10 stored (`features.apply_inactives` then resolves the team:
listed players to 0, unlisted Questionable / Doubtful players to 1.0). It only upserts; it
deletes nothing. A team must be one of the game's two teams, and the game must not have kicked off.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import db  # noqa: E402
from src.features import parse_dt  # noqa: E402
from src.ingest_injuries import _snap_shares, player_key  # noqa: E402

SOURCES = ("official_team_article", "nfl_com_list")


def main(argv):
    dry = "--dry-run" in argv
    argv = [a for a in argv if a != "--dry-run"]
    gid, source, *lists = argv
    if source not in SOURCES:
        raise SystemExit(f"source must be one of {SOURCES}")
    store = db.get_store()
    game = store.select("games", {"game_id": gid})[0]
    now = datetime.now(timezone.utc)
    if parse_dt(game["kickoff_time"]) <= now:
        raise SystemExit(f"{gid} has kicked off; a list stored now could not have been used pregame")
    season, week = int(game["season"]), int(game["week"])
    shares = _snap_shares(season)
    known = {}
    for r in store.select("injuries", {"sport": "nfl", "season": season, "week": week}):
        known[player_key(r["team"], r["player"])] = r
    try:
        import nfl_data_py as nfl

        ros = nfl.import_weekly_rosters([season])
        ros = ros[ros.week == ros.week.max()]
        pos = {player_key(t, n): str(p).upper() for t, n, p in zip(ros.team, ros.player_name, ros.position)}
    except Exception:  # noqa: BLE001 - positions are a convenience; the list is what matters
        pos = {}
    stamp = now.isoformat()
    rows = []
    for item in lists:
        team, names = item.split("=", 1)
        if team not in (game["home_team"], game["away_team"]):
            raise SystemExit(f"{team} is not in {gid}")
        for name in [n.strip() for n in names.split(";") if n.strip()]:
            k = player_key(team, name)
            rep = known.get(k)
            rows.append({"game_id": gid, "team": team, "player": rep["player"] if rep else name, "sport": "nfl",
                         "season": season, "week": week, "espn_id": "",
                         "position": (rep or {}).get("position") or pos.get(k),
                         "snap_share": shares.get(k), "source": source, "first_seen_at": stamp, "pulled_at": stamp})
    for r in rows:
        on = known.get(player_key(r["team"], r["player"]))
        print(f"  {r['team']:<4} {r['player']:<26} {str(r['position']):<5} share {r['snap_share']}  "
              f"report: {(on or {}).get('status') or ('on report, no status' if on else 'not on the report')}")
    teams = {r["team"] for r in rows}
    print(f"{len(rows)} rows for {sorted(teams)} ({source}){' [dry run, nothing stored]' if dry else ''}")
    if not dry:
        db.upsert_or_mirror(store, "inactives", rows)
        print("stored")


if __name__ == "__main__":
    main(sys.argv[1:])
