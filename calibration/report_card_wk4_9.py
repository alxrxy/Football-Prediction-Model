"""Report card, weeks 4-9 (week-9 copy of report_card.py, 2026-11-15): props record and anytime-TD grading. Read-only; nothing is written to the store.
python calibration/report_card.py stats_player_week_2026.csv out_prefix

Props: per game, the last archived list generated before kickoff (P67 rule), graded as calibration/props_inventory.py
does. Weeks 4-7 and TNF from nflverse; other week-8 games from ESPN final boxes, only once ESPN says completed.
TD: scorers from the archived pregame sims; the market side is rebuilt from stored raw odds, since TD lists are not archived."""
import sys, os, json, glob, re, math, collections; sys.path.insert(0, os.getcwd())
import numpy as np, pandas as pd, nfl_data_py as nfl
from datetime import datetime
from src import db, td_props
from src.ingest_td_props import parse_event
from src.ingest_injuries import player_key
from src.live_sim import game_usage, scoring_so_far

STATS, OUT = sys.argv[1], sys.argv[2]
SEASON, WEEKS, N_BOOT = 2026, (4, 5, 6, 7, 8, 9), 4000
rng = np.random.default_rng(20261101)
ts = lambda x: datetime.fromisoformat(str(x).replace("Z", "+00:00"))
load = lambda f: json.load(open(f, encoding="utf-8"))
COL = {"player_pass_yds": "passing_yards", "player_rush_yds": "rushing_yards", "player_reception_yds": "receiving_yards", "player_receptions": "receptions"}
BOX = {"player_pass_yds": "pass_yds", "player_rush_yds": "rush_yds", "player_reception_yds": "rec_yds", "player_receptions": "rec"}
ESPN_TEAM = {"LAR": "LA", "WSH": "WAS"}

st = pd.read_csv(STATS, low_memory=False); st = st[st.season == SEASON]
snaps = nfl.import_snap_counts([SEASON])
stat = {(int(r.week), player_key(r.team, r.player_display_name)): r for r in st.itertuples()}
played = {(int(r.week), player_key(r.team, r.player)) for r in snaps.itertuples() if (r.offense_snaps or 0) + (r.st_snaps or 0) > 0}


def espn_finals() -> dict:
    """game_id suffix 'AWAY_HOME' -> {player_key: usage}, for completed week-8 games in the ESPN final cache."""
    out = {}
    for f in glob.glob("data/cache/espn_final_*.json"):
        d = load(f)
        if ts(d["fetched_at"]) < ts("2026-11-01T00:00:00+00:00"):
            continue
        s = d["data"]; c = s["header"]["competitions"][0]
        if not c["status"]["type"].get("completed"):
            continue
        tm = {x["homeAway"]: x for x in c["competitors"]}
        ab = {k: ESPN_TEAM.get(v["team"]["abbreviation"], v["team"]["abbreviation"]) for k, v in tm.items()}
        usage = game_usage(s, {tm["home"]["id"]: 0, tm["away"]["id"]: 1})
        out[f"{ab['away']}_{ab['home']}"] = {player_key(ab[side], u["name"]): u for side, i in (("home", 0), ("away", 1)) for u in usage[i].values()}
    return out


FINALS = espn_finals()


def grade_prop(r: dict, wk: int) -> tuple[str, float | None]:
    k = (wk, player_key(r["team"], r["odds_name"]))
    gid = r["game_id"]
    if wk == 8 and gid[8:] != "CAR_GB":
        if gid[8:] not in FINALS:
            return "not_final", None
        u = FINALS[gid[8:]].get(k[1])
        if u is None:
            return "void", None
        v = float(u[BOX[r["market"]]])
    else:
        s = stat.get(k)
        if s is None and k not in played:
            return "void", None
        v = getattr(s, COL[r["market"]]) if s is not None else 0
        v = 0.0 if pd.isna(v) else float(v)
    return ("P" if v == r["line"] else ("W" if (v > r["line"]) == (r["pick"] == "over") else "L")), v


