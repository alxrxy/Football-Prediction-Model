"""Tests for the P67 archive of served props rankings (phase A, A1-A3, A5).

    python -m tests.test_props_archive

Each test works in a temp folder: the archive keeps the exact served bytes,
never overwrites, keeps each lines file once, and props.run's served files
are the same whether the archive works or fails.
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

from src import p62_compare, props
from src import props_archive as pa

PASS, FAIL = 0, 0
GID = "2099_04_PIT_CLE"   # kickoff far ahead, so rank() never treats the game as started


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


SIMS = {GID: {"margin": {"p50": 1}, "total": {"p50": 40}, "home_win_prob": 0.5, "generated_at": "2099-10-01T00:00:00+00:00",
              "box_score": {"home": {"players": [{"player": "Jerry Jeudy", "position": "WR",
                                                  "receiving": {"yds": q(40), "rec": q(3)}}]},
                            "away": {"players": [{"player": "Aaron Rodgers", "position": "QB", "passing": {"yds": q(200)}},
                                                 {"player": "DK Metcalf", "position": "WR",
                                                  "receiving": {"yds": q(70), "rec": q(5)}}]}}}}


def bk(point):
    return {"point": point, "over": -110, "under": -110}


LINES = {"pulled_at": "2099-10-01T00:00:00+00:00", "season": 2099, "week": 4, "markets": [],
         "games": {GID: {"home": "CLE", "away": "PIT", "kickoff": "2099-10-04T17:00:00+00:00",
                         "pulled_at": "2099-10-01T00:00:00+00:00",
                         "players": {"Aaron Rodgers": {"player_pass_yds": {"draftkings": bk(212.5)}},
                                     "DK Metcalf": {"player_reception_yds": {"draftkings": bk(55.5)}},
                                     "Jerry Jeudy": {"player_reception_yds": {"draftkings": bk(45.5)}}}}}}


def served(generated_at="2099-10-01T03:47:05.123+00:00", week=4):
    return json.dumps({"generated_at": generated_at, "season": 2099, "week": week, "lines_pulled_at": "x",
                       "props": [{"rank": 1}], "more": [{"rank": 26}], "held_out": [], "started": []}).encode("utf-8")


def test_exact_bytes_and_index():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        b, lines = served(), json.dumps(LINES).encode("utf-8")
        path = pa.archive(b, lines, commit="abc1234", out=out)
        check("stored under season_week/stamp", path.relative_to(out).as_posix(), "2099_w04/20991001T034705Z.json")
        check("exact served bytes", path.read_bytes(), b)
        rows = pa.index_rows(out)
        check("one index row", len(rows), 1)
        r = rows[0]
        check("index fields", (r["week"], r["git_commit"], r["line_source"], r["origin"], r["top"], r["more"]),
              ("4", "abc1234", "odds_api", "live", "1", "1"))
        check("served sha recorded", r["served_sha256"], pa._sha(b))
        check("lines kept by sha", (out / "lines" / f"{pa._sha(lines)[:12]}.json").read_bytes(), lines)


def test_append_only_and_lines_once():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        lines = json.dumps(LINES).encode("utf-8")
        first = pa.archive(served(), lines, commit="c", out=out)
        second = pa.archive(served(), lines, commit="c", out=out)   # same stamp
        check("collision gets a suffix", second.name, "20991001T034705Z_2.json")
        check("first file untouched", first.read_bytes(), served())
        check("lines file kept once", len(list((out / "lines").glob("*.json"))), 1)
        check("two index rows", len(pa.index_rows(out)), 2)


def test_seed_from_p62():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        pulls, out = root / "pulls", root / "archive"
        for stamp, gen, week in (("20990930T030000Z", "2099-09-30T03:01:00+00:00", 3),
                                 ("20991001T034505Z", "2099-10-01T03:47:05+00:00", 4)):
            d = pulls / stamp / f"rank_{stamp}"
            d.mkdir(parents=True)
            (d / "props.json").write_bytes(served(gen, week))
            (pulls / stamp / "odds.json").write_bytes(b'{"games": {}}')
        now = root / "props.json"
        now.write_bytes(served("2099-10-01T03:47:05+00:00", 4))
        notes = pa.seed_from_p62(pulls, now, out)
        rows = pa.index_rows(out)
        check("week 3 left out, week 4 seeded", [(r["week"], r["origin"]) for r in rows], [("4", "p62_shadow")])
        check("re-serialisation checked and reported", any("re-serialises byte-identically" in n for n in notes), True)
        check("newest compared with served", any("== served props.json" in n for n in notes), True)
        again = pa.seed_from_p62(pulls, now, out)
        check("re-seeding skips what is archived", (len(pa.index_rows(out)), any("already archived" in n for n in again)),
              (1, True))


def _run_props(tmp: Path, archive_fn=None):
    """props.run on fixture lines and sims, every path redirected into tmp."""
    saved = (props.PROPS_LINES_JSON, props.PROPS_JSON, props.PUBLIC_PROPS_JSON, props._sims, pa.ARCHIVE_DIR,
             pa.archive, p62_compare.export)
    (tmp / "public").mkdir(exist_ok=True)
    props.PROPS_LINES_JSON = tmp / "props_lines.json"
    props.PROPS_LINES_JSON.write_text(json.dumps(LINES), encoding="utf-8")
    props.PROPS_JSON, props.PUBLIC_PROPS_JSON = tmp / "props.json", tmp / "public" / "props.json"
    props._sims = lambda: copy.deepcopy(SIMS)
    real_archive = pa.archive
    pa.archive = archive_fn or (lambda s, l, **k: real_archive(s, l, commit="test", out=tmp / "archive"))
    p62_compare.export = lambda *a, **k: {"verdict": {}}   # keep the real page file out of the test
    try:
        props.run(with_explanations=False)
    finally:
        (props.PROPS_LINES_JSON, props.PROPS_JSON, props.PUBLIC_PROPS_JSON, props._sims, pa.ARCHIVE_DIR,
         pa.archive, p62_compare.export) = saved
    return tmp / "props.json", tmp / "public" / "props.json"


def _same_but_time(a: bytes, b: bytes) -> bool:
    x, y = json.loads(a), json.loads(b)
    x.pop("generated_at"), y.pop("generated_at")
    return x == y


def test_props_run_archives_what_it_serves():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        served_file, public = _run_props(tmp)
        kept = list((tmp / "archive").glob("2099_w04/*.json"))
        check("one archive file", len(kept), 1)
        check("archive bytes == props.json bytes", kept[0].read_bytes() if kept else None, served_file.read_bytes())
        check("lines it ranked kept", (tmp / "archive" / "lines" / f"{pa._sha((tmp / 'props_lines.json').read_bytes())[:12]}.json").exists(), True)

        def broken(*a, **k):
            raise OSError("disk full")

        tmp2 = tmp / "failing"
        tmp2.mkdir()
        served2, public2 = _run_props(tmp2, archive_fn=broken)
        check("archive failure: ranking still served", served2.exists() and public2.exists(), True)
        check("archive failure: public copy identical", served2.read_bytes(), public2.read_bytes())
        check("served content identical with archive on or failing (bar generated_at)",
              _same_but_time(served_file.read_bytes(), served2.read_bytes()), True)


if __name__ == "__main__":
    for fn in [test_exact_bytes_and_index, test_append_only_and_lines_once, test_seed_from_p62,
               test_props_run_archives_what_it_serves]:
        print(fn.__name__)
        fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
