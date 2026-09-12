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

### Results: holdout is the most recent season, never trained on

Mean absolute error in points of margin:

| | NFL (285 games) | NCAAF (762 games) |
|---|---|---|
| **Closing line** | **9.67** | **11.85** |
| `fundamentals` | 10.15 (+0.48) | 12.97 (+1.13) |
| `with_market` | 9.67 (+0.00) | 11.88 (+0.03) |

Neither model beats the line. `with_market` matching the line almost exactly is
confirmation it simply learned to copy it.

Against the spread, break-even at -110 juice is 52.4%:

| Edge threshold | NFL | NCAAF |
|---|---|---|
| >= 2.0 pts | 52.4% (n=147) | 52.8% (n=587) |
| >= 3.0 pts | 48.0% (n=98) | 52.7% (n=490) |
| >= 4.0 pts | 47.8% (n=67) | 53.9% (n=423) |
| >= 6.0 pts | 31.2% (n=16) | 53.6% (n=295) |

The college numbers sit above break-even, and it would be easy to call them
profitable. They are not significant — one-sided p ranges from 0.27 to 0.46, so
a season of results this good happens by chance roughly a third of the time. The
NFL numbers are worse: the win rate *falls* as the model's disagreement with the
line grows, which is the opposite of a real edge.

### The value gate

Because of the above, `predict_ml` reads its own backtest and refuses to label
anything a value pick unless some threshold beat the line significantly. Edges
are still computed, stored and displayed — none is called value. The point of
running a backtest is to be allowed to change the answer.

A useful side observation: the ML model's largest college edge is 3.3 points
where the baseline claimed 10.5. The trained model converges toward the market,
which is itself evidence the baseline's big "edges" were its own error rather
than the market's.

### The obvious next improvement

The ML layer does not use injuries — the training set has no injury features,
though nflverse publishes reports back to 2009. Adding them is the most
promising upgrade available, and is a prerequisite for the value flag ever
passing its own gate.

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
