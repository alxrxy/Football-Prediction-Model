"""Tests for P62's Sportradar shadow pull (Phase 1).

    python -m tests.test_shadow_props_sr

Pins the converter and maps (S8d), and S6(a): whatever the shadow does,
including every way Sportradar can fail, props_lines.json is byte-identical to
a run with the shadow off and the props pull returns normally.
"""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import requests

from src import shadow_props_sr as sh

PASS, FAIL = 0, 0
FIXTURE = Path(__file__).parent / "fixtures" / "sr_props_pit_cle_2026w4.json"
NOW = datetime(2026, 10, 1, 23, 0, tzinfo=timezone.utc)


def check(label: str, got, want) -> None:
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got {got!r}, want {want!r}")


def outcome(kind, total, price, removed=False):
    return {"type": kind, "total": str(total), "odds_american": str(price), "removed": removed}


def book(name, total=50.5, over=-110, under=-110, removed=False, outcomes=None):
    return {"name": name, "removed": removed,
            "outcomes": outcomes if outcomes is not None else [outcome("over", total, over),
                                                               outcome("under", total, under)]}


def payload(books, market="total receiving yards (incl. overtime)", is_live=False, name="Pittman, Michael"):
    return {"sport_event_players_props": {
        "sport_event": {"id": "sr:sport_event:1"},
        "players_props": [{"player": {"name": name}, "markets": [{"name": market, "is_live": is_live, "books": books}]}],
        "players_markets": {"markets": []}}}


def test_first_last():
    check("Last, First", sh.first_last("Pittman, Michael"), "Michael Pittman")
    check("suffix kept in place", sh.first_last("Penix Jr., Michael"), "Michael Penix Jr.")
    check("two-word last name", sh.first_last("St. Brown, Amon-Ra"), "Amon-Ra St. Brown")
    check("no comma kept", sh.first_last("DK Metcalf"), "DK Metcalf")


def test_convert_real_payload():
    """The 9/30 PIT @ CLE response (trimmed to the four priced markets)."""
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    players, counts = sh.convert(data)
    check("Rodgers converted", "Aaron Rodgers" in players, True)
    books = {b for p in players.values() for m in p.values() for b in m}
    check("only mapped books", books <= set(sh.BOOK_MAP.values()), True)
    check("consensus never a book", "consensus" in books, False)
    check("consensus counted", counts["consensus_dropped"] > 0, True)
    check("no unmapped book in this payload", counts["unmapped_books"], [])
    rodgers = players["Aaron Rodgers"]["player_pass_yds"]["draftkings"]
    check("numbers, not strings", (type(rodgers["point"]), type(rodgers["over"])), (float, int))
    check("markets are the four keys", {m for p in players.values() for m in p} <= set(sh.MARKET_MAP.values()), True)


def test_convert_exclusions():
    players, counts = sh.convert(payload([
        book("DraftKings"), book("FanDuel", removed=True), book("consensus"), book("SomeNewBook"),
        book("MGM", outcomes=[outcome("over", 50.5, -110, removed=True), outcome("under", 50.5, -110, removed=True)]),
        book("BetRivers", outcomes=[outcome("over", 50.5, -110), outcome("under", 51.5, -110)]),
    ]))
    check("only DraftKings kept", list(players["Michael Pittman"]["player_reception_yds"]), ["draftkings"])
    check("removed book + all-removed outcomes", counts["removed"], 2)
    check("unmapped listed", counts["unmapped_books"], ["SomeNewBook"])
    check("two totals is ambiguous, not guessed", counts["ambiguous"], 1)
    players, counts = sh.convert(payload([book("DraftKings")], is_live=True))
    check("live market dropped", (players, counts["live_dropped"]), ({}, 1))
    players, _ = sh.convert(payload([book("DraftKings")], market="longest reception (incl. overtime)"))
    check("unpriced market ignored", players, {})


def test_map_events():
    events = [{"id": "e1", "away": "PIT", "home": "CLE", "start_time": "2026-10-02T00:15:00+00:00"},
              {"id": "e2", "away": "LA", "home": "PHI", "start_time": "2026-10-04T17:00:00+00:00"}]
    games = {"2026_04_PIT_CLE": {"away": "PIT", "home": "CLE", "kickoff": "2026-10-02T00:15:00+00:00"},
             "2026_04_LA_PHI": {"away": "LA", "home": "PHI", "kickoff": "2026-10-04T17:00:00Z"},
             "2026_04_KC_LV": {"away": "KC", "home": "LV", "kickoff": "2026-10-04T20:25:00+00:00"}}
    mapping, problems = sh.map_events(events, games)
    check("two mapped", mapping, {"2026_04_PIT_CLE": "e1", "2026_04_LA_PHI": "e2"})
    check("unmapped reported", problems, ["2026_04_KC_LV: 0 Sportradar events match"])
    games["2026_04_PIT_CLE"]["kickoff"] = "2026-10-09T00:15:00+00:00"
    mapping, problems = sh.map_events(events, games)
    check("kickoff far off is not a match", "2026_04_PIT_CLE" in mapping, False)


