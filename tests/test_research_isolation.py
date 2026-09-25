"""P46: research layers must never reach live code.

    python -m tests.test_research_isolation

research/ holds unvalidated work (the scheme / formation layer). Nothing under
src/ or the pipeline entry points may import it until an item is walk-forward
validated and promoted on purpose, at which point this test is the thing that
has to change.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PASS, FAIL = 0, 0
IMPORT = re.compile(r"^\s*(from\s+research\b|import\s+research\b|from\s+\.+research\b)", re.M)


def check(label, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got {got!r}, want {want!r}")


def test_live_code_never_imports_research():
    live = sorted(ROOT.glob("src/*.py")) + [ROOT / "run_pipeline.py", ROOT / "run_sunday.py"]
    offenders = [p.name for p in live if p.exists() and IMPORT.search(p.read_text(encoding="utf-8"))]
    check("no live module imports research/", offenders, [])
    check("the check actually scanned the live modules", len(live) > 20, True)


if __name__ == "__main__":
    test_live_code_never_imports_research()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
