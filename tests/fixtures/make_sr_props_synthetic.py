"""Writes tests/fixtures/sr_props_synthetic.json: a SYNTHETIC payload in the shape of Sportradar's
Odds Comparison Player Props response (sport_event_players_props). Every id, line and price is made
up by this script (fixed seed); nothing is copied from a Sportradar response. It replaced a captured
trial-API payload that had been committed as a fixture (2026-11-20).

    python tests/fixtures/make_sr_props_synthetic.py
"""
import json
import random
from pathlib import Path

rng = random.Random(20261120)
HOME, AWAY = "sr:competitor:900002", "sr:competitor:900001"
BOOKS = ["MGM", "DraftKings", "FanDuel", "BetRivers", "WilliamHillNewJersey", "consensus"]
MARKETS = {"pass": ("sr:market:9001", "total passing yards (incl. overtime)"),
           "rush": ("sr:market:9002", "total rushing yards (incl. overtime)"),
           "recyds": ("sr:market:9003", "total receiving yards (incl. overtime)"),
           "rec": ("sr:market:9004", "total receptions (incl. overtime)")}
PLAYERS = [  # name as the feed writes it, team, {market: made-up centre line}
    ("Rodgers, Aaron", AWAY, {"pass": 200.5, "rush": 4.5}),
    ("Watson, Deshaun", HOME, {"pass": 190.5, "rush": 20.5}),
    ("Metcalf, DK", AWAY, {"recyds": 60.5, "rec": 4.5}),
    ("Pittman, Michael", AWAY, {"recyds": 50.5, "rec": 4.5}),
    ("Jeudy, Jerry", HOME, {"recyds": 45.5, "rec": 3.5}),
    ("Judkins, Quinshon", HOME, {"rush": 65.5, "recyds": 15.5, "rec": 2.5}),
]


def price() -> str:
    p = rng.choice([-125, -120, -115, -112, -110, -108, -105, 100, 105])
    return f"+{p}" if p > 0 else str(p)


def book(i: int, name: str, line: float) -> dict:
    total = line + rng.choice([-1.0, 0.0, 0.0, 0.0, 1.0])
    opened = total + rng.choice([-1.0, 0.0, 1.0])
    outs = [{"id": f"sr:outcome:{12 + k}", "type": side, "odds_american": price(), "open_odds_american": price(),
             "total": f"{total:.1f}", "open_total": f"{opened:.1f}", "removed": False}
            for k, side in enumerate(("over", "under"))]
    return {"id": f"sr:book:{9100 + i}", "name": name, "removed": False,
            "external_sport_event_id": f"synthetic-{i}", "external_market_id": f"synthetic-{rng.randrange(10**6)}",
            "outcomes": outs}


doc = {"generated_at": "2026-09-30T22:10:33+00:00",
       "_note": "SYNTHETIC test fixture: ids, lines and prices are invented (tests/fixtures/make_sr_props_synthetic.py).",
       "sport_event_players_props": {
           "sport_event": {"id": "sr:sport_event:900000001", "start_time": "2026-10-02T00:15:00+00:00",
                           "start_time_confirmed": True, "status": "not_started",
                           "competitors": [
                               {"id": HOME, "name": "Cleveland Browns", "country": "USA", "country_code": "USA",
                                "abbreviation": "CLE", "qualifier": "home", "rotation_number": 102},
                               {"id": AWAY, "name": "Pittsburgh Steelers", "country": "USA", "country_code": "USA",
                                "abbreviation": "PIT", "qualifier": "away", "rotation_number": 101}]},
           "players_props": [
               {"player": {"id": f"sr:player:{900100 + n}", "name": name, "competitor_id": team},
                "markets": [{"id": MARKETS[m][0], "name": MARKETS[m][1], "is_live": False,
                             "books": [book(i, b, line) for i, b in enumerate(BOOKS)]} for m, line in lines.items()]}
               for n, (name, team, lines) in enumerate(PLAYERS)],
           "players_markets": {"markets": []}}}
out = Path(__file__).parent / "sr_props_synthetic.json"
out.write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")
print(f"wrote {out} ({out.stat().st_size} bytes)")
