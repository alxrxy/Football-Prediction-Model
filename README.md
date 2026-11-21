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

### Gameday inactives (Sundays)

About 90 minutes before each kickoff a team posts its official inactive list,
which is the first time a Questionable player is known either way. ESPN's core
API carries it on the per-competition roster (`didNotPlay`), and 404s until it
posts. Once a team's list is in, an inactive player drops to a play
probability of 0 and a Questionable, Doubtful or Probable player *not* on the
list goes to 1.0, in place of the flat 0.55 the practice trend gives him. Out
and IR are left alone.

Every team posts on its own clock, so a Sunday needs one refresh per kickoff
window rather than one for the day:

```bash
python run_sunday.py --plan     # the day's windows and when each refresh runs
python run_sunday.py --watch    # wait for each window, refresh, repeat
python run_sunday.py            # one refresh now, for the next window
```

The windows are clustered from the day's actual kickoff times, so a London
morning game or a flexed start schedules itself. Each one grades finished
games, pulls injuries and inactives, refreshes weather and odds, re-predicts,
re-simulates only the games still to kick off, re-ranks props for that
window's games and rebuilds the dashboard. nflverse is not re-ingested: its
play data only changes after games finish.

Coverage differs enormously by sport, and the report says which applies:

- **NFL** — nflverse's mandated weekly report covers all 32 teams, with ESPN
  filling in same-day changes. Genuinely useful.
- **NCAAF** — no mandated report exists. ESPN's feed is editorially curated and
  typically lists a handful of teams out of 138, so college injury coverage is
  inherently partial. Teams with no data get no adjustment rather than being
  assumed healthy.

## Setup

Checked from a fresh clone on 2026-11-20 (Windows 11, Python 3.11.9, Node 24). The NFL
pipeline runs with **no keys at all**; keys add live lines, props and the Q&A.

**You need**

- **Python 3.11.** The pins in `requirements.txt` are 3.11 builds (pandas 1.5.3,
  numpy 1.26.4); other versions are untested.
- **Node 18+ and npm**, only for the dashboard.

**Steps**

```bash
# 1. Python environment
python -m venv .venv
.venv\Scripts\activate            # macOS / Linux: source .venv/bin/activate
pip install -r requirements.txt

# 2. Optional: keys. Copy the template and fill in what you have (see the table below).
copy .env.example .env             # macOS / Linux: cp .env.example .env

# 3. Data + baseline predictions for the current NFL week (about a minute; creates data/football.db)
python run_pipeline.py

# 4. Optional: the ML layer. Builds the 2016+ training file (about a minute) and trains the model.
python -m src.build_training --sport nfl --start 2016
python -m src.train_model --sport nfl
python run_pipeline.py --model both --skip-ingest

# 5. Simulate games (about 30 s each), then export for the dashboard
python -m src.simulate_nfl --date 2026-11-22 --upcoming-only --quiet     # one slate date; repeat per date
python -m src.export_sims
python -m src.export_dashboard --no-explain      # --no-explain: no Claude call
python -m src.td_board                            # optional: the experimental TD board

# 6. Dashboard
cd dashboard
npm ci
npm run dev                                       # http://localhost:5174

# 7. Optional: Claude Q&A on the game pages (needs Claude_API_KEY), in a second terminal
python -m src.api_server                          # 127.0.0.1:8787; the dashboard proxies /api to it

# Tests
python -m pytest -q
```

**Keys**

| Variable | Needed for | Without it |
|---|---|---|
| none | nflverse data, weather, ESPN injuries, baseline predictions, simulation, dashboard | this all works |
| `ODDS_API_KEY` (The Odds API; has a free tier) | live book lines; player props and TD lines | lines are skipped with a warning and NFL games keep the nflverse schedule line; props and TD pulls stop with a clear message |
| `Claude_API_KEY` (paid, metered) | game Q&A, prop explanations, game notes | Q&A answers "No Claude API key found"; use `--no-explain` on exports |
| `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` | hosted storage (`STORAGE_BACKEND=supabase`) | local SQLite at `data/football.db`, the default |
| `CFBD_API_KEY` | college football (`--sport ncaaf`) | college does not run |
| `SPORTRADAR_API_KEY*`, `FANTASYPROS_API_KEY` | finished experiments (P61, P62, P47) | nothing in the weekly routine uses them |

Secrets live in `.env` (git-ignored, as is `Lock.txt`). Never commit either.

**What a fresh clone does not have.** `data/` and `models/` are git-ignored, so the
training file, the trained model, the simulation tables and every stored prediction
are built locally by the steps above. Two things degrade until step 4 has run: the
ML layer is skipped ("No trained model"), and line restating falls back to a plain
normal curve (a warning says so).

## Running

```bash
python run_pipeline.py                    # NFL (the default): every slate through the next Sunday's week
python run_pipeline.py --sport ncaaf      # college; needs CFBD_API_KEY
python run_pipeline.py --sport both
python run_pipeline.py --model both       # baseline and ML (the ML needs a trained model)
python run_pipeline.py --date 2026-09-19
python run_pipeline.py --skip-ingest      # re-predict from stored data
python run_pipeline.py --fresh-odds       # bypass odds cache (costs quota)
```

