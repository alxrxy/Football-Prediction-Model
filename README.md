# Football Predictor

Free-data-only prediction system for NFL and NCAAF. Produces a win probability,
a predicted spread, and a value-vs-market flag per game.

Built against `football-predictor-architecture.md`. **All eight steps of the
section 7 build order are complete.**

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
| 8 | React dashboard | done |
| — | NFL game simulation (separate phase) | built; not yet in `run_pipeline.py` |

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
For Supabase, any column added later is also repeated in the migrations section
of `db/PASTE_INTO_SUPABASE.sql` as `alter table ... add column if not exists`,
so re-running that whole file stays safe and additive.

## Storage

`STORAGE_BACKEND` in `.env` selects the backend. Both use identical table names
and primary keys, so switching requires no code change.

- `sqlite` — local file at `data/football.db`. Default.
- `supabase` — the hosted project.

To move onto Supabase:

1. Open the project's **SQL Editor**, paste all of `db/PASTE_INTO_SUPABASE.sql`,
   Run. PostgREST cannot execute DDL, so this one step is manual. The script is
   idempotent, ends by printing what it created, and enables row level security
   so a leaked anon key cannot read or write your data.
2. `python -m src.sync_to_supabase --check` to confirm all tables exist.
3. `python -m src.sync_to_supabase` to push the local data up.
4. Set `STORAGE_BACKEND=supabase` in `.env`.

## Dashboard

```bash
cd dashboard && npm install && npm run dev     # http://localhost:5173
python -m src.export_dashboard                 # refresh its data
```

Slate table (market line vs both models, edge, lean, confidence), a
click-through per-game breakdown showing the layer-by-layer path to the number
plus the injury report behind it, and the backtest panel. See
`dashboard/README.md`.

For a single self-contained file with the snapshot inlined:

```bash
cd dashboard && npm run build
python -m src.export_static_dashboard
```

The backtest sits beside the picks rather than behind a tab, and games that pass
the Stage 1 edge test (below) are labelled `unvalidated` rather than `value`
until closing line value backs them. The trained model's value gate is
separate, reported in the backtest panel, and currently shut.

## Grading

```bash
python -m src.grade --refresh              # re-pull finals, then score
python -m src.grade --sport nfl
python -m src.grade --model ml-v1 --since 2026-09-01
python run_pipeline.py --sport both --grade   # grade, then predict the next slate
```

Fills `actual_home_points`, `actual_away_points` and `graded_at`, then reports
straight-up record, against-the-spread record, margin error against the closing
line, and a Brier score for the win probabilities — broken out by edge size and
confidence tier, each with its sample size and a significance test.

**It grades against the line stored with the prediction**, which is the line as
it stood when the prediction was made. Grading against a line pulled afterwards
would score the model against a number it never saw, and would flatter it,
since lines drift toward the result as information arrives.

The report states sample size prominently and refuses to draw conclusions below
200 graded spread results. A weekend is about 90 games, which sounds
substantial and cannot separate a genuine 55% edge from a coin flip. This is the
piece that will eventually let the value gate open honestly — or confirm it
should stay shut.

Run `python -m tests.test_grade` for the grading maths (20 hand-computed cases).

## Value flags and closing line value (Stage 1)

```bash
python -m src.clv                  # fill closing lines for finished games, report CLV
python -m src.clv --report         # report only, no ESPN calls
python -m src.clv --backfill       # log leans for predictions made before clv_log existed
python calibration/stage1_before_after.py calibration/<date>_stage1_before_after.md
python -m tests.test_market && python -m tests.test_clv
```

A game used to be flagged when the model's margin sat 2+ points from the
market's. That flagged most of the slate and faded the sharpest number
available whenever the model was wrong: the pregame flags went 15-25. The flag
is now decided in probability space (`src/market.py`), following Stage 1 of
`nfl-modeling-research.md`:

1. **Devig.** Each book's spread is devigged from both sides' prices (Shin by
   default; `odds_ratio` and `log` are also available via `DEVIG_METHOD`),
   restated at the consensus line, and the median taken. Pinnacle is used on
   its own if `ODDS_BOOKMAKERS` brings it in. Restating across lines uses the
   real distribution of margins near that spread, so a half point across 3 or
   7 counts for more than one across 5. With no stored prices the line is
   taken at −110 both ways.
