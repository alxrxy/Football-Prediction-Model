"""P49: a pregame inactive flag on a QB the final injury report doesn't rule out
is held, not applied, unless he may be the starter and the books don't back him.

    python -m pytest tests/test_qb_hold.py

ESPN's pregame `didNotPlay` carries last week's inactives forward, so week 3 of
2026 benched Darnold (SEA) and Murray (MIN) in the sim, and TNF benched Penix.
The cases below are those players and the week-2/3 replay's edge cases. No
network or database: hand-built rows and a hand-built QB context.
"""

from __future__ import annotations

import pytest

from src import config
from src.features import apply_inactives

PULLED = "2026-09-27T15:45:00+00:00"


def _rep(player, team, status, prob, position="QB", snap=0.9):
    return {"player": player, "team": team, "sport": "nfl", "season": 2026, "week": 3, "position": position,
            "status": status, "play_probability": prob, "snap_share": snap, "source": "nflverse",
            "pulled_at": "2026-09-26T20:00:00+00:00"}


def _flag(player, team, game, position="QB"):
    return {"game_id": game, "team": team, "player": player, "sport": "nfl", "season": 2026, "week": 3,
            "position": position, "snap_share": None, "source": "espn_inactives", "pulled_at": PULLED}


# Depth order as nflverse publishes it; books-priced passers per game; snap leaders.
QB = {
    "depth": {
        "SEA": ["Sam Darnold", "Drew Lock", "Jalen Milroe"],
        "WAS": ["Marcus Mariota", "Jayden Daniels"],
        "MIN": ["J.J. McCarthy", "Kyler Murray", "Carson Wentz"],
        "TB": ["Baker Mayfield", "Teddy Bridgewater", "Jalon Daniels"],
        "ATL": ["Michael Penix Jr.", "Tua Tagovailoa", "Cooper Rush"],
        "GB": ["Jordan Love", "Tyrod Taylor"],
        "KC": ["Patrick Mahomes", "Justin Fields"],
        "BUF": ["Josh Allen", "Mitchell Trubisky"],
    },
    "priced": {
        "SEA_WAS": {"Sam Darnold", "Marcus Mariota"},
        "MIN_TB": {"Kyler Murray", "Baker Mayfield"},
        "ATL_GB": {"Michael Penix Jr.", "Jordan Love"},
        "KC_BUF": {"Justin Fields", "Josh Allen"},     # the books have moved to the backup
        "CAR_ATL": {"Bryce Young"},                    # no ATL QB priced (week 2)
    },
    "leaders": {"ATL": "Cooper Rush"},
}


@pytest.fixture(autouse=True)
def _rule_on(monkeypatch):
    monkeypatch.setattr(config, "INACTIVES_QB_HOLD", True)


# The report sets the current week; a real one is never empty.
FILLER = _rep("Some Lineman", "NYG", "questionable", 0.55, position="G")


def _run(report, flags):
    holds: list[dict] = []
    out = {(r["team"], r["player"]): r for r in apply_inactives([FILLER, *report], flags, qb=QB, holds=holds)}
    return out, {h["player"]: h for h in holds}


def test_false_starter_flags_are_held():
    """Darnold and Murray (week 3) and Penix (TNF): flagged, off the final
    report, priced by the books, and they played."""
    report = [_rep("Mayfield Neighbor", "TB", "questionable", 0.55, position="WR")]
    flags = [_flag("Sam Darnold", "SEA", "SEA_WAS"), _flag("Kyler Murray", "MIN", "MIN_TB"),
             _flag("Michael Penix Jr.", "ATL", "ATL_GB")]
    out, holds = _run(report, flags)
    for team, player in (("SEA", "Sam Darnold"), ("MIN", "Kyler Murray"), ("ATL", "Michael Penix Jr.")):
        assert (team, player) not in out, f"{player} must not be added as inactive"
        assert holds[player]["decision"] == "hold"
        assert "books price him" in holds[player]["reason"]


