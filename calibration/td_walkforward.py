import sys, math, random, pandas as pd
df = pd.read_pickle(sys.argv[1])
lg = lambda p: math.log(p / (1 - p)); sg = lambda x: 1 / (1 + math.exp(-x))
ll = lambda p, y: -(y * math.log(max(p, 1e-6)) + (1 - y) * math.log(max(1 - p, 1e-6)))
GRID = [i / 100 for i in range(-60, 61, 2)]
test = []
for W in (4, 5, 6):
    tr, te = df[df.week < W], df[df.week == W]
    shift = {}
    for pos in ("QB", "RB", "WR", "TE"):
        t = tr[tr.pos == pos]
        shift[pos] = min(GRID, key=lambda s: sum(ll(sg(lg(p) + s), y) for p, y in zip(t.p, t.y))) if len(t) else 0.0
    print(W, shift)
    for r in te.itertuples():
        q = sg(lg(r.p) + shift.get(r.pos, 0.0))
        test.append((r.game_id, r.pos, ll(r.p, r.y), ll(q, r.y)))
T = pd.DataFrame(test, columns=["g", "pos", "raw", "cal"])
d = (T.cal - T.raw).mean()
games = T.g.unique().tolist(); by = {g: T[T.g == g] for g in games}; rng = random.Random(5); bs = []
for _ in range(5000):
    s = pd.concat([by[rng.choice(games)] for _ in games]); bs.append((s.cal - s.raw).mean())
bs.sort()
print(f"test rows {len(T)} games {len(games)}: log loss raw {T.raw.mean():.4f} cal {T.cal.mean():.4f} diff {d:+.4f} CI [{bs[125]:+.4f}, {bs[4875]:+.4f}]")
print(T.groupby("pos")[["raw", "cal"]].mean().round(4).to_string())
