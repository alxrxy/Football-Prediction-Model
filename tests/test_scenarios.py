"""Tests for P66 QB scenarios (comparison only).

    python -m tests.test_scenarios

Pins which scenarios a team gets from its signals (IND @ WAS and NYJ @ CHI as
served 2026-10-01), that a scenario edits only a copy of the injury list, that
the store is read-only, and what the control comparison may ignore.
"""

from __future__ import annotations

import sys

from src import scenarios as sc

PASS, FAIL = 0, 0


def check(label: str, got, want) -> None:
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got {got!r}, want {want!r}")


def inj(team, player, status, prob):
    return {"team": team, "player": player, "position": "QB", "status": status, "play_probability": prob,
            "snap_share": 0.9, "source": "espn"}


def test_was_questionable_starter_and_books_qb():
    """IND @ WAS: Daniels questionable, books price Mariota (the next QB): two
    scenarios, the 'out' one naming Mariota as the books' QB."""
    specs = sc.team_specs("WAS", ["Jayden Daniels", "Marcus Mariota"], [inj("WAS", "Jayden Daniels", "questionable", 0.55)],
                          {"qb1": "Jayden Daniels", "priced": "Marcus Mariota"}, [])
    check("labels", [s["label"] for s in specs],
          ["Jayden Daniels plays", "Jayden Daniels out (Marcus Mariota starts, the books' QB)"])
    check("changes", [s["changes"] for s in specs], [{"Jayden Daniels": 1.0}, {"Jayden Daniels": 0.0}])


def test_chi_doubtful_starter_and_third_qb():
    """NYJ @ CHI: Williams doubtful, sim starts Keenum, books price Bagent (QB3):
    three scenarios; Bagent's has Williams out and Bagent promoted."""
    specs = sc.team_specs("CHI", ["Caleb Williams", "Case Keenum", "Tyson Bagent"],
                          [inj("CHI", "Caleb Williams", "doubtful", 0.1)],
                          {"qb1": "Case Keenum", "priced": "Tyson Bagent"}, [])
    check("labels", [s["label"] for s in specs],
          ["Caleb Williams plays", "Caleb Williams out (Case Keenum starts)", "Tyson Bagent starts (the books' QB)"])
    check("Bagent scenario", (specs[2]["changes"], specs[2]["starter"]), ({"Caleb Williams": 0.0}, "Tyson Bagent"))


def test_healthy_team_gets_nothing():
    check("no signal, no scenario", sc.team_specs("KC", ["Patrick Mahomes"], [], None, []), [])


def test_books_qb_without_status_is_a_starter_swap_only():
    specs = sc.team_specs("NYJ", ["Geno Smith", "Tyrod Taylor"], [], {"qb1": "Geno Smith", "priced": "Tyrod Taylor"}, [])
    check("one scenario, no injury change", [(s["label"], s["changes"], s["starter"]) for s in specs],
          [("Tyrod Taylor starts (the books' QB)", {}, "Tyrod Taylor")])


def test_apply_edits_a_copy():
    base = [inj("CHI", "Caleb Williams", "doubtful", 0.1)]
    out = sc._apply(base, "CHI", {"Caleb Williams": 0.0})
    check("copy changed", (out[0]["play_probability"], out[0]["status"]), (0.0, "out"))
    check("original untouched", (base[0]["play_probability"], base[0]["status"]), (0.1, "doubtful"))
    out = sc._apply(base, "CHI", {"Caleb Williams": 1.0})
    check("plays: probability 1, no status", (out[0]["play_probability"], out[0]["status"]), (1.0, None))


def test_p53_warning_parsed():
    w = sc._warnings({"components": {"input_warnings": ["CHI: sim QB1 Case Keenum, but the books price Tyson Bagent",
                                                        "something else"]}})
    check("parsed", w, {"CHI": {"qb1": "Case Keenum", "priced": "Tyson Bagent"}})


def test_store_is_read_only():
    class Store:
        def select(self, *a, **k):
            return ["row"]

        def upsert(self, *a, **k):
            raise AssertionError("reached the real store")

    ro = sc.ReadOnlyStore(Store())
    check("reads pass", ro.select("x"), ["row"])
    try:
        ro.upsert("game_simulations", [])
        blocked = False
    except PermissionError:
        blocked = True
    check("writes raise", blocked, True)


def test_control_comparison():
    stored = {"generated_at": "a", "margin_50_high": 20, "box_score": '{"home": {"p": 1.0}}',
              "components": '{"anchor": {"model": "baseline-v1 @ x", "margin_home": 11.64}}',
              "td_scorers": '{"depth_chart_as_of": "t1", "rows": [1]}'}
    fresh = {"generated_at": "b", "margin_50_high": 20.0, "box_score": {"home": {"p": 1}},
             "components": {"anchor": {"model": "scenario", "margin_home": 11.64}},
             "td_scorers": {"depth_chart_as_of": "t2", "rows": [1]}, "_kickoff": "x"}
    check("stamps and 20 vs 20.0 ignored", sc._same_sim(fresh, stored), True)
    fresh["components"]["anchor"]["margin_home"] = 11.65
    check("a produced value differs", sc._same_sim(fresh, stored), False)


if __name__ == "__main__":
    for t in [v for k, v in dict(globals()).items() if k.startswith("test_")]:
        print(t.__name__)
        t()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
