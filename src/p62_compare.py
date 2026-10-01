"""P62 Phase 1 measurement: criteria S1-S5 over every saved shadow pull. Read-only.

    python -m src.p62_compare --since 2026-10-04T00:00Z            # report to stdout
    python -m src.p62_compare --since ... --out calibration/p62/report.md
    python -m src.p62_compare --no-grade                           # skip S5 (no ESPN calls)
    python -m src.p62_compare --export                             # S8(c): the props-page JSON

Reads data/props_sr/pulls/<stamp>/ (odds.json, sr.json, holdouts.json and the
first rank_*/sims.json after the pull) and the shadow manifest. Writes nothing
but the report, or with --export the props-page section's JSON (S8(c): built
over the validation window from saved files only, no ESPN call, so S5 is
reported as not graded there). Criteria as confirmed 2026-09-30 (calibration-log.md, 'P62
Phase 1 criteria confirmed'); each is reported PASS / FAIL / STOP, or
UNMEASURED with the reason, never silently skipped.

Pairs: a game counts only where the Sportradar game was pulled in this shadow
run and within PAIR_MINUTES of the Odds API game's own pull; others are listed
as excluded. Both files are restricted to the paired games before ranking, so
a carried-forward game on either side cannot show up as a difference.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

from . import config, market
from .ingest_injuries import player_key
from .props import NAME_MATCH, TOP_N, match_player, pnorm, rank
from .shadow_props_sr import OUT_DIR

PAIR_MINUTES = 10.0
GAP_MINUTES = 5.0
S1_COVERAGE = 0.98
S3_TOTAL_BAR = 0.95
S3_P_BAR = 0.95
S3_P_TOL = 0.02
MOVE_REPORT = 5
# Validation window (calibration-log.md, P62 row: weeks 4 and 5).
WINDOW_START = "2026-10-01T03:22Z"
WINDOW_END = "2026-10-15T03:22Z"
PUBLIC_P62_JSON = config.ROOT / "dashboard" / "public" / "p62_compare.json"
DIFF_ROWS = 400   # line differences carried into the page JSON; the count is always full
ACTUAL_KEY = {"player_pass_yds": "pass_yds", "player_rush_yds": "rush_yds",
              "player_reception_yds": "rec_yds", "player_receptions": "rec"}


def _parse(ts) -> datetime | None:
    if not ts:
        return None
    dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@dataclass
class Pull:
    stamp: str
    at: datetime
    odds: dict
    sr: dict
    holdouts: dict | None
    sims: dict | None
    games: list[str] = field(default_factory=list)          # paired games
    excluded: dict[str, str] = field(default_factory=dict)  # game -> reason
    minutes: dict[str, float] = field(default_factory=dict)

    def lines(self, which: str) -> dict:
        src = self.odds if which == "odds" else self.sr
        return {**{k: v for k, v in src.items() if k != "games"},
                "games": {g: src["games"][g] for g in self.games}}


def load_pulls(out: Path = OUT_DIR, since: datetime | None = None, until: datetime | None = None) -> list[Pull]:
    pulls = []
    for d in sorted((out / "pulls").glob("*")) if (out / "pulls").exists() else []:
        if not (d / "odds.json").exists() or not (d / "sr.json").exists():
            continue
        at = datetime.strptime(d.name, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        if (since and at < since) or (until and at > until):
            continue
        odds = json.loads((d / "odds.json").read_text(encoding="utf-8"))
        sr = json.loads((d / "sr.json").read_text(encoding="utf-8"))
        holds = json.loads((d / "holdouts.json").read_text(encoding="utf-8")) if (d / "holdouts.json").exists() else None
        ranks = sorted(d.glob("rank_*/sims.json"))
        sims = json.loads(ranks[0].read_text(encoding="utf-8")) if ranks else None
        p = Pull(d.name, at, odds, sr, holds, sims)
        for gid, g in (sr.get("games") or {}).items():
            if g.get("pulled_at") != sr.get("pulled_at"):
                continue   # carried from an earlier shadow pull
            og = (odds.get("games") or {}).get(gid)
            if og is None:
                p.excluded[gid] = "not in the paired Odds API file"
                continue
            mins = (_parse(g["pulled_at"]) - _parse(og.get("pulled_at") or odds.get("pulled_at"))).total_seconds() / 60
            p.minutes[gid] = round(mins, 1)
            if 0 <= mins <= PAIR_MINUTES:
                p.games.append(gid)
            else:
                p.excluded[gid] = f"{mins:.1f} min after the Odds API pull (> {PAIR_MINUTES:g})"
        pulls.append(p)
    return pulls


def manifest_rows(out: Path = OUT_DIR) -> list[dict]:
    path = out / "manifest.csv"
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# --- S1 coverage -------------------------------------------------------------

def coverage(p: Pull, top_keys: set | None) -> dict:
    """Every Odds API game x market x player entry: covered, absent or misnamed."""
    entries, misses = 0, []
    for gid in p.games:
        o = p.odds["games"][gid]["players"]
        s = p.sr["games"][gid]["players"]
        s_norm = {pnorm(n): n for n in s}
        for name, mk in o.items():
            for m, books in mk.items():
                entries += 1
                sname = s_norm.get(pnorm(name))
                if sname is not None and m in s[sname]:
                    continue
                if sname is not None:
                    kind = "absent"   # the player is there, the market is not
                else:
                    # A word-order swap ("Rodgers Aaron", an unconverted "Last, First")
                    # scores low on the ratio but is a name failure, not coverage.
                    tokens = sorted(pnorm(name).split())
                    swapped = next((x for x in s if sorted(pnorm(x).split()) == tokens), None)
                    best = max(s, key=lambda x: SequenceMatcher(None, pnorm(x), pnorm(name)).ratio(), default=None)
                    ratio = SequenceMatcher(None, pnorm(best), pnorm(name)).ratio() if best else 0.0
                    # A nickname / legal-name pair ("Cam" / "Cameron Ward", "Woody" /
                    # "Jo'Quavious Marks") shares only the last name. Counted as a name
                    # failure (user ruling 10/1) when exactly one Sportradar player in the
                    # game has that last name and no Odds API player already claims him.
                    claimed = {s_norm[k] for k in (pnorm(x) for x in o) if k in s_norm}
                    last = pnorm(name).split(" ")[-1] if pnorm(name) else ""
                    same_last = [x for x in s if x not in claimed and pnorm(x).split(" ")[-1] == last]
                    if swapped is not None:
                        kind = f"misnamed (as {swapped!r}, word order)"
                    elif ratio >= NAME_MATCH:
                        kind = f"misnamed (as {best!r}, {ratio:.2f})"
                    elif len(same_last) == 1:
                        kind = f"misnamed (as {same_last[0]!r}, same last name)"
                    else:
                        kind = "absent"
                misses.append({"pull": p.stamp, "game": gid, "player": name, "market": m, "kind": kind,
                               "books": sorted(books), "in_top": bool(top_keys and (gid, name, m) in top_keys)})
    return {"entries": entries, "misses": misses}


# --- S2 names and identity -----------------------------------------------------

def priced_qbs(lines: dict, gid: str) -> set[str]:
    """The set P49 / P53 / P51 build: names with a pass-yds line, by player_key."""
    players = ((lines.get("games") or {}).get(gid) or {}).get("players") or {}
    return {player_key("", n)[1] for n, m in players.items() if "player_pass_yds" in m}


def names(p: Pull, misnamed: list[dict]) -> list[str]:
    fails = [f"{p.stamp} {m['game']} {m['player']} {m['market']}: {m['kind']}" for m in misnamed]
    # (b) same sim player through props.match_player
    if p.sims is not None:
        for gid in p.games:
            box = (p.sims.get(gid) or {}).get("box_score") or {}
            players = [(side, x) for side in ("home", "away") for x in (box.get(side) or {}).get("players") or []]
            if not players:
                continue
            s_norm = {pnorm(n): n for n in p.sr["games"][gid]["players"]}
            for oname in p.odds["games"][gid]["players"]:
                sname = s_norm.get(pnorm(oname))
                if sname is None:
                    continue
                a, b = match_player(oname, players), match_player(sname, players)
                ka = a and (a[0], a[1]["player"])
                kb = b and (b[0], b[1]["player"])
                if ka != kb:
                    fails.append(f"{p.stamp} {gid} {oname!r} -> {ka} but Sportradar {sname!r} -> {kb}")
    # (c) priced-QB sets
    for gid in p.games:
        a, b = priced_qbs(p.odds, gid), priced_qbs(p.sr, gid)
        if a != b:
            fails.append(f"{p.stamp} {gid} priced QBs differ: Odds API {sorted(a)} vs Sportradar {sorted(b)}")
    # (d) hold tables, exact names as the lookups use them
    if p.holdouts is not None:
        for gid, name, m in p.holdouts.get("prop_holdouts", []):
            if gid not in p.games:
                continue
            a = m in (p.odds["games"][gid]["players"].get(name) or {})
            b = m in (p.sr["games"][gid]["players"].get(name) or {})
            if a != b:
                fails.append(f"{p.stamp} PROP_HOLDOUTS ({gid}, {name!r}, {m}) resolves in Odds API={a}, Sportradar={b}")
        for gid, key in p.holdouts.get("known_defects", []):
            if gid not in p.games or str(key).startswith("team:"):
                continue
            a, b = key in p.odds["games"][gid]["players"], key in p.sr["games"][gid]["players"]
            if a != b:
                fails.append(f"{p.stamp} KNOWN_DEFECTS ({gid}, {key!r}) resolves in Odds API={a}, Sportradar={b}")
    return fails


# --- S3 lines ----------------------------------------------------------------

def _p_over(v: dict) -> float | None:
    if v.get("over") is None or v.get("under") is None:
        return None
    return market.devig([v["over"], v["under"]])[0]


def line_diffs(p: Pull, prev: Pull | None) -> tuple[int, int, int, int, list[dict]]:
    """(book entries compared, totals equal, P(over) compared, P(over) within tol, differences)."""
    n = same = pn = pok = 0
    diffs = []
    for gid in p.games:
        o = p.odds["games"][gid]["players"]
        s = p.sr["games"][gid]["players"]
        s_norm = {pnorm(x): x for x in s}
        po = ((prev.odds.get("games") or {}).get(gid) or {}).get("players") or {} if prev else {}
        ps = ((prev.sr.get("games") or {}).get(gid) or {}).get("players") or {} if prev else {}
        po_norm = {pnorm(x): x for x in po}
        ps_norm = {pnorm(x): x for x in ps}
        for name, mk in o.items():
            sname = s_norm.get(pnorm(name))
            if sname is None:
                continue
            for m, books in mk.items():
                for book, ov in books.items():
                    sv = (s[sname].get(m) or {}).get(book)
                    if sv is None:
                        continue
                    n += 1
                    pa, pb = _p_over(ov), _p_over(sv)
                    total_eq = ov.get("point") == sv.get("point")
                    same += total_eq
                    p_ok = None
                    if total_eq and pa is not None and pb is not None:
                        pn += 1
                        p_ok = abs(pa - pb) <= S3_P_TOL
                        pok += p_ok
                    if total_eq and p_ok is not False:
                        continue
                    prev_o = ((po.get(po_norm.get(pnorm(name), "")) or {}).get(m) or {}).get(book)
                    prev_s = ((ps.get(ps_norm.get(pnorm(name), "")) or {}).get(m) or {}).get(book)
                    if (prev_o and prev_o == sv) or (prev_s and prev_s == ov):
                        tag = "lag"
                    elif p.minutes.get(gid, 0) > GAP_MINUTES:
                        tag = "gap"
                    else:
                        tag = "unexplained"
                    diffs.append({"pull": p.stamp, "game": gid, "player": name, "market": m, "book": book,
                                  "odds": ov, "sr": sv, "minutes": p.minutes.get(gid), "tag": tag,
                                  "kind": "total" if not total_eq else "price"})
    return n, same, pn, pok, diffs


# --- S4 ranking --------------------------------------------------------------

def _key(r: dict) -> tuple:
    return (r["game_id"], r["player"], r["market"])


def _status(result: dict) -> dict:
    """key -> (rank or None, pick) over ranked rows; top-N membership by rank."""
    return {_key(r): (r["rank"], r["pick"]) for r in result["ranked"]}


def _restrict_to_shared(sr: dict, odds: dict) -> tuple[dict, dict]:
    """Both files cut to the books both carry, per player-market (user ruling
    10/1: restricting only Sportradar cannot remove a change caused by a book
    only the Odds API carries, e.g. BetOnline or Bovada)."""
    a, b = json.loads(json.dumps(odds)), json.loads(json.dumps(sr))
    for gid in a["games"]:
        oa, ob = a["games"][gid]["players"], b["games"][gid]["players"]
        ob_norm = {pnorm(x): x for x in ob}
        for name, mk in oa.items():
            sname = ob_norm.get(pnorm(name))
            for m in list(mk):
                other = (ob.get(sname) or {}).get(m) or {}
                shared = set(mk[m]) & set(other)
                mk[m] = {k: v for k, v in mk[m].items() if k in shared}
                if sname is not None and m in ob[sname]:
                    ob[sname][m] = {k: v for k, v in ob[sname][m].items() if k in shared}
        claimed = {ob_norm.get(pnorm(n)) for n in oa}
        for sname, mk in ob.items():
            if sname not in claimed:
                for m in mk:
                    mk[m] = {}   # no Odds API counterpart: nothing shared
    return a, b


def _where(result: dict) -> dict:
    """key -> (state, row) over every priced prop: 'ranked', 'held: gap',
    'held: structural' or 'started'. A key missing here was never priced."""
    out = {_key(r): ("started", r) for r in result["started"]}
    out.update({_key(r): (f"held: {r['held_reason']}", r) for r in result["held_out"]})
    out.update({_key(r): ("ranked", r) for r in result["ranked"]})
    return out


def ranking(p: Pull, line_keys: set, absent_keys: set) -> dict | None:
    if p.sims is None or not p.games:
        return None
    a, b = rank(p.lines("odds"), p.sims, now=p.at), rank(p.lines("sr"), p.sims, now=p.at)
    ra, rb = _restrict_to_shared(p.lines("sr"), p.lines("odds"))
    ra_, rb_ = _status(rank(ra, p.sims, now=p.at)), _status(rank(rb, p.sims, now=p.at))
    sa, sb = _status(a), _status(b)
    top = lambda st, k: k in st and st[k][0] <= TOP_N   # noqa: E731
    changes, moves = [], []
    # odds-name lookup for attribution: key -> odds name
    odds_name = {_key(r): r["odds_name"] for r in a["ranked"] + a["held_out"]}
    sr_name = {_key(r): r["odds_name"] for r in b["ranked"] + b["held_out"]}
    where_a, where_b = _where(a), _where(b)
    for k in set(sa) | set(sb):
        kinds = []
        if top(sa, k) != top(sb, k):
            kinds.append("enters" if top(sb, k) else "leaves")
        if k in sa and k in sb and sa[k][1] != sb[k][1]:
            kinds.append("flips")
        if top(sa, k) and top(sb, k) and abs(sa[k][0] - sb[k][0]) >= MOVE_REPORT:
            moves.append({"pull": p.stamp, "key": k, "odds_rank": sa[k][0], "sr_rank": sb[k][0]})
        if not kinds:
            continue
        name = odds_name.get(k) or sr_name.get(k) or k[1]
        same_top = top(ra_, k) == top(rb_, k)
        same_pick = k not in ra_ or k not in rb_ or ra_[k][1] == rb_[k][1]
        if same_top and same_pick:
            cause = "book mix"   # the change disappears on the books both carry
        elif (k[0], pnorm(name), k[2]) in line_keys:
            cause = "line"
        elif (k[0], pnorm(name), k[2]) in absent_keys:
            cause = "coverage"
        else:
            cause = "unexplained"
        wa, wb = where_a.get(k, ("not priced", {})), where_b.get(k, ("not priced", {}))
        ref = wa[1] or wb[1]
        changes.append({"pull": p.stamp, "key": k, "kinds": kinds, "cause": cause,
                        "odds": sa.get(k), "sr": sb.get(k),
                        # Held-out and started props keep their line and side,
                        # so the page can say where a prop went, not just that it left.
                        "odds_state": wa[0], "sr_state": wb[0],
                        "odds_line": wa[1].get("line"), "sr_line": wb[1].get("line"),
                        "odds_side": wa[1].get("pick"), "sr_side": wb[1].get("pick"),
                        "label": ref.get("label"), "team": ref.get("team"), "game": ref.get("game")})
    return {"changes": changes, "moves": moves, "odds_rank": a, "sr_rank": b}


# --- S5 record ---------------------------------------------------------------

def _actual(game: dict) -> dict | None:
    from .export_sims import _espn_day, actual_result, slate_day

    try:
        state = _espn_day(slate_day(game["kickoff"])).get((game["home"], game["away"]))
        if state is None or state.state != "post":
            return None
        return actual_result(state)
    except Exception:  # noqa: BLE001 - reported as not graded
        return None


def grade(rows: list[dict], actual: dict, game: dict) -> list[dict]:
    lines = {}
    for side in ("home", "away"):
        team = game[side]
        for u in actual["players"][side]:
            lines[player_key(team, u["name"])] = u
    out = []
    for r in rows:
        u = lines.get(player_key(r["team"], r["odds_name"]))
        if u is None:
            out.append({**r, "result": "name unmatched"})
            continue
        v = u.get(ACTUAL_KEY[r["market"]], 0)
        res = "push" if v == r["line"] else ("W" if (v > r["line"]) == (r["pick"] == "over") else "L")
        out.append({**r, "actual": v, "result": res})
    return out


def record(pulls: list[Pull], do_grade: bool) -> dict:
    """S5: per game, the last pull before kickoff that has sims; both lists' top-N rows."""
    last: dict[str, Pull] = {}
    for p in pulls:
        if p.sims is None:
            continue
        for gid in p.games:
            ko = _parse(p.odds["games"][gid].get("kickoff"))
            if ko and p.at < ko and (gid not in last or p.at > last[gid].at):
                last[gid] = p
    out = {"graded": [], "not_final": [], "unmatched_sr": [], "unmatched_odds": []}
    if not do_grade:
        return out
    for gid, p in sorted(last.items()):
        game = p.odds["games"][gid]
        actual = _actual(game)
        if actual is None:
            out["not_final"].append(gid)
            continue
        for which, rk in (("odds", rank(p.lines("odds"), p.sims, now=p.at)), ("sr", rank(p.lines("sr"), p.sims, now=p.at))):
            rows = [r for r in rk["ranked"][:TOP_N] if r["game_id"] == gid]
            for g in grade(rows, actual, game):
                g["list"] = which
                out["graded"].append(g)
                if g["result"] == "name unmatched":
                    out["unmatched_sr" if which == "sr" else "unmatched_odds"].append(f"{gid} {g['odds_name']} {g['market']}")
    return out