With no `--date`, the runner picks the next date that actually has unplayed
games, so a run on a Tuesday still shows Sunday's slate. Without `ODDS_API_KEY`
the live-lines step is skipped with a warning and the run continues.

On an NFL Sunday, `python run_sunday.py --watch` runs the whole refresh once
per kickoff window, so the inactive lists are picked up before each set of
games starts. See [Gameday inactives](#gameday-inactives-sundays).

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
cd dashboard && npm ci && npm run dev          # http://localhost:5174
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
- **A nullified penalty consumes a down.** Real football replays 69.8% of them
  and consumes almost none; the engine advances the down regardless, which
  shortens every drive and is the measured cause of its pass-attempt
  shortfall (`python -m src.simulate_nfl --calibrate` prints drive outcomes,
  series survival and down-state progression against real play-by-play).
  `PENALTY_REPLAY=1` switches to replaying the down; it is off by default
  until the calibration comparison has been reviewed, because it changes
  simulated output and makes stored `game_simulations` and any props ranked
  against them stale.
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

Open `http://localhost:5174/live.html` with the dashboard dev server running.
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
python -m src.train_model --sport nfl --holdout 2025     # train + backtest on the 2025 season (the numbers below)
python -m src.train_model --sport nfl                    # default: holds out the LATEST season, i.e. the one in progress
python run_pipeline.py --model both                      # baseline and ML
```

`--holdout` matters. With no flag the holdout is the newest season in the
training file, which during a season is a partial one (151 games of 2026 on
2026-11-20), so the printed numbers change week to week. `--holdout 2025` trains
on 2016-2023, validates on 2024 and scores 2025, and is what the tables below use.

`train_model` **saves the model it trains** to `models/nfl_margin.json`, replacing
the one the pipeline serves. To reproduce the backtest without touching a model
you are using, run it in a separate clone.

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

### Results: 2025 holdout, never used in fitting

Reproduce with `python -m src.build_training --sport nfl --start 2016` then
`python -m src.train_model --sport nfl --holdout 2025`. The numbers below are that
command's output on 2026-11-20 (2,191 training games 2016-2023, 285 validation
games 2024, 285 holdout games 2025).

Early stopping chooses the number of trees, which makes whatever set it watches
part of fitting. The season before the holdout is therefore carved out as a
validation set, and the holdout is touched exactly once, at scoring time.

Mean absolute error in points of margin, NFL 2025 (285 games):

| | MAE | vs the closing line | Weeks 1-4 (64 games) |
|---|---|---|---|
| **Closing line** | **9.670** | | 8.844 |
| `fundamentals` | 10.150 | +0.480 (worse) | 9.040 |
| `with_market` | 9.610 | -0.061 | 8.764 |

Against the spread on the same 285 games (break-even at -110 is 52.4%; p-values
corrected for the ten model-by-threshold tests):

| Edge | `fundamentals` | `with_market` | corrected p |
|---|---|---|---|
| >= 0.0 | 142/285 = 49.8% | 151/285 = 53.0% | 1.000 / 1.000 |
| >= 2.0 | 69/138 = 50.0% | 52/88 = 59.1% | 1.000 / 1.000 |
| >= 3.0 | 44/94 = 46.8% | 21/37 = 56.8% | 1.000 / 1.000 |
| >= 4.0 | 25/56 = 44.6% | 12/17 = 70.6% | 1.000 / 0.666 |
| >= 6.0 | 7/19 = 36.8% | none | 1.000 |

**Conclusion: neither model beats the closing line.**

- `fundamentals`, the only model that can disagree with the market, is 0.48
  points worse than the line and sits at 50% or below against the spread at
  every threshold.
- `with_market` is 0.06 points better than the line on 285 games. That is the
  line with a small correction. No significance test was run on that margin
  difference, and it does not turn into a spread edge: no threshold survives the
  correction for multiple comparisons.
- It does not hold up on newer games. Holding out the 2026 season to date
  instead (`python -m src.train_model --sport nfl`, 151 games on 2026-11-20):
  closing line 9.573, `fundamentals` 9.957, `with_market` 9.908. Both are worse
  than the line.

The college model was not re-run for this update. Its last stored result
(2026-09-12, 762 games of 2025): closing line 11.846, `fundamentals` 13.19,
`with_market` 11.88. Neither beats the line there either.

### Live record, 2026 season

```bash
python calibration/live_record.py                 # current season, both models
python calibration/live_record.py --season 2026 --json live_record.json
```

Read-only: the store is wrapped so that any write raises, and nothing is graded
or refreshed (`python -m src.grade` prints a fuller report but writes grades to
the store). It counts every finished, non-tied game whose stored prediction was
generated before the stored kickoff, and compares with the line stored with that
prediction. Each game and model has one stored row, the last pregame run.

Output on 2026-11-20 (weeks 1-10; 140 graded games per model; 9 finished games had
no pregame prediction and are not counted):

| | Winner accuracy | Brier | Log loss | Margin MAE |
|---|---|---|---|---|
| `baseline-v1` | 61.4% | 0.2343 | 0.6642 | 10.77 |
| `ml-v1` | 67.9% | 0.2164 | 0.6246 | 9.90 |
| Reference | market favourite 68.8% | constant 50%: 0.2500 | constant 50%: 0.6931 | stored line 9.56 / 9.57 |

Calibration, by confidence in the side picked (predicted, then how often that side won):

| Confidence | `baseline-v1` n | predicted | actual | `ml-v1` n | predicted | actual |
|---|---|---|---|---|---|---|
| 50-55% | 29 | 52.9% | 55.2% | 32 | 52.7% | 53.1% |
| 55-60% | 27 | 57.6% | 48.1% | 23 | 57.4% | 65.2% |
| 60-65% | 18 | 62.1% | 66.7% | 27 | 62.5% | 70.4% |
| 65-70% | 19 | 67.6% | 68.4% | 17 | 67.9% | 76.5% |
| 70-80% | 31 | 75.4% | 67.7% | 36 | 74.7% | 77.8% |
| 80%+ | 16 | 84.2% | 68.8% | 5 | 82.4% | 60.0% |

What it says, plainly: both models are better than a coin flip and **neither
beats the market** on winners or on margin. The baseline is overconfident above
70%. The bins are small (5 to 36 games), so the calibration table is a description,
not a fitted curve.

### A result that did not survive scrutiny

An earlier version of this backtest reported 65.1% ATS at edge >= 3 with
p=0.047, marked SIGNIFICANT. It was wrong, for two compounding reasons:

1. The holdout season was being used as the early-stopping `eval_set`, so the
   model was tuned on the season used to judge it.
2. No correction was applied for testing ten model/threshold combinations.

Fixing both dropped that bucket to 58.3% with a corrected p of 1.000.
(Note, 2026-11-20: 58.3% was the figure when this was written. The current
rebuild, `train_model --sport nfl --holdout 2025`, gives 56.8% for the same
bucket, 21 of 37, corrected p still 1.000; see the table above.) The
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

## Data sources and terms

**The terms notes below are UNVERIFIED.** Nobody read the providers' current
terms-of-use pages when this section was written (2026-11-20). The notes come from
this project's own log and from general knowledge of these services, and they may
be wrong or out of date. **If you use, fork or publish this project, read each
provider's current terms yourself.** This is not legal advice.

| Source | Used for | Access | Terms note (unverified) |
|---|---|---|---|
| nflverse, via `nfl_data_py` | schedules, play-by-play, weekly injuries, snap counts, rosters, depth charts | open files on GitHub, no key | open data project; check its licence and attribution requirements |
| Open-Meteo | kickoff-hour weather | public API, no key | the free API is offered for non-commercial use with attribution |
| The Odds API | game lines, player props, anytime-TD prices | API key (free tier exists) | the key is personal; redistribution of raw odds is likely restricted |
| **ESPN** (`site.api.espn.com`, `sports.core.api.espn.com`) | injury feed, gameday rosters / inactives, final scores, live game state | **unofficial, undocumented endpoints; no key, no agreement** | ESPN publishes no public API or terms for these endpoints. The code sends a browser User-Agent and fetches over `urllib` because ESPN rejects other clients. Access can change or stop at any time, and automated use may not be permitted |
| Sportradar | player-prop lines (P61 / P62 experiments, ended 2026-10-30) | trial API keys | trial data is licensed for evaluation; the project's log flags that holding several trial keys may breach the trial terms (P65). Not used by the weekly routine |
| FantasyPros | one read-only check of per-day practice data (P47) | API key, free tier | not used by the pipeline |
| CollegeFootballData | college games, ratings and lines | API key | college is not part of the weekly routine |
| NFL team sites and NFL.com | official injury reports and inactive lists | **read by hand, never scraped** | the project's log records that team-site terms forbid automated collection (P47), so nothing here fetches them |
| Anthropic API | game Q&A and written explanations | paid API key | not a data source; game numbers are sent to it as context |

What is and is not in this repository:

- `data/` (the database, caches of API responses, odds, archives) and `models/` are
  git-ignored. No raw provider data is meant to be committed.
- The calibration log and the report cards under `calibration/` quote derived
  numbers (lines, injury statuses, player results) from these sources.
- Test fixtures: `tests/fixtures/sr_props_synthetic.json` is synthetic (invented
  ids, lines and prices), and so is
  `tests/fixtures/roster_all_qbs_inactive_synthetic.json` (invented ids and names;
  the regression case for a bad inactive list, P42).
- Two captured responses (a Sportradar trial payload and an ESPN gameday roster) were
  tracked test fixtures until 2026-11-20, when synthetic ones replaced them.

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
