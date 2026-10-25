"""Stale ESPN inactive-list detector (warn-only)."""

from __future__ import annotations

from src.stale_inactives import EARLY_MINUTES, MAX_NAMES, previous_lists, stale_reasons

K = lambda *names: [("TB", n) for n in names]  # noqa: E731


def test_early_read_is_flagged_and_t90_is_not():
    assert stale_reasons(K("a", "b"), EARLY_MINUTES + 10, None)[0].startswith("read 105 min")
    assert stale_reasons(K("a", "b"), 88, None) == []


def test_superset_of_previous_list_is_flagged_but_a_partial_repeat_is_not():
    prev = K("a", "b", "c")
    assert "superset" in stale_reasons(K("a", "b", "c"), 80, prev)[0]
    assert "superset" in stale_reasons(K("a", "b", "c", "d"), 80, prev)[0]
    assert stale_reasons(K("a", "b", "x"), 80, prev) == []
    assert stale_reasons(K("a"), 80, []) == []           # no previous list: nothing to compare


def test_too_many_names_is_flagged():
    names = K(*[str(i) for i in range(MAX_NAMES + 1)])
    assert any("more than" in r for r in stale_reasons(names, 60, None))
    assert stale_reasons(K(*[str(i) for i in range(MAX_NAMES)]), 60, None) == []


def test_empty_list_is_never_flagged():
    assert stale_reasons([], 300, K("a")) == []


def test_previous_lists_takes_each_teams_latest_earlier_week():
    rows = [{"team": "TB", "player": "A", "season": 2026, "week": 5},
            {"team": "TB", "player": "B", "season": 2026, "week": 6},
            {"team": "TB", "player": "C", "season": 2026, "week": 7},
            {"team": "CAR", "player": "D", "season": 2025, "week": 18}]
    got = previous_lists(rows, 2026, 7)
    assert got == {"TB": [("TB", "b")]}


def test_probe_replay_of_the_10_25_stale_tb_list():
    """TB's 10/25 ESPN list (read T-105 min) still named Baker Mayfield, who was active: flagged early."""
    tb = K("baker mayfield", "antoine winfield", "demonte capehart", "sean tucker", "billy schrauth",
           "luke haggard", "benjamin morrison")
    reasons = stale_reasons(tb, 105, None)
    assert reasons and reasons[0].startswith("read 105 min")