# --- report ------------------------------------------------------------------

CRITERIA = {"S1": "Coverage", "S2": "Names and game identity", "S3": "Lines",
            "S4": "Ranking", "S5": "Record"}


def _best_rank(c: dict) -> int:
    return min((c["odds"] or [999])[0], (c["sr"] or [999])[0])


def _collected(pulls: list[Pull], paired: int, v: dict) -> dict:
    """run()'s results as plain data for the props-page section (S8(c))."""
    entries, absent, misnamed, changes = v["entries"], v["absent"], v["misnamed"], v["changes"]
    n, same, pn, pok, diffs, rec = v["n"], v["same"], v["pn"], v["pok"], v["diffs"], v["rec"]
    graded = [x for x in rec["graded"] if x["result"] in ("W", "L", "push")]

    def wlp(which: str) -> str:
        c = Counter(x["result"] for x in graded if x["list"] == which)
        return f"{c['W']}-{c['L']}-{c['push']}"

    causes = Counter(c["cause"] for c in changes)
    tags = Counter(d["tag"] for d in diffs)
    criteria = [
        ("S1", v["s1"], [
            f"top-{TOP_N} Odds API props absent from Sportradar: {len(v['top_absent'])}",
            f"covered {entries - len(absent)} of {entries} entries ({v['covered']:.1%}; bar {S1_COVERAGE:.0%})"
            if entries else "no entries compared",
            f"{len(absent)} absent, {len(misnamed)} misnamed (misnamed count under S2)"],
         [f"{m['game']} {m['player']} {m['market']}: {m['kind']}{' [top]' if m['in_top'] else ''}"
          for m in v["all_misses"]]),
        ("S2", v["s2"], [f"{len(v['fails'])} name or game-identity failures"]
         + [f"unmeasured {u}" for u in v["unmeasured"]], v["fails"]),
        ("S3", v["s3"], [
            f"totals equal {same} of {n} ({v['r_tot']:.1%}; bar {S3_TOTAL_BAR:.0%})" if n else "nothing compared",
            f"P(over) within {S3_P_TOL} {pok} of {pn} ({v['r_p']:.1%}; bar {S3_P_BAR:.0%})" if pn
            else "no prices compared",
            f"{len(diffs)} differences" + (": " + ", ".join(f"{k} {c}" for k, c in tags.most_common()) if diffs else "")],
         []),
        ("S4", v["s4"], [
            f"{len(changes)} ranking changes"
            + (" (" + ", ".join(f"{k} {c}" for k, c in causes.most_common()) + ")" if changes else ""),
            f"{len(v['unexplained'])} unexplained",
            f"{len(v['moves'])} move{'' if len(v['moves']) == 1 else 's'} of {MOVE_REPORT}+ places inside the top {TOP_N} (reported only)"], []),
        ("S5", v["s5"], (
            ["graded in the full report (python -m src.p62_compare), not on refresh: grading reads ESPN"]
            if not v["do_grade"] else [
                f"Sportradar top-{TOP_N} props unmatched in grading: {len(rec['unmatched_sr'])}",
                f"not final yet: {', '.join(rec['not_final']) or 'none'}",
                f"Odds API list {wlp('odds')}, Sportradar list {wlp('sr')} (reported only)"]),
         rec["unmatched_sr"]),
    ]
    return {
        "pulls": [{"stamp": p.stamp, "at": p.at.isoformat(), "games": len(p.games),
                   "excluded": len(p.excluded), "ranked": p.sims is not None} for p in pulls],
        "paired": paired,
        "excluded": sum(len(p.excluded) for p in pulls),
        "criteria": [{"id": k, "name": CRITERIA[k], "status": st, "detail": det, "items": items}
                     for k, st, det, items in criteria],
        "changes": [{"pull": c["pull"], "game_id": c["key"][0], "player": c["key"][1], "market": c["key"][2],
                     "game": c["game"], "team": c["team"], "label": c["label"], "kinds": c["kinds"],
                     "cause": c["cause"],
                     "odds_rank": c["odds"][0] if c["odds"] else None, "odds_pick": c["odds"][1] if c["odds"] else None,
                     "sr_rank": c["sr"][0] if c["sr"] else None, "sr_pick": c["sr"][1] if c["sr"] else None,
                     "odds_state": c["odds_state"], "sr_state": c["sr_state"],
                     "odds_side": c["odds_side"], "sr_side": c["sr_side"],
                     "odds_line": c["odds_line"], "sr_line": c["sr_line"]}
                    for c in sorted(changes, key=lambda c: (c["pull"], _best_rank(c)))],
        "moves": [{"pull": m["pull"], "game_id": m["key"][0], "player": m["key"][1], "market": m["key"][2],
                   "odds_rank": m["odds_rank"], "sr_rank": m["sr_rank"]} for m in v["moves"]],
        "line_diffs": [{k: d[k] for k in ("pull", "game", "player", "market", "book", "kind", "tag", "minutes")}
                       | {"odds": {k: d["odds"].get(k) for k in ("point", "over", "under")},
                          "sr": {k: d["sr"].get(k) for k in ("point", "over", "under")}}
                       for d in diffs[:DIFF_ROWS]],
        "line_diff_count": len(diffs),
    }