2. **Blend.** The model's cover probability is combined with the market's in
   log-odds space, `logit p = w·logit p_model + (1−w)·logit p_market`, with
   `w = MODEL_MARKET_WEIGHT = 0.15`.
3. **Buffer.** A game is flagged only when the lean side's blended cover
   probability beats the break-even of its price (52.4% at −110) by
   `EDGE_BUFFER = 3` pp.

At w = 0.15 a flag takes about an 11-point disagreement in the NFL (about 14 in
college) on a −110 line, so almost nothing flags. That is intended: the model
hasn't shown it knows something the line doesn't. `w` should rise only when
closing line value says it has.

**Closing line value.** Every lean, flagged or not, goes into `clv_log` at
prediction time with the lean side's vig-free probability. After the game, the
close is taken from ESPN's pickcenter (DraftKings' closing line and prices,
free, both sports), devigged the same way and restated at the lean's line:
`clv_pp = p_close − p_market`. `python -m src.grade` fills it in and prints the
report. Leans made after kickoff, and closes implausibly far from the stored
line (bad line data, not movement), are kept but left out of the means. CLV
becomes readable at ~50–65 leans, far sooner than an ATS record. The research's
rule is to keep `w` at 0 if it's negative by then.

**Prices.** `ingest_odds` keeps both sides' prices in `odds_snapshots`
(append-only, pregame pulls only). It no longer stores in-play prices at all: a
game that has kicked off keeps its last pregame line, which is its close.

**Two new tables**, `odds_snapshots` and `clv_log`. Re-paste
`db/PASTE_INTO_SUPABASE.sql` into the Supabase SQL Editor, then push what the
local mirror collected in the meantime:
`python -m src.sync_to_supabase --tables odds_snapshots clv_log`. Until then
both are written to, and read back from, the local SQLite mirror, with a
warning.

## Game simulation (NFL)

```bash
python -m src.simulate_nfl --game 2026_01_DEN_KC --no-store   # one game, printed only
python -m src.simulate_nfl --date 2026-09-20                  # a slate, written to game_simulations
python -m src.simulate_nfl --calibrate                        # engine vs real NFL scoring
python -m src.sim_data --rebuild                              # rebuild the play library
python -m tests.test_simulate
```

A build phase of its own. It writes only the `game_simulations` table, never
reads or writes `predictions`, and is not called by `run_pipeline.py`.

**How a game is simulated.** 10,000 games are played snap by snap, all in
lockstep as numpy arrays (about a second per game). Each scrimmage snap is
drawn from the 112k real plays run in the same down / distance / field-zone
situation in 2023–25; its net yardage comes from the change in field position,
so penalties are included. On 4th down, teams go, kick or punt as often as NFL
teams actually do from that spot, and late in the game they follow the score
instead. Punts, field goals (distance plus forecast wind), PATs and two-point
tries all come from real outcomes. Kickoffs use 2025 only, because that
season's rule change moved drive starts. Overtime follows the rule where both
teams get a possession.

**Team strength** is exponential tilting of that shared library. Each play is
weighted by `exp(lambda * EPA)`, with lambda solved so that the offence
averages its expected EPA per play against this defence: its offensive rating
plus the opponent's defensive rating. A good offence therefore draws more of
the plays that actually worked in every situation, without an invented yardage
curve. Pass rate over expected shifts each team's run/pass mix.

**Play-calling follows the scoreboard.** Before each simulated snap the call is
made, run or dropback, at that situation's pass rate shifted by the offence's
lead (nine bands) and the phase of the game (six, including the two-minute
drill and the last five minutes). The shifts are fitted on the 2023–25 play
library (`sim_data._script_shift`). A simulated team that goes ahead runs and
one that falls behind throws, so player volume follows each simulated game
rather than an average one. `python -m src.simulate_nfl --calibrate` prints
team volume by final margin against real games (`--no-script` for the engine
without it):

| rush att per team | lost 15+ | lost 8–14 | within 7 | won 8–14 | won 15+ |
|---|---|---|---|---|---|
| sim, script off | 24.1 | 25.2 | 26.3 | 26.8 | 27.9 |
| sim, script on | 21.4 | 22.7 | 26.6 | 30.1 | 32.5 |
| real 2023–25 | 20.7 | 21.6 | 26.4 | 29.4 | 31.6 |

