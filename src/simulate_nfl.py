"""NFL game simulation: Monte Carlo on top of the prediction pipeline.

    python -m src.simulate_nfl --game 2026_01_DEN_KC             one game, printed and stored
    python -m src.simulate_nfl --game 2026_01_DEN_KC --no-store  printed only
    python -m src.simulate_nfl --date 2026-09-13                 every game on a slate
    python -m src.simulate_nfl --calibrate                       engine vs real NFL scoring

A build phase of its own, deliberately not wired into run_pipeline.py. Output
lands in `game_simulations`; the `predictions` table is never read or written.

How it sits on the existing pipeline
------------------------------------
The simulator does not produce a rival margin. Each game's features come from
the same FeatureContext the baseline uses, and the baseline's final margin
(power rating plus home field, rest, travel, injuries and wind) is the anchor:
a small symmetric EPA offset is solved so the simulated games average exactly
that margin. What the simulator adds is everything around the centre: the
spread of outcomes, the total, how the points arrive (touchdowns versus field
goals), and who is likely to score them.

Offence and defence are kept separate because the total depends on them
individually. Each side's expected EPA per play is its offensive rating plus
the opponent's defensive rating, with the injury report split by position: a
missing quarterback lowers his own offence, a missing cornerback raises the
opposing offence. Situational points are shared equally between the sides.
"""

from __future__ import annotations

import argparse
import zlib
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from . import config, db
from .box_score import BOX_CONFIDENCE, BOX_NOTE, POOL_CATEGORIES, box_score, player_pool, td_counts
from .features import FeatureContext, latest_injury_report, parse_dt
from .ingest_injuries import player_key
from .ingest_nflverse import PLAYS_PER_GAME
from .predict_baseline import predict_game, slate_window
from .sim_data import (
    USAGE_CATEGORIES, SimTables, build_tables, load_pbp, pass_rate_oe, player_roles,
)
from .simulate import (
    DRIVE_OUTCOMES, Offense, PlayerPool, SimResult, allocate_scorers, simulate_game, summarize,
)

SIM_VERSION = "sim-v1"
N_SIMS = 10_000
PILOT_SIMS = 4_000
PROBE_EPA = 0.04          # size of the offset used to measure margin per EPA

OFFENSE_POSITIONS = {"QB", "RB", "FB", "WR", "TE", "T", "OT", "LT", "RT",
                     "G", "OG", "LG", "RG", "C", "OL"}
SPECIAL_TEAMS = {"K", "P", "LS"}

TOP_SCORERS = 8
MIN_SCORER_PROB = 0.03
MIN_SHIFT_SHARE = 0.03    # injury shifts smaller than this aren't worth listing

TD_SCORER_CONFIDENCE = "low"
TD_SCORER_NOTE = (
    "Lower confidence than the score and TD/FG counts. Scorers are assigned from "
    "each player's historical red-zone target share and goal-line / red-zone carry "
    "share, with an injured player's share moved to the next man on the depth chart. "
    "It knows nothing about this week's game plan, snap limits or matchup-specific usage."
)


@dataclass
class SimInputs:
    """Loaded once per run and shared by every game on it."""

    tables: SimTables
    roles: pd.DataFrame
    depth_as_of: str
    proe: dict[str, float]


def load_inputs(season: int) -> SimInputs:
    tables = build_tables()
    pbp = load_pbp((season - 1, season))
    roles, as_of = player_roles(season, pbp)
    return SimInputs(tables, roles, as_of, pass_rate_oe(pbp, season))


# --- per-side strength -----------------------------------------------------

def injury_split(detail: list[dict], team_points: float) -> tuple[float, float]:
    """(offence cost, defence cost) in points, both >= 0.

    Scaled to the team's capped injury total so the split never charges more
    than the baseline did. Specialists are left out: kicking is drawn from the
    league table, so there is nothing of theirs to weaken.
    """
    raw = sum(d["points"] for d in detail)
    if raw <= 0:
        return 0.0, 0.0
    scale = abs(team_points) / raw
    pos = lambda d: (d.get("position") or "").upper()  # noqa: E731
    off = sum(d["points"] for d in detail if pos(d) in OFFENSE_POSITIONS)
    spec = sum(d["points"] for d in detail if pos(d) in SPECIAL_TEAMS)
    return off * scale, (raw - off - spec) * scale


