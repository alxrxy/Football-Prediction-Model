"""The pipeline must run without ODDS_API_KEY, and default to the NFL (2026-11-20)."""

from __future__ import annotations

import run_pipeline
from src import config, ingest_odds


def test_missing_odds_key_skips_lines_with_a_warning(monkeypatch, capsys):
    monkeypatch.setattr(config, "ODDS_API_KEY", "")

    def no_network(*a, **k):
        raise AssertionError("no request may be made without a key")

    def no_store():
        raise AssertionError("the store must not be opened when lines are skipped")

    monkeypatch.setattr(ingest_odds, "get_json", no_network)
    monkeypatch.setattr(ingest_odds.db, "get_store", no_store)
    assert ingest_odds.run("nfl") == 0                       # returns; it used to raise SystemExit
    out = capsys.readouterr().out
    assert "ODDS_API_KEY is not set" in out and "SKIPPED" in out


def test_pipeline_defaults_to_nfl():
    assert run_pipeline.build_parser().parse_args([]).sport == "nfl"
    assert run_pipeline.build_parser().parse_args(["--sport", "ncaaf"]).sport == "ncaaf"