def prop_rows() -> pd.DataFrame:
    files = sorted(glob.glob("data/props_archive/2026_w0*/*.json"))
    docs = [(ts(load(f)["generated_at"]), f) for f in files]
    last = {}
    for gen, f in docs:
        for r in (d := load(f))["props"] + d["more"]:
            if gen < ts(r["kickoff"]) and (r["game_id"] not in last or last[r["game_id"]][0] < gen):
                last[r["game_id"]] = (gen, f)
    out, skipped = [], collections.Counter()
    for gid, (gen, f) in sorted(last.items()):
        d, wk = load(f), int(gid[5:7])
        for part in ("props", "more", "held_out"):
            for r in (x for x in d[part] if x["game_id"] == gid):
                if r.get("line") is None or r.get("pick") is None or r.get("market") not in COL:
                    skipped[(part, r.get("held_reason"))] += 1
                    continue
                res, v = grade_prop(r, wk)
                price = r.get("price")
                u = 0.0 if res not in "WL" or not price else ((price / 100 if price > 0 else 100 / -price) if res == "W" else -1.0)
                out.append({"game_id": gid, "week": wk, "player": r["player"], "market": r["market"], "line": r["line"], "pick": r["pick"], "price": price,
                            "gap": abs(r.get("gap") or 0), "p_model": r.get("p_model"), "p_market": r.get("p_market"), "rank": r.get("rank"),
                            "part": part, "held_reason": r.get("held_reason"), "served_at": gen.isoformat(), "actual": v, "result": res, "u": u,
                            "under_won": None if v is None or v == r["line"] else v < r["line"]})
    print("ungraded fields", dict(skipped))
    return pd.DataFrame(out)


def wilson(w: int, n: int) -> tuple[float, float]:
    if not n:
        return (0.0, 0.0)
    z, p = 1.96, w / n
    c, h = (p + z * z / (2 * n)) / (1 + z * z / n), z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return c - h, c + h


def boot_roi(g: pd.DataFrame) -> tuple[float, float]:
    """95% CI for ROI, resampling whole games: rows in a game share a script."""
    s = g.groupby("game_id").agg(u=("u", "sum"), n=("u", "size"))
    if len(s) < 2:
        return (float("nan"), float("nan"))
    i = rng.integers(0, len(s), (N_BOOT, len(s)))
    return tuple(np.percentile(100 * s.u.values[i].sum(1) / s.n.values[i].sum(1), [2.5, 97.5]))


def trust(n: int, games: int) -> str:
    return "TOO SMALL" if n < 100 or games < 10 else ("thin" if n < 300 else "usable")


def line(label: str, g: pd.DataFrame) -> dict:
    n, w = len(g), int((g.result == "W").sum())
    lo, hi = wilson(w, n); a, b = boot_roi(g) if n else (float("nan"), float("nan"))
    be = np.mean([abs(p) / (abs(p) + 100) if p < 0 else 100 / (p + 100) for p in g.price]) if n else float("nan")
    return {"Split": label, "n": n, "Games": g.game_id.nunique(), "W-L": f"{w}-{n - w}", "Win %": f"{100 * w / n:.1f}" if n else "-",
            "95% CI": f"{100 * lo:.0f}-{100 * hi:.0f}" if n else "-", "Break-even %": f"{100 * be:.1f}" if n else "-", "Market % ": f"{100 * g.p_market.mean():.1f}" if n else "-",
            "Units": f"{g.u.sum():+.1f}", "ROI %": f"{100 * g.u.sum() / n:+.1f}" if n else "-", "ROI 95% CI": f"{a:+.0f} to {b:+.0f}" if n and a == a else "-",
            "Trust": trust(n, g.game_id.nunique())}


def table(rows: list[dict]) -> str:
    h = list(rows[0]); return "\n".join(["| " + " | ".join(h) + " |", "|" + "---|" * len(h)] + ["| " + " | ".join(str(r[k]) for k in h) + " |" for r in rows])


MARKETS = {"player_reception_yds": "Receiving yds", "player_receptions": "Receptions", "player_rush_yds": "Rush yds", "player_pass_yds": "Pass yds"}
GAPS = [(0, .05), (.05, .10), (.10, .15), (.15, .20), (.20, .25), (.25, 9)]


