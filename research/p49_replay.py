"""P49 QB-only rule replay v2 (read-only). Per game: report as of kickoff, list as first seen
pregame, nflverse depth chart as of the week, books-priced QBs from the saved props_lines
snapshots, snap leader = 2026 dropback leader in earlier weeks. Played = nflverse pbp; for
PHI@CHI (no pbp yet) only Keenum is confirmed (scoring plays), the rest unknown."""
import json, os, re, sys
from collections import defaultdict
sys.path.insert(0, r"C:\Users\alexr\OneDrive\Desktop\Football Predictor")
import pandas as pd
import nfl_data_py as nfl
from src import config, db, features, simulate_nfl
from src.box_score import passer_weights
from src.features import apply_inactives, latest_injury_report, parse_dt, qb_context, qb_availability_loss
from src.ingest_injuries import player_key
from src.predict_ml import load_model

ROOT = r"C:\Users\alexr\OneDrive\Desktop\Football Predictor"
HERE = os.path.dirname(os.path.abspath(__file__))
s = db.get_store()
games = {g["game_id"]: g for g in s.select("games", {"sport": "nfl"}) if g.get("season") == 2026}
kick = {gid: parse_dt(g["kickoff_time"]) for gid, g in games.items()}
pre = [{**r, "pulled_at": games[r["game_id"]]["kickoff_time"]} for r in db.select_merged(s, "inactives", {"season": 2026})
       if r["week"] in (2, 3) and parse_dt(r["first_seen_at"]) < kick[r["game_id"]]]
inj_all = s.select("injuries", {"sport": "nfl", "season": 2026})
preds = defaultdict(dict)
for p in s.select("predictions", {"sport": "nfl"}):
    if p["game_id"] in games:
        preds[p["game_id"]][p["model_version"]] = p
sims = {x["game_id"]: x for x in s.select("game_simulations", {}) if x["game_id"] in games}

pbp = nfl.import_pbp_data([2026], columns=["game_id", "week", "posteam", "passer_player_name",
                                           "rusher_player_name", "qb_dropback"], downcast=True, cache=False)


def abbr(name):
    n = re.sub(r"\b(Jr|Sr|II|III|IV)\.?$", "", str(name).strip()).strip()
    parts = re.sub(r"[^A-Za-z .'-]", "", n).split()
    return (parts[0][0] + "." + parts[-1]).lower().replace("'", "") if len(parts) >= 2 else n.lower()


touch = defaultdict(int)
for col in ("passer_player_name", "rusher_player_name"):
    for (gid, team, n), c in pbp.dropna(subset=[col]).groupby(["game_id", "posteam", col]).size().items():
        touch[(gid, team, str(n).lower().replace("'", ""))] += c
pbp_games = set(pbp["game_id"].unique())


def played(gid, team, name):
    if gid in pbp_games:
        return "Y" if touch.get((gid, team, abbr(name)), 0) else "n"
    if gid == "2026_03_PHI_CHI" and name == "Case Keenum":
        return "Y"
    return "?"


drops = pbp[pbp["qb_dropback"] == 1].dropna(subset=["passer_player_name"])
DC = nfl.import_depth_charts([2026])


def depth_asof(week):
    k = min(kick[g] for g in games if games[g].get("week") == week)
    d = DC[(DC["pos_abb"] == "QB") & DC["gsis_id"].notna()].copy()
    d["dtp"] = pd.to_datetime(d["dt"], utc=True)
    d = d[d["dtp"] < k]
    d = d[d["dtp"] == d.groupby("team")["dtp"].transform("max")].sort_values("pos_rank").drop_duplicates(["team", "gsis_id"])
    return {tm: list(g["player_name"]) for tm, g in d.groupby("team")}


def leaders_asof(week, depth):
    out = {}
    for team, g in drops[drops["week"] < week].groupby("posteam"):
        lead = g.groupby("passer_player_name").size().idxmax().lower().replace("'", "")
        full = [n for t_ in depth for n in depth[t_] if abbr(n) == lead]
        out[team] = full[0] if full else lead
    return out


def snap(path):
    return json.load(open(os.path.join(ROOT, "data", "snapshots", path, "props_lines.json"), encoding="utf-8"))


L = {2: snap("pre-friday_2026-09-18"), 3: snap("pre-sunday_2026-09-27")}
L[3]["games"]["2026_03_PHI_CHI"] = snap("wk3-props_2026-09-28")["games"]["2026_03_PHI_CHI"]
QB = {}
for w in (2, 3):
    dep = depth_asof(w)
    QB[w] = qb_context(s, lines=L[w], depth=dep)
    QB[w]["leaders"] = leaders_asof(w, dep)

