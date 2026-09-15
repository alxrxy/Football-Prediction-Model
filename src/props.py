"""Best props of the week: every priced player prop against the simulation.

    python -m src.ingest_props     # pull the lines first (Odds API quota)
    python -m src.props            # rank them, and have Claude explain the top ones
    python -m src.props --no-explain

For each player prop the Odds API lists (data/props_lines.json):

  market   each book's over/under devigged (Shin), at the line most books
           post, averaged across books: the market's vig-free P(over)
  model    P(over) read off that player's simulated stat line, from the
           latest stored pregame simulation of the game
  gap      model minus market on the side the model prefers

Props are ranked by that gap. Like the side flags, nothing here is a
validated edge: player projections are the simulator's lowest-confidence
output, and a big gap is as likely to be a usage miss (a role change the
depth chart hasn't caught) as a mispriced line. Gaps beyond MAX_GAP are held
out of the ranking for exactly that reason and listed separately. Each row
also carries the Stage 1 test (blended with the market at the model weight,
3 pp past the price's break-even) so a prop that would pass it is marked.

The top TOP_N get a plain-English explanation from Claude, in one call per
distinct list, cached so re-running the export doesn't re-bill.

Writes data/props.json and dashboard/public/props.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher
from statistics import mean, median

import numpy as np

from . import config, market
from .box_score import PCT_GRID
from .names import norm

PROPS_LINES_JSON = config.DATA_DIR / "props_lines.json"
PROPS_JSON = config.DATA_DIR / "props.json"
PUBLIC_PROPS_JSON = config.ROOT / "dashboard" / "public" / "props.json"

# Odds API market -> (box-score group, stat, label)
MARKETS = {
    "player_pass_yds": ("passing", "yds", "Pass yds"),
    "player_rush_yds": ("rushing", "yds", "Rush yds"),
    "player_reception_yds": ("receiving", "yds", "Rec yds"),
    "player_receptions": ("receiving", "rec", "Receptions"),
}
TOP_N = 25
MAX_GAP = 0.25          # model vs market gaps past this are held out as likely usage misses
NAME_MATCH = 0.88

# Alt lines: for each top prop, an easier alternate line on the same side
# where the simulation gives at least ALT_MIN_P, priced no shorter than
# ALT_MIN_PRICE, with the best expected return among those. "Safe, but still
# decent odds", in numbers. Books post most alternates as overs only, so an
# under pick often has none.
ALT_OF = {m: f"{m}_alternate" for m in MARKETS}
ALT_MIN_P = 0.65
ALT_MIN_PRICE = -250

_SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b")


def pnorm(name: str) -> str:
    """Player name for matching: casefolded, punctuation and suffixes gone."""
    return re.sub(r"\s+", " ", _SUFFIX.sub(" ", norm(name))).strip()


# --- probabilities ---------------------------------------------------------

def p_over(q: dict, line: float) -> float:
    """P(stat > line) from a simulated stat summary.

    Exact for counts carrying `ge` (P(stat >= k) per k); for yards, linear
    between the stored percentiles (a 5% grid when the simulation stored one,
    else the 10/25/50/75/90 quantiles), with the tails beyond the grid split
    evenly.
    """
    if q.get("ge"):
        k = math.floor(line) + 1
        return float(q["ge"][k]) if k < len(q["ge"]) else 0.0
    if q.get("pct"):
        xs, ps = np.asarray(q["pct"], float), np.asarray(PCT_GRID, float) / 100
    else:
        xs = np.asarray([q["p10"], q["p25"], q["median"], q["p75"], q["p90"]], float)
        ps = np.asarray([0.10, 0.25, 0.50, 0.75, 0.90])
    xs = np.maximum.accumulate(xs) + np.arange(len(xs)) * 1e-6
    if line < xs[0]:
        cdf = ps[0] / 2
    elif line > xs[-1]:
        cdf = 1 - (1 - ps[-1]) / 2
    else:
        cdf = float(np.interp(line, xs, ps))
    return 1.0 - cdf


def market_view(books: dict) -> dict | None:
    """Vig-free P(over) at the line most books post, and each side's best price."""
    priced = {b: v for b, v in books.items()
              if v.get("over") is not None and v.get("under") is not None and v.get("point") is not None}
    if not priced:
        return None
    counts = Counter(v["point"] for v in priced.values())
    top = max(counts.values())
    point = median(sorted(p for p, c in counts.items() if c == top))
    fair, best = [], {"over": None, "under": None}
    for book, v in priced.items():
        if v["point"] != point:
            continue
        fair.append(market.devig([v["over"], v["under"]])[0])
        for side in ("over", "under"):
            if best[side] is None or market.implied(v[side]) < market.implied(best[side][0]):
                best[side] = (v[side], book)
    if not fair:
        return None
    return {"point": point, "p_over": mean(fair), "books": len(fair), "best": best}


