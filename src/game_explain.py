"""Plain-language "why the model leans this way" notes for each NFL game.

    python -m src.game_explain              print today's notes (no dashboard write)
    python -m src.game_explain --factors    print the factor breakdowns only, no Claude call

Display only. Nothing here changes a prediction: it reads the baseline's stored
components, splits the served margin into the factors that produced it, and
asks Claude to put those factors into two or three sentences.

Two guards keep a note tied to the number it explains:
  - the factors must add back up to the served margin (to 0.05 pts), or the
    game gets no note; a breakdown that doesn't reconcile would be explaining
    some other number
  - every figure in Claude's text must appear in the numbers it was given, or
    the note is dropped; a paraphrase is fine, an invented number is not

Same call pattern as the prop explanations (src/props.py): one call for the
whole slate through claude_ai.ask, cached by the exact input, so a re-export
with unchanged numbers costs nothing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone

from . import config, db
from .features import parse_dt

# ingest_nflverse: power_rating = (off EPA/play - def EPA/play) * PLAYS_PER_GAME,
# and the prior season is weighted as PRIOR_PLAYS_WEIGHT plays.
from .ingest_nflverse import PLAYS_PER_GAME, PRIOR_PLAYS_WEIGHT

RECONCILE_TOL = 0.05
# Injured players worth naming: the rest are folded into the side's total.
NAME_INJURY_PTS = 0.3
# Below this the served margin is called a toss-up rather than a lean.
TOSS_UP_PTS = 1.0
# A game whose baseline win probability shows as 45-55% (rounded, as the page
# shows it) is a close game: its note says why it is close, not just the lean.
CLOSE_WIN_PROB = (45, 55)

SYSTEM = (
    "You write short explanations for a personal NFL prediction page. Each game comes with the model's "
    "predicted margin and the factors that add up to it, already computed. For each game write two to "
    "four plain-English sentences a casual fan can follow: which team the model favours and by how much, "
    "the one or two factors that drive that most, and anything pulling the other way. If the model and the "
    "market line differ by 3 points or more, say so in one clause, without claiming to know why the market "
    "differs. If caveats are listed, work the most relevant one in briefly, in plain words. "
    "Rules: use only the numbers given, rounded as given; do not add any other figure; give a play "
    "probability as the percentage shown, never as 'coin-flip' or similar; describe a player's status only as "
    "it is given next to that player's name, and never move a caveat from one player to another; don't judge "
    "how reliable a factor is beyond what a caveat says; call the team rating "
    "a 'team rating' or 'rating gap', never 'opponent-adjusted'; never recommend a bet, never say 'lock' or "
    "'value'; no hype. "
    "For a game marked 'close game', explain why it is close rather than only stating the lean: name the "
    "factor or factors favouring the model's side and the factor or factors offsetting them, in the form "
    "'the rating gap favours X, but Y pulls the other way', using only the factors given. If nothing pulls "
    "the other way, say that the factors favouring the lean are all small."
)
SCHEMA = {
    "type": "object",
    "properties": {"explanations": {"type": "array", "items": {
        "type": "object",
        "properties": {"game_id": {"type": "string"}, "text": {"type": "string"}},
        "required": ["game_id", "text"], "additionalProperties": False}}},
    "required": ["explanations"], "additionalProperties": False,
}


# --- factors ---------------------------------------------------------------

def _ratings(store, season: int) -> dict[str, dict]:
    """Each team's latest stored rating row this season."""
    latest: dict[str, dict] = {}
    for r in store.select("team_ratings", {"sport": "nfl", "season": season}):
        if r["team"] not in latest or int(r["week"]) > int(latest[r["team"]]["week"]):
            latest[r["team"]] = r
    return latest


def prior_share(store, season: int) -> float | None:
    """Roughly how much of each rating is still last season, as ingest_nflverse weights it."""
    done = [g for g in store.select("games", {"sport": "nfl", "season": season}) if g.get("completed")]
    if not done:
        return None
    per_team = len(done) * 2 / 32 * PLAYS_PER_GAME
    return PRIOR_PLAYS_WEIGHT / (PRIOR_PLAYS_WEIGHT + per_team)


