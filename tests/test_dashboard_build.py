"""The dashboard must compile: a JSX syntax error once reached localhost:5174 (2026-10-29,
an unterminated string in GamesPage.jsx). Runs `vite build` into a temp dir; skipped only when
Node / the dashboard's node_modules are not installed."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

DASHBOARD = Path(__file__).resolve().parents[1] / "dashboard"


def test_dashboard_compiles():
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx or not (DASHBOARD / "node_modules").exists():
        pytest.skip("node / dashboard node_modules not installed")
    with tempfile.TemporaryDirectory() as out:
        r = subprocess.run([npx, "vite", "build", "--outDir", out, "--emptyOutDir", "--logLevel", "error"],
                           cwd=DASHBOARD, capture_output=True, text=True, timeout=300)
        assert r.returncode == 0, f"dashboard build failed:\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}"
