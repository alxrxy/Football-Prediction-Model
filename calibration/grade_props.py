"""Projected vs actual player lines for one simulated NFL game. Read-only.

    python calibration/grade_props.py 2026_01_DAL_NYG calibration/2026-09-13_nfl_DAL_NYG_props.md

The projection graded is the simulation median (what the dashboard shows).
Error = actual − median, so + means the player beat the projection. % error is
relative to the projection and is left blank when the projection is 0. The
band columns say whether the actual fell in the middle 50% / 80% of
simulations; a calibrated projection lands in them about 50% / 80% of the time.
"""
import json, sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from src import db
from src.export_sims import _espn_day, actual_result, slate_day
from src.features import parse_dt
from src.ingest_injuries import player_key
from tabulate import tabulate

GAME_ID = sys.argv[1] if len(sys.argv) > 1 else "2026_01_DAL_NYG"
OUT = sys.argv[2] if len(sys.argv) > 2 else None

local = db.SqliteStore()
sim = next(r for r in local.select("game_simulations") if r["game_id"] == GAME_ID)
game = next(g for g in local.select("games", {"sport": "nfl"}) if g["game_id"] == GAME_ID)
local.close()
home, away = sim["home_team"], sim["away_team"]
box = json.loads(sim["box_score"])

state = _espn_day(slate_day(game["kickoff_time"]))[(home, away)]
assert state.state == "post", f"{GAME_ID} is not final ({state.detail})"
actual = actual_result(state)

STATS = [("passing", "att", "pass_att", "Pass att"), ("passing", "cmp", "pass_cmp", "Pass cmp"),
         ("passing", "yds", "pass_yds", "Pass yds"), ("passing", "td", "pass_td", "Pass TD"),
         ("passing", "int", "pass_int", "INT"),
         ("rushing", "att", "car", "Rush att"), ("rushing", "yds", "rush_yds", "Rush yds"),
         ("rushing", "td", "rush_td", "Rush TD"),
         ("receiving", "tgt", "tgt", "Targets"), ("receiving", "rec", "rec", "Receptions"),
         ("receiving", "yds", "rec_yds", "Rec yds"), ("receiving", "td", "rec_td", "Rec TD")]
RARE = {"Pass TD", "INT", "Rush TD", "Rec TD"}

rows, unprojected = [], []
for side, team in (("away", away), ("home", home)):
    lines = {player_key(team, u["name"]): u for u in actual["players"][side]}
    seen = set()
    for p in box[side]["players"]:
        k = player_key(team, p["player"]); seen.add(k)
        u = lines.get(k)
        for group, stat, key, label in STATS:
            q = (p.get(group) or {}).get(stat)
            if not q:
                continue
            act = u[key] if u else 0
            proj = q["median"]
            rows.append(dict(team=team, player=p["player"], pos=p["position"], label=label, group=group,
                             proj=proj, mean=q["mean"], p10=q["p10"], p25=q["p25"], p75=q["p75"], p90=q["p90"],
                             act=act, err=act - proj, pct=((act - proj) / proj * 100) if proj else None,
                             in50=q["p25"] <= act <= q["p75"], in80=q["p10"] <= act <= q["p90"],
                             no_stats=u is None))
    for k, u in lines.items():
        if k not in seen and u["car"] + u["tgt"] + u["pass_att"] > 0:
            unprojected.append((team, u))


def f(x, d=1): return "—" if x is None else (f"{x:+.{d}f}" if isinstance(x, float) else f"{x:+d}")


out = []
P = out.append
P(f"## {away} @ {home} — props, projected vs actual\n")
P(f"Final: {away} {actual['away_score']}, {home} {actual['home_score']}. Pregame sim `{sim['sim_version']}`, "
  f"{sim['n_sims']:,} runs, generated {sim['generated_at'][:16]}Z (kickoff {game['kickoff_time'][:16]}Z); "
  f"box-score confidence tagged `{box.get('confidence')}`. Projection = simulation median.\n")
P(f"Score projection: median {away} {sim['median_away_points']:.0f} – {home} {sim['median_home_points']:.0f} "
  f"(mean {sim['mean_away_points']:.1f}–{sim['mean_home_points']:.1f}), {home} win {sim['home_win_prob']:.0%}. "
  f"TDs projected mode {sim['away_td_mode']}/{sim['home_td_mode']}, actual {actual['td']['away']}/{actual['td']['home']}; "
  f"FGs mode {sim['away_fg_mode']}/{sim['home_fg_mode']}, actual {actual['fg']['away']}/{actual['fg']['home']}.\n")

P("### Per player\n")
tbl = []
last = None
for r in rows:
    who = f"{r['player']} ({r['team']} {r['pos']})" + (" — no stats" if r["no_stats"] else "")
    tbl.append([who if who != last else "", r["label"], f"{r['proj']:g}", f"{r['mean']:.1f}",
                f"{r['p25']:g}–{r['p75']:g}", r["act"], f(r["err"]),
                "—" if r["pct"] is None else f"{r['pct']:+.0f}%", "✓" if r["in50"] else "", "✓" if r["in80"] else "✗"])
    last = who
P(tabulate(tbl, headers=["Player", "Stat", "Proj", "Mean", "50% band", "Actual", "Err", "Err %", "In 50%", "In 80%"],
           tablefmt="github"))