def _possible_duplicates(injuries: list[dict]) -> list[str]:
    """Two injury rows for one side with the same surname and position (P43's nickname miss)."""
    seen: dict[tuple[str, str], str] = {}
    pairs = []
    for i in injuries:
        name = re.sub(r"\b(Jr|Sr|II|III|IV)\.?$", "", i["player"].strip()).strip()
        key = (name.split()[-1].lower() if name else "", i.get("position") or "")
        if key in seen and seen[key] != i["player"]:
            pairs.append(f"{seen[key]} / {i['player']}")
        seen.setdefault(key, i["player"])
    return pairs


def factors(game: dict, ratings: dict[str, dict] | None = None, prior: float | None = None) -> dict | None:
    """The served baseline margin split into additive factors, home-team points.

    None when there's no baseline breakdown, or when the parts don't add back up
    to the served margin.
    """
    base = game.get("baseline") or {}
    layers, layer1 = base.get("layers"), base.get("layer1")
    margin = base.get("margin_home")
    if not layers or not layer1 or margin is None or layer1.get("baseline_margin") is None:
        return None
    home, away = game["home"], game["away"]

    rating_gap = layer1["baseline_margin"]
    parts = {
        "rating_gap": rating_gap,
        "home_field": layers.get("home_field") or 0.0,
        "rest": layers.get("rest") or 0.0,
        "travel": layers.get("travel") or 0.0,
        "injuries": layers.get("injury") or 0.0,
    }
    adjusted = sum(parts.values())
    wind_factor = layers.get("wind_factor") or 1.0
    parts["weather"] = round(adjusted * wind_factor - adjusted, 2)
    if abs(sum(parts.values()) - margin) > RECONCILE_TOL:
        return None

    out = {
        "home": home, "away": away,
        "favoured": home if margin > 0 else away,
        "margin_home": round(margin, 1),
        "toss_up": abs(margin) < TOSS_UP_PTS,
        "win_prob_home": base.get("win_prob_home"),
        "close": (base.get("win_prob_home") is not None
                  and CLOSE_WIN_PROB[0] <= round(base["win_prob_home"] * 100) <= CLOSE_WIN_PROB[1]),
        "parts": {k: round(v, 1) for k, v in parts.items()},
        "rest_days": {home: layers.get("home_rest_days"), away: layers.get("away_rest_days")},
        "away_travel_miles": layers.get("away_travel_miles"),
        "wind_mph": layers.get("wind_mph"),
        "neutral": bool(game.get("neutral")),
        "injury_points": {home: layers.get("home_injury_points"), away: layers.get("away_injury_points")},
        "injured": {},
        "caveats": [],
    }

    # The rating gap, split into offence and defence (the centring cancels in a difference).
    rh, ra = (ratings or {}).get(home), (ratings or {}).get(away)
    if rh and ra and None not in (rh.get("off_epa"), ra.get("off_epa"), rh.get("def_epa"), ra.get("def_epa")):
        off = (rh["off_epa"] - ra["off_epa"]) * PLAYS_PER_GAME
        dfn = (ra["def_epa"] - rh["def_epa"]) * PLAYS_PER_GAME
        if abs(off + dfn - rating_gap) <= 0.1:
            out["rating_split"] = {"offence": round(off, 1), "defence": round(dfn, 1)}

    for side, team in (("home", home), ("away", away)):
        rows = (game.get("injuries") or {}).get(side) or []
        out["injured"][team] = [
            {"player": i["player"], "position": i.get("position"), "points": round(i["points"], 1),
             "status": i.get("status"),
             "practice": f"{i['practice']} in practice" if i.get("practice") else "no practice report",
             "play_prob": i.get("play_prob")}
            for i in rows if (i.get("points") or 0) >= NAME_INJURY_PTS
        ][:3]
        for i in rows:
            if i.get("position") == "QB" and (i.get("points") or 0) >= 1.0:
                out["caveats"].append(
                    f"The {i['points']:.1f}-point charge for {team} QB {i['player']} is a generic value "
                    "scaled by his snap share, not a comparison with the quarterback who replaces him.")
        # Only a questionable tag with no practice report behind it is the flat
        # default. Questionable + limited practice is also 0.55, but that value
        # comes from the practice table (ingest_injuries.PLAY_PROBABILITY).
        flat = [i["player"] for i in rows if i.get("status") == "questionable" and not i.get("practice")
                and i.get("play_prob") == 0.55 and (i.get("points") or 0) >= NAME_INJURY_PTS]
        if flat:
            out["caveats"].append(
                f"{', '.join(flat)} ({team}, questionable) {'is' if len(flat) == 1 else 'are'} priced at a "
                "flat 55% chance to play, the default for any questionable player.")
        for pair in _possible_duplicates(rows):
            out["caveats"].append(
                f"{team}'s injury list may count one player twice ({pair}); a known feed issue (P43).")

    if prior is not None:
        out["caveats"].append(
            # Rounded to 10%: this counts games, the rating itself counts plays.
            f"Team ratings are still about {round(prior, 1):.0%} last season's play and are not "
            "adjusted for opponents.")
    if game.get("known_issue"):
        out["caveats"].append(game["known_issue"])

    mkt = base.get("market_spread")
    if mkt is not None:
        out["market_margin_home"] = round(-mkt, 1)
        out["gap_to_market"] = round(margin + mkt, 1)
    ml = game.get("ml") or {}
    if ml.get("margin_home") is not None:
        out["ml_margin_home"] = round(ml["margin_home"], 1)
    return out


