"""run_sunday step order (P51): a window's props lines are pulled before its sim.

    python -m tests.test_sunday_order
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PASS, FAIL = 0, 0


def check(label: str, got, want) -> None:
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got {got!r}, want {want!r}")


def test_props_pull_precedes_sim():
    src = (Path(__file__).resolve().parents[1] / "run_sunday.py").read_text(encoding="utf-8")
    steps = re.findall(r'step\("([^"]+)"', src)
    order = [s for s in steps if s in ("props: pull lines", "simulate", "props: rank")]
    check("window order: pull lines, simulate, rank", order, ["props: pull lines", "simulate", "props: rank"])


if __name__ == "__main__":
    test_props_pull_precedes_sim()
    print(f"\n{PASS} passed, {FAIL} FAILED")
    sys.exit(1 if FAIL else 0)