P("\n### By stat category\n")
cats = {}
for r in rows:
    cats.setdefault(r["label"], []).append(r)
agg = []
for label, rs in cats.items():
    sized = [r for r in rs if r["proj"] >= 1]
    mape = sum(abs(r["pct"]) for r in sized) / len(sized) if sized else None
    tot_p, tot_a = sum(r["proj"] for r in rs), sum(r["act"] for r in rs)
    agg.append(dict(label=label, n=len(rs), mae=sum(abs(r["err"]) for r in rs) / len(rs),
                    bias=sum(r["err"] for r in rs) / len(rs), mape=mape, tot_p=tot_p, tot_a=tot_a,
                    in50=sum(r["in50"] for r in rs), in80=sum(r["in80"] for r in rs)))
ranked = sorted([a for a in agg if a["label"] not in RARE and a["mape"] is not None], key=lambda a: a["mape"])
P(tabulate([[a["label"], a["n"], f"{a['mae']:.1f}", f"{a['bias']:+.1f}", f"{a['mape']:.0f}%",
             f"{a['tot_p']:g} → {a['tot_a']:g}", f"{a['in50']}/{a['n']}", f"{a['in80']}/{a['n']}"] for a in ranked],
           headers=["Stat (ranked closest → furthest)", "n", "MAE", "Mean err", "Mean |err %|",
                    "Sum proj → actual", "In 50%", "In 80%"], tablefmt="github"))
P("\nMean |err %| is over lines projected at 1 or more, so a 0-median projection doesn't divide by zero.\n")
rare = [a for a in agg if a["label"] in RARE]
P(tabulate([[a["label"], a["n"], f"{sum(r['mean'] for r in cats[a['label']]):.2f}", a["tot_a"],
             f"{a['in80']}/{a['n']}"] for a in rare],
           headers=["Rare-count stat", "n", "Sum of projected means", "Actual total", "In 80%"], tablefmt="github"))

P("\n### Yards error split into volume vs efficiency\n")
split = []
for group, vol, yds, vlabel, ylabel in (("rushing", "Rush att", "Rush yds", "carries", "yds/carry"),
                                        ("receiving", "Targets", "Rec yds", "targets", "yds/target")):
    by_player = {}
    for r in rows:
        if r["label"] in (vol, yds):
            by_player.setdefault((r["team"], r["player"]), {})[r["label"]] = r
    v_err = e_err = 0.0
    for d in by_player.values():
        if vol not in d or yds not in d:
            continue
        pv, pyd = d[vol]["mean"], d[yds]["mean"]
        av, ayd = d[vol]["act"], d[yds]["act"]
        per = pyd / pv if pv else 0.0
        v_err += (av - pv) * per                       # yards from more/fewer touches at projected efficiency
        e_err += ayd - av * per                        # yards from efficiency on the actual touches
    split.append([group, f"{v_err:+.0f}", f"{e_err:+.0f}", f"{v_err + e_err:+.0f}"])
P(tabulate(split, headers=["Group", f"From volume", "From efficiency", "Total vs projected mean"], tablefmt="github"))
P("\nVolume = (actual − projected-mean touches) × projected yards per touch; efficiency = the rest.\n")

P("### Team totals\n")
tt = []
for side, team in (("away", away), ("home", home)):
    ps = actual["players"][side]
    acts = {"pass_att": sum(u["pass_att"] for u in ps), "pass_yds": sum(u["pass_yds"] for u in ps),
            "rush_att": sum(u["car"] for u in ps), "rush_yds": sum(u["rush_yds"] for u in ps)}
    for k, lab in (("pass_att", "Pass att"), ("pass_yds", "Pass yds"), ("rush_att", "Rush att"), ("rush_yds", "Rush yds")):
        q = box[side]["team"][k]
        tt.append([team, lab, f"{q['median']:g}", f"{q['p25']:g}–{q['p75']:g}", acts[k], f"{acts[k] - q['median']:+g}",
                   f"{(acts[k] - q['median']) / q['median'] * 100:+.0f}%"])
P(tabulate(tt, headers=["Team", "Stat", "Proj", "50% band", "Actual", "Err", "Err %"], tablefmt="github"))

if unprojected:
    P("\n### Recorded stats with no projection\n")
    P(tabulate([[f"{u['name']} ({t})", u["car"], u["rush_yds"], u["tgt"], u["rec"], u["rec_yds"], u["td"]]
                for t, u in unprojected],
               headers=["Player", "Car", "Rush yds", "Tgt", "Rec", "Rec yds", "TD"], tablefmt="github"))
scorers = json.loads(sim["td_scorers"]) if sim.get("td_scorers") else {}
if scorers:
    P("\n### Anytime TD scorer projections\n")
    tdl = []
    for side, team in (("away", away), ("home", home)):
        lines = {player_key(team, u["name"]): u for u in actual["players"][side]}
        for sc in scorers.get(side) or []:
            u = lines.get(player_key(team, sc["player"]))
            prob = sc.get("anytime_td", sc.get("prob"))
            tdl.append([f"{sc['player']} ({team})", f"{prob:.0%}" if isinstance(prob, (int, float)) else prob,
                        u["td"] if u else 0])
    P(tabulate(tdl, headers=["Player", "Anytime TD prob", "Actual TDs"], tablefmt="github"))

text = "\n".join(out)
print(text)
if OUT:
    open(OUT, "w", encoding="utf-8").write(text + "\n")
