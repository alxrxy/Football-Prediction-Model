# Football Predictor

Free-data-only prediction system for NFL and NCAAF. Produces a win probability,
a predicted spread, and a value-vs-market flag per game.

Built against `football-predictor-architecture.md`. Currently through **step 4**
of the section 7 build order.

## Status

| Step | Scope | State |
|------|-------|-------|
| 1 | Repo scaffold + schema + `.env` | done |
| 2 | CFBD ingestion (games, SP+/Elo, lines, venues, teams) | done |
| 3 | Odds API + Open-Meteo ingestion | done |
| 4 | Baseline prediction, Layers 1+2+4 | done |
| 5 | nflverse ingestion + NFL Elo | not started |
| 6 | ESPN injury / depth-chart pipeline | not started |
| 7 | XGBoost Layer 3 | not started |
| 8 | React dashboard | not started |

The injury term in Layer 2 is wired up but **inactive** — it reads an empty
`injuries` table and contributes exactly 0 until step 6. The report says so on
every run rather than implying injuries were priced in.

## Setup

```bash
pip install -r requirements.txt
```

Secrets live in `.env` (git-ignored, as is `Lock.txt`). See `.env.example`.

## Running

```bash
python run_cfb_today.py                 # full pipeline for today's slate
python run_cfb_today.py --date 2026-09-19
python run_cfb_today.py --skip-ingest   # re-predict from stored data
python run_cfb_today.py --fresh-odds    # bypass odds cache (costs quota)
```

Each ingestion module also runs standalone:

```bash
python -m src.ingest_cfbd
python -m src.ingest_weather
python -m src.ingest_odds --sport ncaaf
python -m src.predict_baseline --date 2026-09-12
```

## Storage

`STORAGE_BACKEND` in `.env` selects the backend. Both use identical table names
and primary keys, so switching requires no code change.

- `sqlite` — local file at `data/football.db`. Default.
- `supabase` — the hosted project.

To move onto Supabase:

1. Open the project's **SQL Editor**, paste all of `db/schema_supabase.sql`, Run.
   PostgREST cannot execute DDL, so this one step is manual.
2. `python -m src.sync_to_supabase --check` to confirm all tables exist.
3. `python -m src.sync_to_supabase` to push the local data up.
4. Set `STORAGE_BACKEND=supabase` in `.env`.

## Rate limits

- **The Odds API** — ~500 requests/month shared across both sports. One request
  per sport per run, disk-cached for `ODDS_CACHE_MINUTES` (default 180). Quota
  remaining is printed every run. `--fresh-odds` is the only thing that bypasses
  the cache.
- **CFBD** — free tier. One call per resource per week, never per team. Ratings
  and venues are cached for hours to days.
- **ESPN** — unofficial, so every call is wrapped and failure degrades the
  pipeline instead of stopping it.
- **Open-Meteo** — no key. Coordinates are batched, so a full slate is ~2 calls.

## Conventions that matter

- **Spreads are always home-team lines**: negative means the home team is
  favored. Both CFBD and The Odds API are normalized to this on ingest. CFBD's
  sign is derived from its `formattedSpread` string (which names the favorite
  explicitly) rather than its raw `spread` field, so an upstream sign change
  cannot silently flip the market.
- **Edge is positive when the model prefers the home side**:
  `edge = model_margin_home + market_spread`.
- Raw ingested rows and derived predictions live in separate tables, every raw
  row carrying `pulled_at`.

## Known limitations

- **The value threshold is not yet meaningful.** The baseline's mean absolute
  disagreement with the market is ~4 points, so the spec'd 2.0-point threshold
  flags most of the slate. Every run prints a calibration block with a threshold
  sensitivity table. Treat the flags as unvalidated until step 7 and a real
  backtest.
- **Layer 2 coefficients are priors, not fitted values** — home field, rest,
  travel and wind magnitudes are conservative guesses documented in
  `src/features.py`. Backtesting should replace them.
- **FCS opponents have no SP+ rating** and are filled with a flat
  replacement-level proxy (`-28`). Those games are predicted and logged but
  never value-flagged, since the "edge" would mostly be the proxy's own error.
- Today is **paper trading only**.
