"""P54: a connection failure is retried and then raised; only a genuinely
missing table falls back to the local SQLite mirror.

    python -m tests.test_p54
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

import httpx
from postgrest.exceptions import APIError

from src import db, export_sims
from src.db import StoreUnavailable, SupabaseStore

PASS, FAIL = 0, 0


def check(label: str, got, want) -> None:
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got {got!r}, want {want!r}")


def missing() -> APIError:
    # The exact error Supabase returned for a table that doesn't exist (probed 2026-09-29).
    return APIError({"code": "PGRST205", "message": "Could not find the table 'public.x' in the schema cache"})


def connect() -> httpx.ConnectError:
    return httpx.ConnectError("connection dropped")


class Query:
    """execute() raises each scripted error in turn, then returns `result`."""

    def __init__(self, errors, result="ok"):
        self.errors, self.result, self.calls = list(errors), result, 0

    def execute(self):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return self.result


def store() -> SupabaseStore:
    s = object.__new__(SupabaseStore)
    s.RETRY_WAIT = (0.0, 0.0)
    return s


class FakeLocal:
    """Stands in for the local SQLite mirror and records what reaches it."""
    written: list = []

    def upsert(self, table, rows):
        FakeLocal.written.append((table, len(rows)))

    def select(self, table, where=None):
        return []

    def close(self):
        pass


class FailingStore:
    backend = "supabase"

    def __init__(self, exc):
        self.exc = exc

    def upsert(self, table, rows):
        raise self.exc

    def select(self, table, where=None):
        raise self.exc


def with_fake_local(fn):
    real = db.SqliteStore
    db.SqliteStore = FakeLocal
    FakeLocal.written = []
    db._MIRRORED.discard("game_simulations")
    try:
        return fn()
    finally:
        db.SqliteStore = real
        db._MIRRORED.discard("game_simulations")


def test_classification():
    check("PGRST205 is a missing table", db.is_missing_table(missing()), True)
    check("Postgres 42P01 is a missing table", db.is_missing_table(APIError({"code": "42P01"})), True)
    check("a connection error is not a missing table", db.is_missing_table(connect()), False)
    check("another API error is not a missing table", db.is_missing_table(APIError({"code": "23505"})), False)
    check("a connection error is transient", db.is_transient(connect()), True)
    check("a timeout is transient", db.is_transient(httpx.ReadTimeout("slow")), True)
    check("a missing table is not transient", db.is_transient(missing()), False)


def test_retry_then_success():
    q = Query([connect(), connect()])
    check("recovers on the third attempt", store()._execute(q, "write t"), "ok")
    check("three attempts", q.calls, 3)


def test_retry_exhausted_raises_loudly():
    q = Query([connect()] * 3)
    try:
        store()._execute(q, "write game_simulations")
        check("raises StoreUnavailable", False, True)
    except StoreUnavailable as exc:
        check("raises StoreUnavailable", True, True)
        check("message says it was not mirrored", "Not falling back to the local mirror" in str(exc), True)
    check("stopped after three attempts", q.calls, 3)


def test_missing_table_not_retried():
    q = Query([missing()])
    try:
        store()._execute(q, "read t")
    except APIError as exc:
        check("missing table raised as is", exc.code, "PGRST205")
    check("no retry for a missing table", q.calls, 1)


def test_write_connection_failure_not_mirrored():
    def run():
        try:
            db.upsert_or_mirror(FailingStore(StoreUnavailable("down")), "game_simulations", [{"game_id": "g"}])
            check("connection failure raises", False, True)
        except StoreUnavailable:
            check("connection failure raises", True, True)
        check("nothing written to the local mirror", FakeLocal.written, [])
        check("table not marked as mirrored", "game_simulations" in db._MIRRORED, False)
    with_fake_local(run)


def test_write_missing_table_mirrored():
    def run():
        where = db.upsert_or_mirror(FailingStore(missing()), "game_simulations", [{"game_id": "g"}])
        check("missing table goes to the mirror", where, "sqlite (mirror)")
        check("rows reached the mirror", FakeLocal.written, [("game_simulations", 1)])
    with_fake_local(run)


def test_read_paths():
    def run():
        try:
            db.select_merged(FailingStore(StoreUnavailable("down")), "game_simulations")
            check("select_merged raises on a connection failure", False, True)
        except StoreUnavailable:
            check("select_merged raises on a connection failure", True, True)
        check("select_merged did not mark it mirrored", "game_simulations" in db._MIRRORED, False)
        check("select_merged on a missing table falls back",
              db.select_merged(FailingStore(missing()), "game_simulations"), [])
        try:
            export_sims._read_all(FailingStore(StoreUnavailable("down")), "game_simulations")
            check("export_sims raises on a connection failure", False, True)
        except StoreUnavailable:
            check("export_sims raises on a connection failure", True, True)
        check("export_sims on a missing table reads the mirror",
              export_sims._read_all(FailingStore(missing()), "game_simulations"), [])
    with_fake_local(run)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(name)
            fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
