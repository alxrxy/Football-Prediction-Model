"""Week-10 FINAL BOARD (display only; reads stored outputs, changes no served number).

Tier rules: calibration-log.md, 2026-11-15 'final board' entry, written before this ran.
    python calibration/board_wk10.py   -> data/board/board_2026_w10.json, data/board/board_2026_w10.html
"""
from __future__ import annotations

import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import db  # noqa: E402
from src.export_dashboard import _market, _rerun_on_inactives  # noqa: E402

SKIP = {"2026_10_NE_DET"}   # user rule: not touched
BACKUP_QB = {               # team -> (starter, usual 2026 snap leader); official sources in the log
    "MIN": ("Kirk Cousins", "Kyler Murray"), "MIA": ("Kyle McCord", "Malik Willis"),
    "SEA": ("Drew Lock", "Sam Darnold"), "LV": ("Fernando Mendoza", "Kirk Cousins"),
    "ARI": ("Carson Beck", "Jacoby Brissett"), "BAL": ("Jacoby Brissett", "Tyler Huntley / Lamar Jackson"),
}
# Unconfirmed starter / key player at the game's run time (updated per window; empty = none).
UNCONFIRMED: dict[str, list[str]] = json.loads(
    (ROOT / "data/board/unconfirmed_2026_w10.json").read_text(encoding="utf-8")) \
    if (ROOT / "data/board/unconfirmed_2026_w10.json").exists() else {}
NOTES: dict[str, dict] = json.loads((ROOT / "data/board/notes_2026_w10.json").read_text(encoding="utf-8")) \
    if (ROOT / "data/board/notes_2026_w10.json").exists() else {}


def sgn(x: float | None, eps: float = 0.0) -> int:
    if x is None or abs(x) <= eps:
        return 0
    return 1 if x > 0 else -1


def tier(src_winners: dict, gap: float | None, official: bool, backup: list, unconf: list) -> tuple[str, list[str]]:
    named = {k: v for k, v in src_winners.items() if v != 0}
    votes = list(named.values())
    maj = 1 if votes.count(1) > votes.count(-1) else -1 if votes.count(-1) > votes.count(1) else 0
    dis = len(votes) // 2 if maj == 0 else sum(1 for v in votes if v != maj)
    why_low, why_med = [], []
    if backup:
        why_low.append("backup QB: " + ", ".join(backup))
    if unconf:
        why_low.append("unconfirmed: " + ", ".join(unconf))
    if gap is not None and gap > 5.0:
        why_low.append(f"model-market gap {gap:.1f} > 5")
    if named.get("baseline") and named.get("ml") and named["baseline"] != named["ml"]:
        why_low.append("baseline and ML disagree on the winner")
    if dis >= 2:
        why_low.append(f"{dis} disagreements on the winner")
    if why_low:
        return "Low", why_low
    if dis == 1:
        odd = [k for k, v in named.items() if v != maj]
        why_med.append(f"one disagreement ({odd[0]})")
    if gap is not None and 3.0 <= gap <= 5.0:
        why_med.append(f"model-market gap {gap:.1f} (3-5)")
    if not official:
        why_med.append("lists not official (PRELIMINARY)")
    if why_med:
        return "Medium", why_med
    return "High", ["all four agree, gap < 3, lists official, no backup QB, nothing unconfirmed"]


