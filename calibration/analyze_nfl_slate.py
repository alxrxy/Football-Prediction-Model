"""Per-game scoring, tier breakdown and miss diagnostics for one graded NFL slate. Read-only.

    python calibration/analyze_nfl_slate.py 2026-09-13 calibration/2026-09-13_nfl.md

Reads predictions and finals from the configured store (run
`python -m src.grade --sport nfl --refresh` first) and pregame simulations from
the local SQLite mirror, where `game_simulations` lives.
"""
import json, sys, math
from datetime import date
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from src import db
from src.features import parse_dt
from src.predict_baseline import slate_window
from tabulate import tabulate

SLATE = sys.argv[1] if len(sys.argv) > 1 else "2026-09-13"
OUT = sys.argv[2] if len(sys.argv) > 2 else None
start, end = slate_window(date.fromisoformat(SLATE))

s = db.get_store()
games = {g["game_id"]: g for g in s.select("games", {"sport": "nfl"})}
preds = s.select("predictions", {"sport": "nfl"})
s.close()
local = db.SqliteStore()
sims = {r["game_id"]: r for r in local.select("game_simulations") if r.get("sport") == "nfl"}
local.close()


def comp(p):
    c = p.get("components")
    return json.loads(c) if isinstance(c, str) else (c or {})


# Unknown-snap QBs are charged DEFAULT_SNAP_SHARE (0.35) x 1.0 x 6.0 = 2.1 pts
# (2.4 with a status multiplier). A real starter's charge is far larger.
def p2_charge(details):
    return sum(abs(d.get("points") or 0) for d in details
               if d.get("position") == "QB" and 1.9 <= abs(d.get("points") or 0) <= 2.5)


by = {}
for p in preds:
    g = games.get(p["game_id"])
    k = parse_dt(g.get("kickoff_time")) if g else None
    if not g or not k or not (start <= k < end):
        continue
    by.setdefault(p["game_id"], {})[p["model_version"]] = p

rows = []
for gid, mp in by.items():
    b, m = mp.get("baseline-v1"), mp.get("ml-v1")
    g = games[gid]
    if not b or g.get("home_points") is None or not g.get("completed"):
        continue
    c = comp(b); l2 = c.get("layer2", {})
    actual = g["home_points"] - g["away_points"]
    mkt = b["market_spread"]
    sim = sims.get(gid)
    r = dict(
        gid=gid, kick=parse_dt(g["kickoff_time"]), home=g["home_team"], away=g["away_team"],
        hp=g["home_points"], ap=g["away_points"], actual=actual,
        pred=b["model_margin_home"], wp=b["model_win_prob_home"], mkt=mkt, edge=b["edge"],
        conf=b["confidence"], is_value=bool(b["is_value"]), l1=c.get("layer1_baseline_margin"),
        hfa=l2.get("home_field", 0), rest=l2.get("rest", 0), travel=l2.get("travel", 0),
        inj=l2.get("injury", 0) or 0, wind=l2.get("wind_factor", 1) or 1,
        p2_home=p2_charge(l2.get("home_injuries") or []), p2_away=p2_charge(l2.get("away_injuries") or []),
        ml_pred=m["model_margin_home"] if m else None, ml_edge=m["edge"] if m else None,
        ml_wp=m["model_win_prob_home"] if m else None, ml_conf=m["confidence"] if m else None,
        sim_conf=sim.get("score_confidence") if sim else None,
        sim_after_kick=bool(sim and parse_dt(sim["generated_at"]) > parse_dt(g["kickoff_time"])),
    )
    r["err"] = r["pred"] - actual                          # + => model too high on home
    r["ml_err"] = (r["ml_pred"] - actual) if r["ml_pred"] is not None else None
    r["mkt_err"] = (-mkt - actual) if mkt is not None else None
    r["resid"] = (actual + mkt) if mkt is not None else None   # + => home covered
    r["su"] = None if actual == 0 else ((r["wp"] > 0.5) == (actual > 0))
    r["ml_su"] = None if actual == 0 or r["ml_wp"] is None else ((r["ml_wp"] > 0.5) == (actual > 0))
    r["mkt_su"] = None if (mkt is None or mkt == 0 or actual == 0) else ((mkt < 0) == (actual > 0))

    def ats(edge):
        if edge is None or edge == 0 or r["resid"] is None: return None
        if r["resid"] == 0: return "P"
        return "W" if (edge > 0) == (r["resid"] > 0) else "L"
    r["ats"], r["ml_ats"] = ats(r["edge"]), ats(r["ml_edge"])
    r["lean"] = (r["home"] if r["edge"] > 0 else r["away"]) if r["edge"] else None
    r["su_pick"] = r["home"] if r["wp"] > 0.5 else r["away"]
    r["lean_fav"] = None if (mkt in (None, 0) or not r["edge"]) else ((r["edge"] > 0) == (mkt < 0))
    r["agree"] = None if not r["ml_edge"] else ((r["edge"] > 0) == (r["ml_edge"] > 0))
    # The edge with the P2 default-share QB charges removed (approximate: same
    # wind multiplier on the injury term as the model uses).
    r["edge_p2"] = r["edge"] + (r["p2_home"] - r["p2_away"]) * r["wind"]
    r["ats_p2"] = ats(r["edge_p2"])
    rows.append(r)
