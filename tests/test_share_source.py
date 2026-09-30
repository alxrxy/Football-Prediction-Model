"""Tests for the P48 snap-share source labels (display only, no number changes).

    python -m tests.test_share_source
"""

from __future__ import annotations

import sys

import pandas as pd

from src import export_dashboard, features, ingest_injuries
from src.features import DEFAULT_SNAP_SHARE, score_injuries, share_source
from src.ingest_injuries import merge_snap_shares, player_key, share_sources

PASS, FAIL = 0, 0


def check(label: str, got, want) -> None:
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got {got!r}, want {want!r}")


def snaps(rows):
    return pd.DataFrame(rows, columns=["team", "player", "position", "offense_pct", "defense_pct"])


# 2026: Samuel plays; Porter has no 2026 snaps. 2025: both played.
CUR = snaps([("PIT", "Jamel Samuel", "CB", 0.0, 1.0), ("PIT", "Jamel Samuel", "CB", 0.0, 0.9)])
PRIOR = snaps([("PIT", "Joey Porter", "CB", 0.0, 0.946), ("PIT", "Jamel Samuel", "CB", 0.0, 0.40)])
SOURCES = share_sources({2026: CUR, 2025: PRIOR}, 2026)


def test_sources_match_the_charged_shares():
    merged = merge_snap_shares([CUR, PRIOR])
    check("same players as the share merge", set(SOURCES), set(merged))
    check("same share values as the share merge",
          {k: round(v[1], 9) for k, v in SOURCES.items()}, {k: round(v, 9) for k, v in merged.items()})
    check("current-season player is 'current'", SOURCES[player_key("PIT", "Jamel Samuel")][0], "current")
    check("no 2026 snaps -> 'prior'", SOURCES[player_key("PIT", "Joey Porter")][0], "prior")


def test_share_source_rules():
    check("None share -> default", share_source("PIT", "Nobody", None, SOURCES), "default")
    check("None share -> default even with no sources", share_source("PIT", "Nobody", None, {}), "default")
    check("suffix normalised (Porter Jr. -> prior)", share_source("PIT", "Joey Porter Jr.", 0.946, SOURCES), "prior")
    check("current", share_source("PIT", "Jamel Samuel", 0.95, SOURCES), "current")
    check("3-dp rounded breakdown share still matches", share_source("PIT", "Joey Porter Jr.", 0.9464, SOURCES), "prior")
    half_way = {player_key("LAC", "Trey Lance"): ("prior", 0.3775), player_key("GB", "Warren Brinson"): ("prior", 0.3725)}
    check("half-way rounding 0.3775 -> 0.378 matches", share_source("LAC", "Trey Lance", 0.378, half_way), "prior")
    check("half-way rounding 0.3725 -> 0.372 matches", share_source("GB", "Warren Brinson", 0.372, half_way), "prior")
    check("share differing from that season's -> unknown", share_source("PIT", "Joey Porter Jr.", 0.80, SOURCES), None)
    check("empty sources -> unknown, not guessed", share_source("PIT", "Joey Porter Jr.", 0.946, {}), None)
    check("breakdown default share, not in feed -> default",
          share_source("PIT", "Nobody", DEFAULT_SNAP_SHARE, SOURCES), "default")
    check("other share, not in feed -> unknown", share_source("PIT", "Nobody", 0.5, SOURCES), None)


def test_scoring_numbers_unchanged():
    rows = [
        {"player": "Joey Porter Jr.", "team": "PIT", "position": "CB", "status": "out", "snap_share": 0.946,
         "play_probability": 0.0},
        {"player": "Jamel Samuel", "team": "PIT", "position": "CB", "status": "questionable",
         "practice_trend": "limited", "snap_share": 0.95, "play_probability": 0.55},
        {"player": "Nobody", "team": "PIT", "position": "WR", "status": "out", "snap_share": None,
         "play_probability": 0.0},
    ]
    plain_pts, plain = score_injuries([dict(r) for r in rows], "nfl")
    tagged_rows = [dict(r, share_source=share_source("PIT", r["player"], r["snap_share"], SOURCES)) for r in rows]
    tagged_pts, tagged = score_injuries(tagged_rows, "nfl")
    check("penalty identical with tags", tagged_pts, plain_pts)
    check("breakdown identical apart from the tag",
          [{k: v for k, v in b.items() if k != "share_source"} for b in tagged],
          [{k: v for k, v in b.items() if k != "share_source"} for b in plain])
    check("breakdown carries the tag", {b["player"]: b["share_source"] for b in tagged},
          {"Joey Porter Jr.": "prior", "Jamel Samuel": "current", "Nobody": "default"})