def decimal_odds(price: float) -> float:
    return 1 + (price / 100 if price > 0 else 100 / -price)


def pick_alt(row: dict, q: dict, offers: list[dict]) -> dict | None:
    """The alternate line to show beside a prop: the same side as the pick at
    an easier line (lower for an over, higher for an under), the simulation
    giving it ALT_MIN_P or better, priced ALT_MIN_PRICE or longer; of those,
    the best expected return per unit. The safer version of the pick, at
    odds still worth having."""
    best = None
    for o in offers:
        if o.get("side") != row["pick"] or o.get("point") is None or o.get("price") is None:
            continue
        easier = o["point"] < row["line"] if row["pick"] == "over" else o["point"] > row["line"]
        if not easier or o["price"] < ALT_MIN_PRICE:
            continue
        pm = p_over(q, o["point"])
        p = pm if row["pick"] == "over" else 1 - pm
        if p < ALT_MIN_P:
            continue
        ev = p * decimal_odds(o["price"]) - 1
        if best is None or ev > best["ev"]:
            best = {"line": o["point"], "price": o["price"], "book": o["book"], "p_model": round(p, 4),
                    "breakeven": round(market.implied(o["price"]), 4), "ev": round(ev, 4)}
    return best


# --- matching --------------------------------------------------------------

def match_player(name: str, players: list[tuple[str, dict]]) -> tuple[str, dict] | None:
    """(side, box entry) for an Odds API player name, among both teams' lines."""
    target = pnorm(name)
    best, score = None, 0.0
    for side, p in players:
        cand = pnorm(p["player"])
        if cand == target:
            return side, p
        s = SequenceMatcher(None, cand, target).ratio()
        if s > score:
            best, score = (side, p), s
    return best if score >= NAME_MATCH else None


# --- ranking ---------------------------------------------------------------

def _sims() -> dict[str, dict]:
    from . import db
    from .export_sims import _json, _latest, _read_all, pregame_view

    store = db.get_store()
    rows = _latest(_read_all(store, "game_simulations"), "generated_at")
    games = {g["game_id"]: g for g in store.select("games", {"sport": "nfl"})}
    store.close()
    out = {}
    for gid, row in rows.items():
        g = games.get(gid, {})
        view = pregame_view(row, g.get("kickoff_time"))
        view["box_score"] = _json(row.get("box_score"))   # with the pricing grids
        out[gid] = view
    return out


def rank(lines: dict, sims: dict[str, dict]) -> dict:
    rows, unmatched, unprojected = [], 0, 0
    for gid, g in (lines.get("games") or {}).items():
        sim = sims.get(gid)
        box = (sim or {}).get("box_score") or {}
        players = [(side, p) for side in ("home", "away") for p in (box.get(side) or {}).get("players") or []]
        if not players:
            unprojected += len(g["players"])
            continue
        margin = sim.get("margin") or {}
        for name, by_market in g["players"].items():
            hit = match_player(name, players)
            if hit is None:
                unmatched += 1
                continue
            side, p = hit
            team = g[side]
            for mkey, books in by_market.items():
                if mkey not in MARKETS:
                    continue
                group, stat, label = MARKETS[mkey]
                q = (p.get(group) or {}).get(stat)
                mv = market_view(books)
                if not q or mv is None:
                    continue
                pm = p_over(q, mv["point"])
                pick = "over" if pm >= mv["p_over"] else "under"
                p_model = pm if pick == "over" else 1 - pm
                p_market = mv["p_over"] if pick == "over" else 1 - mv["p_over"]
                price, book = mv["best"][pick]
                breakeven = market.implied(price)
                blended = market.blend(p_model, p_market, config.MODEL_MARKET_WEIGHT)
                rows.append({
                    "game_id": gid, "game": f"{g['away']} @ {g['home']}", "kickoff": g.get("kickoff"),
                    "player": p["player"], "odds_name": name, "team": team,
                    "position": f"{p.get('position') or ''}{p.get('depth_rank') or ''}",
                    "market": mkey, "label": label, "line": mv["point"], "pick": pick,
                    "price": price, "book": book, "books": mv["books"],
                    "p_model": round(p_model, 4), "p_market": round(p_market, 4),
                    "gap": round(p_model - p_market, 4),
                    "blended": round(blended, 4), "breakeven": round(breakeven, 4),
                    "passes_stage1": blended - breakeven >= config.EDGE_BUFFER,
                    "sim": {k: q.get(k) for k in ("median", "mean", "p10", "p25", "p75", "p90")},
                    "touches": p.get("touches"),
                    "game_sim": {"home_win_prob": sim.get("home_win_prob"), "margin_home": margin.get("p50"),
                                 "total": (sim.get("total") or {}).get("p50")},
                    "sim_generated_at": sim.get("generated_at"),
                    "_q": q,   # the full stat summary, for pricing alt lines; not exported
                })
    held = [r for r in rows if r["gap"] > MAX_GAP]
    ranked = sorted((r for r in rows if r["gap"] <= MAX_GAP), key=lambda r: -r["gap"])
    for i, r in enumerate(ranked, 1):
        r["rank"] = i
    return {"ranked": ranked, "held_out": sorted(held, key=lambda r: -r["gap"]),
            "unmatched_players": unmatched, "unprojected_players": unprojected}