def test_ruled_out_qb_is_applied():
    report = [_rep("Jayden Daniels", "WAS", "out", 0.0)]
    out, holds = _run(report, [_flag("Jayden Daniels", "WAS", "SEA_WAS")])
    assert out[("WAS", "Jayden Daniels")]["play_probability"] == 0.0
    assert "Jayden Daniels" not in holds


def test_healthy_backup_is_held_and_logged():
    out, holds = _run([], [_flag("Jalon Daniels", "TB", "MIN_TB")])
    assert ("TB", "Jalon Daniels") not in out
    assert holds["Jalon Daniels"]["decision"] == "hold"
    assert holds["Jalon Daniels"]["reason"].startswith("backup")


def test_non_qb_flags_are_untouched():
    report = [_rep("Brock Bowers", "LV", None, 1.0, position="TE")]
    out, holds = _run(report, [_flag("Brock Bowers", "LV", "LV_NO", position="TE")])
    assert out[("LV", "Brock Bowers")]["play_probability"] == 0.0
    assert holds == {}


def test_late_scratch_starter_is_unresolved_not_held():
    """Criterion 9: a starter flagged inactive, off the report, with the books
    pricing his backup, stays applied and is reported for review."""
    out, holds = _run([], [_flag("Patrick Mahomes", "KC", "KC_BUF")])
    assert out[("KC", "Patrick Mahomes")]["play_probability"] == 0.0
    assert holds["Patrick Mahomes"]["decision"] == "unresolved"
    assert "Justin Fields" in holds["Patrick Mahomes"]["reason"]


def test_starter_with_no_price_is_unresolved():
    """Penix, week 2: on PUP (so off the weekly report), top of the chart, and
    the books priced no ATL QB. The flag was right and must stand."""
    out, holds = _run([], [_flag("Michael Penix Jr.", "ATL", "CAR_ATL")])
    assert out[("ATL", "Michael Penix Jr.")]["play_probability"] == 0.0
    assert holds["Michael Penix Jr."]["decision"] == "unresolved"


def test_snap_leader_below_the_starter_is_unresolved():
    """Cooper Rush, week 3: ATL's weeks 1-2 starter, a genuine inactive once
    Penix returned. A snap leader is cross-checked, never held as a backup."""
    out, holds = _run([], [_flag("Cooper Rush", "ATL", "ATL_GB")])
    assert out[("ATL", "Cooper Rush")]["play_probability"] == 0.0
    assert holds["Cooper Rush"]["decision"] == "unresolved"


def test_starter_ruled_out_passes_the_start_to_the_next_man():
    """With the depth-chart QB1 out on the report, the next QB is the projected
    starter and is cross-checked, not held as a backup."""
    report = [_rep("Josh Allen", "BUF", "out", 0.0)]
    out, holds = _run(report, [_flag("Mitchell Trubisky", "BUF", "KC_BUF")])
    assert holds["Mitchell Trubisky"]["decision"] == "unresolved"
    assert out[("BUF", "Mitchell Trubisky")]["play_probability"] == 0.0


def test_no_depth_chart_falls_back_to_the_books():
    qb = {**QB, "depth": None, "leaders": {}}
    holds: list[dict] = []
    out = {(r["team"], r["player"]): r for r in apply_inactives(
        [FILLER], [_flag("Sam Darnold", "SEA", "SEA_WAS"), _flag("Drew Lock", "SEA", "SEA_WAS")], qb=qb, holds=holds)}
    by = {h["player"]: h["decision"] for h in holds}
    assert by == {"Sam Darnold": "hold", "Drew Lock": "unresolved"}
    assert ("SEA", "Drew Lock") in out and ("SEA", "Sam Darnold") not in out


def test_flag_off_applies_everything(monkeypatch):
    monkeypatch.setattr(config, "INACTIVES_QB_HOLD", False)
    out, holds = _run([], [_flag("Sam Darnold", "SEA", "SEA_WAS")])
    assert out[("SEA", "Sam Darnold")]["play_probability"] == 0.0
    assert holds == {}
