"""TD board: every simulated player's chance of 1+ and 2+ touchdowns, with the reasons.

    python -m src.td_board          # writes data/td_board.json and the dashboard copy

DISPLAY / SHADOW ONLY, labelled EXPERIMENTAL and UNVALIDATED. It reads the stored
pregame simulations and the already-ranked anytime-TD list; it changes neither,
runs no simulation and writes nothing to the store.

- 1+ TD and 2+ TD are the share of that game's stored 10,000 simulations in which
  the player scored at least once / at least twice (`td_scorers.anytime_td`,
  `td_scorers.two_plus_td`). 2+ TD has never been graded.
- "Every player" means every player the simulator gives touchdown usage to
  (about eight a team). A player it gives no usage to has no number, not a zero.
- Edge vs market exists only where books post an anytime-TD price for the player
  (the devigged probability from `td_props`).
- The explanation blocks are season-to-date facts from nflverse play-by-play:
  team TD profile, what the opponent allows by position, the player's red-zone,
  inside-10 and goal-line work, the game script, and injuries that move his role.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from . import config, db
from .features import parse_dt
from .ingest_injuries import player_key

OUT = config.DATA_DIR / "td_board.json"
PUBLIC = config.ROOT_DIR / "dashboard" / "public" / "td_board.json" if hasattr(config, "ROOT_DIR") \
    else Path(__file__).resolve().parents[1] / "dashboard" / "public" / "td_board.json"
LABEL = ("EXPERIMENTAL / UNVALIDATED. Touchdowns are binary and high-variance; the scorer split is "
         "usage extrapolation. 2+ TD is new and has never been graded.")
GROUPS = {"RB": "RB", "FB": "RB", "HB": "RB", "WR": "WR", "TE": "TE", "QB": "QB"}


def edge(p_model: float | None, p_market: float | None) -> float | None:
    """Model minus devigged market, in probability points; None without a price."""
    if p_model is None or p_market is None:
        return None
    return round(float(p_model) - float(p_market), 4)


def sort_rows(rows: list[dict], key: str) -> list[dict]:
    """The three board orders. Unpriced players sort last on edge, never as zero."""
    if key == "edge":
        return sorted(rows, key=lambda r: (r.get("edge") is None, -(r.get("edge") or 0.0)))
    field = {"one": "p_one", "two": "p_two"}[key]
    return sorted(rows, key=lambda r: -(r.get(field) or 0.0))


def implied_points(spread_home: float | None, total: float | None, home: bool) -> float | None:
    if spread_home is None or total is None:
        return None
    return round(total / 2 - (spread_home if home else -spread_home) / 2, 1)


# --- season facts from play-by-play ----------------------------------------------------------

def season_facts(season: int, before_week: int) -> dict:
    """Team, defence and player touchdown facts from regular-season games before `before_week`."""
    import nfl_data_py as nfl
    import pandas as pd

    cols = ["game_id", "season_type", "week", "posteam", "defteam", "play_type", "yardline_100", "touchdown",
            "td_team", "td_player_id", "rusher_player_id", "receiver_player_id", "pass_attempt", "rush_attempt",
            "qb_scramble", "sack", "drive", "fixed_drive"]
    p = nfl.import_pbp_data([season], columns=cols, downcast=False, cache=False)
    p = p[(p.season_type == "REG") & (p.week < before_week) & p.posteam.notna()]
    ros = nfl.import_weekly_rosters([season])
    ros = ros.sort_values("week")
    idcol = "player_id" if "player_id" in ros.columns else "gsis_id"
    pos_by_id = {r[idcol]: GROUPS.get(str(r["position"]).upper()) for _, r in ros.iterrows() if isinstance(r[idcol], str)}
    id_by_key = {player_key(r["team"], r["player_name"]): r[idcol] for _, r in ros.iterrows() if isinstance(r[idcol], str)}

    games = p.groupby("posteam").game_id.nunique().to_dict()
    dgames = p.groupby("defteam").game_id.nunique().to_dict()
    off_td = p[(p.touchdown == 1) & (p.td_team == p.posteam)]
    run = p[(p.play_type == "run") & (p.qb_scramble != 1)]
    tgt = p[(p.play_type == "pass") & p.receiver_player_id.notna()]
    rz_drives = p[p.yardline_100 <= 20].groupby("posteam").apply(lambda d: d[["game_id", "fixed_drive"]].drop_duplicates().shape[0]).to_dict()
    rz_td_drives = off_td[off_td.yardline_100 <= 20].groupby("posteam").apply(lambda d: d[["game_id", "fixed_drive"]].drop_duplicates().shape[0]).to_dict()

    teams = {}
    for t, n in games.items():
        tt = off_td[off_td.posteam == t]
        teams[t] = {"games": int(n), "td_per_game": round(len(tt) / n, 2),
                    "rush_td_per_game": round(float((tt.play_type == "run").sum()) / n, 2),
                    "pass_td_per_game": round(float((tt.play_type == "pass").sum()) / n, 2),
                    "rz_trips_per_game": round(rz_drives.get(t, 0) / n, 2),
                    "rz_td_rate": round(rz_td_drives.get(t, 0) / rz_drives[t], 3) if rz_drives.get(t) else None}

    off_td = off_td.assign(grp=off_td.td_player_id.map(pos_by_id))
    allowed: dict = {}
    for grp in ("RB", "WR", "TE", "QB"):
        per = {t: round(float(((off_td.defteam == t) & (off_td.grp == grp)).sum()) / n, 2) for t, n in dgames.items()}
        order = sorted(per, key=lambda t: -per[t])
        for t in per:
            allowed.setdefault(t, {})[grp] = {"per_game": per[t], "rank_most_allowed": order.index(t) + 1, "of": len(order)}

    def counts(frame, col):
        return frame.groupby(["posteam", col]).size().to_dict()

    c = {"rz_tgt": counts(tgt[tgt.yardline_100 <= 20], "receiver_player_id"),
         "i10_tgt": counts(tgt[tgt.yardline_100 <= 10], "receiver_player_id"),
         "gl_tgt": counts(tgt[tgt.yardline_100 <= 5], "receiver_player_id"),
         "rz_car": counts(run[run.yardline_100 <= 20], "rusher_player_id"),
         "i10_car": counts(run[run.yardline_100 <= 10], "rusher_player_id"),
         "gl_car": counts(run[run.yardline_100 <= 5], "rusher_player_id")}
    team_tot = {k: {} for k in c}
    for k, d in c.items():
        for (t, _), n in d.items():
            team_tot[k][t] = team_tot[k].get(t, 0) + n
    tds = off_td.groupby(["posteam", "td_player_id"]).size().to_dict()
    touched = pd.concat([run[["posteam", "rusher_player_id", "game_id"]].rename(columns={"rusher_player_id": "pid"}),
                         tgt[["posteam", "receiver_player_id", "game_id"]].rename(columns={"receiver_player_id": "pid"})])
    pg = touched.groupby(["posteam", "pid"]).game_id.nunique().to_dict()
    return {"teams": teams, "allowed": allowed, "counts": c, "team_tot": team_tot, "tds": tds, "player_games": pg,
            "id_by_key": id_by_key, "through_week": before_week - 1}


def player_usage(facts: dict, team: str, name: str) -> dict | None:
    pid = facts["id_by_key"].get(player_key(team, name))
    if pid is None:
        return None
    out = {"games_with_a_touch_or_target": int(facts["player_games"].get((team, pid), 0)),
           "tds": int(facts["tds"].get((team, pid), 0))}
    for k, d in facts["counts"].items():
        n = int(d.get((team, pid), 0))
        tot = facts["team_tot"][k].get(team, 0)
        out[k] = n
        out[k + "_team_share"] = round(n / tot, 3) if tot else None
    return out


# --- build ----------------------------------------------------------------------------------

def build(season: int | None = None, week: int | None = None, now: datetime | None = None,
          store=None, facts: dict | None = None, td_list: dict | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    own = store is None
    store = store or db.get_store()
    try:
        games = [g for g in store.select("games", {"sport": "nfl"}) if (season is None or g["season"] == season)]
        if week is None:
            up = [g for g in games if not g.get("completed") and parse_dt(g["kickoff_time"]) and parse_dt(g["kickoff_time"]) > now]
            first = min(up, key=lambda g: parse_dt(g["kickoff_time"]))
            season, week = first["season"], first["week"]
        wk = sorted([g for g in games if g["season"] == season and g["week"] == week], key=lambda g: g["kickoff_time"])
        sims = {g["game_id"]: (db.select_merged(store, "game_simulations", {"game_id": g["game_id"]}) or [None])[0] for g in wk}
        injuries = store.select("injuries", {"sport": "nfl", "season": season, "week": week})
    finally:
        if own:
            store.close()
    if td_list is None:
        path = config.DATA_DIR / "td_props.json"
        td_list = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    priced = {}
    for part in ("props", "more", "held_out"):
        for r in td_list.get(part) or []:
            priced[(r["game_id"], player_key(r["team"], r["player"]))] = r
    facts = facts if facts is not None else season_facts(season, week)
    out_by_team: dict = {}
    for r in injuries:
        if r.get("status") in ("out", "ir", "doubtful", "questionable", "inactive"):
            out_by_team.setdefault(r["team"], []).append(r)

    rows, game_meta = [], []
    for g in wk:
        gid, sim = g["game_id"], sims.get(g["game_id"])
        started = parse_dt(g["kickoff_time"]) <= now
        meta = {"game_id": gid, "away": g["away_team"], "home": g["home_team"], "kickoff": g["kickoff_time"],
                "started": started, "simulated": bool(sim)}
        game_meta.append(meta)
        if not sim:
            continue
        ts = sim.get("td_scorers") or {}
        spread, total = sim.get("market_spread"), sim.get("market_total")
        meta.update({"market_spread_home": spread, "market_total": total, "sim_margin_home": sim.get("sim_margin_home"),
                     "sim_total": round((sim.get("mean_home_points") or 0) + (sim.get("mean_away_points") or 0), 1),
                     "sim_generated_at": sim.get("generated_at")})
        box = sim.get("box_score") or {}
        for side, team, opp in (("away", g["away_team"], g["home_team"]), ("home", g["home_team"], g["away_team"])):
            tb = ((box.get(side) or {}).get("team") or {}) if isinstance(box.get(side), dict) else {}
            plays = None
            if tb.get("pass_att") and tb.get("rush_att"):
                plays = round(tb["pass_att"]["mean"] + tb["rush_att"]["mean"], 1)
            script = {"market_spread_team": None if spread is None else (spread if side == "home" else -spread),
                      "market_total": total, "implied_points": implied_points(spread, total, side == "home"),
                      "sim_points": round(sim.get(f"mean_{side}_points") or 0, 1),
                      "sim_team_tds": sim.get(f"{side}_td_mean"), "sim_plays": plays,
                      "sim_win_prob": round(sim["home_win_prob"] if side == "home" else 1 - sim["home_win_prob"], 3)}
            shifts = (ts.get("injury_shifts") or {}).get(team) or []
            for p in ts.get(side) or []:
                name, pos = p["player"], (p.get("position") or "").upper()
                grp = GROUPS.get(pos, pos)
                m = priced.get((gid, player_key(team, name)))
                p_mkt = m.get("p_market") if m else None
                role = [{"kind": "gains", "from": s["player"], "status": s.get("status"), "play_prob": s.get("play_prob"),
                         "carry_share": s.get("moved_carry_share"), "target_share": s.get("moved_target_share")}
                        for s in shifts if s.get("to") == name]
                role += [{"kind": "own_status", "status": s.get("status"), "play_prob": s.get("play_prob")}
                         for s in shifts if s.get("player") == name]
                mates = [{"player": r["player"], "position": r.get("position"), "status": r.get("status"),
                          "play_prob": r.get("play_probability")}
                         for r in out_by_team.get(team, [])
                         if GROUPS.get((r.get("position") or "").upper()) in ("RB", "WR", "TE", "QB")
                         and player_key(team, r["player"]) != player_key(team, name)]
                rows.append({
                    "game_id": gid, "game": f"{g['away_team']} @ {g['home_team']}", "kickoff": g["kickoff_time"],
                    "started": started, "team": team, "opponent": opp, "player": name, "position": pos,
                    "depth_rank": p.get("depth_rank"),
                    "p_one": p.get("anytime_td"), "p_two": p.get("two_plus_td"), "expected_tds": p.get("expected_tds"),
                    "p_market": p_mkt, "yes_price": m.get("yes_price") if m else None, "books": m.get("books") if m else None,
                    "edge": edge(p.get("anytime_td"), p_mkt),
                    "held_out": bool(m and m.get("held_reason")) if m else False,
                    "explain": {
                        "team_profile": facts["teams"].get(team),
                        "opponent_allows": {"group": grp, **(facts["allowed"].get(opp, {}).get(grp) or {})} if grp in ("RB", "WR", "TE", "QB") else None,
                        "usage_season": player_usage(facts, team, name),
                        "usage_sim_shares": {k: p.get(k) for k in ("rz_target_share", "rz_carry_share", "gl_carry_share")},
                        "game_script": script,
                        "role_injuries": role,
                        "teammates_out_or_questionable": mates[:8],
                    }})
    hist_path = config.DATA_DIR / "board" / "forward_bars.json"
    history = json.loads(hist_path.read_text(encoding="utf-8")).get("td") if hist_path.exists() else None
    return {"generated_at": now.isoformat(), "season": season, "week": week, "label": LABEL,
            "two_plus_note": "2+ TD is NEW and EXPERIMENTAL: no 2+ TD number has been graded yet.",
            "method": "Share of each game's stored 10,000 pregame simulations with 1+ / 2+ touchdowns for the player. "
                      "Edge = model minus devigged market, only where books post an anytime-TD price.",
            "facts_through_week": facts.get("through_week"), "lines_pulled_at": td_list.get("lines_pulled_at"),
            "history": history, "games": game_meta, "players": sort_rows(rows, "one"),
            "counts": {"players": len(rows), "priced": sum(r["p_market"] is not None for r in rows),
                       "games": sum(1 for m in game_meta if m["simulated"])}}


def publish(doc: dict) -> None:
    text = json.dumps(doc, indent=1, default=str)
    OUT.write_text(text, encoding="utf-8")
    PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC.write_text(text, encoding="utf-8")


def run() -> dict:
    doc = build()
    publish(doc)
    c = doc["counts"]
    print(f"[td-board] week {doc['week']}: {c['players']} players in {c['games']} games, {c['priced']} with a market price "
          f"-> {OUT} and {PUBLIC}")
    return doc


if __name__ == "__main__":
    argparse.ArgumentParser(description="TD board (1+ / 2+ TD per player, experimental).").parse_args()
    run()
