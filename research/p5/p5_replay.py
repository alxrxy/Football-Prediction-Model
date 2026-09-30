"""P5 (NFL): cap large early-season edges? Research only; nothing live.

    python research/p5/p5_replay.py [out.md]

Criteria were set with the user 2026-09-30 (calibration-log.md, P5 row) before
this ran, with the P22 phase-1 replay's numbers already visible:
- claim: size-reliability in weeks 1-4 (is a large edge less reliable ATS than a moderate one);
- bar: P37's lean slope (ATS result on edge size), cap only if negative with permutation p < 0.05;
- sample: the P22 phase-1 walk-forward replay, candidate A+B (frozen), weeks 1-4 of 2016-25;
- reported, not a gate: margin error of large early edges against the line.
The frozen A+B arm is rebuilt with the harness's own code (no tuning) and must
reproduce the published weeks 1-4 row before anything else is read.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research" / "p22"))
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else None
sys.argv = sys.argv[:1]  # the harness reads argv[1] as its own output path at import
import p22_phase1 as H  # noqa: E402

lines: list[str] = []


def say(text=""):
    print(text)
    lines.append(text)


pbp, totals, league_ppg = H.load()
games = pd.read_csv(ROOT / "data" / "training_nfl.csv")
games = games[(games["season"] >= 2016) & (games["season"] <= 2025) & (games["week"] <= 18) & games["market_spread"].notna()]

r_off, r_def = H.carry_factors(pbp, True, False, 300)
arm = {"adj": True, "filt": False, "lam": 300, "r_off": r_off, "r_def": r_def}
say("# P5 (NFL): large early-season edges on the P22 rating (research only)")
say()
say(f"Frozen A+B rebuilt: penalty 300, carry off {r_off:.3f} / def {r_def:.3f} (published 0.459 / 0.394).")
res = H.evaluate(pbp, games, totals, league_ppg, arm)
w = res[res["week"] <= 4]
e, r = w["edge"].to_numpy(), w["resid"].to_numpy()
got = (len(w), H.ats_record(e[np.abs(e) >= 3], r[np.abs(e) >= 3]), H.ats_record(e[np.abs(e) >= 6], r[np.abs(e) >= 6]),
       round(H.lean_slope(e, r), 3))
want = (635, (123, 102, 5), (30, 19, 0), 0.044)
ok = (round(r_off, 3), round(r_def, 3)) == (0.459, 0.394) and got == want
say(f"Reproduces the published weeks 1-4 row (n, >=3, >=6, lean slope): {got} vs {want}: **{'YES' if ok else 'NO - stopping'}**")
say()
if not ok:
    OUT and OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    sys.exit(1)

slope, p = H.perm_p(e, r)
cap = slope < 0 and p < 0.05
say("## Gate: P37 lean slope, weeks 1-4 (cap only if negative with permutation p < 0.05)")
say()
say(f"- lean slope **{slope:+.3f}**, permutation p **{p:.3f}** ({H.N_PERM:,} permutations) -> **{'CAP' if cap else 'NO CAP'}**")
say()

say("## Reported, not a gate")
say()
rows = []
a = np.abs(e)
for name, m in (("< 3", a < 3), ("3 to < 6", (a >= 3) & (a < 6)), (">= 6", a >= 6), ("all", a >= 0)):
    s = w[m]
    rows.append([name, len(s), H.fmt_rec(*H.ats_record(s["edge"].to_numpy(), s["resid"].to_numpy())),
                 f"{s['err'].mean():.2f}", f"{s['resid'].abs().mean():.2f}", f"{s['err'].mean() - s['resid'].abs().mean():+.2f}"])
H.lines = []
H.table(rows, ["abs edge, weeks 1-4", "n", "ATS", "model MAE", "line MAE", "model - line"])
lines.extend(H.lines)
say()
say("Margin error: `model MAE` is the rating's margin against the result; `line MAE` is the closing line's.")

if OUT:
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nwrote {OUT}")
