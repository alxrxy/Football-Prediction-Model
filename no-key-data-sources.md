# No-Key Data Sources

These three sources need no signup, no API key, and no auth header. Keys for CFBD and The Odds API live separately in `Lock.txt` — this file is just for the free/open ones.

---

## nfl_data_py — Python package

**Install:**
```
pip install nfl_data_py
```

**Usage:**
```python
import nfl_data_py as nfl

pbp = nfl.import_pbp_data([2024, 2025])       # play-by-play w/ EPA/WPA
rosters = nfl.import_rosters([2025])           # team rosters
injuries = nfl.import_injuries([2025])         # weekly injury reports w/ practice status
schedules = nfl.import_schedules([2025])       # game schedules
```

Pulls straight from the `nflverse-data` GitHub releases under the hood. No auth, no rate limit to plan around — just needs internet access.

---

## ESPN site API — unofficial, no key

Plain HTTP GET, no auth header required.

**Base URLs:**
- NFL: `https://site.api.espn.com/apis/site/v2/sports/football/nfl/`
- NCAAF: `https://site.api.espn.com/apis/site/v2/sports/football/college-football/`

**Useful endpoints to append:**
- `scoreboard` — current week's games/scores
- `teams/{team_id}/depthchart` — depth chart by team
- `teams/{team_id}` — roster + team info

**Example:**
```
GET https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/kc/depthchart
```

**Caveat:** this is undocumented/unofficial. Wrap every call in try/except with a fallback (e.g., skip depth-chart enrichment for that team rather than crash the pipeline), and don't hammer it with high request frequency — it could change or rate-limit without notice.

---

## Open-Meteo — no key

Plain HTTP GET, no auth required.

**Base URL:** `https://api.open-meteo.com/v1/forecast`

**Required params:** `latitude`, `longitude`, plus the weather fields wanted (e.g., `hourly=temperature_2m,precipitation_probability,windspeed_10m`).

**Example:**
```
GET https://api.open-meteo.com/v1/forecast?latitude=39.05&longitude=-94.48&hourly=temperature_2m,windspeed_10m,precipitation_probability
```

**Note:** needs a stadium lat/long lookup table (one-time build, 32 NFL + FBS venues) to feed this per game — build that table early since both weather and travel-distance features depend on it.
