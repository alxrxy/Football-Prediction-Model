"""P68 replay (read-only): which hold rule per position group for ESPN's pregame inactive flags.

    python research/p68/p68_replay.py [out.md]

Design and conditions: calibration-log.md, P68 decisions 1-6 (2026-10-07), set before this ran. Nothing is
stored, served or exported; raw roster logging is switched off for the post-game reads (INACTIVES_RAW=0).

Sample: weeks 2-3 + week 4 PIT @ CLE, every flag first seen before kickoff. Two flag sets (decision 6, (1)):
  upper = every flag seen at any pregame read;   lower = the flags on each list's latest stored read.
Truth (decision 6, (2)): played = any snap (nflverse); genuine inactive = no snaps AND did-not-play on the post-game
ESPN roster; no snaps but active post-game = third bucket (neither side).
Candidates (decision 1): R2 = hold unless the final official report gives a game status (out / doubtful /
questionable); R3 = hold if on the team's prior-week list and not ruled out (out / doubtful) this week; R2&R3; D =
team-level: hold every flag on a list identical to the prior week's list. R3 / D need a prior-week list: weeks 3-4.
Cost (decision 2): points = weight x snap share x 6 x the play probability the player has if the flag is held (his
report probability; 1.0 when he is not on the report). A false flag applied costs that; a genuine flag held costs
that. Skill also: usage = his share of team targets + carries in his earlier 2026 games (2025 if none).
"""
from __future__ import annotations

import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ["INACTIVES_RAW"] = "0"
import nfl_data_py as nfl  # noqa: E402
from src import db, ingest_inactives as II  # noqa: E402
from src.features import POSITION_WEIGHTS, DEFAULT_POSITION_WEIGHT, parse_dt  # noqa: E402
from src.ingest_injuries import _practice, play_probability, player_key  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "research" / "p68" / "p68_replay_results.md"
SEASON, WEEKS = 2026, (2, 3, 4)
RNG = np.random.default_rng(68)
N_BOOT = 2000
SCALE = 6.0
lines: list[str] = []


def say(s=""):
    print(s, flush=True)
    lines.append(str(s))


def group(pos):
    p = (pos or "").upper()
    if p == "QB":
        return "QB"
    if p in ("RB", "FB", "WR", "TE"):
        return "skill"
    if p in ("OT", "OG", "G", "T", "C", "OL", "LT"):
        return "OL"
    return "defense/ST"


# --- data -----------------------------------------------------------------------------------------------
st = db.get_store()
games = {g["game_id"]: g for g in st.select("games", {"sport": "nfl"}) if g.get("season") == SEASON}
ko = {gid: parse_dt(g["kickoff_time"]) for gid, g in games.items()}
inact = [r for r in st.select("inactives") if r.get("season") == SEASON and r.get("week") in WEEKS
         and parse_dt(r.get("first_seen_at")) and parse_dt(r["first_seen_at"]) < ko[r["game_id"]]]
latest = {}
for r in inact:
    k = (r["game_id"], r["team"])
    latest[k] = max(latest.get(k, ""), str(r["pulled_at"]))

snaps = nfl.import_snap_counts([SEASON])
snaps = snaps[snaps.week.isin(range(1, 5))]
snap_any = {(int(w), t, player_key(t, p)) for w, t, p, o, d, s in
            zip(snaps.week, snaps.team, snaps.player, snaps.offense_snaps, snaps.defense_snaps, snaps.st_snaps)
            if (o or 0) + (d or 0) + (s or 0) > 0}
inj = nfl.import_injuries([SEASON])
inj = inj[inj.week.isin(WEEKS) & (inj.game_type == "REG")]
report = {}
for w, t, n, s, pr in zip(inj.week, inj.team, inj.full_name, inj.report_status, inj.practice_status):
    s = (s or "").strip().lower() or None
    s = s if s in ("out", "doubtful", "questionable") else None
    report[(int(w), t, player_key(t, n))] = (s, _practice(pr))

# post-game ESPN rosters (did-not-play), one read per week
post = {}
for w in WEEKS:
    rows, log = II.fetch(st, SEASON, w, include_final=True, shares={})
    got = {(x["game"], x.get("team")) for x in log if x.get("team")}
    for x in log:
        if x.get("team"):
            post.setdefault(("teams", w), set()).add(x["team"])
    for r in rows:
        post[(w, r["team"], player_key(r["team"], r["player"]))] = True
say(f"post-game rosters read: " + ", ".join(f"wk{w} {len(post.get(('teams', w), ()))} teams" for w in WEEKS))

