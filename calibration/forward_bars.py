"""Forward trust bars for the Props and TD labels (user rule, 2026-11-19). Read-only.

    python calibration/forward_bars.py <stats_player_week_2026.csv> data/board/forward_bars.json

Props bar: 300+ forward kept rows (F2 live: weeks 8 on) over 30+ games, ROI interval above
zero, and beating the bet-every-under baseline on the same rows.
TD bar: lists archived before grading (P81), 150+ forward "yes" picks, and beating the market
over 40+ games. "Forward" TD picks are the top-25 yes picks of each game's last served list
archived before its kickoff (weeks 9 on, when the live archive began; week 8 has one captured game).
"""
import glob
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STATS, OUT = sys.argv[1], sys.argv[2]
_argv, sys.argv = sys.argv, [str(ROOT / "calibration/report_card_wk4_10.py"), STATS, "unused"]
spec = importlib.util.spec_from_file_location("rc", ROOT / "calibration/report_card_wk4_10.py")
rc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc)
sys.argv = _argv

FORWARD_FROM = 8
res: dict = {}

# ---- props -------------------------------------------------------------------------------------
p = rc.prop_rows()
G = rc.f2_groups(p)
kept = G["kept"][G["kept"].week >= FORWARD_FROM]
n, games = len(kept), kept.game_id.nunique()
roi = 100 * kept.u.sum() / n if n else float("nan")
lo, hi = rc.boot_roi(kept) if n else (float("nan"), float("nan"))
ku = kept[kept.under_won.notna()]
under_roi = 100 * (ku.under_won.astype(bool).sum() * 100 / 110 - (~ku.under_won.astype(bool)).sum()) / len(ku) if len(ku) else float("nan")
w = int((kept.result == "W").sum())
props_met = bool(n >= 300 and games >= 30 and lo > 0 and roi > under_roi)
res["props"] = {"forward_weeks": sorted(int(x) for x in kept.week.unique()), "kept_rows": n, "games": games, "record": f"{w}-{n - w}",
                "win_pct": round(100 * w / n, 1) if n else None, "roi_pct": round(roi, 1), "roi_ci": [round(lo, 1), round(hi, 1)],
                "under_baseline_roi_pct": round(under_roi, 1),
                "bar": "300+ forward kept rows over 30+ games, ROI interval above zero, beating the under baseline",
                "checks": {"rows>=300": n >= 300, "games>=30": games >= 30, "roi_ci_above_zero": bool(lo > 0), "beats_under": bool(roi > under_roi)},
                "met": props_met,
                "by_week": {int(wk): {"rows": len(g), "record": f"{int((g.result == 'W').sum())}-{int((g.result == 'L').sum())}",
                                      "roi_pct": round(100 * g.u.sum() / len(g), 1)} for wk, g in kept.groupby("week")}}

# ---- TD ----------------------------------------------------------------------------------------
ts = rc.ts
last: dict = {}
for f in sorted(glob.glob(str(ROOT / "data/archive/served_lists/td/2026_w*/*.json"))):
    d = json.load(open(f, encoding="utf-8"))
    gen = ts(d["generated_at"])
    for part in ("props", "more", "held_out"):
        for r in d.get(part) or []:
            if gen < ts(r["kickoff"]) and (r["game_id"] not in last or last[r["game_id"]][0] < gen):
                last[r["game_id"]] = (gen, f)
rows = []
for gid, (gen, f) in sorted(last.items()):
    d = json.load(open(f, encoding="utf-8"))
    wk = int(gid[5:7])
    for part in ("props", "more", "held_out"):
        for r in d.get(part) or []:
            if r["game_id"] != gid:
                continue
            k = (wk, rc.player_key(r["team"], r.get("odds_name") or r["player"]))
            s = rc.stat.get(k)
            if s is None and k not in rc.played:
                continue                                           # did not play: void
            y = 0 if s is None else int(np.nan_to_num(s.rushing_tds) + np.nan_to_num(s.receiving_tds) > 0)
            price = r.get("yes_price")
            u = None if price is None else ((price / 100 if price > 0 else 100 / -price) if y else -1.0)
            rows.append({"game_id": gid, "week": wk, "part": part, "player": r["player"], "pick": r["pick"], "p": r["p_model"],
                         "pm": r["p_market"], "y": y, "u": u, "two_plus": r.get("two_plus_td")})
t = pd.DataFrame(rows)
if len(t):
    yes = t[(t.part == "props") & (t.pick == "yes")]
    priced = t[t.pm.notna()]
    brier = lambda a, b: float(((a - b) ** 2).mean())  # noqa: E731
    d_b = (priced.p - priced.y) ** 2 - (priced.pm - priced.y) ** 2
    g = d_b.groupby(priced.game_id).agg(["sum", "size"])
    rng = np.random.default_rng(20261119)
    i = rng.integers(0, len(g), (4000, len(g)))
    boot = g["sum"].to_numpy()[i].sum(1) / g["size"].to_numpy()[i].sum(1)
    blo, bhi = np.percentile(boot, [2.5, 97.5])
    yu = yes[yes.u.notna()]
    td_met = bool(len(yes) >= 150 and priced.game_id.nunique() >= 40 and bhi < 0)
    res["td"] = {"forward_weeks": sorted(int(x) for x in t.week.unique()), "games": int(t.game_id.nunique()),
                 "yes_picks": len(yes), "yes_scored": int(yes.y.sum()), "yes_predicted_pct": round(100 * yes.p.mean(), 1) if len(yes) else None,
                 "yes_market_pct": round(100 * yes.pm.mean(), 1) if len(yes) else None,
                 "yes_units": round(float(yu.u.sum()), 1), "yes_roi_pct": round(100 * float(yu.u.sum()) / len(yu), 1) if len(yu) else None,
                 "priced_rows": len(priced), "priced_games": int(priced.game_id.nunique()),
                 "sim_brier": round(brier(priced.p, priced.y), 4), "market_brier": round(brier(priced.pm, priced.y), 4),
                 "sim_minus_market_brier": round(float(d_b.mean()), 4), "brier_diff_ci": [round(float(blo), 4), round(float(bhi), 4)],
                 "bar": "lists archived first, 150+ forward yes picks, beating the market over 40+ games",
                 "checks": {"archived_first": True, "yes_picks>=150": len(yes) >= 150, "games>=40": bool(priced.game_id.nunique() >= 40),
                            "beats_market": bool(bhi < 0)},
                 "met": td_met,
                 "by_week": {int(wk): {"games": int(x.game_id.nunique()), "yes_picks": int(((x.part == "props") & (x.pick == "yes")).sum()),
                                       "yes_scored": int(x[(x.part == "props") & (x.pick == "yes")].y.sum())} for wk, x in t.groupby("week")},
                 "history_note": "Earlier graded history (weeks 4, 6, 7; lists rebuilt, not archived): top-25 yes picks went 7 of 38 against 30% predicted."}
Path(OUT).write_text(json.dumps(res, indent=1), encoding="utf-8")
print(json.dumps(res, indent=1))
