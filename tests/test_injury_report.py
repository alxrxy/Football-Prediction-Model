"""Tests for picking the current injury report out of the injuries table.

    python -m tests.test_injury_report

Rows are upserted and never deleted, so the table holds every report ever
pulled. Charging a player from an old pull is exactly the bug these pin down:
a player who has since been cleared must stop costing his team points.
"""

from __future__ import annotations

import sys

from src.features import latest_injury_report, score_injuries

PASS, FAIL = 0, 0


def check(label: str, got, want) -> None:
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got {got!r}, want {want!r}")


def row(player, source, pulled_at, team="NE", week=2):
    return {"player": player, "source": source, "pulled_at": pulled_at,
            "team": team, "season": 2026, "week": week}


def players(rows):
    return sorted(r["player"] for r in rows)


def test_dropped_player_not_charged():
    """A player missing from the latest pull is no longer on the report."""
    rows = [
        row("Cleared Guy", "nflverse", "2026-09-12T08:46:00+00:00"),
        row("Still Out", "nflverse", "2026-09-13T16:18:00+00:00"),
    ]
    check("only the latest pull", players(latest_injury_report(rows)), ["Still Out"])


def test_latest_is_per_source():
    """A feed that failed this run falls back to its own previous report."""
    rows = [
        row("Espn Old", "espn", "2026-09-12T18:38:00+00:00"),
        row("Espn New", "espn", "2026-09-13T16:18:00+00:00"),
        # nflverse failed on the 16:18 run; its last good pull is still used.
        row("Nflverse Last", "nflverse", "2026-09-12T08:46:00+00:00"),
    ]
    check("per-source latest", players(latest_injury_report(rows)),
          ["Espn New", "Nflverse Last"])


def test_mixed_timestamp_formats():
    """Supabase and SQLite render the same instant differently."""
    rows = [
        row("A", "espn", "2026-09-13T16:18:00Z"),
        row("B", "espn", "2026-09-13T16:18:00+00:00"),
        row("C", "espn", "2026-09-13T11:18:00-05:00"),
    ]
    check("same instant kept", players(latest_injury_report(rows)), ["A", "B", "C"])


def test_partial_pull_keeps_other_teams():
    """P19: a pull covering 2 teams leaves every other team's report in force."""
    rows = [
        row("Hou Earlier", "nflverse", "2026-09-17T08:00:00+00:00", team="HOU"),
        row("Kc Earlier", "nflverse", "2026-09-17T08:00:00+00:00", team="KC"),
        row("Buf Later", "nflverse", "2026-09-18T08:00:00+00:00", team="BUF"),
        row("Det Later", "nflverse", "2026-09-18T08:00:00+00:00", team="DET"),
    ]
    check("other teams kept", players(latest_injury_report(rows)),
          ["Buf Later", "Det Later", "Hou Earlier", "Kc Earlier"])


def test_per_team_latest_still_clears():
    """Within one team, only its latest pull counts."""
    rows = [
        row("Cleared", "nflverse", "2026-09-17T08:00:00+00:00", team="HOU"),
        row("Still Out", "nflverse", "2026-09-18T08:00:00+00:00", team="HOU"),
    ]
    check("team's latest pull", players(latest_injury_report(rows)), ["Still Out"])


def test_last_week_not_carried_forward():
    """A team yet to file this week has no nflverse rows, not last week's."""
    rows = [
        row("Wk1 Stale", "nflverse", "2026-09-16T07:42:00+00:00", team="ATL", week=1),
        row("Wk2 Buf", "nflverse", "2026-09-17T00:36:00+00:00", team="BUF", week=2),
        row("Espn Atl", "espn", "2026-09-17T00:36:00+00:00", team="ATL", week=2),
    ]
    check("latest week only", players(latest_injury_report(rows)), ["Espn Atl", "Wk2 Buf"])


def test_espn_stays_whole_pull():
    """ESPN is one league-wide call: a team missing from it has nobody listed."""
    rows = [
        row("Espn Old Hou", "espn", "2026-09-16T08:00:00+00:00", team="HOU"),
        row("Espn New Kc", "espn", "2026-09-17T08:00:00+00:00", team="KC"),
    ]
    check("espn latest pull only", players(latest_injury_report(rows)), ["Espn New Kc"])


