"""Tests for the P62 Phase 1 comparison (S1-S4 measurement over saved pulls).

    python -m tests.test_p62_compare

Each test builds saved pulls in a temp folder and checks that the comparison
reports what the criteria say it must: identical files pass everything, and
each kind of difference lands in the criterion and cause it belongs to.
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

from src import p62_compare as pc

PASS, FAIL = 0, 0
ODDS_AT = "2026-10-04T15:00:00+00:00"
SR_AT = "2026-10-04T15:02:00+00:00"
GID = "2026_04_PIT_CLE"


def check(label: str, got, want) -> None:
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got {got!r}, want {want!r}")


def q(median):
    return {"p10": median * 0.5, "p25": median * 0.75, "median": median, "p75": median * 1.25, "p90": median * 1.5}


SIMS = {GID: {"margin": {"p50": 1}, "total": {"p50": 40}, "home_win_prob": 0.5, "generated_at": ODDS_AT,
              "box_score": {"home": {"players": [{"player": "Jerry Jeudy", "position": "WR",
                                                  "receiving": {"yds": q(40), "rec": q(3)}}]},
                            "away": {"players": [{"player": "Aaron Rodgers", "position": "QB", "passing": {"yds": q(200)}},
                                                 {"player": "DK Metcalf", "position": "WR",
                                                  "receiving": {"yds": q(70), "rec": q(5)}}]}}}}


def bk(point, over=-110, under=-110):
    return {"point": point, "over": over, "under": under}


PLAYERS = {"Aaron Rodgers": {"player_pass_yds": {"draftkings": bk(212.5), "fanduel": bk(212.5)}},
           "DK Metcalf": {"player_reception_yds": {"draftkings": bk(55.5), "fanduel": bk(55.5)}},
           "Jerry Jeudy": {"player_reception_yds": {"draftkings": bk(45.5), "fanduel": bk(45.5)}}}


def lines(players, at):
    return {"pulled_at": at, "season": 2026, "week": 4, "markets": [],
            "games": {GID: {"home": "CLE", "away": "PIT", "kickoff": "2026-10-04T17:00:00+00:00",
                            "players": players, "pulled_at": at}}}


def write_pull(root: Path, stamp: str, odds_players, sr_players, sr_at=SR_AT, holdouts=None, sims=SIMS):
    d = root / "pulls" / stamp
    d.mkdir(parents=True)
    (d / "odds.json").write_text(json.dumps(lines(odds_players, ODDS_AT)), encoding="utf-8")
    (d / "sr.json").write_text(json.dumps(lines(sr_players, sr_at)), encoding="utf-8")
    (d / "holdouts.json").write_text(json.dumps(holdouts or {"prop_holdouts": [], "known_defects": []}), encoding="utf-8")
    if sims is not None:
        (d / "rank_20261004T150500Z").mkdir()
        (d / "rank_20261004T150500Z" / "sims.json").write_text(json.dumps(sims), encoding="utf-8")


def run(root, min_gameday=1):
    """The comparison logic tests use one gameday pull, so they run with the minimum at 1; the minimum itself
    (user, 2026-10-07) has its own test below."""
    saved = pc.MIN_GAMEDAY_PAIRS
    pc.MIN_GAMEDAY_PAIRS = min_gameday
    try:
        return pc.run(None, None, do_grade=False, out_dir=root)
    finally:
        pc.MIN_GAMEDAY_PAIRS = saved


def test_identical_files_pass():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_pull(root, "20261004T150200Z", PLAYERS, PLAYERS)
        text, v = run(root)
        check("S1 pass", v["S1"], "PASS")
        check("S2 pass", v["S2"], "PASS")
        check("S3 pass", v["S3"], "PASS")
        check("S4 pass", v["S4"], "PASS")
        check("S5 skipped, said so", v["S5"], "UNMEASURED (grading skipped)")
        check("no changes", "changes: 0" in text, True)


def test_pair_window():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_pull(root, "20261004T152000Z", PLAYERS, PLAYERS, sr_at="2026-10-04T15:20:00+00:00")
        text, v = run(root)
        check("20 min apart is excluded, not compared", v["S1"], "UNMEASURED")
        check("no pairs: S2 unmeasured, not pass", v["S2"], "UNMEASURED (no paired games)")
        check("no pairs: S4 unmeasured, not pass", v["S4"], "UNMEASURED")
        check("no pairs: S3 unmeasured", v["S3"], "UNMEASURED")
        check("exclusion listed", "20.0 min after the Odds API pull" in text, True)


def test_word_order_is_misnamed_and_stops():
    sr = copy.deepcopy(PLAYERS)
    sr["Metcalf DK"] = sr.pop("DK Metcalf")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_pull(root, "20261004T150200Z", PLAYERS, sr)
        text, v = run(root)
        check("reversed name is misnamed, not absent", "misnamed (as 'Metcalf DK', word order)" in text, True)
        check("S2 stops", v["S2"], "STOP")


def test_priced_qb_difference_stops():
    sr = copy.deepcopy(PLAYERS)
    del sr["Aaron Rodgers"]
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_pull(root, "20261004T150200Z", PLAYERS, sr)
        text, v = run(root)
        check("priced-QB sets differ -> stop", v["S2"], "STOP")
        check("named in the report", "priced QBs differ" in text, True)
        check("Rodgers absent counts in S1", v["S1"], "FAIL")


def test_holdout_name_difference_stops():
    holds = {"prop_holdouts": [[GID, "DK Metcalf", "player_reception_yds"]], "known_defects": []}
    sr = copy.deepcopy(PLAYERS)
    sr["D.K. Metcalf"] = sr.pop("DK Metcalf")   # same pnorm, different raw string
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_pull(root, "20261004T150200Z", PLAYERS, sr, holdouts=holds)
        text, v = run(root)
        check("raw-name hold lookup differs -> stop (S2d)", v["S2"], "STOP")
        check("S1 still covered (pnorm match)", v["S1"], "PASS")


def test_line_difference_counted_and_attributed():
    sr = copy.deepcopy(PLAYERS)
    sr["Jerry Jeudy"]["player_reception_yds"] = {"draftkings": bk(30.5), "fanduel": bk(30.5)}
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_pull(root, "20261004T150200Z", PLAYERS, sr)
        text, v = run(root)
        check("S3 sees 2 of 6 totals differ", "totals equal 4/6" in text, True)
        check("tagged unexplained (2 min apart, no previous pull)", "unexplained 2" in text, True)
        check("Jeudy's flip attributed to line", "flips -> line" in text, True)
        check("S4 not stopped by an explained change", v["S4"], "PASS")


def test_extra_book_is_book_mix():
    sr = copy.deepcopy(PLAYERS)
    sr["Jerry Jeudy"]["player_reception_yds"]["betmgm"] = bk(30.5)
    sr["Jerry Jeudy"]["player_reception_yds"]["betrivers"] = bk(30.5)
    sr["Jerry Jeudy"]["player_reception_yds"]["williamhill_us"] = bk(30.5)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_pull(root, "20261004T150200Z", PLAYERS, sr)
        text, v = run(root)
        check("shared books agree", v["S3"], "PASS")
        check("change from Sportradar-only books -> book mix", "-> book mix" in text, True)
        check("no unexplained", v["S4"], "PASS")


def test_no_sims_is_unmeasured_not_pass():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_pull(root, "20261004T150200Z", PLAYERS, PLAYERS, sims=None)
        text, v = run(root)
        check("S4 unmeasured without ranking sims", v["S4"], "UNMEASURED")
        check("S2 says partly unmeasured", v["S2"], "PASS (partly unmeasured)")


def test_nickname_is_misnamed_not_absent():
    """User ruling 10/1: Cam / Cameron is a name failure (S2), not coverage (S1)."""
    sr = copy.deepcopy(PLAYERS)
    sr["Kaylin Metcalf"] = sr.pop("DK Metcalf")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_pull(root, "20261004T150200Z", PLAYERS, sr)
        text, v = run(root)
        check("misnamed by shared last name", "misnamed (as 'Kaylin Metcalf', same last name)" in text, True)
        check("coverage unaffected", "covered 3/3" in text, True)
        check("S2 stops", v["S2"], "STOP")


def test_odds_only_book_is_book_mix():
    """User ruling 10/1: both files cut to shared books, so a change caused by a
    book only the Odds API carries is book mix, not unexplained."""
    odds = copy.deepcopy(PLAYERS)
    for b in ("betonlineag", "bovada", "betmgm"):
        odds["Jerry Jeudy"]["player_reception_yds"][b] = bk(30.5)   # Odds-API-only books move the posted line
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_pull(root, "20261004T150200Z", odds, PLAYERS)
        text, v = run(root)
        check("odds-only books -> book mix", "-> book mix" in text and "-> unexplained" not in text, True)
        check("S4 passes", v["S4"], "PASS")


def test_lag_tag():
    """A Sportradar value equal to the Odds API's previous pull is lag, not unexplained."""
    old = copy.deepcopy(PLAYERS)
    old["Jerry Jeudy"]["player_reception_yds"] = {"draftkings": bk(30.5), "fanduel": bk(30.5)}
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_pull(root, "20261004T150200Z", old, old)          # earlier pull: both at 30.5
        later = root / "pulls" / "20261004T160200Z"
        write_pull(root, "20261004T160200Z", PLAYERS, old)      # books moved to 45.5; Sportradar still 30.5
        for f, at in (("odds.json", "2026-10-04T16:00:00+00:00"), ("sr.json", "2026-10-04T16:02:00+00:00")):
            d = json.loads((later / f).read_text(encoding="utf-8"))
            d["pulled_at"] = d["games"][GID]["pulled_at"] = at
            (later / f).write_text(json.dumps(d), encoding="utf-8")
        text, v = run(root)
        check("tagged lag", "lag 2" in text, True)