**It is anchored to the pipeline.** A small symmetric EPA offset is solved so
that the simulations average exactly the baseline margin, which already
includes home field, rest, travel, injuries and wind. The simulator adds what
surrounds that centre: the spread of outcomes, the total, and how the points
arrive. The injury report is split by position: a missing quarterback weakens
his own offence, and a missing cornerback strengthens the opposing one.

**TD scorers are deliberately low confidence.** Each simulated touchdown is
handed to a player by his share of that kind of opportunity. Goal-line rushing
TDs go by goal-line carry share, red-zone passing TDs by red-zone target share,
and so on. Small samples are shrunk toward the player's broader share. The
current nflverse depth chart sets volume. Outside the playing slots, a player
gets only his slot's typical share, so a former starter now on the bench
doesn't keep a starter's workload, and a backup quarterback gets nothing.
An injured player's share passes to the next man down at his position, in
proportion to how unlikely he is to play. This extrapolates historical usage;
it does not simulate game plans, which is why the output is flagged below the
score and TD/FG counts.

**Calibration.** Two league-average teams, unanchored, against the 2023–25
actuals:

| | sim | real |
|---|---|---|
| points / team | 22.5 | 22.6 |
| TDs / team | 2.50 | 2.51 |
| FGs / team | 1.69 | 1.70 |
| defensive + return TDs / team-game | 0.134 | 0.132 |
| total points, sd | 12.8 | 13.6 |
| tie rate | 0.9% | 0.1% |

Known gaps:

- **Ties run high.** Ten-minute overtime without clock management leaves too
  many games level. Some of the gap is also a rule change: the reference
  seasons mostly ended OT on an opening-drive touchdown.
- **Totals are slightly too narrow**, about 6% less spread than real games,
  because each simulated game holds both teams' strength fixed.
- **Not modelled:** timeouts, the two-minute drill, onside kicks, fakes, and
  two-point decisions by chart (tries happen at the league base rate).
- **The modal exact score is weak.** It typically carries 0.5–1% and is usually
  within sampling noise of several others; the report says how many. The median
  is the steadier headline.
- **Supabase needs the table created first.** Re-run
  `db/PASTE_INTO_SUPABASE.sql` (it is idempotent). Until then a stored run
  prints a clear error, and `sync_to_supabase --check` lists the table as
  missing.

## Live tracking (NFL)

```bash
python -m src.live_tracker                 # poll every ~2.5 min until the day's games are over
python -m src.live_tracker --once          # one cycle
python -m src.live_tracker --no-notify     # no desktop toasts
python -m tests.test_live
```

Open `http://localhost:5173/live.html` with the dashboard dev server running.
The page re-reads `live.json` every 20 seconds.

A layer of its own. It reads the stored pregame prediction and simulation,
never changes either, and writes only `live_tracking`: one timestamped
snapshot per game per poll, so a game's whole trajectory is kept.

**Polling.** Each cycle makes one scoreboard call, which says which games are
in progress, plus one summary call per in-progress game for its scoring plays.
Games that haven't kicked off are never polled. With nothing live, the tracker
sleeps until the next kickoff, and it exits when nothing starts within 12
hours. A finished game gets one closing snapshot. Every ESPN call and every
parse is guarded: a failed request or a malformed game skips that piece of that
cycle, three failures in a row raise an alert, and polling carries on.

**What counts as diverging.** The pregame simulation records the score every
five minutes of game clock in all 10,000 simulated games. A live game is placed
in the distribution for its own elapsed time:

| flag | fires when | extreme when |
|---|---|---|
| `pace_high` / `pace_low` | total so far is beyond the 5th/95th percentile of simulations at this point | beyond 1st/99th |
| `margin_home` / `margin_away` | home margin so far is beyond the 5th/95th percentile | beyond 1st/99th |
| `underdog_leading` | the pregame underdog leads by more than 7 | leads by 14+, or any such lead in the 4th |

