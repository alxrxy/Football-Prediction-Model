"""ESPN injury-feed health guard (feed repair, 2026-11-19)."""

from __future__ import annotations

from datetime import datetime, timezone

from src.ingest_injuries import espn_feed_health

NOW = datetime(2026, 10, 25, 16, 0, tzinfo=timezone.utc)


def row(week, pulled, source="espn"):
    return {"source": source, "season": 2026, "week": week, "pulled_at": pulled}


def test_the_october_gap_is_flagged_stale():
    # Week 7 refresh on 10/25: the newest ESPN pull is the week-6 one from 10/18.
    stored = [row(6, "2026-10-18T16:00:00+00:00"), row(7, "2026-10-25T15:00:00+00:00", "nflverse")]
    h = espn_feed_health(stored, 2026, 7, fresh_rows=0, now=NOW)
    assert h["stale"] and h["newest_week"] == 6 and h["age_days"] == 7.0


def test_a_current_week_pull_is_fresh():
    stored = [row(6, "2026-10-18T16:00:00+00:00"), row(7, "2026-10-25T15:30:00+00:00")]
    h = espn_feed_health(stored, 2026, 7, fresh_rows=120, now=NOW)
    assert not h["stale"] and h["newest_week"] == 7


def test_an_empty_answer_is_stale_even_with_current_rows_stored():
    stored = [row(7, "2026-10-25T15:30:00+00:00")]
    assert espn_feed_health(stored, 2026, 7, fresh_rows=0, now=NOW)["stale"]


def test_no_espn_rows_at_all_is_stale():
    assert espn_feed_health([row(7, "2026-10-25T15:00:00+00:00", "nflverse")], 2026, 7, fresh_rows=0, now=NOW)["stale"]