def test_grade():
    rows = [{"game_id": GID, "team": "PIT", "odds_name": "DK Metcalf", "player": "DK Metcalf",
             "market": "player_reception_yds", "line": 55.5, "pick": "under"},
            {"game_id": GID, "team": "PIT", "odds_name": "Aaron Rodgers", "player": "Aaron Rodgers",
             "market": "player_pass_yds", "line": 212.5, "pick": "over"},
            {"game_id": GID, "team": "CLE", "odds_name": "Jerry Jeudy", "player": "Jerry Jeudy",
             "market": "player_receptions", "line": 4.0, "pick": "over"},
            {"game_id": GID, "team": "CLE", "odds_name": "Jeudy Jerry", "player": "Jerry Jeudy",
             "market": "player_receptions", "line": 4.5, "pick": "over"}]
    actual = {"players": {"away": [{"name": "DK Metcalf", "rec_yds": 40, "rec": 3},
                                   {"name": "Aaron Rodgers", "pass_yds": 250}],
                          "home": [{"name": "Jerry Jeudy", "rec_yds": 50, "rec": 4}]}}
    out = pc.grade(rows, actual, {"home": "CLE", "away": "PIT"})
    check("under that stays under wins; over that clears wins; exact line pushes; bad name unmatched",
          [r["result"] for r in out], ["W", "W", "push", "name unmatched"])