def splits(g: pd.DataFrame) -> list[dict]:
    rows = [line("ALL", g)]
    rows += [line(MARKETS[m], g[g.market == m]) for m in MARKETS if (g.market == m).any()]
    rows += [line(f"{MARKETS[m]} {p}", g[(g.market == m) & (g.pick == p)]) for m in MARKETS for p in ("over", "under") if ((g.market == m) & (g.pick == p)).any()]
    rows += [line(p.capitalize(), g[g.pick == p]) for p in ("over", "under")]
    rows += [line(f"Rank top {k}", g[g["rank"] <= k]) for k in (5, 10, 25)] + [line("Rank 26+", g[g["rank"] > 25])]
    rows += [line(f"Gap {a:.2f}-{b:.2f}" if b < 9 else f"Gap {a:.2f}+", g[(g.gap >= a) & (g.gap < b)]) for a, b in GAPS if ((g.gap >= a) & (g.gap < b)).any()]
    rows += [line(f"Week {w}", g[g.week == w]) for w in WEEKS if (g.week == w).any()]
    return rows


def f2_groups(p: pd.DataFrame) -> dict:
    g = p[p.result.isin(["W", "L"]) & p.price.notna()].copy()
    ranked = g[g.part.isin(["props", "more"])]
    return {"served": ranked, "kept": ranked[ranked.gap >= .10], "f2": pd.concat([ranked[ranked.gap < .10], g[g.held_reason == "min_gap"]]),
            "usage": g[g.held_reason == "gap"], "structural": g[g.held_reason == "structural"]}


# --- TD -------------------------------------------------------------------------------------------------------

def td_scorers() -> pd.DataFrame:
    rows = []
    def add(wk, gid, home, away, pg, actual_of):
        for side, team in (("home", home), ("away", away)):
            for p in (pg.get("scorers") or {}).get(side) or []:
                y = actual_of(team, p)
                if y is not None:
                    rows.append(dict(week=wk, game_id=gid, team=team, player=p["player"], pos=p["position"], depth=p.get("depth_rank"), p=p["anytime_td"], n_td=y, y=int(y > 0)))
    for f in sorted(glob.glob("data/sims_archive/2026_w0*.json")):
        d = load(f); wk = int(d["week"])
        for s in d["slates"]:
            for g in s["games"]:
                pg = g.get("pregame") or {}
                if pg and not pg.get("after_kickoff") and g.get("actual"):
                    add(wk, g["game_id"], g["game_id"].split("_")[3], g["game_id"].split("_")[2], pg, lambda t, p: p.get("actual_tds"))
    for s in load("data/sims.json")["slates"]:
        for g in s["games"]:
            pg = g.get("pregame") or {}
            if str(g["game_id"]).startswith("2026_08") and pg and not pg.get("after_kickoff") and g["game_id"][8:] in FINALS:
                box = FINALS[g["game_id"][8:]]
                add(8, g["game_id"], g["game_id"].split("_")[3], g["game_id"].split("_")[2], pg, lambda t, p: (box.get(player_key(t, p["player"])) or {"td": 0})["td"])
    store = db.get_store()
    gid = "2026_08_CAR_GB"; game = store.select("games", {"game_id": gid})[0]
    sim = store.select("game_simulations", {"game_id": gid})[0]; store.close()
    assert ts(sim["generated_at"]) < ts(game["kickoff_time"])
    sc = sim["td_scorers"]
    def tnf(team, p):
        s = stat.get((8, player_key(team, p["player"])))
        return 0 if s is None else int(np.nan_to_num(s.rushing_tds) + np.nan_to_num(s.receiving_tds))
    add(8, gid, "GB", "CAR", {"scorers": sc}, tnf)
    df = pd.DataFrame(rows)
    return df[df.week.isin(WEEKS)].reset_index(drop=True)