def side_targets(features: dict, ctx: FeatureContext, league_epa: float) -> dict | None:
    """Expected EPA per play for each offence against this defence."""
    home, away = features["home_team"], features["away_team"]
    h, a = ctx.ratings.get(home) or {}, ctx.ratings.get(away) or {}
    if None in (h.get("off_epa"), h.get("def_epa"), a.get("off_epa"), a.get("def_epa")):
        return None
    rated = [r for r in ctx.ratings.values() if r.get("off_epa") is not None]
    league_off = float(np.mean([r["off_epa"] for r in rated]))
    league_def = float(np.mean([r["def_epa"] for r in rated]))

    situational = features["hfa"] + features["rest_adj"] + features["travel_adj"]
    h_off_inj, h_def_inj = injury_split(features["home_injury_detail"], features["home_injury_points"])
    a_off_inj, a_def_inj = injury_split(features["away_injury_detail"], features["away_injury_points"])

    def side(off_rating, opp_def, sit, own_off_inj, opp_def_inj):
        points = sit / 2 - own_off_inj + opp_def_inj
        return {
            "target_epa": league_epa + (off_rating - league_off) + (opp_def - league_def)
            + points / PLAYS_PER_GAME,
            "off_epa": off_rating, "opp_def_epa": opp_def,
            "situational_pts": round(sit / 2, 3),
            "own_offense_injury_pts": round(-own_off_inj, 3),
            "opp_defense_injury_pts": round(opp_def_inj, 3),
        }

    return {
        "home": side(h["off_epa"], a["def_epa"], situational, h_off_inj, a_def_inj),
        "away": side(a["off_epa"], h["def_epa"], -situational, a_off_inj, h_def_inj),
    }


def anchored_simulation(tables: SimTables, targets: dict, proe: tuple[float, float],
                        anchor: float, wind: float, n: int, seed: int, pools: tuple | None = None):
    """Solve the EPA offset that makes the simulated margin average `anchor`.

    Margin is close to linear in a small symmetric offset, so two pilot runs on
    common random numbers give the slope, and the full run uses the solved
    offset. Returns (result, offset, slope, unanchored pilot margin).
    """
    def run(delta, count, s, with_players=None):
        return simulate_game(
            tables,
            Offense(targets["home"]["target_epa"] + delta, proe[0]),
            Offense(targets["away"]["target_epa"] - delta, proe[1]),
            n=count, seed=s, wind_mph=wind, pools=with_players,
        )

    margin = lambda r: float((r.points[:, 0] - r.points[:, 1]).mean())  # noqa: E731
    m0 = margin(run(0.0, PILOT_SIMS, seed))
    m1 = margin(run(PROBE_EPA, PILOT_SIMS, seed))
    slope = (m1 - m0) / PROBE_EPA
    if slope <= 10:   # would mean the engine barely responds to strength; refuse to extrapolate
        raise RuntimeError(f"margin barely responds to EPA offset (slope {slope:.1f})")
    delta = (anchor - m0) / slope
    return run(delta, n, seed + 1, pools), delta, slope, m0


# --- scorers ---------------------------------------------------------------

def team_shares(roles: pd.DataFrame, team: str, injuries: list[dict]):
    """Depth-chart skill players and each one's share of every opportunity
    type, with injuries applied.

    Within a position, players are walked in depth order. An injured player
    keeps his share times his play probability; the rest passes to the next
    man down, who is himself subject to his own play probability. So a ruled
    out RB1's goal-line work goes to RB2 rather than being spread evenly
    across the whole backfield.
    """
    squad = roles[roles["team"] == team].sort_values(["position", "rank"]).reset_index(drop=True)
    report = {player_key(team, r["player"]): r for r in injuries if r.get("team") == team}
    cats = list(USAGE_CATEGORIES)
    base = squad[cats].to_numpy(float)
    eff = np.zeros_like(base)
    play_prob = np.ones(len(squad))
    shifts = []

    for _pos, idx in squad.groupby("position").groups.items():
        idx = sorted(idx, key=lambda i: squad.at[i, "rank"])
        carry = np.zeros(len(cats))
        for n, i in enumerate(idx):
            row = report.get(player_key(team, squad.at[i, "player"]))
            q = 1.0 if row is None else float(row.get("play_probability") or 0.0)
            total = base[i] + carry
            eff[i], carry = total * q, total * (1 - q)
            play_prob[i] = q
            moved = total * (1 - q)
            if q < 1 and (moved[0] + moved[2]) >= MIN_SHIFT_SHARE:
                nxt = squad.at[idx[n + 1], "player"] if n + 1 < len(idx) else None
                shifts.append({
                    "player": squad.at[i, "player"],
                    "position": f"{squad.at[i, 'position']}{squad.at[i, 'rank']}",
                    "status": row.get("status"),
                    "play_prob": round(q, 2),
                    "to": nxt,
                    "moved_target_share": round(float(moved[0]), 3),
                    "moved_carry_share": round(float(moved[2]), 3),
                })

    totals = eff.sum(axis=0)
    shares = {c: eff[:, k] / totals[k] if totals[k] > 0 else eff[:, k] for k, c in enumerate(cats)}
    squad["play_prob"] = play_prob
    return squad, shares, shifts