ctx = features.FeatureContext(s, "nfl")
model, meta = load_model("nfl")
inputs = simulate_nfl.load_inputs(2026)
rows_out, effects, qb4 = [], [], []
for gid in sorted({r["game_id"] for r in pre}):
    g = games[gid]
    w = g["week"]
    h_, a_ = g["home_team"], g["away_team"]
    report = latest_injury_report([r for r in inj_all if r.get("week") == w and parse_dt(r.get("pulled_at")) < kick[gid]])
    lists = [r for r in pre if r["game_id"] == gid]
    config.INACTIVES_QB_HOLD = False
    old = apply_inactives(report, lists)
    config.INACTIVES_QB_HOLD = True
    holds = []
    new = apply_inactives(report, lists, qb=QB[w], holds=holds)
    hd = {player_key(x["team"], x["player"]): x for x in holds}
    rep = {player_key(r["team"], r["player"]): r for r in report}
    for r in (r for r in lists if r.get("position") == "QB"):
        k = player_key(r["team"], r["player"])
        x = hd.get(k)
        lead = QB[w]["leaders"].get(r["team"], "")
        rows_out.append(dict(
            w=w, gid=gid, team=r["team"], player=r["player"], status=(rep.get(k) or {}).get("status"),
            played=played(gid, r["team"], r["player"]), decision=x["decision"] if x else "apply",
            reason=x["reason"] if x else "", priced=r["player"] in QB[w]["priced"].get(gid, set()),
            leader=lead == r["player"] or abbr(lead) == abbr(r["player"])))

    def inj(rows):
        ctx.injuries = rows
        hi, _, hb = ctx.injury_adjustment(h_)
        ai, _, ab = ctx.injury_adjustment(a_)
        ql = (qb_availability_loss([i for i in rows if i.get("team") == a_])
              - qb_availability_loss([i for i in rows if i.get("team") == h_]))
        br = {(h_, b["player"]): b["points"] for b in hb}
        br.update({(a_, b["player"]): b["points"] for b in ab})
        return hi - ai, ql, br

    (io, qo, bo), (in_, qn, bn) = inj(old), inj(new)
    dml = None
    ml = preds[gid].get("ml-v1")
    if ml and (ml.get("components") or {}).get("features"):
        f0 = dict(ml["components"]["features"])
        f1 = {**f0, "injury_diff": f0["injury_diff"] + in_ - io, "qb_loss_diff": f0["qb_loss_diff"] + qn - qo}
        X = pd.DataFrame([f0, f1])[meta["features"]].apply(pd.to_numeric, errors="coerce").astype(float)
        p0, p1 = model.predict(X)
        dml = float(p1 - p0)
    changed = {k: (bo.get(k, 0.0), bn.get(k, 0.0)) for k in set(bo) | set(bn) if abs(bo.get(k, 0.0) - bn.get(k, 0.0)) > 1e-9}
    effects.append((gid, in_ - io, dml, changed))
    for side in ("home", "away"):
        team = g[side + "_team"]
        opp = a_ if side == "home" else h_
        squad, _, _ = simulate_nfl.team_shares(inputs.roles, team, new)
        wts = passer_weights(squad)
        after = squad.at[int(wts.argmax()), "player"] if len(wts) else None
        sim = sims.get(gid)
        ps = [(p["passing"]["att"]["mean"], p["player"])
              for p in ((sim or {}).get("box_score") or {}).get(side, {}).get("players", []) if p.get("passing")]
        before = max(ps)[1] if ps else None
        oppq = {player_key(team, q) for q in QB[w]["depth"].get(opp, [])}
        pr = sorted(n for n in QB[w]["priced"].get(gid, set()) if player_key(team, n) not in oppq)
        qb4.append((w, gid, team, before, after, pr))

print("ALL FLAGGED QBs (week, game, team, player, report status, played, decision, P=priced L=snap leader, reason)")
for r in rows_out:
    print(f"wk{r['w']} {r['gid']:<16}{r['team']:<4}{r['player']:<24}{str(r['status']):<13}{r['played']:<2}"
          f"{r['decision']:<11}{'P' if r['priced'] else '-'}{'L' if r['leader'] else '-'}  {r['reason']}")
json.dump(rows_out, open(os.path.join(HERE, "p49_rows.json"), "w"))
print("\nC1 played & flagged:", [(r["player"], r["decision"]) for r in rows_out if r["played"] == "Y"])
print("C2 held, didn't play, priced or snap leader:",
      [(r["w"], r["player"], r["priced"], r["leader"]) for r in rows_out
       if r["played"] == "n" and r["decision"] == "hold" and (r["priced"] or r["leader"])])
print("C2 held, didn't play:", sum(1 for r in rows_out if r["played"] == "n" and r["decision"] == "hold"),
      "| unknown (MNF):", [(r["player"], r["decision"]) for r in rows_out if r["played"] == "?"])
ruled = [r for r in rows_out if (r["status"] or "") in features.QB_RULED_STATUSES]
print("C5 ruled (out/ir/doubtful/questionable) applied:", sum(1 for r in ruled if r["decision"] == "apply"), "/", len(ruled))
print("Unresolved:", [(r["w"], r["gid"], r["player"], r["played"], r["reason"]) for r in rows_out if r["decision"] == "unresolved"])
print("\nC3 SERVED-NUMBER EFFECT (home margin change): baseline / ML | charges changed (team player: old -> new)")
for gid, b, m, ch in effects:
    if abs(b) > 1e-9 or (m and abs(m) > 1e-9):
        mm = "" if m is None else f"{m:+6.2f}"
        print(f"  {gid:<18}{b:+6.2f} {mm:>7} | " + "; ".join(f"{t} {p}: {o:.2f}->{n:.2f}" for (t, p), (o, n) in sorted(ch.items())))
print("\nC4 SIM QB1 vs BOOKS (after rule; current roles)")
for w, gid, team, b, a, pr in qb4:
    if (pr and a not in pr) or b != a:
        print(f"  wk{w} {gid:<18}{team:<4} served {b} -> after {a} | priced {pr} {'OK' if (not pr or a in pr) else 'MISMATCH'}")
print(f"  teams {len(qb4)}; mismatches after {sum(1 for x in qb4 if x[5] and x[4] not in x[5])}; "
      f"served mismatches {sum(1 for x in qb4 if x[5] and x[3] not in x[5])}")
s.close()