Pace and margin flags wait for five minutes of game clock. Percentiles are
mid-ranked, so a 0–0 start counts as ordinary rather than as a 0th-percentile
low. Each flag is announced once, and again only if it escalates to extreme,
so a flag hovering at its threshold doesn't re-alert every poll.

**Where alerts go:**
- a console banner,
- `data/live/alerts.log`,
- a Windows desktop toast,
- the live page, which shows each game's score, flags, and two charts: points
  and margin against the simulated 50%/90% range, drawn exactly from the
  scoring plays.

A restarted tracker reloads the day's alerts and snapshots, and doesn't
re-announce flags it already raised.

**If no simulation is stored** for a game (the usual case until
`game_simulations` exists in Supabase), the tracker builds one on first sight
of the game. It is pinned to the stored pregame prediction, so its centre is
still the pregame number. If `live_tracking` is missing from Supabase,
snapshots go to the local SQLite mirror for the session, with a warning, rather
than being lost.

### Player projections and the game view

```bash
python -m src.simulate_nfl --date 2026-09-13 2026-09-20 --quiet   # simulate slates
python -m src.export_sims                                         # refresh the game view's data
python -m tests.test_box_score
```

Every simulation, pregame and live, now tracks full stat lines. Each simulated
play is credited to players as it happens:

- a designed run goes to a ball carrier chosen by carry share for that part of
  the field (goal line, red zone, open field),
- a scramble and every pass go to that simulated game's quarterback (a doubtful
  starter plays some simulations and his backup the rest),
- a target goes to a receiver chosen by red-zone, short or deep target share.

The shares are the same injury- and depth-chart-adjusted shares the TD scorer
list uses, so the two always agree: touchdowns are credited on the play
itself. Yards come from the real play drawn, so they are league-typical for the
situation rather than each player's own efficiency.

Each player's line is summarised the way the score is: median, mean, the most
likely count, and the middle 50% and 80% of simulations. Only players with
meaningful usage appear. The result is stored as `box_score` on
`game_simulations`, and on `live_simulations` as projected finals (stats so far
plus the simulated rest).

Against the 2023–25 actuals, two league-average teams produce these per-team
box-score totals:

| per team | sim | real |
|---|---|---|
| pass attempts | 32.8 | 32.7 |
| completions | 21.3 | 21.2 |
| passing yards | 237 | 232 |
| carries | 26.1 | 26.1 |
| rushing yards | 120 | 118 |

**The game view.** Every NFL row on the dashboard expands. The NFL tab also
lists every game on today's slate and the next three, finished, live or
upcoming, in the Game simulations section. Each game shows:

- the projected final score and its distribution,
- the TD/FG counts,
- the likely scorers,
- every player's passing, rushing and receiving line with its ranges.

While a game is on, the view offers the live model next to the pregame
projection and refreshes every poll. Once the game is over, the actual score,
counts, scorers and player lines sit beside the pregame projection, each with
where it fell (inside the 50% range, the 80% range, or outside). The live
tracker re-exports the view's data whenever a game goes final.

Player projections are labelled lower confidence than the score and win
projections throughout. Usage shifts week to week in ways historical shares
don't capture.

### Live projections (live-resume simulation)

On every poll, each game in progress is simulated 10,000 more times from where
it stands (score, clock, possession, down and distance). That takes about 0.2
seconds a game. It uses the same engine and the same anchored team strengths
as the pregame simulation, so any gap between the pregame numbers and the live
ones comes from what has happened on the field, not from a different model.
Each game keeps the same random seed from poll to poll, so the projection moves
only when the game state changes. `--live-sims N` changes the number of
simulations.

- **Where the resumed games start.** The scoreboard's live situation is used
  when it has one. During timeouts and quarter breaks the tracker falls back to
  the last real snap in ESPN's summary. After a score the next event is the
  kickoff, with any extra point still to come tried first. At halftime the
  second-half kickoff goes to whichever side didn't take the opening one.
- **Storage.** `live_simulations` gets one row per poll, keyed to the
  `live_tracking` snapshot it ran from. Each row repeats the pregame margin and
  win probability, so "before kickoff" and "now" sit side by side.