ODDS = {"pulled_at": "2026-10-01T22:58:00+00:00", "season": 2026, "week": 4, "markets": list(sh.MARKET_MAP.values()),
        "games": {"2026_04_PIT_CLE": {"home": "CLE", "away": "PIT", "kickoff": "2026-10-02T00:15:00+00:00",
                                      "event_id": "oddsapi1", "players": {}, "pulled_at": "2026-10-01T22:58:00+00:00"}}}
SCHEDULE = {"schedules": [{"sport_event": {"id": "sr:sport_event:71515842", "start_time": "2026-10-02T00:15:00+00:00",
                                           "competitors": [{"qualifier": "home", "abbreviation": "CLE"},
                                                           {"qualifier": "away", "abbreviation": "PIT"}]}}]}


def fake_get(props):
    def get(path):
        if path == sh.SCHEDULE_PATH:
            return SCHEDULE
        if callable(props):
            return props()
        return props
    return get


def test_pull_saves_pair():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        odds_path = tmp / "props_lines.json"
        odds_path.write_text(json.dumps(ODDS), encoding="utf-8")
        rows = sh.shadow(ODDS, {"2026_04_PIT_CLE"}, get=fake_get(data), now=NOW, out=tmp / "sr",
                         lines_path=tmp / "props_lines_sr.json", odds_path=odds_path)
        check("saved", rows[0]["result"], "saved")
        check("minutes after the odds pull", rows[0]["minutes_after_odds"], 2.0)
        sr = json.loads((tmp / "props_lines_sr.json").read_text(encoding="utf-8"))
        g = sr["games"]["2026_04_PIT_CLE"]
        check("keeps the Odds API event id (for --alts)", g["event_id"], "oddsapi1")
        check("same schema keys", set(g) >= {"home", "away", "kickoff", "event_id", "books", "players", "pulled_at"}, True)
        pull = tmp / "sr" / "pulls" / "20261001T230000Z"
        check("pair saved: odds copy, sr file, raw", sorted(p.name for p in pull.iterdir()),
              ["odds.json", "raw_2026_04_PIT_CLE.json", "sr.json"])


def _raises(exc):
    def f():
        raise exc
    return f


class _Resp:
    def __init__(self, status, text=""):
        self.status_code, self.text = status, text

    def raise_for_status(self):
        raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        raise ValueError("not json")


def test_failures_never_raise_and_never_touch_odds():
    """S6(a): every failure is logged, nothing raised, props_lines.json untouched."""
    from src.sportradar import KeyManager, QuotaExhausted

    cases = {
        "timeout": fake_get(_raises(requests.Timeout("read timed out"))),
        "401/403": fake_get(_raises(requests.HTTPError("403 Forbidden"))),
        "429 (gave up)": fake_get(_raises(RuntimeError("gave up after 4 attempts (last status 429)"))),
        "malformed JSON": fake_get(_raises(ValueError("Expecting value"))),
        "empty response": fake_get({}),
        "schedule fails": lambda path: (_ for _ in ()).throw(requests.ConnectionError("no route")),
        "over budget (KEY1 only)": fake_get(_raises(QuotaExhausted("within 50 of 1000"))),
    }
    for label, get in cases.items():
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            odds_path = tmp / "props_lines.json"
            odds_path.write_text(json.dumps(ODDS), encoding="utf-8")
            before = odds_path.read_bytes()
            try:
                rows = sh.shadow(ODDS, {"2026_04_PIT_CLE"}, get=get, now=NOW, out=tmp / "sr",
                                 lines_path=tmp / "props_lines_sr.json", odds_path=odds_path)
                raised = False
            except Exception:  # noqa: BLE001
                rows, raised = [], True
            check(f"{label}: no raise", raised, False)
            check(f"{label}: props_lines.json untouched", odds_path.read_bytes() == before, True)
            check(f"{label}: logged as not saved", bool(rows) and not rows[0]["result"].startswith("saved"), True)
            check(f"{label}: no shadow file written", (tmp / "props_lines_sr.json").exists(), False)

    # A real KeyManager restricted to KEY1 over budget: refuses before any call, no rotation.
    with tempfile.TemporaryDirectory() as tmp:
        km = KeyManager(usage_dir=Path(tmp), names=[sh.SHADOW_KEY], values={sh.SHADOW_KEY: "x", "SPORTRADAR_API_KEY2": "y"},
                        quota=1, margin=0, now=lambda: NOW)
        km._append({"event": "call", "utc": NOW.isoformat(), "key": sh.SHADOW_KEY, "product": "oddscomparison-player-props",
                    "path": "/x", "status": 200})
        calls = []
        try:
            km.get("/oddscomparison-player-props/x", fetch=lambda *a, **k: calls.append(1) or _Resp(200))
            outcome_ = "called"
        except QuotaExhausted:
            outcome_ = "refused"
        check("KEY1-only manager stops at budget, no other key, no call", (outcome_, calls), ("refused", []))