def main() -> None:
    store = db.get_store()
    games = {g["game_id"]: g for g in store.select("games", {"season": 2026, "week": 10, "sport": "nfl"})}
    preds = {(r["game_id"], r["model_version"]): r for r in store.select("predictions", {"game_id": list(games)})}
    sims = {r["game_id"]: r for r in store.select("game_simulations", {"game_id": list(games)})}
    odds: dict = {}
    for r in store.select("odds", {"game_id": list(games)}):
        odds.setdefault(r["game_id"], []).append(r)
    inact = db.select_merged(store, "inactives", {"season": 2026, "week": 10})
    shadow_path = ROOT / "data/board/p82_shadow_2026_w10.json"
    shadow = {g["game_id"]: g for g in json.loads(shadow_path.read_text(encoding="utf-8"))["games"]} \
        if shadow_path.exists() else {}
    board = []
    for gid, g in sorted(games.items(), key=lambda kv: str(kv[1].get("kickoff_time"))):
        if gid in SKIP:
            continue
        b, m, s = preds.get((gid, "baseline-v1")), preds.get((gid, "ml-v1")), sims.get(gid)
        home, away = g["home_team"], g["away_team"]
        row = {"game_id": gid, "matchup": f"{away} @ {home}", "kickoff": g.get("kickoff_time")}
        if not b:
            row["status"] = "NO STORED PREDICTION (not re-run per user rule)" if gid == "2026_10_WAS_NYG" else "no prediction"
            board.append(row)
            continue
        comp = json.loads(b["components"]) if isinstance(b["components"], str) else b["components"]
        l2 = comp["layer2"]
        mk = _market(odds.get(gid, [])) or {}
        spread = mk.get("spread", b.get("market_spread"))
        base_m = float(b["model_margin_home"])
        ml_m = float(m["model_margin_home"]) if m else None
        wp = float(s["home_win_prob"]) if s else None
        mkt_m = -float(spread) if spread is not None else None
        gap = abs(base_m - mkt_m) if mkt_m is not None else None
        official = _rerun_on_inactives(g, b, inact)
        backup = [f"{t} {BACKUP_QB[t][0]} (usual {BACKUP_QB[t][1]})" for t in (away, home) if t in BACKUP_QB]
        unconf = UNCONFIRMED.get(gid, [])
        winners = {"baseline": sgn(base_m), "ml": sgn(ml_m), "sim": sgn(None if wp is None else wp - 0.5),
                   "market": sgn(mkt_m)}
        t, why = tier(winners, gap, official, backup, unconf)
        top = lambda side: sorted(l2.get(f"{side}_injuries", []), key=lambda x: -x["points"])[:3]  # noqa: E731
        lean_team = home if base_m > 0 else away if base_m < 0 else "pick'em"
        row.update({
            "label": "OFFICIAL LISTS" if official else "PRELIMINARY",
            "baseline_margin_home": round(base_m, 1), "ml_margin_home": None if ml_m is None else round(ml_m, 1),
            "sim_home_wp": None if wp is None else round(wp, 3),
            "market_spread_home": spread, "market_total": mk.get("total"), "market_source": mk.get("source"),
            "market_pulled_at": mk.get("pulled_at"),
            "gap_pts": None if gap is None else round(gap, 1),
            "model_vs_market": None if mkt_m is None else round(base_m - mkt_m, 1),
            "injury_total": {away: round(-float(l2.get("away_injury_points") or 0), 2),
                             home: round(-float(l2.get("home_injury_points") or 0), 2)},
            "top_charges": {away: [(x["player"], x["position"], x["status"], x["points"]) for x in top("away")],
                            home: [(x["player"], x["position"], x["status"], x["points"]) for x in top("home")]},
            "tier": t, "tier_reasons": why, "winners": winners,
            "lean": f"{lean_team} by {abs(base_m):.1f} (baseline headline)",
            "shadow": shadow.get(gid), "notes": NOTES.get(gid, {}),
            "baseline_generated_at": b["generated_at"],
        })
        board.append(row)
    out = {"generated_at": datetime.now(timezone.utc).isoformat(), "week": 10, "season": 2026,
           "labels": {"headline": "Baseline is the headline (P8). ML, sim and the P82 shadow are shown beside it.",
                      "shadow": "P82 SHADOW, UNVALIDATED: replacement-starter credit, gates G1-G6 not run.",
                      "tier": "Tiers follow rules written in calibration-log.md before they were applied; not validated "
                              "as predictive of accuracy."},
           "games": board}
    d = ROOT / "data/board"
    d.mkdir(exist_ok=True)
    (d / "board_2026_w10.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    (d / "board_2026_w10.html").write_text(render_html(out), encoding="utf-8")
    for r in board:
        print(f"{r['matchup']:<10} {r.get('label','-'):<15} base {r.get('baseline_margin_home')} ml {r.get('ml_margin_home')} "
              f"wp {r.get('sim_home_wp')} mkt {r.get('market_spread_home')}/{r.get('market_total')} gap {r.get('gap_pts')} "
              f"| {r.get('tier','-')}: {'; '.join(r.get('tier_reasons', []))}")


def render_html(out: dict) -> str:
    e = lambda x: html.escape(str(x if x is not None else "-"))  # noqa: E731
    rows = []
    for g in out["games"]:
        if "tier" not in g:
            rows.append(f"<section class='g'><h2>{e(g['matchup'])}</h2><p class='warn'>{e(g.get('status',''))}</p></section>")
            continue
        sh = g.get("shadow")
        shadow_html = ""
        if sh:
            parts = []
            for t in sh["teams"]:
                n = t["expected_starter"]
                parts.append(
                    f"<li><b>{e(t['team'])} {e(n['name'])}</b>{' <span class=lc>LOW-CONFIDENCE (&lt;200 career dropbacks)</span>' if t['low_confidence'] else ''}: "
                    f"{n['dropbacks_2025_26']} dropbacks 2025-26 ({n['career_dropbacks_2015_26']} career since 2015); "
                    f"opp-adj EPA/db {n['epa_db_opp_adj']}, success {n['success_rate']}, CPOE {n['cpoe']}, sack rate {n['sack_rate']}; "
                    f"shrunk {n['epa_db_shrunk']:+.3f}. Usual: {e(', '.join(q['name'] + ' (' + str(q['dropbacks_2025_26']) + ' db)' for q in t['usual_starter']))} "
                    f"{t['usual_shrunk_epa_db']:+.3f}. Effect vs usual {t['pts_vs_usual']:+.1f} pts, vs replacement "
                    f"{t['pts_vs_replacement']:+.1f} pts; flat charge in headline {t['flat_qb_charge_in_headline']:.2f}.</li>")
            shadow_html = (f"<div class='shadow'><b>P82 SHADOW (UNVALIDATED)</b>: headline {sh['headline_margin_home']:+.1f} → shadow "
                           f"{sh['shadow_margin_home']:+.1f} (difference {sh['difference']:+.1f}, home margin)<ul>{''.join(parts)}</ul></div>")
        inj = " | ".join(f"{e(t)} −{v:.2f}" for t, v in g["injury_total"].items())
        top = "<br>".join(f"{e(t)}: " + ", ".join(f"{e(p)} ({e(pos)}, {e(st)}) {pts:.2f}" for p, pos, st, pts in v)
                          for t, v in g["top_charges"].items())
        notes = "".join(f"<li><b>{e(k)}</b>: {e(v)}</li>" for k, v in g["notes"].items())
        rows.append(f"""<section class='g t{g['tier']}'><h2>{e(g['matchup'])} <span class='tier'>{g['tier']}</span> <span class='lab'>{e(g['label'])}</span></h2>
<table><tr><th>Baseline (headline)</th><th>ML</th><th>Sim home win%</th><th>Market</th><th>Model − market</th></tr>
<tr><td>{g['baseline_margin_home']:+.1f}</td><td>{g['ml_margin_home']:+.1f}</td><td>{g['sim_home_wp']*100:.0f}%</td>
<td>{e(str(g['market_spread_home']))} / {e(str(g['market_total']))}</td><td>{g['model_vs_market']:+.1f}</td></tr></table>
<p class='small'>Margins are home minus away; market spread is the home line (negative = home favoured).</p>
<p><b>Injury charge totals</b>: {inj}<br><span class='small'>{top}</span></p>
<p><b>Tier {g['tier']}</b>: {e('; '.join(g['tier_reasons']))}</p>{shadow_html}<ul>{notes}</ul></section>""")
    return f"""<!DOCTYPE html><html><head><meta charset='utf-8'><title>Week 10 final board</title><style>
body{{font-family:system-ui,sans-serif;max-width:980px;margin:2em auto;padding:0 1em;color:#222}}
.g{{border:1px solid #ccc;border-radius:8px;padding:.6em 1em;margin:1em 0}}.tHigh{{border-left:6px solid #2a7}}
.tMedium{{border-left:6px solid #d90}}.tLow{{border-left:6px solid #c33}}.tier{{font-size:.8em;padding:2px 8px;border-radius:10px;background:#eee}}
.lab{{font-size:.7em;color:#555}}table{{border-collapse:collapse}}td,th{{border:1px solid #ddd;padding:3px 8px;font-size:.9em}}
.small{{font-size:.8em;color:#555}}.shadow{{background:#f6f3ff;padding:.4em .8em;border-radius:6px;font-size:.9em}}.lc{{color:#c33;font-weight:600}}.warn{{color:#c33}}
</style></head><body><h1>NFL week 10 final board</h1><p class='small'>Generated {e(out['generated_at'])}. {e(out['labels']['headline'])} {e(out['labels']['shadow'])} {e(out['labels']['tier'])}</p>
{''.join(rows)}</body></html>"""


if __name__ == "__main__":
    main()
