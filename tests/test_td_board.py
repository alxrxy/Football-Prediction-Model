"""TD board (experimental display): ordering, edge, and that every simulated player is listed."""

from __future__ import annotations

from datetime import datetime, timezone

from src import td_board


def test_edge_needs_a_market_price():
    assert td_board.edge(0.40, 0.30) == 0.10
    assert td_board.edge(0.40, None) is None
    assert td_board.edge(None, 0.30) is None


def test_sort_orders_and_unpriced_last_on_edge():
    rows = [{"player": "a", "p_one": 0.5, "p_two": 0.05, "edge": None},
            {"player": "b", "p_one": 0.3, "p_two": 0.20, "edge": -0.02},
            {"player": "c", "p_one": 0.4, "p_two": 0.10, "edge": 0.07}]
    assert [r["player"] for r in td_board.sort_rows(rows, "one")] == ["a", "c", "b"]
    assert [r["player"] for r in td_board.sort_rows(rows, "two")] == ["b", "c", "a"]
    assert [r["player"] for r in td_board.sort_rows(rows, "edge")] == ["c", "b", "a"]   # no price sorts last, not as 0


def test_implied_points_split_the_total_by_the_spread():
    assert td_board.implied_points(-3, 45, home=True) == 24.0
    assert td_board.implied_points(-3, 45, home=False) == 21.0
    assert td_board.implied_points(None, 45, home=True) is None


class _Store:
    def __init__(self, games, sims, injuries):
        self.t = {"games": games, "game_simulations": sims, "injuries": injuries}
        self.backend = "sqlite"

    def select(self, table, where=None):
        rows = self.t.get(table, [])
        return [r for r in rows if all(r.get(k) == v for k, v in (where or {}).items())]

    def close(self):
        pass


def _fixture():
    games = [{"game_id": "2026_11_AAA_BBB", "sport": "nfl", "season": 2026, "week": 11, "away_team": "AAA",
              "home_team": "BBB", "kickoff_time": "2026-11-22T18:00:00+00:00", "completed": False}]
    scorers = lambda names: [{"player": n, "position": "RB", "anytime_td": p, "two_plus_td": q, "expected_tds": p + q,  # noqa: E731
                              "depth_rank": i + 1, "rz_target_share": 0.1, "rz_carry_share": 0.5, "gl_carry_share": 0.6}
                             for i, (n, p, q) in enumerate(names)]
    sims = [{"game_id": "2026_11_AAA_BBB", "market_spread": -3, "market_total": 45, "sim_margin_home": 3.0,
             "mean_home_points": 24.0, "mean_away_points": 21.0, "home_td_mean": 2.8, "away_td_mean": 2.4,
             "home_win_prob": 0.6, "generated_at": "2026-11-19T20:00:00+00:00", "box_score": {},
             "td_scorers": {"away": scorers([("Al One", 0.45, 0.10), ("Al Two", 0.20, 0.02)]),
                            "home": scorers([("Bo One", 0.55, 0.15), ("Bo Two", 0.10, 0.01)]),
                            "injury_shifts": {"BBB": [{"to": "Bo One", "player": "Bo Hurt", "status": "out", "position": "RB1",
                                                       "play_prob": 0.0, "moved_carry_share": 0.3, "moved_target_share": 0.05}]}}}]
    facts = {"teams": {}, "allowed": {}, "counts": {}, "team_tot": {}, "tds": {}, "player_games": {}, "id_by_key": {},
             "through_week": 10}
    td_list = {"props": [{"game_id": "2026_11_AAA_BBB", "team": "BBB", "player": "Bo One", "p_market": 0.50,
                          "yes_price": -110, "books": 5}], "more": [], "held_out": []}
    return _Store(games, sims, []), facts, td_list


def test_every_simulated_player_is_listed_with_both_probabilities_and_labels():
    store, facts, td_list = _fixture()
    doc = td_board.build(2026, 11, now=datetime(2026, 11, 19, 21, 0, tzinfo=timezone.utc), store=store, facts=facts,
                         td_list=td_list)
    assert doc["counts"] == {"players": 4, "priced": 1, "games": 1}
    assert [p["player"] for p in doc["players"]] == ["Bo One", "Al One", "Al Two", "Bo Two"]      # default: 1+ TD
    assert all(p["p_one"] is not None and p["p_two"] is not None for p in doc["players"])
    bo = doc["players"][0]
    assert bo["edge"] == 0.05 and bo["explain"]["role_injuries"][0]["from"] == "Bo Hurt"
    assert bo["explain"]["game_script"]["implied_points"] == 24.0
    assert doc["players"][1]["edge"] is None                                                       # no price, no edge
    assert "EXPERIMENTAL" in doc["label"] and "UNVALIDATED" in doc["label"] and "EXPERIMENTAL" in doc["two_plus_note"]


def test_a_started_game_is_marked_started():
    store, facts, td_list = _fixture()
    doc = td_board.build(2026, 11, now=datetime(2026, 11, 22, 19, 0, tzinfo=timezone.utc), store=store, facts=facts,
                         td_list=td_list)
    assert all(p["started"] for p in doc["players"])


def test_build_on_the_sqlite_backend_decodes_json_columns(tmp_path):
    """SQLite hands JSON columns back as text (Supabase returns objects). The board must read both:
    `python -m src.td_board` crashed on the default backend with "'str' object has no attribute 'get'"."""
    from src.db import SqliteStore, stamp

    fake, facts, td_list = _fixture()
    store = SqliteStore(tmp_path / "td_board.db")
    store.upsert("games", stamp([{**g, "is_neutral_site": False} for g in fake.t["games"]]))
    store.upsert("game_simulations", [{**s, "n_sims": 10000, "sim_version": "sim-v1", "sport": "nfl", "home_team": "BBB", "away_team": "AAA",
                                       "box_score": {"home": {"team": {"pass_att": {"mean": 30.0}, "rush_att": {"mean": 28.0}}}}}
                                      for s in fake.t["game_simulations"]])
    raw = store.select("game_simulations", {"game_id": "2026_11_AAA_BBB"})[0]
    assert isinstance(raw["td_scorers"], str) and isinstance(raw["box_score"], str)      # the condition that broke it
    doc = td_board.build(2026, 11, now=datetime(2026, 11, 19, 21, 0, tzinfo=timezone.utc), store=store, facts=facts,
                         td_list=td_list)
    store.close()
    assert doc["counts"] == {"players": 4, "priced": 1, "games": 1}
    bo = next(p for p in doc["players"] if p["player"] == "Bo One")
    assert bo["p_two"] == 0.15 and bo["explain"]["role_injuries"][0]["from"] == "Bo Hurt"
    assert bo["explain"]["game_script"]["sim_plays"] == 58.0
