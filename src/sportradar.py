"""Sportradar client: one active key, usage counted locally, sequential failover.

    python -m src.sportradar --status        # active key and this month's usage per key

Nothing in the pipeline calls this yet (diagnosis only, 2026-09-30).

Keys are SPORTRADAR_API_KEY1..N in .env, used in that order. KEY1 is primary.
Sportradar sends no quota headers, so every call made through `get` is
appended to data/sportradar/usage.jsonl (key *name*, product, path, status,
never the key value) and usage is counted from that file. Before each call the
active key is the first key in order that is below
SPORTRADAR_MONTHLY_QUOTA - SPORTRADAR_QUOTA_MARGIN calls for every product this
calendar month (UTC) and has not been refused this month. When that changes
from the previous call's key, a `switch` line is written with the time, both
key names and the reason. Keys are never used in parallel or round-robin: the
next key is touched only when the one before it is spent. A new month starts
back on KEY1.

A 403 whose body reads as a quota or inactive-key refusal marks the key
refused for the month and retries once on the next key. A 429 is the 1-call-
per-second rate limit, not quota: wait and retry on the same key. Calls are
spaced by SPORTRADAR_MIN_INTERVAL seconds across processes (the last call's
time is kept in the state file), since two back-to-back processes hit 429.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import requests

from . import config

BASE = "https://api.sportradar.com"
MONTHLY_QUOTA = int(os.getenv("SPORTRADAR_MONTHLY_QUOTA", "1000"))
QUOTA_MARGIN = int(os.getenv("SPORTRADAR_QUOTA_MARGIN", "50"))
MIN_INTERVAL = float(os.getenv("SPORTRADAR_MIN_INTERVAL", "1.5"))
USAGE_DIR = config.DATA_DIR / "sportradar"

_REFUSAL_WORDS = ("quota", "limit exceeded", "inactive", "over qps", "not authorized", "developer inactive")


class QuotaExhausted(RuntimeError):
    pass


def key_names() -> list[str]:
    names, i = [], 1
    while os.getenv(f"SPORTRADAR_API_KEY{i}", "").strip():
        names.append(f"SPORTRADAR_API_KEY{i}")
        i += 1
    return names


def product(path: str) -> str:
    """'/nfl/official/trial/v7/...' -> 'nfl'; quota is counted per product."""
    return path.lstrip("/").split("/", 1)[0]


class KeyManager:
    def __init__(self, usage_dir: Path = USAGE_DIR, names: list[str] | None = None,
                 values: dict[str, str] | None = None, quota: int = MONTHLY_QUOTA,
                 margin: int = QUOTA_MARGIN, now: Callable[[], datetime] | None = None):
        self.dir = Path(usage_dir)
        self.names = names if names is not None else key_names()
        self.values = values if values is not None else {n: os.getenv(n, "").strip() for n in self.names}
        self.quota, self.margin = quota, margin
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.ledger = self.dir / "usage.jsonl"
        self.state_path = self.dir / "state.json"

    # --- ledger ---
    def _lines(self) -> list[dict]:
        if not self.ledger.exists():
            return []
        return [json.loads(x) for x in self.ledger.read_text(encoding="utf-8").splitlines() if x.strip()]

    def _append(self, row: dict) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        with self.ledger.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")

    def _state(self) -> dict:
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save_state(self, state: dict) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(state, indent=1), encoding="utf-8")

    def usage(self) -> dict[str, Counter]:
        """Calls this UTC month, per key name, per product."""
        month = self.now().strftime("%Y-%m")
        out: dict[str, Counter] = {n: Counter() for n in self.names}
        for row in self._lines():
            if row.get("event") == "call" and row.get("utc", "").startswith(month):
                out.setdefault(row["key"], Counter())[row["product"]] += 1
        return out

    def refused(self) -> set[str]:
        month = self.now().strftime("%Y-%m")
        return {r["key"] for r in self._lines()
                if r.get("event") == "refused" and r.get("utc", "").startswith(month)}

    # --- selection ---
    def active(self) -> str:
        """First key in order with room on every product and no refusal this month.
        Logs a switch line when it differs from the key the last call used."""
        use, refused = self.usage(), self.refused()
        limit = self.quota - self.margin
        chosen = None
        for n in self.names:
            if n in refused or not self.values.get(n):
                continue
            if max(use.get(n, Counter()).values(), default=0) < limit:
                chosen = n
                break
        if chosen is None:
            raise QuotaExhausted(f"every Sportradar key is within {self.margin} of {self.quota} "
                                 f"calls this month or refused: {dict((n, dict(use.get(n, {}))) for n in self.names)}")
        state = self._state()
        prev = state.get("active")
        if prev and prev != chosen:
            if prev in refused:
                reason = "refused by Sportradar"
            else:
                reason = (f"{max(use.get(prev, Counter()).values(), default=0)} calls "
                          f">= {limit} (quota {self.quota} - margin {self.margin})")
            if self.names.index(chosen) < self.names.index(prev):
                reason = "new month: back to primary"
            self._append({"event": "switch", "utc": self._stamp(), "from": prev, "to": chosen, "reason": reason})
            print(f"[sportradar] key switch {prev} -> {chosen}: {reason}")
        if prev != chosen:
            state["active"] = chosen
            self._save_state(state)
        return chosen

    def _stamp(self) -> str:
        return self.now().isoformat(timespec="seconds")

    # --- calls ---
    def _throttle(self) -> None:
        last = self._state().get("last_call_epoch", 0.0)
        wait = MIN_INTERVAL - (time.time() - last)
        if wait > 0:
            time.sleep(wait)

    def get(self, path: str, params: dict | None = None, *,
            fetch: Callable[..., requests.Response] = requests.get) -> dict:
        """GET BASE+path with the active key. Every attempt is logged and counted."""
        for attempt in range(4):
            name = self.active()
            self._throttle()
            resp = fetch(BASE + path, params=params, timeout=45,
                         headers={"x-api-key": self.values[name], "accept": "application/json"})
            state = self._state()
            state["last_call_epoch"] = time.time()
            self._save_state(state)
            self._append({"event": "call", "utc": self._stamp(), "key": name,
                          "product": product(path), "path": path, "status": resp.status_code})
            if resp.status_code == 429:
                time.sleep(MIN_INTERVAL * (attempt + 1))
                continue
            if resp.status_code == 403 and any(w in resp.text.lower() for w in _REFUSAL_WORDS):
                self._append({"event": "refused", "utc": self._stamp(), "key": name,
                              "detail": resp.text[:200]})
                continue
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError(f"Sportradar {path}: gave up after 4 attempts (last status {resp.status_code})")


def status(km: KeyManager | None = None) -> str:
    km = km or KeyManager()
    use, refused = km.usage(), km.refused()
    lines = [f"quota {km.quota}/key/product/month, switch at {km.quota - km.margin}; "
             f"active: {km._state().get('active', '(none yet)')}"]
    for n in km.names:
        tag = " refused" if n in refused else ""
        lines.append(f"  {n}: {dict(use.get(n, {})) or 0}{tag}")
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()
    print(status())
