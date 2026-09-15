"""Closing line value for every model lean (Stage 1 of nfl-modeling-research.md).

    python -m src.clv                    fill closing lines for finished games, then report
    python -m src.clv --report           report only
    python -m src.clv --sport nfl
    python -m src.clv --backfill         log leans for already-graded predictions first

WHY CLV. A flagged ATS record says almost nothing at this sample size: telling
a genuine 55% edge from luck takes hundreds of bets. Closing line value has
about a tenth of the noise, so it becomes readable in ~50-65 bets. It also
asks a sharper question: after the model leaned one way, did the market move
that way too?

WHAT IS LOGGED. Every lean, flagged or not, one row per game and model in
clv_log. With the model at weight 0.15 in the blend a flag is rare, so waiting
for 65 flags would take more than a season. The lean sample is what says
whether the model has earned more weight; flags are reported as their own line.

HOW. At prediction time the lean side's vig-free probability at the line is
stored (p_market, from src/market.py). After the game, the closing line and
prices are devigged the same way and restated at that line (p_close), so
clv_pp = p_close - p_market, and positive means the market moved toward the
lean. The close comes from ESPN's pickcenter (DraftKings' open and close with
prices, free, both sports), else from the last pregame odds snapshot. When
DraftKings' own quote at prediction time is known, CLV is measured
book-to-book (clv_basis 'same_book'); otherwise consensus to close.
"""

from __future__ import annotations

import argparse
import math
from datetime import datetime, timedelta, timezone
from statistics import median

from . import config, db, market
from .features import MARGIN_SIGMA, parse_dt
from .http import safe_get_json

REF_BOOK = "oddsapi:draftkings"      # the book ESPN's close comes from
ESPN_BASE = {"nfl": config.ESPN_NFL, "ncaaf": config.ESPN_CFB}
ESPN_ALIASES = {"WSH": "WAS", "LAR": "LA"}
BROWSER_UA = {"User-Agent": "Mozilla/5.0"}
CLV_READABLE_N = 50                  # below this, the mean CLV is noise
# A close further than this from the line at prediction time is almost always
# bad line data (a stale or mismatched stored line), not market movement.
# Those leans are kept but marked suspect and left out of the CLV means.
MAX_PLAUSIBLE_MOVE = {"nfl": 4.5, "ncaaf": 7.5}


def _num(value) -> float | None:
    """ESPN writes lines and prices as strings: '-2.5', '+100', 'EVEN', 'PK'."""
    if value is None:
        return None
    text = str(value).strip().lower().lstrip("ou")
    if text in ("even", "ev", "pk", "pick"):
        return 100.0 if "even" in text or text == "ev" else 0.0
    try:
        return float(text)
    except ValueError:
        return None


# --- logging a lean -----------------------------------------------------------

def lean_row(pred: dict, home: str, away: str, kickoff, prices: list[dict] | None) -> dict | None:
    """The clv_log row for one prediction, or None if it has no lean."""
    me = (pred.get("components") or {}).get("market_edge")
    if not me or not me.get("side"):
        return None
    side = me["side"]
    ref = next((b for b in prices or [] if b.get("book") == REF_BOOK and b.get("spread") is not None), None)
    p_model = me["p_model_home"] if side == "home" else 1 - me["p_model_home"]
    return {
        "game_id": pred["game_id"],
        "model_version": pred["model_version"],
        "market": "spread",
        "sport": pred.get("sport"),
        "side": side,
        "team": home if side == "home" else away,
        "is_flag": bool(pred.get("is_value")),
        "kickoff_time": kickoff if isinstance(kickoff, str) or kickoff is None else kickoff.isoformat(),
        "flagged_at": pred.get("generated_at"),
        "line": me["line"],
        "price": int(me["price"]),
        "p_model": round(p_model, 4),
        "p_market": me["p_side_market"],
        "p_blend": me["p_side_blend"],
        "breakeven": me["breakeven"],
        "edge_pp": me["edge_pp"],
        "edge_points": pred.get("edge"),
        "weight": me["weight"],
        "buffer": me["buffer"],
        "devig_method": me["devig"],
        "market_source": me["market_source"],
        "ref_book": REF_BOOK if ref else None,
        "ref_line": ref["spread"] if ref else None,
        "ref_price_home": ref.get("spread_price_home") if ref else None,
        "ref_price_away": ref.get("spread_price_away") if ref else None,
    }


def log_leans(store: db.Store, rows: list[dict | None]) -> int:
    rows = [r for r in rows if r]
    if rows:
        where = db.upsert_or_mirror(store, "clv_log", rows)
        print(f"[clv] {len(rows)} lean(s) logged ({where}); {sum(r['is_flag'] for r in rows)} flagged")
    return len(rows)