- **Scorers from here.** These start from the pregame usage shares and are
  pulled toward each player's share of his team's carries and targets so far
  this game (ESPN's box score). The game's own usage gets weight
  `opportunities / (opportunities + 30)`, about a third by halftime.
  Red-zone and goal-line shares scale with the same shift, and a player the
  depth chart missed joins with his live share. They remain low confidence.
- **On the live page**, each game gets:
  - a "Before kickoff vs. live model now" table,
  - win probability through the game (the live model against ESPN's own, with
    the pregame figure as a reference line),
  - the projected final margin with its 80% range,
  - the live scorer lists.

Team strengths don't update from in-game performance. A side dominating on the
field carries its lead forward but keeps its pregame strength for the plays
still to come. Timeouts aren't modelled, so late-game clock use is approximate.

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

## Claude API sections (Q&A, best props, live games)

```bash
python -m src.api_server          # local Q&A server on 127.0.0.1:8787 (holds the API key)
python -m src.ingest_props        # NFL player-prop lines, ~64 Odds API credits a pull (cached)
python -m src.ingest_props --only-missing   # just the games with no props yet, ~4 credits each
python -m src.props               # rank props vs the simulations; top 25, Claude explains each
python -m src.props --alts        # also pull alternate lines (extra Odds API credits; off by default)
cd dashboard && npm run dev       # http://localhost:5174, proxies /api to the server
python -m tests.test_props
```

The NFL tab is a hub of full-page sections (the URL hash keeps your place:
`#/nfl/games`, `#/nfl/game/<id>`, `#/nfl/props`, `#/nfl/live`, `#/nfl/record`):
**Games** (every game of the week as a card; each opens a game page with the
simulation, the baseline breakdown and Q&A), **Props**, **Live**, and
**Record** (track record and backtest). Team names, colours and logos come
from `dashboard/src/nflTeams.json`, written by `python -m src.export_team_meta`.
The live page only trusts `live.json` while the tracker is writing it (10
minutes), so a stopped tracker's old snapshot never shows a finished game as
live.

The one metered piece of the stack. The key is read from `Claude_API_KEY` in
`.env`; the page never sees it. Three sections use it:

- **Ask about this game**, on every game page. The question goes to the
  local server, which sends Claude only that game's numbers as a few dozen
  lines of text (`src/game_context.py`): prediction, market, Stage 1 result,
  baseline pieces, injuries, simulation ranges, key players, ranked props.
  About 2¢ a question.
- **Props**, with its own Q&A about the week's list. Each prop line is devigged
  across books and compared with that player's simulated chance; ranked by
  the gap. The top 25 are shown as cards, the rest (and the props held out
  for gaps past 25 pp, likely usage misses) in a dropdown beneath. Each top
  prop used to get an alt line; alternates are now **off by default**. Books
  post them as overs only, and the simulator's usage bias (P17) makes the
  ranking all unders, so a pull costs ~1 credit per (game, stat) pair and
  attaches nothing — on 2026-09-16 it spent 9 credits for zero alt lines.
  `--alts` turns them back on: the easier line on the pick's side that the
  simulation gives 65%+, priced −250 or longer, with the best expected return.
  Claude writes the explanations once per export (cached), not per
  page view. See P17:
  the simulator doesn't yet model each player's own efficiency, so treat
  the list as a check on the simulator for now.
- **Live**. While the live tracker runs, each game in progress gets a
  scoreboard, the live model's win chance over the game, projections, the
  scoring log and key players, and a Q&A that answers from the live state
  (score, clock, field position, live win chance, projected finals).

Cost controls: `claude-opus-5` at low effort (`CLAUDE_API_MODEL`,
`CLAUDE_API_EFFORT`), refusal fallbacks on, answers capped, 40 questions an
hour, and a daily cap (`CLAUDE_DAILY_BUDGET_USD`, default $2). Every call's
tokens and estimated cost go to `data/claude_usage.jsonl`;
`/api/health` shows today's spend.

## Known limitations

- **Neither model beats the closing line.** See the backtest section. The ML
  layer's value flags are gated off as a result. The baseline's flags now use
  the Stage 1 test and fire on almost nothing at the starting model weight.
- **Closing lines are one book.** CLV's close is DraftKings via ESPN. The
  research recommends a sharp anchor (Pinnacle), which needs `ODDS_BOOKMAKERS`
  and a pull just before kickoff, and both cost Odds API quota.
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
