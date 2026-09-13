"""Per-game scoring + miss diagnostics for one graded CFB slate. Read-only."""
import json, sys, math
from datetime import datetime, timedelta, timezone
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from src import db
from src.features import parse_dt
from tabulate import tabulate

SLATE = sys.argv[1] if len(sys.argv) > 1 else "2026-09-12"
OUT = sys.argv[2] if len(sys.argv) > 2 else None
start = datetime.fromisoformat(SLATE).replace(hour=11, tzinfo=timezone.utc)
end = start + timedelta(days=1)

s = db.get_store()
games = {g["game_id"]: g for g in s.select("games", {"sport": "ncaaf"})}
preds = s.select("predictions", {"sport": "ncaaf"})
s.close()

def comp(p):
    c = p.get("components")
    return json.loads(c) if isinstance(c, str) else (c or {})

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
    if not b or g.get("home_points") is None:
        continue
    c = comp(b); l2 = c.get("layer2", {})
    actual = g["home_points"] - g["away_points"]
    mkt = b["market_spread"]
    r = dict(
        gid=gid, kick=parse_dt(g["kickoff_time"]), home=g["home_team"], away=g["away_team"],
        neutral=bool(g.get("is_neutral_site")), hp=g["home_points"], ap=g["away_points"],
        actual=actual, pred=b["model_margin_home"], wp=b["model_win_prob_home"],
        mkt=mkt, edge=b["edge"], conf=b["confidence"], src=b["baseline_source"],
        is_value=bool(b["is_value"]), l1=c.get("layer1_baseline_margin"),
        hfa=l2.get("home_field", 0), rest=l2.get("rest", 0), travel=l2.get("travel", 0),
        inj=l2.get("injury", 0) or 0, inj_cov=l2.get("injury_coverage"),
        inj_detail=(l2.get("home_injuries") or []) + (l2.get("away_injuries") or []),
        wind=l2.get("wind_factor", 1), books=(c.get("market") or {}).get("books"),
        ml_pred=m["model_margin_home"] if m else None, ml_edge=m["edge"] if m else None,
        ml_elo=((comp(m).get("features") or {}).get("elo_diff")) if m else None,
    )
    r["err"] = r["pred"] - actual                       # + => model too high on home
    r["mkt_err"] = (-mkt - actual) if mkt is not None else None
    r["resid"] = (actual + mkt) if mkt is not None else None   # + => home covered
    r["su"] = None if actual == 0 else ((r["wp"] > 0.5) == (actual > 0))
    r["mkt_su"] = None if (mkt is None or mkt == 0 or actual == 0) else ((mkt < 0) == (actual > 0))
    def ats(edge):
        if edge is None or r["resid"] is None: return None
        if r["resid"] == 0: return "P"
        return "W" if (edge > 0) == (r["resid"] > 0) else "L"
    r["ats"], r["ml_ats"] = ats(r["edge"]), ats(r["ml_edge"])
    r["lean"] = (r["home"] if r["edge"] > 0 else r["away"]) if r["edge"] is not None else None
    r["lean_fav"] = None if (mkt in (None, 0) or r["edge"] is None) else ((r["edge"] > 0) == (mkt < 0))
    rows.append(r)
rows.sort(key=lambda r: r["kick"])

def pct(a, n): return f"{a}/{n} ({a/n*100:.0f}%)" if n else "—"
def rec(rs, key="ats"):
    w = sum(r[key] == "W" for r in rs); l = sum(r[key] == "L" for r in rs); p = sum(r[key] == "P" for r in rs)
    return f"{w}-{l}" + (f"-{p}" if p else "") + (f" ({w/(w+l)*100:.0f}%)" if w + l else "")
def mean(xs):
    xs = [x for x in xs if x is not None]; return sum(xs)/len(xs) if xs else float("nan")
def mae(rs, k): return mean([abs(r[k]) for r in rs if r[k] is not None])

out = []
P = out.append
P(f"## Full slate — {SLATE} ({len(rows)} graded games)\n")
tbl = []
for r in rows:
    tbl.append([
        r["kick"].strftime("%H:%MZ"),
        f"{r['away']} @ {r['home']}" + (" (N)" if r["neutral"] else ""),
        f"{r['ap']}-{r['hp']}",
        f"{-r['pred']:+.1f}", f"{r['mkt']:+.1f}" if r["mkt"] is not None else "—",
        f"{r['edge']:+.1f}" if r["edge"] is not None else "—",
        r["lean"] or "—", r["ats"] or "—",
        "✓" if r["su"] else ("✗" if r["su"] is False else "tie"),
        f"{r['actual']:+d}", f"{r['err']:+.1f}",
        f"{r['mkt_err']:+.1f}" if r["mkt_err"] is not None else "—",
        f"{r['inj']:+.1f}" if r["inj"] else "",
        r["conf"] + ("/FCS" if r["src"] == "sp_plus_fcs_proxy" else ""),
        f"{-r['ml_pred']:+.1f}" if r["ml_pred"] is not None else "—", r["ml_ats"] or "—",
    ])