# --- the close ------------------------------------------------------------------

def _espn(sport: str, path: str, params: dict | None = None, cache_minutes: int = 0, tag: str = ""):
    return safe_get_json(f"{ESPN_BASE[sport]}/{path}", params=params, headers=BROWSER_UA,
                         transport="urllib", timeout=20, retries=2,
                         cache_minutes=cache_minutes, cache_tag=tag)


def espn_event_id(sport: str, game: dict) -> str | None:
    """College game ids are ESPN event ids; NFL ids are nflverse's, so the
    ESPN event is found on that day's scoreboard by team codes."""
    if sport == "ncaaf":
        return str(game["game_id"])
    kickoff = parse_dt(game.get("kickoff_time"))
    if kickoff is None:
        return None
    day = (kickoff - timedelta(hours=5)).strftime("%Y%m%d")   # ESPN dates are US Eastern days
    board = _espn(sport, "scoreboard", {"dates": day}, cache_minutes=60, tag=f"espn_board_{sport}") or {}
    for event in board.get("events") or []:
        comp = (event.get("competitions") or [{}])[0]
        sides = {c.get("homeAway"): ESPN_ALIASES.get(c["team"]["abbreviation"], c["team"]["abbreviation"])
                 for c in comp.get("competitors") or [] if c.get("team")}
        if sides.get("home") == game["home_team"] and sides.get("away") == game["away_team"]:
            return str(event.get("id"))
    return None


def espn_close(sport: str, game: dict) -> dict | None:
    """DraftKings' closing spread and prices from ESPN's pickcenter, once the
    game is over (before then pickcenter can show live numbers)."""
    event = espn_event_id(sport, game)
    if not event:
        return None
    summary = _espn(sport, "summary", {"event": event}, cache_minutes=60 * 24 * 14, tag=f"espn_summary_{sport}")
    if not summary:
        return None
    status = (((summary.get("header") or {}).get("competitions") or [{}])[0].get("status") or {})
    if (status.get("type") or {}).get("state") != "post":
        return None
    for pc in summary.get("pickcenter") or []:
        ps = pc.get("pointSpread") or {}
        home_close = (ps.get("home") or {}).get("close") or {}
        away_close = (ps.get("away") or {}).get("close") or {}
        line = _num(home_close.get("line"))
        if line is None:
            line = _num(pc.get("spread"))
        if line is None:
            continue
        ph = _num(home_close.get("odds")) or _num((pc.get("homeTeamOdds") or {}).get("spreadOdds"))
        pa = _num(away_close.get("odds")) or _num((pc.get("awayTeamOdds") or {}).get("spreadOdds"))
        name = ((pc.get("provider") or {}).get("name") or "espn").lower().replace(" ", "")
        return {
            "close_line": line,
            "close_price_home": int(ph) if ph else None,
            "close_price_away": int(pa) if pa else None,
            "close_source": f"espn:{name}",
            "close_at": game.get("kickoff_time"),
        }
    return None


def snapshot_close(store: db.Store, game: dict) -> dict | None:
    """The last pregame odds snapshot, as a consensus: median line, and the
    median prices of the books at that line."""
    kickoff = parse_dt(game.get("kickoff_time"))
    rows = [r for r in db.select_merged(store, "odds_snapshots", {"game_id": game["game_id"]})
            if kickoff is None or (parse_dt(r.get("pulled_at")) or kickoff) < kickoff]
    latest: dict[str, dict] = {}
    for r in rows:
        if r.get("spread") is None:
            continue
        if r["book"] not in latest or parse_dt(r["pulled_at"]) > parse_dt(latest[r["book"]]["pulled_at"]):
            latest[r["book"]] = r
    if not latest:
        return None
    line = median(float(r["spread"]) for r in latest.values())
    line = round(line * 2) / 2
    at_line = [r for r in latest.values() if float(r["spread"]) == line
               and r.get("spread_price_home") and r.get("spread_price_away")]
    return {
        "close_line": line,
        "close_price_home": int(median(r["spread_price_home"] for r in at_line)) if at_line else None,
        "close_price_away": int(median(r["spread_price_away"] for r in at_line)) if at_line else None,
        "close_source": "oddsapi_last_pregame",
        "close_at": max(r["pulled_at"] for r in latest.values()),
    }


