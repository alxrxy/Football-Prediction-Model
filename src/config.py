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
VALUE_EDGE_THRESHOLD = float(os.getenv("VALUE_EDGE_THRESHOLD", "2.0"))

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