def test_context_tags_rows():
    ctx = features.FeatureContext.__new__(features.FeatureContext)
    ctx.sport = "nfl"
    ctx.injuries = [{"player": "Joey Porter Jr.", "team": "PIT", "position": "CB", "status": "out",
                     "snap_share": 0.946, "play_probability": 0.0}]
    ctx.share_sources = SOURCES
    _, _, breakdown = ctx.injury_adjustment("PIT")
    check("injury_adjustment tags the breakdown", breakdown[0]["share_source"], "prior")
    check("stored rows not mutated", "share_source" in ctx.injuries[0], False)
    ctx.share_sources = {}
    _, _, breakdown = ctx.injury_adjustment("PIT")
    check("no sources -> unlabelled", breakdown[0]["share_source"], None)


def _game(home_items, away_items):
    return {"home": "PIT", "away": "CIN", "injuries": {"home": home_items, "away": away_items}}


def test_export_labels():
    tagged = _game([{"player": "Joey Porter Jr.", "snap_share": 0.946, "points": 0.72, "share_source": "prior"},
                    {"player": "Jamel Samuel", "snap_share": 0.95, "points": 0.3, "share_source": "current"}],
                   [{"player": "X", "snap_share": 0.35, "points": 0.2, "share_source": "default"}])

    real = ingest_injuries.snap_share_sources
    ingest_injuries.snap_share_sources = lambda season: (_ for _ in ()).throw(AssertionError("fetched"))
    try:
        export_dashboard.label_share_sources([tagged], 2026)
        check("all tagged -> no snap feed fetch", True, True)
    except AssertionError:
        check("all tagged -> no snap feed fetch", False, True)
    finally:
        ingest_injuries.snap_share_sources = real
    check("prior label", tagged["injuries"]["home"][0]["share_label"], "2025 share")
    check("current has no label", tagged["injuries"]["home"][1]["share_label"], None)
    check("default label", tagged["injuries"]["away"][0]["share_label"], "default share")
    check("game lists its prior-season charges", tagged["prior_season_shares"],
          [{"team": "PIT", "player": "Joey Porter Jr.", "points": 0.72}])

    old = _game([{"player": "Joey Porter Jr.", "snap_share": 0.946, "points": 0.72}], [])
    export_dashboard.label_share_sources([old], 2026, SOURCES)
    check("pre-P48 prediction falls back to the feed", old["injuries"]["home"][0]["share_source"], "prior")
    none = _game([{"player": "Joey Porter Jr.", "snap_share": 0.946, "points": 0.72}], [])
    export_dashboard.label_share_sources([none], 2026, {})
    check("feed unavailable -> unlabelled", (none["injuries"]["home"][0]["share_source"],
                                              none["injuries"]["home"][0]["share_label"], none["prior_season_shares"]),
          (None, None, []))


def test_feed_failure_gives_empty_map():
    import nfl_data_py as nfl

    real = nfl.import_snap_counts

    def fake(years):
        if years == [2025]:
            raise ConnectionError("down")
        return CUR

    nfl.import_snap_counts = fake
    try:
        check("one season failing -> empty map", ingest_injuries.snap_share_sources(2026), {})
    finally:
        nfl.import_snap_counts = real


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(name)
            fn()
    print(f"\n{PASS} passed, {FAIL} FAILED")
    sys.exit(1 if FAIL else 0)