def td_market_rows() -> pd.DataFrame:
    """Every priced player in a game with stored pregame raw odds, ranked as td_props.rank would have."""
    pre = {}
    for f in glob.glob("data/sims_archive/2026_w0*.json"):
        for s in (d := load(f))["slates"]:
            for g in s["games"]:
                if (pg := g.get("pregame")) and not pg.get("after_kickoff") and g.get("actual"):
                    pre[g["game_id"]] = (g, pg)
    lines = {}
    def offer(gid, players, pulled, kick):
        if ts(pulled) < ts(kick) and players and (gid not in lines or lines[gid][1] < pulled):
            lines[gid] = (players, pulled)
    for f in glob.glob("data/cache/td_props_2026_0*.json"):
        d = load(f); gid = re.search(r"td_props_(2026_\d\d_\w+?_\w+?)_[0-9a-f]{16}", f).group(1)
        if gid in pre and isinstance(d.get("data"), dict):
            offer(gid, parse_event(d["data"]), d["fetched_at"], pre[gid][0]["kickoff"] if "kickoff" in pre[gid][0] else d["data"]["commence_time"])
    for f in glob.glob("data/snapshots/*/**/td_props_lines.json", recursive=True) + ["data/td_props_lines.json"]:
        d = load(f)
        for gid, g in (d.get("games") or {}).items():
            if gid in pre:
                offer(gid, g.get("players"), g.get("pulled_at") or d["pulled_at"], g["kickoff"])
    print("TD line games by week", collections.Counter(int(g[5:7]) for g in lines))
    out = []
    by_week = collections.defaultdict(dict)
    for gid in lines:
        if int(gid[5:7]) >= 4:
            by_week[int(gid[5:7])][gid] = lines[gid]
    for wk, games in sorted(by_week.items()):
        lg = {"games": {gid: {"home": gid.split("_")[3], "away": gid.split("_")[2], "kickoff": "2026-01-01T00:00:00+00:00", "players": v[0]} for gid, v in games.items()}}
        res = td_props.rank(lg, {gid: pre[gid][1] for gid in games})
        for r in res["started"]:
            k = (wk, player_key(r["team"], r["player"])); s = stat.get(k)
            if s is None and k not in played:
                y = None
            else:
                y = 0 if s is None else int(np.nan_to_num(s.rushing_tds) + np.nan_to_num(s.receiving_tds) > 0)
            hold = abs(r["gap"]) > td_props.TD_MAX_GAP or (r["game_id"], r["odds_name"]) in td_props.PLAYER_HOLDOUTS
            out.append(dict(week=wk, game_id=r["game_id"], team=r["team"], player=r["player"], pos=re.sub(r"\d", "", r["position"]), p=r["p_model"], pm=r["p_market"], gap=r["gap"],
                            yes_price=r["yes_price"], hold=hold, y=y, has_stat=s is not None))
    m = pd.DataFrame(out); m = m[m.y.notna()].copy(); m["y"] = m.y.astype(int); m["rank"] = np.nan
    for wk, g in m.groupby("week"):
        r = g[~g.hold].assign(a=lambda x: x.gap.abs()).sort_values("a", ascending=False)
        m.loc[r.index, "rank"] = range(1, len(r) + 1)
    return m


brier = lambda p, y: float(np.mean((np.asarray(p, float) - np.asarray(y, float)) ** 2))
def logloss(p, y):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6); y = np.asarray(y, float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def diff_ci(df: pd.DataFrame, a: str, b: str, f) -> tuple[float, float, float]:
    """Mean per-row loss of a minus b (negative: a better), with a 95% CI resampling whole games."""
    if f == "b":
        la, lb = (df[a] - df.y) ** 2, (df[b] - df.y) ** 2
    else:
        pa, pb = df[a].clip(1e-6, 1 - 1e-6), df[b].clip(1e-6, 1 - 1e-6)
        la, lb = -(df.y * np.log(pa) + (1 - df.y) * np.log(1 - pa)), -(df.y * np.log(pb) + (1 - df.y) * np.log(1 - pb))
    s = pd.DataFrame({"g": df.game_id, "d": la - lb}).groupby("g").d.agg(["sum", "size"])
    i = rng.integers(0, len(s), (N_BOOT, len(s)))
    x = s["sum"].values[i].sum(1) / s["size"].values[i].sum(1)
    return float((la - lb).mean()), float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))