def test_empty():
    check("empty table", latest_injury_report([]), [])


def test_snap_share_falls_back_per_player():
    """P14: week 1's snaps cover only teams that have played, and never a
    player who was already hurt. Everyone else takes last season's share."""
    import pandas as pd

    from src.ingest_injuries import merge_snap_shares, player_key

    current = pd.DataFrame({"team": ["NE", "NE"], "player": ["Played Both", "Rookie"],
                            "offense_pct": [0.9, 0.4], "defense_pct": [0.0, 0.0]})
    prior = pd.DataFrame({"team": ["NE", "KC", "NE"], "player": ["Played Both", "Hurt Starter", "Sat Week One"],
                          "offense_pct": [0.5, 0.93, 0.0], "defense_pct": [0.0, 0.0, 0.75]})
    shares = merge_snap_shares([current, prior])
    check("current season wins", shares[player_key("NE", "Played Both")], 0.9)
    check("team yet to play -> prior", shares[player_key("KC", "Hurt Starter")], 0.93)
    check("player without current snaps -> prior", shares[player_key("NE", "Sat Week One")], 0.75)
    check("rookie keeps current", shares[player_key("NE", "Rookie")], 0.4)


# --- gameday inactives (P10) --------------------------------------------------

def _rep(player, status, team="BUF", week=2, prob=0.55, snap=0.8):
    return {"player": player, "team": team, "sport": "nfl", "season": 2026, "week": week, "position": "WR",
            "status": status, "play_probability": prob, "snap_share": snap, "source": "espn",
            "pulled_at": "2026-09-17T22:50:00+00:00"}


def _inact(player, team="BUF", week=2, pulled="2026-09-17T22:45:00+00:00", game="g1", snap=None):
    return {"game_id": game, "team": team, "player": player, "sport": "nfl", "season": 2026, "week": week,
            "position": "RB", "snap_share": snap, "source": "espn_inactives", "pulled_at": pulled}


def test_inactives_override():
    from src.features import apply_inactives

    report = [_rep("T.J. Sanders", "questionable"), _rep("Cole Bishop", "questionable"),
              _rep("Ed Oliver", "out", prob=0.0), _rep("Joey Bosa", "questionable", team="MIA")]
    out = {r["player"]: r for r in apply_inactives(report, [_inact("T.J. Sanders"), _inact("Ty Johnson", snap=0.2)])}
    check("a questionable player on the list is out", (out["T.J. Sanders"]["status"], out["T.J. Sanders"]["play_probability"]),
          ("inactive", 0.0))
    check("a questionable player not on it is active", (out["Cole Bishop"]["status"], out["Cole Bishop"]["play_probability"]),
          ("active", 1.0))
    check("an Out row is left as it is", (out["Ed Oliver"]["status"], out["Ed Oliver"]["play_probability"]), ("out", 0.0))
    check("a team with no posted list is unchanged", out["Joey Bosa"], report[3])
    check("an unreported inactive is added, at his snap share",
          (out["Ty Johnson"]["status"], out["Ty Johnson"]["play_probability"], out["Ty Johnson"]["snap_share"]),
          ("inactive", 0.0, 0.2))
    out2 = {r["player"]: r for r in apply_inactives(report, [_inact("Nobody Known")])}
    check("an unreported inactive with no snaps on record costs nothing", out2["Nobody Known"]["snap_share"], 0.0)
    check("nothing posted: report unchanged", apply_inactives(report, []), report)


