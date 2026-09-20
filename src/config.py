"""Central config. Everything secret comes from .env — never from Lock.txt."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _utf8_console() -> None:
    """Windows consoles default to cp1252, which mangles team names like
    "San José State" and any dash in the report. Force UTF-8 where possible."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


_utf8_console()

# --- Secrets ---
CFBD_API_KEY = os.getenv("CFBD_API_KEY", "").strip()
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "").strip()
# Claude API, for the dashboard's Q&A and prop explanations (src/claude_ai.py).
# Read under any of these names; .env carries it as Claude_API_KEY.
CLAUDE_API_KEY = (os.getenv("ANTHROPIC_API_KEY") or os.getenv("Claude_API_KEY")
                  or os.getenv("CLAUDE_API_KEY") or "").strip()


def _supabase_url() -> str:
    """Normalize to the project root.

    The dashboard shows the URL with '/rest/v1/' appended; the Python client
    wants the bare project origin and adds the REST path itself. Accept either.
    """
    raw = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    for suffix in ("/rest/v1", "/rest"):
        if raw.endswith(suffix):
            raw = raw[: -len(suffix)]
    return raw.rstrip("/")


SUPABASE_URL = _supabase_url()

# Accept either naming. The service-role key bypasses RLS, which is what an
# ingestion job needs; anon is the read-only fallback.
SUPABASE_SERVICE_KEY = (
    os.getenv("SUPABASE_SERVICE_KEY", "").strip()
    or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
)
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "").strip()

# --- Storage ---
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "sqlite").strip().lower()
SQLITE_PATH = ROOT / os.getenv("SQLITE_PATH", "data/football.db")

# --- Paths ---
DATA_DIR = ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
SCHEMA_SQLITE = ROOT / "db" / "schema_sqlite.sql"
SCHEMA_SUPABASE = ROOT / "db" / "PASTE_INTO_SUPABASE.sql"

# --- Tuning ---
ODDS_CACHE_MINUTES = int(os.getenv("ODDS_CACHE_MINUTES", "180"))
# Optional comma-separated Odds API bookmaker keys used instead of the "us"
# region, e.g. to add pinnacle as the sharp anchor. Up to 10 books cost the
# same quota as one region.
ODDS_BOOKMAKERS = os.getenv("ODDS_BOOKMAKERS", "").strip()
# The old flag: |model margin - market| in points. No longer decides value
# (see src/market.py); kept for the point-sensitivity table in reports.
VALUE_EDGE_THRESHOLD = float(os.getenv("VALUE_EDGE_THRESHOLD", "2.0"))

# Stage 1 edge logic (src/market.py). The model's weight in the log-odds blend
# with the devigged market, and the margin over break-even a flag needs. Raise
# the weight only once logged CLV is positive over ~65+ leans.
MODEL_MARKET_WEIGHT = float(os.getenv("MODEL_MARKET_WEIGHT", "0.15"))
EDGE_BUFFER = float(os.getenv("EDGE_BUFFER", "0.03"))
DEVIG_METHOD = os.getenv("DEVIG_METHOD", "shin").strip().lower()

# P13: take the NFL prior-season offense from the expected starting
# quarterback's games (src/qb_prior.py), in both the baseline rating and the
# ML replay. Off until it passes its adoption test (calibration-log.md). The
# ML model must be retrained whenever this changes, or it is served features
# built differently from the ones it was trained on.
QB_CONDITIONAL_PRIOR = os.getenv("QB_CONDITIONAL_PRIOR", "0").strip().lower() in ("1", "true", "yes")

# A nullified penalty replays the down instead of consuming one
# (src/simulate.py). Measured 2026-09-16: real football replays 69.8% of them
# and consumes almost none, while the engine consumes 71.7%, which shortens
# every drive and is the cause of its pass-attempt shortfall. On since
# 2026-09-19, re-validated against the 2026-09-16 calibration first. Set
# PENALTY_REPLAY=0 for the old behaviour; either way, flipping it changes
# simulated output, so stored game_simulations and any props ranked against
# them go stale and must be regenerated.
PENALTY_REPLAY = os.getenv("PENALTY_REPLAY", "1").strip().lower() in ("1", "true", "yes")

# Shift each prop category's simulated probability by its measured bias
# (src/props.py BIAS_FIT). Display-only: it never touches the simulation
# engine or the game-level predictions, which are calibrated separately and do
# not have this problem. A stopgap over an unfixed root cause, fitted in sample
# on one week, so it is off unless asked for.
PROPS_BIAS_ADJUST = os.getenv("PROPS_BIAS_ADJUST", "0").strip().lower() in ("1", "true", "yes")

# P31. Drop a depth-chart player from the simulated pool when his offensive
# snap participation is below USAGE_MIN_PARTICIPATION, before shares are
# normalised. 10.1% of every team's target share sits on players who have
# never taken a snap this season; the vector sums to 1.131, and normalising
# takes that excess out of everyone proportionally, so the biggest shares pay
# the most of it. Out of sample over 2025 weeks 11-18, replayed on the depth
# chart as it stood, the trim moves the top target-share quartile from 0.801
# to 0.919 of realised, brings the per-team sum to 0.996 and improves share
# MAE from 0.0430 to 0.0424. Off until it has been compared against a live
# Sunday with P10 inactives applied, since P10 attacks the same defect.
# Flipping it changes simulated output, so stored game_simulations and any
# props ranked against them go stale and must be regenerated.
USAGE_PARTICIPATION_TRIM = os.getenv("USAGE_PARTICIPATION_TRIM", "0").strip().lower() in ("1", "true", "yes")
USAGE_MIN_PARTICIPATION = float(os.getenv("USAGE_MIN_PARTICIPATION", "0.10"))

# Claude API: the one metered piece of the stack. Low effort suits short,
# data-grounded answers; the daily cap stops a runaway page or loop from
# running up a bill (src/claude_ai.py refuses calls past it).
# Prefixed CLAUDE_API_ because tools running this code (Claude Code among
# them) may export their own CLAUDE_MODEL / CLAUDE_EFFORT, which a bare name
# would silently pick up.
CLAUDE_MODEL = os.getenv("CLAUDE_API_MODEL", "claude-opus-5").strip()
CLAUDE_EFFORT = os.getenv("CLAUDE_API_EFFORT", "low").strip().lower()
CLAUDE_DAILY_BUDGET_USD = float(os.getenv("CLAUDE_DAILY_BUDGET_USD", "2.0"))

# Player-prop markets pulled from The Odds API (src/ingest_props.py). Each
# costs one credit per game per region: 4 markets x 16 games = 64 a pull.
PROP_MARKETS = os.getenv(
    "PROP_MARKETS", "player_pass_yds,player_rush_yds,player_reception_yds,player_receptions"
).strip()

# --- API bases ---
CFBD_BASE = "https://api.collegefootballdata.com"
ODDS_BASE = "https://api.the-odds-api.com/v4"
OPEN_METEO_BASE = "https://api.open-meteo.com/v1/forecast"
ESPN_NFL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
ESPN_CFB = "https://site.api.espn.com/apis/site/v2/sports/football/college-football"

MODEL_VERSION = "baseline-v1"


def require(name: str) -> str:
    """Fetch a required secret or exit with an actionable message."""
    value = globals().get(name, "")
    if not value:
        sys.exit(
            f"Missing {name}. Add it to {ROOT / '.env'} and re-run.\n"
            f"(See .env.example for the expected format.)"
        )
    return value


def ensure_dirs() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    CACHE_DIR.mkdir(exist_ok=True)
    SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
