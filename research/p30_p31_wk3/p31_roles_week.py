"""P31 re-grade, part A: the roles vector at a point in time, trim off vs on,
against real targets in the week's games kicked off after the cutoff.
Same method as the 9/21 flip evaluation (production player_roles and
_participation_trim; pbp, snaps and depth chart cut at the cutoff).
Usage: python p31_roles_week.py WEEK CUTOFF_ISO OUT.parquet   (read-only)"""
import os, sys
os.environ["USAGE_PARTICIPATION_TRIM"] = "1"
sys.path.insert(0, r"C:\Users\alexr\OneDrive\Desktop\Football Predictor")
import pandas as pd, nfl_data_py as nfl
from src import sim_data, simulate_nfl

WEEK, CUTOFF, OUT = int(sys.argv[1]), pd.Timestamp(sys.argv[2]), sys.argv[3]
SKILL = ["WR", "TE", "RB", "FB"]
sch = nfl.import_schedules([2026])
sch["ko"] = pd.to_datetime(sch["gameday"] + " " + sch["gametime"]).dt.tz_localize("America/New_York").dt.tz_convert("UTC")
before = set(sch.loc[sch["ko"] < CUTOFF, "game_id"])
evalg = set(sch.loc[(sch["week"] == WEEK) & (sch["ko"] >= CUTOFF), "game_id"])

pbp_all = sim_data.load_pbp((2025, 2026))
pbp = pbp_all[(pbp_all["season"] == 2025) | pbp_all["game_id"].isin(before)]
_snaps = nfl.import_snap_counts
nfl.import_snap_counts = lambda yrs: (lambda s: s[(s["season"] < 2026) | s["game_id"].isin(before)])(_snaps(yrs))
_depth = nfl.import_depth_charts
nfl.import_depth_charts = lambda yrs: (lambda d: d[pd.to_datetime(d["dt"], utc=True) < CUTOFF])(_depth(yrs))
roles, as_of = sim_data.player_roles(2026, pbp)
roles = roles.reset_index(drop=True)
print(f"week {WEEK} cutoff {CUTOFF} depth as of {as_of}; eval games {len(evalg)}; pbp has {len(evalg & set(pbp_all['game_id']))}")

rows = []
for team, sq in roles.groupby("team"):
    sq = sq.sort_values(["position", "rank"]).reset_index(drop=True)
    base = sq[["tgt_all"]].to_numpy(float)
    on = simulate_nfl._participation_trim(sq, base)
    s = sq[["team", "player_id", "player", "position", "rank"]].copy()
    s["w_off"], s["w_on"] = base[:, 0], on[:, 0]
    rows.append(s[s["position"].isin(SKILL)])
v = pd.concat(rows)
tgt = pbp_all[pbp_all["game_id"].isin(evalg) & (pbp_all["pass_attempt"] == 1)
              & (pbp_all["sack"] != 1) & pbp_all["receiver_player_id"].notna()]
act = tgt.groupby(["posteam", "receiver_player_id"]).size().rename("act").reset_index()
team_act = tgt.groupby("posteam").size().rename("team_act")
v = v[v["team"].isin(team_act.index)]
v = v.merge(team_act, left_on="team", right_index=True)
v = v.merge(act, left_on=["team", "player_id"], right_on=["posteam", "receiver_player_id"], how="left").fillna({"act": 0})
v["week"] = WEEK
v.drop(columns=["posteam", "receiver_player_id"]).to_parquet(OUT)
print(f"teams {v['team'].nunique()}, pool rows {len(v)}, real targets {int(team_act.sum())}, in pool {int(v['act'].sum())}")
