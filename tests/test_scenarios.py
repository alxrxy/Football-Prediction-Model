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


def test_publish_merges_and_retires():
    """A window refresh replaces its own games, drops one that no longer
    qualifies, keeps other windows' games, and drops kicked-off games."""
    import json
    import tempfile
    from datetime import datetime, timedelta, timezone
    from pathlib import Path

    future = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    prev = {"season": 2026, "week": 4, "games": {
        "OTHER_WINDOW": {"kickoff": future, "scenarios": []},
        "NOW_KNOWN": {"kickoff": future, "scenarios": []},
        "KICKED_OFF": {"kickoff": past, "scenarios": []}}}
    saved = (sc.OUT_JSON, sc.PUBLIC_JSON, sc.run_game, sc.db.get_store, sc.FeatureContext)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        sc.OUT_JSON, sc.PUBLIC_JSON = tmp / "s.json", tmp / "nope" / "s.json"
        sc.OUT_JSON.write_text(json.dumps(prev), encoding="utf-8")
        sc.run_game = lambda gid, *a, **k: {"kickoff": future, "scenarios": [1]} if gid == "STILL_OPEN" else None
        import src.simulate_nfl as sn
        saved_sn = (sn.load_inputs, sn.qb_check_inputs)
        sn.load_inputs = lambda season: None
        sn.qb_check_inputs = lambda store: None

        class Store:
            def select(self, *a, **k):
                return []

            def close(self):
                pass

        class Ctx:
            def __init__(self, *a, **k):
                self.games = [{"game_id": g, "season": 2026, "week": 4, "kickoff_time": future,
                               "home_team": "H", "away_team": "A"} for g in ("STILL_OPEN", "NOW_KNOWN")]
        sc.db.get_store, sc.FeatureContext = (lambda: Store()), Ctx
        import src.ingest_injuries as ii
        saved_iw = ii._infer_week
        ii._infer_week = lambda *a: 4
        saved_sm = sc.db.select_merged
        sc.db.select_merged = lambda *a, **k: []
        lines_path = sc.config.DATA_DIR / "props_lines.json"
        try:
            out = sc.run(publish=True, game_ids={"STILL_OPEN", "NOW_KNOWN"})
            got = json.loads(sc.OUT_JSON.read_text(encoding="utf-8"))
        finally:
            (sc.OUT_JSON, sc.PUBLIC_JSON, sc.run_game, sc.db.get_store, sc.FeatureContext) = saved
            sn.load_inputs, sn.qb_check_inputs = saved_sn
            ii._infer_week = saved_iw
            sc.db.select_merged = saved_sm
    check("merged games", sorted(got["games"]), ["OTHER_WINDOW", "STILL_OPEN"])
    check("summary names what qualified", "1 scenario(s)" in sc.summary({**out, "games": {
        "STILL_OPEN": {"away": "A", "home": "H", "scenarios": [1], "control": {"reproduces_served": True}}}}), True)


if __name__ == "__main__":
    for t in [v for k, v in dict(globals()).items() if k.startswith("test_")]:
        print(t.__name__)
        t()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


def test_label_names_the_qb_actually_simulated():
    """Display only (10/7): 'Daniels out (Mariota starts)' simulated Kaliakmanis, because Mariota is doubtful;
    the label must name the QB the simulation started and say why the named one did not."""
    from src.scenarios import actual_label

    got = actual_label("Jayden Daniels out (Marcus Mariota starts)", "Marcus Mariota", "doubtful", "Athan Kaliakmanis")
    check("names the simulated QB and why", got,
          "Jayden Daniels out (Athan Kaliakmanis starts in the simulation; Marcus Mariota is doubtful)")
    got = actual_label("Baker Mayfield out (Jalon Daniels starts, the books' QB)", "Jalon Daniels", "out", "Teddy Bridgewater")
    check("books' QB case relabelled too", got,
          "Baker Mayfield out (Teddy Bridgewater starts in the simulation; Jalon Daniels is out)")
    same = "Baker Mayfield out (Jalon Daniels starts, the books' QB)"
    check("unchanged when the named QB is simulated", actual_label(same, "Jalon Daniels", None, "Jalon Daniels"), same)
    check("unchanged when nothing is simulated", actual_label(same, "Jalon Daniels", None, None), same)


def test_relabel_stored_payload_without_sims():
    from src.scenarios import relabel

    payload = {"games": {"2026_05_NYG_WAS": {"scenarios": [
        {"team": "WAS", "label": "Jayden Daniels plays", "sim_qbs": {"WAS": {"player": "Jayden Daniels"}}},
        {"team": "WAS", "label": "Jayden Daniels out (Marcus Mariota starts)",
         "sim_qbs": {"WAS": {"player": "Athan Kaliakmanis"}}}]}}}
    n = relabel(payload, {("WAS", "Marcus Mariota"): "doubtful"})
    labels = [s["label"] for s in payload["games"]["2026_05_NYG_WAS"]["scenarios"]]
    check("one label changed", n, 1)
    check("stored labels", labels, ["Jayden Daniels plays",
          "Jayden Daniels out (Athan Kaliakmanis starts in the simulation; Marcus Mariota is doubtful)"])