def test_partial_response_keeps_other_games():
    """A partial pull: one game fails, the other is saved; the failure is listed."""
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    odds = json.loads(json.dumps(ODDS))
    odds["games"]["2026_04_KC_LV"] = {"home": "LV", "away": "KC", "kickoff": "2026-10-04T20:25:00+00:00", "players": {}}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        rows = sh.shadow(odds, {"2026_04_PIT_CLE", "2026_04_KC_LV"}, get=fake_get(data), now=NOW, out=tmp / "sr",
                         lines_path=tmp / "props_lines_sr.json")
        results = {r["game_id"]: r["result"][:8] for r in rows}
        check("one saved, one unmapped", results, {"2026_04_PIT_CLE": "saved", "2026_04_KC_LV": "unmapped"})


def test_ingest_props_identical_with_shadow_failing_or_off():
    """S6(a)/S8(a) at the ingest level: props_lines.json byte-identical with the
    shadow off, failing, raising, or succeeding; the run returns normally."""
    import os

    from src import config, db, ingest_props

    class FrozenDT(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW

    class Store:
        def select(self, table, where=None):
            if table == "games":
                return [{"game_id": "2026_04_PIT_CLE", "sport": "nfl", "season": 2026, "week": 4, "completed": False,
                         "home_team": "CLE", "away_team": "PIT", "kickoff_time": "2026-10-02T00:15:00+00:00"}]
            return [{"team": "CLE", "full_name": "Cleveland Browns"}, {"team": "PIT", "full_name": "Pittsburgh Steelers"}]

        def close(self):
            pass

    event = {"id": "oddsapi1", "home_team": "Cleveland Browns", "away_team": "Pittsburgh Steelers",
             "commence_time": "2026-10-02T00:15:00Z"}
    odds_event = {"bookmakers": [{"key": "draftkings", "markets": [{"key": "player_pass_yds", "outcomes": [
        {"name": "Over", "description": "Aaron Rodgers", "point": 212.5, "price": -112},
        {"name": "Under", "description": "Aaron Rodgers", "point": 212.5, "price": -112}]}]}]}

    def get_json(url, params=None, cache_minutes=None, cache_tag=None, capture_meta=None):
        if capture_meta is not None:
            capture_meta["from_cache"] = False
        return [event] if url.endswith("/events") else odds_event

    saved = (db.get_store, ingest_props.get_json, ingest_props.datetime, ingest_props.PROPS_LINES_JSON,
             config.require, sh.shadow, os.environ.get("P62_SHADOW"))
    outputs = {}
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            db.get_store = lambda: Store()
            ingest_props.get_json = get_json
            ingest_props.datetime = FrozenDT
            ingest_props.PROPS_LINES_JSON = tmp / "props_lines.json"
            config.require = lambda name: "k"
            real = saved[5]
            modes = {
                "off": ("0", real),
                "failing": ("1", lambda o, g, **k: real(o, g, get=fake_get(_raises(requests.Timeout("t"))), now=NOW,
                                                        out=tmp / "sr_fail", lines_path=tmp / "sr_fail.json", **k)),
                "raising": ("1", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))),
                "succeeding": ("1", lambda o, g, **k: real(o, g, get=fake_get(json.loads(FIXTURE.read_text(encoding="utf-8"))),
                                                           now=NOW, out=tmp / "sr_ok", lines_path=tmp / "sr_ok.json", **k)),
            }
            for mode, (flag, fn) in modes.items():
                os.environ["P62_SHADOW"] = flag
                sh.shadow = fn
                try:
                    ingest_props.run(cache_minutes=0)
                    ok = True
                except Exception:  # noqa: BLE001
                    ok = False
                check(f"{mode}: props pull returns normally", ok, True)
                outputs[mode] = ingest_props.PROPS_LINES_JSON.read_bytes()
            check("succeeding shadow wrote its own file", (tmp / "sr_ok.json").exists(), True)
    finally:
        (db.get_store, ingest_props.get_json, ingest_props.datetime, ingest_props.PROPS_LINES_JSON,
         config.require, sh.shadow, flag) = saved
        if flag is None:
            os.environ.pop("P62_SHADOW", None)
        else:
            os.environ["P62_SHADOW"] = flag
    for mode in ("failing", "raising", "succeeding"):
        check(f"props_lines.json byte-identical: off vs {mode}", outputs.get(mode) == outputs.get("off"), True)


if __name__ == "__main__":
    for fn in [
        test_first_last,
        test_convert_real_payload,
        test_convert_exclusions,
        test_map_events,
        test_pull_saves_pair,
        test_failures_never_raise_and_never_touch_odds,
        test_partial_response_keeps_other_games,
        test_ingest_props_identical_with_shadow_failing_or_off,
    ]:
        print(fn.__name__)
        fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