def test_ir_counts_as_out():
    """P20: ESPN's "Injured Reserve" was dropped, so an IR'd starter vanished."""
    from src.ingest_injuries import _status, play_probability

    check("Injured Reserve becomes ir", _status("Injured Reserve"), "ir")
    check("an IR player does not play", play_probability("ir", None), 0.0)
    for status in ("out", "doubtful", "questionable", "probable"):
        check(f"{status} unchanged", _status(status.title()), status)
    check("an unknown status is still dropped", _status("Suspension"), None)
    # The charge is position weight x snap share x (1 - play prob) x 6.5:
    # HOU's To'oTo'o at 0.88 snaps is the case P20 was logged on.
    points, breakdown = score_injuries(
        [{"player": "Henry To'oTo'o", "team": "HOU", "position": "LB", "status": "ir",
          "snap_share": 0.88, "play_probability": 0.0}], "nfl")
    check("an IR linebacker is charged", round(points, 2), -1.06)
    check("and says why in the breakdown", breakdown[0]["status"], "ir")


def test_ir_survives_a_posted_inactive_list():
    """An IR player is not on the game roster, so a list that omits him says
    nothing about him -- and one that names him must not add a second row."""
    from src.features import apply_inactives

    report = [_rep("Henry Tooto'o", "ir", prob=0.0), _rep("Cole Bishop", "questionable")]
    out = apply_inactives(report, [_inact("T.J. Sanders")])
    rows = {r["player"]: r for r in out}
    check("IR is left alone by a list that omits him",
          (rows["Henry Tooto'o"]["status"], rows["Henry Tooto'o"]["play_probability"]), ("ir", 0.0))
    listed = apply_inactives(report, [_inact("Henry Tooto'o")])
    check("a list naming him does not add a second row", len(listed), len(report))
    check("and he stays out", [r["play_probability"] for r in listed if "Tooto" in r["player"]], [0.0])


def test_inactives_never_gate_a_later_week():
    from src.features import apply_inactives

    report = [_rep("Cole Bishop", "questionable", week=3)]
    check("last week's list does not touch this week's report",
          apply_inactives(report, [_inact("Cole Bishop", week=2)]), report)


def test_inactives_latest_pull_wins():
    from src.features import apply_inactives

    report = [_rep("T.J. Sanders", "questionable"), _rep("Cole Bishop", "questionable")]
    rows = [_inact("T.J. Sanders", pulled="2026-09-17T22:00:00+00:00"),
            _inact("Cole Bishop", pulled="2026-09-17T22:30:00+00:00")]
    out = {r["player"]: r for r in apply_inactives(report, rows)}
    check("a corrected list replaces the earlier one", (out["T.J. Sanders"]["status"], out["Cole Bishop"]["status"]),
          ("active", "inactive"))


def test_inactives_fetch_not_posted_writes_nothing():
    from src import ingest_inactives as ii

    class Store:
        def select(self, table, where=None):
            if table == "games":
                return [{"game_id": "g1", "season": 2026, "week": 2, "home_team": "BUF", "away_team": "DET"}]
            return [{"team": "BUF", "full_name": "Buffalo Bills"}, {"team": "DET", "full_name": "Detroit Lions"}]

    board = {"events": [{"id": "1", "date": "2026-09-18T00:15Z", "competitions": [{
        "status": {"type": {"state": "pre"}},
        "competitors": [{"homeAway": "home", "team": {"id": "2", "displayName": "Buffalo Bills"}},
                        {"homeAway": "away", "team": {"id": "8", "displayName": "Detroit Lions"}}]}]}]}
    roster = {"entries": [{"playerId": 1, "displayName": "T. Sanders", "didNotPlay": True, "athlete": {"$ref": "x"}},
                          {"playerId": 2, "displayName": "J. Allen", "didNotPlay": False, "athlete": {"$ref": "y"}}]}
    from datetime import datetime, timezone
    # 23:00Z against a 00:15Z kickoff is 1.25 h out, inside the P33 window.
    now = datetime(2026, 9, 17, 23, 0, tzinfo=timezone.utc)
    saved = ii._get, ii._athlete
    try:
        ii._get = lambda url, params=None: (200, board) if "scoreboard" in url else (404, None)
        rows, log = ii.fetch(Store(), 2026, 2, now=now)
        check("404 before posting: no rows", rows, [])
        check("and it is logged as not posted", sum(x["result"].startswith("not posted") for x in log), 2)
        ii._get = lambda url, params=None: (200, board) if "scoreboard" in url else (200, roster)
        ii._athlete = lambda ref: ("T.J. Sanders", "DT")
        rows, log = ii.fetch(Store(), 2026, 2, now=now)
        check("posted: only didNotPlay players, full names", sorted({(r["team"], r["player"]) for r in rows}),
              [("BUF", "T.J. Sanders"), ("DET", "T.J. Sanders")])
        far = datetime(2026, 9, 16, 0, 0, tzinfo=timezone.utc)
        rows, log = ii.fetch(Store(), 2026, 2, now=far)
        check("a game outside the window is not asked", (rows, log[0]["result"]), ([], "outside window"))
    finally:
        ii._get, ii._athlete = saved


