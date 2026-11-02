"""Tests for the served-list archive: nothing reaches the page unarchived.

    python -m tests.test_served_archive

Each fixture test works in a temp folder. test_every_live_served_list_is_archived
reads the real served files: it fails if a props or TD list is being served
that the archive does not hold byte for byte.
"""

from __future__ import annotations

import copy
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

from src import p62_compare, props, served_archive as sa, td_props
from src import props_archive as pa

PASS, FAIL = 0, 0
GID = "2099_04_PIT_CLE"   # kickoff far ahead, so neither rank treats the game as started
ROWS = "2099_w04"


def check(label: str, got, want) -> None:
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got {got!r}, want {want!r}")


def served(generated_at="2099-10-01T03:47:05.123+00:00", **extra):
    return json.dumps({"generated_at": generated_at, "season": 2099, "week": 4, "lines_pulled_at": "x",
                       "props": [{"rank": 1, "game_id": GID}], "more": [{"rank": 26, "game_id": GID}],
                       "held_out": [], "started": [], **extra}).encode("utf-8")


def q(median):
    return {"p10": median * 0.5, "p25": median * 0.75, "median": median, "p75": median * 1.25, "p90": median * 1.5}


SIMS = {GID: {"margin": {"p50": 1}, "total": {"p50": 40}, "home_win_prob": 0.5, "market_total": 44.0,
              "generated_at": "2099-10-01T00:00:00+00:00",
              "box_score": {"home": {"players": [{"player": "Jerry Jeudy", "position": "WR", "anytime_td": 0.3,
                                                  "receiving": {"yds": q(40), "rec": q(3)}}]},
                            "away": {"players": [{"player": "DK Metcalf", "position": "WR", "anytime_td": 0.4,
                                                  "receiving": {"yds": q(70), "rec": q(5)}}]}}}}
PROP_LINES = {"pulled_at": "2099-10-01T00:00:00+00:00", "season": 2099, "week": 4, "markets": [],
              "games": {GID: {"home": "CLE", "away": "PIT", "kickoff": "2099-10-04T17:00:00+00:00",
                              "pulled_at": "2099-10-01T00:00:00+00:00",
                              "players": {"DK Metcalf": {"player_reception_yds": {"draftkings": {"point": 55.5, "over": -110, "under": -110}}},
                                          "Jerry Jeudy": {"player_reception_yds": {"draftkings": {"point": 45.5, "over": -110, "under": -110}}}}}}}
TD_LINES = {"pulled_at": "2099-10-01T00:00:00+00:00", "season": 2099, "week": 4,
            "games": {GID: {"home": "CLE", "away": "PIT", "kickoff": "2099-10-04T17:00:00+00:00",
                            "players": {"DK Metcalf": {"draftkings": {"yes": 150, "no": -190}},
                                        "Jerry Jeudy": {"draftkings": {"yes": 200, "no": -250}}}}}}


def test_exact_bytes_read_only_and_index():
    with tempfile.TemporaryDirectory() as tmp:
        out, b, lines = Path(tmp), served(), b'{"games": {}}'
        path = sa.archive("td", b, lines, commit="abc1234", out=out)
        check("stored by kind, week and stamp", path.relative_to(out).as_posix(), f"td/{ROWS}/20991001T034705Z.json")
        check("exact served bytes", path.read_bytes(), b)
        check("read-only on disk", bool(path.stat().st_mode & stat.S_IWRITE), False)
        r = sa.index_rows(out)[0]
        check("index row", (r["kind"], r["week"], r["git_commit"], r["origin"], r["rows"], r["games"]),
              ("td", "4", "abc1234", "live", "2", GID))
        check("archive time recorded", bool(r["archived_at"]), True)
        check("raw lines kept with it", (out / "lines" / f"{r['lines_sha256'][:12]}.json").read_bytes(), lines)
        check("model-only rows counted", sa._summary(json.loads(served(model_only=[{"game_id": "g2"}])))["rows"], 3)
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)