rows.sort(key=lambda r: (r["kick"], r["away"]))


def pct(a, n): return f"{a}/{n} ({a/n*100:.0f}%)" if n else "—"
def rec(rs, key="ats"):
    w = sum(r[key] == "W" for r in rs); l = sum(r[key] == "L" for r in rs); p = sum(r[key] == "P" for r in rs)
    return (f"{w}-{l}" + (f"-{p}" if p else "") + (f" ({w/(w+l)*100:.0f}%)" if w + l else "")) if rs else "—"
def su(rs, key="su"):
    xs = [r[key] for r in rs if r[key] is not None]; return pct(sum(xs), len(xs))
def mean(xs):
    xs = [x for x in xs if x is not None]; return sum(xs)/len(xs) if xs else float("nan")
def mae(rs, k): return mean([abs(r[k]) for r in rs if r[k] is not None])
def corr(xs, ys):
    mx, my = mean(xs), mean(ys)
    d = math.sqrt(sum((x-mx)**2 for x in xs) * sum((y-my)**2 for y in ys))
    return sum((x-mx)*(y-my) for x, y in zip(xs, ys)) / d if d else float("nan")
def mark(v): return "✓" if v else ("✗" if v is False else "tie")


out = []
P = out.append
P(f"## Full slate — {SLATE} ({len(rows)} graded games)\n")
tbl = []
for r in rows:
    tbl.append([
        r["kick"].strftime("%H:%MZ"), f"{r['away']} @ {r['home']}", f"{r['ap']}-{r['hp']}",
        f"{-r['pred']:+.1f}", f"{r['mkt']:+.1f}", f"{r['edge']:+.1f}",
        r["su_pick"], mark(r["su"]), r["lean"] or "—", r["ats"] or "—",
        f"{r['actual']:+d}", f"{r['err']:+.1f}", f"{r['mkt_err']:+.1f}",
        f"{r['inj']:+.1f}" if r["inj"] else "", "value" if r["is_value"] else "", r["conf"],
        f"{-r['ml_pred']:+.1f}" if r["ml_pred"] is not None else "—", mark(r["ml_su"]), r["ml_ats"] or "—",
    ])
P(tabulate(tbl, headers=["Kick", "Away @ Home", "Final (A-H)", "Model", "Market", "Edge", "SU pick", "SU",
                         "ATS lean", "ATS", "Act. margin", "Model err", "Mkt err", "Inj adj", "Flag", "Tier",
                         "ML model", "ML SU", "ML ATS"], tablefmt="github"))
P("\nModel / Market / ML model are home lines (negative = home favored). SU pick = side with win prob > 50%. "
  "ATS lean = sign of edge. Act. margin = home − away. Model err = predicted home margin − actual (+ = too high on home).\n")