def scorer_table(result: SimResult, side: int, squad: pd.DataFrame,
                 shares: dict[str, np.ndarray], seed: int) -> list[dict]:
    # With players tracked, touchdowns are credited on the play itself, so
    # the scorer list and the projected box score always agree.
    counts = (td_counts(result.players[side]) if result.players is not None
              else allocate_scorers(result, side, shares, seed))
    anytime = (counts >= 1).mean(axis=0)
    out = []
    for i in np.argsort(-anytime)[:TOP_SCORERS]:
        if anytime[i] < MIN_SCORER_PROB:
            break
        entry = {
            "player": squad.at[i, "player"],
            "position": squad.at[i, "position"],
            "depth_rank": int(squad.at[i, "rank"]),
            "anytime_td": round(float(anytime[i]), 4),
            "two_plus_td": round(float((counts[:, i] >= 2).mean()), 4),
            "expected_tds": round(float(counts[:, i].mean()), 3),
            "rz_target_share": round(float(shares["tgt_rz"][i]), 3),
            "rz_carry_share": round(float(shares["car_rz"][i]), 3),
            "gl_carry_share": round(float(shares["car_gl"][i]), 3),
        }
        if squad.at[i, "play_prob"] < 1:
            entry["play_prob"] = round(float(squad.at[i, "play_prob"]), 2)
        out.append(entry)
    return out


# --- one game --------------------------------------------------------------

def simulate_one(game: dict, ctx: FeatureContext, inputs: SimInputs, n: int = N_SIMS,
                 anchor: float | None = None, anchor_label: str | None = None) -> dict | None:
    """Simulate one game. `anchor` overrides the margin the simulations are
    pinned to; the live tracker passes the stored pregame prediction, so a
    simulation built after kickoff still centres on the pregame number."""
    features = ctx.build(game)
    pred = predict_game(features)
    if pred is None:
        print(f"  [skip] {game['away_team']} @ {game['home_team']}: no power rating")
        return None
    tables = inputs.tables
    targets = side_targets(features, ctx, tables.league_epa)
    if targets is None:
        print(f"  [skip] {game['away_team']} @ {game['home_team']}: no offensive/defensive EPA split")
        return None

    home, away = game["home_team"], game["away_team"]
    proe = (inputs.proe.get(home, 0.0), inputs.proe.get(away, 0.0))
    wind = 0.0 if features["is_dome"] else float(features["wind_mph"] or 0.0)
    seed = zlib.crc32(game["game_id"].encode())
    anchor = pred["model_margin_home"] if anchor is None else float(anchor)

    squads = {team: team_shares(inputs.roles, team, ctx.injuries) for team in (home, away)}
    pools = tuple(player_pool(squads[t][0], squads[t][1]) for t in (home, away))
    result, delta, slope, unanchored = anchored_simulation(
        tables, targets, proe, anchor, wind, n, seed, pools
    )
    s = summarize(result)

    scorers, injury_shifts, boxes = {}, {}, {}
    for side, team in ((0, home), (1, away)):
        squad, shares, shifts = squads[team]
        scorers[team] = scorer_table(result, side, squad, shares, seed + 7 + side)
        injury_shifts[team] = shifts
        boxes[team] = box_score(result.players[side], squad)

    top = s["top_scores"][0]
    r3 = lambda x: round(float(x), 3)  # noqa: E731
    return {
        "game_id": game["game_id"],
        "sim_version": SIM_VERSION,
        "sport": "nfl",
        "home_team": home,
        "away_team": away,
        "n_sims": n,
        "modal_home_points": top["home"],
        "modal_away_points": top["away"],
        "modal_score_prob": top["prob"],
        "median_home_points": s["home_points"]["p50"],
        "median_away_points": s["away_points"]["p50"],
        "mean_home_points": r3(s["mean_home"]),
        "mean_away_points": r3(s["mean_away"]),
        "home_win_prob": r3(s["home_win"]),
        "tie_prob": r3(s["tie"]),
        "margin_50_low": s["margin"]["p25"], "margin_50_high": s["margin"]["p75"],
        "margin_80_low": s["margin"]["p10"], "margin_80_high": s["margin"]["p90"],
        "total_50_low": s["total"]["p25"], "total_50_high": s["total"]["p75"],
        "total_80_low": s["total"]["p10"], "total_80_high": s["total"]["p90"],
        "home_td_mode": s["td_mode"][0], "away_td_mode": s["td_mode"][1],
        "home_fg_mode": s["fg_mode"][0], "away_fg_mode": s["fg_mode"][1],
        "home_td_mean": r3(s["td_mean"][0]), "away_td_mean": r3(s["td_mean"][1]),
        "home_fg_mean": r3(s["fg_mean"][0]), "away_fg_mean": r3(s["fg_mean"][1]),
        "anchor_margin_home": anchor,
        "sim_margin_home": r3(s["mean_home"] - s["mean_away"]),
        "market_spread": features["market_spread"],
        "market_total": features["market_total"],
        # Score and TD/FG counts inherit the baseline's data-completeness tier;
        # scorers are always a tier below it, whatever the inputs.
        "score_confidence": pred["confidence"],
        "td_scorer_confidence": TD_SCORER_CONFIDENCE,
        "distributions": {
            "top_scores": s["top_scores"],
            "scores_tied_with_mode": s["scores_tied_with_mode"],
            "home_points": s["home_points"], "away_points": s["away_points"],
            "margin_home": s["margin"], "total": s["total"],
            "home_td": s["td"][0], "away_td": s["td"][1],
            "home_fg": s["fg"][0], "away_fg": s["fg"][1],
            "overtime_prob": r3(s["overtime"]),
            "pace": s["pace"],
            "away_win_prob": r3(s["away_win"]),
        },
        "td_scorers": {
            "confidence": TD_SCORER_CONFIDENCE,
            "note": TD_SCORER_NOTE,
            "depth_chart_as_of": inputs.depth_as_of,
            "home": scorers[home],
            "away": scorers[away],
            "return_td_prob": {home: r3(s["return_td"][0]), away: r3(s["return_td"][1])},
            "injury_shifts": injury_shifts,
        },
        "box_score": {"confidence": BOX_CONFIDENCE, "note": BOX_NOTE,
                      "home": boxes[home], "away": boxes[away]},
        "components": {
            "anchor": {
                "model": anchor_label or pred["model_version"],
                "margin_home": anchor,
                "unanchored_sim_margin": r3(unanchored),
                "offset_epa_per_play": round(delta, 5),
                "margin_per_epa": round(slope, 1),
            },
            "home_offense": {**{k: r3(v) for k, v in targets["home"].items()},
                             "target_epa": round(targets["home"]["target_epa"] + delta, 5),
                             "pass_rate_oe": r3(proe[0]), "tilt": round(result.tilt[0], 4)},
            "away_offense": {**{k: r3(v) for k, v in targets["away"].items()},
                             "target_epa": round(targets["away"]["target_epa"] - delta, 5),
                             "pass_rate_oe": r3(proe[1]), "tilt": round(result.tilt[1], 4)},
            "league_epa": round(tables.league_epa, 5),
            "wind_mph": wind,
            "possessions": [round(p, 2) for p in s["possessions"]],
            "tables": tables.meta,
        },
        "generated_at": db.utcnow(),
        "_kickoff": game.get("kickoff_time"),
        "_baseline_components": pred["components"],
    }