def test_immutable_and_tamper_evident():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        path = sa.archive("props", served(), out=out, commit="c")
        check("same bytes again stores nothing new",
              (sa.archive("props", served(), out=out, commit="c"), len(sa.index_rows(out))), (path, 1))
        other = sa.archive("props", served(rev=2), out=out, commit="c")
        check("same stamp, new bytes gets a suffix", other.name, "20991001T034705Z_2.json")
        check("first file untouched", path.read_bytes(), served())
        try:
            path.write_bytes(b"edited")
            refused = False
        except PermissionError:
            refused = True
        check("a plain overwrite is refused", refused, True)
        check("clean archive verifies", sa.verify(out), [])
        for f in (path, other):
            os.chmod(f, stat.S_IWRITE | stat.S_IREAD)
        path.write_bytes(b"edited")
        other.unlink()
        check("an edit and a removal are both reported", len(sa.verify(out)), 2)


def test_unarchived_catches_a_served_list_not_in_the_archive():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        out, file = root / "archive", root / "td_props.json"
        file.write_bytes(served())
        check("unarchived list is caught", sa.unarchived({"td": [file]}, out), [file])
        sa.archive("td", served(), out=out, commit="c")
        check("archived list passes", sa.unarchived({"td": [file]}, out), [])
        check("a different kind does not count", sa.unarchived({"props": [file]}, out), [file])
        file.write_bytes(served(rev=2))
        check("a list changed after archiving is caught", sa.unarchived({"td": [file]}, out), [file])


def _redirect_props(tmp: Path):
    saved = (props.PROPS_LINES_JSON, props.PROPS_JSON, props.PUBLIC_PROPS_JSON, props._sims, pa.ARCHIVE_DIR,
             sa.ARCHIVE_DIR, pa.archive, p62_compare.export)
    (tmp / "public").mkdir(exist_ok=True)
    props.PROPS_LINES_JSON = tmp / "props_lines.json"
    props.PROPS_LINES_JSON.write_text(json.dumps(PROP_LINES), encoding="utf-8")
    props.PROPS_JSON, props.PUBLIC_PROPS_JSON = tmp / "props.json", tmp / "public" / "props.json"
    props._sims = lambda: copy.deepcopy(SIMS)
    sa.ARCHIVE_DIR = tmp / "served"
    real = pa.archive
    pa.archive = lambda s, l, **k: real(s, l, commit="test", out=tmp / "p67")
    p62_compare.export = lambda *a, **k: {"verdict": {}}
    return saved


def _restore_props(saved) -> None:
    (props.PROPS_LINES_JSON, props.PROPS_JSON, props.PUBLIC_PROPS_JSON, props._sims, pa.ARCHIVE_DIR,
     sa.ARCHIVE_DIR, pa.archive, p62_compare.export) = saved


def test_props_run_archives_before_serving():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        saved = _redirect_props(tmp)
        try:
            props.run(with_explanations=False)
            kept = list((tmp / "served" / "props" / ROWS).glob("*.json"))
            check("one archived list", len(kept), 1)
            check("archive == served props.json", kept[0].read_bytes() if kept else None, props.PROPS_JSON.read_bytes())
            check("archive == public props.json", kept[0].read_bytes() if kept else None, props.PUBLIC_PROPS_JSON.read_bytes())
            check("nothing unarchived", sa.unarchived({"props": [props.PROPS_JSON, props.PUBLIC_PROPS_JSON]}, tmp / "served"), [])
            before = props.PROPS_JSON.read_bytes(), props.PUBLIC_PROPS_JSON.read_bytes()

            def broken(*a, **k):
                raise OSError("disk full")

            real, sa.archive = sa.archive, broken
            try:
                props.run(with_explanations=False)
                raised = False
            except OSError:
                raised = True
            finally:
                sa.archive = real
            check("archive failure stops the refresh", raised, True)
            check("archive failure: last archived list stays served",
                  (props.PROPS_JSON.read_bytes(), props.PUBLIC_PROPS_JSON.read_bytes()), before)
        finally:
            _restore_props(saved)


def _redirect_td(tmp: Path):
    saved = (td_props.TD_LINES_JSON, td_props.TD_PROPS_JSON, td_props.PUBLIC_TD_PROPS_JSON, td_props._sims,
             td_props._upcoming_week, td_props.model_only, sa.ARCHIVE_DIR)
    (tmp / "public").mkdir(exist_ok=True)
    td_props.TD_LINES_JSON = tmp / "td_lines.json"
    td_props.TD_LINES_JSON.write_text(json.dumps(TD_LINES), encoding="utf-8")
    td_props.TD_PROPS_JSON, td_props.PUBLIC_TD_PROPS_JSON = tmp / "td.json", tmp / "public" / "td.json"
    td_props._sims = lambda: copy.deepcopy(SIMS)
    td_props._upcoming_week = lambda: (2099, 4)
    sa.ARCHIVE_DIR = tmp / "served"
    return saved


