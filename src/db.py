"""Storage adapter.

One interface, two backends. `STORAGE_BACKEND=supabase` talks to the real
project; `sqlite` runs the identical pipeline against a local file so nothing
is blocked on account setup. Same table names, same primary keys, so switching
is a one-line .env change with no code edits.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
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
    "game_simulations": ["game_id", "sim_version"],
    "live_tracking": ["game_id", "polled_at"],
    "live_simulations": ["game_id", "polled_at"],
    "odds_snapshots": ["game_id", "book", "pulled_at"],
    "clv_log": ["game_id", "model_version", "market"],
    "inactives": ["game_id", "team", "player"],
}

JSON_COLUMNS = {"components", "distributions", "td_scorers", "flags", "recent_scoring", "pregame",
                "start_state", "scorers", "box_score"}


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
        schema = config.SCHEMA_SQLITE.read_text(encoding="utf-8")
        self.conn.executescript(schema)
        self._add_missing_columns(schema)
        self.conn.commit()

    def _add_missing_columns(self, schema: str) -> None:
        """Bring an existing file up to date with the schema.

        `create table if not exists` is a no-op on a table that already exists,
        so a column added to the schema after the mirror was created would
        never appear. Rather than making the developer delete the file, diff
        the declared columns against the live ones and ALTER in the gaps.
        """
        for match in re.finditer(
            r"create table if not exists\s+(\w+)\s*\((.*?)\n\);", schema,
            re.DOTALL | re.IGNORECASE,
        ):
            table, body = match.group(1), match.group(2)
            existing = {
                r["name"] for r in self.conn.execute(f"pragma table_info({table})")
            }
            if not existing:
                continue
            for line in body.split("\n"):
                line = line.strip().rstrip(",")
                if not line or line.startswith("primary key") or line.startswith("--"):
                    continue
                parts = line.split()
                name, decl = parts[0], " ".join(parts[1:])
                if name in existing or name.lower() in ("primary", "unique", "foreign"):
                    continue
                # SQLite cannot ADD COLUMN with a NOT NULL and no default.
                decl = decl.replace("not null", "").strip()
                self.conn.execute(f"alter table {table} add column {name} {decl}")
                print(f"  [migrate] {table}.{name} added to local mirror")

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


# Why a Supabase call failed decides what happens next (P54). A missing table
# (the schema not re-pasted yet) is the one case the local mirror exists for.
# A dropped connection or a timeout says nothing about the table: it is
# retried, and if it keeps failing the run stops loudly. It is never mirrored,
# which would split the data across two stores behind a "table missing" message.
MISSING_TABLE_CODES = {"PGRST205", "42P01"}   # PostgREST schema cache; Postgres undefined_table


def is_missing_table(exc: BaseException) -> bool:
    return getattr(exc, "code", None) in MISSING_TABLE_CODES


def is_transient(exc: BaseException) -> bool:
    import httpx

    return isinstance(exc, httpx.TransportError)


class StoreUnavailable(RuntimeError):
    """A Supabase call that kept failing on the connection (P54)."""


class SupabaseStore(Store):
    backend = "supabase"
    ATTEMPTS = 3
    RETRY_WAIT = (2.0, 5.0)     # seconds before the 2nd and 3rd attempts

    def _execute(self, query, what: str):
        """Run a request, retrying connection errors; anything else raises as is."""
        for attempt in range(1, self.ATTEMPTS + 1):
            try:
                return query.execute()
            except Exception as exc:  # noqa: BLE001 - classified below
                if not is_transient(exc):
                    raise
                if attempt == self.ATTEMPTS:
                    raise StoreUnavailable(
                        f"{what}: {type(exc).__name__} on all {self.ATTEMPTS} attempts ({exc}). "
                        "Not falling back to the local mirror: the table exists, the connection failed (P54)."
                    ) from exc
                print(f"  [retry] {what}: {type(exc).__name__} (attempt {attempt}/{self.ATTEMPTS})")
                time.sleep(self.RETRY_WAIT[attempt - 1])

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
            self._execute(self.client.table(table).upsert(chunk, on_conflict=on_conflict), f"write {table}")
            written += len(chunk)
        return written

    # PostgREST caps every response at a server-side maximum (1000 rows by
    # default) and reports no error when it truncates. Paging is therefore not
    # an optimization here but a correctness requirement: odds and depth_charts
    # both exceed it, and a silently short read degrades features rather than
    # failing, which is far harder to notice.
    PAGE_SIZE = 1000
    READ_ATTEMPTS = 3

    @staticmethod
    def _filtered(query, where: dict[str, Any] | None):
        for k, v in (where or {}).items():
            query = query.in_(k, list(v)) if isinstance(v, (list, tuple)) else query.eq(k, v)
        return query

    def _pages(self, table: str, where: dict[str, Any] | None) -> list[dict]:
        """Every page of a read, sorted by the table's primary key (P53).

        Each OFFSET page is its own query, and without ORDER BY Postgres may
        return rows in a different order each time, so one page can repeat
        rows another skips (seen on injuries: a 66-row overlap, in bursts).
        TABLE_KEYS equals each table's primary key, so the order is total and
        comes off the PK index."""
        keys = TABLE_KEYS.get(table)
        if not keys:
            print(f"  [warn] no key for {table}: paged read is unordered (P53)")
        rows: list[dict] = []
        offset = 0
        while True:
            query = self._filtered(self.client.table(table).select("*"), where)
            for k in keys or ():
                query = query.order(k)
            page = self._execute(query.range(offset, offset + self.PAGE_SIZE - 1), f"read {table}").data
            rows.extend(page)
            if len(page) < self.PAGE_SIZE:
                return rows
            offset += self.PAGE_SIZE

    def select(self, table: str, where: dict[str, Any] | None = None) -> list[dict]:
        """Every matching row. A read that spans pages is checked against the
        server's exact count (P53): unordered pages used to repeat rows other
        pages skipped. On 9/29 that dropped Jayden
        Daniels' `out` row and the sim started him. A short or overlapping read
        is retried, then raised, never returned. `_pages` now orders by primary
        key (the root-cause fix); the check stays because ordering cannot stop
        rows being written between page requests."""
        keys = TABLE_KEYS.get(table)
        for attempt in range(1, self.READ_ATTEMPTS + 1):
            rows = self._pages(table, where)
            if len(rows) < self.PAGE_SIZE:
                return rows            # one page: a single consistent query
            expected = self._execute(self._filtered(
                self.client.table(table).select("*", count="exact", head=True), where), f"count {table}").count
            unique = len({tuple(str(r.get(k)) for k in keys) for r in rows}) if keys else len(rows)
            if expected is None or unique == len(rows) == expected:
                return rows
            print(f"  [P53] incomplete read of {table}: {unique} unique of {len(rows)} rows, "
                  f"server has {expected} (attempt {attempt}/{self.READ_ATTEMPTS})")
        raise IncompleteRead(f"{table}: {unique} unique of {len(rows)} rows read, server has {expected}, "
                             f"after {self.READ_ATTEMPTS} attempts; refusing to continue on partial data (P53)")


class IncompleteRead(RuntimeError):
    """A paged read that could not be made to match the server's count (P53)."""


