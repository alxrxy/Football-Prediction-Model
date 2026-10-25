"""Stale ESPN inactive-list detector, WARN-ONLY (user-approved 2026-10-25; Step-3 entry in calibration-log.md).

On 2026-10-18 and 2026-10-25 ESPN served the previous week's inactive lists as if they were this week's. A list
is flagged when any of these holds:
  (a) it was read more than EARLY_MINUTES before kickoff: lists post at T-90 min, so it cannot be this week's;
  (b) it holds every name on the team's previous stored list (a superset; empty previous lists never match);
  (c) it has more than MAX_NAMES names.
Warn-only: the reasons are reported and logged; nothing is skipped and no stored row changes. Called from the
P33 probe (`probe_inactives`), which writes only under data/inactives_probe/.
"""

from __future__ import annotations

EARLY_MINUTES = 95
MAX_NAMES = 7


def stale_reasons(names: list[str], lead_minutes: float | None, previous: list[str] | None) -> list[str]:
    """Why this list looks stale; empty when none applies. `names` and `previous` are normalised player keys."""
    if not names:
        return []
    out = []
    if lead_minutes is not None and lead_minutes > EARLY_MINUTES:
        out.append(f"read {lead_minutes:.0f} min before kickoff (lists post at T-90)")
    prev = set(previous or [])
    if prev and prev <= set(names):
        out.append(f"superset of the previous list ({len(prev)}/{len(prev)} kept, {len(set(names) - prev)} added)")
    if len(set(names)) > MAX_NAMES:
        out.append(f"{len(set(names))} names (more than {MAX_NAMES})")
    return out


def previous_lists(rows: list[dict], season: int, week: int) -> dict[str, list[str]]:
    """team -> the player keys of its latest stored list from an earlier week of this season."""
    from .ingest_injuries import player_key

    best: dict[str, int] = {}
    for r in rows:
        if r.get("season") == season and (r.get("week") or 0) < week:
            best[r["team"]] = max(best.get(r["team"], 0), r["week"])
    out: dict[str, list[str]] = {}
    for r in rows:
        if r.get("season") == season and best.get(r["team"]) == r.get("week"):
            out.setdefault(r["team"], []).append(player_key(r["team"], r["player"]))
    return out
