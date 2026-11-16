"""P82 SHADOW VIEW, week 10 2026 (UNVALIDATED; display only; nothing served reads it).

Rules are in calibration-log.md, 2026-11-15 'final board' entry, written before this ran.
Replacement-starter credit from the QB's own 2025-26 record: opponent-adjusted EPA/dropback,
shrunk toward replacement level (k = 250 dropbacks), times league dropbacks per team-game.

    python calibration/p82_shadow_wk10.py            -> data/board/p82_shadow_2026_w10.json + table
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import db  # noqa: E402

K = 250                 # shrinkage prior, dropbacks (not fitted)
REPL_MAX_DB = 300       # replacement pool: QBs with < 300 dropbacks in the window
LOW_CONF_CAREER = 200   # career dropbacks below this: low confidence

# team, expected starter, usual starter (2026 snap leader unless noted), source of the starter
CASES = [
    ("2026_10_MIN_GB", "MIN", "Kirk Cousins", ["Kyler Murray"], "vikings.com 11/13: Cousins starts; Murray inactive"),
    ("2026_10_MIA_IND", "MIA", "Kyle McCord", ["Malik Willis"], "NFL.com: Willis IR, McCord first start"),
    ("2026_10_SEA_LV", "SEA", "Drew Lock", ["Sam Darnold"], "seahawks.com 11/13: Darnold Out, Lock starts"),
    ("2026_10_SEA_LV", "LV", "Fernando Mendoza", ["Kirk Cousins"], "raiders.com 11/14: Mendoza first start; Cousins left for MIN"),
    ("2026_10_LA_ARI", "ARI", "Carson Beck", ["Jacoby Brissett"], "azcardinals.com 11/13: Beck starts; Brissett traded, Minshew hurt"),
    ("2026_10_LAC_BAL", "BAL", "Jacoby Brissett", ["Tyler Huntley", "Lamar Jackson"],
     "baltimoreravens.com 11/14: Brissett debut, Lamar IR (Huntley IR); usual = 2026 snap-weighted Huntley/Lamar"),
]


def ids_by_name() -> dict[str, str]:
    import nfl_data_py as nfl
    d = nfl.import_depth_charts([2025, 2026])
    d = d[d.pos_abb == "QB"].dropna(subset=["gsis_id"])
    return dict(zip(d.player_name, d.gsis_id))


def main() -> None:
    dbk = pd.read_parquet(ROOT / "data/cache/p82_dropbacks_2024_2026.parquet")
    dbk = dbk[(dbk.season >= 2025) & (dbk.season_type == "REG")].copy()
    dbk["qb"] = dbk.passer_player_id.fillna(dbk.rusher_player_id)
    dbk = dbk.dropna(subset=["qb", "epa"])
    # opponent adjustment: defence's season EPA/dropback allowed above league
    lg = dbk.groupby("season").epa.mean()
    dfa = dbk.groupby(["season", "defteam"]).epa.mean() - lg.reindex(
        dbk.groupby(["season", "defteam"]).epa.mean().index.get_level_values(0)).values
    dbk["adj"] = dbk.epa - dfa.reindex(pd.MultiIndex.from_arrays([dbk.season, dbk.defteam])).values
    per = dbk.groupby("qb").agg(n=("adj", "size"), raw=("epa", "mean"), adj=("adj", "mean"),
                                success=("success", "mean"), cpoe=("cpoe", "mean"), sack=("sack", "mean"),
                                name=("passer_player_name", lambda s: s.dropna().mode().iat[0] if s.notna().any() else None))
    pool = dbk[dbk.qb.isin(per.index[per.n < REPL_MAX_DB])]
    repl = float(pool.adj.mean())
    per["shrunk"] = (per.n * per.adj + K * repl) / (per.n + K)
    s26 = dbk[dbk.season == 2026]
    dbpg = len(s26) / s26.groupby(["game_id", "posteam"]).ngroups

    # career dropbacks, 2015-2026 regular season (sim pbp cache + 2026 pull)
    car = []
    for yr in range(2015, 2026):
        p = pd.read_parquet(ROOT / f"data/cache/sim_pbp_{yr}.parquet",
                            columns=["season_type", "qb_dropback", "passer_player_id", "rusher_player_id"])
        p = p[(p.qb_dropback == 1) & (p.season_type == "REG")]
        car.append(p.passer_player_id.fillna(p.rusher_player_id))
    car.append(dbk[dbk.season == 2026].qb)
    career = pd.concat(car).value_counts()

    names = ids_by_name()
    store = db.get_store()
    preds = {r["game_id"]: r for r in store.select("predictions", {"model_version": "baseline-v1"})
             if r["game_id"].startswith("2026_10")}
    snaps = None

    def qb(name):
        gid = names.get(name)
        row = per.loc[gid] if gid in per.index else None
        n = int(row.n) if row is not None else 0
        return {
            "name": name, "gsis_id": gid, "dropbacks_2025_26": n,
            "career_dropbacks_2015_26": int(career.get(gid, 0)),
            "epa_db_raw": None if row is None else round(float(row.raw), 3),
            "epa_db_opp_adj": None if row is None else round(float(row.adj), 3),
            "success_rate": None if row is None else round(float(row.success), 3),
            "cpoe": None if row is None or pd.isna(row.cpoe) else round(float(row.cpoe), 1),
            "sack_rate": None if row is None else round(float(row.sack), 3),
            "epa_db_shrunk": round(float(row.shrunk) if row is not None else repl, 3),
        }

    out = []
    for gid, team, new, usual, src in CASES:
        p = preds.get(gid)
        if not p:
            continue
        comp = json.loads(p["components"]) if isinstance(p["components"], str) else p["components"]
        home = gid.split("_")[3]
        side = "home" if team == home else "away"
        flat = sum(x["points"] for x in comp["layer2"].get(f"{side}_injuries", []) if x["position"] == "QB")
        nq = qb(new)
        uq = [qb(u) for u in usual]
        if len(uq) > 1:   # snap-weighted mix (BAL)
            import nfl_data_py as nfl
            if snaps is None:
                snaps = nfl.import_snap_counts([2026])
            w = [float(snaps[(snaps.team == team) & (snaps.player == u.split(" ", 1)[0][0] + "." + u.split(" ", 1)[1])
                             ].offense_snaps.sum() or snaps[(snaps.team == team) & (snaps.player == u)].offense_snaps.sum())
                 for u in usual]
            usual_shrunk = sum(q["epa_db_shrunk"] * wi for q, wi in zip(uq, w)) / sum(w)
        else:
            usual_shrunk = uq[0]["epa_db_shrunk"]
        vs_usual = (nq["epa_db_shrunk"] - usual_shrunk) * dbpg
        vs_repl = (nq["epa_db_shrunk"] - repl) * dbpg
        sign = 1 if side == "home" else -1
        headline = float(p["model_margin_home"])
        shadow = headline + sign * flat + sign * vs_usual
        out.append({
            "game_id": gid, "team": team, "side": side, "starter_source": src,
            "expected_starter": nq, "usual_starter": uq, "usual_shrunk_epa_db": round(usual_shrunk, 3),
            "flat_qb_charge_in_headline": round(flat, 2),
            "pts_vs_usual": round(vs_usual, 2), "pts_vs_replacement": round(vs_repl, 2),
            "headline_margin_home": round(headline, 2), "shadow_margin_home": round(shadow, 2),
            "difference": round(shadow - headline, 2),
            "low_confidence": nq["career_dropbacks_2015_26"] < LOW_CONF_CAREER,
            "baseline_generated_at": p["generated_at"],
        })
    # combine both teams in one game (SEA @ LV)
    by_game: dict = {}
    for r in out:
        g = by_game.setdefault(r["game_id"], {"game_id": r["game_id"], "teams": [],
                                               "headline_margin_home": r["headline_margin_home"]})
        g["teams"].append(r)
    for g in by_game.values():
        g["shadow_margin_home"] = round(g["headline_margin_home"] + sum(t["difference"] for t in g["teams"]), 2)
        g["difference"] = round(g["shadow_margin_home"] - g["headline_margin_home"], 2)
    res = {"label": "P82 SHADOW, UNVALIDATED: not the headline; gates G1-G6 not run (calibration-log 2026-11-15)",
           "k_dropbacks": K, "replacement_epa_db": round(repl, 3), "replacement_pool": f"QBs < {REPL_MAX_DB} dropbacks, 2025-26",
           "dropbacks_per_team_game_2026": round(dbpg, 1), "games": list(by_game.values())}
    path = ROOT / "data/board/p82_shadow_2026_w10.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    print(f"replacement {repl:+.3f} EPA/db | {dbpg:.1f} db/team-game | k={K}")
    for g in res["games"]:
        for t in g["teams"]:
            n, u = t["expected_starter"], t["usual_starter"]
            print(f"{g['game_id']} {t['team']}: {n['name']} n={n['dropbacks_2025_26']} car={n['career_dropbacks_2015_26']} "
                  f"adj {n['epa_db_opp_adj']} sr {n['success_rate']} cpoe {n['cpoe']} sack {n['sack_rate']} shrunk {n['epa_db_shrunk']}"
                  f" | usual {[(q['name'], q['dropbacks_2025_26'], q['epa_db_shrunk']) for q in u]}"
                  f" | flat {t['flat_qb_charge_in_headline']} vs_usual {t['pts_vs_usual']:+} vs_repl {t['pts_vs_replacement']:+}"
                  f"{' LOW-CONF' if t['low_confidence'] else ''}")
        print(f"   headline {g['headline_margin_home']:+.1f} -> shadow {g['shadow_margin_home']:+.1f} ({g['difference']:+.1f})")


if __name__ == "__main__":
    main()