# usage share proxy for skill players: (targets + carries) / team, earlier 2026 games, else 2025 (from pbp)
from src import sim_data as sd  # noqa: E402
pbp = sd.load_pbp((SEASON - 1, SEASON))
pbp = pbp[pbp["season_type"] == "REG"] if "season_type" in pbp else pbp
tg = pbp[pbp["receiver_player_id"].notna() & (pbp["play_type"] == "pass")][["season", "week", "posteam", "receiver_player_id"]]
ca = pbp[pbp["rusher_player_id"].notna() & (pbp["play_type"] == "run")][["season", "week", "posteam", "rusher_player_id"]]
touch = pd.concat([tg.rename(columns={"receiver_player_id": "pid"}), ca.rename(columns={"rusher_player_id": "pid"})])
per = touch.groupby(["season", "week", "posteam", "pid"]).size().rename("n").reset_index()
per["share"] = per.n / per.groupby(["season", "week", "posteam"]).n.transform("sum")
ros = nfl.import_seasonal_rosters([SEASON - 1, SEASON])[["player_id", "player_name", "team", "season"]]
name_to_id = {}
for pid, nm, tm in zip(ros.player_id, ros.player_name, ros.team):
    name_to_id.setdefault(player_key(tm, nm), pid)


def usage(team, name, week):
    pid = name_to_id.get(player_key(team, name))
    if pid is None:
        return 0.0
    w = per[per.pid == pid]
    cur = w[(w.season == SEASON) & (w.week < week)]
    src = cur if len(cur) else w[w.season == SEASON - 1]
    return float(src["share"].mean()) if len(src) else 0.0


# --- flag table -----------------------------------------------------------------------------------------
def table(bound):
    rows = [r for r in inact if bound == "upper" or str(r["pulled_at"]) == latest[(r["game_id"], r["team"])]]
    out = []
    for r in rows:
        w, t = int(r["week"]), r["team"]
        k = player_key(t, r["player"])
        played = (w, t, k) in snap_any
        if played:
            truth = "false"
        elif (w, t, k) in post:
            truth = "genuine"
        elif t in post.get(("teams", w), ()):
            truth = "third"
        else:
            truth = "unknown"
        st_, pr = report.get((w, t, k), (None, None))
        on_report = (w, t, k) in report
        pp_held = play_probability(st_, pr) if on_report else 1.0
        weight = POSITION_WEIGHTS.get((r.get("position") or "").upper(), DEFAULT_POSITION_WEIGHT)
        share = r.get("snap_share") or 0.0
        out.append({"week": w, "game_id": r["game_id"], "team": t, "player": r["player"], "key": k,
                    "group": group(r.get("position")), "truth": truth, "status": st_, "on_report": on_report,
                    "pp_held": pp_held, "pts": weight * share * SCALE * pp_held,
                    "use": usage(t, r["player"], w) if group(r.get("position")) == "skill" else 0.0})
    df = pd.DataFrame(out).drop_duplicates(["week", "team", "key"])
    lists = {(w, t): set(g.key) for (w, t), g in df.groupby(["week", "team"])}
    df["prior_list"] = [k in lists.get((w - 1, t), set()) if (w - 1, t) in lists else np.nan
                        for w, t, k in zip(df.week, df.team, df.key)]
    df["has_prior"] = [(w - 1, t) in lists for w, t in zip(df.week, df.team)]
    df["identical"] = [lists.get((w, t)) == lists.get((w - 1, t)) if (w - 1, t) in lists else False
                       for w, t in zip(df.week, df.team)]
    df["R2"] = df.status.isna()
    df["R3"] = (df.prior_list == True) & ~df.status.isin(["out", "doubtful"])  # noqa: E712
    df["R2&R3"] = df.R2 & df.R3
    df["D"] = df.identical
    return df, lists


CANDS = ["R2", "R3", "R2&R3", "D"]
SIMPLER = {"R2": 0, "R3": 0, "R2&R3": 1, "D": 2}


def score(d, cand):
    held = d[d[cand]]
    f, g = held[held.truth == "false"], held[held.truth == "genuine"]
    return {"caught": len(f), "wrong": len(g), "removed": f.pts.sum(), "added": g.pts.sum(),
            "use_removed": f.use.sum(), "use_added": g.use.sum()}


def boot_net(d, a, b, unit="pts"):
    """90% CI of (net benefit of a) - (net benefit of b), resampling games."""
    gids = d.game_id.unique()
    by = {gid: d[d.game_id == gid] for gid in gids}

    def net(x, c):
        h = x[x[c]]
        return h.loc[h.truth == "false", unit].sum() - h.loc[h.truth == "genuine", unit].sum()
    diffs = []
    for _ in range(N_BOOT):
        s = pd.concat([by[g] for g in RNG.choice(gids, len(gids))])
        diffs.append(net(s, a) - net(s, b))
    return np.percentile(diffs, [5, 95])


