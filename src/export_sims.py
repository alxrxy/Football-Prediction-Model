"""Per-game simulation detail for the dashboard's game view.

    python -m src.export_sims                          today's slate and the next three
    python -m src.export_sims --dates 2026-09-13 2026-09-20

Writes data/sims.json and dashboard/public/sims.json, read by the game view
behind every NFL row on the dashboard. For each game on each slate:

  pregame   the stored pregame simulation: score distribution, TD/FG counts,
            scorers and the full projected box score. Generate it with
            `python -m src.simulate_nfl --date ...`.
  actual    for finished games, the final score, TD/FG counts and every
            player's line from ESPN's box score, matched onto the projections.
  live      not here: games in progress are read from live.json, which the
            live tracker rewrites every poll.

The live tracker re-runs this whenever a game it follows goes final, so a
finished game's actual result appears without anyone re-exporting by hand.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import date, datetime, timedelta, timezone

from . import config, db
from .features import parse_dt
from .http import safe_get_json
from .ingest_injuries import player_key
from .predict_baseline import SLATE_START_UTC_HOUR, slate_window

SIMS_JSON = config.DATA_DIR / "sims.json"
PUBLIC_SIMS_JSON = config.ROOT / "dashboard" / "public" / "sims.json"
FUTURE_SLATES = 3
FINAL_CACHE_MINUTES = 60 * 24 * 365     # a final box score doesn't change
BROWSER_UA = {"User-Agent": "Mozilla/5.0"}


def _json(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return value


def slate_day(kickoff) -> str | None:
    """Same convention as the predictors: a kickoff before 11:00Z belongs to
    the previous day's slate."""
    k = parse_dt(kickoff)
    return None if k is None else (k - timedelta(hours=SLATE_START_UTC_HOUR)).date().isoformat()


def default_dates(games: list[dict], now: datetime) -> list[str]:
    today = (now - timedelta(hours=SLATE_START_UTC_HOUR)).date().isoformat()
    later = sorted({d for g in games if (d := slate_day(g.get("kickoff_time"))) and d > today})
    return [today] + later[:FUTURE_SLATES]


def _read_all(store, table: str) -> list[dict]:
    """Rows from the configured store plus the local mirror, where runs made
    while the hosted table was missing wrote them."""
    rows = []
    try:
        rows += store.select(table)
    except Exception:  # noqa: BLE001 - table not created upstream yet
        pass
    if store.backend != "sqlite":
        local = None
        try:
            local = db.SqliteStore()
            rows += local.select(table)
        except Exception:  # noqa: BLE001
            pass
        finally:
            if local is not None:
                local.close()
    return rows


def _latest(rows: list[dict], key: str) -> dict[str, dict]:
    best: dict[str, tuple] = {}
    for r in rows:
        gid, when = r.get("game_id"), parse_dt(r.get(key))
        if gid and when and (gid not in best or when > best[gid][0]):
            best[gid] = (when, r)
    return {gid: r for gid, (_, r) in best.items()}


def pregame_view(row: dict, kickoff) -> dict:
    dist = _json(row.get("distributions")) or {}
    comp = _json(row.get("components")) or {}
    made, kick = parse_dt(row.get("generated_at")), parse_dt(kickoff)
    return {
        "sim_version": row.get("sim_version"),
        "n_sims": row.get("n_sims"),
        "generated_at": row.get("generated_at"),
        "after_kickoff": bool(made and kick and made > kick),
        "score_confidence": row.get("score_confidence"),
        "anchor": comp.get("anchor"),
        "anchor_margin_home": row.get("anchor_margin_home"),
        "market_spread": row.get("market_spread"),
        "market_total": row.get("market_total"),
        "home_win_prob": row.get("home_win_prob"),
        "away_win_prob": dist.get("away_win_prob"),
        "tie_prob": row.get("tie_prob"),
        "overtime_prob": dist.get("overtime_prob"),
        "modal": {"home": row.get("modal_home_points"), "away": row.get("modal_away_points"),
                  "prob": row.get("modal_score_prob"), "tied": dist.get("scores_tied_with_mode")},
        "median": {"home": row.get("median_home_points"), "away": row.get("median_away_points")},
        "mean": {"home": row.get("mean_home_points"), "away": row.get("mean_away_points")},
        "home_points": dist.get("home_points"),
        "away_points": dist.get("away_points"),
        "margin": dist.get("margin_home"),
        "total": dist.get("total"),
        "top_scores": dist.get("top_scores"),
        "td": {"home": dist.get("home_td"), "away": dist.get("away_td"),
               "home_mode": row.get("home_td_mode"), "away_mode": row.get("away_td_mode")},
        "fg": {"home": dist.get("home_fg"), "away": dist.get("away_fg"),
               "home_mode": row.get("home_fg_mode"), "away_mode": row.get("away_fg_mode")},
        "scorers": _json(row.get("td_scorers")),
        "box_score": _json(row.get("box_score")),
    }