# --- report ----------------------------------------------------------------

def _pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def _by(margin_home: float, home: str, away: str) -> str:
    """A home-minus-away margin in words, so its sign can't be misread
    against a spread, whose sign convention is the opposite."""
    if abs(margin_home) < 0.05:
        return "pick'em"
    return f"{home if margin_home > 0 else away} by {abs(margin_home):.1f}"


def _dist(d: dict, cap: int = 5) -> str:
    keys = list(d)[:cap]
    return "  ".join(f"{k}:{d[k] * 100:>3.0f}%" for k in keys)


def format_report(row: dict) -> str:
    h, a = row["home_team"], row["away_team"]
    d, sc = row["distributions"], row["td_scorers"]
    kick = parse_dt(row.get("_kickoff"))
    comp = row["components"]
    market = row["market_spread"]
    lines = [
        "=" * 78,
        f"{a} @ {h}   kickoff {kick.strftime('%a %Y-%m-%d %H:%MZ') if kick else '?'}"
        f"   {row['n_sims']:,} simulations ({row['sim_version']})",
        "=" * 78,
        f"Pipeline {comp['anchor']['model']}: {_by(row['anchor_margin_home'], h, a)}"
        f"   -> simulations average {_by(row['sim_margin_home'], h, a)}"
        f"  (engine before anchoring: {_by(comp['anchor']['unanchored_sim_margin'], h, a)})",
        f"Market   {_by(-market, h, a)} (home line {market:+.1f}), total {row['market_total']}"
        if market is not None else "Market   no line",
        "",
        f"SCORE, TD & FG COUNTS  [confidence: {row['score_confidence']} - completeness of the pipeline inputs]",
        f"  Most likely exact    {a} {row['modal_away_points']} - {h} {row['modal_home_points']}"
        f"   ({row['modal_score_prob'] * 100:.1f}% of sims"
        + (f"; within sampling noise of the next {d['scores_tied_with_mode']})"
           if d["scores_tied_with_mode"] else ")"),
        f"  Next most likely     " + ",  ".join(
            f"{a} {t['away']}-{t['home']} ({t['prob'] * 100:.1f}%)" for t in d["top_scores"][1:4]),
        f"  Median               {a} {row['median_away_points']:.0f} - {h} {row['median_home_points']:.0f}",
        f"  Mean                 {a} {row['mean_away_points']:.1f} - {h} {row['mean_home_points']:.1f}",
        f"  Win probability      {h} {_pct(row['home_win_prob'])}   {a} {_pct(d['away_win_prob'])}"
        f"   tie {row['tie_prob'] * 100:.1f}%   (overtime {_pct(d['overtime_prob'])})",
        "",
        f"  {'range covering':22} {'50% of sims':>14} {'80% of sims':>14}",
    ]
    for label, q in ((f"{h} points", d["home_points"]), (f"{a} points", d["away_points"]),
                     (f"margin ({h})", d["margin_home"]), ("total", d["total"])):
        signed = label.startswith("margin")
        f = (lambda v: f"{v:+.0f}") if signed else (lambda v: f"{v:.0f}")
        lines.append(f"  {label:22} {f(q['p25']):>6} to {f(q['p75']):<5} {f(q['p10']):>6} to {f(q['p90']):<5}")
    lines += [
        "",
        f"  {'':10} {'most likely':>11} {'mean':>6}   distribution",
        f"  {h + ' TDs':10} {row['home_td_mode']:>11} {row['home_td_mean']:>6.2f}   {_dist(d['home_td'])}",
        f"  {a + ' TDs':10} {row['away_td_mode']:>11} {row['away_td_mean']:>6.2f}   {_dist(d['away_td'])}",
        f"  {h + ' FGs':10} {row['home_fg_mode']:>11} {row['home_fg_mean']:>6.2f}   {_dist(d['home_fg'])}",
        f"  {a + ' FGs':10} {row['away_fg_mode']:>11} {row['away_fg_mean']:>6.2f}   {_dist(d['away_fg'])}",
        "",
        "-" * 78,
        f"TD SCORERS  [confidence: {sc['confidence'].upper()} - lower than the score and TD/FG counts]",
        "-" * 78,
    ]
    import textwrap
    lines += ["  " + ln for ln in textwrap.wrap(sc["note"], 74)]
    lines.append(f"  Depth chart as of {sc['depth_chart_as_of']}.")
    for team, key in ((h, "home"), (a, "away")):
        lines.append("")
        lines.append(f"  {team:26} {'anytime':>8} {'2+':>5} {'exp':>5}   RZ tgt  RZ car  GL car")
        for p in sc[key]:
            name = f"{p['player']} ({p['position']}{p['depth_rank']})"
            flag = f"  [plays {p['play_prob']:.0%}]" if "play_prob" in p else ""
            lines.append(
                f"  {name:26} {_pct(p['anytime_td']):>8} {_pct(p['two_plus_td']):>5} "
                f"{p['expected_tds']:>5.2f}   {_pct(p['rz_target_share']):>6} "
                f"{_pct(p['rz_carry_share']):>7} {_pct(p['gl_carry_share']):>7}{flag}"
            )
        lines.append(f"  {'defence / return TD (team)':26} {_pct(sc['return_td_prob'][team]):>8}")
        for sh in sc["injury_shifts"][team]:
            lines.append(
                f"  injury: {sh['player']} ({sh['position']}, {sh['status'] or 'on report'}, "
                f"{sh['play_prob']:.0%} to play) -> {sh['to'] or 'rest of group'} "
                f"(+{sh['moved_target_share']:.0%} targets, +{sh['moved_carry_share']:.0%} carries)"
            )
    box = row.get("box_score")
    if box:
        r0 = lambda q: f"{q['median']:.0f} ({q['p25']:.0f}-{q['p75']:.0f})"  # noqa: E731
        lines += ["", "-" * 78,
                  f"PROJECTED BOX SCORE  [confidence: {box['confidence'].upper()} - player lines, below the score]",
                  "-" * 78, "  median (middle 50% of simulations)"]
        for team, key in ((a, "away"), (h, "home")):
            b = box[key]
            lines.append(f"  {team}: pass yds {r0(b['team']['pass_yds'])}, rush yds {r0(b['team']['rush_yds'])}")
            for p in b["players"][:9]:
                parts = []
                if "passing" in p:
                    ps = p["passing"]
                    parts.append(f"{ps['cmp']['median']:.0f}/{ps['att']['median']:.0f}, {r0(ps['yds'])} pass yds")
                if "rushing" in p:
                    parts.append(f"{p['rushing']['att']['median']:.0f} car, {r0(p['rushing']['yds'])} rush yds")
                if "receiving" in p:
                    rc = p["receiving"]
                    parts.append(f"{rc['rec']['median']:.0f}/{rc['tgt']['median']:.0f} rec, {r0(rc['yds'])} rec yds")
                name = f"{p['player']} ({p['position'] or '?'}{p['depth_rank'] or ''})"
                lines.append(f"    {name:28} " + " | ".join(parts))
    ho, ao = comp["home_offense"], comp["away_offense"]
    lines += [
        "",
        "-" * 78,
        "Inputs (EPA per play, points)",
        f"  {h} offence  target {ho['target_epa']:+.4f}  | off {ho['off_epa']:+.4f}  vs {a} def "
        f"{ho['opp_def_epa']:+.4f} | situational {ho['situational_pts']:+.2f}  own inj "
        f"{ho['own_offense_injury_pts']:+.2f}  opp def inj {ho['opp_defense_injury_pts']:+.2f} | "
        f"PROE {ho['pass_rate_oe']:+.1%}",
        f"  {a} offence  target {ao['target_epa']:+.4f}  | off {ao['off_epa']:+.4f}  vs {h} def "
        f"{ao['opp_def_epa']:+.4f} | situational {ao['situational_pts']:+.2f}  own inj "
        f"{ao['own_offense_injury_pts']:+.2f}  opp def inj {ao['opp_defense_injury_pts']:+.2f} | "
        f"PROE {ao['pass_rate_oe']:+.1%}",
        f"  anchor offset {comp['anchor']['offset_epa_per_play']:+.4f} EPA/play "
        f"({comp['anchor']['margin_per_epa']:.0f} pts of margin per 1.0)  | wind {comp['wind_mph']:.0f} mph"
        f"  | possessions {comp['possessions'][0]:.1f} / {comp['possessions'][1]:.1f}",
    ]
    return "\n".join(lines)