def naive_rates(t: pd.DataFrame) -> pd.DataFrame:
    """Walk-forward league rate by position (and position + depth): each week uses only earlier archived weeks."""
    hist = []
    for f in sorted(glob.glob("data/sims_archive/2026_w0*.json")):
        d = load(f); wk = int(d["week"])
        if wk >= 4:
            continue
        for s in d["slates"]:
            for g in s["games"]:
                pg = g.get("pregame") or {}
                if pg and not pg.get("after_kickoff"):
                    for side in ("home", "away"):
                        for p in (pg.get("scorers") or {}).get(side) or []:
                            if p.get("actual_tds") is not None:
                                hist.append(dict(week=wk, pos=p["position"], depth=p.get("depth_rank"), y=int(p["actual_tds"] > 0)))
    all_ = pd.concat([pd.DataFrame(hist), t[["week", "pos", "depth", "y"]]])
    t = t.copy(); t["naive_pos"], t["naive_depth"] = np.nan, np.nan
    for w in WEEKS:
        pr = all_[all_.week < w]; a, b = pr.groupby("pos").y.mean(), pr.groupby(["pos", "depth"]).y.mean(); base = pr.y.mean()
        ix = t.week == w
        t.loc[ix, "naive_pos"] = t[ix].pos.map(a).fillna(base)
        t.loc[ix, "naive_depth"] = [b.get((x, d), a.get(x, base)) for x, d in zip(t[ix].pos, t[ix].depth)]
    return t, len(hist)


def pct(x): return f"{100 * x:.1f}"


def units(g: pd.DataFrame) -> np.ndarray:
    return np.where(g.y == 1, np.where(g.yes_price > 0, g.yes_price / 100, 100 / -g.yes_price), -1.0)


def yes_line(label: str, g: pd.DataFrame) -> dict:
    n, w = len(g), int(g.y.sum()); lo, hi = wilson(w, n); u = units(g); a, b = boot_roi(g.assign(u=u))
    be = np.mean([abs(x) / (abs(x) + 100) if x < 0 else 100 / (x + 100) for x in g.yes_price])
    return {"Group": label, "Picks": n, "Games": g.game_id.nunique(), "Scored": w, "Hit %": pct(w / n), "95% CI": f"{100 * lo:.0f}-{100 * hi:.0f}", "Sim %": pct(g.p.mean()), "Market %": pct(g.pm.mean()),
            "Break-even %": pct(be), "Units": f"{u.sum():+.1f}", "ROI %": f"{100 * u.sum() / n:+.1f}", "ROI 95% CI": f"{a:+.0f} to {b:+.0f}" if a == a else "-", "Trust": trust(n, g.game_id.nunique())}


def score_line(label: str, g: pd.DataFrame, cols: dict) -> dict:
    r = {"Group": label, "n": len(g), "Games": g.game_id.nunique(), "Actual %": pct(g.y.mean())}
    for k, c in cols.items():
        r[f"{k} Brier"], r[f"{k} log loss"] = f"{brier(g[c], g.y):.4f}", f"{logloss(g[c], g.y):.4f}"
    return r


def diff_line(label: str, g: pd.DataFrame, a: str, b: str) -> dict:
    x, l, h = diff_ci(g, a, b, "b"); y, l2, h2 = diff_ci(g, a, b, "l")
    return {"Comparison": label, "n": len(g), "Games": g.game_id.nunique(), "Brier diff": f"{x:+.4f}", "95% CI": f"{l:+.4f} to {h:+.4f}", "Log-loss diff": f"{y:+.4f}", "95% CI ": f"{l2:+.4f} to {h2:+.4f}"}


