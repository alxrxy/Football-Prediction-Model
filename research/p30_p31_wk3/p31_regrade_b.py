"""P31 re-grade, part B: props raw P(over) vs market vs outcome. Week 3 is the
trim-on arm only (the stored pregame sims, re-priced against the saved lines
with props.rank; read-only). The 9/20 week-2 arms were not kept."""
import json, sys
sys.path.insert(0, r"C:\Users\alexr\OneDrive\Desktop\Football Predictor")
from datetime import datetime, timezone
from statistics import mean
import numpy as np, pandas as pd, nfl_data_py as nfl
from src import props, sim_data
from src.ingest_injuries import player_key

pbp = sim_data.load_pbp((2026,))
def box(week, gids):
    wk = pbp[pbp["game_id"].isin(gids) & (pbp["two_point_attempt"] != 1)]
    cp = wk[(wk["complete_pass"] == 1) & wk["receiver_player_id"].notna()]
    ru = wk[(wk["rush_attempt"] == 1) & wk["rusher_player_id"].notna()]
    st = {"player_receptions": cp.groupby(["game_id", "receiver_player_id"]).size(),
          "player_reception_yds": cp.groupby(["game_id", "receiver_player_id"])["yards_gained"].sum(),
          "player_rush_yds": ru.groupby(["game_id", "rusher_player_id"])["yards_gained"].sum(),
          "player_pass_yds": cp.groupby(["game_id", "passer_player_id"])["yards_gained"].sum()}
    ros = nfl.import_weekly_rosters([2026]); ros = ros[ros["week"] == week]
    name, status = {}, {}
    for t, pn, fn, ln, pid, s in zip(ros["team"], ros["player_name"], ros["football_name"], ros["last_name"], ros["player_id"], ros["status"]):
        for nm in {pn, f"{fn} {ln}"}:
            if isinstance(nm, str):
                name[player_key(t, nm)] = pid; status[pid] = s
    return st, name, status

def grade(rows, week):
    st, name, status = box(week, {r["game_id"] for r in rows})
    out, void = [], 0
    for r in rows:
        pid = name.get(player_key(r["team"], r["player"]))
        if pid is None or status.get(pid) not in ("ACT",):
            void += 1; continue
        x = float(st[r["market"]].get((r["game_id"], pid), 0.0))
        out.append({**r, "y": 1.0 if x > r["line"] else 0.0, "week": week})
    return pd.DataFrame(out), void

# week 3: re-price every line against the stored pregame sims
lines = json.load(open(r"C:\Users\alexr\OneDrive\Desktop\Football Predictor\data\snapshots\wk3-props_2026-09-28\props_lines.json"))
res = props.rank(lines, props._sims(), now=datetime(2026, 9, 24, tzinfo=timezone.utc))
w3 = []
for r in res["ranked"] + res["held_out"]:
    ov = r["pick"] == "over"
    w3.append({"game_id": r["game_id"], "player": r["player"], "team": r["team"], "market": r["market"],
               "position": r["position"], "line": r["line"],
               "on": r["p_model_raw"] if ov else 1 - r["p_model_raw"],
               "mkt": r["p_market"] if ov else 1 - r["p_market"]})
g3, v3 = grade(w3, 3)
print(f"week 3 priced props {len(w3)}, graded {len(g3)}, void (not ACT / unmatched) {v3}")

pos = lambda p: str(p).rstrip("0123456789")
G = [("all receiving", lambda d: d["market"].isin(["player_receptions", "player_reception_yds"])),
     ("receptions", lambda d: d["market"] == "player_receptions"),
     ("rec yds", lambda d: d["market"] == "player_reception_yds"),
     ("RB rush yds", lambda d: (d["market"] == "player_rush_yds") & (d["position"].map(pos) == "RB")),
     ("QB rush yds", lambda d: (d["market"] == "player_rush_yds") & (d["position"].map(pos) == "QB")),
     ("pass yds", lambda d: d["market"] == "player_pass_yds")]
def clus(d, a, b, B=4000):
    diff = (d[a] - d["y"]) ** 2 - (d[b] - d["y"]) ** 2
    gi = d["week"].astype(str) + d["game_id"]; ids = gi.unique(); by = {x: diff[gi == x].to_numpy() for x in ids}
    rng = np.random.default_rng(0)
    bs = [np.concatenate([by[x] for x in rng.choice(ids, len(ids))]).mean() for _ in range(B)]
    return diff.mean(), np.percentile(bs, 2.5), np.percentile(bs, 97.5)
WRONGQB = {"2026_03_SEA_WAS", "2026_03_MIN_TB", "2026_03_PHI_CHI"}
for lab, d in (("week 3", g3), ("week 3 excl. the 3 wrong-QB sims (P49/P51)", g3[~g3["game_id"].isin(WRONGQB)])):
    print(f"\n== {lab}")
    print(f"{'group':<14}{'n':>5}{'on':>7}{'mkt':>7}{'actual':>8} | {'Brier on':>9}{'mkt':>8}" + ("   off" if lab == "week 2" else ""))
    for name, f in G:
        s = d[f(d)]
        if not len(s): continue
        b = lambda c: ((s[c] - s["y"]) ** 2).mean()
        extra = f"{b('off'):>8.4f}" if lab == "week 2" else ""
        print(f"{name:<14}{len(s):>5}{s['on'].mean():>7.3f}{s['mkt'].mean():>7.3f}{s['y'].mean():>8.3f} | {b('on'):>9.4f}{b('mkt'):>8.4f}{extra}")
    r = d[G[0][1](d)]
    m, lo, hi = clus(r, "on", "mkt")
    print(f"  receiving Brier on - market {m:+.4f} [{lo:+.4f}, {hi:+.4f}] (game-clustered 95%)")
g3.to_parquet("props_graded.parquet")