# --- engine calibration ----------------------------------------------------

def calibrate(n: int = 20_000, game_script: bool = True) -> str:
    """Two league-average teams on a neutral field, against what real NFL
    teams actually scored over the library seasons. Nothing is anchored here,
    so this is the honest test of whether the engine's scoring is realistic."""
    import nfl_data_py as nfl

    from .sim_data import POOL_SEASONS

    tables = build_tables()
    avg = Offense(tables.league_epa)
    # Team box-score totals don't depend on how usage is split, so a generic
    # three-man pool is enough to check them.
    pool = PlayerPool(names=["QB", "RB", "WR"],
                      cum={c: np.cumsum([0.1, 0.6, 0.3]) for c in POOL_CATEGORIES},
                      passer_weights=np.array([1.0, 0.0, 0.0]))
    r = simulate_game(tables, avg, avg, n=n, seed=1, pools=(pool, pool),
                      game_script=game_script, track_drives=True)
    s = summarize(r)
    pbp = load_pbp(POOL_SEASONS)
    games = pbp["game_id"].nunique()
    real_td = float(((pbp["touchdown"] == 1) & pbp["td_team"].notna()).sum()) / (2 * games)
    real_fg = float((pbp["field_goal_result"] == "made").sum()) / (2 * games)
    sched = nfl.import_schedules(list(POOL_SEASONS)).dropna(subset=["home_score"])
    hs, as_ = sched["home_score"], sched["away_score"]
    # Real games are between unequal teams, so their margin spread includes
    # the spread of team quality; two identical sim teams should come in under
    # it. The total's spread has no such excuse and should match.
    rows = [
        ("points / team", (s["mean_home"] + s["mean_away"]) / 2, float(pd.concat([hs, as_]).mean())),
        ("TDs / team", float(np.mean(s["td_mean"])), real_td),
        ("FGs / team", float(np.mean(s["fg_mean"])), real_fg),
        ("total sd", float(r.points.sum(axis=1).std()), float((hs + as_).std())),
        ("margin sd", float((r.points[:, 0] - r.points[:, 1]).std()), float((hs - as_).std())),
        ("overtime rate", s["overtime"], float((sched["overtime"] == 1).mean())),
        ("tie rate", s["tie"], float((hs == as_).mean())),
    ]
    # Box-score totals per team-game. A pass attempt excludes sacks and
    # scrambles; a rush attempt includes scrambles, as nflverse records them.
    snaps = pbp[pbp["play_type"].isin(["pass", "run"]) & (pbp["two_point_attempt"] != 1)]
    team_games = snaps[["game_id", "posteam"]].drop_duplicates().shape[0]
    att = snaps[(snaps["pass_attempt"] == 1) & (snaps["sack"] != 1)]
    rush = snaps[snaps["rush_attempt"] == 1]
    real = {
        "pass_att": len(att), "pass_cmp": att["complete_pass"].sum(),
        "pass_yds": att.loc[att["complete_pass"] == 1, "yards_gained"].sum(),
        "rush_att": len(rush), "rush_yds": rush["yards_gained"].sum(),
    }
    for key, total in real.items():
        sim = float(np.mean([side[key].sum(axis=1).mean() for side in r.players]))
        rows.append((f"{key} / team", sim, float(total) / team_games))
    out = [f"League-average vs league-average, {n:,} sims, vs {list(POOL_SEASONS)} actuals ({len(sched)} games)",
           f"  {'':16} {'sim':>8} {'real':>8}"]
    out += [f"  {k:16} {a:>8.3f} {b:>8.3f}" for k, a, b in rows]
    out.append(f"  sim possessions/team {np.mean(s['possessions']):.2f}")
    out.append(f"  game script {'on' if game_script else 'off'}")
    out.append(volume_by_margin(r, pbp, sched))
    out.append(drive_report(r, pbp))
    return "\n".join(out)