def _lean(team: str, other: str, margin: float) -> str:
    return f"{team} by {abs(margin):.1f} over {other}"


def _toward(v: float, home: str, away: str) -> str:
    return f"{abs(v):.1f} toward {home if v > 0 else away}"


def _pct(p) -> str | None:
    return None if p is None else f"{p:.0%} to play"


def describe(gid: str, f: dict) -> str:
    """One game's factors as a compact line for the prompt."""
    home, away, p = f["home"], f["away"], f["parts"]
    fav = f["favoured"]
    other = away if fav == home else home
    bits = [f"{gid} | {away} at {home}{' (neutral site)' if f['neutral'] else ''}",
            f"model: {_lean(fav, other, f['margin_home'])}" + (" (toss-up)" if f["toss_up"] else "")
            + (f" (close game: {home} win probability {round(f['win_prob_home'] * 100)}%)" if f.get("close") else ""),
            # Each factor names the team it helps: a signed home-team number
            # was misread as favouring the wrong side.
            "factors: " + ", ".join(f"{k.replace('_', ' ')} {_toward(v, home, away)}"
                                    for k, v in p.items() if v)]
    if f.get("rating_split"):
        s = f["rating_split"]
        bits.append(f"rating gap from offence {_toward(s['offence'], home, away)}, "
                    f"from defence {_toward(s['defence'], home, away)}")
    rd = f["rest_days"]
    if p["rest"] and None not in rd.values():
        bits.append(f"rest: {home} {rd[home]:.0f} days, {away} {rd[away]:.0f} days")
    if p["travel"] and f.get("away_travel_miles"):
        bits.append(f"{away} travels {f['away_travel_miles']:.0f} miles")
    if p["weather"] and f.get("wind_mph") is not None:
        bits.append(f"wind {f['wind_mph']:.0f} mph shrinks the margin")
    for team in (home, away):
        pts = f["injury_points"].get(team)
        names = "; ".join(f"{i['player']} {i['position']} {i['points']:.1f}"
                          + f" ({', '.join(x for x in (i.get('status'), i['practice'], _pct(i.get('play_prob'))) if x)})"
                          for i in f["injured"][team])
        if pts:
            bits.append(f"{team} injuries cost {abs(pts):.1f}" + (f": {names}" if names else ""))
    if f.get("market_margin_home") is not None:
        m = f["market_margin_home"]
        bits.append(f"market: {_lean(home if m > 0 else away, away if m > 0 else home, m)}; "
                    f"model minus market {abs(f['gap_to_market']):.1f} pts")
    if f.get("ml_margin_home") is not None:
        m = f["ml_margin_home"]
        bits.append(f"second (ML) model: {_lean(home if m > 0 else away, away if m > 0 else home, m)}")
    if f["caveats"]:
        bits.append("caveats: " + " ".join(f["caveats"]))
    return " | ".join(bits)


# --- the number guard --------------------------------------------------------

# A digit run glued to letters ("49ers") is a name, not a figure.
_NUM = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![A-Za-z])")


def _numbers(text: str) -> list[float]:
    return [float(x) for x in _NUM.findall(text.replace(",", ""))]


def unsupported_numbers(text: str, source: str) -> list[float]:
    """Figures in `text` that don't appear in `source` (as given, or rounded to a whole number)."""
    allowed = set()
    for x in _numbers(source):
        allowed |= {round(x, 1), float(round(x))}
    # Small counts written as numerals ("2 factors") are harmless; a small decimal is still a claim.
    return [x for x in _numbers(text) if round(x, 1) not in allowed and not (x.is_integer() and x <= 4)]


