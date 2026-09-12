"""Storage adapter.

One interface, two backends. `STORAGE_BACKEND=supabase` talks to the real
project; `sqlite` runs the identical pipeline against a local file so nothing
is blocked on account setup. Same table names, same primary keys, so switching
is a one-line .env change with no code edits.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Iterable

from . import config

# Conflict targets, mirroring the primary keys in db/schema_*.sql.
TABLE_KEYS: dict[str, list[str]] = {
    "venues": ["venue_id"],
    "teams": ["team", "sport"],
    "games": ["game_id"],
    "team_ratings": ["team", "sport", "season", "week"],
    "injuries": ["player", "team", "sport", "season", "week"],
    "depth_charts": ["team", "sport", "position", "depth_order"],
    "weather": ["game_id"],
    "odds": ["game_id", "book"],
    "predictions": ["game_id", "model_version"],
}

JSON_COLUMNS = {"components"}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    """Base interface."""

    backend = "none"

    def upsert(self, table: str, rows: list[dict[str, Any]]) -> int:
        raise NotImplementedError

    def select(self, table: str, where: dict[str, Any] | None = None) -> list[dict]:
        raise NotImplementedError

    def close(self) -> None:
        pass


class SqliteStore(Store):
    backend = "sqlite"

    def __init__(self, path=None):
        config.ensure_dirs()
        self.path = path or config.SQLITE_PATH
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(config.SCHEMA_SQLITE.read_text(encoding="utf-8"))
        self.conn.commit()

    @staticmethod
    def _encode(row: dict[str, Any]) -> dict[str, Any]:
        out = {}
        for k, v in row.items():
            if k in JSON_COLUMNS and not isinstance(v, (str, type(None))):
                out[k] = json.dumps(v)
            elif isinstance(v, bool):
                out[k] = int(v)
            elif isinstance(v, (dict, list)):
                out[k] = json.dumps(v)
            else:
                out[k] = v
        return out

    def upsert(self, table: str, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        keys = TABLE_KEYS[table]
        written = 0
        for row in rows:
            row = self._encode(row)
            cols = list(row)
            placeholders = ", ".join("?" for _ in cols)
            updates = [c for c in cols if c not in keys]
            set_clause = ", ".join(f"{c}=excluded.{c}" for c in updates) or None
            sql = (
                f"insert into {table} ({', '.join(cols)}) values ({placeholders}) "
                f"on conflict({', '.join(keys)}) do "
                + (f"update set {set_clause}" if set_clause else "nothing")
            )
            self.conn.execute(sql, [row[c] for c in cols])
            written += 1
        self.conn.commit()
        return written

    def select(self, table: str, where: dict[str, Any] | None = None) -> list[dict]:
        sql = f"select * from {table}"
        params: list[Any] = []
        if where:
            clauses = []
            for k, v in where.items():
                if isinstance(v, (list, tuple)):
                    clauses.append(f"{k} in ({', '.join('?' for _ in v)})")
                    params.extend(v)
                else:
                    clauses.append(f"{k} = ?")
                    params.append(v)
            sql += " where " + " and ".join(clauses)
        cur = self.conn.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]

    def close(self) -> None:
        self.conn.close()


class SupabaseStore(Store):
    backend = "supabase"

    def __init__(self):
        from supabase import create_client

        url = config.require("SUPABASE_URL")
        key = config.require("SUPABASE_SERVICE_KEY")
        self.client = create_client(url, key)

    def upsert(self, table: str, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        on_conflict = ",".join(TABLE_KEYS[table])
        written = 0
        # Chunked so a large slate doesn't blow the request size limit.
        for i in range(0, len(rows), 500):
            chunk = rows[i : i + 500]
            self.client.table(table).upsert(chunk, on_conflict=on_conflict).execute()
            written += len(chunk)
        return written

    def select(self, table: str, where: dict[str, Any] | None = None) -> list[dict]:
        query = self.client.table(table).select("*")
        for k, v in (where or {}).items():
            query = query.in_(k, list(v)) if isinstance(v, (list, tuple)) else query.eq(k, v)
        return query.execute().data


def get_store() -> Store:
    if config.STORAGE_BACKEND == "supabase":
        return SupabaseStore()
    return SqliteStore()


def stamp(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Tag every raw row with pulled_at, per architecture §2."""
    now = utcnow()
    out = []
    for row in rows:
        row.setdefault("pulled_at", now)
        out.append(row)
    return out
