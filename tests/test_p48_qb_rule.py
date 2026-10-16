"""Tests for P48's narrow QB rule (no-snap backup QBs carry no charge).

    python -m tests.test_p48_qb_rule

No network: snap data is hand-built in the shape nflverse's snap counts use.
"""

from __future__ import annotations

import sys

import pandas as pd

from src import config
from src.features import score_injuries, zero_unsnapped_backup_qbs
from src.ingest_injuries import qb_snap_context_from

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
    return pd.DataFrame(rows, columns=["player", "team", "position", "game_type", "offense_snaps"])


# CLE, week 4 (PIT @ CLE, 10/1): Watson starts; Taylen Green, the emergency
# third QB, has no snaps in either season and ESPN lists him out.
FRAMES = {
    2026: snaps([("Deshaun Watson", "CLE", "QB", "REG", 180), ("Shedeur Sanders", "CLE", "QB", "REG", 1),
                 ("Jacoby Brissett", "ARI", "QB", "REG", 240)]),
    2025: snaps([("Dillon Gabriel", "CLE", "QB", "REG", 372), ("Trey Lance", "LAC", "QB", "REG", 100)]),
}
CTX = qb_snap_context_from(FRAMES, 2026)


def qb(player, status="out", share=None, play_probability=0.0):
    return {"player": player, "position": "QB", "status": status, "snap_share": share,
            "play_probability": play_probability}


def charge(rows):
    return round(-score_injuries(rows, "nfl")[0], 2)


def test_context():
    check("the snap leader is the QB with the most snaps this season", CTX["leaders"], {"CLE": "Deshaun Watson",
                                                                                         "ARI": "Jacoby Brissett"})
    check("a player with last season's snaps on any team counts as snapped", "trey lance" in CTX["snapped"], True)
    check("a player with no snaps is not", "taylen green" in CTX["snapped"], False)


def test_no_snap_backup_is_zeroed():
    rows = [qb("Taylen Green")]
    check("before: the 0.35 default at full QB weight", charge(rows), 2.1)
    out, zeroed = zero_unsnapped_backup_qbs("CLE", rows, CTX)
    check("Green is zeroed", zeroed, ["Taylen Green"])
    check("and costs nothing", charge(out), 0.0)
    check("the input rows are not modified", rows[0]["snap_share"], None)


def test_slot_passes_to_the_next_qb():
    # With Green zeroed (a known 0.0, ranked last) the one QB slot goes to the
    # next QB on the report, priced on his own share.
    rows = [qb("Taylen Green"), qb("Shedeur Sanders", status="questionable", share=0.2, play_probability=0.55)]
    check("before: Green holds the slot (0.35 > 0.20)", charge(rows), 2.1)
    out, _ = zero_unsnapped_backup_qbs("CLE", rows, CTX)
    check("after: Sanders takes it, 1.0 x 0.20 x 0.45 x 6", charge(out), 0.54)


def test_leader_ruled_out_keeps_the_charge():
    for status in ("out", "doubtful", "ir", "inactive"):
        rows = [qb("Deshaun Watson", status=status, share=0.95), qb("Taylen Green")]
        out, zeroed = zero_unsnapped_backup_qbs("CLE", rows, CTX)
        check(f"leader {status}: nothing zeroed", (zeroed, out is rows), ([], True))
    rows = [qb("Deshaun Watson", status="questionable", share=0.95, play_probability=0.55), qb("Taylen Green")]
    check("leader questionable (not ruled out): Green still zeroed",
          zero_unsnapped_backup_qbs("CLE", rows, CTX)[1], ["Taylen Green"])


def test_qbs_with_snaps_on_record_are_untouched():
    rows = [qb("Dillon Gabriel", status="ir", share=0.562)]
    check("a prior-season share is kept (narrow rule, not M1)", zero_unsnapped_backup_qbs("CLE", rows, CTX)[1], [])
    rows = [qb("Trey Lance")]
    check("no share on this team, but snaps elsewhere last season: kept",
          zero_unsnapped_backup_qbs("CLE", rows, CTX)[1], [])
    rows = [{"player": "Taylen Green", "position": "WR", "status": "out", "snap_share": None}]
    check("not a QB: kept", zero_unsnapped_backup_qbs("CLE", rows, CTX)[1], [])


def test_rule_off():
    rows = [qb("Taylen Green")]
    check("no snap context: off", zero_unsnapped_backup_qbs("CLE", rows, {})[0] is rows, True)
    check("team with no 2026 leader: off", zero_unsnapped_backup_qbs("NYJ", rows, CTX)[0] is rows, True)
    config.QB_ZERO_SNAP_RULE = False
    try:
        check("QB_ZERO_SNAP_RULE=0: off", zero_unsnapped_backup_qbs("CLE", rows, CTX)[0] is rows, True)
    finally:
        config.QB_ZERO_SNAP_RULE = True


if __name__ == "__main__":
    for fn in [test_context, test_no_snap_backup_is_zeroed, test_slot_passes_to_the_next_qb,
               test_leader_ruled_out_keeps_the_charge, test_qbs_with_snaps_on_record_are_untouched, test_rule_off]:
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