def test_inactives_ignore_rosters_read_early():
    """P33. Asked more than 2 h out, the endpoint answers 200 with stale
    didNotPlay flags that look exactly like a real list, so the gate is the
    clock, not the contents."""
    from datetime import datetime, timedelta, timezone

    from src import ingest_inactives as ii

    class Store:
        def select(self, table, where=None):
            if table == "games":
                return [{"game_id": "g1", "season": 2026, "week": 2, "home_team": "BUF", "away_team": "DET"}]
            return [{"team": "BUF", "full_name": "Buffalo Bills"}, {"team": "DET", "full_name": "Detroit Lions"}]

    board = {"events": [{"id": "1", "date": "2026-09-18T00:15Z", "competitions": [{
        "status": {"type": {"state": "pre"}},
        "competitors": [{"homeAway": "home", "team": {"id": "2", "displayName": "Buffalo Bills"}},
                        {"homeAway": "away", "team": {"id": "8", "displayName": "Detroit Lions"}}]}]}]}
    # A full-looking 7-man list, the shape the premature reads took on 2026-09-20.
    roster = {"entries": [{"playerId": i, "displayName": f"P. {i}", "didNotPlay": True, "athlete": {"$ref": str(i)}}
                          for i in range(7)]}
    kick = datetime(2026, 9, 18, 0, 15, tzinfo=timezone.utc)
    saved = ii._get, ii._athlete
    try:
        ii._get = lambda url, params=None: (200, board) if "scoreboard" in url else (200, roster)
        ii._athlete = lambda ref: (f"Player {ref}", "WR")
        for hours, want_rows, label in (
            (8.6, 0, "a roster 8.6 h out is not asked (the 2026-09-20 IND case)"),
            (4.3, 0, "nor one 4.3 h out (the DEN/LAC/SEA cases)"),
            (2.5, 0, "nor one just outside the gate"),
            (1.58, 14, "a 20:25Z game at its own window's refresh is inside"),
            (1.25, 14, "and so is the T-75m refresh the schedule aims for"),
        ):
            now = kick - timedelta(hours=hours)
            rows, log = ii.fetch(Store(), 2026, 2, now=now)
            check(label, len(rows), want_rows)
            if not want_rows:
                check(f"  and it is logged as outside the window at {hours} h", log[0]["result"], "outside window")
        # --replay must still reach a finished game, whatever the clock says.
        rows, _ = ii.fetch(Store(), 2026, 2, now=kick - timedelta(hours=8.6), include_final=True)
        check("--replay is not gated by the lookahead", len(rows), 14)
    finally:
        ii._get, ii._athlete = saved


if __name__ == "__main__":
    for fn in [
        test_dropped_player_not_charged,
        test_latest_is_per_source,
        test_mixed_timestamp_formats,
        test_partial_pull_keeps_other_teams,
        test_per_team_latest_still_clears,
        test_last_week_not_carried_forward,
        test_espn_stays_whole_pull,
        test_empty,
        test_snap_share_falls_back_per_player,
        test_ir_counts_as_out,
        test_ir_survives_a_posted_inactive_list,
        test_inactives_override,
        test_inactives_never_gate_a_later_week,
        test_inactives_latest_pull_wins,
        test_inactives_fetch_not_posted_writes_nothing,
        test_inactives_ignore_rosters_read_early,
    ]:
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
