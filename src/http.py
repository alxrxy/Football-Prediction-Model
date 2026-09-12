"""Shared HTTP helpers: retries, backoff, and a disk cache.

The cache exists mainly to protect The Odds API quota (~500 req/month shared
across both sports) — re-running the pipeline five times while debugging must
not cost five requests.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

from . import config

USER_AGENT = "football-predictor/0.1"


class FetchError(RuntimeError):
    pass


def get_json(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: int = 45,
    retries: int = 3,
    cache_minutes: int = 0,
    cache_tag: str = "",
    capture_meta: dict | None = None,
) -> Any:
    """GET returning parsed JSON, with optional disk caching and backoff.

    `capture_meta`, if given, is populated with quota info (`quota_remaining`,
    `from_cache`) so callers can report how much of a metered budget is left.
    """
    cache_path = None
    if cache_minutes > 0:
        cache_path = _cache_path(url, params, cache_tag)
        cached = _read_cache(cache_path, cache_minutes, capture_meta)
        if cached is not None:
            return cached

    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            resp = requests.get(
                url,
                params=params,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json", **(headers or {})},
                timeout=timeout,
            )
            if resp.status_code == 429:
                wait = min(30, 2 ** attempt * 5)
                print(f"  rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            if capture_meta is not None:
                capture_meta["quota_remaining"] = resp.headers.get("x-requests-remaining")
                capture_meta["quota_used"] = resp.headers.get("x-requests-used")
                capture_meta["from_cache"] = False
            if cache_path is not None:
                _write_cache(cache_path, data, resp.headers)
            return data
        except Exception as exc:  # noqa: BLE001 - retried below
            last_error = exc
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise FetchError(f"GET {url} failed after {retries} attempts: {last_error}")


def get_json_with_headers(url: str, **kwargs) -> tuple[Any, dict]:
    """Like get_json but also returns response headers (for quota tracking).

    Deliberately uncached — callers that need live headers want a live call.
    """
    resp = requests.get(
        url,
        params=kwargs.get("params"),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json", **(kwargs.get("headers") or {})},
        timeout=kwargs.get("timeout", 45),
    )
    resp.raise_for_status()
    return resp.json(), dict(resp.headers)


def safe_get_json(url: str, **kwargs) -> Any | None:
    """For unofficial/flaky endpoints (ESPN). Returns None instead of raising,
    so one bad team's depth chart degrades the pipeline rather than killing it.
    """
    try:
        return get_json(url, **kwargs)
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] {url} unavailable: {type(exc).__name__}")
        return None


# --- cache internals -------------------------------------------------------

def _cache_path(url: str, params: dict | None, tag: str) -> Path:
    config.ensure_dirs()
    key = hashlib.sha256(f"{url}|{sorted((params or {}).items())}".encode()).hexdigest()[:16]
    name = f"{tag + '_' if tag else ''}{key}.json"
    return config.CACHE_DIR / name


def _read_cache(path: Path, minutes: int, capture_meta: dict | None = None):
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        fetched = datetime.fromisoformat(payload["fetched_at"])
        age = datetime.now(timezone.utc) - fetched
        if age < timedelta(minutes=minutes):
            print(f"  [cache] hit, age {int(age.total_seconds() // 60)}m ({path.name})")
            if capture_meta is not None:
                capture_meta["quota_remaining"] = payload.get("quota_remaining")
                capture_meta["from_cache"] = True
            return payload["data"]
    except Exception:  # noqa: BLE001 - a corrupt cache entry is just a miss
        return None
    return None


def _write_cache(path: Path, data, headers: dict) -> None:
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "quota_remaining": headers.get("x-requests-remaining"),
        "data": data,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
