# NFL / NCAAF Game Predictor — Architecture & Build Spec

**Goal:** A free-data-only prediction system for NFL and NCAAF games that produces a win probability, predicted spread, and a "value vs. market" flag for each upcoming game, incorporating team strength, situational factors, injuries/depth chart, and weather.

**Timeline constraint:** Needs a working, testable MVP for today's CFB slate, with NFL following for tomorrow. Build order below is sequenced for that — get a thin end-to-end pipeline live first, then layer in sophistication.

---

## 1. High-level architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      DATA INGESTION LAYER                    │
│  nfl_data_py │ CFBD API │ ESPN site API │ Odds API │ Open-Meteo│
└───────────────────────────┬───────────────────────────────────┘
                             ▼
                    ┌─────────────────┐
                    │  Supabase (DB)   │  raw + processed tables
                    └────────┬─────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                   FEATURE ENGINEERING LAYER                  │
│  power ratings │ situational adj │ injury impact │ weather    │
└───────────────────────────┬───────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                      MODELING LAYER                           │
│  Layer 1: Elo/SP+ baseline                                    │
│  Layer 2: situational + injury adjustment                     │
│  Layer 3: ML model (XGBoost) — win prob / spread               │
│  Layer 4: market comparison → value signal                     │
└───────────────────────────┬───────────────────────────────────┘
                             ▼
                ┌─────────────────────────┐
                │  Predictions table (DB)  │
                └───────────┬─────────────┘
                             ▼
              ┌───────────────────────────┐
              │  React dashboard + logs    │
              └───────────────────────────┘
