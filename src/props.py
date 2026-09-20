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
# decent odds", in numbers.
#
# OFF BY DEFAULT (opt in with --alts). Books post alternates as overs only, and
# the simulation's usage bias means the ranking is currently all unders, so a
# pull costs ~1 credit per (game, stat) pair and attaches nothing: on 2026-09-16
# it spent 9 credits for zero alt lines. Worth turning back on if the top of the
# list stops being one-sided -- see P17 in nfl-modeling-research.md.
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


# --- empirical bias correction (display only) ------------------------------
# The simulator projects individual skill players under their market lines. On
# 2026-09-16 the simulated P(over) averaged .38-.43 against a market .50 for
# receptions, receiving yards and rushing yards, while passing yards ran
# slightly the other way. The cause is not fixed -- the open work is bucket
# composition and the within-bucket run/pass mix -- so this removes the
# measured systematic component and nothing else.
#
# One log-odds offset per category, fitted so that category's mean simulated
# P(over) matches the market's mean over that week's priced props. Two things
# to be honest about: it is fitted IN SAMPLE, so it is guaranteed to look
# right on the week it came from, and the per-category samples are small
# (25-69 props). Re-derive rather than trust these once the engine changes.
BIAS_FIT = {
    "measured_at": "2026-09-16",
    "method": "per-category log-odds offset, fitted so mean simulated P(over) "
              "matches mean market P(over) on that week's priced props",
    "in_sample": True,
    # Receptions refitted 2026-09-18 after throwaways stopped counting as
    # targets (P27), on the week-2 priced props. P27 moves targets only, not
    # receptions or yards, so the refit landed where the old fit was
    # (+0.5214 -> +0.5104). Receiving yards are split by position below.
    # Passing yards refitted the same day: the 9/16 fit (-0.0930, n=25, first
    # pull) had gone stale, and on the full week-2 slate the simulation sits
    # on the market (-0.12pp raw), so the offset is now all but zero.
    # Receiving refitted again 2026-09-19 after backups got partial weight on
    # their own history (P25, k32+fb), which moves ~0.3 targets per starter
    # slot to the backups: receptions +0.5104 -> +0.5517.
    # Everything refitted once more the same day with PENALTY_REPLAY on (more
    # possessions and plays, ~+0.3 pass attempts a team): props moved ~0.5pp
    # toward the market. Passing yards is still provisional (P29: the tied-line
    # bug drops about a third of starting QBs from its sample).
    # Passing yards refitted again after QB-specific scramble rates (P24) moved
    # some running QBs' pass attempts to scrambles: -0.0475 -> -0.0212. Still
    # provisional under P29, which remains open.
    # ALL REFITTED 2026-09-20 on the complete sample P29 restores. The tied-line
    # bug had been dropping 8.7% of priced markets, skewed to starting
    # quarterbacks, and the two offsets built mostly on quarterbacks were the
    # two that moved: passing yards CHANGES SIGN (-0.0212 -> +0.0732, n 23 ->
    # 32) and QB rushing grows 41% (-0.1818 -> -0.2564, n 21 -> 27). The
    # receiving offsets barely move, which is consistent with the bug taking
    # mostly quarterbacks. Fitted on the simulations stored 2026-09-19 with
    # USAGE_PARTICIPATION_TRIM and QB_EXPECTED_STARTER both off; either flag
    # changes simulated output and needs another refit.
    "offsets": {
        "player_pass_yds": +0.0732,
        "player_receptions": +0.5522,
    },
    "measured_at_by_market": {"player_pass_yds": "2026-09-20", "player_receptions": "2026-09-20",
                              "player_reception_yds": "2026-09-20"},
    "n": {"player_pass_yds": 32, "player_reception_yds": 155, "player_receptions": 154},
    "raw_bias_pp": {"player_pass_yds": -1.69, "player_reception_yds": -9.55, "player_receptions": -12.07},
    # Rushing is corrected by position (P26). The single category offset hid two
    # biases pulling opposite ways, QBs over and backs under. Refitted
    # 2026-09-18 after scrambles and kneels left the carry shares (P23), on the
    # week-2 priced props, same method. QBs then got no offset and were held out
    # of the ranking, because runners and pocket QBs sat on opposite sides.
    #
    # QB rushing returned to the ranking 2026-09-19, after P24 gave each QB his
    # own scramble rate: offset -0.182 (n=21, raw +4.22pp, 90% CI -0.36 to
    # +0.03). No split: pocket, middle and running QBs all lean the same way
    # with overlapping intervals, and Spearman(line, gap) fell from -0.79 to
    # -0.29 (p=0.20).
    #
    # RB rushing refitted 2026-09-19 (+0.107 -> +0.195) after k32+fb (P25) moved
    # carries from RB1/RB2 to the backs behind them.
    #
    # Receiving yards split too (P26 by-position check, 2026-09-18): backs run
    # about half as far under as WRs and TEs (RB +0.21, 90% CI +0.08 to +0.34,
    # which excludes the category fit of +0.40). Receptions did not split: all
    # three positions sit within each other's intervals.
    "position_offsets": {
        "player_rush_yds": {"RB": +0.1929, "QB": -0.2564},
        "player_reception_yds": {"WR": +0.4342, "TE": +0.5417, "RB": +0.2668},
    },
    "position_n": {"player_rush_yds": {"RB": 55, "QB": 27}, "player_reception_yds": {"WR": 81, "TE": 38, "RB": 36}},
    "position_raw_bias_pp": {"player_rush_yds": {"RB": -4.26, "QB": +5.67},
                             "player_reception_yds": {"WR": -9.88, "TE": -12.46, "RB": -6.34}},
    "position_measured_at": "2026-09-20",
    "position_notes": {
        "player_rush_yds": {"RB": (
            "Mean-fitted: it lifts every back by the same amount, but starters (the higher lines) still run "
            "under and backups sit near the market. That starter/backup split may overlap with the "
            "backup-usage defect (issue 1, P25), so the offset may need refitting once that is diagnosed."
        )},
        "player_reception_yds": {"ALL": (
            "Same pattern at every position: after the offset, low lines sit over the market and high lines "
            "under, so starters are still under-projected. That is efficiency compression (P17), which a "
            "constant cannot fix."
        )},
    },
}

