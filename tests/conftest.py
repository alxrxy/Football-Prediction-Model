"""Make a failed check() fail its test under pytest (P38).

Every test module here reports through a check() helper that prints a failure
and bumps a module-level counter (FAIL, or the FAILED list in test_qb_prior)
without raising. The modules' own runners (python -m tests.<module>) read that
counter and exit 1; pytest never did, so a failed check passed under pytest.

This hook reads the same counter around each test call and fails the test if
it rose. The modules and their runners are untouched. Every check in the test
still runs and prints, so all of its failures show in the captured output,
not just the first.
"""

import pytest


def _failures(module) -> int | None:
    if hasattr(module, "FAIL"):
        return int(module.FAIL)
    if hasattr(module, "FAILED"):
        return len(module.FAILED)
    return None


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    module = item.module
    before = _failures(module)
    if before is None and hasattr(module, "check"):
        # A module with a check() helper but no counter this hook knows would
        # silently pass again; refuse rather than let it opt out.
        raise RuntimeError(f"{module.__name__} has check() but no FAIL / FAILED counter (P38)")
    result = yield
    if before is not None and (after := _failures(module)) > before:
        failed = ""
        if hasattr(module, "FAILED"):
            failed = ": " + ", ".join(map(str, module.FAILED[before:after]))
        pytest.fail(f"{after - before} check(s) failed{failed} (see captured stdout)", pytrace=False)
    return result


@pytest.fixture(autouse=True)
def _raw_rosters_to_tmp(tmp_path, monkeypatch):
    """P68's raw roster logger must never write test fixtures into data/inactives_raw/: tests that call
    ingest_inactives.fetch (test_injury_report and others) would otherwise log their fake reads there."""
    from src import espn_feed_report, inactives_raw

    monkeypatch.setattr(inactives_raw, "RAW_DIR", tmp_path / "inactives_raw")
    monkeypatch.setattr(espn_feed_report, "OUT_DIR", tmp_path / "espn_feed_flags")   # P68 C, same reason
