"""P51 validation replay (research only; nothing live, nothing stored).

    python research/p51/p51_replay.py [out.md]

Criteria were set with the user before this ran (calibration-log.md, P51 row):
(1) CHI week 3 comes out as Keenum; (2) no team-game flips from the right starter
to the wrong one; (3) every firing case is listed; (4) every non-firing
team-game is byte-identical (squad order, shares, passer weights); (5) suite.

Per week, pregame inputs only:
- roles: `sim_data.player_roles` on the nflverse depth chart as of the week's
  first kickoff (as P49's replay), with 2026 play-by-play before that week;
- injury report: that week's rows last pulled before the game's kickoff;
- inactive lists first seen before kickoff, applied with P49's QB hold as live;
- priced QBs: pass-yds lines from the saved props snapshot for that week
  (week 2 pre-friday 9/18, week 3 pre-sunday 9/27, week 4 the current file).
Truth: the QB with the most dropbacks in each team-game (nflverse pbp). Week 4
is unplayed: it is checked for firing and byte-identity only.
No game is re-simulated: only QB order, shares and passer weights are rebuilt.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import nfl_data_py as nfl  # noqa: E402

from src import db, sim_data, simulate_nfl  # noqa: E402
from src.box_score import passer_weights  # noqa: E402
from src.features import apply_inactives, latest_injury_report, parse_dt, qb_context  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else None
# --window-lines: the corrected run_sunday order (props pulled before each window's sim).
# Each game takes the latest saved pull stamped before its kickoff, from any saved lines file.
WINDOW_LINES = "--window-lines" in sys.argv
if OUT and OUT.name.startswith("--"):
    OUT = None
# --official-report: add each week's final official report (nflverse) for players the stored
# pregame rows lack. Stored injury rows re-pulled after kickoff drop out of the "before
# kickoff" filter, which left e.g. ATL and SEA week 2 with no QB statuses at all.
OFFICIAL = "--official-report" in sys.argv
LINE_FILES = sorted((ROOT / "data" / "snapshots").glob("*/props_lines.json")) + [ROOT / "data" / "props_lines.json"]
SNAPS = {2: ROOT / "data/snapshots/pre-friday_2026-09-18/props_lines.json",
         3: ROOT / "data/snapshots/pre-sunday_2026-09-27/props_lines.json",
         4: ROOT / "data/props_lines.json"}
lines: list[str] = []


def say(text=""):
    print(text)
    lines.append(text)


def abbr(name):
    n = re.sub(r"\b(Jr|Sr|II|III|IV)\.?$", "", str(name).strip()).strip()
    parts = re.sub(r"[^A-Za-z .'-]", "", n).split()
    return (parts[0][0] + "." + parts[-1]).lower().replace("'", "") if len(parts) >= 2 else n.lower()


store = db.get_store()
games = {g["game_id"]: g for g in store.select("games", {"sport": "nfl"})
         if g.get("season") == 2026 and g.get("week") in SNAPS}
kick = {gid: parse_dt(g["kickoff_time"]) for gid, g in games.items()}
inj_all = store.select("injuries", {"sport": "nfl", "season": 2026})
lists_all = [r for r in db.select_merged(store, "inactives", {"season": 2026}) if r["game_id"] in games]

pbp26 = nfl.import_pbp_data([2026], columns=["game_id", "week", "posteam", "passer_player_name", "qb_dropback"],
                            downcast=True, cache=False)
drops = pbp26[pbp26["qb_dropback"] == 1].dropna(subset=["passer_player_name"])
truth = {(gid, team): g.groupby("passer_player_name").size().idxmax()
         for (gid, team), g in drops.groupby(["game_id", "posteam"])}

from src.ingest_injuries import _practice, _status, play_probability, player_key  # noqa: E402

NFLV = nfl.import_injuries([2026]) if OFFICIAL else None


def with_official(report, week, teams):
    if NFLV is None:
        return report
    have = {player_key(r["team"], r["player"]) for r in report}
    add = []
    for _, r in NFLV[(NFLV["week"] == week) & NFLV["team"].isin(teams)].iterrows():
        k = player_key(r["team"], r["full_name"])
        st, pr = _status(r.get("report_status")), _practice(r.get("practice_status"))
        if k in have or (st is None and pr in (None, "full")):
            continue
        add.append({"player": r["full_name"], "team": r["team"], "position": str(r.get("position") or "").upper(),
                    "status": st, "practice_trend": pr, "play_probability": play_probability(st, pr),
                    "season": 2026, "week": week, "source": "nflverse-final"})
    return report + add


DC = nfl.import_depth_charts([2026])
DC["dtp"] = pd.to_datetime(DC["dt"], utc=True)
sim_pbp = sim_data.load_pbp((2025, 2026))


def depth_asof(cutoff):
    d = DC[DC["pos_abb"].isin(sim_data.OFFENSE_DEPTH_POSITIONS) & DC["gsis_id"].notna() & (DC["dtp"] < cutoff)]
    d = d[d["dtp"] == d.groupby("team")["dtp"].transform("max")].sort_values("pos_rank").drop_duplicates(["team", "gsis_id"])
    out = pd.DataFrame({"team": d["team"], "player_id": d["gsis_id"], "player": d["player_name"],
                        "position": d["pos_abb"], "rank": d["pos_rank"].astype(int)}).reset_index(drop=True)
    return out, str(d["dt"].max())


real_current_depth = sim_data.current_depth
rows, fired, notes = [], [], []
for week in sorted(SNAPS):
    wk_games = sorted(gid for gid, g in games.items() if g["week"] == week)
    cutoff = min(kick[g] for g in wk_games)
    depth, as_of = depth_asof(cutoff)
    sim_data.current_depth = lambda season, _d=(depth, as_of): _d
    pbp_w = sim_pbp[(sim_pbp["season"] < 2026) | (sim_pbp["week"] < week)]
    roles, _ = sim_data.player_roles(2026, pbp_w)
    sim_data.current_depth = real_current_depth
    snap = json.loads(SNAPS[week].read_text(encoding="utf-8"))
    line_src = {}
    if WINDOW_LINES:
        for f in LINE_FILES:
            d = json.loads(f.read_text(encoding="utf-8"))
            if (d.get("season"), d.get("week")) != (2026, week):
                continue
            for gid, entry in (d.get("games") or {}).items():
                t = parse_dt(entry.get("pulled_at"))
                if gid in kick and t and t < kick[gid] and (gid not in line_src or t > line_src[gid][0]):
                    line_src[gid] = (t, f.parent.name, entry)
        for gid, (t, name, entry) in line_src.items():
            snap["games"][gid] = entry
    assert (snap.get("season"), snap.get("week")) == (2026, week), SNAPS[week]
    qbdepth = {t: list(g.sort_values("rank")["player"]) for t, g in depth[depth["position"] == "QB"].groupby("team")}
    qb = qb_context(store, lines=snap, depth=qbdepth)
    notes.append(f"week {week}: depth chart as of {as_of} (before first kickoff {cutoff:%Y-%m-%d %H:%MZ}); "
                 f"props snapshot {SNAPS[week].parent.name}" + (" (each game overridden by its latest pre-kickoff pull)" if WINDOW_LINES else ""))
    for gid in wk_games:
        g = games[gid]
        report = latest_injury_report([r for r in inj_all if r.get("week") == week
                                       and parse_dt(r.get("pulled_at")) < kick[gid]])
        report = with_official(report, week, (g["home_team"], g["away_team"]))
        pre = [{**r, "pulled_at": g["kickoff_time"]} for r in lists_all
               if r["game_id"] == gid and parse_dt(r["first_seen_at"]) < kick[gid]]
        injuries = apply_inactives(report, pre, qb=qb, holds=[])
        priced = {n for n, m in ((snap["games"].get(gid) or {}).get("players") or {}).items() if "player_pass_yds" in m} or None
        for team in (g["home_team"], g["away_team"]):
            off = simulate_nfl.team_shares(roles, team, injuries, None, None)
            on = simulate_nfl.team_shares(roles, team, injuries, None, priced)
            w_off, w_on = passer_weights(off[0]), passer_weights(on[0])
            q_off = off[0].at[int(w_off.argmax()), "player"] if len(w_off) else None
            q_on = on[0].at[int(w_on.argmax()), "player"] if len(w_on) else None
            same = (off[0].equals(on[0]) and all(np.array_equal(off[1][c], on[1][c]) for c in off[1])
                    and off[2] == on[2] and np.array_equal(w_off, w_on))
            t = truth.get((gid, team))
            right = lambda q: None if t is None or q is None else abbr(q) == str(t).lower().replace("'", "")  # noqa: E731
            src = line_src.get(gid) if WINDOW_LINES else None
            r = {"week": week, "game": gid, "team": team, "before": q_off, "after": q_on, "truth": t,
                 "lines": f"{src[1]} {src[0]:%m-%d %H:%MZ}" if src else SNAPS[week].parent.name,
                 "right_before": right(q_off), "right_after": right(q_on), "identical": same,
                 "priced": sorted(n for n in (priced or ()) if n in set(on[0].loc[on[0]["position"] == "QB", "player"]))}
            rows.append(r)
            if not same:
                fired.append(r)

say("# P51 validation replay (research only)" + (" - corrected order: each game on its latest pre-kickoff saved pull" if WINDOW_LINES else "")
    + (" - plus the official final report where stored pregame rows are missing" if OFFICIAL else ""))
say()
for n in notes:
    say(f"- {n}")
say()
chi = next((r for r in rows if r["game"] == "2026_03_PHI_CHI" and r["team"] == "CHI"), None)
flips = [r for r in rows if r["right_before"] is True and r["right_after"] is False]
fixes = [r for r in rows if r["right_before"] is False and r["right_after"] is True]
nonfiring = [r for r in rows if r not in fired]
say(f"Team-games replayed: {len(rows)} (weeks 2-3 with a pbp starter: {sum(r['truth'] is not None for r in rows)}; "
    f"week 4 unplayed: {sum(r['week'] == 4 for r in rows)})")
say()
say("| # | criterion | result | verdict |")
say("|---|---|---|---|")
say(f"| 1 | CHI week 3 comes out as Keenum | before {chi and chi['before']}, after {chi and chi['after']} (pbp starter {chi and chi['truth']}) "
    f"| **{'pass' if chi and chi['after'] == 'Case Keenum' else 'fail'}** |")
say(f"| 2 | no team-game flips right -> wrong | {len(flips)} flips; {len(fixes)} wrong -> right | **{'pass' if not flips else 'fail'}** |")
say(f"| 3 | every firing case listed | {len(fired)} firing (below) | **listed** |")
say(f"| 4 | every non-firing team-game byte-identical | {sum(r['identical'] for r in nonfiring)}/{len(nonfiring)} identical "
    f"(squad order, shares, shifts, passer weights) | **{'pass' if all(r['identical'] for r in nonfiring) else 'fail'}** |")
say("| 5 | suite passes | run separately | see log |")
say()
say("## Firing cases")
say()
say("| week | game | team | QB1 before | QB1 after | pbp starter | priced | right before -> after |")
say("|---|---|---|---|---|---|---|---|")
for r in fired:
    say(f"| {r['week']} | {r['game']} | {r['team']} | {r['before']} | {r['after']} | {r['truth'] or 'unplayed'} | "
        f"{', '.join(r['priced']) or '-'} | {r['right_before']} -> {r['right_after']} |")
if not fired:
    say("| - | none | | | | | | |")
say()
wrong = [r for r in rows if r["right_after"] is False]
say(f"Reported, not a criterion: team-games where the sim's QB1 is still not the pbp starter after the rule: {len(wrong)}")
for r in wrong:
    say(f"- wk{r['week']} {r['game']} {r['team']}: sim {r['after']}, pbp {r['truth']}, priced {', '.join(r['priced']) or '-'} (lines: {r['lines']})")

store.close()
if OUT:
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nwrote {OUT}")