def apply_close(row: dict, close: dict) -> dict:
    """CLV of one logged lean against a close."""
    sport, line, side = row["sport"], float(row["line"]), row["side"]
    table = market.margin_table(sport)
    method = row.get("devig_method") or config.DEVIG_METHOD
    own = (lambda p: p) if side == "home" else (lambda p: 1 - p)

    ph = close.get("close_price_home") or market.ASSUMED_PRICE
    pa = close.get("close_price_away") or market.ASSUMED_PRICE
    p_close_home = table.move(market.devig([ph, pa], method)[0], float(close["close_line"]), line)

    same_book = (row.get("ref_book") and row.get("ref_line") is not None
                 and close["close_source"] == "espn:" + row["ref_book"].split(":")[-1])
    if same_book:
        rh = row.get("ref_price_home") or market.ASSUMED_PRICE
        ra = row.get("ref_price_away") or market.ASSUMED_PRICE
        p_then = own(table.move(market.devig([rh, ra], method)[0], float(row["ref_line"]), line))
    else:
        p_then = float(row["p_market"])
    # A prediction made after kickoff was priced against an in-play line
    # (19 college games on 2026-09-12): there is no pregame lean to value.
    flagged, kickoff = parse_dt(row.get("flagged_at")), parse_dt(row.get("kickoff_time"))
    if flagged and kickoff and flagged > kickoff:
        basis = "after_kickoff"
    elif abs(float(close["close_line"]) - line) > MAX_PLAUSIBLE_MOVE.get(sport, 7.5):
        basis = "suspect_line"
    else:
        basis = "same_book" if same_book else "consensus"
    return {
        **{k: close.get(k) for k in ("close_line", "close_price_home", "close_price_away",
                                     "close_source", "close_at")},
        "p_close": round(own(p_close_home), 4),
        "clv_pp": round(own(p_close_home) - p_then, 4) if basis in ("same_book", "consensus") else None,
        "clv_basis": basis,
    }


def ats_result(row: dict, game: dict) -> str | None:
    if not game.get("completed") or game.get("home_points") is None:
        return None
    cover = (game["home_points"] - game["away_points"]) + float(row["line"])  # + => home covered
    if cover == 0:
        return "P"
    return "W" if (cover > 0) == (row["side"] == "home") else "L"


def _closed(r: dict) -> bool:
    return r.get("clv_pp") is not None or r.get("clv_basis") in ("suspect_line", "after_kickoff")


def capture(sport: str | None = None, store: db.Store | None = None,
            recompute: bool = False) -> list[dict]:
    """Fill closes and results for logged leans whose game is over.

    recompute re-derives CLV from each row's stored close, for when the
    arithmetic in apply_close changes; it makes no ESPN calls for those rows.
    """
    own_store = store is None
    store = store or db.get_store()
    where = {"sport": sport} if sport else None
    rows = db.select_merged(store, "clv_log", where)
    games = {g["game_id"]: g for g in store.select("games", where)}
    now = datetime.now(timezone.utc)
    closes: dict[str, dict | None] = {}
    changed = []
    for r in rows:
        game = games.get(r["game_id"])
        kickoff = parse_dt(r.get("kickoff_time")) or (parse_dt(game.get("kickoff_time")) if game else None)
        if not game or kickoff is None or kickoff > now:
            continue
        if recompute and r.get("close_line") is not None:
            updated = {**r, **apply_close(r, r)}
            if updated != r:
                updated["is_flag"] = bool(updated.get("is_flag"))
                changed.append(updated)
            continue
        if _closed(r) and r.get("result") is not None:
            continue
        updated = dict(r)
        if not _closed(r):
            if r["game_id"] not in closes:
                closes[r["game_id"]] = espn_close(r["sport"], game) or snapshot_close(store, game)
            close = closes[r["game_id"]]
            if close:
                updated.update(apply_close(r, close))
        if r.get("result") is None and (res := ats_result(r, game)):
            updated["result"] = res
            updated["graded_at"] = db.utcnow()
        if updated != r:
            updated["is_flag"] = bool(updated.get("is_flag"))
            changed.append(updated)
    if changed:
        db.upsert_or_mirror(store, "clv_log", changed)
        by_key = {(c["game_id"], c["model_version"]): c for c in changed}
        rows = [by_key.get((r["game_id"], r["model_version"]), r) for r in rows]
    print(f"[clv] {len(changed)} lean(s) given a close or result")
    if own_store:
        store.close()
    return rows


# --- backfill -------------------------------------------------------------------