def run(since: datetime | None, until: datetime | None, do_grade: bool = True, out_dir: Path = OUT_DIR,
        collect: dict | None = None) -> tuple[str, dict]:
    """The report and the verdict per criterion. `collect`, when given, is
    filled with the same results as plain data (the props-page section)."""
    pulls = load_pulls(out_dir, since, until)
    verdict: dict[str, str] = {}
    lines: list[str] = [f"# P62 Phase 1 comparison ({len(pulls)} pulls"
                        f"{', since ' + since.isoformat() if since else ''}{', until ' + until.isoformat() if until else ''})", ""]
    if not pulls:
        verdict = {k: "UNMEASURED" for k in CRITERIA}
        if collect is not None:
            collect.update({"pulls": [], "paired": 0, "excluded": 0, "criteria": [
                {"id": k, "name": CRITERIA[k], "status": v, "detail": ["no saved pulls in range"], "items": []}
                for k, v in verdict.items()], "changes": [], "moves": [], "line_diffs": [], "line_diff_count": 0})
        return "\n".join(lines + ["No saved pulls in range."]), verdict
    paired = sum(len(p.games) for p in pulls)
    lines += ["## Pairs", "", f"{paired} game pairs within {PAIR_MINUTES:g} min; "
              f"{sum(len(p.excluded) for p in pulls)} excluded; "
              f"{sum(p.sims is None for p in pulls)} pull(s) with no ranking sims kept (S1a, S2b, S4, S5 unmeasured there).", ""]
    for p in pulls:
        for g, why in p.excluded.items():
            lines.append(f"- excluded {p.stamp} {g}: {why}")
    # manifest problems (S2a) inside the range
    man = [r for r in manifest_rows(out_dir)
           if (not since or (_parse(r["run_utc"]) or since) >= since) and (not until or (_parse(r["run_utc"]) or until) <= until)]
    mapping = [r for r in man if r["result"].startswith(("unmapped", "mapping"))]
    errors = [r for r in man if r["result"].startswith("error")]

    # S1
    all_misses, entries, top_unmeasured = [], 0, 0
    top_sets = {}
    for p in pulls:
        top = None
        if p.sims is not None:
            rk = rank(p.lines("odds"), p.sims, now=p.at)
            top = {(r["game_id"], r["odds_name"], r["market"]) for r in rk["ranked"][:TOP_N]}
        else:
            top_unmeasured += 1
        top_sets[p.stamp] = top
        c = coverage(p, top)
        entries += c["entries"]
        all_misses += c["misses"]
    absent = [m for m in all_misses if m["kind"] == "absent"]
    misnamed = [m for m in all_misses if m["kind"].startswith("misnamed")]
    # Misnamed entries are charged to S2, not to coverage (S1c).
    covered = (entries - len(absent)) / entries if entries else None
    top_absent = [m for m in absent if m["in_top"]]
    s1 = "UNMEASURED" if not entries else ("PASS" if not top_absent and covered >= S1_COVERAGE else "FAIL")
    verdict["S1"] = s1
    lines += ["", f"## S1 coverage: {s1}", "",
              f"- (a) top-{TOP_N} Odds API players absent from Sportradar: {len(top_absent)}"
              + (f" ({top_unmeasured} pull(s) without sims not checked)" if top_unmeasured else ""),
              f"- (b) covered {entries - len(absent)}/{entries} = {covered:.1%} (bar {S1_COVERAGE:.0%}; misnamed not counted here)" if entries else "- (b) no entries",
              f"- (c) {len(absent)} absent, {len(misnamed)} misnamed (charged to S2)"]
    for m in all_misses:
        lines.append(f"  - {m['pull']} {m['game']} {m['player']} {m['market']}: {m['kind']}"
                     f"{' [TOP]' if m['in_top'] else ''} books={','.join(m['books'])}")

    # S2
    fails = [f"mapping: {r['run_utc']} {r['game_id']} {r['result']}" for r in mapping]
    unmeasured = []
    for p in pulls:
        mine = [m for m in misnamed if m["pull"] == p.stamp]
        fails += names(p, mine)
        if not p.games:
            continue
        if p.sims is None:
            unmeasured.append(f"{p.stamp}: (b) no ranking sims")
        if p.holdouts is None:
            unmeasured.append(f"{p.stamp}: (d) hold tables not saved")
    s2 = ("STOP" if fails else "UNMEASURED (no paired games)" if not paired
          else "PASS" if not unmeasured else "PASS (partly unmeasured)")
    verdict["S2"] = s2
    lines += ["", f"## S2 names and game identity: {s2}", ""]
    lines += [f"- {f}" for f in fails] or ["- no differences"]
    lines += [f"- unmeasured {u}" for u in unmeasured]

    # S3
    n = same = pn = pok = 0
    diffs = []
    for i, p in enumerate(pulls):
        a, b, c, d, df = line_diffs(p, pulls[i - 1] if i else None)
        n, same, pn, pok = n + a, same + b, pn + c, pok + d
        diffs += df
    r_tot = same / n if n else None
    r_p = pok / pn if pn else None
    s3 = "UNMEASURED" if not n else ("PASS" if r_tot >= S3_TOTAL_BAR and (r_p or 0) >= S3_P_BAR else "FAIL")
    verdict["S3"] = s3
    tags = Counter(d["tag"] for d in diffs)
    lines += ["", f"## S3 lines: {s3}", "",
              f"- (a) totals equal {same}/{n} = {r_tot:.1%} (bar {S3_TOTAL_BAR:.0%})" if n else "- (a) nothing compared",
              f"- (b) P(over) within {S3_P_TOL} {pok}/{pn} = {r_p:.1%} (bar {S3_P_BAR:.0%})" if pn else "- (b) nothing compared",
              f"- (c) {len(diffs)} differences: " + ", ".join(f"{k} {v}" for k, v in tags.most_common())]
    by_book = Counter((d["book"], d["kind"]) for d in diffs)
    lines += [f"  - {b} {k}: {c}" for (b, k), c in sorted(by_book.items())]
    for d in diffs:
        lines.append(f"  - {d['pull']} {d['game']} {d['player']} {d['market']} {d['book']} [{d['tag']}, {d['kind']}, "
                     f"{d['minutes']} min] odds {d['odds']} vs sr {d['sr']}")

    # S4
    line_keys = {(d["game"], pnorm(d["player"]), d["market"]) for d in diffs}
    absent_keys = {(m["game"], pnorm(m["player"]), m["market"]) for m in absent}
    changes, moves, s4_unmeasured = [], [], []
    for p in pulls:
        r = ranking(p, line_keys, absent_keys)
        if r is None:
            s4_unmeasured.append(p.stamp)
            continue
        changes += r["changes"]
        moves += r["moves"]
    unexplained = [c for c in changes if c["cause"] == "unexplained"]
    s4 = "UNMEASURED" if len(s4_unmeasured) == len(pulls) else ("STOP" if unexplained else "PASS")
    verdict["S4"] = s4
    lines += ["", f"## S4 ranking: {s4}", "",
              f"- changes: {len(changes)} ({', '.join(f'{k} {v}' for k, v in Counter(c['cause'] for c in changes).most_common()) or 'none'})"
              f"; unexplained {len(unexplained)}; pulls without sims: {len(s4_unmeasured)}"]
    per_pull = defaultdict(Counter)
    for c in changes:
        for k in c["kinds"]:
            per_pull[c["pull"]][f"{k}/{c['cause']}"] += 1
    for stamp, cnt in sorted(per_pull.items()):
        lines.append(f"  - {stamp}: " + ", ".join(f"{k} {v}" for k, v in sorted(cnt.items())))
    for c in changes:
        lines.append(f"  - {c['pull']} {c['key']} {'+'.join(c['kinds'])} -> {c['cause']} (odds {c['odds']}, sr {c['sr']})")
    lines += [f"  - move {m['pull']} {m['key']}: {m['odds_rank']} -> {m['sr_rank']}" for m in moves]

    # S5
    rec = record(pulls, do_grade)
    s5 = ("UNMEASURED (grading skipped)" if not do_grade else
          "STOP" if rec["unmatched_sr"] else ("PASS" if rec["graded"] else "UNMEASURED (no final game yet)"))
    verdict["S5"] = s5
    lines += ["", f"## S5 record: {s5}", "",
              f"- (a) Sportradar top-{TOP_N} props unmatched in grading: {len(rec['unmatched_sr'])}"
              f" (Odds API list, for context: {len(rec['unmatched_odds'])})",
              *[f"  - {u}" for u in rec["unmatched_sr"]],
              f"- not final yet: {', '.join(rec['not_final']) or 'none'}",
              "- (b) reported only; two weeks is not evidence for either source:"]
    for which in ("odds", "sr"):
        g = [x for x in rec["graded"] if x["list"] == which and x["result"] in ("W", "L", "push")]
        for m in sorted({x["market"] for x in g}):
            c = Counter(x["result"] for x in g if x["market"] == m)
            dec = c["W"] + c["L"]
            lines.append(f"  - {which} {m}: {c['W']}-{c['L']}-{c['push']}"
                         + (f" ({c['W'] / dec:.0%})" if dec else ""))
    both = defaultdict(dict)
    for x in rec["graded"]:
        both[_key(x)][x["list"]] = x
    for k, v in both.items():
        if "odds" in v and "sr" in v and v["odds"]["line"] != v["sr"]["line"]:
            lines.append(f"  - different line {k}: odds {v['odds']['line']} {v['odds'].get('result')}, "
                         f"sr {v['sr']['line']} {v['sr'].get('result')}")

    # S7(c) quota, from the same pulls
    lines += ["", "## S7(c) calls (reported)", "",
              f"- shadow pulls {len(pulls)}, game pulls {sum(len(p.games) + len(p.excluded) for p in pulls)}, "
              f"shadow errors logged {len(errors)}",
              f"- hypothetical Odds API credits a switch would have saved on these pulls: "
              f"{4 * sum(len(p.games) + len(p.excluded) for p in pulls)} (4 markets x games pulled; HYPOTHETICAL)"]
    head = ["## Verdict", ""] + [f"- {k}: {v}" for k, v in verdict.items()] + [""]
    if collect is not None:
        collect.update(_collected(pulls, paired, locals()))
    return "\n".join(lines[:2] + head + lines[2:]), verdict


