"""QB_STATUS_LABELS: a starting-QB label that stays true whichever way the official report goes.

    python -m pytest tests/test_qb_status_label.py

It states the simulation's QB split and the books' priced QB as of the refresh, then a fixed note; it never
claims a report has or hasn't posted. Display only. No network or database: stub sim row and lines.
"""

from __future__ import annotations

import json
import re

from src import export_dashboard as E

GAME_ID_RE = re.compile(r"^\d{4}_\d{2}_[A-Z]{2,3}_[A-Z]{2,3}$")


def _sim():
    box = {"away": {"players": [
               {"player": "Baker Mayfield", "passing": {"att": {"mean": 18.46}}},
               {"player": "Jalon Daniels", "passing": {"att": {"mean": 12.13}}},
               {"player": "Bucky Irving", "rushing": {"att": {"mean": 14.0}}}]},
           "home": {"players": [{"player": "Dak Prescott", "passing": {"att": {"mean": 32.5}}}]}}
    return {"game_id": "2026_05_TB_DAL", "home_team": "DAL", "away_team": "TB",
            "generated_at": "2026-10-07T08:14:55+00:00", "box_score": json.dumps(box)}


LINES = {"games": {"2026_05_TB_DAL": {"players": {
    "Jalon Daniels": {"player_pass_yds": {}, "player_rush_yds": {}},
    "Dak Prescott": {"player_pass_yds": {}},
    "CeeDee Lamb": {"player_reception_yds": {}}}}}}


def test_label_states_split_and_priced_qb():
    cfg = E.QB_STATUS_LABELS["2026_05_TB_DAL"]
    text = E.qb_status_label("2026_05_TB_DAL", "TB", cfg["note"], _sim(), LINES)
    assert "as of this refresh (simulation 2026-10-07 08:14Z)" in text
    assert "starts Baker Mayfield in about 60% and Jalon Daniels in about 40% of games" in text
    assert "the books price Jalon Daniels as TB's passer" in text          # DAL's Prescott is not counted
    assert text.endswith(cfg["note"])
    assert "hasn't posted" not in text and "has not posted" not in text


def test_label_degrades_without_data():
    text = E.qb_status_label("2026_05_TB_DAL", "TB", "NOTE.", None, None)
    assert "the simulation's starting-QB split is not available at this refresh" in text
    assert "the books price no TB quarterback yet" in text and text.endswith("NOTE.")


def test_label_entries_keyed_by_game():
    for gid, cfg in E.QB_STATUS_LABELS.items():
        assert GAME_ID_RE.match(gid) and cfg["team"] in gid.split("_")[2:]
        assert gid not in E.KNOWN_GAME_ISSUES          # one source of label per game
