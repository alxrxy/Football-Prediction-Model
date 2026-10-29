import sys, random, pandas as pd
g = pd.read_pickle(sys.argv[1])
F = {"F1": lambda d: ~((d.market == "player_rush_yds") & (d.pick == "over")), "F2": lambda d: d.gap >= 0.10,
     "F3": lambda d: d.pick != "over", "F4": lambda d: ~((d.market == "player_rush_yds") & (d.pick == "over")) & (d.gap >= 0.10)}
roi = lambda d: d.u.sum() / len(d) if len(d) else float("nan")
for name, f in F.items():
    kept_parts, all_parts, sel = [], [], []
    for W in (5, 6, 7):
        tr, te = g[g.week < W], g[g.week == W]
        ok = roi(tr[f(tr)]) - roi(tr) >= 0.05; sel.append((W, ok, round(100 * (roi(tr[f(tr)]) - roi(tr)), 1)))
        all_parts.append(te); kept_parts.append(te[f(te)] if ok else te)
    A, K = pd.concat(all_parts), pd.concat(kept_parts)
    diff = roi(K) - roi(A)
    games = A.game_id.unique().tolist(); rng = random.Random(4); bs = []
    ga = {x: A[A.game_id == x] for x in games}; gk = {x: K[K.game_id == x] for x in games}
    for _ in range(5000):
        s = [rng.choice(games) for _ in games]
        a = pd.concat([ga[x] for x in s]); k = pd.concat([gk[x] for x in s])
        bs.append(roi(k) - roi(a))
    bs.sort()
    nkept = sum(len(kp) for (W, ok, _), kp in zip(sel, kept_parts) if ok)
    print(f"{name}: selected {sel}  test all ROI {100*roi(A):+.1f}% (n {len(A)})  kept ROI {100*roi(K):+.1f}% (n {len(K)}, filtered-week rows {nkept})  diff {100*diff:+.1f}pp  CI [{100*bs[125]:+.1f}, {100*bs[4875]:+.1f}]")