# --- explanations ----------------------------------------------------------

EXPLAIN_SYSTEM = (
    "You write short explanations for a personal NFL prop-ranking page. Each prop is ranked by the gap "
    "between a game simulation's probability and the betting market's vig-free probability. For each "
    "prop, write one or two plain-English sentences: what the simulation expects and why that differs "
    "from the line (the player's role and volume, the game script the simulation expects, the spread "
    "and total), then the main risk to it; if an alt line is given, add a clause on why it's the safer "
    "version. Use only the numbers given. These are unvalidated model "
    "outputs: no hype, no 'lock', and never tell anyone to bet."
)
EXPLAIN_SCHEMA = {
    "type": "object",
    "properties": {"explanations": {"type": "array", "items": {
        "type": "object",
        "properties": {"rank": {"type": "integer"}, "text": {"type": "string"}},
        "required": ["rank", "text"], "additionalProperties": False}}},
    "required": ["explanations"], "additionalProperties": False,
}


def _describe(r: dict) -> str:
    alt = r.get("alt")
    extra = (f" | alt line: {r['pick']} {alt['line']} at {alt['price']:+d} ({alt['book']}), simulation "
             f"{alt['p_model']:.0%}" if alt else "")
    return _describe_base(r) + extra


def _describe_base(r: dict) -> str:
    s, gs = r["sim"], r["game_sim"]
    hw = gs.get("home_win_prob")
    home, away = r["game"].split(" @ ")[1], r["game"].split(" @ ")[0]
    return (
        f"#{r['rank']} | {r['player']} ({r['team']} {r['position']}) | {r['label']} {r['pick']} {r['line']} "
        f"at {r['price']:+d} ({r['book']}) | market {r['p_market']:.0%} vs simulation {r['p_model']:.0%} "
        f"({r['books']} books) | sim median {s['median']}, middle 50% {s['p25']}-{s['p75']}, "
        f"80% {s['p10']}-{s['p90']}, {r['touches']} touches/game | game {r['game']}: "
        f"{home} win {hw:.0%}, sim margin {home} {gs['margin_home']:+.0f}, total {gs['total']:.0f}"
        if hw is not None and gs.get("margin_home") is not None and gs.get("total") is not None else
        f"#{r['rank']} | {r['player']} ({r['team']} {r['position']}) | {r['label']} {r['pick']} {r['line']} "
        f"| market {r['p_market']:.0%} vs simulation {r['p_model']:.0%} | sim median {s['median']}"
    )