# --- actual results --------------------------------------------------------

def _espn_day(day: str) -> dict:
    """(home, away) -> LiveState for every ESPN event on a date (US Eastern,
    which matches the slate-day convention for night games)."""
    from .live_tracker import parse_scoreboard

    payload = safe_get_json(f"{config.ESPN_NFL}/scoreboard", params={"dates": day.replace("-", "")},
                            headers=BROWSER_UA, transport="urllib", timeout=15, retries=2)
    states, _ = parse_scoreboard(payload)
    return {(s.home, s.away): s for s in states}


def _line(u: dict) -> dict:
    return {
        "passing": ({"att": u["pass_att"], "cmp": u["pass_cmp"], "yds": u["pass_yds"],
                     "td": u["pass_td"], "int": u["pass_int"]} if u["pass_att"] else None),
        "rushing": {"att": u["car"], "yds": u["rush_yds"], "td": u["rush_td"]} if u["car"] else None,
        "receiving": ({"tgt": u["tgt"], "rec": u["rec"], "yds": u["rec_yds"], "td": u["rec_td"]}
                      if u["tgt"] or u["rec"] else None),
        "td": u["td"],
    }


def actual_result(state) -> dict | None:
    """Final score, TD/FG counts and every player's line for a finished game."""
    from .live_sim import game_usage, scoring_so_far

    summary = safe_get_json(f"{config.ESPN_NFL}/summary", params={"event": state.espn_id},
                            headers=BROWSER_UA, transport="urllib", timeout=15, retries=2,
                            cache_minutes=FINAL_CACHE_MINUTES, cache_tag=f"espn_final_{state.espn_id}")
    if not isinstance(summary, dict):
        return None
    sides = {state.home_id: 0, state.away_id: 1}
    usage = game_usage(summary, sides)
    tds, fgs = scoring_so_far(summary, sides)
    return {
        "home_score": state.home_score, "away_score": state.away_score,
        "td": {"home": tds[0], "away": tds[1]}, "fg": {"home": fgs[0], "away": fgs[1]},
        "players": {"home": list(usage[0].values()), "away": list(usage[1].values())},
    }


def attach_actuals(pregame: dict, actual: dict, home: str, away: str) -> None:
    """Put each player's actual line beside his projection (names matched the
    same suffix-insensitive way as everywhere else), mark which projected
    scorers scored, and list anyone who recorded stats without a projection."""
    box = pregame.get("box_score") or {}
    scorers = pregame.get("scorers") or {}
    actual["scorers"], actual["unprojected"] = {}, {}
    for side, team in (("home", home), ("away", away)):
        lines = {player_key(team, u["name"]): u for u in actual["players"][side]}
        seen = set()
        for p in (box.get(side) or {}).get("players") or []:
            k = player_key(team, p["player"])
            u = lines.get(k)
            p["actual"] = _line(u) if u else {"td": 0, "no_stats": True}
            seen.add(k)
        for sc in scorers.get(side) or []:
            u = lines.get(player_key(team, sc["player"]))
            sc["actual_tds"] = u["td"] if u else 0
        actual["scorers"][side] = [u["name"] for u in lines.values() if u["td"] > 0]
        actual["unprojected"][side] = [
            {"name": u["name"], **_line(u)} for k, u in lines.items()
            if k not in seen and u["car"] + u["tgt"] + u["pass_att"] > 0
        ]