P("## Headline\n")
msu = [r for r in rows if r["mkt_su"] is not None]
brier = lambda k: mean([(r[k] - (1.0 if r["actual"] > 0 else 0.5 if r["actual"] == 0 else 0.0))**2 for r in rows])
P(tabulate([
    ["Straight up", su(rows), su(rows, "ml_su"), f"fav {pct(sum(r['mkt_su'] for r in msu), len(msu))}"],
    ["ATS, all", rec(rows), rec(rows, "ml_ats"), ""],
    ["ATS, value-flagged", rec([r for r in rows if r["is_value"]]), "gate off", ""],
    ["ATS, not flagged", rec([r for r in rows if not r["is_value"]]), "", ""],
    ["Margin MAE", f"{mae(rows, 'err'):.2f}", f"{mae(rows, 'ml_err'):.2f}", f"{mae(rows, 'mkt_err'):.2f}"],
    ["Mean signed err (+ = too high on home)", f"{mean([r['err'] for r in rows]):+.2f}",
     f"{mean([r['ml_err'] for r in rows]):+.2f}", f"{mean([r['mkt_err'] for r in rows]):+.2f}"],
    ["Closer to final than market", f"{sum(abs(r['err']) < abs(r['mkt_err']) for r in rows)}/{len(rows)}",
     f"{sum(abs(r['ml_err']) < abs(r['mkt_err']) for r in rows)}/{len(rows)}", ""],
    ["Brier", f"{brier('wp'):.3f}", f"{brier('ml_wp'):.3f}", ""],
], headers=["", "Baseline", "ML", "Market"], tablefmt="github"))

P("\n## Confidence tiers\n")
tiers = []
for model, ck, sk, ak, ek in (("Baseline", "conf", "su", "ats", "err"), ("ML", "ml_conf", "ml_su", "ml_ats", "ml_err")):
    for t in ("high", "medium", "low"):
        grp = [r for r in rows if r[ck] == t]
        tiers.append([model, t, len(grp), su(grp, sk) if grp else "—", rec(grp, ak),
                      f"{mae(grp, ek):.2f}" if grp else "—", f"{mae(grp, 'mkt_err'):.2f}" if grp else "—"])
P(tabulate(tiers, headers=["Model", "Tier", "n", "SU", "ATS", "MAE", "Market MAE"], tablefmt="github"))
sc = {}
for r in rows: sc[r["sim_conf"]] = sc.get(r["sim_conf"], 0) + 1
P(f"\nSimulator score_confidence on these games: {sc}.")

P("\n### Splits that do vary (baseline)\n")
split = []
def add(label, grp):
    split.append([label, len(grp), su(grp), rec(grp), f"{mae(grp, 'err'):.2f}" if grp else "—",
                  f"{mae(grp, 'mkt_err'):.2f}" if grp else "—",
                  f"{mean([abs(r['edge']) for r in grp]):.1f}" if grp else "—"])
add("value-flagged", [r for r in rows if r["is_value"]])
add("not flagged", [r for r in rows if not r["is_value"]])
for lo, hi in ((0, 2), (2, 4), (4, 6), (6, 99)):
    add(f"|edge| {lo}-{hi if hi < 99 else '+'}", [r for r in rows if lo <= abs(r["edge"]) < hi])
add("baseline & ML lean agree", [r for r in rows if r["agree"]])
add("baseline & ML lean disagree", [r for r in rows if r["agree"] is False])
add("|injury adj| >= 1", [r for r in rows if abs(r["inj"]) >= 1])
add("|injury adj| < 1", [r for r in rows if abs(r["inj"]) < 1])
add("lean favorite", [r for r in rows if r["lean_fav"]])
add("lean underdog", [r for r in rows if r["lean_fav"] is False])
add("lean home", [r for r in rows if r["edge"] > 0])
add("lean away", [r for r in rows if r["edge"] < 0])
P(tabulate(split, headers=["Split", "n", "SU", "ATS", "MAE", "Market MAE", "Mean |edge|"], tablefmt="github"))