# --- run ------------------------------------------------------------------------------------------------
results = {}
for bound in ("upper", "lower"):
    d, lists = table(bound)
    say(f"\n## Bound: {bound} ({'every flag seen at any pregame read' if bound == 'upper' else 'flags on the latest stored read'})")
    say(f"flags {len(d)}: " + ", ".join(f"{k} {v}" for k, v in Counter(d.truth).most_common()))
    say("\n| group | flags | false | genuine | third bucket | unknown |")
    say("|---|---|---|---|---|---|")
    for gname in ("QB", "skill", "OL", "defense/ST"):
        x = d[d.group == gname]
        c = Counter(x.truth)
        say(f"| {gname} | {len(x)} | {c['false']} | {c['genuine']} | {c['third']} | {c['unknown']} |")

    # (i) D's false-alarm rate on genuine lists (weeks 3-4: a prior list exists)
    lst = d[d.has_prior].groupby(["week", "team"]).agg(identical=("identical", "first"),
                                                         false=("truth", lambda s: (s == "false").sum()))
    genuine_lists = lst[lst["false"] == 0]
    say(f"\n(i) identical-to-last-week lists: {int(lst.identical.sum())} of {len(lst)} lists with a prior week; "
        f"on genuine lists (no false flag): {int(genuine_lists.identical.sum())} of {len(genuine_lists)} "
        f"= {genuine_lists.identical.mean() if len(genuine_lists) else float('nan'):.1%} false-alarm rate")
    ident = lst[lst.identical]
    for (w, t), r in ident.iterrows():
        say(f"    identical: wk{w} {t} ({len(lists[(w, t)])} flags, {int(r['false'])} false)")

    # (ii) candidates per group, on weeks 3-4 (all four defined); R2 on weeks 2-4 for context
    say("\n(ii) candidates, weeks 3-4 (R3 and D need a prior list). Points / usage removed (false flags held) vs added (genuine held)")
    say("| group | candidate | caught / false | wrong holds / genuine | pts removed | pts added | net pts | use removed | use added | eligible |")
    say("|---|---|---|---|---|---|---|---|---|---|")
    d34 = d[d.has_prior]
    for gname in ("skill", "OL", "defense/ST", "QB"):
        x = d34[d34.group == gname]
        nf, ng = (x.truth == "false").sum(), (x.truth == "genuine").sum()
        for c in CANDS:
            s = score(x, c)
            ok_pts = s["added"] <= s["removed"]
            ok_use = s["use_added"] <= s["use_removed"]
            elig = ("yes" if ok_pts and (gname != "skill" or ok_use) else
                    "SPLIT (to user)" if gname == "skill" and ok_pts != ok_use else "no")
            if s["caught"] == 0 and s["wrong"] == 0:
                elig = "holds nothing"
            results[(bound, gname, c)] = {**s, "eligible": elig, "nf": nf, "ng": ng}
            say(f"| {gname} | {c} | {s['caught']}/{nf} | {s['wrong']}/{ng} | {s['removed']:.2f} | {s['added']:.2f} | "
                f"{s['removed'] - s['added']:+.2f} | {s['use_removed']:.2f} | {s['use_added']:.2f} | {elig} |")
    x = d[d.group != "QB"]
    s = score(x, "R2")
    say(f"context, R2 on weeks 2-4 (non-QB): caught {s['caught']}/{(x.truth == 'false').sum()}, wrong holds "
        f"{s['wrong']}/{(x.truth == 'genuine').sum()}, net pts {s['removed'] - s['added']:+.2f}")
    results[(bound, "frame")] = d

# selection: per group, per bound, then must agree across bounds
say("\n## Selection (decision 1 rule; must win under both bounds; within noise the simpler rule wins)")
say("Noise: 90% game-bootstrap CI of the difference in net points between the top candidate and each simpler eligible one.")
picks = {}
for gname in ("skill", "OL", "defense/ST"):
    per = {}
    for bound in ("upper", "lower"):
        d = results[(bound, "frame")]
        d34 = d[(d.has_prior) & (d.group == gname)]
        elig = [c for c in CANDS if results[(bound, gname, c)]["eligible"] == "yes"
                and not (c == "D" and results[(bound, gname, c)]["caught"] == 0)]
        split = [c for c in CANDS if results[(bound, gname, c)]["eligible"].startswith("SPLIT")]
        if not elig:
            per[bound] = ("none eligible" + (f"; split: {split}" if split else ""), None)
            continue
        best = max(elig, key=lambda c: (results[(bound, gname, c)]["caught"], -SIMPLER[c]))
        why = f"most caught: {best}"
        for c in sorted(elig, key=lambda c: SIMPLER[c]):
            if SIMPLER[c] < SIMPLER[best]:
                lo, hi = boot_net(d34, best, c)
                if lo <= 0 <= hi:
                    why += f"; {c} within noise of {best} (CI {lo:+.2f}..{hi:+.2f}) -> {c}"
                    best = c
                    break
        per[bound] = (why, best)
    a, b = per["upper"][1], per["lower"][1]
    picks[gname] = a if a == b and a is not None else None
    say(f"- **{gname}**: upper -> {per['upper'][0]}; lower -> {per['lower'][0]}. "
        f"**{'SELECTED ' + a if picks[gname] else 'no rule wins under both bounds: today’s behaviour'}**")

