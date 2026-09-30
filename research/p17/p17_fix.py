import pathlib

p = pathlib.Path(r"C:\Users\alexr\AppData\Local\Temp\claude\C--Users-alexr-OneDrive-Desktop-Football-Predictor\3037449c-15fa-4700-94ae-cf9ae2541ecf\scratchpad\p17_walkforward.py")
s = p.read_text(encoding="utf-8")
old_start = s.index("def predict(")
old_end = s.index("VARIANTS = [")
new_predict = '''CAT_PRIOR_M = 10.0   # pseudo-targets of the position's category mix, for players with thin history


def predict(week_df, lg, pp, pl, ymean, k, prior, catmix, posmix):
    """Expected yards and receptions per (game, team, pid) before scaling to team totals.

    As the engine does it: each player's targets are split across categories by his PRE-WEEK category shares
    (not that week's actual split, which would leak the outcome), then each category's plays are credited.
    """
    out = []
    for (gid, team), g in week_df.groupby(["game_id", "posteam"]):
        tg = g.groupby("pid").agg(n=("pid", "size"), pos=("pos", "first"))
        q = []
        for pid, x in tg.iterrows():
            own = catmix.loc[pid].to_numpy(float) if pid in catmix.index else np.zeros(3)
            pm = posmix.loc[x["pos"]].to_numpy(float) if x["pos"] in posmix.index else np.full(3, 1 / 3)
            q.append((own + CAT_PRIOR_M * pm) / (own.sum() + CAT_PRIOR_M))
        q = np.array(q) * tg["n"].to_numpy(float)[:, None]          # expected targets by category
        yds = np.zeros(len(tg)); rec = np.zeros(len(tg))
        for cat in range(3):
            rowt = q[:, cat]
            n_tot = rowt.sum()
            if n_tot <= 0:
                continue
            share = rowt / n_tot
            mix = lg.loc[cat].to_numpy(float) if cat in lg.index else np.full(NB, 1 / NB)
            yb = np.array([0.0] + [ymean.get((cat, b), 0.0) for b in range(1, NB)])
            if k is None:
                W = share[:, None] * mix[None, :]
            else:
                P = []
                for pid, x in tg.iterrows():
                    pri = (pp.loc[(x["pos"], cat)].to_numpy(float) if prior == "pos" and (x["pos"], cat) in pp.index else mix)
                    own = pl.loc[(pid, cat)].to_numpy(float) if (pid, cat) in pl.index else np.zeros(NB)
                    P.append((own + k * pri) / (own.sum() + k))
                W = ipf(share[:, None] * np.array(P), share, mix)
            yds += (W * yb[None, :]).sum(1) * n_tot
            rec += W[:, 1:].sum(1) * n_tot
        for j, pid in enumerate(tg.index):
            out.append((gid, team, pid, float(yds[j]), float(rec[j])))
    return pd.DataFrame(out, columns=["game_id", "team", "pid", "yds_raw", "rec_raw"])


'''
s = s[:old_start] + new_predict + s[old_end:]
s = s.replace('''    own_all = hist.groupby("pid").agg(ht=("pid", "size"), hy=("yds", "sum"))''',
'''    own_all = hist.groupby("pid").agg(ht=("pid", "size"), hy=("yds", "sum"))
    catmix = hist.groupby(["pid", "cat"]).size().unstack(fill_value=0).reindex(columns=range(3), fill_value=0)
    posmix = hist.groupby(["pos", "cat"]).size().unstack(fill_value=0).reindex(columns=range(3), fill_value=0)
    posmix = posmix.div(posmix.sum(1), axis=0)''')
s = s.replace("pr = predict(wk, *cache[w24], k, prior)", "pr = predict(wk, *cache[w24], k, prior, catmix, posmix)")
s = s.replace('df.to_pickle(OUT / "p17_wf.pkl")', 'df.to_pickle(OUT / "p17_wf2.pkl")')
p.write_text(s, encoding="utf-8")
q = pathlib.Path(str(p).replace("p17_walkforward.py", "p17_score.py"))
q.write_text(q.read_text(encoding="utf-8").replace('"p17_wf.pkl"', '"p17_wf2.pkl"'), encoding="utf-8")
print("ok")