def real_drive_outcomes(pbp: pd.DataFrame) -> pd.DataFrame:
    """Every real drive's end reason and snap count, labelled the way the
    engine now labels its own, so the two distributions are comparable.

    Derived from play-by-play rather than written down as constants: the point
    of the diagnostic is to keep being true after the library seasons roll.
    """
    g = pbp[pbp["posteam"].notna() & pbp["fixed_drive"].notna()].copy()
    if "season_type" in g.columns:
        g = g[g["season_type"] == "REG"]
    play_type = g["play_type"].astype(str)
    g["scrim"] = (((g["pass_attempt"] == 1) & (g["sack"] != 1)).astype(int)
                  + (g["sack"] == 1).astype(int)
                  + (g["rush_attempt"] == 1).astype(int))
    g["is_punt"] = (play_type == "punt").astype(int)
    last = lambda s: s.dropna().iloc[-1] if s.notna().any() else None  # noqa: E731
    d = g.groupby(["game_id", "posteam", "fixed_drive"]).agg(
        plays=("scrim", "sum"), td=("touchdown", "max"), td_team=("td_team", "last"),
        fg=("field_goal_result", last), punt=("is_punt", "max"),
        intc=("interception", "max"), fum=("fumble_lost", "max"),
        saf=("safety", "max"), last_down=("down", "last"),
    ).reset_index()

    def label(row) -> str:
        if row.punt:
            return "punt"
        if row.fg == "made":
            return "FG made"
        if row.fg in ("missed", "blocked"):
            return "FG miss"
        if row.td == 1:
            return "TD" if row.td_team == row.posteam else "def TD"
        if row.intc == 1 or row.fum == 1:
            return "turnover"
        if row.saf == 1:
            return "safety"
        if row.last_down == 4:
            return "downs"
        return "end of half/game"

    d["outcome"] = d.apply(label, axis=1)
    return d[d["plays"] > 0]