def export(path: Path = PUBLIC_P62_JSON, out_dir: Path = OUT_DIR, now: datetime | None = None) -> dict:
    """S8(c): the props-page section's data, over the validation window, from
    saved shadow files only (no grading, so no ESPN call). Nothing else reads it."""
    data: dict = {}
    since, until = _parse(WINDOW_START), _parse(WINDOW_END)
    _, verdict = run(since, until, do_grade=False, out_dir=out_dir, collect=data)
    payload = {"generated_at": (now or datetime.now(timezone.utc)).isoformat(),
               "window": {"start": since.isoformat(), "end": until.isoformat()},
               "top_n": TOP_N, "verdict": verdict, **data}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
    return payload


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since")
    ap.add_argument("--until")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--no-grade", action="store_true")
    ap.add_argument("--export", action="store_true", help="write the props-page JSON (S8c) and stop")
    args = ap.parse_args()
    if args.export:
        payload = export()
        print(f"wrote {PUBLIC_P62_JSON}: " + ", ".join(f"{k} {v}" for k, v in payload["verdict"].items()))
        return
    text, verdict = run(_parse(args.since), _parse(args.until), do_grade=not args.no_grade)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    print(text if not args.out else "\n".join(f"{k}: {v}" for k, v in verdict.items()))


if __name__ == "__main__":
    main()
