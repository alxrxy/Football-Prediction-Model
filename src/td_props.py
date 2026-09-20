"""Anytime-touchdown props against the simulation. Exploratory.

    python -m src.ingest_td_props      # pull the lines first (1 credit a game)
    python -m src.td_props             # rank them

A separate list from src/props.py, with its own lines file, output file,
hold-out rule and confidence label; nothing here reads or writes props.json.

  model    P(player scores >= 1 rushing or receiving TD), from the stored
           pregame simulation's box score. The engine credits each simulated
           TD on the play itself, to a ball carrier or target chosen by
           goal-line / red-zone / open-field usage share (nflverse play-by-
           play), with an injured player's share moved down the depth chart
           (simulate_nfl.team_shares). No new prediction path.
  market   the books' vig-free P(yes), estimated -- see below
  gap      model minus market, in probability points; ranked by its size in
           either direction

Devigging. Books post this market as Yes only: on 2026-09-16 not one of six
books priced a No for any player in the four games sampled, so the two-way
Shin devig the yardage props use has nothing to work with. Instead each
book's prices are made consistent with the game total. Read each Yes price
as a Poisson rate, lambda = -ln(1 - q); a book's lambdas summed over one game
are the player TDs it is implicitly pricing, which ran 6.1-8.5 against the
~4.5-5.7 the totals support (a 35-40% overround). One factor per book per
game scales them down to market_total x TD_PER_POINT, and p = 1 - exp(-k *
lambda). This is the power devig on the No side, (1 - p) = (1 - q)^k, with k
fixed by the market's own total rather than by a No price. It assumes the
book spreads its margin evenly in log space, and that its list covers every
scorer (fringe players it omits would make the devigged market slightly too
high). When a book does post both sides, its pair is devigged directly.

Why this is lower confidence than the yardage list. TD scoring is binary and
high-variance, and the scorer split is usage extrapolation, the simulator's
least certain output.

Caveats re-checked 2026-09-20 against the shipped engine. The 2026-09-16
drive-length gap is closed: PENALTY_REPLAY has been ON since 2026-09-19, so
the old "replay-the-down fix is switched off" warning is gone. Two of this
list's original defects are also fixed and are not repeated in the NOTE -
Waller and the fullbacks are back in the box score (P25, k32+fb), and pocket
quarterbacks no longer scramble at the league rate (P24). What remains open:

  P18   the engine converts first-and-goal far below real (1st & 0-2.5 .323
        vs .486), diagnosed 2026-09-16 and deliberately deferred. It is the
        most relevant unfixed defect for a market settled at the goal line.
  bias  the engine now runs ~8.3% hot on touchdowns overall (5.14 offensive
        TDs a game vs the 4.75 the market totals imply, over the 2026 week-2
        slate). This is the opposite direction to the 09-16 measurement, and
        no bias correction has been fitted for this market, so it is raw in
        every number here.

Nothing here is a validated edge.

Writes data/td_props.json and dashboard/public/td_props.json.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
from datetime import datetime, timezone
from statistics import mean

from . import config, market
from .props import _kicked_off, _sims, match_player

TD_LINES_JSON = config.DATA_DIR / "td_props_lines.json"
TD_PROPS_JSON = config.DATA_DIR / "td_props.json"
PUBLIC_TD_PROPS_JSON = config.ROOT / "dashboard" / "public" / "td_props.json"

# Rushing + receiving TDs scored by the offence per point scored, 2023-25
# regular seasons (3,871 TDs / 36,825 points, 816 games; nflverse).
TD_PER_POINT = 0.1051
MIN_BOOK_PLAYERS = 12   # a book listing fewer players can't be normalised over the game
TOP_N = 25
# Gaps past this are held out as likely usage/depth-chart misses. Set from the
# 2026-09-16 sample, not validated; independent of props.MAX_GAP.
TD_MAX_GAP = 0.20

CONFIDENCE = "exploratory"
# Caveats re-checked against the live engine on 2026-09-20. The two defects
# this list shipped with on 09-16 are fixed and are deliberately NOT repeated
# here: Darren Waller and the fullbacks are back in the box score (P25,
# k32+fb) and pocket quarterbacks no longer scramble at the league rate (P24).
# Re-flagging a fixed bug misleads in the other direction. What is named below
# is what is still open.
NOTE = (
    "Lower confidence than the yardage props. Touchdowns are binary and high-variance, and "
    "the scorer split is usage extrapolation - the simulator's least certain output. Two "
    "open issues sit in these numbers. P18: the engine converts first-and-goal far below "
    "real (1st & 0-2.5 converts .323 against .486), which is the single most relevant defect "
    "for a market decided at the goal line, and it is diagnosed but not fixed. And the engine "
    "now runs about 8.3% hot on touchdowns as a whole (5.14 offensive TDs a game against the "
    "4.75 the market totals imply, measured across the 2026 week-2 slate), with no bias "
    "correction fitted for this market, so that sits raw in every number below. Books post "
    "Yes only, so the market probability is an estimate: prices are scaled to what the game "
    "total implies."
)


def is_team_entry(name: str) -> bool:
    """Books list each defence / special-teams unit as a "player"; those TDs
    are not rushing or receiving TDs, so they are out of the normalisation
    and the ranking."""
    low = name.lower()
    return "d/st" in low or low.endswith(" defense") or low.endswith(" defence")


def _lam(q: float) -> float:
    return -math.log(max(1.0 - q, 1e-9))


def book_factors(players: dict, market_total: float | None) -> dict[str, float]:
    """book -> k, the log-space scale that makes a book's Yes-only prices sum
    to the player TDs the game total implies."""
    if not market_total:
        return {}
    target = float(market_total) * TD_PER_POINT
    sums: dict[str, list[float]] = {}
    for name, books in players.items():
        if is_team_entry(name):
            continue
        for book, v in books.items():
            if v.get("yes") is not None:
                sums.setdefault(book, []).append(_lam(market.implied(v["yes"])))
    return {b: target / sum(ls) for b, ls in sums.items() if len(ls) >= MIN_BOOK_PLAYERS and sum(ls) > 0}


def market_view(books: dict, factors: dict[str, float]) -> dict | None:
    """Vig-free P(yes) averaged across books, and the best Yes / No price."""
    fair, best = [], {"yes": None, "no": None}
    for book, v in books.items():
        yes, no = v.get("yes"), v.get("no")
        if yes is not None and no is not None:
            fair.append(market.devig([yes, no])[0])
        elif yes is not None and book in factors:
            fair.append(1.0 - math.exp(-factors[book] * _lam(market.implied(yes))))
        else:
            continue
        for side, price in (("yes", yes), ("no", no)):
            if price is not None and (best[side] is None or market.implied(price) < market.implied(best[side][0])):
                best[side] = (price, book)
    if not fair:
        return None
    raw = [market.implied(v["yes"]) for v in books.values() if v.get("yes") is not None]
    return {"p_yes": mean(fair), "p_yes_raw": mean(raw), "books": len(fair), "best": best}


def rank(lines: dict, sims: dict[str, dict]) -> dict:
    rows, unmatched, unprojected, team_entries, games = [], [], 0, 0, {}
    for gid, g in (lines.get("games") or {}).items():
        sim = sims.get(gid)
        box = (sim or {}).get("box_score") or {}
        players = [(side, p) for side in ("home", "away") for p in (box.get(side) or {}).get("players") or []]
        if not players or not g.get("players"):
            unprojected += len(g.get("players") or {})
            continue
        scorers = {(side, s["player"]): s for side in ("home", "away")
                   for s in ((sim.get("scorers") or {}).get(side) or [])}
        factors = book_factors(g["players"], sim.get("market_total"))
        games[gid] = {
            "game": f"{g['away']} @ {g['home']}", "market_total": sim.get("market_total"),
            "implied_player_tds": round(float(sim["market_total"]) * TD_PER_POINT, 2)
            if sim.get("market_total") else None,
            "book_factors": {b: round(k, 3) for b, k in factors.items()},
            "sim_player_tds": round(sum(_lam(min(p.get("anytime_td") or 0.0, 0.999)) for _, p in players), 2),
        }
        margin = sim.get("margin") or {}
        for name, books in g["players"].items():
            if is_team_entry(name):
                team_entries += 1
                continue
            hit = match_player(name, players)
            if hit is None:
                # Mostly fringe players under the box score's one-touch floor;
                # a big market price here means the depth chart missed a role.
                yes = [market.implied(v["yes"]) for v in books.values() if v.get("yes") is not None]
                unmatched.append({"game_id": gid, "player": name,
                                  "p_market_raw": round(mean(yes), 4) if yes else None})
                continue
            side, p = hit
            mv = market_view(books, factors)
            if mv is None or p.get("anytime_td") is None:
                continue
            pm, pk = float(p["anytime_td"]), mv["p_yes"]
            gap = pm - pk
            pick = "yes" if gap >= 0 else "no"
            best = mv["best"][pick]
            price, book = best if best else (None, None)
            breakeven = market.implied(price) if price is not None else None
            p_side_model, p_side_market = (pm, pk) if pick == "yes" else (1 - pm, 1 - pk)
            blended = market.blend(p_side_model, p_side_market, config.MODEL_MARKET_WEIGHT)
            sc = scorers.get((side, p["player"])) or {}
            rows.append({
                "game_id": gid, "game": games[gid]["game"], "kickoff": g.get("kickoff"),
                "player": p["player"], "odds_name": name, "team": g[side],
                "position": f"{p.get('position') or ''}{p.get('depth_rank') or ''}",
                "pick": pick,
                "p_model": round(pm, 4), "p_market": round(pk, 4),
                "p_market_raw": round(mv["p_yes_raw"], 4),
                "gap": round(gap, 4),
                "ratio": round(pm / pk, 3) if pk > 0 else None,
                "price": price, "book": book, "yes_price": (mv["best"]["yes"] or (None,))[0],
                "books": mv["books"],
                # Only a side a book actually prices can be tested against a break-even.
                "breakeven": round(breakeven, 4) if breakeven is not None else None,
                "blended": round(blended, 4),
                "passes_stage1": breakeven is not None and blended - breakeven >= config.EDGE_BUFFER,
                "two_plus_td": p.get("two_plus_td"),
                "touches": p.get("touches"),
                "expected_tds": sc.get("expected_tds"),
                "usage": {k: sc.get(k) for k in ("rz_target_share", "rz_carry_share", "gl_carry_share")}
                if sc else None,
                "play_prob": sc.get("play_prob"),
                "game_sim": {"home_win_prob": sim.get("home_win_prob"), "margin_home": margin.get("p50"),
                             "total": (sim.get("total") or {}).get("p50"),
                             "market_spread": sim.get("market_spread"), "market_total": sim.get("market_total")},
                "sim_generated_at": sim.get("generated_at"),
            })
    # A game already under way cannot be bet at its pregame line, so it is
    # kept but never ranked, exactly as props.rank does. Without this the
    # carried-forward games dominate the list: on 2026-09-20 twelve of the
    # top twenty-five sat on games that had already kicked off.
    now = datetime.now(timezone.utc)
    started = [r for r in rows if _kicked_off(r.get("kickoff"), now)]
    rows = [r for r in rows if not _kicked_off(r.get("kickoff"), now)]
    # Mark each game so the page can say "pulled but already kicked off"
    # instead of counting it among the games it is still ranking.
    started_ids = {r["game_id"] for r in started} - {r["game_id"] for r in rows}
    for gid, g in games.items():
        g["started"] = gid in started_ids
    held = [r for r in rows if abs(r["gap"]) > TD_MAX_GAP]
    ranked = sorted((r for r in rows if abs(r["gap"]) <= TD_MAX_GAP), key=lambda r: -abs(r["gap"]))
    for i, r in enumerate(ranked, 1):
        r["rank"] = i
    return {"ranked": ranked, "held_out": sorted(held, key=lambda r: -abs(r["gap"])),
            "started": sorted(started, key=lambda r: -abs(r["gap"])),
            "games": games, "unmatched": sorted(unmatched, key=lambda u: -(u["p_market_raw"] or 0)),
            "team_entries": team_entries, "unprojected_players": unprojected}


def bias_summary(rows: list[dict]) -> dict | None:
    """How the simulation sits against the market on average: the TD-list
    analogue of the yardage props' under-bias check."""
    if not rows:
        return None
    return {
        "n": len(rows),
        "mean_p_model": round(mean(r["p_model"] for r in rows), 4),
        "mean_p_market": round(mean(r["p_market"] for r in rows), 4),
        "share_model_lower": round(sum(r["gap"] < 0 for r in rows) / len(rows), 3),
    }