# Props whose simulated probability measures a known engine defect rather than
# the player, kept out of the ranking entirely until the defect is fixed.
# Keyed by (market, position). Empty since 2026-09-19: QB rushing, held out
# here while every QB scrambled at the league rate, returned to the ranking
# once P24 gave each QB his own rate.
STRUCTURAL_HOLDOUTS: dict[tuple[str, str], str] = {}

# Single props held out for the same reason: the simulated number is known to
# be meaningless, not a disagreement worth reading. Keyed by (game_id, the
# books' player name, market). Remove each entry once its item is fixed or the
# game has kicked off. A KNOWN_DEFECTS label still applies to the player's
# other props.
PROP_HOLDOUTS = {
    ("2026_02_SEA_ARI", "Drew Lock", "player_rush_yds"): (
        "Drew Lock rushing yards (P28): the simulation has Lock as SEA's QB2 behind Darnold, so his projection "
        "is near zero while the books price him as the starter. Held out until the starter mismatch is fixed."
    ),
}

# A quarterback the books price as a starter whose simulation has him at a
# median of zero is not a disagreement about the player, it is a disagreement
# about who is playing (P28). Held out wherever it occurs, so this does not
# need a hand-written entry per quarterback per week. Gated on
# QB_EXPECTED_STARTER with the rest of P28 part 1.
QB_MARKETS = {"player_pass_yds", "player_pass_tds", "player_pass_attempts",
              "player_pass_completions", "player_pass_interceptions"}


def _starter_mismatch(market: str, position: str, line, q: dict) -> str | None:
    """Held-out note when a priced quarterback simulates at a median of zero."""
    if not config.QB_EXPECTED_STARTER or market not in QB_MARKETS:
        return None
    if not (position or "").upper().startswith("QB"):
        return None
    median = (q or {}).get("median")
    if median is None or median > 0 or not line or line <= 0:
        return None
    return ("Starter mismatch (P28): the books price this quarterback with a line of "
            f"{line}, but the simulation has him at a median of 0, which means it does not "
            "expect him to play. That gap measures who is starting, not the player, so it "
            "is held out of the ranking.")


# Props known to be measuring a defect, labelled on the page but left in the
# ranking. Keyed by (game_id, the books' player name), or (game_id, "team:XXX")
# for every prop of that team's players. Remove each entry once its item is
# fixed or the game has kicked off.
KNOWN_DEFECTS = {
    ("2026_02_SEA_ARI", "Drew Lock"): (
        "Known defect (P28): books price Lock as SEA's passer and post no Darnold line, but the simulation "
        "has him as QB2 behind Darnold (median 0 passing yards). This gap is a starter-designation mismatch, "
        "not a read on Lock. Not yet diagnosed."
    ),
    ("2026_02_CAR_ATL", "team:ATL"): (
        "Known issue, treat with caution (P28): ATL's starting QB is unsettled. The simulation splits the passing "
        "60/40 Tua/Cooper Rush, while the books price Rush (who started week 1). Every ATL projection depends on "
        "which one plays."
    ),
}