def drive_report(r: SimResult, pbp: pd.DataFrame) -> str:
    """How simulated drives end, against how real ones do.

    The engine can match points per team and still be wrong here, which is
    what the 2026-09-16 diagnostic found: it ran more possessions of fewer
    plays each, and that is where the pass-attempt shortfall comes from. A
    rush happens on early downs whatever else is true, while pass attempts
    need drives that keep going.
    """
    if not r.drives:
        return "  drive tracking off"
    counts = np.asarray(r.drives["counts"], dtype=float)
    plays = np.asarray(r.drives["plays"], dtype=float)
    total = counts.sum()
    if not total:
        return "  no drives tracked"

    real = real_drive_outcomes(pbp)
    real_share = real["outcome"].value_counts(normalize=True)
    real_plays = real.groupby("outcome")["plays"].mean()

    out = ["", f"  {'drive outcome':18} {'sim':>7} {'real':>7}   {'sim p/d':>8} {'real p/d':>9}"]
    for i, name in enumerate(DRIVE_OUTCOMES):
        share = counts[i] / total
        per = plays[i] / counts[i] if counts[i] else float("nan")
        out.append(f"  {name:18} {share:>7.3f} {real_share.get(name, 0.0):>7.3f}   "
                   f"{per:>8.2f} {real_plays.get(name, float('nan')):>9.2f}")
    out.append(f"  {'ALL':18} {1.0:>7.3f} {1.0:>7.3f}   "
               f"{plays.sum() / total:>8.2f} {real['plays'].mean():>9.2f}")
    sim_per_team = total / (2 * len(r.points))
    real_per_team = len(real) / real.groupby(["game_id", "posteam"]).ngroups
    out.append(f"  drives / team-game   sim {sim_per_team:.2f}   real {real_per_team:.2f}")
    return "\n".join(out)


MARGIN_BANDS = [-14.5, -7.5, 7.5, 14.5]
MARGIN_LABELS = ("lost by 15+", "lost by 8-14", "within 7", "won by 8-14", "won by 15+")


def volume_by_margin(r, pbp: pd.DataFrame, sched: pd.DataFrame) -> str:
    """Team rush and pass attempts by how the game finished for that team.

    The engine can match league totals and still get this flat, which is the
    game-script miss behind P11: a team that leads runs the ball, and one that
    trails throws it. Real games are between unequal teams, so the real
    column carries some team quality too; the slope across bands is the check.
    """
    sim_margin = np.concatenate([r.points[:, 0] - r.points[:, 1], r.points[:, 1] - r.points[:, 0]])
    sim = {k: np.concatenate([r.players[0][k].sum(axis=1), r.players[1][k].sum(axis=1)])
           for k in ("rush_att", "pass_att")}
    snaps = pbp[pbp["play_type"].isin(["pass", "run"]) & (pbp["two_point_attempt"] != 1)]
    tg = pd.DataFrame({
        "game_id": snaps["game_id"].astype(str), "team": snaps["posteam"].astype(str),
        "rush_att": (snaps["rush_attempt"] == 1).astype(int),
        "pass_att": ((snaps["pass_attempt"] == 1) & (snaps["sack"] != 1)).astype(int),
    }).groupby(["game_id", "team"], as_index=False)[["rush_att", "pass_att"]].sum()
    tg = tg.merge(sched[["game_id", "home_team", "home_score", "away_score"]].astype({"game_id": str}),
                  on="game_id")
    diff = (tg["home_score"] - tg["away_score"]).to_numpy()
    real_margin = np.where(tg["team"].to_numpy() == tg["home_team"].to_numpy(), diff, -diff)
    rush, passes = tg["rush_att"].to_numpy(), tg["pass_att"].to_numpy()
    sb, rb = np.digitize(sim_margin, MARGIN_BANDS), np.digitize(real_margin, MARGIN_BANDS)
    lines = ["  team volume by final margin   rush att sim / real   pass att sim / real   games sim / real"]
    for i, label in enumerate(MARGIN_LABELS):
        s, q = sb == i, rb == i
        if not s.any() or not q.any():
            continue
        lines.append(f"    {label:<14} {sim['rush_att'][s].mean():>10.1f} / {rush[q].mean():<5.1f}"
                     f" {sim['pass_att'][s].mean():>12.1f} / {passes[q].mean():<5.1f}"
                     f" {s.mean():>11.1%} / {q.mean():.1%}")
    return "\n".join(lines)


