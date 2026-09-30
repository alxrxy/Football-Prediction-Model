"""Tests for the Sportradar key manager (src/sportradar.py).

    python -m tests.test_sportradar
"""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from src import sportradar
from src.sportradar import KeyManager, QuotaExhausted

PASS, FAIL = 0, 0


def check(label: str, got, want) -> None:
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got {got!r}, want {want!r}")


NAMES = ["SPORTRADAR_API_KEY1", "SPORTRADAR_API_KEY2", "SPORTRADAR_API_KEY3"]
VALUES = {n: f"secret{i}" for i, n in enumerate(NAMES, 1)}


class Resp:
    def __init__(self, status: int, body: str = "{}"):
        self.status_code, self.text = status, body

    def json(self):
        return json.loads(self.text)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def manager(tmp, month=(2026, 9), quota=5, margin=1):
    return KeyManager(Path(tmp), NAMES, VALUES, quota, margin,
                      now=lambda: datetime(*month, 15, 12, tzinfo=timezone.utc))


def calls(km, n, fetch=lambda *a, **k: Resp(200)):
    return [km.get("/nfl/official/trial/v7/en/x.json", fetch=fetch) for _ in range(n)]


def lines(tmp):
    return [json.loads(x) for x in (Path(tmp) / "usage.jsonl").read_text().splitlines()]


def test_primary_until_margin_then_next_in_sequence():
    sportradar.MIN_INTERVAL = 0
    with tempfile.TemporaryDirectory() as tmp:
        km = manager(tmp)                      # switch at 5 - 1 = 4 calls
        sent = []
        calls(km, 6, fetch=lambda url, **k: sent.append(k["headers"]["x-api-key"]) or Resp(200))
        check("4 calls on primary, then key 2", sent, ["secret1"] * 4 + ["secret2"] * 2)
        sw = [r for r in lines(tmp) if r["event"] == "switch"]
        check("one switch logged", [(r["from"], r["to"]) for r in sw], [(NAMES[0], NAMES[1])])
        check("switch reason names the count", "4 calls >= 4" in sw[0]["reason"], True)
        check("ledger never holds a key value", "secret" in (Path(tmp) / "usage.jsonl").read_text(), False)


def test_quota_counted_per_product():
    sportradar.MIN_INTERVAL = 0
    with tempfile.TemporaryDirectory() as tmp:
        km = manager(tmp)
        calls(km, 3)
        km.get("/oddscomparison-player-props/trial/v2/en/books.json", fetch=lambda *a, **k: Resp(200))
        check("3 nfl + 1 props stays on primary", km.active(), NAMES[0])
        check("usage split by product", dict(km.usage()[NAMES[0]]),
              {"nfl": 3, "oddscomparison-player-props": 1})


def test_refusal_moves_on_and_429_does_not():
    sportradar.MIN_INTERVAL = 0
    with tempfile.TemporaryDirectory() as tmp:
        km = manager(tmp, quota=100)
        seq = iter([Resp(429), Resp(200), Resp(403, '{"message":"Developer Inactive"}'), Resp(200)])
        sent = []
        calls(km, 2, fetch=lambda url, **k: sent.append(k["headers"]["x-api-key"]) or next(seq))
        check("429 retried on same key; 403 refusal moves to key 2", sent,
              ["secret1", "secret1", "secret1", "secret2"])
        check("refusal recorded", km.refused(), {NAMES[0]})
        check("failed attempts still counted", km.usage()[NAMES[0]]["nfl"], 3)


def test_new_month_returns_to_primary():
    sportradar.MIN_INTERVAL = 0
    with tempfile.TemporaryDirectory() as tmp:
        calls(manager(tmp), 5)
        check("september ends on key 2", manager(tmp).active(), NAMES[1])
        check("october starts on primary", manager(tmp, month=(2026, 10)).active(), NAMES[0])
        check("logged as back to primary", lines(tmp)[-1]["reason"], "new month: back to primary")


def test_all_spent_raises():
    sportradar.MIN_INTERVAL = 0
    with tempfile.TemporaryDirectory() as tmp:
        km = manager(tmp, quota=2, margin=1)
        calls(km, 3)
        try:
            km.active()
            got = "no error"
        except QuotaExhausted:
            got = "QuotaExhausted"
        check("every key spent raises", got, "QuotaExhausted")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            print(name)
            fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