# --- Claude ----------------------------------------------------------------------

def explain(lines: dict[str, str]) -> dict[str, str]:
    """game_id -> note, from one Claude call, cached by the exact input."""
    from . import claude_ai

    content = "Games, one per line:\n" + "\n".join(lines.values())
    key = hashlib.sha256((config.CLAUDE_MODEL + SYSTEM + content).encode()).hexdigest()[:16]
    cache = config.CACHE_DIR / f"game_explain_{key}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    r = claude_ai.ask(SYSTEM, [{"role": "user", "content": content}], purpose="game_explain",
                      max_tokens=12000, schema=SCHEMA)
    if not r["text"]:
        print(f"  [warn] no game explanations came back ({r['stop_reason']})")
        return {}
    out = {e["game_id"]: e["text"].strip() for e in json.loads(r["text"])["explanations"]
           if e["game_id"] in lines}
    config.ensure_dirs()
    cache.write_text(json.dumps(out), encoding="utf-8")
    print(f"  game explanations: {len(out)} games, {r['tokens']['input']} in / {r['tokens']['output']} out, "
          f"~${r['cost_usd']:.3f}")
    return out


def attach(games: list[dict], *, call_claude: bool = True) -> None:
    """Add an `explanation` to each exported NFL game in place. Never raises."""
    now = datetime.now(timezone.utc)
    # A game that has kicked off keeps what it had; it gets no new note.
    upcoming = [g for g in games if (k := parse_dt(g.get("kickoff"))) is not None and k > now]
    for g in games:
        g["explanation"] = None
    if not upcoming:
        return
    ratings, prior = {}, None
    try:
        store = db.get_store()
        try:
            season = int(str(upcoming[0]["game_id"])[:4])
            ratings, prior = _ratings(store, season), prior_share(store, season)
        finally:
            store.close()
    except Exception as exc:  # noqa: BLE001 - a missing split only loses detail
        print(f"  [warn] game explanations: ratings unavailable ({exc})")

    facts, lines = {}, {}
    for g in upcoming:
        f = factors(g, ratings, prior)
        if f is None:
            print(f"  [warn] {g['game_id']}: breakdown doesn't reconcile with the served margin; no note")
            continue
        facts[g["game_id"]], lines[g["game_id"]] = f, describe(g["game_id"], f)

    notes: dict[str, str] = {}
    if call_claude and lines:
        try:
            notes = explain(lines)
        except Exception as exc:  # noqa: BLE001 - the page is still worth writing
            print(f"  [warn] game explanations skipped: {exc}")

    def guarded(batch: dict[str, str]) -> dict[str, str]:
        kept = {}
        for gid, text in batch.items():
            if bad := unsupported_numbers(text, lines[gid]):
                print(f"  [warn] {gid}: note cites {bad}, not in its inputs; dropped")
            else:
                kept[gid] = text
        return kept

    notes = guarded(notes)
    # One retry, for just the games that came back missing or were dropped.
    if call_claude and notes and (redo := {gid: line for gid, line in lines.items() if gid not in notes}):
        try:
            notes |= guarded(explain(redo))
        except Exception as exc:  # noqa: BLE001
            print(f"  [warn] game explanation retry skipped: {exc}")

    at = datetime.now(timezone.utc).isoformat()
    for g in upcoming:
        gid = g["game_id"]
        if (f := facts.get(gid)) is None:
            continue
        text = notes.get(gid)
        g["explanation"] = {"text": text, "favoured": f["favoured"], "toss_up": f["toss_up"], "close": f["close"],
                            "parts": f["parts"], "caveats": f["caveats"],
                            "model": config.CLAUDE_MODEL if text else None, "generated_at": at}


if __name__ == "__main__":
    from . import export_dashboard

    parser = argparse.ArgumentParser(description="Explain each NFL game's predicted margin.")
    parser.add_argument("--factors", action="store_true", help="print the factor lines only, no Claude call")
    args = parser.parse_args()
    games = export_dashboard.build("nfl", explain=False)["games"]
    attach(games, call_claude=not args.factors)
    for g in games:
        e = g.get("explanation") or {}
        print(f"\n{g['away']} @ {g['home']}  {e.get('parts')}")
        print("  " + (e.get("text") or "(no note)"))
        for c in e.get("caveats") or []:
            print("   - " + c[:160])