def get_store() -> Store:
    if config.STORAGE_BACKEND == "supabase":
        return SupabaseStore()
    return SqliteStore()


# Tables that are newer than a hosted project may have: if one is missing
# upstream (the schema file not re-pasted yet), rows go to the local mirror
# rather than failing the run or being lost.
_MIRRORED: set[str] = set()


def upsert_or_mirror(store: Store, table: str, rows: list[dict[str, Any]]) -> str:
    """Write rows; returns the backend they landed in."""
    if not rows:
        return store.backend
    if store.backend == "sqlite":
        store.upsert(table, rows)
        return "sqlite"
    if table not in _MIRRORED:
        try:
            store.upsert(table, rows)
            return store.backend
        except Exception as exc:  # noqa: BLE001
            if not is_missing_table(exc):
                raise                 # P54: only a missing table is mirrored
            _MIRRORED.add(table)
            print(f"  [warn] {table} does not exist in {store.backend} ({exc.code}); "
                  "using the local SQLite mirror.")
            print("         Paste db/PASTE_INTO_SUPABASE.sql into the Supabase SQL Editor to create it.")
    local = SqliteStore()
    try:
        local.upsert(table, rows)
    finally:
        local.close()
    return "sqlite (mirror)"


def select_merged(store: Store, table: str, where: dict[str, Any] | None = None) -> list[dict]:
    """Rows from the configured store, plus any the local mirror holds that it
    lacks (written while the hosted table was missing)."""
    rows: list[dict] = []
    if table not in _MIRRORED or store.backend == "sqlite":
        try:
            rows = store.select(table, where)
        except Exception as exc:  # noqa: BLE001
            if not is_missing_table(exc):
                raise                 # partial read (P53) or connection failure (P54)
            _MIRRORED.add(table)
    if store.backend == "sqlite":
        return rows
    keys = TABLE_KEYS[table]
    seen = {tuple(str(r.get(k)) for k in keys) for r in rows}
    local = SqliteStore()
    try:
        rows += [r for r in local.select(table, where) if tuple(str(r.get(k)) for k in keys) not in seen]
    finally:
        local.close()
    return rows


def stamp(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Tag every raw row with pulled_at, per architecture §2."""
    now = utcnow()
    out = []
    for row in rows:
        row.setdefault("pulled_at", now)
        out.append(row)
    return out