def test_sim_check_swaps_both_read_points():
    """S8(b) is only meaningful if both places the sim reads props lines see the
    variant file: P49's qb_context and P53's qb_check_inputs."""
    from src import features, p62_sim_check, simulate_nfl

    class Store:
        def select(self, table, where=None):
            return []

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        f = tmp / "variant.json"
        f.write_text(json.dumps(lines({"Only Variant": {"player_pass_yds": {"draftkings": bk(200.5)}}}, ODDS_AT)),
                     encoding="utf-8")
        d = p62_sim_check._variant(tmp, "v", f)
        saved = (features.config, simulate_nfl.config)
        features.config = simulate_nfl.config = p62_sim_check._DataDir(d)
        try:
            p49 = features.qb_context(Store(), depth={})["priced"].get(GID)
            p53 = simulate_nfl.qb_check_inputs(Store()).books.get(GID, {}).get("pass")
        finally:
            features.config, simulate_nfl.config = saved
        check("P49 reads the variant", p49, {"Only Variant"})
        check("P53 reads the variant", p53, {"Only Variant"})
        check("restored afterwards", features.config is saved[0] and simulate_nfl.config is saved[1], True)


def test_export_page_json():
    """S8(c): the page JSON says what the report says, and building it opens no socket."""
    import socket

    sr = copy.deepcopy(PLAYERS)
    sr["Jerry Jeudy"]["player_reception_yds"] = {"draftkings": bk(30.5), "fanduel": bk(30.5)}
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_pull(root, "20261004T150200Z", PLAYERS, sr)
        _, want = pc.run(pc._parse(pc.WINDOW_START), pc._parse(pc.WINDOW_END), do_grade=False, out_dir=root)
        real = socket.socket

        def no_network(*a, **k):
            raise AssertionError("export opened a socket")

        socket.socket = no_network
        try:
            out = root / "public" / "p62_compare.json"
            pc.export(out, out_dir=root)
        finally:
            socket.socket = real
        d = json.loads(out.read_text(encoding="utf-8"))
        check("verdict same as the report", d["verdict"], want)
        check("one status line per criterion, S1-S5", [(c["id"], c["status"]) for c in d["criteria"]],
              [(k, want[k]) for k in ("S1", "S2", "S3", "S4", "S5")])
        check("S5 says why it is not graded", "not on refresh" in d["criteria"][4]["detail"][0], True)
        jeudy = [c for c in d["changes"] if c["player"] == "Jerry Jeudy"]
        check("Jeudy's change listed with its cause", [(c["kinds"], c["cause"]) for c in jeudy], [(["flips"], "line")])
        check("both lines carried", (jeudy[0]["odds_line"], jeudy[0]["sr_line"]), (45.5, 30.5))
        check("line differences carried", (d["line_diff_count"], len(d["line_diffs"])), (2, 2))
        check("difference row has both sides", d["line_diffs"][0]["sr"]["point"], 30.5)