def backfill(store: db.Store, sport: str | None = None) -> int:
    """Log leans for graded predictions made before clv_log existed.

    Those predictions stored no prices, so the market is taken at -110 both
    ways at the stored line (50/50), and is_flag is the new blended test, not
    the old points flag the prediction carried.
    """
    where = {"sport": sport} if sport else None
    games = {g["game_id"]: g for g in store.select("games", where)}
    have = {(r["game_id"], r["model_version"]) for r in db.select_merged(store, "clv_log", where)}
    rows = []
    for p in store.select("predictions", where):
        game = games.get(p["game_id"])
        if (p["game_id"], p["model_version"]) in have or not game or p.get("market_spread") is None:
            continue
        comp = p.get("components") or {}
        if isinstance(comp, str):
            import json
            comp = json.loads(comp)
        sigma = comp.get("residual_sd") or MARGIN_SIGMA.get(p["sport"], 16.0)
        me = market.spread_edge(float(p["model_margin_home"]), float(sigma), float(p["market_spread"]),
                                [], p["sport"])
        gated = p["model_version"] != config.MODEL_VERSION and not (comp.get("value_gate") or {}).get("allowed")
        proxy = p.get("baseline_source") in ("sp_plus_fcs_proxy", "elo")
        pred = {**p, "components": {"market_edge": me},
                "is_value": me["flag"] and not gated and not proxy}
        row = lean_row(pred, game["home_team"], game["away_team"], game.get("kickoff_time"), [])
        if row:
            row["market_source"] = "assumed_-110 (backfill)"
            rows.append(row)
    return log_leans(store, rows)


# --- report ---------------------------------------------------------------------

def _stats(rows: list[dict]) -> dict:
    clv = [float(r["clv_pp"]) for r in rows if r.get("clv_pp") is not None]
    n = len(clv)
    mean = sum(clv) / n if n else None
    sd = math.sqrt(sum((x - mean) ** 2 for x in clv) / (n - 1)) if n > 1 else None
    se = sd / math.sqrt(n) if sd is not None else None
    w = sum(r.get("result") == "W" for r in rows)
    l = sum(r.get("result") == "L" for r in rows)
    return {"n": n, "mean": mean, "sd": sd, "t": (mean / se) if se else None,
            "beat": sum(x > 0 for x in clv), "same": sum(x == 0 for x in clv), "w": w, "l": l}


def report(rows: list[dict]) -> str:
    lines = ["", "CLOSING LINE VALUE (vig-free probability at the close minus at prediction, lean side)"]
    late = [r for r in rows if r.get("clv_basis") == "after_kickoff"]
    rows = [r for r in rows if r.get("clv_basis") != "after_kickoff"]
    groups: list[tuple[str, list[dict]]] = []
    for model in sorted({r["model_version"] for r in rows}):
        mine = [r for r in rows if r["model_version"] == model]
        groups.append((f"{model}, all leans", mine))
        groups.append((f"{model}, flagged", [r for r in mine if r.get("is_flag")]))
        for sport in sorted({r["sport"] for r in mine}):
            groups.append((f"{model}, {sport} leans", [r for r in mine if r["sport"] == sport]))
    suspect = [r for r in rows if r.get("clv_basis") == "suspect_line"]
    for label, grp in groups:
        s = _stats(grp)
        if not s["n"]:
            lines.append(f"  {label:28} n=  0")
            continue
        t = f"t {s['t']:+.2f}" if s["t"] is not None else "t  n/a"
        lines.append(
            f"  {label:28} n={s['n']:>3}  mean {s['mean'] * 100:+.2f} pp  "
            f"(sd {((s['sd'] or 0) * 100):.2f}, {t})  beat close {s['beat']}/{s['n']}"
            f" (no move {s['same']})  ATS {s['w']}-{s['l']}"
        )
    if suspect:
        lines.append(
            f"  {len(suspect)} lean(s) left out: the close sat further from the stored line than a "
            f"market moves ({', '.join(f'{k} >{v} pts' for k, v in MAX_PLAUSIBLE_MOVE.items())}), "
            "which means the stored line was wrong, not that the market moved."
        )
    if late:
        lines.append(f"  {len(late)} lean(s) left out: predicted after kickoff, against an in-play line.")
    lines.append(
        f"  CLV is readable from ~{CLV_READABLE_N}-65 leans; below that the mean is noise. Raise "
        f"MODEL_MARKET_WEIGHT (now {config.MODEL_MARKET_WEIGHT}) only on positive CLV over 65+."
    )
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Closing line value for model leans.")
    parser.add_argument("--sport", choices=["ncaaf", "nfl"])
    parser.add_argument("--report", action="store_true", help="report only; no ESPN calls")
    parser.add_argument("--backfill", action="store_true", help="log leans for graded predictions first")
    parser.add_argument("--recompute", action="store_true", help="re-derive CLV from stored closes")
    args = parser.parse_args()
    s = db.get_store()
    if args.backfill:
        backfill(s, args.sport)
    rows = (db.select_merged(s, "clv_log", {"sport": args.sport} if args.sport else None)
            if args.report else capture(args.sport, s, recompute=args.recompute))
    print(report(rows))
    s.close()
