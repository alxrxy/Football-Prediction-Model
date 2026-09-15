"""Stage 1 before/after: the old points flag against the blended, devigged test.

    python calibration/stage1_before_after.py calibration/2026-09-15_stage1_before_after.md

Two samples, both read-only:
  1. Every graded live prediction (both sports, both models), with closing
     line value from clv_log (run `python -m src.clv --backfill` first).
  2. The ML models' 2025 holdout seasons, scored with the saved models (no
     retraining). Those lines are closing lines, so there is no CLV there,
     only the flag rule's record and the probability scores.

Historical predictions stored no prices, so the market is taken at -110 both
ways at the stored line. Proper scores exclude pushes.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tabulate import tabulate  # noqa: E402

from src import config, db, market  # noqa: E402
from src.features import MARGIN_SIGMA, parse_dt  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else None
W = config.MODEL_MARKET_WEIGHT
SWEEP = (0.0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.50, 1.00)
PROXY = ("sp_plus_fcs_proxy", "elo")


def comp(p):
    c = p.get("components")
    return json.loads(c) if isinstance(c, str) else (c or {})


def ats(rows, side_key):
    w = sum(1 for r in rows if r["cover"] != 0 and (r["cover"] > 0) == (r[side_key] == "home"))
    l = sum(1 for r in rows if r["cover"] != 0 and (r["cover"] > 0) != (r[side_key] == "home"))
    p = sum(1 for r in rows if r["cover"] == 0)
    rec = f"{w}-{l}" + (f"-{p}" if p else "")
    return rec + (f" ({w / (w + l) * 100:.0f}%)" if w + l else "")


def scores(rows, key):
    """Log loss and Brier of P(home covers), pushes excluded."""
    xs = [(r[key], 1.0 if r["cover"] > 0 else 0.0) for r in rows if r["cover"] != 0]
    if not xs:
        return float("nan"), float("nan")
    ll = -sum(y * math.log(max(p, 1e-9)) + (1 - y) * math.log(max(1 - p, 1e-9)) for p, y in xs) / len(xs)
    br = sum((p - y) ** 2 for p, y in xs) / len(xs)
    return ll, br


def clv_line(rows):
    xs = [r["clv"] for r in rows if r["clv"] is not None]
    if not xs:
        return "—"
    m = sum(xs) / len(xs)
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) if len(xs) > 1 else float("nan")
    return f"{m * 100:+.2f} pp (n={len(xs)}, sd {sd * 100:.2f}, beat close {sum(x > 0 for x in xs)})"


LATE: list[dict] = []   # graded predictions made after kickoff, against in-play lines


def build_live():
    s = db.get_store()
    games = {g["game_id"]: g for g in s.select("games")}
    preds = s.select("predictions")
    clv = {(r["game_id"], r["model_version"]): r for r in db.select_merged(s, "clv_log")}
    s.close()
    # The ML model has no FCS proxy of its own; a game is a proxy game for
    # both models if the baseline had to fill a side with one.
    proxy_games = {p["game_id"] for p in preds if p.get("baseline_source") in PROXY}
    rows = []
    for p in preds:
        g = games.get(p["game_id"])
        if not g or not g.get("completed") or g.get("home_points") is None or p.get("market_spread") is None:
            continue
        if parse_dt(p["generated_at"]) > parse_dt(g["kickoff_time"]):
            cover = (g["home_points"] - g["away_points"]) + float(p["market_spread"])
            LATE.append({"model": p["model_version"], "old_flag": bool(p["is_value"]), "cover": cover,
                         "old_side": "home" if float(p["edge"]) > 0 else "away"})
            continue
        c = comp(p)
        sigma = float(c.get("residual_sd") or MARGIN_SIGMA[p["sport"]])
        line, margin = float(p["market_spread"]), float(p["model_margin_home"])
        proxy = p["game_id"] in proxy_games
        baseline = p["model_version"] == config.MODEL_VERSION
        me = market.spread_edge(margin, sigma, line, [], p["sport"])
        lr = clv.get((p["game_id"], p["model_version"]))
        rows.append({
            "model": p["model_version"], "sport": p["sport"], "gid": p["game_id"],
            "game": f"{g['away_team']} @ {g['home_team']}", "sigma": sigma, "margin": margin, "line": line,
            "edge": float(p["edge"]), "cover": (g["home_points"] - g["away_points"]) + line, "proxy": proxy,
            # Old rule: the stored flag for the baseline. The ML gate kept its
            # flags off, so its old line is the same points heuristic, for reference.
            "old_flag": bool(p["is_value"]) if baseline else (abs(float(p["edge"])) >= 2 and not proxy),
            "old_side": "home" if float(p["edge"]) > 0 else "away",
            "new_flag": me["flag"] and not proxy, "new_side": me["side"], "edge_pp": me.get("edge_pp"),
            "p_model": me["p_model_home"], "p_blend": me["p_blend_home"], "p_market": 0.5,
            "clv": (float(lr["clv_pp"]) if lr and lr.get("clv_pp") is not None
                    and lr["side"] == me["side"] else None),
            "close": lr and lr.get("close_line"), "close_src": lr and lr.get("close_source"),
        })
    return rows


def build_holdout(sport):
    import pandas as pd
    import xgboost as xgb

    meta_path = config.ROOT / "models" / f"{sport}_margin.meta.json"
    if not meta_path.exists():
        return []
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    model = xgb.XGBRegressor()
    model.load_model(str(config.ROOT / "models" / f"{sport}_margin.json"))
    df = pd.read_csv(config.DATA_DIR / f"training_{sport}.csv")
    df = df[(df.season == meta["holdout_season"]) & df.market_spread.notna() & df.target_margin.notna()]
    if "both_fbs" in df and sport == "ncaaf":
        df = df[df.both_fbs == 1]
    margins = model.predict(df[meta["features"]])
    sigma = float(meta.get("residual_sd") or MARGIN_SIGMA[sport])
    rows = []
    for (_, r), margin in zip(df.iterrows(), margins):
        line, margin = float(r.market_spread), float(margin)
        me = market.spread_edge(margin, sigma, line, [], sport)
        edge = margin + line
        rows.append({"cover": float(r.target_margin) + line, "edge": edge, "margin": margin, "line": line,
                     "sigma": sigma, "old_flag": abs(edge) >= 2, "old_side": "home" if edge > 0 else "away",
                     "new_flag": me["flag"], "new_side": me["side"], "p_model": me["p_model_home"],
                     "p_blend": me["p_blend_home"], "p_market": 0.5, "proxy": False})
    return rows


def sweep(rows, sport):
    out = []
    for w in SWEEP:
        flags, blended = [], []
        for r in rows:
            me = market.spread_edge(r["margin"], r["sigma"], r["line"], [], sport, weight=w)
            blended.append({**r, "p_w": me["p_blend_home"], "side_w": me["side"]})
            if me["flag"] and not r["proxy"]:
                flags.append({**r, "side_w": me["side"]})
        ll, br = scores(blended, "p_w")
        need = market.points_to_flag(rows[0]["sigma"] if rows else MARGIN_SIGMA[sport], weight=w)
        out.append([f"{w:.2f}", f"{need:.1f}" if math.isfinite(need) else "never", len(flags),
                    ats(flags, "side_w") if flags else "—", f"{ll:.4f}", f"{br:.4f}"])
    return out


def panel(title, rows, sport, with_clv):
    lines = [f"### {title}\n"]
    rated = [r for r in rows if not r["proxy"]]
    old, new = [r for r in rows if r["old_flag"]], [r for r in rows if r["new_flag"]]
    table = [
        ["Old: \\|model − market\\| ≥ 2 pts", len(old), ats(old, "old_side"),
         clv_line(old) if with_clv else "n/a (closing lines)"],
        [f"New: blended at w={W}, {config.EDGE_BUFFER * 100:.0f} pp past break-even", len(new),
         ats(new, "new_side") if new else "—", clv_line(new) if with_clv and new else "—"],
        ["Every lean (rated games)", len(rated), ats(rated, "new_side"),
         clv_line(rated) if with_clv else "n/a"],
    ]
    lines.append(tabulate(table, headers=["Rule", "Flags", "ATS", "Mean CLV of those leans"], tablefmt="github"))
    ll_m, br_m = scores(rated, "p_model")
    ll_b, br_b = scores(rated, "p_blend")
    ll_k, br_k = scores(rated, "p_market")
    lines.append("")
    lines.append(tabulate([
        ["Model alone", f"{ll_m:.4f}", f"{br_m:.4f}"],
        [f"Blend, w={W}", f"{ll_b:.4f}", f"{br_b:.4f}"],
        ["Market alone (50/50 at its line)", f"{ll_k:.4f}", f"{br_k:.4f}"],
    ], headers=["P(home covers) from", "Log loss", "Brier"], tablefmt="github"))
    lines.append("")
    lines.append("Model weight sweep (flags exclude FCS-proxy games):\n")
    lines.append(tabulate(sweep(rated, sport), headers=["w", "Pts gap to flag at -110", "Flags", "ATS",
                                                          "Log loss", "Brier"], tablefmt="github"))
    return "\n".join(lines) + "\n"


def main():
    live = build_live()
    out = ["# Stage 1 before/after — generated by calibration/stage1_before_after.py\n",
           f"Model weight {W}, buffer {config.EDGE_BUFFER * 100:.0f} pp, devig {config.DEVIG_METHOD}. "
           "Historical predictions stored no prices: market taken at -110 both ways at the stored line. "
           "Log loss of a coin flip is 0.6931; Brier 0.25.\n"]
    late_base = [r for r in LATE if r["model"] == config.MODEL_VERSION]
    late_flags = [r for r in late_base if r["old_flag"]]
    out.append("## Live predictions graded so far\n")
    out.append(f"Excluded: {len(late_base)} baseline predictions (and their ML twins) generated after "
               f"kickoff, against in-play lines. The old rule flagged {len(late_flags)} of them "
               f"({ats(late_flags, 'old_side')}); those results are not pregame picks.\n")
    for model in (config.MODEL_VERSION, "ml-v1"):
        for sport in ("nfl", "ncaaf"):
            rows = [r for r in live if r["model"] == model and r["sport"] == sport]
            if rows:
                out.append(panel(f"{model} — {sport} ({len(rows)} games)", rows, sport, True))
    both = [r for r in live if r["model"] == config.MODEL_VERSION]
    old = [r for r in both if r["old_flag"]]
    new = [r for r in both if r["new_flag"]]
    out.append(f"**Baseline, both sports:** old flags {len(old)} → {ats(old, 'old_side')}, "
               f"CLV {clv_line(old)}. New flags {len(new)} → {ats(new, 'new_side') if new else '—'}.\n")

    flagged_detail = sorted([r for r in both if r["old_flag"] or r["new_flag"]], key=lambda r: -abs(r["edge"]))
    out.append("### Every game either rule flagged (baseline)\n")
    out.append(tabulate([[r["sport"], r["game"], f"{r['line']:+.1f}", f"{r['edge']:+.1f}",
                          "yes" if r["old_flag"] else "", "yes" if r["new_flag"] else "",
                          f"{r['edge_pp'] * 100:+.1f}" if r["edge_pp"] is not None else "—",
                          f"{r['cover']:+.1f}", "W" if r["cover"] and (r["cover"] > 0) == (r["new_side"] == "home")
                          else ("P" if not r["cover"] else "L"),
                          f"{r['close']:+.1f}" if r["close"] is not None else "—",
                          f"{r['clv'] * 100:+.1f}" if r["clv"] is not None else "—"]
                         for r in flagged_detail],
                        headers=["Sport", "Game", "Line", "Edge pts", "Old flag", "New flag", "vs BE pp",
                                 "Cover (home)", "Lean ATS", "Close", "CLV pp"], tablefmt="github"))
    out.append("")

    out.append("## ML 2025 holdout seasons (saved models, never used in fitting)\n")
    for sport in ("nfl", "ncaaf"):
        rows = build_holdout(sport)
        if rows:
            out.append(panel(f"ml-v1 — {sport} 2025 holdout ({len(rows)} games)", rows, sport, False))
    text = "\n".join(out)
    print(text)
    if OUT:
        Path(OUT).write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
