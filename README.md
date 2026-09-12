# Football Predictor

Free-data-only prediction system for NFL and NCAAF. Produces a win probability,
a predicted spread, and a value-vs-market flag per game.

Built against `football-predictor-architecture.md`. Currently through **step 7**
of the section 7 build order. Only the dashboard remains.

**Read the backtest section before trusting any value flag.** The honest finding
is that neither model beats the closing line, so value flagging is switched off
by the model's own gate.

## Status

| Step | Scope | State |
|------|-------|-------|
| 1 | Repo scaffold + schema + `.env` | done |
| 2 | CFBD ingestion (games, SP+/Elo, lines, venues, teams) | done |
| 3 | Odds API + Open-Meteo ingestion | done |
| 4 | Baseline prediction, Layers 1+2+4 | done |
| 5 | nflverse ingestion + NFL Elo | done |
| 6 | Injury / depth pipeline (nflverse + ESPN) | done |
| 7 | XGBoost Layer 3 + backtest | done |
| 8 | React dashboard | not started |

## Injuries

Each injured player costs his team:

    position weight  x  snap share  x  (1 - play probability)  x  scale

The **snap-share** term is what makes this safe rather than harmful. An injury
report lists third-stringers next to starters, so without it a backup being
ruled out would cost a full starter's penalty. Snap share comes from nflverse
snap counts, joined on a normalized player name — PFR drops generational
suffixes ("Michael Penix") where the injury feeds keep them ("Michael Penix
Jr."), and unjoined stars silently look like unknown reserves.

Only the top few players per position are charged, since if the starting QB is
out the backup plays and charging for both double-counts one job. Play
probability comes from the practice trend: a Questionable player who practised
fully is priced at 0.80 to play, one who sat out all week at 0.25.

Coverage differs enormously by sport, and the report says which applies:

- **NFL** — nflverse's mandated weekly report covers all 32 teams, with ESPN
  filling in same-day changes. Genuinely useful.
- **NCAAF** — no mandated report exists. ESPN's feed is editorially curated and
  typically lists a handful of teams out of 138, so college injury coverage is
  inherently partial. Teams with no data get no adjustment rather than being
  assumed healthy.

## Setup

```bash
pip install -r requirements.txt
```

Secrets live in `.env` (git-ignored, as is `Lock.txt`). See `.env.example`.

## Running

```bash
python run_pipeline.py                    # today's CFB slate
python run_pipeline.py --sport nfl        # next NFL slate with games
python run_pipeline.py --sport both
python run_pipeline.py --date 2026-09-19
python run_pipeline.py --skip-ingest      # re-predict from stored data
python run_pipeline.py --fresh-odds       # bypass odds cache (costs quota)
```

With no `--date`, the runner picks the next date that actually has unplayed
games, so `--sport nfl` on a Tuesday still shows Sunday's slate.

Each module also runs standalone:

```bash
python -m src.ingest_cfbd
python -m src.ingest_nflverse
python -m src.ingest_weather --sport nfl
python -m src.ingest_odds --sport nfl
python -m src.predict_baseline --sport nfl --date 2026-09-13
```

## Ratings

`team_ratings.power_rating` is the sport-neutral Layer 1 input: points above an
average team. The modeling layer reads only this column, so both sports share
one code path.

- **NCAAF** — CFBD's SP+, which is already a points figure, used directly.
- **NFL** — built from play-by-play: offensive EPA per play minus defensive EPA
  per play allowed, scaled by 63 plays a game and centred on the league. A
  conventional margin-aware Elo is computed alongside as a cross-check and as
  the fallback when a team has no pbp.

Early-season shrinkage is the part that matters. In week 1 the current season
has almost no plays, so prior-season EPA is carried forward and the current
season blended in as volume accumulates; the run prints how much weight the
prior season is still carrying.

## Schema changes

Both schema files use `create table if not exists`, which does **not** add a
column to a table that already exists. The SQLite mirror handles this itself by
diffing declared columns against live ones and ALTERing in the gaps on connect.
For Supabase, any column added later is also appended to the bottom of
`db/schema_supabase.sql` as `alter table ... add column if not exists`, so
re-running that whole file stays safe and additive.

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

## The ML layer, and what the backtest says

```bash
python -m src.build_training --sport nfl --start 2016    # historical features
python -m src.train_model --sport nfl                    # train + backtest
python run_pipeline.py --sport nfl --model both          # baseline and ML
```

### Lookahead was the main design constraint

The quickest way to build this training set would be to join each historical
game to CFBD's SP+ ratings. It is also the quickest way to get a model that
looks superb and is worthless: a season's SP+ is computed from that whole
season, including the game being predicted, so the model learns to read the
answer. Every rating used as a feature here is therefore built **walk-forward** —
games are replayed in order, features are recorded from the state *before* each
game, and only then is the result folded in. Live prediction replays the same
history rather than reading `team_ratings`, because that table holds SP+ and a
differently-shrunk EPA that the model never saw.

Where a training column was constant, the live column is held at that same
constant. College training rows carry no rest, EPA or weather, so the live
college model is fed zeros there too. Supplying a real value to a column the
model only ever saw as zero is a silent skew, not an upgrade.

### Two models, and why both are reported

| Model | Market as a feature | Use |
|---|---|---|
| `fundamentals` | no | the only one that can disagree with the market, so the only one that can find value |
| `with_market` | yes | more accurate, and useless for value — the cheapest way to predict a margin is to copy the line |

### Results: holdout is the most recent season, never used in fitting

Early stopping chooses the number of trees, which makes whatever set it watches
part of fitting. The season before the holdout is therefore carved out as a
validation set, and the holdout is touched exactly once, at scoring time.

Mean absolute error in points of margin:

| | NFL (285 games) | NCAAF (762 games) |
|---|---|---|
| **Closing line** | **9.670** | **11.846** |
| `fundamentals` | 10.152 (+0.482) | 12.98 (+1.13) |
| `with_market` | 9.602 (**-0.069**) | 11.88 (+0.03) |

Adding injuries moved the NFL `with_market` model from +0.002 to **-0.069**
versus the line: with injury features it is no longer merely copying the line,
it is slightly correcting it. That is the first evidence in this project of
information the closing line does not fully price.

It is also a very small effect, and it does **not** translate into a spread
edge. Against the spread, no bucket in either sport survives correction for
multiple comparisons — five thresholds across two models is ten chances to
clear p<0.05 by luck, so roughly one false positive is expected per run:

| Edge | NFL win% (n) | raw p | corrected p |
|---|---|---|---|
| >= 2.0 | 56.1% (82) | 0.251 | 1.000 |
| >= 3.0 | 58.3% (36) | 0.238 | 1.000 |
| >= 4.0 | 68.8% (16) | 0.095 | 0.952 |

### A result that did not survive scrutiny

An earlier version of this backtest reported 65.1% ATS at edge >= 3 with
p=0.047, marked SIGNIFICANT. It was wrong, for two compounding reasons:

1. The holdout season was being used as the early-stopping `eval_set`, so the
   model was tuned on the season used to judge it.
2. No correction was applied for testing ten model/threshold combinations.

Fixing both dropped that bucket to 58.3% with a corrected p of 1.000. The
lesson is worth stating plainly: a backtest is only as good as its worst
methodological shortcut, and a betting signal is exactly the wrong place to let
one through.

### Injury features in training

The training set scores every historical NFL injury report with
`features.score_injuries` — the same function the live pipeline calls, so the
model is trained on exactly the feature it is later served. Two features are
produced: `injury_diff` (aggregate points) and `qb_loss_diff` (how much of a
starting quarterback a side is missing), kept separate because losing a QB is a
different kind of event rather than a larger quantity of damage.

Snap share is the lookahead trap here. A player's season-long snap share
includes games *after* the one being predicted, so shares are accumulated week
by week, falling back to the prior season. The injury report itself is
published before kickoff and is fine to use; only the usage weighting attached
to it can leak.

Coverage is ~99% of games across all ten seasons. `injury_diff` correlates
+0.139 with actual margin and — more interestingly — **+0.039 with the market
residual**, the highest of any feature, which is what makes it the most
promising place to keep looking.

College gets zeros: there is no historical CFB injury feed, so the column is
constant in training and held at 0 live to match.

### The next things worth trying

- Line movement (opening vs current) — the sharpest public signal not yet used.
- Weather history for college, which would let the CFB model use the weather
  the live pipeline already collects.
- Several seasons of holdout rather than one; n=285 cannot resolve an edge of
  the size being looked for.

## Rate limits

- **The Odds API** — ~500 requests/month shared across both sports. One request
  per sport per run, disk-cached for `ODDS_CACHE_MINUTES` (default 180). Quota
  remaining is printed every run. `--fresh-odds` is the only thing that bypasses
  the cache.
- **CFBD** — free tier. One call per resource per week, never per team. Ratings
  and venues are cached for hours to days.
- **ESPN** — unofficial, so every call is wrapped and failure degrades the
  pipeline instead of stopping it.
- **nflverse** — no key, no rate limit; reads GitHub releases.
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

- **Neither model beats the closing line.** See the backtest section. The ML
  layer's value flags are gated off as a result; the baseline's flags are still
  shown but are unvalidated and fire on ~77% of rated games.
- **The baseline's value threshold is not meaningful.** Its mean absolute
  disagreement with the market is ~4 points, so the spec'd 2.0-point threshold
  flags most of the slate. Every run prints a threshold sensitivity table.
- **NFL week-1 ratings lean ~99% on last season.** That is the correct thing to
  do with 7 plays of current-season data, but it means the NFL numbers are a
  prior-season model until a few weeks accumulate.
- **Layer 2 coefficients are priors, not fitted values** — home field, rest,
  travel and wind magnitudes are conservative guesses documented in
  `src/features.py`. Backtesting should replace them.
- **FCS opponents have no SP+ rating** and are filled with a flat
  replacement-level proxy (`-28`). Those games are predicted and logged but
  never value-flagged, since the "edge" would mostly be the proxy's own error.
- Today is **paper trading only**.
