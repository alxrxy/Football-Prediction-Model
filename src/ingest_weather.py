"""Open-Meteo weather ingestion, keyed to kickoff hour.

No auth. Open-Meteo accepts comma-separated coordinate lists, so the whole
slate costs a couple of requests rather than one per game. Dome games skip
the API entirely — the weather adjustment is a no-op indoors.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from . import config, db
from .http import safe_get_json

BATCH = 50
# Open-Meteo only forecasts ~16 days ahead; anything beyond that is skipped.
MAX_FORECAST_DAYS = 15


def _parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def run(game_ids: list[str] | None = None, sport: str = "ncaaf") -> int:
    store = db.get_store()
    games = store.select("games", {"sport": sport})
    if game_ids:
        wanted = set(game_ids)
        games = [g for g in games if g["game_id"] in wanted]

    venues = {v["venue_id"]: v for v in store.select("venues")}
    now = datetime.now(timezone.utc)

    rows: list[dict] = []
    pending: list[tuple[dict, dict, datetime]] = []
    missing_venue = 0

    for g in games:
        kickoff = _parse_dt(g.get("kickoff_time"))
        venue = venues.get(str(g.get("venue_id"))) if g.get("venue_id") else None
        if venue is None:
            missing_venue += 1
            continue
        if venue.get("is_dome"):
            rows.append(
                {
                    "game_id": g["game_id"],
                    "temp_f": None,
                    "wind_mph": None,
                    "precip_pct": None,
                    "is_dome": True,
                    "forecast_for": kickoff.isoformat() if kickoff else None,
                }
            )
            continue
        if kickoff is None or not (now - timedelta(days=1) < kickoff < now + timedelta(days=MAX_FORECAST_DAYS)):
            continue
        pending.append((g, venue, kickoff))

    for i in range(0, len(pending), BATCH):
        chunk = pending[i : i + BATCH]
        rows.extend(_fetch_chunk(chunk))

    store.upsert("weather", db.stamp(rows))
    outdoor = sum(1 for r in rows if not r["is_dome"])
    print(
        f"[weather] {len(rows)} rows ({outdoor} outdoor forecasts, "
        f"{len(rows) - outdoor} domes)"
        + (f"; {missing_venue} game(s) had no venue coords" if missing_venue else "")
    )
    store.close()
    return len(rows)


def _fetch_chunk(chunk: list[tuple[dict, dict, datetime]]) -> list[dict]:
    lats = ",".join(f"{v['latitude']:.4f}" for _, v, _ in chunk)
    lons = ",".join(f"{v['longitude']:.4f}" for _, v, _ in chunk)
    start = min(k for _, _, k in chunk).date()
    end = max(k for _, _, k in chunk).date()

    data = safe_get_json(
        config.OPEN_METEO_BASE,
        params={
            "latitude": lats,
            "longitude": lons,
            "hourly": "temperature_2m,windspeed_10m,precipitation_probability",
            "temperature_unit": "fahrenheit",
            "windspeed_unit": "mph",
            "timezone": "UTC",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
        cache_minutes=60,
        cache_tag="meteo",
    )
    if data is None:
        return []

    # A single coordinate returns an object; multiple return a list.
    results = data if isinstance(data, list) else [data]
    rows = []
    for (game, _venue, kickoff), result in zip(chunk, results):
        point = _at_hour(result.get("hourly") or {}, kickoff)
        if point is None:
            continue
        rows.append(
            {
                "game_id": game["game_id"],
                "temp_f": point["temp_f"],
                "wind_mph": point["wind_mph"],
                "precip_pct": point["precip_pct"],
                "is_dome": False,
                "forecast_for": kickoff.isoformat(),
            }
        )
    return rows


def _at_hour(hourly: dict, kickoff: datetime) -> dict | None:
    times = hourly.get("time") or []
    if not times:
        return None
    target = kickoff.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    best_i, best_delta = None, None
    for i, stamp in enumerate(times):
        dt = datetime.fromisoformat(stamp).replace(tzinfo=timezone.utc)
        delta = abs((dt - target).total_seconds())
        if best_delta is None or delta < best_delta:
            best_i, best_delta = i, delta
    if best_i is None or best_delta > 3 * 3600:
        return None

    def pick(key):
        series = hourly.get(key) or []
        return series[best_i] if best_i < len(series) else None

    return {
        "temp_f": pick("temperature_2m"),
        "wind_mph": pick("windspeed_10m"),
        "precip_pct": pick("precipitation_probability"),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest kickoff-hour weather.")
    parser.add_argument("--sport", default="ncaaf")
    args = parser.parse_args()
    run(sport=args.sport)
