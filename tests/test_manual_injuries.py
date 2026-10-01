"""Tests for the hand-transcribed injury file (P64).

    python -m tests.test_manual_injuries

Pins the criteria set in the 2026-09-30 P64 entry: an invalid file is refused
whole with every error listed (C3, C4), a manual row replaces the feeds for
its player so nobody is charged twice (C2), days 1-2 change nothing (C6), and
with no manual rows the report is what it was before (C5).
"""

from __future__ import annotations

import sys

from src import manual_injuries as mi
from src.features import STARTER_SLOTS, latest_injury_report, score_injuries
from src.ingest_injuries import play_probability, player_key

PASS, FAIL = 0, 0

TEAMS = {"PIT", "CIN", "NO", "SEA", "LA", "ATL"}
POSITIONS = set(STARTER_SLOTS)
HEADER = "# season=2026 week=3\nteam,player,pos,injury,d1,d2,d3,game\n"


def check(label: str, got, want) -> None:
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got {got!r}, want {want!r}")


def parse(body: str, header: str = HEADER, week: int = 3):
    return mi.parse(header + body, 2026, week, TEAMS, POSITIONS)


def error_of(body: str, header: str = HEADER, week: int = 3) -> str:
    try:
        parse(body, header, week)
    except mi.ManualFileError as exc:
        return str(exc)
    return ""


def feed(player, team, status, practice, source="nflverse", share=0.9, pos="CB",
         pulled="2026-09-27T15:00:00+00:00"):
    return {"player": player, "team": team, "sport": "nfl", "season": 2026, "week": 3,
            "position": pos, "status": status, "practice_trend": practice,
            "snap_share": share, "play_probability": play_probability(status, practice),
            "source": source, "pulled_at": pulled}


def test_parse_valid_rows():
    rows = parse("PIT,Jalen Ramsey,CB,Hamstring,DNP,LP,LP,Questionable\n"
                 "NO,Kendre Miller,rb,Knee,LP,Full,-,\n"
                 "ATL,\"Penix Jr., Michael\",QB,Knee,-,-,-,Out\n")
    check("three rows", len(rows), 3)
    check("last practice day used", rows[0]["practice"], "limited")
    check("a trailing '-' falls back to the day before", rows[1]["practice"], "full")
    check("position upper-cased", rows[1]["position"], "RB")
    check("blank game status is None", rows[1]["status"], None)
    check("quoted name kept", rows[2]["player"], "Penix Jr., Michael")
    check("all '-' means no practice line", rows[2]["practice"], None)


def test_every_error_listed_at_once():
    """C3: one message names every bad line; nothing is returned."""
    msg = error_of("XXX,A B,CB,x,DNP,LP,LP,Questionable\n"          # line 3
                   "PIT,C D,ZZ,x,DNP,LP,LP,\n"                     # line 4
                   "PIT,E F,CB,x,DNP,maybe,LP,\n"                  # line 5
                   "PIT,G H,CB,x,DNP,LP,LP,Probable\n"             # line 6
                   "PIT,I J,CB,x,DNP,LP\n"                         # line 7
                   "PIT,K L,CB,x,DNP,LP,LP,Out\n"                  # line 8
                   "PIT,K L.,CB,x,DNP,LP,LP,Out\n")                # line 9 (same player_key)
    check("six errors counted (line 8 is valid)", "6 error(s)" in msg, True)
    for needle in ("line 3: unknown team 'XXX'", "line 4: unknown position 'ZZ'",
                   "line 5: d2 'maybe'", "Probable is not accepted", "line 7: 6 columns",
                   "line 9: PIT K L. is already listed on line 8"):
        check(f"names: {needle}", needle in msg, True)


