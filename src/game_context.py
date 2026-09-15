"""Compact per-game context for the Claude Q&A (src/api_server.py).

Claude is billed by the token, so a question carries only that game's
numbers, as a few dozen lines of plain text: the exported JSON behind one NFL
game runs to thousands of tokens, most of it distributions nobody asks about.

Read from the dashboard's own exports, so the server needs no database:
  data/dashboard.json  prediction, market, baseline pieces, injuries (both sports)
  data/sims.json       pregame simulation and, once final, the result (NFL)
  data/props.json      ranked props (NFL)
  data/live.json       live state and live re-projection, while a game is on
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import config

DASHBOARD_JSON = config.DATA_DIR / "dashboard.json"
SIMS_JSON = config.DATA_DIR / "sims.json"
PROPS_JSON = config.DATA_DIR / "props.json"
LIVE_JSON = config.DATA_DIR / "live.json"

_cache: dict[Path, tuple[float, object]] = {}


def _load(path: Path):
    """JSON file contents, re-read only when the file changes."""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    hit = _cache.get(path)
    if hit and hit[0] == mtime:
        return hit[1]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    _cache[path] = (mtime, data)
    return data


# --- formatting --------------------------------------------------------------

def _pct(v) -> str:
    return "?" if v is None else f"{round(float(v) * 100)}%"


def _n(v, digits: int = 0) -> str:
    return "?" if v is None else f"{float(v):.{digits}f}"


def _spread(s, home: str, away: str) -> str:
    if s is None:
        return "?"
    s = float(s)
    return "pick'em" if abs(s) < 0.05 else f"{home if s < 0 else away} -{abs(s):.1f}"


def _range(q: dict | None, digits: int = 0) -> str:
    if not q:
        return "?"
    mid = q.get("median", q.get("p50"))
    return (f"median {_n(mid, digits)}, middle 50% {_n(q.get('p25'), digits)} to {_n(q.get('p75'), digits)}, "
            f"80% {_n(q.get('p10'), digits)} to {_n(q.get('p90'), digits)}")


def _key_players(box: dict | None, side: str, team: str, live: bool = False) -> list[str]:
    """The quarterback, top two backs and top three receivers: the lines people ask about."""
    players = ((box or {}).get(side) or {}).get("players") or []

    def volume(p, group, stat):
        return -(((p.get(group) or {}).get(stat) or {}).get("mean") or 0)

    picks = []
    picks += sorted((p for p in players if p.get("passing")), key=lambda p: volume(p, "passing", "att"))[:1]
    picks += sorted((p for p in players if p.get("rushing") and p not in picks),
                    key=lambda p: volume(p, "rushing", "att"))[:2]
    picks += sorted((p for p in players if p.get("receiving") and p not in picks),
                    key=lambda p: volume(p, "receiving", "tgt"))[:3]
    out = []
    for p in picks:
        parts = []
        if p.get("passing"):
            parts.append(f"pass yds {_range(p['passing'].get('yds'))}")
        if p.get("rushing"):
            parts.append(f"rush yds {_range(p['rushing'].get('yds'))}")
        if p.get("receiving"):
            rec = (p["receiving"].get("rec") or {}).get("median")
            parts.append(f"rec {_n(rec, 1)}, rec yds {_range(p['receiving'].get('yds'))}")
        so_far = p.get("so_far")
        sf = f" | so far: {', '.join(f'{k} {v}' for k, v in so_far.items())}" if live and so_far else ""
        out.append(f"  {team} {p['player']} ({p.get('position') or ''}{p.get('depth_rank') or ''}): "
                   f"{'; '.join(parts)}{sf}")
    return out


# --- pregame -----------------------------------------------------------------

def pregame_text(game: dict | None, sim: dict | None, props: list[dict], sport: str = "") -> str:
    lines: list[str] = []
    home = (game or sim or {}).get("home")
    away = (game or sim or {}).get("away")
    if game:
        lines.append(f"{sport} game: {away} at {home}{' (neutral site)' if game.get('neutral') else ''}, "
                     f"kickoff {game.get('kickoff')} (UTC). Spreads are home lines: negative = home favoured.")
        m = game.get("market") or {}
        if m.get("spread") is not None:
            lines.append(f"Market: {_spread(m['spread'], home, away)}, total {_n(m.get('total'), 1)}.")
        for key, label in (("baseline", "Baseline model"), ("ml", "ML model")):
            p = game.get(key)
            if not p:
                continue
            lines.append(
                f"{label}: {_spread(p.get('model_spread'), home, away)} ({home} margin {_n(p.get('margin_home'), 1)}), "
                f"{home} win {_pct(p.get('win_prob_home'))}, points off the market {_n(p.get('edge'), 1)} "
                f"(+ favours {home}), confidence {p.get('confidence')}"
                + ("; flagged as unvalidated value" if p.get("is_value") else "") + "."
            )
        b = game.get("baseline") or {}
        me = b.get("market_edge") or {}
        if me:
            lines.append(
                f"Stage 1 value test (model blended with the devigged market at weight {me.get('weight')}): "
                f"{me.get('side')} side {_pct(me.get('p_side_blend'))} to cover vs {_pct(me.get('breakeven'))} "
                f"break-even; {'passes' if me.get('flag') else 'does not pass'} (needs 3+ points past break-even)."
            )
        layers, l1 = b.get("layers") or {}, b.get("layer1") or {}
        if l1 or layers:
            lines.append(
                f"Baseline pieces ({home} points): rating difference {_n(l1.get('baseline_margin'), 1)} "
                f"({l1.get('source')}), home field {_n(layers.get('home_field'), 1)}, rest {_n(layers.get('rest'), 1)}, "
                f"travel {_n(layers.get('travel'), 1)}, injuries {_n(layers.get('injury'), 1)}"
                + (f", wind factor {layers.get('wind_factor')}" if layers.get("wind_factor") not in (None, 1) else "")
                + "."
            )
        for side, team in (("away", away), ("home", home)):
            hurt = sorted((game.get("injuries") or {}).get(side) or [], key=lambda i: -(i.get("points") or 0))[:4]
            if hurt:
                lines.append(f"{team} injuries charged: " + "; ".join(
                    f"{i.get('player')} {i.get('position')} {i.get('status') or ''} ({_n(i.get('points'), 2)} pts)"
                    for i in hurt))
    pre = (sim or {}).get("pregame")
    if pre:
        med, mg, tot = pre.get("median") or {}, pre.get("margin") or {}, pre.get("total") or {}
        lines.append(
            f"Simulation ({pre.get('n_sims')} runs, centred on the baseline margin): median final "
            f"{away} {_n(med.get('away'))} - {_n(med.get('home'))} {home}; {home} win {_pct(pre.get('home_win_prob'))}; "
            f"margin ({home}) {_range(mg)}; total {_range(tot)}."
        )
        sc = pre.get("scorers") or {}
        for side, team in (("away", away), ("home", home)):
            if sc.get(side):
                lines.append(f"{team} likeliest TD scorers: "
                             + ", ".join(f"{s['player']} {_pct(s.get('anytime_td'))}" for s in sc[side][:3]))
        if pre.get("box_score"):
            lines.append("Key player projections (simulated, lower confidence than the score):")
            for side, team in (("away", away), ("home", home)):
                lines += _key_players(pre["box_score"], side, team)
    act = (sim or {}).get("actual")
    if act and act.get("home_score") is not None:
        lines.append(f"FINAL: {away} {act['away_score']} - {act['home_score']} {home}."
                     + (f" TD scorers: {away} {', '.join(act['scorers'].get('away') or []) or 'none'}; "
                        f"{home} {', '.join(act['scorers'].get('home') or []) or 'none'}." if act.get("scorers") else ""))
    for p in props[:4]:
        lines.append(f"Ranked prop #{p.get('rank')}: {p['player']} {p['label']} {p['pick']} {p['line']} "
                     f"({p.get('price')}): simulation {_pct(p.get('p_model'))} vs market {_pct(p.get('p_market'))}.")
    return "\n".join(lines)


# --- live ----------------------------------------------------------------------

def live_text(lg: dict) -> str:
    home, away = lg.get("home"), lg.get("away")
    lines = [f"LIVE: {away} {lg.get('away_score')} - {lg.get('home_score')} {home}, {lg.get('detail')}"
             + (f"; {lg['possession']} ball" if lg.get("possession") else "")
             + (f", {lg['down_distance']}" if lg.get("down_distance") else "")
             + (", in the red zone" if lg.get("red_zone") else "") + "."]
    s = lg.get("live_sim") or {}
    if s:
        lines.append(
            f"Live model (re-simulated {s.get('n_sims')} times from this exact state, same team strengths as "
            f"pregame, {_n(s.get('minutes_left'))} min left): {home} win {_pct(s.get('home_win_prob'))} "
            f"(pregame {_pct(s.get('pregame_win_prob_home'))}); projected final median {away} "
            f"{_n(s.get('median_away_points'))} - {_n(s.get('median_home_points'))} {home}; margin ({home}) "
            f"80% {_n(s.get('margin_80_low'))} to {_n(s.get('margin_80_high'))} (pregame margin "
            f"{_n(s.get('pregame_margin_home'), 1)}); total median {_n(s.get('total_median'))}, "
            f"80% {_n(s.get('total_80_low'))}-{_n(s.get('total_80_high'))}."
        )
    if lg.get("espn_home_wp") is not None:
        lines.append(f"ESPN's win probability: {home} {_pct(lg['espn_home_wp'])}.")
    for f in (lg.get("flags") or [])[:3]:
        if isinstance(f, dict) and f.get("message"):
            lines.append(f"Tracker flag: {f['message']}")
    scoring = [r.get("text") or r.get("description") or "" if isinstance(r, dict) else str(r)
               for r in (lg.get("recent_scoring") or [])[-4:]]
    if any(scoring):
        lines.append("Recent scoring: " + " | ".join(x for x in scoring if x))
    if s.get("box_score"):
        lines.append("Key players, projected finals (stats so far plus the simulated rest):")
        for side, team in (("away", away), ("home", home)):
            lines += _key_players(s["box_score"], side, team, live=True)
    return "\n".join(lines)


# --- lookup --------------------------------------------------------------------

LIVE_FRESH_SECONDS = 600


def live_feed() -> dict | None:
    """live.json, but only while the tracker is actually writing it. A stopped
    tracker leaves its last snapshot behind, and that can still call a game
    "in progress" days after it ended."""
    feed = _load(LIVE_JSON) or {}
    try:
        written = datetime.fromisoformat(str(feed.get("generated_at")).replace("Z", "+00:00"))
    except ValueError:
        return None
    if written.tzinfo is None:
        written = written.replace(tzinfo=timezone.utc)
    return feed if (datetime.now(timezone.utc) - written).total_seconds() < LIVE_FRESH_SECONDS else None


def props_text() -> str | None:
    """This week's ranked props, one line each, for questions about the list."""
    d = _load(PROPS_JSON) or {}
    if not d.get("props"):
        return None
    lines = [
        f"NFL week {d.get('week')} player props, lines pulled {d.get('lines_pulled_at')}. Each prop compares the "
        f"game simulation's chance of the pick with the market's vig-free chance (over/under devigged across "
        f"books), ranked by the gap. Gaps past {round((d.get('max_gap') or 0.25) * 100)} points are held out as "
        f"likely usage misses. Known bias (calibration log P17): the simulator gives every player league-typical "
        f"yards per catch and carry and splits targets by depth-chart share, so star receivers tend to project "
        f"under their lines; a big gap is often that bias rather than value. None of these are validated."
    ]
    for p in d["props"]:
        s = p.get("sim") or {}
        lines.append(
            f"#{p.get('rank')} {p['player']} ({p['team']} {p.get('position')}, {p.get('game')}): {p['label']} "
            f"{p['pick']} {p['line']} at {p.get('price')} ({p.get('book')}, {p.get('books')} books); simulation "
            f"{_pct(p.get('p_model'))} vs market {_pct(p.get('p_market'))}, gap +{_n((p.get('gap') or 0) * 100, 1)} pts; "
            f"sim median {s.get('median')} (middle 50% {s.get('p25')}-{s.get('p75')}); "
            f"{'passes' if p.get('passes_stage1') else 'does not pass'} the Stage 1 test."
            + (f" Alt line: {p['pick']} {alt['line']} at {alt['price']} ({alt['book']}), simulation "
               f"{_pct(alt['p_model'])}." if (alt := p.get("alt")) else "")
        )
    if d.get("more"):
        lines.append(f"{len(d['more'])} more props rank below these (smaller gaps).")
    held = d.get("held_out") or []
    if held:
        lines.append("Held out: " + "; ".join(
            f"{h['player']} {h['label']} {h['pick']} {h['line']} (sim {_pct(h.get('p_model'))} vs "
            f"market {_pct(h.get('p_market'))})" for h in held[:6]))
    return "\n".join(lines)


def build(game_id: str) -> dict | None:
    """{mode, text} for a game, or None when no export knows it."""
    feed = live_feed() or {}
    live = next((g for g in feed.get("games") or [] if g.get("game_id") == game_id), None)
    if live and live.get("state") == "in":
        return {"mode": "live", "text": live_text(live)}

    game, sport = None, ""
    for s in (_load(DASHBOARD_JSON) or {}).get("sports") or []:
        game = next((g for g in s.get("games") or [] if g.get("game_id") == game_id), None)
        if game:
            sport = s.get("label", "")
            break
    sim = next((g for sl in (_load(SIMS_JSON) or {}).get("slates") or [] for g in sl.get("games") or []
                if g.get("game_id") == game_id), None)
    if game is None and sim is None:
        return None
    props = [p for p in (_load(PROPS_JSON) or {}).get("props") or [] if p.get("game_id") == game_id]
    mode = "final" if sim and sim.get("status") == "final" else "pregame"
    return {"mode": mode, "text": pregame_text(game, sim, props, sport or "NFL")}