# (iii) decision 3: B vs A Brier on held players' play probability (status players only differ)
say("\n## (iii) Decision 3: B (held player keeps report probability) vs A (promoted to 1.0), Brier vs played")
for bound in ("upper", "lower"):
    d = results[(bound, "frame")]
    for gname, sel in (("non-QB", d.group != "QB"), ("QB", d.group == "QB")):
        for c in ("R2", "R3", "R2&R3"):
            h = d[sel & d[c] & d.truth.isin(["false", "genuine"]) & d.status.isin(["questionable", "doubtful"])]
            if not len(h):
                say(f"- {bound} {gname} {c}: no held player with a game status (A and B identical)")
                continue
            y = (h.truth == "false").astype(float).to_numpy()
            pa, pb = np.ones(len(h)), h.pp_held.to_numpy()
            ba, bb = ((pa - y) ** 2).mean(), ((pb - y) ** 2).mean()
            idx = [RNG.integers(0, len(h), len(h)) for _ in range(N_BOOT)]
            diff = [((pb[i] - y[i]) ** 2).mean() - ((pa[i] - y[i]) ** 2).mean() for i in idx]
            lo, hi = np.percentile(diff, [5, 95])
            verdict = "B better beyond noise" if hi < 0 else "A better beyond noise" if lo > 0 else "within noise: A (today) stays"
            say(f"- {bound} {gname} {c}: n {len(h)}, Brier A {ba:.3f}, B {bb:.3f}, B-A 90% CI {lo:+.3f}..{hi:+.3f} -> {verdict}")

# D's promotion cost: unlisted Questionables on identical-list teams
d = results[("upper", "frame")]
ident_teams = {(w, t) for w, t, i in zip(d.week, d.team, d.identical) if i}
qs = [(w, t, k) for (w, t, k), (s, _) in report.items() if s == "questionable" and (w, t) in ident_teams]
pl = sum(1 for q in qs if q in snap_any)
say(f"\n- D's promotion cost: unlisted Questionables on identical-list teams: {len(qs)} ({pl} played)")

# (iv) decision 4: stale charged ESPN-feed cases
say("\n## (iv) Decision 4: ESPN-only out/doubtful rows, not on the official report, played the prior week, charged, then played")
import json  # noqa: E402
served = {}
for p in st.select("predictions", {"sport": "nfl"}):
    g = games.get(p["game_id"])
    if p["model_version"] != "baseline-v1" or not g or g.get("week") not in WEEKS:
        continue
    c = p["components"]
    c = json.loads(c) if isinstance(c, str) else c
    for side in ("home", "away"):
        for x in ((c or {}).get("layer2") or {}).get(f"{side}_injuries") or []:
            t = g[f"{side}_team"]
            served[(int(g["week"]), t, player_key(t, x["player"]))] = x.get("points") or 0
cases, candidates = [], 0
for r in st.select("injuries", {"sport": "nfl"}):
    if r.get("season") != SEASON or r.get("week") not in WEEKS or not str(r.get("source", "")).startswith("espn"):
        continue
    if (r.get("status") or "").lower() not in ("out", "doubtful"):
        continue
    w, t = int(r["week"]), r["team"]
    k = player_key(t, r["player"])
    if (w, t, k) in report or (w - 1, t, k) not in snap_any:
        continue
    candidates += 1
    if served.get((w, t, k), 0) > 0 and (w, t, k) in snap_any:
        cases.append(f"wk{w} {t} {r['player']} {served[(w, t, k)]:.2f}")
say(f"- C-flaggable rows: {candidates}; stale charged cases (charged and played): {len(cases)} {cases or ''}")
say(f"- B's minimum is 5 by the end of week 10 (decision 4): {len(cases)} so far.")

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("# P68 replay (read-only), weeks 2-3 + PIT @ CLE\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
print(f"\nwrote {OUT}")