P("\n## Directional diagnostics (baseline)\n")
num = sum(r["edge"]*r["resid"] for r in rows); den = sum(r["edge"]**2 for r in rows)
P(f"- Best-fit weight on the edge (actual = market + w·edge): w = {num/den:+.2f} (1 = trust model fully, 0 = market only)")
P(f"- corr(edge, cover residual) = {corr([r['edge'] for r in rows], [r['resid'] for r in rows]):+.3f} over n={len(rows)}")
P(f"- corr(ML edge, cover residual) = {corr([r['ml_edge'] for r in rows], [r['resid'] for r in rows]):+.3f}")
P(f"- Home teams covered {sum(r['resid']>0 for r in rows)}/{sum(r['resid']!=0 for r in rows)}; "
  f"home teams won {sum(r['actual']>0 for r in rows)}/{len(rows)}")
P(f"- Mean signed edge {mean([r['edge'] for r in rows]):+.2f}; leaned home in {sum(r['edge']>0 for r in rows)}/{len(rows)}")
ys = [r["resid"] for r in rows]
for name in ("l1", "hfa", "rest", "travel", "inj"):
    vals = [r[name] or 0 for r in rows]
    mv = mean(vals); sd = math.sqrt(sum((v-mv)**2 for v in vals)/len(vals))
    P(f"  - component {name}: mean {mv:+.2f}, sd {sd:.2f}, corr with cover residual {corr(vals, ys) if sd else float('nan'):+.3f}")

P("\n## P2 counterfactual (default-share QB charges removed)\n")
p2 = [r for r in rows if r["p2_home"] or r["p2_away"]]
P(tabulate([[f"{r['away']} @ {r['home']}", f"{r['p2_away']:.1f}", f"{r['p2_home']:.1f}", f"{r['edge']:+.1f}",
             f"{r['edge_p2']:+.1f}", r["ats"], r["ats_p2"],
             "yes" if (r["ats"] != r["ats_p2"]) else "", "value→no" if r["is_value"] and abs(r["edge_p2"]) < 2
             else ("no→value" if not r["is_value"] and abs(r["edge_p2"]) >= 2 else "")] for r in p2],
           headers=["Game", "Away QB charge", "Home QB charge", "Edge", "Edge w/o P2", "ATS", "ATS w/o P2",
                    "Lean flips?", "Flag change"], tablefmt="github"))
P(f"\nAll games: ATS {rec(rows)} as graded → {rec(rows, 'ats_p2')} without P2 charges; "
  f"MAE unchanged in sign logic, edge change mean {mean([r['edge_p2']-r['edge'] for r in rows]):+.2f}.")

P("\n## Confidently wrong (|edge| >= 4, lost ATS)\n")
bad = sorted([r for r in rows if r["ats"] == "L" and abs(r["edge"]) >= 4], key=lambda r: -abs(r["edge"]))
P(tabulate([[f"{r['away']} @ {r['home']}", f"{r['edge']:+.1f}", r["lean"], f"{-r['pred']:+.1f}", f"{r['mkt']:+.1f}",
             f"{r['ap']}-{r['hp']}", f"{r['resid']:+.1f}", f"{r['l1']:+.1f}",
             f"{r['hfa']+r['rest']+r['travel']:+.1f}", f"{r['inj']:+.1f}",
             f"{-r['ml_pred']:+.1f}"] for r in bad],
           headers=["Game", "Edge", "Lean", "Model", "Market", "Final A-H", "Cover resid", "Power diff",
                    "HFA+rest+travel", "Inj", "ML model"], tablefmt="github"))
late = [f"{r['away']}@{r['home']}" for r in rows if r["sim_after_kick"]]
if late:
    P(f"\nNote: pregame simulations for {len(late)} games were generated after kickoff ({', '.join(late)}); "
      "their sim projections are not graded.")

text = "\n".join(out)
print(text)
if OUT:
    open(OUT, "w", encoding="utf-8").write(text + "\n")
    json.dump(rows, open(OUT.replace(".md", ".json"), "w"), default=str, indent=1)