# --- assembly --------------------------------------------------------------

def build(dates: list[str] | None = None, store=None) -> dict:
    from .live_sim import LIVE_SIM_VERSION

    own_store = store is None
    store = store or db.get_store()
    games = store.select("games", {"sport": "nfl"})
    now = datetime.now(timezone.utc)
    dates = dates or default_dates(games, now)
    today = (now - timedelta(hours=SLATE_START_UTC_HOUR)).date().isoformat()

    sims = _latest(_read_all(store, "game_simulations"), "generated_at")
    lives = _latest([r for r in _read_all(store, "live_simulations")
                     if r.get("sim_version") == LIVE_SIM_VERSION], "polled_at")

    slates = []
    for day in dates:
        start, end = slate_window(date.fromisoformat(day))
        day_games = sorted(
            (g for g in games if (k := parse_dt(g.get("kickoff_time"))) and start <= k < end),
            key=lambda g: g["kickoff_time"],
        )
        if not day_games:
            continue
        espn = _espn_day(day) if day <= today else {}
        entries = []
        for g in day_games:
            state = espn.get((g["home_team"], g["away_team"]))
            if state is not None:
                status = {"post": "final", "in": "live"}.get(state.state, "scheduled")
            else:
                status = "final" if g.get("completed") else "scheduled"
            row = sims.get(g["game_id"])
            pre = pregame_view(row, g.get("kickoff_time")) if row else None

            actual = actual_result(state) if state is not None and state.state == "post" else None
            if actual is None and status == "final" and g.get("home_points") is not None:
                actual = {"home_score": g["home_points"], "away_score": g["away_points"]}
            if actual and actual.get("players"):
                if pre:
                    attach_actuals(pre, actual, g["home_team"], g["away_team"])
                else:
                    # Nothing to match onto, but the result still belongs on screen.
                    actual["scorers"] = {s: [u["name"] for u in actual["players"][s] if u["td"] > 0]
                                         for s in ("home", "away")}
                    actual["unprojected"] = {s: [{"name": u["name"], **_line(u)} for u in actual["players"][s]
                                                 if u["car"] + u["tgt"] + u["pass_att"] > 0]
                                             for s in ("home", "away")}
                actual.pop("players", None)

            live = lives.get(g["game_id"])
            entries.append({
                "game_id": g["game_id"],
                "espn_id": state.espn_id if state else None,
                "home": g["home_team"], "away": g["away_team"],
                "kickoff": g.get("kickoff_time"),
                "status": status,
                "detail": state.detail if state else None,
                "score": ({"home": state.home_score, "away": state.away_score}
                          if state is not None and state.state != "pre" else None),
                "pregame": pre,
                "actual": actual,
                "live_last": ({k: live.get(k) for k in ("polled_at", "elapsed_minutes", "home_win_prob",
                                                        "mean_margin_home", "median_home_points",
                                                        "median_away_points")} if live else None),
            })
        slates.append({"date": day, "games": entries})

    if own_store:
        store.close()
    return {"generated_at": now.isoformat(), "slates": slates}


def run(dates: list[str] | None = None, quiet: bool = False) -> str:
    payload = build(dates)
    config.ensure_dirs()
    SIMS_JSON.write_text(json.dumps(payload, default=str), encoding="utf-8")
    if PUBLIC_SIMS_JSON.parent.exists():
        shutil.copy(SIMS_JSON, PUBLIC_SIMS_JSON)
    if not quiet:
        for s in payload["slates"]:
            simulated = sum(1 for g in s["games"] if g["pregame"])
            finals = sum(1 for g in s["games"] if g["status"] == "final")
            print(f"  {s['date']}: {len(s['games'])} games | {simulated} simulated | {finals} final")
        print(f"  wrote {SIMS_JSON}")
    return str(SIMS_JSON)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export per-game simulation detail for the dashboard.")
    parser.add_argument("--dates", nargs="*", help="slate dates, YYYY-MM-DD (default: today and the next three)")
    args = parser.parse_args()
    run(args.dates or None)