P(tabulate(tbl, headers=["Kick", "Away @ Home", "Final (A-H)", "Model", "Market", "Edge", "Lean",
                         "ATS", "SU", "Act. margin", "Model err", "Mkt err", "Inj adj", "Tier",
                         "ML model", "ML ATS"], tablefmt="github"))
P("\nSpreads are home lines (negative = home favored). Model err = predicted home margin - actual home margin (+ = too high on home). Mkt err = same for the market line.\n")

rated = [r for r in rows if r["src"] == "power_rating" and r["mkt"] is not None]
proxy = [r for r in rows if r["src"] == "sp_plus_fcs_proxy"]
P("## Headline\n")
su = [r for r in rows if r["su"] is not None]; msu = [r for r in rows if r["mkt_su"] is not None]
P(f"- SU: model {pct(sum(r['su'] for r in su), len(su))}; market favorite {pct(sum(r['mkt_su'] for r in msu), len(msu))}")
P(f"- ATS (lean = sign of edge): all {rec(rows)}; fully rated {rec(rated)}; FCS-proxy {rec(proxy)}; flagged value {rec([r for r in rows if r['is_value']])}")
P(f"- ML ATS: all {rec(rows, 'ml_ats')}; fully rated {rec(rated, 'ml_ats')}")
P(f"- MAE: model {mae(rows,'err'):.2f} vs market {mae([r for r in rows if r['mkt'] is not None],'mkt_err'):.2f} (all); "
  f"rated {mae(rated,'err'):.2f} vs {mae(rated,'mkt_err'):.2f}; FCS-proxy {mae(proxy,'err'):.2f} vs {mae(proxy,'mkt_err'):.2f}")
closer = sum(abs(r["err"]) < abs(r["mkt_err"]) for r in rated)
P(f"- Model closer to the final margin than the market in {closer}/{len(rated)} fully-rated games")
P(f"- ML MAE {mean([abs(r['ml_pred']-r['actual']) for r in rows if r['ml_pred'] is not None]):.2f}; "
  f"mean |ML predicted margin| {mean([abs(r['ml_pred']) for r in rows if r['ml_pred'] is not None]):.1f} vs mean |actual| {mean([abs(r['actual']) for r in rows]):.1f}")

P("\n## Directional bias (fully-rated games)\n")
nn = [r for r in rated if not r["neutral"]]
P(f"- Mean signed error, model: {mean([r['err'] for r in rated]):+.2f}  market: {mean([r['mkt_err'] for r in rated]):+.2f}  (+ = too high on home)")
P(f"- Mean signed edge (model - market, home +): {mean([r['edge'] for r in rated]):+.2f}; leaned home in {sum(r['edge']>0 for r in rated)}/{len(rated)}")
P(f"- Lean home ATS {rec([r for r in rated if r['edge']>0])}; lean away ATS {rec([r for r in rated if r['edge']<0])}")
P(f"- Lean favorite ATS {rec([r for r in rated if r['lean_fav']])}; lean underdog ATS {rec([r for r in rated if r['lean_fav'] is False])}")
P(f"- Home teams covered {sum(r['resid']>0 for r in rated)}/{sum(r['resid']!=0 for r in rated)}")
# implied HFA: market-implied margin minus rating diff (non-neutral)
P(f"- Non-neutral: mean (market-implied margin - SP+ diff) = {mean([-r['mkt']-r['l1'] for r in nn]):+.2f} pts "
  f"(market's implied HFA+adjustments); model used {mean([r['pred']-r['l1'] for r in nn]):+.2f}")
P(f"- Non-neutral: mean (actual margin - SP+ diff) = {mean([r['actual']-r['l1'] for r in nn]):+.2f} (n={len(nn)}, very noisy)")
# edge compression: pred vs market on favorite size
for lo, hi in ((0, 7), (7, 17), (17, 99)):
    grp = [r for r in rated if lo <= abs(r["mkt"]) < hi]
    if grp:
        P(f"- Market |spread| {lo}-{hi}: n={len(grp)}, mean |model margin| {mean([abs(r['pred']) for r in grp]):.1f} vs |market| {mean([abs(r['mkt']) for r in grp]):.1f} vs |actual| {mean([abs(r['actual']) for r in grp]):.1f}; "
          f"ATS {rec(grp)}; model err toward fav {mean([r['err']*(-1 if r['mkt']>0 else 1) for r in grp]):+.1f}")
