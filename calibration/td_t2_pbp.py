import sys, math, random, collections; sys.path.insert(0, ".")
import numpy as np, pandas as pd, nfl_data_py as nfl
from src.ingest_injuries import player_key
df = pd.read_pickle(sys.argv[1])
pbp = nfl.import_pbp_data([2026], columns=["game_id", "week", "posteam", "yardline_100", "rush_attempt", "pass_attempt", "rusher_player_name", "receiver_player_name", "rusher_player_id", "receiver_player_id", "season_type", "qb_kneel", "qb_scramble"], downcast=True)
pbp = pbp[(pbp.season_type == "REG")]
gl = pbp[(pbp.rush_attempt == 1) & (pbp.yardline_100 <= 5) & (pbp.qb_kneel != 1)]
tg = pbp[(pbp.pass_attempt == 1) & (pbp.yardline_100 <= 10) & pbp.receiver_player_name.notna()]
rost = nfl.import_weekly_rosters([2026])[["player_id", "player_name", "team"]].drop_duplicates("player_id")
nm = dict(zip(rost.player_id, rost.player_name))
def counts(d, idcol):
    t = d.groupby(["week", "posteam"]).size()
    p = d.groupby(["week", "posteam", idcol]).size()
    return t, p
glt, glp = counts(gl, "rusher_player_id"); tgt, tgp = counts(tg, "receiver_player_id")
def share(tot, per, week, team, key):
    T = tot[(tot.index.get_level_values(0) < week) & (tot.index.get_level_values(1) == team)].sum()
    if not T: return 0.0
    s = per[(per.index.get_level_values(0) < week) & (per.index.get_level_values(1) == team)]
    return float(sum(v for (w, t, pid), v in s.items() if pid in key)) / T
keys = collections.defaultdict(set)
for pid, n in nm.items():
    for t in set(rost[rost.player_id == pid].team): keys[player_key(t, n)].add(pid)
df["gl"] = [share(glt, glp, w, t, keys.get(player_key(t, p), set())) for w, t, p in zip(df.week, df.team, df.player)]
df["t10"] = [share(tgt, tgp, w, t, keys.get(player_key(t, p), set())) for w, t, p in zip(df.week, df.team, df.player)]
print("matched pid share:", np.mean([bool(keys.get(player_key(t, p))) for t, p in zip(df.team, df.player)]).round(3))
lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
ll = lambda p, y: -(y * np.log(np.clip(p, 1e-6, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-6, 1)))
def fit(X, y, it=3000, lr=0.05, l2=1e-3):
    w = np.zeros(X.shape[1])
    for _ in range(it):
        p = 1 / (1 + np.exp(-X @ w)); w -= lr * (X.T @ (p - y) / len(y) + l2 * w)
    return w
X = lambda d: np.c_[np.ones(len(d)), lg(d.p.values), d.gl.values, d.t10.values]
out = []
for W in (4, 5, 6):
    tr, te = df[df.week < W], df[df.week == W]
    w = fit(X(tr), tr.y.values); q = 1 / (1 + np.exp(-X(te) @ w)); print(W, np.round(w, 3))
    out.append(pd.DataFrame({"g": te.game_id, "pos": te.pos, "raw": ll(te.p.values, te.y.values), "cal": ll(q, te.y.values)}))
T = pd.concat(out); d = (T.cal - T.raw).mean()
games = T.g.unique().tolist(); by = {g: T[T.g == g] for g in games}; rng = random.Random(7); bs = []
for _ in range(5000):
    s = pd.concat([by[rng.choice(games)] for _ in games]); bs.append((s.cal - s.raw).mean())
bs.sort(); print(f"test {len(T)} rows / {len(games)} games: raw {T.raw.mean():.4f} T2 {T.cal.mean():.4f} diff {d:+.4f} CI [{bs[125]:+.4f}, {bs[4875]:+.4f}]")
print(T.groupby("pos")[["raw", "cal"]].mean().round(4).to_string())