def bias_adjust(p: float, market_key: str, position: str | None = None) -> float:
    """The simulation's P(over), shifted by the measured offset for that
    category, or for that position within it where the category is split."""
    if not config.PROPS_BIAS_ADJUST:
        return p
    by_pos = BIAS_FIT["position_offsets"].get(market_key)
    shift = by_pos.get(position) if by_pos is not None else BIAS_FIT["offsets"].get(market_key)
    # A split category leaves any position it did not fit (a FB, say) raw.
    if not shift:
        return p
    p = min(max(p, 1e-6), 1 - 1e-6)
    return 1.0 / (1.0 + math.exp(-(math.log(p / (1 - p)) + shift)))


def market_view(books: dict) -> dict | None:
    """Vig-free P(over) at the line most books post, and each side's best price.

    When several lines tie for most-posted, the median of them can fall between
    two real lines -- 182.5 twice and 183.5 twice gives 183.0 -- which no book
    offers, so nothing matched and the prop disappeared: never ranked, never
    held out, not even counted as unmatched (P29). It cost 8.7% of priced
    player-markets, and they were not a random 8.7%: the corrections in
    BIAS_FIT were fitted without them. The tie is now broken toward the tied
    line nearest the consensus of every book, which is always a line somebody
    posts. A median that already lands on a real line is left alone, so this
    changes no prop that previously worked.
    """
    priced = {b: v for b, v in books.items()
              if v.get("over") is not None and v.get("under") is not None and v.get("point") is not None}
    if not priced:
        return None
    counts = Counter(v["point"] for v in priced.values())
    top = max(counts.values())
    tied = sorted(p for p, c in counts.items() if c == top)
    point = median(tied)
    if point not in counts:
        centre = mean(v["point"] for v in priced.values())
        point = min(tied, key=lambda p: (abs(p - centre), p))
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
        # .get: a row without a market key (as in the unit test) simply gets no
        # adjustment, since bias_adjust no-ops on an unknown category.
        pm = bias_adjust(p_over(q, o["point"]), row.get("market"), row.get("position", "").rstrip("0123456789"))
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


def _kicked_off(kickoff: str | None, now: datetime) -> bool:
    try:
        return kickoff is not None and datetime.fromisoformat(kickoff) <= now
    except ValueError:
        return False