def test_header_and_week_scoping():
    """C4: the file must say which week it is, and it must be this run's."""
    check("missing header refused", "missing '# season" in error_of("", header="team,player,pos,injury,d1,d2,d3,game\n"), True)
    check("wrong week refused", "file is for season 2026 week 3; this run is season 2026 week 4"
          in error_of("PIT,A B,CB,x,DNP,LP,LP,Out\n", week=4), True)
    check("bad column header refused", "column header" in error_of(
        "", header="# season=2026 week=3\nteam,name,pos,injury,d1,d2,d3,game\n"), True)


def test_merge_override_add_clear():
    """C1/C2 in small: overrides replace every feed row for the player, an
    unlisted player is untouched, a new player is added."""
    rows = [feed("Jalen Ramsey", "PIT", "questionable", "limited"),
            feed("Jalen Ramsey", "PIT", "questionable", None, source="espn"),
            feed("Other Guy", "PIT", "questionable", "dnp"),
            feed("Kendre Miller", "NO", "questionable", "limited", pos="RB")]
    manual = parse("PIT,Jalen Ramsey,CB,x,DNP,DNP,DNP,Doubtful\n"
                   "NO,Kendre Miller,RB,x,LP,FP,FP,\n"
                   "SEA,New Guy,WR,x,DNP,DNP,DNP,Questionable\n")
    merged, report = mi.merge(rows, manual, {}, 2026, 3)
    keys = [player_key(r["team"], r["player"]) for r in merged]
    check("no player twice", len(keys), len(set(keys)))
    by = {r["player"]: r for r in merged}
    check("override value", by["Jalen Ramsey"]["play_probability"], 0.10)
    check("override tagged manual", by["Jalen Ramsey"]["source"], "manual")
    check("override keeps feed snap share", by["Jalen Ramsey"]["snap_share"], 0.9)
    check("unlisted row unchanged", by["Other Guy"], rows[2])
    check("cleared player is a 1.0 row", by["Kendre Miller"]["play_probability"], 1.0)
    check("added player", by["New Guy"]["play_probability"], 0.25)
    check("actions", [r["action"] for r in report], ["override", "cleared", "added"])
    check("old value is the worst feed row", report[0]["old"], 0.55)


def test_ir_without_snaps_not_added_but_reported():
    manual = parse("SEA,Camp Body,LB,x,-,-,-,IR\n")
    merged, report = mi.merge([], manual, {}, 2026, 3)
    check("not added", merged, [])
    check("reported, not dropped", report[0]["action"].startswith("not added (IR"), True)


def test_days_one_two_inert():
    """C6: d1/d2 change nothing."""
    a = parse("PIT,A B,CB,x,DNP,DNP,LP,Questionable\n")
    b = parse("PIT,A B,CB,x,FP,FP,LP,Questionable\n")
    ma, _ = mi.merge([], a, {}, 2026, 3)
    mb, _ = mi.merge([], b, {}, 2026, 3)
    check("same merged rows", ma, mb)


def stamp(rows, pulled):
    return [dict(r, pulled_at=pulled) for r in rows]


def test_latest_report_with_manual():
    """C2 across runs. t0: plain feed. t1: with the file (PIT's only nflverse
    row moved to manual, so PIT's nflverse falls back to t0). t2: no file."""
    t0, t1, t2 = "2026-09-27T12:00:00+00:00", "2026-09-27T15:00:00+00:00", "2026-09-27T16:00:00+00:00"
    base = [feed("Jalen Ramsey", "PIT", "questionable", "limited"),
            feed("Kendre Miller", "NO", "questionable", "limited", pos="RB"),
            feed("Joe Burrow", "CIN", "questionable", "dnp", pos="QB")]
    manual = parse("PIT,Jalen Ramsey,CB,x,DNP,DNP,DNP,Out\n"
                   "NO,Kendre Miller,RB,x,LP,FP,FP,\n")
    run1, _ = mi.merge([dict(r) for r in base], manual, {}, 2026, 3)
    table = stamp(base, t0) + stamp(run1, t1)

    report = latest_injury_report(table)
    keys = [player_key(r["team"], r["player"]) for r in report]
    check("t1: no player twice (PIT fallback suppressed)", len(keys), len(set(keys)))
    by = {r["player"]: r for r in report}
    check("t1: Ramsey from manual", (by["Jalen Ramsey"]["source"], by["Jalen Ramsey"]["play_probability"]),
          ("manual", 0.0))
    check("t1: cleared Miller gone (not in fallback, no slot taken)", "Kendre Miller" in by, False)
    check("t1: Burrow untouched", by["Joe Burrow"]["source"], "nflverse")

    # C2 score check: PIT charge equals the feed row with the manual value put in by hand.
    by_hand = [dict(base[0], play_probability=0.0)]
    pit = [r for r in report if r["team"] == "PIT"]
    check("t1: PIT charge = hand substitution", round(score_injuries(pit, "nfl")[0], 6),
          round(score_injuries(by_hand, "nfl")[0], 6))

    table += stamp(base, t2)
    report = latest_injury_report(table)
    check("t2: no manual rows once a run without the file has written",
          [r["source"] for r in report], ["nflverse"] * 3)