def build(p, t, m, verdicts: dict) -> tuple[str, dict]:
    G = f2_groups(p); o = []; P = o.append; top = {}
    n_void, n_nf = int((p.result == "void").sum()), p[p.result == "not_final"].game_id.nunique()
    wk8p = sorted(g[8:] for g in p[(p.week == 8) & (p.result != "not_final")].game_id.unique())
    P("# Report card: props and anytime TD, weeks 4-8 (2026)\n")
    P(f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} CT. Read-only: no model change, no re-run, no served prediction touched. Script: `calibration/report_card.py`.\n")
    P(verdicts.get("TOP", "")); P("")
    P("## 1. Props\n")
    P("**What is in this record.** Each game is graded from its last archived list before kickoff (P67 rule). Stake is 1 unit flat at the served price. Week 1-3 lists were never archived.\n")
    P(f"- Week 8 games with a list that are final: {', '.join(wk8p)}. **The eight noon games on 11/1 have no archived list, so they are not in the props record.** Week 6 is one game (DAL @ GB).")
    P(f"- {n_void} rows void (player had no snaps or no box line). {n_nf} game(s) with a list were not final and are skipped.")
    P("- Rank is the row's rank in the list it came from. A week with several lists can contribute more than 5 / 10 / 25 rows to a rank band.")
    P("- 'Market %' is the devigged chance of the picked side. If the model added nothing, Win % would sit near it. Break-even is what the served price needs.")
    P("- ROI intervals resample whole games, because rows in one game move together. Win % intervals are Wilson and treat rows as independent, so they are too narrow.")
    P("- **Trust labels:** TOO SMALL = under 100 rows or under 10 games. thin = 100-299 rows. usable = 300+ rows. 'usable' only means the sample is big enough to read, not that the split makes money.\n")
    P("### Kept vs held\n")
    names = [("All served rows (top 25 + more)", "served"), ("KEPT: raw gap of 0.10 or more (F2)", "kept"), ("HELD by F2: gap under 0.10 (weeks 4-7 were served; week 8 was held live)", "f2"),
             ("HELD as likely usage miss (gap past the cap), never served", "usage"), ("HELD as structural, never served", "structural")]
    P(table([line(a, G[k]) for a, k in names if len(G[k])])); P("")
    P("F2 went live 10/29. For weeks 4-7 'kept' is the filter applied after the fact, and F2 was chosen on those same weeks, so only week 8 is out of sample:\n")
    k8 = G["kept"][G["kept"].week == 8]; f8 = G["f2"][G["f2"].week == 8]
    P(table([line("Week 8 kept", k8)] + ([line("Week 8 held by F2", f8)] if len(f8) else []))); P("")
    for w, title in (("kept", "KEPT rows (the list as it stands today)"), ("served", "All served rows"), ("f2", "HELD by F2")):
        P(f"### Splits: {title}\n"); P(table(splits(G[w]))); P("")
    s = G["served"]; uw = s[s.under_won.notna()]; naive_u = (uw.under_won.astype(bool).sum() * 100 / 110 - (~uw.under_won.astype(bool)).sum()) / len(uw)
    k = G["kept"]; ku = k[k.under_won.notna()]; naive_k = (ku.under_won.astype(bool).sum() * 100 / 110 - (~ku.under_won.astype(bool)).sum()) / len(ku)
    P("### Naive baselines for props\n")
    P(table([{"Baseline, same rows": "Bet every row's under at -110", "Served rows": f"{pct(uw.under_won.astype(bool).mean())}% under, ROI {100 * naive_u:+.1f}%", "Kept rows": f"{pct(ku.under_won.astype(bool).mean())}% under, ROI {100 * naive_k:+.1f}%"},
             {"Baseline, same rows": "Our picks at served prices", "Served rows": f"{pct((s.result == 'W').mean())}% win, ROI {100 * s.u.sum() / len(s):+.1f}%", "Kept rows": f"{pct((k.result == 'W').mean())}% win, ROI {100 * k.u.sum() / len(k):+.1f}%"},
             {"Baseline, same rows": "Market's own view of our side", "Served rows": f"{pct(s.p_market.mean())}%", "Kept rows": f"{pct(k.p_market.mean())}%"}])); P("")
    P(verdicts.get("PROPS", "")); P("")
    tm = t.copy(); mk = m.copy()
    tp = mk[(mk["rank"] <= 25) & (mk.gap > 0)]; ay = mk[mk["rank"].notna() & (mk.gap > 0)]
    P("## 2. Anytime TD\n")
    P("**What is in this record.** TD lists have never been archived and the tab was not wired until 10/29, so there is no complete record of what was shown.\n")
    P(f"- **Player-game grading:** the simulation's scorer lists (top 8 per team), {len(tm)} player-games in {tm.game_id.nunique()} games. Week 8 uses the final 11/1 games and TNF; the eight noon sims date from the 10/29 PRELIMINARY run, before the official reports. Players outside those lists are not graded.")
    P(f"- **Market comparison and picks:** rebuilt with `td_props.rank` from stored raw odds and archived sims: {len(mk)} priced players in {mk.game_id.nunique()} games (weeks {', '.join(str(int(w)) for w in sorted(mk.week.unique()))}). No week 5 or week 8 odds were stored for final games. These are reconstructions, not served lists, though week 7 matches its logged result (17 yes leans, 4 scored).")
    P("- A player with snaps but no stat line counts as not scoring; no snaps is void. The week-7 log entry dropped those rows (123 rows, Brier 0.183 vs 0.178). With them it is 134 rows.")
    P("- Market probabilities are estimates: books post Yes only, so they are scaled to the game total. Yes-side ROI uses the best Yes price stored.\n")
    P("### Yes picks vs how often they scored (rebuilt)\n")
    P(table([yes_line("Top-25 yes picks", tp), yes_line("All ranked yes picks", ay)] + [yes_line(f"Top-25 yes, week {w}", tp[tp.week == w]) for w in sorted(tp.week.unique())])); P("")
    P("**As logged at the time:** week 5 BUF @ LA 5-10 plus 2 ungraded no-line rows (5-12 at zero), not in the table above; week 6 DAL @ GB 1-9, +2.00u; week 7 noon 4-13, -2.75u.\n")
    P("### Hit rate by position (all graded player-games)\n")
    r = []
    for pos in ("RB", "WR", "TE", "QB"):
        g = tm[tm.pos == pos]; w = int(g.y.sum()); lo, hi = wilson(w, len(g))
        r.append({"Position": pos, "Player-games": len(g), "Scored": w, "Hit %": pct(w / len(g)), "95% CI": f"{100 * lo:.0f}-{100 * hi:.0f}", "Sim %": pct(g.p.mean()), "Naive %": pct(g.naive_pos.mean()), "Trust": trust(len(g), g.game_id.nunique())})
    P(table(r)); P(""); pos_rows = r
    P("### Calibration by band\n")
    r = []
    for a, b in ((0, .1), (.1, .2), (.2, .3), (.3, .4), (.4, 1.01)):
        g = tm[(tm.p >= a) & (tm.p < b)]; w = int(g.y.sum()); lo, hi = wilson(w, len(g))
        r.append({"Band": f"{int(a * 100)}-{int(b * 100)}%" if b < 1 else "40%+", "Player-games": len(g), "Predicted %": pct(g.p.mean()), "Actual %": pct(w / len(g)), "95% CI": f"{100 * lo:.0f}-{100 * hi:.0f}", "Diff pp": f"{100 * (w / len(g) - g.p.mean()):+.1f}", "Trust": trust(len(g), g.game_id.nunique())})
    P(table(r)); P(""); top = r
    P("### Brier and log loss\n")
    P("Lower is better. A negative diff means the first model is better. Intervals resample whole games.\n")
    cols3 = {"Sim": "p", "Naive pos": "naive_pos", "Naive pos+depth": "naive_depth"}
    P(table([score_line("All graded player-games", tm, cols3)] + [score_line(pos, tm[tm.pos == pos], cols3) for pos in ("RB", "WR", "TE", "QB")])); P("")
    rates = tm.groupby(["week", "pos"]).naive_pos.first(); mk["naive_pos"] = [rates.get((w, x), np.nan) for w, x in zip(mk.week, mk.pos)]; mk["naive_pos"] = mk.naive_pos.fillna(mk.y.mean())
    colsm = {"Sim": "p", "Market": "pm", "Naive pos": "naive_pos"}
    P(table([score_line("Priced players (market rows)", mk, colsm)] + [score_line(f"Week {w}", mk[mk.week == w], colsm) for w in sorted(mk.week.unique())])); P("")
    d = [diff_line("Sim vs naive position rate, all", tm, "p", "naive_pos"), diff_line("Sim vs naive position + depth, all", tm, "p", "naive_depth"), diff_line("Sim vs market, priced players", mk, "p", "pm"), diff_line("Sim vs naive position, priced players", mk, "p", "naive_pos"), diff_line("Market vs naive position, priced players", mk, "pm", "naive_pos")]
    P(table(d)); P("")
    P("### Best and worst 10 picks (rebuilt ranked yes picks)\n")
    a2 = ay.assign(u=units(ay)); cols = ["week", "player", "team", "pos", "p", "pm", "yes_price", "y", "u"]; ren = {"week": "Wk", "player": "Player", "team": "Team", "pos": "Pos", "p": "Sim", "pm": "Market", "yes_price": "Price", "y": "Scored", "u": "Units"}
    fmt = lambda x: table([{ren[c]: (f"{v:.3f}" if c in ("p", "pm") else (f"{v:+.2f}" if c == "u" else (f"{int(v):+d}" if c == "yes_price" else v))) for c, v in q.items()} for q in x[cols].to_dict("records")])
    P("**Best: largest wins.**\n"); P(fmt(a2.sort_values("u", ascending=False).head(10))); P("")
    P("**Worst: biggest sim-over-market gaps that did not score, each -1u.**\n"); P(fmt(a2[a2.y == 0].sort_values("gap", ascending=False).head(10))); P("")
    P(verdicts.get("TD", "")); P("")
    return "\n".join(o), {"G": {k_: line(k_, g) for k_, g in G.items() if len(g)}, "bands": top, "pos": pos_rows, "tp": yes_line("t", tp), "ay": yes_line("a", ay), "diff": d,
                          "tm": score_line("t", tm, cols3), "mk": score_line("m", mk, colsm), "k8": line("k8", k8) if len(k8) else None, "f8": line("f8", f8) if len(f8) else None, "wk8": wk8p,
                          "naive_under": (round(100 * naive_u, 1), round(100 * naive_k, 1)), "kept_splits": [(x["Split"], x["n"], x["Win %"], x["ROI %"], x["ROI 95% CI"], x["Trust"]) for x in splits(G["kept"])]}