def rank(lines: dict, sims: dict[str, dict], now: datetime | None = None) -> dict:
    """Rank every priced prop by the raw simulation's disagreement with the
    market. Props for games that have kicked off are kept, under `started`,
    but never ranked or held out: their pregame lines can no longer be bet."""
    now = now or datetime.now(timezone.utc)
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
                pm_raw = p_over(q, mv["point"])
                pos = p.get("position") or ""
                pm_adj = bias_adjust(pm_raw, mkey, pos)
                # The pick and the ranking come from the RAW disagreement. The
                # correction is one constant per category, so it cannot order
                # players within a category: three ranking variants built on it
                # all promoted props that sat near the market beforehand. It
                # earns its place on the display, not in the sort.
                pick = "over" if pm_raw >= mv["p_over"] else "under"
                p_market = mv["p_over"] if pick == "over" else 1 - mv["p_over"]
                p_model_raw = pm_raw if pick == "over" else 1 - pm_raw
                p_model = pm_adj if pick == "over" else 1 - pm_adj
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
                    # `gap` is the raw disagreement, and is what rank() sorts and
                    # holds out on, so the ordering is identical whether the
                    # correction is on or off. `gap_adjusted` is the same
                    # distance after correction, carried for the display only.
                    "gap": round(p_model_raw - p_market, 4),
                    "p_model_raw": round(p_model_raw, 4),
                    "gap_adjusted": round(p_model - p_market, 4),
                    "blended": round(blended, 4), "breakeven": round(breakeven, 4),
                    "passes_stage1": blended - breakeven >= config.EDGE_BUFFER,
                    "sim": {k: q.get(k) for k in ("median", "mean", "p10", "p25", "p75", "p90")},
                    "touches": p.get("touches"),
                    "game_sim": {"home_win_prob": sim.get("home_win_prob"), "margin_home": margin.get("p50"),
                                 "total": (sim.get("total") or {}).get("p50")},
                    "sim_generated_at": sim.get("generated_at"),
                    "_q": q,   # the full stat summary, for pricing alt lines; not exported
                    "_structural": (STRUCTURAL_HOLDOUTS.get((mkey, pos))
                                    or PROP_HOLDOUTS.get((gid, name, mkey))
                                    or _starter_mismatch(mkey, pos, mv["point"], q)),
                    "defect_note": KNOWN_DEFECTS.get((gid, name)) or KNOWN_DEFECTS.get((gid, f"team:{team}")),
                })
    started = [r for r in rows if _kicked_off(r["kickoff"], now)]
    rows = [r for r in rows if not _kicked_off(r["kickoff"], now)]
    for r in started:
        r.pop("_structural")
    for r in rows:
        why = r.pop("_structural")
        r["held_reason"] = "structural" if why else "gap" if r["gap"] > MAX_GAP else None
        if why:
            r["held_note"] = why
    held = sorted((r for r in rows if r["held_reason"]), key=lambda r: (r["held_reason"] != "gap", -r["gap"]))
    ranked = sorted((r for r in rows if not r["held_reason"]), key=lambda r: -r["gap"])
    for i, r in enumerate(ranked, 1):
        r["rank"] = i
    return {"ranked": ranked, "held_out": held, "started": started,
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
    defect = f" | {r['defect_note']}" if r.get("defect_note") else ""
    return _describe_base(r) + extra + defect


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

def run(with_explanations: bool = True, top_n: int = TOP_N, with_alts: bool = False) -> dict:
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
    for r in result["ranked"] + result["held_out"] + result["started"]:
        r.pop("_q", None)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lines_pulled_at": lines.get("pulled_at"), "season": lines.get("season"), "week": lines.get("week"),
        # A partial re-pull (--games / --only-missing): lines_pulled_at is then
        # the oldest game's pull, and these name the games that are fresher.
        "lines_refreshed_at": lines.get("refreshed_at"),
        "lines_refreshed_games": [f"{g['away']} @ {g['home']}" for gid in lines.get("refreshed_games") or []
                                  if (g := (lines.get("games") or {}).get(gid))],
        "model_weight": config.MODEL_MARKET_WEIGHT, "edge_buffer": config.EDGE_BUFFER, "max_gap": MAX_GAP,
        "priced": len(result["ranked"]) + len(result["held_out"]),
        "unmatched_players": result["unmatched_players"],
        "unprojected_players": result["unprojected_players"],
        "props": top,
        "more": result["ranked"][top_n:],
        "held_out": result["held_out"],
        # Games already under way or finished: kept for reference, never ranked.
        "started": result["started"],
        "alts_pulled_at": alts_pulled,
        # Only describe the rule when it was actually applied, so the payload
        # never advertises alt lines that were never pulled.
        "alt_rule": {"min_p": ALT_MIN_P, "min_price": ALT_MIN_PRICE} if with_alts else None,
        "bias_adjust": {**BIAS_FIT, "applied": config.PROPS_BIAS_ADJUST},
        "structural_holdouts": [{"market": m, "position": pos, "note": note}
                                for (m, pos), note in STRUCTURAL_HOLDOUTS.items()]
                               + [{"market": m, "player": who, "note": note}
                                  for (_gid, who, m), note in PROP_HOLDOUTS.items()],
    }
    config.ensure_dirs()
    PROPS_JSON.write_text(json.dumps(payload), encoding="utf-8")
    if PUBLIC_PROPS_JSON.parent.exists():
        shutil.copy(PROPS_JSON, PUBLIC_PROPS_JSON)
    print(f"[props] week {payload['week']}: {payload['priced']} props priced, top {len(top)} written "
          f"({sum(r['held_reason'] == 'gap' for r in result['held_out'])} held out as likely usage misses, "
          f"{sum(r['held_reason'] == 'structural' for r in result['held_out'])} held out as engine defects, "
          f"{result['unmatched_players']} names unmatched, "
          f"{len(result['started'])} from games already kicked off, not ranked) -> {PROPS_JSON}")
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
    parser.add_argument("--alts", action="store_true",
                        help="also pull alternate lines (~1 Odds API credit per game/stat pair); "
                             "off by default because an all-unders list qualifies for none")
    args = parser.parse_args()
    run(with_explanations=not args.no_explain, top_n=args.top, with_alts=args.alts)