def test_no_manual_rows_no_change():
    """C5: with no manual rows the report is the pre-P64 one (same rows, same order)."""
    t0, t1 = "2026-09-27T12:00:00+00:00", "2026-09-27T15:00:00+00:00"
    table = (stamp([feed("A B", "PIT", "out", None), feed("C D", "PIT", "questionable", "dnp")], t0)
             + stamp([feed("C D", "PIT", "questionable", "dnp", source="espn")], t0)
             + stamp([feed("C D", "PIT", "questionable", "dnp", source="espn")], t1))
    got = latest_injury_report(table)
    check("nflverse t0 + espn t1", [(r["player"], r["source"], r["pulled_at"]) for r in got],
          [("A B", "nflverse", t0), ("C D", "nflverse", t0), ("C D", "espn", t1)])


def test_invalid_file_stops_run_before_any_write():
    """C3: `ingest_injuries.run` refuses an invalid file before pulling or
    writing anything (depth_charts included), and `check_manual` raises too,
    which run_sunday treats as a critical stop."""
    import tempfile
    from pathlib import Path

    from src import db, ingest_injuries

    class Store:
        backend = "test"
        writes = 0

        def select(self, table, where=None):
            return [{"team": t} for t in TEAMS] if table == "teams" else []

        def upsert(self, *a, **k):
            Store.writes += 1

        def close(self):
            pass

    saved = (mi.MANUAL_DIR, db.get_store, ingest_injuries.ingest_nfl)
    pulled = []
    with tempfile.TemporaryDirectory() as tmp:
        mi.MANUAL_DIR = Path(tmp)
        db.get_store = lambda: Store()
        ingest_injuries.ingest_nfl = lambda *a, **k: pulled.append(1) or []
        try:
            mi.path_for(2026, 3).write_text(HEADER + "PIT,A B,CB,x,DNP,LP,LP,Probable\n", encoding="utf-8")
            for name, fn in (("run", lambda: ingest_injuries.run("nfl", 2026, 3)),
                             ("check_manual", lambda: ingest_injuries.check_manual("nfl", 2026, 3))):
                try:
                    fn()
                    raised = False
                except mi.ManualFileError:
                    raised = True
                check(f"{name} raises on an invalid file", raised, True)
        finally:
            mi.MANUAL_DIR, db.get_store, ingest_injuries.ingest_nfl = saved
    check("nothing pulled", pulled, [])
    check("nothing written", Store.writes, 0)


if __name__ == "__main__":
    for fn in [
        test_parse_valid_rows,
        test_every_error_listed_at_once,
        test_header_and_week_scoping,
        test_merge_override_add_clear,
        test_ir_without_snaps_not_added_but_reported,
        test_days_one_two_inert,
        test_latest_report_with_manual,
        test_no_manual_rows_no_change,
        test_invalid_file_stops_run_before_any_write,
    ]:
        print(fn.__name__)
        fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
