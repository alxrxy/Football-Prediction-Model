"""P62 S8(b): would the sims change if the props lines came from Sportradar? Read-only.

    python -m src.p62_sim_check                    # the latest saved shadow pull
    python -m src.p62_sim_check --pull 20261004T150200Z --sims 2000

The props lines reach the simulator in exactly two places, both reading
props_lines.json from the data folder: P49's priced-QB set
(`features.qb_context`) and P53's / P51's (`simulate_nfl.qb_check_inputs`).
This runs the pull's games three times with `store_results=False`: A with the
pull's Odds API file at those two points, B with its Sportradar file, and A'
with the Odds API file again. Nothing is stored; no served file is touched.
Sims are seeded per game, so A == A' is the control: if it fails, the inputs
moved during the check and the result is INCONCLUSIVE, never a pass.

S8(b) passes when B == A for every game (byte-identical rows once the
generation timestamp is dropped) and the sim QBs are the same. Any difference
is a stop.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from . import config, features, simulate_nfl
from .shadow_props_sr import OUT_DIR

VOLATILE = {"generated_at"}


class _DataDir:
    """The config module with DATA_DIR pointed elsewhere; everything else forwarded."""

    def __init__(self, data_dir: Path):
        self._dir = data_dir

    def __getattr__(self, name):
        return self._dir if name == "DATA_DIR" else getattr(config, name)


def _variant(root: Path, name: str, lines_file: Path) -> Path:
    d = root / name
    d.mkdir()
    shutil.copyfile(lines_file, d / "props_lines.json")
    td = config.DATA_DIR / "td_props_lines.json"
    if td.exists():
        shutil.copyfile(td, d / "td_props_lines.json")   # same in every variant
    return d


_INPUTS: dict = {}


def simulate(games: list[str], data_dir: Path, n: int) -> dict[str, dict]:
    """The steps of simulate_nfl.run (context, anchors, QB check, simulate_one per
    game) with the two props-line reads pointed at data_dir and nothing stored.
    The nflverse inputs don't read props lines, so they are loaded once and
    shared by every run: one load instead of one per game (a per-game reload
    took 48 downloads for 16 games and died on a network timeout, 10/1)."""
    from . import db

    saved = (features.config, simulate_nfl.config)
    features.config = simulate_nfl.config = _DataDir(data_dir)
    store = db.get_store()
    try:
        ctx = features.FeatureContext(store, "nfl")   # P49 reads the lines here
        rows = [g for g in ctx.games if g["game_id"] in set(games)]
        season = int(rows[0]["season"])
        if season not in _INPUTS:
            _INPUTS[season] = simulate_nfl.load_inputs(season)
        anchors = simulate_nfl._stored_anchors(store, rows)
        qbc = simulate_nfl.qb_check_inputs(store)        # P53 / P51 read the lines here
        out = {}
        for game in rows:
            margin, label = anchors.get(game["game_id"], (None, None))
            row = simulate_nfl.simulate_one(game, ctx, _INPUTS[season], n, anchor=margin,
                                            anchor_label=label, qb_check=qbc)
            if row is not None:
                out[game["game_id"]] = row
        return out
    finally:
        store.close()
        features.config, simulate_nfl.config = saved


def _canon(row: dict) -> str:
    clean = {k: v for k, v in row.items() if not k.startswith("_") and k not in VOLATILE}
    return json.dumps(clean, sort_keys=True, default=str)


def sim_qbs(row: dict) -> dict[str, str | None]:
    box = row.get("box_score")
    box = json.loads(box) if isinstance(box, str) else (box or {})
    out = {}
    for side in ("home", "away"):
        qbs = [p for p in (box.get(side) or {}).get("players") or [] if (p.get("position") or "") == "QB"]
        def att(p):
            a = (p.get("passing") or {}).get("att") or {}
            return a.get("median") if a.get("median") is not None else (a.get("mean") or 0)
        out[side] = max(qbs, key=att)["player"] if qbs else None
    return out


def check(pull_dir: Path, n: int) -> tuple[str, list[str]]:
    sr = json.loads((pull_dir / "sr.json").read_text(encoding="utf-8"))
    games = sorted(g for g, v in (sr.get("games") or {}).items() if v.get("pulled_at") == sr.get("pulled_at"))
    lines = [f"S8(b) on pull {pull_dir.name}: {len(games)} game(s), {n:,} sims each"]
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        a_dir = _variant(tmp, "odds", pull_dir / "odds.json")
        b_dir = _variant(tmp, "sr", pull_dir / "sr.json")
        a = simulate(games, a_dir, n)
        b = simulate(games, b_dir, n)
        a2 = simulate(games, a_dir, n)
    verdict = "PASS"
    for gid in games:
        if gid not in a or gid not in b or gid not in a2:
            lines.append(f"  {gid}: not simulated in every run (A {gid in a}, B {gid in b}, A' {gid in a2})")
            verdict = "INCONCLUSIVE" if verdict == "PASS" else verdict
            continue
        control = _canon(a[gid]) == _canon(a2[gid])
        same = _canon(a[gid]) == _canon(b[gid])
        qa, qb = sim_qbs(a[gid]), sim_qbs(b[gid])
        if not control:
            lines.append(f"  {gid}: INCONCLUSIVE, A != A' (inputs moved during the check)")
            verdict = "INCONCLUSIVE" if verdict == "PASS" else verdict
        elif same and qa == qb:
            lines.append(f"  {gid}: identical; sim QBs {qa}")
        else:
            lines.append(f"  {gid}: DIFFERS; sim QBs Odds API {qa} vs Sportradar {qb}")
            verdict = "STOP"
    lines.insert(1, f"verdict: {verdict}")
    return verdict, lines


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pull", default="latest", help="pull stamp under data/props_sr/pulls, or 'latest'")
    ap.add_argument("--root", type=Path, default=OUT_DIR)
    ap.add_argument("--sims", type=int, default=simulate_nfl.N_SIMS)
    ap.add_argument("--dir", type=Path, help="a pull folder outside data/props_sr (e.g. a backup copy)")
    args = ap.parse_args()
    pulls = sorted(p.parent for p in (args.root / "pulls").glob("*/sr.json"))
    if not pulls:
        raise SystemExit("no saved shadow pulls")
    pull = args.dir or (pulls[-1] if args.pull == "latest" else args.root / "pulls" / args.pull)
    _, lines = check(pull, args.sims)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
