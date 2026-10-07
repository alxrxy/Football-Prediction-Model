"""Hand-written holds are scoped to one game, so a player-name hold cannot reach a later week.

    python -m pytest tests/test_holdout_scope.py

`props.PROP_HOLDOUTS` is looked up by (game_id, books' name, market) and
`td_props.PLAYER_HOLDOUTS` by (game_id, books' name); `KNOWN_GAME_ISSUES` by
game_id. A key without a game id would hold that player in every week.
Added 2026-10-07, when the week-4 IND @ WAS / NYJ @ CHI entries were retired.
"""

from __future__ import annotations

import re

from src import export_dashboard, props, td_props

GAME_ID = re.compile(r"^\d{4}_\d{2}_[A-Z]{2,3}_[A-Z]{2,3}$")


def test_prop_holdouts_are_keyed_by_game():
    for key in props.PROP_HOLDOUTS:
        assert len(key) == 3 and GAME_ID.match(key[0]), key


def test_td_holdouts_are_keyed_by_game():
    for key in td_props.PLAYER_HOLDOUTS:
        assert len(key) == 2 and GAME_ID.match(key[0]), key


def test_known_game_issues_are_keyed_by_game():
    for key in export_dashboard.KNOWN_GAME_ISSUES:
        assert GAME_ID.match(key), key


def test_week4_entries_retired():
    assert not [k for k in props.PROP_HOLDOUTS if k[0].startswith("2026_04_")]
    assert not [k for k in td_props.PLAYER_HOLDOUTS if k[0].startswith("2026_04_")]
    assert not [k for k in export_dashboard.KNOWN_GAME_ISSUES if k.startswith("2026_04_")]
