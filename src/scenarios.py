"""P66: the prediction under each realistic starting QB, for games where it is unresolved. Read-only.

    python -m src.scenarios                         # every candidate game this week, printed
    python -m src.scenarios --game 2026_04_NYJ_CHI  # one game
    python -m src.scenarios --publish               # also write data/scenarios.json for the game page

Comparison only. The store is wrapped read-only (writes raise), and nothing
here writes predictions, simulations, props or grades: only
data/scenarios.json and its dashboard copy, which nothing else reads.

Candidates come from signals the pipeline already produces, per team:
  - P53: the served sim's QB1 is not the QB the books price ("input_warnings");
  - a depth QB1 with a game status (questionable / doubtful) on the current report;
  - a P49 'unresolved' hold (a priced or projected starter flagged inactive).
A team with a posted inactive list, or a game that has kicked off, gets none:
the starter is known.

Scenarios, at most three per team: the status QB plays (play probability 1),
the status QB is out (0), and the books' priced QB starts. Each re-runs the
baseline on a copy of the injury list (the margin moves only through the
injury charge) and the sim anchored to that margin, with the expected starter
promoted through the sim's own path (`inputs.starters`). The "as served" row
re-runs the served inputs and is the control: it must reproduce the served sim.

What a scenario cannot show is quarterback quality: the engine gives any
starter the team's passing (P39; the 2026-10-01 NYJ @ CHI run). Every scenario
carries that caveat, and a backup QB's own props are marked unreliable.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
from datetime import datetime, timezone

from . import config, db
from .features import FeatureContext, parse_dt
from .ingest_injuries import player_key
from .predict_baseline import predict_game

OUT_JSON = config.DATA_DIR / "scenarios.json"
PUBLIC_JSON = config.ROOT / "dashboard" / "public" / "scenarios.json"
MAX_PER_TEAM = 3
STATUS_QB = ("questionable", "doubtful")
CAVEAT = ("Comparison only, unvalidated. A scenario changes the margin only through the injury charge "
          "(a generic quarterback value scaled by snap share) and changes who takes the passer slot. It does "
          "not model quarterback quality: the simulation gives any starter this team's passing, so a backup's "
          "own numbers look like the starter's. Props marked unreliable measure that gap, not the player.")
_P53 = re.compile(r"^(?P<team>[A-Z]{2,3}): sim QB1 (?P<qb1>.+?), but the books price (?P<priced>.+)$")


class ReadOnlyStore:
    """Reads pass through; any write raises (P66 writes nothing to the store)."""

    _WRITES = {"upsert", "insert", "delete", "update", "upsert_or_mirror"}

    def __init__(self, store):
        self._store = store

    def __getattr__(self, name):
        if name in self._WRITES:
            raise PermissionError(f"scenarios is read-only: store.{name} is not allowed")
        return getattr(self._store, name)


# --- candidates ----------------------------------------------------------------

def _depth_qbs(roles, team: str) -> list[str]:
    qbs = roles[(roles["team"] == team) & (roles["position"] == "QB")].sort_values("rank")
    return list(qbs["player"])


def _report_row(injuries: list[dict], team: str, player: str) -> dict | None:
    k = player_key(team, player)
    return next((r for r in injuries if r.get("team") == team and player_key(r["team"], r["player"]) == k), None)


def team_specs(team: str, depth: list[str], injuries: list[dict], warning: dict | None,
               unresolved: list[str]) -> list[dict]:
    """The scenarios for one team, from its signals. Each spec: key, label,
    changes {player: play probability}, starter (player name or None)."""
    specs: list[dict] = []
    status_qb = None
    if depth:
        row = _report_row(injuries, team, depth[0])
        if row is not None and (row.get("status") in STATUS_QB or (0 < float(row.get("play_probability") or 0) < 1)):
            status_qb = depth[0]
    for name in unresolved:
        if status_qb is None:
            status_qb = name
    if status_qb is not None:
        nxt = next((q for q in depth if q != status_qb), None)
        specs.append({"key": f"{team}:{status_qb}:plays", "label": f"{status_qb} plays",
                      "changes": {status_qb: 1.0}, "starter": None})
        specs.append({"key": f"{team}:{status_qb}:out", "label": f"{status_qb} out" + (f" ({nxt} starts)" if nxt else ""),
                      "changes": {status_qb: 0.0}, "starter": None, "next": nxt})
    if warning is not None:
        sim_qb1 = warning["qb1"]
        for priced in [p.strip() for p in warning["priced"].split(",") if p.strip()]:
            if priced == sim_qb1:
                continue
            changes = {status_qb: 0.0} if status_qb is not None and status_qb != priced else {}
            out_spec = next((s for s in specs if s["key"].endswith(":out") and s.get("next") == priced), None)
            if out_spec is not None and not out_spec.get("starter"):
                out_spec["label"] = f"{status_qb} out ({priced} starts, the books' QB)"
                continue
            specs.append({"key": f"{team}:{priced}:starts", "label": f"{priced} starts (the books' QB)",
                          "changes": changes, "starter": priced})
    for s in specs:
        s.pop("next", None)
    return specs[:MAX_PER_TEAM]


def _warnings(sim_row: dict | None) -> dict[str, dict]:
    comp = (sim_row or {}).get("components")
    comp = json.loads(comp) if isinstance(comp, str) else (comp or {})
    out = {}
    for w in comp.get("input_warnings") or []:
        if (m := _P53.match(w.strip())):
            out[m["team"]] = {"qb1": m["qb1"], "priced": m["priced"]}
    return out


# --- running a scenario ----------------------------------------------------------

def _apply(injuries: list[dict], team: str, changes: dict[str, float], position: str = "QB") -> list[dict]:
    out = copy.deepcopy(injuries)
    for player, prob in changes.items():
        row = _report_row(out, team, player)
        if row is None:
            if prob >= 1.0:
                continue
            row = {"player": player, "team": team, "position": position, "status": "scenario",
                   "practice_trend": None, "snap_share": None, "source": "scenario"}
            out.append(row)
        row["play_probability"] = float(prob)
        row["status"] = row.get("status") if prob not in (0.0, 1.0) else ("out" if prob == 0 else None)
    return out


def _player_id(roles, team: str, player: str) -> str | None:
    rows = roles[(roles["team"] == team) & (roles["position"] == "QB")]
    k = player_key(team, player)
    hit = [r for _, r in rows.iterrows() if player_key(team, r["player"]) == k]
    return hit[0]["player_id"] if hit else None


def summarize(row: dict, game: dict) -> dict:
    from .export_sims import _json, pregame_view

    view = pregame_view(row, game["kickoff_time"])
    box = _json(row.get("box_score")) or {}
    comp = row.get("components")
    comp = json.loads(comp) if isinstance(comp, str) else (comp or {})
    qbs = {}
    for side, team in (("home", game["home_team"]), ("away", game["away_team"])):
        cands = [p for p in (box.get(side) or {}).get("players") or [] if p.get("position") == "QB"]

        def att(p):
            a = (p.get("passing") or {}).get("att") or {}
            return a.get("median") if a.get("median") is not None else (a.get("mean") or 0)
        if cands:
            q = max(cands, key=att)
            ps = q.get("passing") or {}
            qbs[team] = {"player": q["player"], "pass_att": att(q),
                         "pass_yds": (ps.get("yds") or {}).get("median"), "pass_td": (ps.get("td") or {}).get("median")}
    return {"home_win_prob": view.get("home_win_prob"), "margin_p50": (view.get("margin") or {}).get("p50"),
            "total_p50": (view.get("total") or {}).get("p50"),
            "unanchored_margin": (comp.get("anchor") or {}).get("unanchored_sim_margin"),
            "sim_qbs": qbs, "_view": {**view, "box_score": box}}


def _p_over(lines_game: dict, gid: str, view: dict) -> dict[tuple, dict]:
    """(player, market) -> {line, p_over} from the scenario sim, for every priced prop."""
    from .props import rank

    one = {"games": {gid: lines_game}}
    r = rank(one, {gid: view}, now=datetime(2000, 1, 1, tzinfo=timezone.utc))
    out = {}
    for x in r["ranked"] + r["held_out"]:
        p_raw = x["p_model_raw"] if x["pick"] == "over" else 1 - x["p_model_raw"]
        out[(x["odds_name"], x["market"])] = {"player": x["player"], "team": x["team"], "line": x["line"],
                                              "label": x["label"], "p_over": round(p_raw, 4)}
    return out


def run_game(gid: str, store, ctx: FeatureContext, inputs, n: int | None, lines: dict, qbc) -> dict | None:
    from .simulate_nfl import _stored_anchors, simulate_one

    game = next(g for g in ctx.games if g["game_id"] == gid)
    sim_row = next((r for r in store.select("game_simulations") if r["game_id"] == gid), None)
    warnings = _warnings(sim_row)
    unresolved = {}
    for h in getattr(ctx, "qb_holds", []) or []:
        if h.get("game_id") == gid and h.get("decision") == "unresolved":
            unresolved.setdefault(h["team"], []).append(h["player"])
    week = int(game["week"])
    teams = {}
    for team in (game["home_team"], game["away_team"]):
        specs = team_specs(team, _depth_qbs(inputs.roles, team), ctx.injuries, warnings.get(team),
                           unresolved.get(team, []))
        if specs:
            teams[team] = specs
    if not teams:
        return None

    # Scenarios run at the served sim's count: the control can only reproduce
    # the served sim at the same count, and a scenario's difference from it
    # would otherwise be partly sampling noise. --sims overrides, for quick
    # checks, and the control is then reported as not comparable.
    served_n = int((sim_row or {}).get("n_sims") or 0) or None
    n = n or served_n or 10_000
    anchors = _stored_anchors(store, [game])
    served_anchor = anchors.get(gid, (None, None))[0]
    rebuilt = predict_game(ctx.build(game))
    served = simulate_one(game, ctx, inputs, n, anchor=served_anchor, anchor_label="scenario: as served", qb_check=qbc)
    served_sum = summarize(served, game)
    lines_game = (lines.get("games") or {}).get(gid)
    served_p = _p_over(lines_game, gid, served_sum["_view"]) if lines_game else {}
    served_qb1 = {t: q["player"] for t, q in served_sum["sim_qbs"].items()}

    result = {"game_id": gid, "home": game["home_team"], "away": game["away_team"], "kickoff": game["kickoff_time"],
              "caveat": CAVEAT, "served_margin": served_anchor,
              "rebuilt_margin": rebuilt["model_margin_home"] if rebuilt else None,
              "control": {"label": "As served", **{k: v for k, v in served_sum.items() if k != "_view"},
                          "baseline_margin": served_anchor},
              "scenarios": []}
    result["sims"] = n
    if sim_row is not None:
        result["control"]["reproduces_served"] = (_same_sim(served, sim_row) if n == served_n
                                                  else f"not comparable ({n:,} sims vs the served {served_n:,})")

    for team, specs in teams.items():
        for spec in specs:
            sctx = copy.copy(ctx)
            sctx.injuries = _apply(ctx.injuries, team, spec["changes"])
            feats = sctx.build(game)
            pred = predict_game(feats)
            margin = pred["model_margin_home"]
            side = "home" if team == game["home_team"] else "away"
            raw = sum(float(d.get("points") or 0) for d in feats.get(f"{side}_injury_detail") or [])
            charged = abs(float(feats.get(f"{side}_injury_points") or 0))
            inp = copy.copy(inputs)
            inp.starters = dict(inputs.starters)
            if spec["starter"] and (pid := _player_id(inputs.roles, team, spec["starter"])):
                inp.starters[(week, team)] = pid
            row = simulate_one(game, sctx, inp, n, anchor=margin, anchor_label=f"scenario: {spec['label']}",
                               qb_check=qbc)
            sm = summarize(row, game)
            starter = (sm["sim_qbs"].get(team) or {}).get("player")
            moved = []
            if lines_game:
                sp = _p_over(lines_game, gid, sm["_view"])
                for k, v in sp.items():
                    base = served_p.get(k)
                    unreliable = v["team"] == team and starter and v["player"] == starter and starter != served_qb1.get(team)
                    moved.append({**v, "odds_name": k[0], "market": k[1],
                                  "served_p_over": base["p_over"] if base else None,
                                  "delta": round(v["p_over"] - base["p_over"], 4) if base else None,
                                  "unreliable": bool(unreliable)})
                moved.sort(key=lambda m: (not m["unreliable"], -abs(m["delta"] or 0)))
            result["scenarios"].append({
                "key": spec["key"], "team": team, "label": spec["label"], "changes": spec["changes"],
                "starter_override": spec["starter"], "baseline_margin": margin,
                "injury_points": round(charged, 2), "injury_cap_binds": raw > charged + 0.005,
                "margin_change": round(margin - (served_anchor or 0), 2) if served_anchor is not None else None,
                **{k: v for k, v in sm.items() if k != "_view"},
                "props": [m for m in moved if m["unreliable"]] + [m for m in moved if not m["unreliable"]][:6],
            })
    return result


# Fields that record when or how a run was made, not what it produced.
_STAMPS = {"generated_at", "pulled_at", "id", "created_at", "updated_at"}
_NESTED_STAMPS = {("components", "anchor", "model"), ("td_scorers", "depth_chart_as_of")}


def _norm(v, path=()):
    """JSON-decoded, integral floats as ints (the store returns 20 where a fresh
    run has 20.0), timestamp-only nested fields dropped."""
    if isinstance(v, str) and v[:1] in "[{":
        try:
            v = json.loads(v)
        except ValueError:
            return v
    if isinstance(v, dict):
        return {k: _norm(x, path + (k,)) for k, x in v.items() if path + (k,) not in _NESTED_STAMPS}
    if isinstance(v, list):
        return [_norm(x, path) for x in v]
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def _same_sim(fresh: dict, stored: dict) -> bool:
    """The control: the as-served re-run equals the served sim, every produced
    value compared; only run stamps (when it ran, the anchor's label, the depth
    chart file's timestamp) and number formatting are ignored."""
    keys = (set(fresh) & set(stored)) - _STAMPS
    keys = {k for k in keys if not k.startswith("_")}
    canon = lambda r: json.dumps({k: _norm(r[k], (k,)) for k in keys}, sort_keys=True, default=str)   # noqa: E731
    return canon(fresh) == canon(stored)


def run(game_id: str | None = None, n: int | None = None, publish: bool = False) -> dict:
    from .ingest_injuries import _infer_week
    from .simulate_nfl import load_inputs, qb_check_inputs

    store = ReadOnlyStore(db.get_store())
    try:
        ctx = FeatureContext(store, "nfl")
        now = datetime.now(timezone.utc)
        season = now.year
        week = _infer_week(store, "nfl", season)
        games = [g for g in ctx.games if g.get("season") == season and int(g.get("week") or 0) == week
                 and (k := parse_dt(g.get("kickoff_time"))) and k > now]
        if game_id:
            games = [g for g in games if g["game_id"] == game_id]
        posted = {(r["game_id"], r["team"]) for r in db.select_merged(store, "inactives")}
        lines = json.loads((config.DATA_DIR / "props_lines.json").read_text(encoding="utf-8"))
        inputs = load_inputs(season)
        qbc = qb_check_inputs(store)
        out = {"generated_at": now.isoformat(), "season": season, "week": week, "games": {}}
        for g in games:
            if (g["game_id"], g["home_team"]) in posted and (g["game_id"], g["away_team"]) in posted:
                continue   # both lists posted: the starters are known
            res = run_game(g["game_id"], store, ctx, inputs, n, lines, qbc)
            if res is not None:
                out["games"][g["game_id"]] = res
    finally:
        store.close()
    if publish:
        config.ensure_dirs()
        OUT_JSON.write_text(json.dumps(out, default=str), encoding="utf-8")
        if PUBLIC_JSON.parent.exists():
            shutil.copy(OUT_JSON, PUBLIC_JSON)
    return out


def format_report(out: dict) -> str:
    lines = [f"P66 scenarios, week {out['week']}, {len(out['games'])} game(s)"]
    for gid, g in out["games"].items():
        c = g["control"]
        lines.append(f"\n{g['away']} @ {g['home']}  ({g['sims']:,} sims)  served baseline {g['served_margin']:+.2f} (rebuilt now "
                     f"{g['rebuilt_margin']:+.2f}); control reproduces served: {c.get('reproduces_served')}")
        rows = [c] + g["scenarios"]
        for r in rows:
            qbs = ", ".join(f"{t} {q['player']} {q['pass_att']:.0f} att {q['pass_yds']:.0f} yds"
                            for t, q in (r.get("sim_qbs") or {}).items())
            cap = "  (injury cap binds)" if r.get("injury_cap_binds") else ""
            lines.append(f"  {r['label']:<46} margin {r['baseline_margin']:+6.2f}{cap}  {g['home']} win "
                         f"{r['home_win_prob']:.0%}  p50 {r['margin_p50']:+.0f} / total {r['total_p50']:.0f}  | {qbs}")
            for m in r.get("props", [])[:5]:
                tag = " UNRELIABLE" if m["unreliable"] else ""
                d = "" if m["delta"] is None else f" ({m['delta'] * 100:+.0f} pp vs served)"
                lines.append(f"      {m['player']:<22} {m['label']:<10} {m['line']:>6}  sim P(over) {m['p_over']:.0%}{d}{tag}")
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="QB scenarios for games with an unresolved starter (P66).")
    ap.add_argument("--game")
    ap.add_argument("--sims", type=int)
    ap.add_argument("--publish", action="store_true", help="write data/scenarios.json and the dashboard copy")
    args = ap.parse_args()
    print(format_report(run(args.game, args.sims, args.publish)))