# --- entrypoint ------------------------------------------------------------

def _stored_anchors(store, games: list[dict]) -> dict[str, tuple[float, str]]:
    """The stored baseline margin for each game, when it was made before
    kickoff. A game simulated after it started still centres on the number
    the pipeline published beforehand, not one rebuilt from later data."""
    out = {}
    try:
        rows = store.select("predictions", {"game_id": [g["game_id"] for g in games]})
    except Exception:  # noqa: BLE001
        return out
    kickoffs = {g["game_id"]: parse_dt(g.get("kickoff_time")) for g in games}
    for p in rows:
        made, kick = parse_dt(p.get("generated_at")), kickoffs.get(p["game_id"])
        if (p.get("model_version") == config.MODEL_VERSION and p.get("model_margin_home") is not None
                and made and kick and made <= kick):
            out[p["game_id"]] = (float(p["model_margin_home"]), f"{config.MODEL_VERSION} @ {p['generated_at']}")
    return out


def run(game_id: str | None = None, dates: list[date] | None = None, n: int = N_SIMS,
        store_results: bool = True, quiet: bool = False) -> list[dict]:
    store = db.get_store()
    ctx = FeatureContext(store, "nfl")
    if game_id:
        games = [g for g in ctx.games if g["game_id"] == game_id]
        if not games:
            raise SystemExit(f"no NFL game {game_id!r} in the games table")
    else:
        games = []
        for target in dates or []:
            start, end = slate_window(target)
            games += [g for g in ctx.games if (k := parse_dt(g.get("kickoff_time"))) and start <= k < end]
        games.sort(key=lambda g: g["kickoff_time"])
        if not games:
            raise SystemExit(f"no NFL games on {', '.join(map(str, dates or []))}")

    print(f"[simulate] {len(games)} game(s), {n:,} sims each | loading tables, usage and depth charts")
    inputs = load_inputs(int(games[0]["season"]))
    anchors = _stored_anchors(store, games)

    rows = []
    for game in games:
        margin, label = anchors.get(game["game_id"], (None, None))
        row = simulate_one(game, ctx, inputs, n, anchor=margin, anchor_label=label)
        if row is None:
            continue
        if quiet:
            print(f"  {game['away_team']} @ {game['home_team']}: simulated")
        else:
            print()
            print(format_report(row))
        rows.append(row)

    if store_results and rows:
        clean = [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]
        try:
            store.upsert("game_simulations", clean)
            print(f"\n[simulate] {len(clean)} row(s) written to game_simulations ({store.backend})")
        except Exception as exc:  # noqa: BLE001
            if store.backend == "sqlite":
                print(f"\n[simulate] could not write game_simulations: {exc}")
            else:
                print(f"\n[simulate] game_simulations is missing from {store.backend} "
                      f"({type(exc).__name__}); writing to the local SQLite mirror instead.")
                print("  Paste db/PASTE_INTO_SUPABASE.sql into the Supabase SQL Editor to create it.")
                local = db.SqliteStore()
                local.upsert("game_simulations", clean)
                local.close()
                print(f"[simulate] {len(clean)} row(s) written to game_simulations (local sqlite)")
    store.close()
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monte Carlo NFL game simulation.")
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--game", help="one game_id, e.g. 2026_01_DEN_KC")
    which.add_argument("--date", nargs="+", help="every game on these slate dates, YYYY-MM-DD")
    which.add_argument("--calibrate", action="store_true", help="engine vs real NFL scoring")
    parser.add_argument("--sims", type=int, default=N_SIMS)
    parser.add_argument("--no-store", action="store_true", help="print only, write nothing")
    parser.add_argument("--quiet", action="store_true", help="one line per game instead of the full report")
    parser.add_argument("--no-script", action="store_true",
                        help="with --calibrate: game script off, for a before/after")
    args = parser.parse_args()

    if args.calibrate:
        print(calibrate(game_script=not args.no_script))
    else:
        run(args.game, [date.fromisoformat(d) for d in args.date] if args.date else None,
            args.sims, store_results=not args.no_store, quiet=args.quiet)