# optimal shrink of edge toward market: resid ~ w*edge
num = sum(r["edge"]*r["resid"] for r in rated); den = sum(r["edge"]**2 for r in rated)
w = num/den if den else float("nan")
P(f"- Best-fit weight on the model's edge (actual = market + w*edge): w = {w:+.2f} (1 = trust model fully, 0 = market only)")
xs = [r["edge"] for r in rated]; ys = [r["resid"] for r in rated]
mx, my = mean(xs), mean(ys)
corr = sum((x-mx)*(y-my) for x, y in zip(xs, ys)) / math.sqrt(sum((x-mx)**2 for x in xs)*sum((y-my)**2 for y in ys))
P(f"- corr(edge, cover residual) = {corr:+.3f} over n={len(rated)}")
for name in ("hfa", "rest", "travel", "inj"):
    vals = [r[name] for r in rated]
    if any(vals):
        mv = mean(vals)
        sd = math.sqrt(sum((v-mv)**2 for v in vals)/len(vals))
        cr = (sum((v-mv)*(y-my) for v, y in zip(vals, ys)) / math.sqrt(sum((v-mv)**2 for v in vals)*sum((y-my)**2 for y in ys))) if sd else float("nan")
        P(f"  - component {name}: mean {mv:+.2f}, sd {sd:.2f}, corr with cover residual {cr:+.3f}")

P("\n## Injury-adjusted vs not\n")
inj = [r for r in rows if abs(r["inj"]) >= 0.05]; noinj = [r for r in rows if abs(r["inj"]) < 0.05]
cov = {}
for r in rows: cov[r["inj_cov"]] = cov.get(r["inj_cov"], 0) + 1
P(f"- Injury coverage: {cov}")
for lbl, grp in (("with injury adj", inj), ("no injury adj", noinj)):
    P(f"- {lbl}: n={len(grp)}, ATS {rec(grp)}, model MAE {mae(grp,'err'):.2f} vs market {mae(grp,'mkt_err'):.2f}, SU {pct(sum(bool(r['su']) for r in grp), len(grp))}")
if inj:
    it = []
    for r in inj:
        # did the injury term move the model toward or away from the final?
        without = r["pred"] - r["inj"] * r["wind"]
        helped = abs(r["pred"]-r["actual"]) < abs(without-r["actual"])
        flipped = r["edge"] is not None and ((r["edge"] > 0) != ((r["edge"] - r["inj"]*r["wind"]) > 0))
        it.append([f"{r['away']} @ {r['home']}", f"{r['inj']:+.2f}", r["inj_cov"], f"{r['edge']:+.1f}", r["ats"],
                   "yes" if helped else "no", "yes" if flipped else "",
                   "; ".join(f"{d.get('player')} {d.get('position')} {d.get('status')} {d.get('points')}" for d in r["inj_detail"][:3])])
    P(tabulate(it, headers=["Game", "Inj adj", "Coverage", "Edge", "ATS", "Moved toward final?", "Flipped lean?", "Players"], tablefmt="github"))

P("\n## Confidence tier / edge size\n")
for t in ("high", "medium", "low"):
    grp = [r for r in rows if r["conf"] == t]
    if grp:
        P(f"- tier {t}: n={len(grp)}, ATS {rec(grp)}, MAE {mae(grp,'err'):.2f} vs market {mae(grp,'mkt_err'):.2f}, mean |edge| {mean([abs(r['edge']) for r in grp if r['edge'] is not None]):.1f}")
for lo, hi in ((0, 2), (2, 4), (4, 6), (6, 10), (10, 99)):
    grp = [r for r in rated if lo <= abs(r["edge"]) < hi]
    P(f"- rated |edge| {lo}-{hi}: n={len(grp)}, ATS {rec(grp)}, high-tier {rec([r for r in grp if r['conf']=='high'])}")
bad = sorted([r for r in rows if r["ats"] == "L" and abs(r["edge"]) >= 6], key=lambda r: -abs(r["edge"]))
P("\n### Confidently wrong (|edge| >= 6, lost ATS)\n")
P(tabulate([[f"{r['away']} @ {r['home']}", r["conf"] + ("/FCS" if r["src"] == "sp_plus_fcs_proxy" else ""), f"{r['edge']:+.1f}", r["lean"],
             f"{-r['pred']:+.1f}", f"{r['mkt']:+.1f}", f"{r['ap']}-{r['hp']}", f"{r['resid']:+.1f}",
             f"{r['l1']:+.1f}", f"{r['hfa']+r['rest']+r['travel']:+.1f}", f"{r['inj']:+.1f}", r["books"]] for r in bad],
           headers=["Game", "Tier", "Edge", "Lean", "Model", "Market", "Final A-H", "Cover resid", "SP+ diff", "HFA+rest+travel", "Inj", "Books"],
           tablefmt="github"))

text = "\n".join(out)
print(text)
if OUT:
    open(OUT, "w", encoding="utf-8").write(text)
    json.dump(rows, open(OUT.replace(".md", ".json"), "w"), default=str, indent=1)