def _restore_td(saved) -> None:
    (td_props.TD_LINES_JSON, td_props.TD_PROPS_JSON, td_props.PUBLIC_TD_PROPS_JSON, td_props._sims,
     td_props._upcoming_week, td_props.model_only, sa.ARCHIVE_DIR) = saved


def test_td_run_archives_ranked_and_model_only_lists():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        saved = _redirect_td(tmp)
        try:
            td_props.run()
            td_props.publish()
            kept = sorted((tmp / "served" / "td" / ROWS).glob("*.json"))
            check("ranked list archived", len(kept), 1)
            check("archive == served == public", {kept[0].read_bytes(), td_props.TD_PROPS_JSON.read_bytes(),
                                                  td_props.PUBLIC_TD_PROPS_JSON.read_bytes()}.__len__(), 1)
            row = sa.index_rows(tmp / "served")[0]
            check("raw TD lines kept beside the list",
                  (tmp / "served" / "lines" / f"{row['lines_sha256'][:12]}.json").read_bytes(), td_props.TD_LINES_JSON.read_bytes())

            td_props._upcoming_week = lambda: (2099, 5)   # lines file is week 4: the model-only branch
            td_props.model_only = lambda s, w, sims: {"generated_at": "2099-10-08T00:00:00+00:00", "season": s, "week": w,
                                                      "games_covered": 1, "model_only": [{"game_id": "2099_05_A_B"}]}
            td_props.run()
            check("model-only list archived too", td_props.TD_PROPS_JSON.read_bytes(),
                  next((tmp / "served" / "td" / "2099_w05").glob("*.json")).read_bytes())
            check("model-only row keeps no lines file", sa.index_rows(tmp / "served")[-1]["lines_sha256"], "")
            before = td_props.TD_PROPS_JSON.read_bytes()
            td_props._upcoming_week = lambda: (2099, 4)

            def broken(*a, **k):
                raise OSError("disk full")

            real, sa.archive = sa.archive, broken
            try:
                td_props.run()
                raised = False
            except OSError:
                raised = True
            finally:
                sa.archive = real
            check("archive failure stops the TD refresh", (raised, td_props.TD_PROPS_JSON.read_bytes()), (True, before))
        finally:
            _restore_td(saved)


def test_td_note_is_weeks_4_to_8_and_stays_experimental():
    page = (td_props.config.ROOT / "dashboard" / "src" / "TdPropsPage.jsx").read_text(encoding="utf-8")
    check("note keeps its label", td_props.NOTE.startswith("Experimental."), True)
    check("note has the weeks 4-8 band", ("36.3%" in td_props.NOTE, "28.8" in td_props.NOTE), (True, False))
    check("page banner has the weeks 4-8 band", ("36.3%" in page, "28.8" in page), (True, False))
    check("market sentence has the report-card sample", ("454 priced players in 24 games" in td_props.NOTE,
                                                         "454 priced players in 24 games" in page, "0.183" in page), (True, True, False))


def test_props_tab_label():
    page = (props.config.ROOT / "dashboard" / "src" / "PropsPage.jsx").read_text(encoding="utf-8")
    check("label on the Props tab",
          "Weeks 4-8: served picks 48.3%, -7.7% ROI; kept picks 52.6%, break-even; ranking within the list not validated." in page, True)


def test_every_live_served_list_is_archived():
    check("every served list is in the archive", sa.unarchived(), [])
    check("every archived list still matches its hash", sa.verify(), [])


if __name__ == "__main__":
    for fn in [test_exact_bytes_read_only_and_index, test_immutable_and_tamper_evident,
               test_unarchived_catches_a_served_list_not_in_the_archive, test_props_run_archives_before_serving,
               test_td_run_archives_ranked_and_model_only_lists, test_td_note_is_weeks_4_to_8_and_stays_experimental,
               test_props_tab_label, test_every_live_served_list_is_archived]:
        print(fn.__name__)
        fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