```

Same overall shape as sports-value-picks and the tennis predictor: ingestion → Supabase → feature/model layers → dashboard. Reuse whatever's reusable from those repos (Supabase client setup, scheduler pattern, dashboard shell).

---

## 2. Data ingestion layer

### NFL sources
| Source | Data | Auth |
|---|---|---|
| `nfl_data_py` | play-by-play (EPA/WPA), team/player stats, schedules, rosters, snap counts, **weekly injury report w/ practice status** | none |
| ESPN site API (`site.api.espn.com/apis/site/v2/sports/football/nfl/...`) | live scores, depth charts, status blurbs | none (unofficial) |
| The Odds API | spreads, moneylines, totals | existing key |
| Open-Meteo | wind/temp/precip at stadium coords | none |

### NCAAF sources
| Source | Data | Auth |
|---|---|---|
| CollegeFootballData (CFBD) | games, betting lines, SP+/FPI/Elo ratings, advanced box scores (EPA, success rate, explosiveness), recruiting composite, returning production, rosters | free key — get today at collegefootballdata.com |
| ESPN site API (`.../college-football/...`) | depth charts, live scores, partial injury info | none (unofficial) |
| The Odds API | lines (shares your NFL quota — budget calls) | existing key |
| Open-Meteo | weather per stadium | none |

### Ingestion modules (build as separate, independently-runnable scripts)
- `ingest_cfbd.py` — pulls games, lines, ratings, rosters for current week
- `ingest_nflverse.py` — pulls pbp/stats/injuries via `nfl_data_py`
- `ingest_espn_depth.py` — pulls depth charts + injury blurbs for both sports
- `ingest_odds.py` — pulls current lines from The Odds API for both sports, one call each, cached
- `ingest_weather.py` — pulls forecast per game using stadium lat/long lookup table

Each writes to its own raw table in Supabase, tagged with `pulled_at` timestamp. Keep raw and processed data separate so a bad upstream pull doesn't corrupt derived features.

---

## 3. Database schema (Supabase)

Minimum viable tables:

- `games` — game_id, sport, season, week, home_team, away_team, kickoff_time, venue, is_neutral_site
- `team_ratings` — team, sport, week, elo, sp_plus, fpi, off_epa, def_epa (from CFBD/nflverse)
- `injuries` — player, team, sport, position, status (out/doubtful/questionable/probable), practice_trend (dnp→limited→full), position_weight
- `depth_charts` — team, sport, position, player, depth_order
- `weather` — game_id, temp_f, wind_mph, precip_pct, is_dome
- `odds` — game_id, book, spread, total, moneyline_home, moneyline_away, pulled_at
- `predictions` — game_id, model_win_prob_home, model_spread, market_spread, edge, confidence, generated_at

---

## 4. Feature engineering

For each upcoming game, compute:
- **Power rating differential**: home vs away, from CFBD SP+/Elo (NCAAF) or your computed EPA-based Elo (NFL)
- **Situational**: home/away, rest days, short week flag, travel distance, neutral site
- **Injury-adjusted rating shift**: sum of (position_weight × severity × play_probability) for each injured player on each side. Play probability estimated from practice trend (DNP all week ≈ low, limited→full ≈ high).
- **Depth quality drop-off**: when a starter is out, pull the next player on the depth chart and, if you have season stats for them, discount team's positional rating toward replacement level rather than a flat penalty
- **Weather adjustment**: wind >15mph knocks down passing/kicking projections; precip favors run-heavy/under; skip entirely for dome games
- **Market anchor**: current spread/total, used both as a feature and as the comparison baseline for the value signal

**Position weighting for injuries** (starting point — refine with backtesting):
- QB: highest weight by far
- Edge rusher / CB1 / OL (esp. LT): moderate-high
- RB1 / WR1: moderate
- Depth positions (backup skill, ST): low

---

## 5. Modeling layers

**Layer 1 — Baseline power rating.** NCAAF: use CFBD's SP+ or Elo directly. NFL: compute a simple EPA-based Elo from nflverse pbp (there's no need to reinvent SP+, just get points-per-play differential rolling by week).

**Layer 2 — Situational + injury adjustment.** Apply the shifts from section 4 on top of the baseline rating to get an adjusted power differential.

**Layer 3 — ML model.** XGBoost (or LightGBM) trained on historical games (as many past seasons as CFBD/nflverse give you cleanly) using the adjusted differential + situational features as inputs, predicting either win probability (classification) or point margin (regression). This is the piece that needs training time — good candidate to kick off overnight and let run while other pieces get built.

**Layer 4 — Market comparison.** Compare model output to the current market line. Flag games where the gap exceeds a threshold (start conservative, e.g., 2+ points) as "value" candidates. This mirrors the sports-value-picks approach — the model doesn't need to be right in an absolute sense, it needs to be right *relative to where the market is wrong*.

---

## 6. Automation & dashboard

- Scheduler (reuse the Windows Task Scheduler pattern from sports-value-picks): run ingestion nightly during season, re-run predictions after injury reports update (NFL: Wed/Thu/Fri practice reports; CFB: less standardized, pull daily during game week)
- React dashboard (reuse shell from existing projects): weekly slate view, per-game breakdown showing model line vs market line vs edge, injury report summary, confidence tier

---

## 7. Build order for tonight

1. **Repo scaffold + Supabase schema** — tables above, `.env` for CFBD key, Odds API key
2. **CFBD ingestion + basic ratings pull** — get today's CFB slate with SP+/Elo and lines flowing end-to-end first, since that's the immediate test target
3. **Odds + weather ingestion** — attach to today's games
4. **Baseline prediction (Layers 1+2+4, no ML yet)** — power rating diff + situational/injury adjustment vs market line. This alone is testable against today's games.
5. **nflverse ingestion + NFL Elo** — mirror the CFB pipeline for tomorrow's NFL slate
6. **Injury/depth chart pipeline (ESPN ingestion)** — wire into the adjustment layer for both sports
7. **ML layer (Layer 3) trained on historical data** — kick off training as a background/overnight step; swap into the pipeline once validated against a holdout set
8. **Dashboard** — last, once predictions are flowing reliably

---

## 8. Testing plan for today's games

- Once step 4 is live, generate predictions for today's full CFB slate before kickoff
- Log model spread vs. market spread for every game — don't cherry-pick
- After games finish, score against actual results (both straight-up and against the spread) to get a first read on calibration
- Treat today as a **paper-trading day only** — one slate isn't enough signal to trust the value flags yet; the real test is accumulating a few weeks of logged predictions vs. outcomes before weighting the "edge" signal heavily

---

## 9. What to hand Claude Code

- This document
- `Lock.txt` — CFBD API key and The Odds API key
- `no-key-data-sources.md` — access details for nfl_data_py, ESPN site API, and Open-Meteo
- Supabase project credentials (existing, reuse project or spin up new one — your call)
- Note the free-tier limits explicitly in the prompt: CFBD free tier rate limit, Odds API ~500 req/month shared across both sports, ESPN endpoint is unofficial so wrap calls in try/except with graceful fallback