def to_html(md: str) -> str:
    import html
    inline = lambda s: re.sub(r"`([^`]+)`", r"<code>\1</code>", re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", html.escape(s, quote=False)))
    out, lines, i = [], md.split("\n"), 0
    while i < len(lines):
        s = lines[i]
        if s.startswith("|"):
            head = [c.strip() for c in s.strip().strip("|").split("|")]; i += 2; body = []
            while i < len(lines) and lines[i].startswith("|"):
                body.append([c.strip() for c in lines[i].strip().strip("|").split("|")]); i += 1
            out.append("<div class=t><table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body) + "</tbody></table></div>")
            continue
        if s.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(lines[i][2:]); i += 1
            out.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ul>")
            continue
        m_ = re.match(r"(#+) (.*)", s)
        out.append(f"<h{len(m_[1])}>{inline(m_[2])}</h{len(m_[1])}>" if m_ else (f"<p>{inline(s)}</p>" if s.strip() else ""))
        i += 1
    css = "body{font:15px/1.5 system-ui,sans-serif;max-width:1120px;margin:2em auto;padding:0 1em;color:#1f2328}h1{font-size:26px}h2{margin-top:2em;border-bottom:1px solid #d0d7de;padding-bottom:.2em}.t{overflow-x:auto}table{border-collapse:collapse;margin:1em 0;font-size:13px;font-variant-numeric:tabular-nums}th,td{border:1px solid #d0d7de;padding:4px 8px;text-align:right;white-space:nowrap}th:first-child,td:first-child{text-align:left}th{background:#f6f8fa}code{background:#f0f2f4;padding:0 3px}"
    return f"<!DOCTYPE html><html lang=en><head><meta charset=utf-8><title>Report card, weeks 4-9 (week-9 copy of report_card.py, 2026-11-15)</title><style>{css}</style></head><body>" + "\n".join(out) + "</body></html>"


def main():
    p = prop_rows()
    print("FINALS", sorted(FINALS)); print("week 8", p[p.week == 8].groupby(["game_id", "result"]).size().to_dict()); print("results", p.result.value_counts().to_dict())
    chk = f2_groups(p)["served"]; print("check wks4-7 served graded", len(chk[chk.week <= 7]), "(log 887)")
    t, nh = naive_rates(td_scorers()); m = td_market_rows()
    w7 = m[(m.week == 7) & m.has_stat]; print("check wk7 stat rows", len(w7), "(log 123) Brier", round(brier(w7.p, w7.y), 3), round(brier(w7.pm, w7.y), 3), "(log .183/.178)")
    print("TD games by week", t.groupby("week").game_id.nunique().to_dict())
    v = json.load(open(sys.argv[3], encoding="utf-8")) if len(sys.argv) > 3 else {}
    txt, nums = build(p, t, m, v)
    open(OUT + ".md", "w", encoding="utf-8").write(txt + "\n"); open(OUT + ".html", "w", encoding="utf-8").write(to_html(txt))
    print(json.dumps(nums, indent=0, default=str))


if __name__ == "__main__":
    main()