def test_export_outside_window_or_empty():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_pull(root, "20261020T150200Z", PLAYERS, PLAYERS)   # after the window closes
        out = root / "p62_compare.json"
        d = pc.export(out, out_dir=root)
        check("a pull outside the window is not counted", d["pulls"], [])
        check("all five unmeasured, none pass", [c["status"] for c in d["criteria"]], ["UNMEASURED"] * 5)
        check("file written for the page", out.exists(), True)


def test_export_says_held_out_or_not_priced():
    """A prop off one source's ranking is either held out (line and side kept) or never priced."""
    sr = copy.deepcopy(PLAYERS)
    sr["Jerry Jeudy"]["player_reception_yds"] = {"draftkings": bk(5.5), "fanduel": bk(5.5)}   # gap far past the limit
    del sr["DK Metcalf"]["player_reception_yds"]                                             # no line at all
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_pull(root, "20261004T150200Z", PLAYERS, sr)
        d = pc.export(root / "p62_compare.json", out_dir=root)
        by = {c["player"]: c for c in d["changes"]}
        j, m = by.get("Jerry Jeudy", {}), by.get("DK Metcalf", {})
        check("Jeudy ranked in the Odds API list", j.get("odds_state"), "ranked")
        check("Jeudy held out on a gap in Sportradar's", j.get("sr_state"), "held: gap")
        check("held-out line and side kept", (j.get("sr_line"), j.get("sr_side") is not None), (5.5, True))
        check("Metcalf never priced in Sportradar's", (m.get("sr_state"), m.get("sr_line")), ("not priced", None))


if __name__ == "__main__":
    for fn in [test_identical_files_pass, test_pair_window, test_word_order_is_misnamed_and_stops,
               test_priced_qb_difference_stops, test_holdout_name_difference_stops,
               test_line_difference_counted_and_attributed, test_extra_book_is_book_mix,
               test_no_sims_is_unmeasured_not_pass, test_nickname_is_misnamed_not_absent, test_odds_only_book_is_book_mix,
               test_lag_tag, test_grade,
               test_sim_check_swaps_both_read_points, test_export_page_json, test_export_outside_window_or_empty,
               test_export_says_held_out_or_not_priced]:
        print(fn.__name__)
        fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


