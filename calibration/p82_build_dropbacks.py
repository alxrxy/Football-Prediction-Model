"""Rebuild data/cache/p82_dropbacks_2024_2026.parquet (qb_dropback plays, REG+POST) from nflverse.
The week-10 shadow read a cache built before week 10; this refreshes it. Read-only apart from the cache file."""
from pathlib import Path
import pandas as pd
import nfl_data_py as nfl

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "data/cache/p82_dropbacks_2024_2026.parquet"
old = pd.read_parquet(path)
p = nfl.import_pbp_data([2024, 2025, 2026], downcast=False, cache=False)
p = p[p.qb_dropback == 1]
missing = [c for c in old.columns if c not in p.columns]
assert not missing, missing
new = p[list(old.columns)].reset_index(drop=True)
print("old rows", len(old), "by season", old.groupby("season").size().to_dict(), "max 2026 week", old[old.season == 2026].week.max() if "week" in old else "?")
print("new rows", len(new), "by season", new.groupby("season").size().to_dict(), "max 2026 week", new[new.season == 2026].week.max() if "week" in new else "?")
new.to_parquet(path)
