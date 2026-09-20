"""Copy everything from the local SQLite mirror into Supabase.

    python -m src.sync_to_supabase --check    verify the schema is applied
    python -m src.sync_to_supabase            push all tables

Needed once, after pasting db/PASTE_INTO_SUPABASE.sql into the Supabase SQL Editor.
PostgREST cannot run DDL, so table creation stays a manual paste; everything
after that is automated.

Type coercion: SQLite has no native boolean or json type, so integer flags are
converted back to booleans and `components` is parsed back into an object
before being handed to Postgres.
"""

from __future__ import annotations

import argparse
import json
import sys

import requests

from . import config, db

TABLES = [
    "venues", "teams", "games", "team_ratings",
    "weather", "odds", "injuries", "depth_charts", "predictions",
    "game_simulations", "live_tracking", "live_simulations",
    "odds_snapshots", "clv_log", "inactives",
]

BOOLEAN_COLUMNS = {
    "clv_log": ["is_flag"],
    "venues": ["is_dome"],
    "games": ["is_neutral_site", "is_conference", "completed"],
    "weather": ["is_dome"],
    "predictions": ["is_value"],
    "live_tracking": ["is_red_zone", "alerted"],
}
JSON_COLUMNS = {
    "predictions": ["components"],
    "game_simulations": ["distributions", "td_scorers", "components", "box_score"],
    "live_tracking": ["flags", "recent_scoring", "pregame"],
    "live_simulations": ["start_state", "scorers", "box_score"],
}


def _headers() -> dict:
    key = config.require("SUPABASE_SERVICE_KEY")
    return {"apikey": key, "Authorization": f"Bearer {key}"}


def check() -> list[str]:
    """Return the list of tables missing from Supabase."""
    base = config.require("SUPABASE_URL")
    missing = []
    for table in TABLES:
        resp = requests.get(
            f"{base}/rest/v1/{table}",
            headers=_headers(),
            params={"select": "*", "limit": 1},
            timeout=30,
        )
        if resp.status_code == 404:
            missing.append(table)
        elif resp.status_code >= 400:
            print(f"  [warn] {table}: HTTP {resp.status_code} {resp.text[:120]}")
    return missing


def _coerce(table: str, row: dict) -> dict:
    out = dict(row)
    for col in BOOLEAN_COLUMNS.get(table, []):
        if out.get(col) is not None:
            out[col] = bool(out[col])
    for col in JSON_COLUMNS.get(table, []):
        value = out.get(col)
        if isinstance(value, str):
            try:
                out[col] = json.loads(value)
            except json.JSONDecodeError:
                out[col] = None
    return out


def sync(tables: list[str] | None = None) -> int:
    """Push local rows to Supabase. Upserts overwrite, so once Supabase is the
    live store, push only tables that exist solely in the local mirror:
    a full sync would replace newer Supabase rows (graded predictions, final
    scores) with older local ones."""
    tables = tables or TABLES
    missing = [t for t in check() if t in tables]
    if missing:
        print("Schema not applied yet. Missing tables: " + ", ".join(missing))
        print(f"\nPaste {config.SCHEMA_SUPABASE} into the Supabase SQL Editor and run it,")
        print("then re-run this command.")
        return 1

    source = db.SqliteStore()
    target = db.SupabaseStore()
    total = 0
    for table in tables:
        rows = [_coerce(table, r) for r in source.select(table)]
        if not rows:
            print(f"  {table:14} empty, skipped")
            continue
        target.upsert(table, rows)
        total += len(rows)
        print(f"  {table:14} {len(rows):>5} rows pushed")
    source.close()
    print(f"\nDone: {total} rows in Supabase.")
    print("Set STORAGE_BACKEND=supabase in .env to run the pipeline against it directly.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync local SQLite data into Supabase.")
    parser.add_argument("--check", action="store_true", help="only verify the schema")
    parser.add_argument("--tables", nargs="+", choices=TABLES,
                        help="push only these tables (default: all; see sync() before using the default)")
    args = parser.parse_args()

    if args.check:
        gaps = check()
        if gaps:
            print("Missing tables: " + ", ".join(gaps))
            print(f"Paste {config.SCHEMA_SUPABASE} into the SQL Editor and run it.")
            sys.exit(1)
        print(f"All {len(TABLES)} tables present in Supabase.")
        sys.exit(0)
    sys.exit(sync(args.tables))