def explain(top: list[dict]) -> dict[int, str]:
    """rank -> explanation, from one Claude call, cached by the exact input."""
    from . import claude_ai

    content = "Props, one per line:\n" + "\n".join(_describe(r) for r in top)
    key = hashlib.sha256((config.CLAUDE_MODEL + EXPLAIN_SYSTEM + content).encode()).hexdigest()[:16]
    cache = config.CACHE_DIR / f"props_explain_{key}.json"
    if cache.exists():
        return {int(k): v for k, v in json.loads(cache.read_text(encoding="utf-8")).items()}
    r = claude_ai.ask(EXPLAIN_SYSTEM, [{"role": "user", "content": content}], purpose="props_explain",
                      max_tokens=16000, schema=EXPLAIN_SCHEMA)
    if not r["text"]:
        print(f"  [warn] no explanations came back ({r['stop_reason']})")
        return {}
    out = {int(e["rank"]): e["text"].strip() for e in json.loads(r["text"])["explanations"]}
    config.ensure_dirs()
    cache.write_text(json.dumps(out), encoding="utf-8")
    print(f"  explanations: {len(out)} props, {r['tokens']['input']} in / {r['tokens']['output']} out, "
          f"~${r['cost_usd']:.3f}")
    return out


# --- export ----------------------------------------------------------------

def run(with_explanations: bool = True, top_n: int = TOP_N, with_alts: bool = True) -> dict:
    if not PROPS_LINES_JSON.exists():
        raise SystemExit("No prop lines yet. Run: python -m src.ingest_props")
    lines = json.loads(PROPS_LINES_JSON.read_text(encoding="utf-8"))
    result = rank(lines, _sims())
    top = result["ranked"][:top_n]
    alts_pulled = None
    if with_alts and top:
        from .ingest_props import fetch_alternates

        # Only the (game, stat) pairs the list uses: ~1 credit each.
        needs: dict[str, set[str]] = {}
        for r in top:
            needs.setdefault(r["game_id"], set()).add(ALT_OF[r["market"]])
        try:
            offers, alts_pulled = fetch_alternates(needs, lines)
        except Exception as exc:  # noqa: BLE001 - the ranking stands without alt lines
            print(f"  [warn] alt lines skipped: {exc}")
            offers = {}
        for r in top:
            by_market = offers.get(r["game_id"], {}).get(r["odds_name"], {})
            r["alt"] = pick_alt(r, r["_q"], by_market.get(ALT_OF[r["market"]], []))
    if with_explanations and top:
        try:
            notes = explain(top)
        except Exception as exc:  # noqa: BLE001 - the ranking is still worth writing
            print(f"  [warn] explanations skipped: {exc}")
            notes = {}
        for r in top:
            r["explanation"] = notes.get(r["rank"])
    for r in result["ranked"] + result["held_out"]:
        r.pop("_q", None)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lines_pulled_at": lines.get("pulled_at"), "season": lines.get("season"), "week": lines.get("week"),
        "model_weight": config.MODEL_MARKET_WEIGHT, "edge_buffer": config.EDGE_BUFFER, "max_gap": MAX_GAP,
        "priced": len(result["ranked"]) + len(result["held_out"]),
        "unmatched_players": result["unmatched_players"],
        "unprojected_players": result["unprojected_players"],
        "props": top,
        "more": result["ranked"][top_n:],
        "held_out": result["held_out"],
        "alts_pulled_at": alts_pulled,
        "alt_rule": {"min_p": ALT_MIN_P, "min_price": ALT_MIN_PRICE},
    }
    config.ensure_dirs()
    PROPS_JSON.write_text(json.dumps(payload), encoding="utf-8")
    if PUBLIC_PROPS_JSON.parent.exists():
        shutil.copy(PROPS_JSON, PUBLIC_PROPS_JSON)
    print(f"[props] week {payload['week']}: {payload['priced']} props priced, top {len(top)} written "
          f"({len(result['held_out'])} held out as likely usage misses, "
          f"{result['unmatched_players']} names unmatched) -> {PROPS_JSON}")
    for r in top:
        alt = r.get("alt")
        print(f"  {r['rank']:>2}. {r['player']:<22} {r['label']:<10} {r['pick']:<5} {r['line']:>6} "
              f"{r['price']:+d}  sim {r['p_model']:.0%} vs mkt {r['p_market']:.0%}  (+{r['gap'] * 100:.1f} pp)"
              + (f"  | alt {alt['line']} {alt['price']:+d} sim {alt['p_model']:.0%}" if alt else ""))
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rank NFL player props against the simulations.")
    parser.add_argument("--no-explain", action="store_true", help="skip the Claude explanations")
    parser.add_argument("--top", type=int, default=TOP_N)
    parser.add_argument("--no-alts", action="store_true", help="skip alt lines (no extra Odds API credits)")
    args = parser.parse_args()
    run(with_explanations=not args.no_explain, top_n=args.top, with_alts=not args.no_alts)