def run(top_n: int = TOP_N) -> dict:
    if not TD_LINES_JSON.exists():
        raise SystemExit("No anytime-TD lines yet. Run: python -m src.ingest_td_props")
    lines = json.loads(TD_LINES_JSON.read_text(encoding="utf-8"))
    result = rank(lines, _sims())
    everything = result["ranked"] + result["held_out"]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lines_pulled_at": lines.get("pulled_at"), "season": lines.get("season"), "week": lines.get("week"),
        "confidence": CONFIDENCE, "note": NOTE,
        "devig": {"method": "per-book log-space scale to market_total x td_per_point (Yes-only prices)",
                  "td_per_point": TD_PER_POINT, "min_book_players": MIN_BOOK_PLAYERS},
        "model_weight": config.MODEL_MARKET_WEIGHT, "edge_buffer": config.EDGE_BUFFER, "max_gap": TD_MAX_GAP,
        # Only the games this list is still ranking, so the count cannot
        # contradict the board below it.
        "games_covered": sum(1 for g in result["games"].values() if not g.get("started")),
        "games_started": sum(1 for g in result["games"].values() if g.get("started")),
        "games_in_week": len(lines.get("games") or {}),
        "priced": len(everything),
        "unmatched_players": len(result["unmatched"]),
        # Priced by the market but absent from the simulated box score.
        "unmatched": result["unmatched"],
        "team_entries_skipped": result["team_entries"],
        "unprojected_players": result["unprojected_players"],
        "bias": bias_summary(everything),
        "games": result["games"],
        "props": result["ranked"][:top_n],
        "more": result["ranked"][top_n:],
        "held_out": result["held_out"],
        # Kept for the record but never ranked: their pregame lines can no
        # longer be bet.
        "started": result["started"],
    }
    config.ensure_dirs()
    TD_PROPS_JSON.write_text(json.dumps(payload), encoding="utf-8")
    print(f"[td-props] week {payload['week']}: {payload['priced']} players priced across "
          f"{payload['games_covered']} game(s), {len(result['held_out'])} held out, "
          f"{len(result['unmatched'])} names unmatched, {result['team_entries']} team defences skipped, "
          f"{len(result['started'])} from games already kicked off, not ranked "
          f"-> {TD_PROPS_JSON}")
    b = payload["bias"]
    if b:
        print(f"  mean sim {b['mean_p_model']:.1%} vs devigged market {b['mean_p_market']:.1%}; "
              f"sim lower on {b['share_model_lower']:.0%}")
    return payload


def publish() -> None:
    """Copy the ranking to the dashboard. Separate from run() so a sample can
    be inspected before it is shown."""
    shutil.copy(TD_PROPS_JSON, PUBLIC_TD_PROPS_JSON)
    print(f"  published -> {PUBLIC_TD_PROPS_JSON}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rank NFL anytime-TD props against the simulations.")
    parser.add_argument("--top", type=int, default=TOP_N)
    parser.add_argument("--no-publish", action="store_true", help="write data/td_props.json only")
    args = parser.parse_args()
    run(top_n=args.top)
    if not args.no_publish:
        publish()