def test_gameday_minimum_for_s3_s4():
    """User, 2026-10-07: S3 and S4 cannot pass before MIN_GAMEDAY_PAIRS gameday pull pairs."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_pull(root, "20261004T150200Z", PLAYERS, PLAYERS)     # kickoff 17:00Z, 2 h later: a gameday pair
        _, v = run(root, min_gameday=6)
        check("S3 insufficient below the minimum", v["S3"], "INSUFFICIENT (passing so far; 1 of 6 gameday pull pairs)")
        check("S4 insufficient below the minimum", v["S4"], "INSUFFICIENT (passing so far; 1 of 6 gameday pull pairs)")
        check("S1 unaffected", v["S1"], "PASS")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_pull(root, "20261004T150200Z", PLAYERS, PLAYERS)
        early = json.loads((root / "pulls" / "20261004T150200Z" / "odds.json").read_text(encoding="utf-8"))
        early["games"][GID]["kickoff"] = "2026-10-06T17:00:00+00:00"          # two days out: not gameday
        (root / "pulls" / "20261004T150200Z" / "odds.json").write_text(json.dumps(early), encoding="utf-8")
        text, v = run(root, min_gameday=1)
        check("a midweek pull is not a gameday pair", v["S3"], "INSUFFICIENT (passing so far; 0 of 1 gameday pull pairs)")
        check("count shown in the report", "gameday pull pairs (a paired game kicks off within 3 h): 0" in text, True)


NL = chr(10)


def _manifest(root, game_id):
    (root / "manifest.csv").write_text(
        "run_utc,odds_pulled_at,minutes_after_odds,game_id,sr_event_id,result,players,book_lines,removed,"
        "live_dropped,consensus_dropped,unmapped_books,ambiguous,file" + NL
        + f"2026-10-04T15:02:00+00:00,{ODDS_AT},2,{game_id},,unmapped: {game_id}: 0 Sportradar events match,,,,,,,," + NL,
        encoding="utf-8")


def test_no_market_on_either_source_is_excluded_not_a_stop():
    """User ruling 2026-10-07: no Odds API lines and no Sportradar event -> excluded and reported."""
    other = "2026_04_MIN_NO"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_pull(root, "20261004T150200Z", PLAYERS, PLAYERS)
        odds = json.loads((root / "pulls" / "20261004T150200Z" / "odds.json").read_text(encoding="utf-8"))
        odds["games"][other] = {"home": "NO", "away": "MIN", "kickoff": "2026-10-04T17:00:00+00:00",
                                "players": {}, "pulled_at": ODDS_AT}
        (root / "pulls" / "20261004T150200Z" / "odds.json").write_text(json.dumps(odds), encoding="utf-8")
        _manifest(root, other)
        text, v = run(root)
        check("no market on either source: S2 passes", v["S2"], "PASS")
        check("and the game is reported as excluded", f"excluded (no market on either source): 2026-10-04T15:02:00+00:00 {other}" in text, True)
        odds["games"][other]["players"] = {"Some Player": {"player_pass_yds": {"draftkings": bk(200.5)}}}
        (root / "pulls" / "20261004T150200Z" / "odds.json").write_text(json.dumps(odds), encoding="utf-8")
        _, v = run(root)
        check("Odds API lines with no Sportradar event still stop", v["S2"], "STOP")


def test_did_not_play_is_not_an_s5_failure():
    """User ruling 2026-10-07 (Fant): no snap row that week while the team's snaps are posted -> not graded."""
    import pandas as pd

    saved = pc._snap_rows
    pc._snap_rows = lambda season: pd.DataFrame({"week": [4, 4], "team": ["NO", "NO"],
                                                 "player": ["Juwan Johnson", "Chris Olave"]})
    try:
        check("absent from posted snaps -> did not play", pc._did_not_play("2026_04_ATL_NO", "NO", "Noah Fant"), True)
        check("in the snaps -> played (a name failure stays a failure)",
              pc._did_not_play("2026_04_ATL_NO", "NO", "Juwan Johnson"), False)
        check("team-week not posted -> unknown, stays a failure",
              pc._did_not_play("2026_04_ATL_NO", "ATL", "Bijan Robinson"), False)
    finally:
        pc._snap_rows = saved
