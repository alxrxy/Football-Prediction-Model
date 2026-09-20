# Calibration log

Running record of graded slates and the model changes they suggest. **Nothing
in here has been applied to the model** unless its status says so. One slate is
far too few games to recalibrate on, so each proposal is logged with the
evidence behind it and the test it has to pass, and evidence is added to it
week by week.

Newest entry first. Per-game tables live in `calibration/<date>_<sport>.md`.

## How to add an entry

```bash
# CFB
python -m src.grade --sport ncaaf --refresh          # pull finals, fill actual_* columns
python calibration/analyze_slate.py 2026-09-19 calibration/2026-09-19_ncaaf.md
# NFL
python -m src.grade --sport nfl --refresh --since 2026-09-20
python calibration/analyze_nfl_slate.py 2026-09-20 calibration/2026-09-20_nfl.md
python calibration/grade_props.py 2026_02_WAS_DAL calibration/2026-09-20_nfl_WAS_DAL_props.md   # any simulated game
```

Then add a dated section below, add a row to the season-to-date record, and
update the tracker: add the slate's evidence to each proposal, and flip a
status only when its adoption test is met.

## Proposal tracker

| ID | Proposal | Kind | First seen | Evidence so far | Adoption test | Status |
|----|----------|------|------------|-----------------|---------------|--------|
| P1 | Charge only injury rows from the latest pull per team/week | bug fix | 2026-09-13 | 29 stale NFL rows; would flip 2 of 13 value flags today. Graded 9/13: the two flags it created (DET, GB) both lost ATS, which says nothing about a correctness fix | none needed; it's a correctness bug | **applied 2026-09-13** (`features.latest_injury_report`); NFL slate re-run before kickoff |
| P2 | Stop pricing unknown-snap QBs at 35% of a starter | logic | 2026-09-13 | 8/13 NFL games carry a ~2.1 pt charge for a backup/rookie QB. Graded 9/13: 5 games affected; removing the charges flips 2 leans (ATL@PIT, NO@DET), both to wins, 3-10 → 5-8 | rebuild NFL training with the change; holdout MAE vs line must not get worse | proposed |
| P3 | Replace the flat FCS proxy (-28); grade proxy games separately | logic + reporting | 2026-09-12 | proxy games: model MAE 17.1 vs market 10.8, ATS 13-20 | proxy-game MAE within 2 pts of the market over 100+ games | proposed |
| P4 | Make confidence tiers discriminate: SP+/Elo agreement, early-season demotion | logic | 2026-09-12 | 47/47 rated CFB games "high"; 9/13 NFL: 13/13 "high" in both models and 13/13 sims. Season: "high" = every rated game (26-34 ATS), "low" = only FCS proxies, "medium" never assigned. The agreement signal did *not* carry to NFL: baseline/ML agree 1-6, disagree 2-3 | "high" beats "medium" ATS over 200+ graded games | proposed; agreement signal now 18-20 agree / 8-13 disagree across both sports, i.e. unproven |
| P5 | Upper edge cap for early-season edges (large edge = stale rating) | threshold | 2026-09-12 | CFB rated \|edge\| 6-10 went 2-7. NFL wk 1 \|edge\| ≥ 6 went 0-4, MAE 15.6 vs market 8.1; NFL ratings are ~94% prior season this week | \|edge\|>8 (CFB) / >6 (NFL) in weeks 1-4 loses ATS over 60+ games | proposed; extended to NFL 2026-09-14 |
| P6 | CFB home field 2.4 → ~2.8 | weight | 2026-09-12 | slate: model leaned away 30/47, -2.1 pts vs market; history: market-implied HFA 3.2 (2017-25) but 0.5 in 2025 | mean signed edge on non-neutral games < -1.0 across 4+ weeks | watch |
| P7 | Do not use the CFB ML model's margins until its compression is explained | investigate | 2026-09-12 | mean \|ML margin\| 9.5 vs actual 24.7; MAE 20.6. *Correction 09-15: the "Georgia −27 vs market −69.5" example below used an in-play line (P15); DK closed −40.5* | n/a, diagnose first | investigate |
| P8 | NFL: consider the ML margin (or a blend) as the headline number | model selection | 2026-09-14 | 9/13: ML SU 10/13 vs baseline 6/13, MAE 11.46 vs 13.10, Brier 0.214 vs 0.256; ATS both poor (4-8, 3-10) | ML MAE below baseline MAE over 4+ NFL weeks (~60 games), and not worse vs market | watch |
| P9 | NFL injury term: check its magnitude | weight | 2026-09-14 | 9/13: \|injury adj\| ≥ 1 went 0-5 ATS, MAE 12.3 vs market 8.8; corr(injury term, cover residual) −0.00. 9/14 DEN@KC: term −0.95 toward DEN (−2.63 with real snap shares, P14), market already −2.5 with the same report; lost | fitted coefficient on the injury term (actual − market ~ injury) positive and significant over 100+ games. **Exclude 2026-09-17 DET@BUF**: its term (1.56) was set before P20, which understates DET's side (Pacheco on IR uncounted), and before P10/P21 — four players priced at the flat 0.55 with the official inactives already public. The fixed code would not produce that number, so the game cannot speak to this coefficient | watch |
| P10 | Props: apply game-day inactives before simulating | data | 2026-09-14 | DAL@NYG: 4 projected players recorded nothing (N. Harris 5.3 car, Beckham, Cambre, Abanikanda), none on the injury list; Singletary took 10 touches + TD unprojected. **Widened 2026-09-17 (DET@BUF):** this is not a sequencing problem. There is no inactives ingestion path anywhere in the pipeline, and the ESPN feed structurally cannot supply one — a full league pull at 22:50Z returned only `Active` (614), `Questionable` (134), `Injured Reserve` (40), `Out` (9), `Doubtful` (3), with no gameday inactive designation. `ingest_injuries._status` would discard one anyway (see P20, P21). Consequence at T-75 min, with the official list already public: DET@BUF still priced 4 players at the flat questionable/limited 0.55 (D.J. Reed 0.75 pts, Cole Bishop, T.J. Sanders, Ty Johnson) when each was by then resolved to 0 or 1 **Source found and confirmed 2026-09-19:** the ESPN core API per-competition roster flags inactives `didNotPlay` (DET@BUF: 8 BUF / 9 DET, incl. T.J. Sanders and Ty Johnson); 404 before posting. Week-1 payoff: 6 inactive projected players, 1.4% of projected touches (Kamara, N. Harris). See the 2026-09-19 P10 entry | acquire a real inactives source first (ESPN gameday roster endpoint or equivalent), then re-sim after it lands; track "projected, no stats" rate weekly | **built and validated on replay 2026-09-19; not yet run live.** Criteria 1-5 pass; criterion 6 (posting time) needs a live Sunday. New `inactives` table: paste `db/PASTE_INTO_SUPABASE.sql` to create it upstream (the local mirror is used until then). See the 2026-09-19 P10 build entry |
| P11 | Props: rushing volume bands too narrow (game script) | investigate | 2026-09-14 | DAL@NYG: rush att in the 50% band 2/8, rush yds 1/8; team rush att −8 (trailing DAL), +9 (leading NYG). DEN@KC: leading KC 38 rush att vs median 25 (p90 31), trailing DEN 15 | 50% band hit rate for rush att in 40-60% over 10+ simulated games | **engine change applied 2026-09-15** (game-script play-calling): calibration rush att by final margin 21.4 → 32.5 vs real 20.7 → 31.6, was flat 24.1 → 27.9; league totals within 3%. The band test itself still needs 10+ graded games |
| P12 | Run pregame sims before the first kickoff | process | 2026-09-14 | 12/13 week-1 sims written 23:11Z, after kickoff, so only DAL@NYG props are gradeable | n/a | proposed |
| P13 | NFL prior-season rating must be QB-conditional (weight the prior by the expected starter's games, or add a QB-change term) | logic | 2026-09-15 | DEN@KC: KC's 2025 rating includes 146 backup-QB plays at −0.347 EPA; Mahomes-only prior moves KC +2.9 pts, edge −3.46 → −0.56, flag off. Scope: 11/32 teams shift ≥ 1 pt from non-primary starts (NYJ +5.1, IND +3.8, KC +2.9) | rebuild NFL training with QB-conditioned prior; holdout MAE vs line must not get worse, and weeks 1-4 MAE should improve | **tested 2026-09-15, not adopted.** Starter-games prior (≥ 4 starts): baseline wks 1-4 2016-25 MAE 10.46 → 10.56 (moved games 10.08 → 10.53); ML 2025 holdout MAE 10.08 → 10.10, wks 1-4 8.98 → 9.13. Fails both parts. Code kept behind `QB_CONDITIONAL_PRIOR=0` |
| P14 | Snap-share fallback is per dataset, not per player | bug fix | 2026-09-15 | `_snap_shares` stops at 2026 once it has > 500 rows, so teams that hadn't played and players who sat out week 1 get no share: 78/154 latest NFL injury rows; every DEN/KC row. DEN@KC injury term −0.95 → −2.63 with real shares | none needed; correctness bug | **applied 2026-09-15** (`ingest_injuries.merge_snap_shares`); NFL rows without a share 78/154 → 32/161 on the week-2 pull |
| P15 | Never grade a prediction made after kickoff; never store in-play lines | bug fix | 2026-09-15 | 19 of 80 CFB predictions on 09-12 were generated at 18:37Z, after 16:00–17:00 kickoffs, against in-play Odds API lines (Georgia −69.5 vs DK close −40.5). The old rule flagged 8 of them, 6-2. Pregame-only flagged record is 15-25, not 21-27 | none needed | **applied**: predict-side guard since 2026-09-14 (`ba6d7f3`); `ingest_odds` skips in-play events and CLV marks late leans `after_kickoff`, 2026-09-15 |
| P17 | Props: model each player's own efficiency and target share before trusting the prop ranking (research Stage 4) | logic | 2026-09-15 | Week 2, first pull (1-5 books, Tuesday): 46 props priced, top 10 gaps 17-25 pp, 15 more held out past 25 pp. One-sided pattern: star receivers under (J. Williams rec yds sim 37 vs 56.5, St. Brown rec 5 vs 7.5, Nabers rec 3 vs 5.5); QB pass yds off both ways (Goff 222 vs 265.5, Stafford 285 vs 242.5). The engine gives every player league-typical yards per play and splits targets by depth-chart share **Confirmed as a cause 2026-09-18 (week-1 actuals, n=174 receivers with 8+ games in 2025):** yards per target are drawn from league plays by situation, so efficiency is compressed toward average. Top tercile by own 2025 yds/target (9.12): sim 7.63 vs week-1 actual 8.56, yards 0.80x actual; bottom tercile (5.33): sim 6.60 vs 6.47, 1.24x. Zero-sum against calibrated team pass yards, so the priced starters lose what the low-efficiency receivers gain **Walk-forward 2026-09-19 (2025 weeks 3-18, criteria written down first):** outcome-aware crediting with shrunk per-player rates improves out-of-sample rec yds MSE −1.28% (7/8 weeks, CI touches 0) and receptions −2.91%, but narrowly fails the tercile criterion. More importantly, the current engine is already within ~3% per tercile given targets (0.97 / 1.01), so the 0.80 / 1.24 compression above does not reproduce: efficiency given targets is a 1-3% effect, not the source of the props under-bias. See the 2026-09-19 P17 entry | prop gaps centre near 0 across a week (mean \|gap\| < 8 pp), then prop CLV ≥ 0 over 65+ leans | **not building as scoped** (user, 2026-09-19): design walk-forward done, small and marginal gain, and the premise did not reproduce. The open question it raised is P30 |
| P18 | Simulator: first-and-short (goal-to-go) conversion far below real | bug | 2026-09-16 | Engine diagnostic, `--calibrate` over 20k league-average sims: 1st & 0-2.5 converts .323 vs real .486 (y/p 0.34 vs 0.43); 1st & 2.5-5.5 .216 vs .329 (y/p 1.41 vs 2.64); 1st & 5.5-9.5 .119 vs .163. On 1st down a to-go under 10 means the ball is inside the 10, so these are almost all goal-to-go snaps. Consistent with sim TD share .196 vs real .220. At ~1% of all snaps it does **not** explain the 11% plays-per-drive shortfall, which was measured separately and traced to possession count | 1st-down conversion within 3 pp of real in each sub-10 distance bin, and sim TD share within 1 pp of real | proposed; **deliberately deferred 2026-09-16** so it does not pull focus from the punt / three-and-out investigation |
| P16 | Baseline model weight to 0 if its NFL leans show no CLV | weight | 2026-09-15 | backfill: 75 pregame baseline leans −0.22 pp (t −1.22), but 61 are CFB and priced at an assumed −110 against DK's close; NFL n=14 | NFL lean CLV ≤ 0 at 65+ NFL leans (≈ week 5) → set `MODEL_MARKET_WEIGHT=0` for the baseline | watch |
| P19 | A partial injury pull must not retire other teams' reports: `latest_injury_report` keeps the latest pull *per source*, not per team/week as P1 intended | bug fix | 2026-09-16 | The 19:46Z week-2 nflverse pull held only BUF/DET (8 rows, the Thursday game). Because it was the newest nflverse pull, the week-1 nflverse report (91 rows) was silently dropped for the other 30 teams, which fell back to ESPN only. This time it helped by accident: the week-1 statuses were stale, e.g. Penix OUT, and CAR@ATL moved 0.60 → 4.77 when that row fell away. The same mechanism can just as easily drop a current report for most of the league in a future week, with no warning | none needed; correctness bug. Test: a pull covering 2 teams leaves every other team's latest report in force | **applied 2026-09-16** (`features.latest_injury_report`). Kept apart from the engine-change sequence because it is a data-pipeline correctness fix. For nflverse the report is now the latest week only, and within that week each team's latest pull; ESPN is unchanged (latest whole pull). Last week's statuses are deliberately not carried forward, so the 9/16 outcome (30 teams on ESPN until they file week 2) was the right one. Validated before landing: identical 137 selected rows on the live table, and injury_adj unchanged on all 16 week-2 games. The old code fails the new partial-pull test. Residual: a team whose whole report clears mid-week writes no rows, so its earlier same-week rows stay in force |
| P20 | ESPN "Injured Reserve" status is discarded, so IR'd starters vanish instead of counting as out | bug fix | 2026-09-16 | `ingest_injuries._status` keeps only out/doubtful/questionable/probable. HOU LB To'oTo'o (0.88 snaps) went to IR 09-16 and dropped out of the injury layer, instead of costing HOU ~1.06 pts. **Scope measured 2026-09-17:** the 22:50Z league-wide pull carried **40** players at `Injured Reserve`, every one of them silently dropped — this is league-wide, not a one-team case. Tonight's DET@BUF: Isiah Pacheco (DET, IR) contributed nothing to the injury layer, so DET's burden is understated and the true term favours BUF by more than the 1.56 served | none needed; correctness bug | proposed (after P19); **queued for the week of 2026-09-22** alongside 2A/P23 |
| P21 | ESPN rows carry no practice participation, so every Questionable player plays at a flat 0.55 | logic | 2026-09-16 | Penix: full practice, charged 2.52 (0.80 → 1.12). Terrell: DNP, charged 0.70 (0.25 → 1.17). Burrow: "says he will play", charged 2.70. ESPN's `shortComment` states the practice level in plain text | practice-aware play probability does not worsen NFL injury-term fit (P9) | proposed (after P19) |
| P22 | NFL power rating: no opponent adjustment; defense regressed the same as offense (×0.75); prior season carries ~94% in week 2 | logic | 2026-09-16 | CIN@HOU baseline −16.37 vs market −2.5. Of the +10.93 rating gap, +12.98 is the 2025 defensive EPA gap alone, −0.98 offense, −1.08 week 1. The only value flag on the week-2 slate comes from this. See also P5, P13 | rebuild with separate off/def regression (and opponent adjustment); weeks 1-4 and holdout MAE vs line must improve | proposed (after P19) |
| P23 | Usage shares: drop scrambles and kneels from carry shares (issue 2A) | bug fix | 2026-09-16 | `sim_data._usage_events` counts every `rush_attempt`, including 1,224 scrambles and 487 kneels (2025-26), while the engine separately credits every scramble to the QB. Read-only week-2 re-sim, 10k sims, 195 priced props: QB rush att 5.42 → 3.33 per team-game (real 2025 3.25), RB carries 20.54 → 22.61 (+10%), team rush att/yds and game totals/margins unchanged to 3 decimals. RB rush yds P(over) 0.329 → 0.393 vs market 0.500, about 40% of the RB gap. Receiving unchanged. See the 2026-09-16 entry | QB rush att ≈ 3.3 per team-game; RB carries up ≈ 10%; team rush totals, game totals and margins unchanged; rushing props correction re-fit with separate QB and RB offsets (P26) | **applied 2026-09-18** (moved ahead of the 9/22 plan at the user's call). Validated before landing, read-only week-2 re-sim: QB rush att 5.41 → 3.26 per team-game (real 3.25), RB carries 20.47 → 22.53 (+10.1%), team rush att/yds, game totals and margins identical to 4 decimals. See the 2026-09-18 entry |
| P24 | Usage shares: QB-specific scramble rate (issue 2B) | logic | 2026-09-16 | The engine credits scrambles at the league rate (5.9% of dropbacks) whatever the QB (Goff 0.9%, Stafford 1.2%). With P23 applied, QB rush yds split both ways: runners well under (Lamar Jackson P(over) 0.146, Daniels 0.219), pocket QBs still over (D. Jones sim 19.4 vs 8.5 line, Purdy 21.6 vs 13.5) **Design walk-forward and read-only engine prototype 2026-09-19 (criteria written down first): all pass.** Scramble rate is a stable QB trait (r 0.87). A shrunk per-QB rate cuts scramble MSE 25.8% out of sample (8/8 weeks). The per-offense sampler factor leaves dropbacks, points and margins unchanged and moves QB rush att toward real for pocket QBs (err 1.22 → 0.26) and runners (1.51 → 0.64); QB rush-yds |gap| 0.163 → 0.116. See the 2026-09-19 P24 entry | QB rush att and rush-yds P(over) move toward real and market for both running and pocket QBs, with dropbacks, points and margins unchanged (**revised 2026-09-19** from "no change to team totals": running QBs' teams are meant to swap some pass attempts for scrambles). Full criteria in the 2026-09-19 P24 entry | **applied 2026-09-19** (user-approved build): per-offense scramble factor in the sampler, pregame and live. Re-validated with the same checks: production reproduces the prototype exactly, all criteria pass. Pass-yds offset refitted (−0.0212, provisional under P29). QB rushing props still held out, pending the user's decision. See the 2026-09-19 build entry |
| P25 | Usage shares: use backups' own history beyond the playing slots; FB prior is zero (issue 1) | logic | 2026-09-16 | `blend_roles` gives players beyond QB1/RB2/WR3/TE1/FB1 only the slot average: 76 have their own red-zone share at least 2x that average (TE2s Njoku, Freiermuth, Mayer, Kmet all a flat 3.2%). D. Waller (CAR TE3, 14.1% of targets) is simulated at 2.3%, falls under `MIN_TOUCHES` and drops out of the box score. FBs are zeroed even with history (Heyward 14% of goal-line carries) | **revised 2026-09-18:** per-player target and carry shares closer to realised week-by-week shares (walk-forward, squared error). The original second clause, "starters not pushed further under their prop lines", assumed starters' shares were too low; the 2025 backtest shows they are already slightly too high (WR starters +5%, TE +3% against realised). A fix that corrects toward reality is the right direction even if it moves starters further under the market; that residual gap is the receiving investigation's to explain, not this item's | **applied 2026-09-19** as `k32+fb` (moved ahead of the 9/22 plan at the user's call): `sim_data.BACKUP_HISTORY_GAMES = 32`, and an FB with no slot prior keeps his own history. Re-validated before landing with the shipped `blend_roles`: identical shares to the 9/18 reference (max diff 0.0), and the 2025 walk-forward reproduces every locked number (tgt_all −4.5% 15/16 weeks, car_all −2.1% 8/16, tgt_rz −0.6% 15/16, car_gl −0.8% 10/16; weeks 11-18 −5.3 / −3.0 / −0.8 / −1.7). Live check: game totals, margins and team volume identical. Receiving offsets refitted (P26). See the 2026-09-19 entry |
| P26 | Props bias correction: fit offsets by position, not one per category | logic | 2026-09-16 | The single rushing offset (+0.346) hides two biases pulling in opposite directions: QB rush yds lean over (P(over) 0.649, 7/9 overs), RB rush yds lean under (0.329, 2/24). Their mean (0.416) looked like one under-bias. Receiving and passing corrections may hide the same thing, and not moving under P23 is no evidence either way | rebuild with P23: separate QB/RB rushing offsets; before trusting the receiving and passing offsets, check each by position (WR/TE/RB for receptions and rec yds; pocket vs running QBs for pass yds) and split any that disagree | **rushing half applied 2026-09-18:** RB offset +0.107 (n=39, mean-fitted, starters still under); QB rushing gets no offset and is held out of the ranking as an engine defect until P24, because a QB offset averages runners (far under) with pocket passers (far over). Receiving and passing by-position checks still open (receiving investigation, 2026-09-18). **Receiving half applied 2026-09-18 (after P27):** receptions stay one offset (+0.510, n=127; WR/TE/RB intervals overlap); receiving yards split by position (WR +0.418 n=63, TE +0.553 n=28, RB +0.212 n=28; RB's 90% CI +0.08 to +0.34 excludes the category's +0.40). **Passing refitted 2026-09-18 (evening):** −0.093 → **+0.005** (n=20, raw −0.12pp; the 9/16 fit came from the 25-prop first pull). One offset: the pocket-vs-running split was not tested, and with the category mean on the market there is nothing for it to separate yet. **Caveat 2026-09-19:** that pass-yds fit is provisional. P29 dropped about a third of starting QBs from its sample; refit after P29. **Refitted 2026-09-19 after P25:** receptions +0.5104 → +0.5517 (n=138); rec yds WR +0.4560, TE +0.5586, RB +0.2389 (RB interval +0.11 to +0.36 still excludes the category +0.43, so the split stays). **RB rushing refitted the same day at the user's call:** +0.107 → **+0.195** (n=41, raw −4.32pp, 90% CI +0.02 to +0.39), because k32+fb moves carries from RB1/RB2 to RB3+. **QB rushing offset added 2026-09-19 after P24:** −0.182 (n=21), no split needed; QB rushing props ranked again. See the 2026-09-19 QB rushing entry |
| P27 | Engine: throwaways are credited as receiver targets | bug fix | 2026-09-18 | 4.25% of library pass attempts (2023-25) have no intended receiver and are all incomplete, yet `simulate._Game._credit` gives every attempt a target. Catch rate over all attempts is 0.645 and the sim's week-1 starter catch rate is 0.643; real catch rate over true targets is 0.674 (week-1 actual 0.676). Sim team targets 32.2 vs actual 29.6. See the 2026-09-18 receiving entry. **Corrected 2026-09-18 (fix run):** the diagnosis said this accounted for the ~4-5% receptions shortfall. It cannot: a throwaway was credited as an *incomplete* target, so removing it lowers targets and nothing else. Receptions and receiving yards per player are unchanged by construction, and every priced prop's raw P(over) was unchanged (324/324). Team receiving is calibrated (sim 20.33 completions / 30.03 true targets per team-game vs 2025 20.62 / 30.70, week 1 20.47 / 29.74), so the per-player receptions shortfall is in how catches are split between players (P17, P25), not P27 | sim catch rate ≈ 0.674; team targets ≈ 95.8% of pass attempts; QB pass att/cmp/yds, team totals, game totals and margins unchanged; receiving offsets refitted | **applied 2026-09-18** (`TABLES_VERSION` 5: `targeted` library field; `_credit` still draws a receiver for every attempt, so the random stream is untouched, then drops the credit on throwaways). Validated read-only on the 15 weekend games, 10k sims, against a same-code control with the field stripped: catch rate 0.6487 → **0.6771** (library over true targets 0.6773), targets/attempt 1.000 → **0.9581**, QB pass att/cmp/yds per player, team totals, game totals and margins identical (max diff 0.0). Receiving offsets refitted (P26). See the 2026-09-18 P27 entry |
| P28 | Starter designation: when the starter is out or disputed, the sim's next QB follows the depth chart while the market prices a different passer (SEA: Lock; ATL: Cooper Rush) | investigate | 2026-09-18 | Week 2, SEA @ ARI. Books price only Lock for SEA pass yds (207.5), with no Sam Darnold line posted. The stored sim has Darnold QB1 (17.8 att, median 172 yds) and Lock QB2 (12.0 att, **median 0**, mean 93), so the raw sim reads Lock's under at 0.746 against a market 0.500, and he sits **#2 on the ranked list**. His rushing prop (6.5) is held out as QB rushing. Looks like a depth-chart / starter-designation or injury-status mismatch, distinct from the usage and efficiency items. Not diagnosed **Second team, 2026-09-19 (targeted re-pull):** with Penix now OUT, books price **Cooper Rush** as ATL's passer (183.5, 5 books) and post no Tua Tagovailoa line, while the sim starts Tua (QB2, 18.3 att, median 156) with Rush as QB3 (12.0 att, **median 0**). So it is not SEA-specific: the sim's next man up follows the depth chart, and the books' does not. Rush's pass-yds prop is currently dropped by P29, and his rushing prop is held out as QB rushing, so nothing about it shows on the page **ATL game-level check, 2026-09-19 (read-only):** inconsistent, and the CAR@ATL numbers correspond to neither QB. (1) The sim cannot disagree with the baseline at game level: `anchored_simulation` pins the margin to the baseline's; QB identity only routes box-score credit. So the question is the baseline's −5.59 Penix charge (1.0 × 0.932 snap share × 6.0, a generic starter-out value that never asks who replaces him). (2) ATL's rating is ~94% 2025 ATL offense, whose dropbacks were split Cousins 283 (−0.023 EPA/db) / Penix 303 (+0.035): mix +0.007, so the rating is only about half Penix. **Cooper Rush started ATL's week-1 game** (Penix did not play; 57 plays, −0.321 EPA/play). (3) On the same scale (EPA/db difference × 0.603 dropbacks/play × 63), relative to the rating: Tua +0.4 (2025) to +4.3 (2024-25); Rush −7.3 (2024-26, 404 db, −0.185 EPA/db, 43rd of 44). So the correct charge is about 0 if Tua starts, and about −7.3 if Rush starts. The −5.59 charged is neither. The sim's own mix (Tua 0.6 from an nflverse row with no status, Rush 0.4) implies about −0.3 to −2.7. (4) Consequence: if Rush starts (the market's view, and who started week 1), ATL is ~1.7 pts too strong, so ≈ CAR +1.5 vs the market's CAR −2.5, with no flag either way. If Tua starts, ATL is ~6-10 pts too weak and the true number is an ATL edge. The edge's sign depends on the QB, and the served number reflects neither. The ML model uses the same generic `qb_availability_loss`. **Labelled 2026-09-19 at the user's call** (see status) | the sim's QB1 for every team matches the market's priced passer (or the confirmed starter) before props are ranked; a priced QB2 with sim median 0 is flagged, not ranked | proposed; **queued for the week of 2026-09-22** (user, 2026-09-19: log, don't fix tonight). Affects **SEA and ATL**, not just SEA. **First step when picked up: check the ATL game-level prediction for impact. It has not been checked.** The sim runs ATL with Tua starting (depth-chart QB2) while the market prices Cooper Rush, and the baseline charges Penix out at 5.59 pts against an unexamined replacement, so the CAR@ATL margin (baseline ATL −0.2, ML CAR −1.6, market CAR −2.5) may carry this error. Only after that, the props side. SEA's Lock pass-yds prop is labelled on the page via `props.KNOWN_DEFECTS`; ATL has no label, because Rush's pass-yds prop is dropped by P29 and his rushing prop is held out as QB rushing. **CAR@ATL labelled 2026-09-19:** `export_dashboard.KNOWN_GAME_ISSUES` puts a "known issue, treat with caution" caveat on the game view and a tag on the games list, and passes it into the game Q&A context; `props.KNOWN_DEFECTS` gained a team-wide key, `(game_id, "team:ATL")`, so every ATL prop carries the note. The numbers themselves are unchanged. Remove both entries once P28 is fixed or the game kicks off. **2026-09-19:** Lock's rushing prop is held out via `props.PROP_HOLDOUTS` now that QB rushing is ranked again; remove it together with the KNOWN_DEFECTS entries |
| P29 | Props: `market_view` silently drops a prop when two lines tie for most books | bug fix | 2026-09-19 | `point = median(tied modal lines)`: with an even number of tied lines, the median is a line no book posts (Cooper Rush 182.5 ×2 / 183.5 ×2 → 183.0), no book matches it, and the prop returns None: never ranked or held out, and not counted as unmatched either. **37 of 424** priced player-markets on the 2026-09-19 lines (38/398 on the 9/17 file), and they are skewed to starting QBs' pass yds (Herbert, Mayfield, Purdy, D. Jones, Willis, Stafford/Dart on 9/17). The 2026-09-18 pass-yds offset refit (n=20) and the 9/16 fits were therefore taken on a sample missing these props | every priced player-market either produces a row or is counted as a named exclusion; then refit the pass-yds offset on the full set | proposed; **queued for the week of 2026-09-22** (user, 2026-09-19: log, don't fix tonight). **Knock-on: the live pass-yds offset (+0.005, fitted 2026-09-18, n=20) was fit on an incomplete sample missing roughly a third of starting QBs. Refit it once P29 is fixed; do not treat it as final.** The receiving and rushing fits are exposed too, less heavily (e.g. Rashee Rice, Alec Pierce, Josh Downs, Noah Gray rec yds were dropped) |
| P30 | Why did 2026 week 1 show a 0.80 / 1.24 receiving-yards tercile split when the 2025 walk-forward shows 0.97 / 1.01? | investigate | 2026-09-19 | The P17 walk-forward found the current engine, given each receiver's targets and pre-week category mix, within ~3% per tercile across 2025 weeks 11-18. The 2026-09-18 week-1 check (n=138 starters, one week) measured 0.80x yards for the top tercile and 1.24x for the bottom. Candidates: one-week noise and selection; or the SIMULATED target distribution (who gets how many deep vs short targets, which the walk-forward held at each player's own historical mix) rather than efficiency. Distinct from P17 (efficiency given targets) and P25 (target volume) | to be written into this log when the diagnosis is scoped, before it runs (process rule, 2026-09-19) | proposed; **queued for the week of 2026-09-22**; not started, and deliberately kept out of the 2026-09-19 push (uncertain scope) |

Not proposed: **raising VALUE_EDGE_THRESHOLD on its own.** On both slates the
baseline's edge had no positive relationship to the cover result (CFB w =
+0.05; NFL w = −0.64, flagged 3-7), and a higher threshold keeps the flag's
error while firing less often. The threshold only becomes meaningful after
P3–P5 remove the edges that are just rating error.

*Superseded 2026-09-15:* the points threshold no longer decides flags; Stage 1
does (see that entry). The same caution still applies to it. At a fixed model
weight the blended test is still monotone in |edge|, so what it flags are the
largest disagreements, and those are mostly stale ratings (P5, P13). That is
why the weight starts low and rises only on CLV.

## Season-to-date record (baseline-v1)

| Slate | Sport | Games | SU model | SU market fav | ATS all | ATS flagged | MAE model | MAE market | Tiers assigned |
|---|---|---|---|---|---|---|---|---|---|
| 2026-09-12 | NCAAF | 80 | 64/80 (80%) | 72/80 (90%) | 36-44 (45%) | 18-19 (49%) | 14.13 | 10.84 | 47 high / 33 low |
| 2026-09-13 | NFL | 13 | 6/13 (46%) | 10/13 (77%) | 3-10 (23%) | 3-7 (30%) | 13.10 | 10.73 | 13 high |
| 2026-09-14 | NFL (MNF, DEN@KC) | 1 | 0/1 | 1/1 | 0-1 | 0-1 | 22.46 | 18.50 | 1 high |
| **To date** | | **94** | **70/94 (74%)** | **83/94 (88%)** | **39-55 (41%)** | **21-27 (44%)** | **14.08** | **10.90** | |
| **To date, pregame only** (P15) | | **75** | | | **29-46 (39%)** | **15-25 (38%)** | | | |

The pregame-only row drops the 19 CFB predictions made after kickoff against
in-play lines (they went 10-9, flagged 6-2). It is the honest record of the
old flag.

By confidence tier, to date:

| Tier | Games | SU | ATS | MAE | Market MAE |
|---|---|---|---|---|---|
| high | 61 (47 CFB rated + 14 NFL) | 39/61 (64%) | 26-35 (43%) | 12.42 | 10.97 |
| medium | 0 | — | — | — | — |
| low | 33 (all CFB FCS-proxy) | 31/33 (94%) | 13-20 (39%) | 17.13 | 10.80 |

The tiers are not meaningful yet. "Low" has only ever meant "one side is an
FCS proxy", and those games are mismatches, which is why low beats high
straight up. See P4.

NFL ML model (ml-v1), to date: SU 11/14, ATS 4-9 (1 no-lean; `grade.py`
counts it as a loss, 4-10), MAE 12.08.

---

## 2026-09-19 — P10 built: gameday inactives; validated on replay; not yet run live

**Built.**
- `src/ingest_inactives.py`: scoreboard → one roster call per team → `didNotPlay` players → athlete record for the
  full name (cached). A 404 or no flagged players means "not posted" and nothing is written. Games more than 12 h
  from kickoff, or already final, are skipped (`--replay` takes the whole week and stores nothing).
  `first_seen_at` is kept across pulls, so posting time gets measured.
- **New `inactives` table** (SQLite schema, `db/PASTE_INTO_SUPABASE.sql`, `db.TABLE_KEYS`). It is separate from
  `injuries`, whose key has no source column: an ESPN injury re-pull would otherwise overwrite an inactive row and
  flip the player to active. Until the table exists in Supabase, rows go to the local SQLite mirror through
  `upsert_or_mirror` and are read back with `select_merged`.
- `features.apply_inactives`, applied in `FeatureContext` (baseline, ML features and sims) and in the dashboard
  export. For a team with a posted list: inactive → play probability 0 ("inactive"); a reported questionable /
  doubtful / probable player not on the list → 1.0 ("active"); Out and IR untouched. An unreported inactive is added
  at his snap share, 0 if he has none. Only the report's current week, and the latest pull per team-game, are used.
- Hook: `ingest_injuries.run` (NFL) fetches inactives after the injury report.
- Tests: 13 new checks in `test_injury_report`; all 12 suites pass; the dashboard builds. The game page shows the
  status text ("inactive" / "active") as it does for any other status.

**Validation against the written criteria** (replay of weeks 1 and 2, read-only):

| criterion | result | verdict |
|---|---|---|
| 1. inactives resolve to our players | week 1: 88/91 skill-position (97%); week 2: 4/4. All four P10 DET@BUF players right: T.J. Sanders and Ty Johnson inactive, D.J. Reed and Cole Bishop active. The 3 week-1 misses (Miller Moss, Cambre, Abanikanda) are not on today's depth chart, which is replay staleness rather than the join | pass |
| 2. 404 / empty → nothing written | test | pass |
| 3. precedence rules | tests: inactive 0, not-listed Q/D/P 1.0, Out untouched, unposted team unchanged, a past week's list ignored, latest pull wins | pass |
| 4. DET@BUF rescored | DET −5.45 → −4.23, BUF −4.51 → −4.27. Reed, Maddox, Bishop and DJ Moore Q → active; Sanders, Ty Johnson, Blake Miller, Mahogany and others inactive. Rescored on the current stored week-2 pull; the 9/17 pre-kickoff pull was overwritten | pass |
| 5. week-1 replay | the name join finds 11 projected players inactive, not the 6 by gsis id. The 9 still on the depth chart all go to zero share, it passes down (Kamara → Kendre Miller, Claiborne → DeeJay Dallas), and team shares sum exactly as before | pass |
| 6. posting time | not measurable until a live Sunday; `first_seen_at` records it | open |

Week 1 had 236 inactives across 32 lists (~7.4 a team). Of all 236, 154 match a player in our roles, snap counts or
injury report. The rest have no snaps on record (elevated practice-squad players and deep reserves) and cost
nothing.

**Not yet live:** no list has been stored (no upcoming game has one posted). The first real use is the Sunday
windows.

## 2026-09-19 — P10 design stage: ESPN gameday inactives confirmed; build criteria written down

Read-only diagnosis. No production code.

**Source, confirmed in our environment.** ESPN core API,
`/v2/sports/football/leagues/nfl/events/{event}/competitions/{event}/competitors/{team}/roster`: one call per team,
event and team ids from the site scoreboard (`?week=N&seasontype=2&dates=YYYY`; the date-range form returns 400).
- DET@BUF (final): BUF 55 entries (53 + 2 elevations), DET 56. **`didNotPlay: true` on 8 and 9 players**, exactly
  roster size minus the gameday active limit. Every dressed player has a statistics object and no inactive has one,
  so this is the inactive list, not "took no snaps". DET's list has Blake Miller and Mahogany (ruled out in the 9/17
  snapshot); BUF's has T.J. Sanders and Ty Johnson, two of the four players priced at the flat questionable 0.55 on
  9/17 (P10 evidence).
- `active` is false even for starters, so it is unusable. Use `didNotPlay` only.
- **Before posting, the endpoint returns HTTP 404**, not an empty list (all Sunday games at T−35h). Treat both 404
  and empty as "not posted yet".
- **Posting time not verified by us.** The reference implementation (liddar12/NFL2026 PR #85) reports ~10 h before
  kickoff; the NFL deadline is ~90 min. Only checkable on Sunday morning.
- Entries carry ESPN athlete ids and abbreviated names ("K. Allen", "Johnson").

**Join.** nflverse seasonal rosters carry `espn_id`: 97.8% of our 579 simulated skill players map to a gsis id. On
DET@BUF, 89/111 game-roster entries joined; all 17 inactives are real players and 12 joined directly. The misses
are OL and rookies (Blake Miller, Mahogany, Reed-Adams, Bowry, McLaughlin), which matter to the injury layer
(Miller was 1.80 pts). Chosen join, with no schema change: fetch each inactive's athlete record (≤ ~9 calls per
team) for the full display name, then match by `player_key(team, name)`, exactly as the ESPN injury rows already
match.

**Payoff, measured on week 1** (14 simulated games, final, rosters available): 6 of 280 projected players were
inactive, carrying **1.4% of projected touches**, concentrated in RB2s: Kamara 8.1 and Najee Harris 6.6 touches (the
DAL@NYG case in P10's evidence), plus Tolbert, Claiborne, Ty Johnson, Sturdivant. That explains **6 of the 53**
"projected but recorded no stats" players; the other 47 were active and simply got no touches, a shares question. So
the props payoff is targeted (the RB2 / backup cases) rather than broad. The injury layer benefits separately:
questionable players resolved to 0 or 1 instead of a flat 0.55.

**Design.**
1. `ingest_injuries.fetch_inactives(week)`: scoreboard → per game, one roster call per team. 404 or no entries =
   not posted, and nothing is written. Each inactive's athlete record gives the full name. Rows go to the existing
   `injuries` table as source `espn_inactives`, status `out`, play_probability 0.
2. Precedence in `features.latest_injury_report`: for a team whose inactives are posted this week, inactives are
   out, and every reported questionable / doubtful / probable player not on the list is **active (play_probability
   1.0)**, overriding the flat 0.55. Out and IR rows are untouched. Teams without a posted list are unchanged. Week
   keying means a list can never gate a later game (each team plays once a week), so no removal step is needed.
3. No new depth logic: `team_shares` and `passer_weights` already pass an absent player's share to the next man
   down the depth chart.
4. Operation: inactives post ~90 min before each window, so value needs a refresh (injuries → pipeline → re-sim →
   props) after posting and before kickoff: three windows on a Sunday. Manual per window, or automated in
   `live_tracker` (an extra step).

**Build criteria (written before any code).**
1. Replay DET@BUF and week 1: every inactive resolves to a name matching our roles or injury rows (all 4 P10
   DET@BUF players; ≥ 95% of skill-position inactives).
2. 404 / empty list: zero rows written, report unchanged (test).
3. Precedence (tests): inactive → 0; reported Q/D/P not on the list → 1.0; Out/IR untouched; teams with no posted
   list unchanged.
4. DET@BUF replay: rescored injury term shows the four flat-0.55 players resolved (Sanders and Ty Johnson out,
   Reed and Bishop active).
5. Week-1 replay: the 6 inactive projected players get zero touches, their share passes down the depth chart, and
   team totals are unchanged.
6. Live, first Sunday: log when each game's list first appears, and set the polling window from that.

**Estimate.** Ingestion + join ~1.5 h; precedence + tests ~1.5 h; CLI / pipeline hook + an "inactive" label on the
page ~1 h; replay validation ~1 h: **~4-5 h**. Automating the Sunday windows in `live_tracker`: +1-2 h (optional).

## 2026-09-19 — QB rushing props back in the ranking, with their own offset; Lock's held out

At the user's call, after P24.
- **Offset:** fitted the same way as the other categories on the 21 week-2 QB rushing props: **−0.182** (raw
  +4.22pp, 90% CI −0.36 to +0.03).
- **By-position check (P26 rule):** pocket −0.20 (n=3), middle −0.26 (n=11), running −0.06 (n=7). All lean the same
  way with overlapping intervals, so one offset, no split. Spearman(line, gap) is −0.29 (p=0.20), against the −0.79
  that made a QB offset meaningless on 9/18.
- **Top 25, previewed before going live** (the same checks as when the receiving correction shipped): two QB rushing
  props entered, Daniel Jones over 8.5 (#18) and Drew Lock under 6.5 (#23), replacing the two Tee Higgins props at
  #24-25. Overs 4 → 5 of 25; mean raw gap 22.6 → 22.7pp; mean touches 7.1 → 6.8 against a population 7.1. So no
  edges are manufactured and there is no low-volume tilt. Ranking stays on the raw gap.
- **Lock's rushing prop is held out** (user's call). It is the P28 starter mismatch (the sim has Lock as QB2, with a
  near-zero projection), not a disagreement worth reading. It goes through a new per-prop holdout, `props.PROP_HOLDOUTS`
  (keyed by game, the books' player name and market), and shows under "Held out · engine defect" with its reason.
  His passing prop stays ranked (#13) with the P28 label. Tee Higgins's receiving yards took #25.
- `STRUCTURAL_HOLDOUTS` is now empty. The page note says QBs have their own offset.
- Live: 19 QB rushing props ranked. Lamar Jackson's under (26.6pp) is held out as a gap over 25%. Tests 51/51 props,
  12 suites pass.

## 2026-09-19 — P24 built: QB-specific scramble rates in the play sampler; re-validated; live

**Change.**
- `Offense.scramble_factor`.
- `SimTables.base_weights(pass_rate_oe, scramble_factor)` reweights scrambles within each bucket and rescales that
  bucket's other dropbacks so its dropback mass is unchanged. A factor of 1 is bit-identical to before.
- The sampler cache key includes the factor.
- `sim_data.qb_scramble_rates`: own scrambles / dropbacks over the prior and current seasons, shrunk by
  `SCRAMBLE_PRIOR_DROPBACKS = 25` toward the prior season's league rate. `qb_dropback` joined the pbp columns so the
  dropback definition matches the validated one exactly.
- `sim_data.scramble_factor`: the passer-weighted team rate over the league rate. Pregame (`simulate_nfl`) weights by
  each QB's play probability. Live (`live_sim`) uses whoever is actually throwing today.
- The factor is recorded in each stored sim's targets. Nine new tests; all 12 suites pass; the dashboard builds.

**Re-validation: the same checks, re-run unchanged** (`p24_estimator.py`, `cmp_p24.py`), fed by read-only re-sims from
the production code (factors on, and forced to 1 as the control):
- Production reproduces the validated prototype exactly: identical box scores, factors and margins on all 15 games;
  identical per-QB rates for all 579 players (league 0.054917).
- Trait r 0.869; scramble MSE −25.8% (8/8 weeks); terciles 0.98 / 1.07. Dropbacks 36.01 → 35.97; points −0.15;
  anchor error 0.24 → 0.18. QB rush att error: pocket 1.22 → 0.26, running 1.51 → 0.64, middle 0.38 → 0.27. QB
  rush-yds |gap| 0.163 → 0.116 (pocket 0.225 → 0.103, running 0.179 → 0.128). Every criterion passes, with numbers
  identical to the design-stage run.

**Live:** weekend re-simmed and stored (it matches the validated run), `export_sims`, props re-ranked, dashboard
exported.

**Passing-yards correction refitted:** −0.0475 → **−0.0212** (n=23, raw +0.50pp, 90% CI −0.16 to +0.15). **Still
provisional: P29 (tied-line averaging drops about a third of starting QBs' pass-yds props) remains open, so this fit
is taken on an incomplete sample.** The other corrections drifted only slightly under P24 and were left as they are:
receptions +0.524 (refit +0.541), rec yds WR +0.447 (+0.469), TE +0.537 (+0.553), RB +0.212 (+0.241), RB rush
+0.218 (+0.212).

**Not decided:** QB rushing props stay held out of the ranking (`STRUCTURAL_HOLDOUTS`). Whether to return them, with
their own correction, is a separate decision for the user.

## 2026-09-19 — P24 (issue 2B) design stage: criteria written down before running

Written before any result was seen, per the process rule.

**How the engine does it now.** A scramble is a library dropback play. Every offense draws dropbacks from the league
library, so scrambles come at the league rate (~5.9% of dropbacks) whatever the QB. Designed QB runs are already
player-specific through carry shares (since P23).

**Design under test.** A per-offense scramble factor in the play sampler: within each bucket, scramble plays are
weighted by (the offense's expected QB scramble rate ÷ league rate), and the bucket's other dropback plays are rescaled
so the bucket's total dropback mass is unchanged. Dropback rate, game script, PROE and the EPA tilt carry through, and
the margin anchor holds. The expected QB rate is the passer-weighted mix of the team's QBs (play probabilities, as the
box score assigns passers). The per-QB rate is own scrambles/dropbacks shrunk to the league rate: (scr + k·league) /
(dropbacks + k), with 2024 at weight 1 or 0.5. Scramble yardage stays league (a v2 question, measured below only to
decide whether it is needed).

**Criteria.**
- *Trait stability (stop if it fails):* 2024 → 2025 correlation of QB scramble rate ≥ 0.5 among QBs with 150+
  dropbacks in both seasons.
- *Estimator walk-forward, 2025 (k and recency chosen on weeks 3-10, judged on 11-18),* scrambles per QB-game given
  actual dropbacks: (1) MSE below the league-rate baseline overall and in at least 6 of 8 weeks; (2) terciles by
  pre-week own rate: predicted/actual scrambles within 0.85-1.15 for the low and high terciles.
- *Engine prototype, read-only, week-2 weekend slate (scratch monkeypatch, nothing stored):* (3) dropbacks, points
  and margins per team unchanged within noise; (4) QB rush attempts per team-game move toward each QB's own real
  per-game figure in both the running and pocket groups; (5) QB rush-yards P(over) moves toward the market for both
  groups (mean |gap| shrinks in each).
- *Revision to P24's written adoption test:* "no change to team totals" becomes "dropbacks, points and margins
  unchanged". Running QBs' teams are meant to swap some pass attempts for scrambles, as in real football.

**Stop rule.** If the trait is unstable, or the estimator improves scramble MSE by less than 5% out of sample, stop
and report.

**Results (added after the run; the criteria above were not changed).** Read-only throughout: nothing in src/
changed, nothing was stored.

| criterion | result | verdict |
|---|---|---|
| trait stability | 2024 → 2025 r = **0.87** (n=31); 2025 rates 1.1%-8.8% (10th-90th pct) | pass |
| 1. scramble MSE, weeks 11-18 | **−25.8%** vs league rate, better in **8/8** weeks (k = 25, prior season weight 1) | pass |
| 2. terciles, pred/actual | low **0.98**, high **1.07** (baseline 2.19 / 0.73) | pass |
| 3. dropbacks / points / margins | dropbacks 36.01 → 35.97 per team-game (max 0.6); points −0.15 per game (max 0.78); anchor error 0.24 → 0.18 | pass |
| 4. QB rush att vs own real per game | pocket (rate ≤ 3.7%, n=5): mean \|sim−real\| 1.22 → **0.26**; running (≥ 6.4%, n=13): 1.51 → **0.64**; middle: 0.38 → 0.27 | pass |
| 5. QB rush-yds P(over) vs market | pocket (n=3) mean \|gap\| 0.225 → **0.103**; running (n=7) 0.179 → **0.128**; middle 0.135 → 0.112; all 0.163 → 0.116; Spearman(line, P(over)) −0.68 → **−0.19** | pass |

The control run (same patched path, factor 1) reproduced the stored sims exactly. Scramble factors applied ranged
0.23 (Stafford) to 2.57 (Willis), median 0.99. Team pass att 31.69 → 31.50 and rush att 27.00 → 27.15, the intended
swap of pass attempts for scrambles.

**Yards per scramble is not a QB trait** (2024 → 2025 r = 0.00, n=17), so scramble yardage stays league-wide. No v2
is needed for it.

**Residuals, not part of this item:** running QBs still sit ~0.4 rush att a game under their real figure (the
designed-run side), and some big-line runners stay well under (Lamar Jackson P(over) 0.146 → 0.231 at 40.5). QB
rushing props are still held out of the ranking (`STRUCTURAL_HOLDOUTS`). Whether to lift that and fit a QB rushing
offset is a separate decision after the build.

**Build scope if approved (est. 2-3 h):** an `Offense.scramble_factor` field; `base_weights` applies it with a
per-bucket dropback-mass rescale; the sampler cache key includes it; `sim_data` computes shrunk per-QB scramble rates;
`simulate_nfl` and `live_sim` set each offense's factor from the passer-weighted QB mix; tests. Then re-validate
against these same criteria with the production code, re-sim, and refit the pass-yds offset (P29 caveat stands).
Nothing built yet.


## 2026-09-19 — P17 design-stage walk-forward: criteria written down before running

Written before any result was seen, per the process rule (criteria go in the log when they are set).

**Design under test (receiving only, v1).** Outcome-aware crediting: the engine keeps every sampled play, so team
totals and game outcomes are unchanged by construction. It chooses each target's receiver in proportion to target
share × that receiver's likelihood of the play's outcome (incomplete, or a completion in a yards band) within its
category (red zone / deep / short). The weights are re-balanced (IPF) so every receiver's total target share is
unchanged. Per-player outcome rates: own history shrunk to a prior as n/(n+k), with n = targets in that category. The
prior is either league-wide by category or by position (WR/TE/RB); 2024 counts at weight 1 or 0.5. No matchup
adjustment in v1.

**Walk-forward harness.** 2025 weeks 3-18. Each week uses only pbp before it (2024 + earlier 2025 weeks). It is
scored on receivers with at least one target that week, given their actual targets by category, and constrained to
that team-game's actual receiving yards / receptions: each player's predicted share of the team total, so only the
split between players is being tested, which is P17's defect. Baseline = the current engine: league outcome rates
by category. k, prior and recency are chosen on weeks 3-10 and judged on weeks 11-18.

**Pass criteria (judged on weeks 11-18):**
1. Receiving yards per player-game: MSE below baseline overall, and below it in at least 6 of 8 weeks.
2. Receptions per player-game: MSE below baseline overall (not worse than baseline if catch rate adds nothing).
3. Tercile calibration (terciles by pre-week own yds/target, players with 20+ prior targets): predicted/actual
   yards moves toward 1.00 for the top and bottom terciles against baseline (baseline on week 1 of 2026 was 0.80 /
   1.24), with neither ending further from 1.00 than it started.
4. Team totals unchanged: holds by construction; checked as an identity (sum of predicted = team actual).

**Stop rule.** If the best variant improves yards MSE by less than 1% out of sample, or only passes with
matchup or per-week tuning, stop and report rather than extend the chain.

**Results (added after the run; the criteria above were not changed).**

*Harness correction, disclosed.* The first run gave both models each player's actual red-zone/deep/short split for
the week. That leaks the outcome (a big-yardage week is one with more deep targets), and the engine cannot know it,
since it uses each player's historical category shares. The harness was corrected to split each player's actual
targets by his pre-week category shares (pos-mix prior, 10 pseudo-targets), which matches "baseline = the current
engine" as written. The first-run headline was −1.07% (6/8 weeks), close to the corrected figures below.

Chosen on weeks 3-10: k = 100, position prior, 2024 at weight 0.5 (−1.01% there). Judged on weeks 11-18:

| criterion | baseline | chosen | verdict |
|---|---|---|---|
| 1. rec yds MSE, weeks better | 260.5 | 257.2 (**−1.28%**), **7/8** weeks | pass; 90% team-game bootstrap CI −2.59% to +0.11% |
| 2. receptions MSE | 0.695 | 0.674 (**−2.91%**) | pass |
| 3. terciles, pred/actual yds (bottom / top) | 1.012 / 0.968 | 0.985 / 0.981 | **fail, narrowly**: top improves, bottom overshoots (1.2% → 1.5% from 1.00) |
| 4. team totals | identity | identity (max error 6e-14) | pass |

The position prior alone (no player signal) gives −0.08% on yards and −2.26% on receptions, so most of the
receptions gain is position-level catch rate. The player-specific part adds ~1.2% on yards. The stop rule (under
1%) is not triggered, but only just, and the CI touches zero.

**The main finding: the compression P17 was scoped on does not reproduce.** In the 2025 walk-forward the CURRENT
engine, given each player's targets and his pre-week category mix, is already within ~3% per tercile (0.97 / 1.01).
The 0.80 / 1.24 from the 2026 week-1 check (n=138, one week) is not a property of efficiency given targets. Either it
was one-week noise and selection, or it came from the simulated target distribution (who gets how many deep and
short targets) rather than from efficiency. Player efficiency is therefore a 1-3% effect, not the ~10pp props
under-bias. Nothing was built; the design is parked pending the user's decision.


## 2026-09-19 — PENALTY_REPLAY switched on; props offsets refitted

**Change.** `config.PENALTY_REPLAY` now defaults to on (`PENALTY_REPLAY=0` restores the old behaviour). A nullified
penalty replays the down instead of consuming it (commit b863918, 2026-09-16). This moves ahead of the plan to wait
for week-2 grading, at the user's call.

**Re-validation against the 2026-09-16 sign-off.** No explicit list of the eight accept criteria was ever written
down, so the recorded evidence was reproduced item by item.
**Process gap:** the "8 accept criteria" from 9/16 were stated in conversation but never written into this log or
the commits, so this validation had to be reconstructed. From now on, write validation criteria into
calibration-log.md (the item's adoption-test cell or its entry) at the time they are set, so they can be retrieved later.
- **Calibration** (20k league-average sims, `--calibrate`) reproduces 9/16 exactly, off and on: points / team
  22.199 → 22.635 (real 22.629), pass att 31.928 → 32.325 (32.735), rush att 26.648 → 26.560 (26.139), rush yds
  122.712 → 121.787 (117.536), possessions 11.84 → 11.09. That is expected, since 2A, P27 and k32+fb change only
  how usage is credited to players.
- **Like-for-like residuals, flag on:** series / drive −1.9% and drives / team-game +1.0% (both inside the ±2% band);
  plays / drive −2.7% (the one known miss, explained by the FG deficit, .148 vs .158); series conversion −0.7%;
  plays / series −0.6%.
- **Accounting identities, flag off and on, seeds 1 and 7, 5k sims:** drives = possessions; TD-ending drives =
  offensive TDs; FG-made drives = FGs; the first-down histogram sums to the drive count; and series started −
  converted + TD drives = drives. All hold to the unit. (First written without the TD term, which failed by exactly
  the TD count in every run: the engine counts a touchdown as a converted series.)
- **Tests:** all 12 suites pass with the flag on.

**Live check (read-only, 15 weekend games).** The flag-off control reproduced the stored sims exactly. Flag on: total
points +0.76 per game (range +0.38 to +1.26); per team-game, pass att 31.35 → 31.69 (real 2025 32.08), completions
20.32 → 20.53, rush att 27.05 → 27.00. Simulated margins stay on their baseline anchors. Anchor error is about the
same either way (mean 0.21 off, 0.24 on; max 0.72 / 0.61): it is existing noise from the 4k-sim pilot runs, not
caused by the flag. Props moved ~0.5pp toward the market in every category.

**Offsets refitted** (in sample, week-2 slate): pass yds +0.005 → −0.048 (n=23, still provisional under P29);
receptions +0.552 → +0.524; rec yds WR +0.447, TE +0.537, RB +0.212 (RB interval +0.10 to +0.33 still excludes the
category +0.41, so the split stays); RB rush +0.195 → +0.218.

Live: weekend re-simmed and stored (it matches the validated run), `export_sims`, props re-ranked, dashboard exported.
Uncommitted pending the user's review.

## 2026-09-19 — P25 (issue 1) applied: k32+fb; receiving offsets refitted

**Change.** In `sim_data.blend_roles`, players beyond the playing slots now take their own history at weight
games/(games+32) (`BACKUP_HISTORY_GAMES`) instead of 0, still clipped to 0.5-3x the slot norm. A fullback with no
slot prior (nflverse labels no one FB) keeps his own history unclipped instead of being forced to 0. The sim builds
roles fresh on every run, so there is no cache to invalidate.

**Re-validation against the locked criteria**, 2025 walk-forward (weeks 3-18, depth chart before each week's first
kickoff, availability from weekly rosters), using the shipped function. The shipped shares are identical to the 9/18
reference (max difference 0.0):

| MSE vs production | weeks 3-18 | locked | weeks 11-18 | locked | weeks better | locked |
|---|---|---|---|---|---|---|
| tgt_all | −4.5% | −4.5% | −5.3% | −5.3% | 15/16 | 15/16 |
| car_all | −2.1% | −2.1% | −3.0% | −3.1% | 8/16 | 8/16 |
| tgt_rz | −0.6% | −0.6% | −0.8% | −0.8% | 15/16 | 15/16 |
| car_gl | −0.8% | −0.8% | −1.7% | −1.7% | 10/16 | 10/16 |

**Live check (read-only, 15 weekend games, 10k sims).** The control run with the old blend reproduced the stored sims
exactly. Game totals, margins and team volume are unchanged (max difference 0.0): the change only redistributes
usage. Per team-game: WR1 −0.19, WR2 −0.16, TE1 −0.13 targets, WR3+ +0.21 and TE2 +0.09; RB1 −0.31 and RB2 −0.14
carries, RB3+ +0.50. Box-score players listed 325 → 339: Waller (CAR TE3) and the FBs Juszczyk and Ingold now appear;
Njoku and Kmet (TE2) rise from ~1.8 to 2.1-2.4 targets. Props, raw P(over) against the market: starters' receptions
0.413 → 0.394 and backups' 0.242 → 0.261. Starters go further under, as the revised P25 criterion anticipated. Passing
is unchanged. Props held out as likely usage misses: 44 → 55.

**Receiving offsets refitted** (in sample, week-2 slate, same method): receptions +0.5517 (n=138, positions overlap,
so one offset); receiving yards WR +0.4560 (66), TE +0.5586 (31), RB +0.2389 (32, still split). The RB rushing offset
was then refitted too, at the user's call: +0.107 → +0.195 (n=41).

Tests: all 12 suites pass; `test_depth_slot_governs_volume` updated for the new backup weight, plus an FB case.
The dashboard builds. Live: weekend re-simmed and stored (it matches the validated run), `export_sims`, props
re-ranked, dashboard exported, then re-ranked again after the RB refit.

## 2026-09-19 — Targeted prop re-pull (NYG@LA, CAR@ATL); P29 found; P28 widened

`ingest_props --only-missing` would have pulled nothing: it only re-pulls games with no props, and all 16 had them.
It would still have stamped the file's `pulled_at` as now, making 9/17 prices look fresh. The user chose a targeted
pull instead. New `ingest_props --games` re-pulls only the named games and carries the rest forward, including games
already played. A re-pull that comes back empty keeps the lines already on file. Whenever anything is carried, the
top-level `pulled_at` is the **oldest** game's pull time, and `refreshed_at` / `refreshed_games` record what is
fresher; the props page subtitle names the re-pulled games. Dry-run with the API stubbed: exactly 2 paid calls, the
other 14 games byte-identical. Live pull at 00:20Z: quota 306 → 289. 8 of that is this pull; the 306 figure dated
from 9/17 23:00Z, before two game-odds pulls, so the rest is most likely those (not verified per call).

**What the books did:**
- **Nacua: nothing.** Receptions still 6.5, yards 85.5 → 84.5, both near 50/50. The books still price him as a full
  go. The sim halved him on the flat questionable 0.55 (P21), so both props stay held out at 41-50pp gaps. The move is
  the model's, not the market's.
- **CAR@ATL: books priced the Penix-out game.** Players 5 → 14. **Cooper Rush** is the ATL passer (183.5); Kyle Pitts,
  Waller, Brooks, Hubbard, Legette and Dotson were added. Bijan Robinson's rush line went 81.5 → 83.5 (gap 15.6 → 18.1,
  rank 68 → 48). Xavier Legette receptions over 1.5 entered the top 25 at #20, and Ashton Jeanty rush yds left it.
- **NYG@LA:** new small lines (Skattebo, Kyren Williams receiving, Malachi Fields); Kyren Williams's rush market was
  pulled. Stafford pass yds is now ranked (#87, over 242.5), after the 9/17 file dropped it under P29.
- Priced props 324 → 349. The other 13 games' ranking inputs are identical.

**Found: P29** (`market_view` tied-mode median; 37/424 props silently dropped, mostly starting-QB pass yds).
**P28 widened** to ATL: the sim starts Tua (the depth chart's QB2), and the books price Cooper Rush.

## 2026-09-18 (evening) — Passing-yds offset refitted, P28 labelled, TD tab unwired

Display-only; the engine and stored sims are untouched.

- **Pass-yds offset −0.093 → +0.005** (P26). Same in-sample method, week-2 slate, n=20, raw bias −0.12pp. It now moves
  no pass-yds probability by more than 0.13pp.
- **P28 labelled.** New `props.KNOWN_DEFECTS` (keyed by game and the books' player name) attaches a `defect_note` to
  every row for that player. The card shows it as a caveat, the table row as a sub-line, and the Claude explanation
  prompt gets it too; the generated #2 explanation now leads with the defect. The prop stays ranked (#2); it is not
  held out.
- **TD tab no longer reachable.** `NflHub.jsx` is back to its committed version, so it routes props to `PropsPage` and
  `#/nfl/props/td` falls through to the ordinary props page. The wiring is kept in the untracked `td-tab-wiring.patch`
  (`git apply td-tab-wiring.patch` restores it). `PropsSection.jsx`, `TdPropsPage.jsx`, the `tabs` prop on
  `PropsPage` and the TD styles in `hub.css` stay uncommitted and are not in the built bundle.
  `dashboard/public/td_props.json` is still in `public/`, so the file itself is fetchable by URL, but no page shows it.

Props re-ranked (no odds pull) and dashboard exported after these changes. Tests: props 48/48, with the correction
on and off.

## 2026-09-18 — P27 applied: throwaways no longer credited as targets; receiving offsets refitted

**Change.** `sim_data.TABLES_VERSION` 4 → 5 adds `targeted` (a pass attempt with an intended receiver). The v5 library
is identical to v4 in every existing array (112,518 plays). 4.23% of attempts are throwaways; none are completions,
27 are interceptions. `simulate._Game._credit` still draws a receiver for every attempt, so the random stream and
every game outcome are unchanged, then drops the receiver credit where `targeted` is false.

**Validation**, read-only, on the 15 weekend week-2 games at 10k sims. Same code in both runs, with the control
run's `targeted` stripped (the control reproduced the stored sims exactly):

| criterion | target | control | P27 |
|---|---|---|---|
| catch rate (rec / tgt) | ≈ 0.674 | 0.6487 | **0.6771** |
| targets / pass attempt | ≈ 95.8% | 100% | **95.81%** |
| QB pass att / cmp / yds (per player) | unchanged | | identical (max diff 0.0) |
| team totals, game totals, margins | unchanged | 44.749 / +3.694 | identical (max diff 0.0) |
| receptions = completions, rec yds = pass yds | holds | yes | yes |

Tests: new `test_throwaways_are_not_targets` (box score); all 12 suites pass with the props correction on and off.
`test_rank`'s gap check compared against the bias-adjusted probability, so it failed whenever `.env` turned the
correction on. That predates this run. It now compares against `p_model_raw`, which is what `gap` is.

**What P27 did not do: move any prop.** Receptions and receiving yards per player are identical by construction,
and raw P(over) is unchanged on 324/324 priced props. The 9/18 diagnosis said P27 "accounts for the ~4-5%
receptions shortfall". That was wrong: the throwaway was an incomplete target, so it lowered the catch rate without
costing anyone a catch. Team receiving is calibrated (per team-game, sim 20.33 completions and 30.03 true targets;
2025 20.62 / 30.70; 2026 week 1 20.47 / 29.74). The per-player receptions shortfall comes from how catches are split
between players (P17 efficiency and catch-rate compression, and P25's shares), not from the team total.
This reopens one item from the 9/18 diagnosis: its week-1 "targets 1.003" compared throwaway-inflated sim targets
against true actual targets, so on true targets the starters sit about 4% under (one week, n=138, SE ≈ 5%). That is
within noise, and it points the same way as the receptions gap.

**Receiving offsets refitted**, in sample on the week-2 priced props (the method is unchanged: a log-odds shift so
that the mean P(over) matches the market; 90% bootstrap CI):

| | n | raw P(over) | mkt | offset | 90% CI | old |
|---|---|---|---|---|---|---|
| receptions (all) | 127 | 0.386 | 0.499 | **+0.510** | +0.40, +0.62 | +0.521 |
| rec yds WR | 63 | 0.404 | 0.500 | **+0.418** | +0.32, +0.53 | +0.401 (one offset for the whole category) |
| rec yds TE | 28 | 0.374 | 0.502 | **+0.553** | +0.37, +0.73 | |
| rec yds RB | 28 | 0.451 | 0.501 | **+0.212** | +0.08, +0.34 | |

Receptions positions (WR +0.46, TE +0.57, RB +0.59) overlap, so they stay as one offset. Receiving yards split under
the P26 rule, because RB's interval excludes the category fit (+0.400). In every group the low lines end up over
after correction and the high lines under, so starters are still under-projected. That is P17, and no constant fixes it.
The pass-yds offset (−0.093 from 9/16) is now stale: the refit is +0.005. It was left alone, out of scope.

**Live, 21:30Z:** weekend sims re-stored (15 rows, supabase), `export_sims`, `props` re-ranked (no odds pull),
`export_dashboard`. The stored boxes equal the validated run. The ranking order is unchanged, since it sorts on the
raw gap. Displayed targets drop ~4%. The displayed receiving-yards probabilities move by position (RB less, TE more).

Side item logged separately as **P28** (SEA / Drew Lock starter mismatch). Not diagnosed here.

## 2026-09-18 — Receiving under-bias: diagnosis (P27, P17), nothing changed

Read-only, current engine (post-P23, pre-P25). Question: why do priced receivers sit ~10-18% under their lines?

**Ruled out:**
- *Team pass volume.* Sim QB pass-yds mean 218.7 vs market line 222.9 across 21 teams (−2%); week-1 sim pass att
  32.2 vs actual 31.4.
- *Shares.* 2025 walk-forward (P25 entry): starters' shares are slightly high, not low. Week-1 starters' simulated
  targets 4.65 vs actual 4.63 per game (ratio 1.003, n=138, SE 0.22).
- *Distribution shape.* Sim median/mean for receiving yards 0.847 vs real 2025 0.853. The sim is ~18% wider (IQR/mean
  1.01 vs 0.85), but that is not what puts it under.
- *The market.* Lines track each player's own 2025 median (ratio 0.989), and week-1 actuals landed at 0.97 (targets),
  0.99 (receptions) and 1.01 (yards) of those players' 2025 per-game averages. The market's anchor held up; the sim's
  did not.

**What it is: conversion, not volume.** Week-1 starters, sim/actual: targets 1.003, receptions 0.954, yards 0.913.
1. **Throwaway targets (P27, new).** 4.25% of library attempts have no intended receiver; the engine credits each to a
   receiver as an incomplete target. Sim catch rate 0.643 = league catch rate over all attempts 0.645; real over true
   targets 0.674. A plain accounting bug, same class as P23.
2. **Efficiency compression (P17).** League yards per target by situation for every receiver: top tercile by own
   2025 yds/target gets 0.80x of actual yards, bottom tercile 1.24x. Zero-sum against calibrated team yards, and the
   priced players are mostly in the upper terciles.
3. **Availability leak (minor, overlaps P10/P20).** Live roles hold 2.5% of team target share on reserve/IR players and
   0.2% on inactives (week-2 roster status), before the injury layer.

Caveat: the reality checks lean on one week of actuals (n=138 starters) and 2025 per-game averages computed over games
with at least one target.

Side finding: SEA's pass-yds market is priced on Drew Lock (207.5) while the sim has him as QB2 (median 0), which puts
him at #2 in the ranked list. A depth-chart/injury mismatch, not investigated.

## 2026-09-18 — Props backlog: P23 shipped, P26 rushing split, P25 validated and banked

**P23 (issue 2A) applied.** `sim_data._usage_events` now excludes scrambles and kneels from carry shares. Validated
read-only against the locked criteria before anything was stored (pre-change state snapshotted in
`data/snapshots/pre-2A_2026-09-18/`, which also keeps the week-2 out-of-sample check of the 9/16 correction possible):

| criterion | target | before | after |
|---|---|---|---|
| QB rush att per team-game | ≈ 3.3 (real 3.25) | 5.41 | 3.26 |
| RB carries per team-game | up ≈ 10% | 20.47 | 22.53 (+10.1%) |
| team rush att / yds, totals, margins | unchanged | | identical to 4 decimals |

Props, raw, 324 paired: RB rush yds P(over) 0.414 → 0.477, QB 0.707 → 0.539; receiving and passing unmoved.

**P26 rushing rebuild: only half validates.** Fitted by position on the week-2 priced props (same method):

| | n | offset | P(over) low-line half | high-line half | Spearman(line, P(over)) |
|---|---|---|---|---|---|
| QB rush | 19 | −0.184 | 0.667 | 0.423 | −0.79 (p < 0.001) |
| RB rush | 39 | +0.107 | 0.521 | 0.435 | −0.33 (p = 0.04) |

Simulated QB rushing sits at 15-30 yards whatever the QB against lines of 0.5-40.5 (P24), so a QB offset averages two
opposite errors and barely changes the distance from market (0.173 → 0.164). Shipped: RB +0.107 labelled as mean-fitted
with starters still under; QB rushing props held out of the ranking entirely (`props.STRUCTURAL_HOLDOUTS`).

**P25 (issue 1) diagnosed, fix validated, banked for the week of 2026-09-22.** 2025 walk-forward, weeks 3-18: each
week's roles built from pbp before it and the last depth-chart snapshot before its first kickoff, availability from
weekly rosters (status ACT, broader than game-day actives), renormalised per team as `team_shares` does, scored
against realised shares.

- Production under-credits backups with a real role: 110 players / 425 player-weeks, predicted 2.9% of targets vs 6.0%
  realised.
- Full own history for backups (P25 as first written) overshoots them 16-52% and worsens carries, red-zone targets and
  goal-line carries: the demoted-starter problem, measured.
- FB zero: nflverse seasonal rosters label no one FB, so no ('FB', rank) prior exists and the history clip forces 0.
- `k32+fb` (backup history at games/(games+32); FBs keep their own history) beats production on squared error in every
  category: tgt_all −4.5% (15/16 weeks), car_all −2.1% (8/16), tgt_rz −0.6% (15/16), car_gl −0.8% (10/16); out of
  sample on weeks 11-18 with K chosen on 3-10, −5.3 / −3.1 / −0.8 / −1.7%. MAE prefers production for FBs only
  because FB carries are mostly zero; MAE rewards predicting the median, which is the wrong target for props.
- **Starters' shares are already slightly too high** against realised (WR +5%, TE +3%, RB carries ≈ 0). The fix lowers
  them. P25's original "starters not pushed further under" criterion rested on the opposite assumption and is revised
  in the tracker. It also means the ~10% receiving volume gap against the market is **not** a share problem.

Held for 9/22 rather than shipped before Sunday: the benefit is mostly backup/TD accuracy (the TD tab is held), and it
would move the receiving baseline mid-investigation and leave the in-sample receiving offsets mis-fitted on the slate.

## 2026-09-17 — NFL (week 2, Thursday) DET @ BUF, pre-kickoff snapshot

Full freshness pass run 22:48–23:00Z, about 75 minutes before the 00:15Z
kickoff: odds re-pulled (32/32 events, quota 370), injuries re-pulled
(185 rows, 32/32 teams), baseline re-predicted, game re-simulated, prop lines
re-pulled fresh (16/16 games, quota 306) and edges re-ranked. No code changed
and `PENALTY_REPLAY` stayed off, so this is a data refresh only.

**What moved.** The injury term carried all of it:

| | before (9/17 00:36Z) | after (9/17 22:50Z) |
|---|---|---|
| injury layer | 0.04 | 1.56 |
| model spread | −4.94 | −6.46 |
| market | −5 | −5.5 |
| home win prob | 64.8% | 69.0% |
| `is_value` | false | false |

DET's burden went 1.22 → 2.72 (Blake Miller, T, 1.0 snap share, ruled **out**
1.80; Mahogany out 0.17; D.J. Reed questionable 0.75); BUF's was flat at 1.15.
The sim followed: BUF win prob .651 → .690, margin p50 5 → 6, total p90 64 →
65. 34 DET@BUF props re-ranked at 23:00Z.

**Grading caveat — do not use this game as evidence about P9.** The stored
prediction is graded against a **pre-P20 injury term**. Two known defects
understate DET's side of that 1.56 specifically:

- **P20:** Isiah Pacheco (DET) is on Injured Reserve and contributes nothing,
  because `_status` discards the IR designation. DET's burden is understated,
  so the true term favours BUF by more than 1.56.
- **P10 / P21:** four players in this game are priced at the flat
  questionable/limited 0.55 (Reed 0.75 pts, Bishop, Sanders, Ty Johnson) even
  though the official inactive list was public before kickoff and resolved each
  to 0 or 1.

Once P20 lands in the week of 2026-09-22, the fixed code would not produce
1.56 for this game. Whatever this result says about the injury layer's
calibration is therefore about a number the pipeline no longer generates. Grade
the game for the record, but exclude it from the P9 fitted-coefficient sample.

**A retracted diagnosis, recorded so it is not repeated.** During the refresh,
two BUF players (Tyrell Shavers, Dorian Strong — both previously `out`, both
~0.40 snap share) disappeared from the injury layer, and their stale
`pulled_at` stamps looked like a P19-style dedup fault. They were not. The live
ESPN payload showed both had cleared the feed entirely — absent as Active, as
IR, as anything — so `latest_injury_report` retiring them is the documented
behaviour that `test_espn_stays_whole_pull` pins. The proposed "fix" would have
resurrected two healthy players, broken that test, and shipped a wrong number
inside the last hour before kickoff. **`pulled_at` alone cannot distinguish
"cleared from the feed" from "not re-stamped by a partial upsert"; read the
upstream payload before concluding a row was wrongly dropped.**

## 2026-09-16 — Usage shares: scramble/kneel confirmation run (P23–P26)

Read-only. Nothing stored, nothing live changed; week 2 stays on the current
engine. The week-2 slate (16 games, 10,000 sims each) was re-simulated twice
with writes blocked: as built, and with scrambles and kneels removed from
`_usage_events`. Both were then ranked against the 195 props already priced,
on raw simulated P(over), with the display correction not involved.

- **Reproducible.** The as-built re-run matched the stored sims on all 195 props.
- **Player splits only.** Team rush att 27.10, rush yds 125.63, mean game total
  45.083 and mean |margin| 8.115 were identical in both runs.

| per team-game | as built | scrambles/kneels removed | real 2025 |
|---|---|---|---|
| QB rush att | 5.42 | 3.33 | 3.25 (1.29 designed + 1.96 scrambles; QBs with ≥ 50 att) |
| RB carries | 20.54 | 22.61 | 23.01 (all non-QB carries) |

| rush yds props | n | as built P(over) | removed P(over) | market |
|---|---|---|---|---|
| RB | 24 | 0.329 (median −22.5% vs line, 2 overs) | 0.393 (−15.5%, 6 overs) | 0.500 |
| QB | 9 | 0.649 (median +28.8%, 7 overs) | 0.443 (4 overs) | 0.502 |
| all | 33 | 0.416 | 0.406 | 0.501 |

Receptions (0.379 → 0.378), receiving yards (0.407 → 0.405) and passing
yards (0.525 → 0.525) did not move.

Read-outs:
- The fix explains about 40% of the RB rushing under-bias and does not tip
  RBs into overs. The other ~60% is unexplained.
- QB rushing props leaned *over*, which hid the RB under-bias in the category
  mean (P26). With the fix, QBs split by style (P24).
- The ~10% target shortfall behind the receiving under-bias has a different
  cause and is still open.

Order for the week of 2026-09-22, one engine change at a time: P23 first,
measured against its adoption test; then `PENALTY_REPLAY`; then P25 and P24.

## 2026-09-15 — Simulator: play-calling follows the score (P11, research Stage 3)

**Applied** (simulator only; predictions and value flags are unaffected, since
the simulations are anchored to the baseline margin):
- Each snap's call, run or dropback, is made at the bucket's pass rate shifted
  in log-odds by the offence's lead (9 bands) × game phase (6, incl. the
  two-minute drill and the last five minutes). Shifts are fitted on the
  2023–25 library, one per state, shrunk by n / (n + 200) (`sim_data._script_shift`).
  A real play of that kind is then drawn from the bucket, so team strength
  (the EPA tilt) and team tendency (PROE) carry through unchanged.
- Live re-simulation uses the same engine, so it gets this too.

Calibration, two league-average teams, 20,000 sims vs 2023–25 real games
(`python -m src.simulate_nfl --calibrate`, `--no-script` for the old engine):

| Team volume by final margin | lost 15+ | lost 8–14 | within 7 | won 8–14 | won 15+ |
|---|---|---|---|---|---|
| rush att, script off | 24.1 | 25.2 | 26.3 | 26.8 | 27.9 |
| rush att, **script on** | **21.4** | **22.7** | **26.6** | **30.1** | **32.5** |
| rush att, real | 20.7 | 21.6 | 26.4 | 29.4 | 31.6 |
| pass att, script off | 31.4 | 32.2 | 32.9 | 33.0 | 34.4 |
| pass att, **script on** | **32.7** | **33.5** | **32.3** | **30.2** | **30.0** |
| pass att, real | 34.1 | 35.8 | 33.5 | 30.2 | 28.6 |

| League totals per team | off | on | real |
|---|---|---|---|
| points | 22.50 | 22.20 | 22.63 |
| pass att | 32.8 | 31.9 | 32.7 |
| rush att | 26.1 | 26.6 | 26.1 |
| pass yds | 237 | 231 | 232 |
| rush yds | 120 | 123 | 118 |

- The old engine had the slope backwards for passing (winners threw more). The
  new one matches the rushing slope closely and most of the passing slope;
  the trailing side still throws ~2 fewer than real teams do.
- Totals move by under 3%: leading teams now run and burn clock, so there are
  slightly fewer snaps. Rush yards per team are now 5 above real (were 3).
- Anchoring still holds: over 14 target margins from −10 to +10, the mean
  |error| of the anchored mean margin is 0.24 pts with the script (0.29
  without; max 0.61 vs 1.07).
- Not changed: time runoff is still drawn from the play's own duration, not
  from the state. Leading teams in real games also snap later; that is the
  next piece of Stage 3 if the calibration's snap count drifts.
- P11's own test (50% band hit rate for rush att over 10+ graded sims) is
  unchanged and still pending. Week-2 sims will be re-run on this engine
  before Thursday.

---

## 2026-09-15 — P13 (QB-conditional prior) tested, not adopted

The test: take last season's offense only from the games started by the
quarterback expected to start now, if he started ≥ 4 for that team; else the
whole season, as before (`src/qb_prior.py`, `QB_CONDITIONAL_PRIOR`). The 4 was
fixed in advance and not tuned. Full tables:
`calibration/2026-09-15_p13_qb_prior_before_after.md` (regenerate with
`python calibration/p13_qb_prior_backtest.py <out.md>`).

| Test | Off | On |
|---|---|---|
| Baseline Layer 1, wks 1-4 2016-25 (615 games), MAE | 10.457 | 10.563 |
| same, the 163 games it moved ≥ 1 pt | 10.083 | 10.532 |
| same, ATS all leans | 301-302 | 302-301 |
| ML 2025 holdout (285), MAE (line 9.67) | 10.080 | 10.096 |
| ML 2025 holdout, wks 1-4 MAE | 8.975 | 9.125 |
| ML 2025 holdout, ATS all leans | 143/285 | 147/285 |

- Worse on both models and both measures of the adoption test. On the games
  it moved, it moved toward the result 54% of the time, by 2.9 pts on
  average: right about as often as wrong, and by a lot. 6 of 10 seasons got
  worse.
- So DEN @ KC was one game where the mechanism was real, not a rule. Likely
  reasons, not tested: a starter's own games are a smaller, noisier sample
  than the season; backup-QB games also reflect the roster around him (a bad
  team loses its starter to a bad line); and the market prices QB changes
  anyway, so a QB-blind prior was already mostly compensated for by the line
  in these comparisons.
- Not tried, and would need a fresh test rather than tuning this one: shrink
  the starter-games mean toward the season mean by sample size, instead of
  replacing it.
- A bug found on the way: the first ML run was a no-op (a variable-name
  clash in `build_training.build_nfl` overwrote the starter ids with injury
  values). Fixed before the numbers above; the backtest now reports how many
  training rows the prior moved (1012 of 3028) so a no-op can't read as "no
  effect" again.
- `train_model` now reports weeks 1-4 MAE on every holdout run. The live model
  and training set are unchanged.

---

## 2026-09-15 — Stage 1 edge logic applied (research doc §4)

**Applied** (code, not weights):
- Devig each book's spread from both prices (Shin), restated at the consensus
  line with the empirical margin distribution.
- Blend the model with the market in log-odds space at model weight 0.15.
- Flag only at 3+ pp past the price's break-even.
- CLV logged for every lean (`clv_log`), closed from ESPN/DraftKings.
- Prices kept in `odds_snapshots`; in-play odds no longer stored.
- P14 applied.

Full tables: `calibration/2026-09-15_stage1_before_after.md` (regenerate with
`python calibration/stage1_before_after.py <out.md>`).

**Before/after, baseline, pregame predictions only** (the historical rows
stored no prices, so the market is taken at −110 both ways):

| | Old flags (≥ 2 pts) | ATS | CLV of old flags | New flags (w 0.15, 3 pp) |
|---|---|---|---|---|
| NFL (14) | 11 | 3-8 | −0.36 pp | 0 |
| CFB rated (37) | 29 | 12-17 | +0.42 pp | 0 |
| **Total** | **40** | **15-25 (38%)** | +0.20 pp | **0** |

Probability of the home side covering, scored (pushes excluded; a coin flip is
0.693):

| Log loss | Model alone | Blend w=0.15 | Market |
|---|---|---|---|
| NFL live (14) | 0.888 | 0.717 | 0.693 |
| CFB live rated (37) | 0.790 | 0.703 | 0.693 |
| ML NFL 2025 holdout (285) | 0.719 | 0.694 | 0.693 |
| ML CFB 2025 holdout (762 FBS) | 0.737 | **0.692** | 0.693 |

- The new rule would have avoided all 40 old flags. Their record was 15-25
  with CLV of about zero. Blending cuts the probability error sharply, but in
  three of four samples the blend is still no better than the market alone. So
  far the model subtracts information more than it adds it.
- Week 2 as run today: 0 of 16 NFL games flag (the old rule: 12). The nearest
  is CIN @ HOU at 2.97 pp, priced from real snapshot prices: HOU −3 at −105,
  break-even 51.2%.
- The one positive sample: the ML CFB 2025 holdout flags 47 games at w 0.15,
  going 31-15-1, and its blend beats the market's log loss slightly. It is one
  of four samples, and on big spreads it is the P7 compression leaning
  mechanically to underdogs. On the 37 rated live CFB games the ML model's new
  flags went 4-4. The ML gate stays shut.
- CLV to date (backfill): baseline 75 pregame leans −0.22 pp (t −1.22), ML 74
  +0.13 pp (t +0.70). The research rule is w = 0 if CLV is negative at 65+.
  Logged as P16 against NFL leans only, since 61 of these are CFB leans priced
  at an assumed −110 against a single book's close.
- New bug found while backfilling (P15): 19 CFB predictions on 09-12 were made
  after kickoff against in-play lines. The corrected record is above.

---

## 2026-09-14 — NFL (week 1, Monday) DEN @ KC post-mortem, written 2026-09-15

One game, graded from ESPN's final (DEN 10 – KC 31). The DB row is not yet
marked completed, so run `python -m src.grade --sport nfl --refresh` to record
it. Full working in `calibration/2026-09-14_nfl_DEN_KC_postmortem.md`.
**Diagnosis only: no weights, thresholds or code changed.** One game is one
data point, and the proposals below have to earn adoption like every other.

The baseline had KC −1.46 against a KC −2 market (edge −3.46) and flagged DEN.
KC won by 21 and covered by 18.5. ML had KC −0.9 (lean DEN, gate off). The
sim, anchored to the baseline, gave KC 45.6%.

**Finding: the input most responsible was Layer 1, the team rating.** None of
the four candidate layers was the main cause. Replacing one input at a time:

| Input | Effect on the −3.46 edge |
|---|---|
| Prior-season rating without QB conditioning (KC's 2025 includes 146 backup-QB plays at −0.347 EPA) | **2.90 pts**. With a Mahomes-starts-only prior the edge is −0.56 and there is no flag |
| Injury term (−0.95) | −0.95 toward DEN. With the real snap shares it would have been −2.63, *further* toward DEN (P14) |
| Situational (HFA, travel, rest, wind) | +2.15 toward KC, correct direction |
| ML layer | same lean, smaller (Elo carries the same contamination: DEN +120 Elo) |
| Sim / game script | anchored, can't move the side. Missed KC's volume once they led: 38 rushes vs median 25 (p90 31) |

- The injury layer behaved as designed and wasn't the cause. The market had
  already priced KC's injuries at −2.5. With both corrections applied the edge
  is −2.23, which is still a flag at the 2.0 threshold. That shows the
  threshold logic (Stage 1 of the research doc) as much as the inputs.
- Most of the *size* of the miss is the game. The market missed by 18.5 too.
  DEN managed 3.7 yds/play and lost the turnovers 2-1. The input problem
  explains the flag, not the 21 points.
- CLV would have been slightly negative: DEN +2 consensus at prediction time vs
  DEN +2.5 at DraftKings' close (open −2.5 −120 → close −2.5 −108; ML −155 →
  −130).
- Scope: the same backup-QB mechanism shifts 11 of 32 teams' 2025 ratings by
  ≥ 1 pt (NYJ +5.1, IND +3.8, KC +2.9, WAS +2.3, CIN +2.3). That's the size of
  the mechanism, not a fitted effect. A team with a new 2026 starter needs his
  number, not last year's primary's.

Proposals: **P13** (QB-conditional prior, logic, needs the training rebuild
test) and **P14** (snap-share fallback, correctness bug, awaiting OK). Added
evidence to **P9** (market already priced the injuries) and **P11** (KC 38
rushes while leading).

---

## 2026-09-13 — NFL (week 1), graded 2026-09-14

13 games, 17:00Z through Sunday night (DAL @ NYG), all graded against the
16:35Z post-P1 predictions stored in Supabase (the local SQLite copy still
holds the 09-12 run; don't grade from it). Thursday (NE@SEA), Friday (SF@LA)
and Monday (DEN@KC) are not part of this slate. Per-game table and splits are
in `calibration/2026-09-13_nfl.md` (+ `.json`), and props in
`calibration/2026-09-13_nfl_DAL_NYG_props.md`.

### Results

| | Baseline | ML | Market |
|---|---|---|---|
| Straight up | 6/13 (46%) | 10/13 (77%) | fav 10/13 (77%) |
| ATS, all | 3-10 (23%) | 4-8 (33%) | |
| ATS, value-flagged | 3-7 (30%) | gate off | |
| ATS, not flagged | 0-3 | | |
| Margin MAE | 13.10 | 11.46 | 10.73 |
| Mean signed error (+ = too high on home) | +3.11 | +1.73 | +2.12 |
| Closer to final than market | 3/13 | 4/13 | |
| Brier | 0.256 | 0.214 | |

| Game | Final (A-H) | Model | Market | Edge | SU pick | SU | ATS lean | ATS | Home margin | Model err | Tier |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ATL @ PIT | 13-20 | −4.8 | −6.5 | −1.7 | PIT | ✓ | ATL | L | +7 | −2.2 | high |
| BAL @ IND | 41-23 | −5.9 | +3.0 | +8.9 | IND | ✗ | IND | L | −18 | +23.9 | high |
| BUF @ HOU | 36-31 | −2.7 | +1.0 | +3.7 | HOU | ✗ | HOU | L | −5 | +7.7 | high |
| CHI @ CAR | 59-37 | +5.9 | +3.0 | −2.9 | CHI | ✓ | CHI | W | −22 | +16.1 | high |
| CLE @ JAX | 10-34 | −12.2 | −8.5 | +3.7 | JAX | ✓ | JAX | W | +24 | −11.8 | high |
| NO @ DET (OT) | 30-31 | −9.0 | −7.0 | +2.0 | DET | ✓ | DET | L | +1 | +8.0 | high |
| NYJ @ TEN | 23-10 | −2.5 | −1.0 | +1.5 | TEN | ✗ | TEN | L | −13 | +15.5 | high |
| TB @ CIN | 27-33 | +4.3 | −3.5 | −7.8 | TB | ✗ | TB | L | +6 | −10.3 | high |
| ARI @ LAC | 26-14 | −11.2 | −9.5 | +1.7 | LAC | ✗ | LAC | L | −12 | +23.2 | high |
| GB @ MIN | 22-39 | +0.9 | −1.5 | −2.5 | GB | ✗ | GB | L | +17 | −17.9 | high |
| MIA @ LV | 13-27 | +3.1 | −3.0 | −6.1 | MIA | ✗ | MIA | L | +14 | −17.1 | high |
| WAS @ PHI | 22-24 | −13.0 | −6.0 | +7.0 | PHI | ✓ | PHI | L | +2 | +11.0 | high |
| DAL @ NYG | 20-28 | −2.4 | +3.0 | +5.4 | NYG | ✓ | NYG | W | +8 | −5.6 | high |

Model and market are home lines. Model err is the predicted home margin minus
the actual home margin.

### Confidence tiers

All 13 games were "high" in both models, and all 13 simulations were "high"
score confidence, so high vs low cannot be compared on this slate at all.
Splits that do vary (baseline):

| Split | n | SU | ATS | MAE | Market MAE |
|---|---|---|---|---|---|
| value-flagged | 10 | 5/10 | 3-7 | 12.94 | 10.35 |
| not flagged | 3 | 1/3 | 0-3 | 13.62 | 12.00 |
| \|edge\| 0-2 | 3 | 1/3 | 0-3 | 13.62 | 12.00 |
| \|edge\| 2-4 | 5 | 3/5 | 2-3 | 12.31 | 12.00 |
| \|edge\| 4-6 | 1 | 1/1 | 1-0 | 5.60 | 11.00 |
| \|edge\| 6+ | 4 | 1/4 | 0-4 | 15.57 | 8.12 |
| baseline & ML agree | 7 | 3/7 | 1-6 | 9.50 | 7.00 |
| baseline & ML disagree | 5 | 3/5 | 2-3 | 17.18 | 15.00 |
| \|injury adj\| ≥ 1 | 5 | 1/5 | 0-5 | 12.27 | 8.80 |
| \|injury adj\| < 1 | 8 | 5/8 | 3-5 | 13.62 | 11.94 |
| lean favorite | 6 | 4/6 | 2-4 | 14.25 | 13.33 |
| lean underdog | 7 | 2/7 | 1-6 | 12.11 | 8.50 |

### Diagnostics

- Best-fit weight on the edge (actual = market + w·edge): **w = −0.64**, and
  corr(edge, cover residual) = −0.22. On 13 games this is noise-sized, but
  it's the second slate with no positive signal in the edge (CFB w = +0.05).
- The four |edge| ≥ 6 games all lost (BAL@IND, TB@CIN, WAS@PHI, MIA@LV). In
  each, most of the edge came from the power-rating difference, and the
  ratings are ~94% last season in week 1. That matches the CFB pattern behind
  P5.
- Lean underdog 1-6. In CFB it was the opposite (17-14). Nothing to act on.
- Home teams won 8/13 and covered 6/13. HFA is a flat 1.9 in every game, so
  it can't be tested from one slate.
- Travel correlated +0.37 with the cover residual (sd 0.24 pts). That's two
  slates in a row where travel looks under-weighted (CFB +0.27), both on tiny
  variation. Not proposed; recheck at week 4.
- Injury layer, first real test: the 5 games with |adj| ≥ 1 went 0-5, and
  the injury term had zero correlation with the cover. The P2 counterfactual
  accounts for 2 of those losses (see tracker). See P9.
- ML vs baseline: the ML model picked winners like the market (10/13) and was
  closer on margin, but its ATS was no better. See P8.
- Pregame simulations for 12 of 13 games were generated at 23:11Z, after
  kickoff. Only DAL @ NYG's (69 minutes before kickoff) can be graded. See P12.

### DAL @ NYG props (Cowboys @ Giants, NYG home)

Sim `sim-v1`, 10,000 runs, generated 23:11Z. Projection = sim median; err =
actual − projection; % is relative to the projection ("—" when the
projection is 0). * = no stats recorded (not on the injury report).
Score: projected median DAL 24 – NYG 27, actual 20–28.

**Passing**

| Player | Att | Cmp | Yds | TD | INT |
|---|---|---|---|---|---|
| Dak Prescott (DAL) | 32→34 (+2, +6%) | 22→22 (0, 0%) | 249.5→175 (−74.5, −30%) | 2→2 (0) | 0→1 (+1) |
| Jaxson Dart (NYG) | 31→29 (−2, −6%) | 21→23 (+2, +10%) | 253→230 (−23, −9%) | 2→3 (+1, +50%) | 0→0 |

**Rushing**

| Player | Att | Yds | TD |
|---|---|---|---|
| Dak Prescott (DAL) | 5→2 (−3, −60%) | 26→14 (−12, −46%) | 0→0 |
| Javonte Williams (DAL) | 14→12 (−2, −14%) | 60→41 (−19, −32%) | 0→1 |
| Emari Demercado (DAL) | 5→2 (−3, −60%) | 18→7 (−11, −61%) | 0→0 |
| Israel Abanikanda (DAL)* | 1→0 (−1, −100%) | 5→0 (−5, −100%) | 0→0 |
| Jaxson Dart (NYG) | 7→11 (+4, +57%) | 36→54 (+18, +50%) | 0→0 |
| Cam Skattebo (NYG) | 12→18 (+6, +50%) | 52→81 (+29, +56%) | 0→1 |
| Najee Harris (NYG)* | 5→0 (−5, −100%) | 21→0 (−21, −100%) | 0→0 |
| Tyrone Tracy Jr. (NYG) | 2→2 (0, 0%) | 5→14 (+9, +180%) | 0→0 |

**Receiving**

| Player | Tgt | Rec | Yds | TD |
|---|---|---|---|---|
| CeeDee Lamb (DAL) | 7→8 (+1, +14%) | 4→5 (+1, +25%) | 56→44 (−12, −21%) | 0→1 |
| George Pickens (DAL) | 6→6 (0, 0%) | 4→3 (−1, −25%) | 47→28 (−19, −40%) | 0→0 |
| Jake Ferguson (DAL) | 5→2 (−3, −60%) | 3→2 (−1, −33%) | 31→6 (−25, −81%) | 0→0 |
| Ryan Flournoy (DAL) | 3→4 (+1, +33%) | 2→2 (0, 0%) | 21→22 (+1, +5%) | 0→0 |
| Javonte Williams (DAL) | 2→5 (+3, +150%) | 2→5 (+3, +150%) | 12→31 (+19, +158%) | 0→1 |
| Emari Demercado (DAL) | 1→0 (−1, −100%) | 1→0 (−1, −100%) | 5→0 (−5, −100%) | 0→0 |
| KaVontae Turpin (DAL) | 1→1 (0, 0%) | 1→1 (0, 0%) | 8→8 (0, 0%) | 0→0 |
| Brevyn Spann-Ford (DAL) | 1→2 (+1, +100%) | 1→2 (+1, +100%) | 8→14 (+6, +75%) | 0→0 |
| Jonathan Mingo (DAL) | 1→1 (0, 0%) | 0→1 (+1, —) | 0→10 (+10, —) | 0→0 |
| Israel Abanikanda (DAL)* | 0→0 | 0→0 | 0→0 | 0→0 |
| Malik Nabers (NYG) | 6→9 (+3, +50%) | 4→6 (+2, +50%) | 44→69 (+25, +57%) | 0→0 |
| Malachi Fields (NYG) | 5→4 (−1, −20%) | 4→2 (−2, −50%) | 43→25 (−18, −42%) | 0→0 |
| Isaiah Likely (NYG) | 4→8 (+4, +100%) | 3→8 (+5, +167%) | 26→78 (+52, +200%) | 0→2 |
| Cam Skattebo (NYG) | 4→0 (−4, −100%) | 3→0 (−3, −100%) | 20→0 (−20, −100%) | 0→0 |
| Darnell Mooney (NYG) | 4→2 (−2, −50%) | 2→2 (0, 0%) | 31→27 (−4, −13%) | 0→0 |
| Theo Johnson (NYG) | 2→1 (−1, −50%) | 1→1 (0, 0%) | 8→9 (+1, +12%) | 0→0 |
| Najee Harris (NYG)* | 1→0 (−1, −100%) | 1→0 (−1, −100%) | 4→0 (−4, −100%) | 0→0 |
| Odell Beckham Jr. (NYG)* | 1→0 (−1, −100%) | 1→0 (−1, −100%) | 8→0 (−8, −100%) | 0→0 |
| Dalen Cambre (NYG)* | 1→0 (−1, −100%) | 0→0 | 0→0 | 0→0 |
| Tyrone Tracy Jr. (NYG) | 0→0 | 0→0 | 0→0 | 0→0 |

Unprojected but recorded stats: Devin Singletary (NYG) 6-16 rushing, 4-4-22
receiving, 1 TD; Hunter Luepke (DAL) 1-7; Luke Schoonmaker (DAL) 1-1-12;
Patrick Ricard (NYG) 1 target.

**By stat category, closest → furthest**

| Stat | Lines | MAE | Mean \|err %\| | Sum proj → actual | In 50% band | In 80% band |
|---|---|---|---|---|---|---|
| Pass completions | 2 | 1.0 | 5% | 43 → 45 | 2/2 | 2/2 |
| Pass attempts | 2 | 2.0 | 6% | 63 → 63 | 2/2 | 2/2 |
| Pass yards | 2 | 48.8 | 19% | 502.5 → 405 | 1/2 | 2/2 |
| Rush attempts | 8 | 3.0 | 55% | 51 → 47 | 2/8 | 6/8 |
| Receptions | 20 | 1.1 | 62% | 37 → 40 | 16/20 | 17/20 |
| Targets | 20 | 1.4 | 63% | 55 → 53 | 14/20 | 18/20 |
| Receiving yards | 20 | 11.4 | 69% | 372 → 371 | 16/20 | 17/20 |
| Rush yards | 8 | 15.5 | 78% | 223 → 211 | 1/8 | 7/8 |

TDs: pass 3.8 projected (sum of means) vs 5 actual; rush 2.1 vs 2; rec 3.6
vs 4. Anytime-TD: the two top-probability backs scored (J. Williams 50% → 2,
Skattebo 52% → 1); Likely (23%) scored 2.

What it says, on one game:

- **Passing volume was the most accurate prop by far** (att/cmp within ~6%).
  Passing yards were the next best on average but split: Dart −9%, Prescott
  −30%. Rushing attempts and rushing yards were the furthest off, and the
  rushing bands were too narrow (1-2 of 8 inside the 50% band where ~4 is
  expected).
- **Team volume was right; the split between players wasn't.** Summed
  receiving projections were almost exact (targets 55 → 53, yards 372 → 371),
  while individual lines missed by 60%+. Likely (+52 yds, 2 TD) vs Fields
  (−18) and Ferguson (−25) is allocation, not total.
- **Game script moved the rushing work**: NYG led and ran 37 times (proj 28),
  DAL trailed and ran 18 (proj 26). See P11.
- **Availability/rotation**: Najee Harris was projected as RB2 (5.3 carries)
  and didn't record a stat; Singletary played that role unprojected. See P10.
- Yards misses split roughly evenly between volume and efficiency (rushing
  −22 / −21, receiving −47 / −60 vs projected means). The efficiency half is
  expected given league-average yards per touch, but one game can't separate
  player efficiency from the opponent's defense, so no proposal yet.
- Overall band calibration across the 82 non-TD lines: 66% inside the 50%
  band and 87% inside the 80% band. Slightly too wide overall because of the
  many low-usage lines, and too narrow for rushing.

### Proposals from this slate (detail)

**P5 extended to NFL.** Week-1 NFL ratings are ~94% prior season, and every
|edge| ≥ 6 lost. In weeks 1-4, show NFL edges above ~6 as "likely stale
rating" rather than value, the same treatment as CFB above ~8.

**P8: NFL headline margin.** The ML model was better on every non-ATS measure
this week. That's 13 games, and the CFB ML model is far worse (P7), so the
proposal is only to keep grading both and switch the NFL headline if ML's
MAE stays ahead over ~60 games.

**P9: injury term magnitude.** The 0-5 in |adj| ≥ 1 games is mostly P2 (2
of the 5) and ATL@PIT, where the market already priced Penix out. Fit the
coefficient once 100+ games have injury adjustments; don't touch the per-
position points before then.

**P10: inactives.** Inactives are posted about 90 minutes before kickoff.
The DAL@NYG sim ran 69 minutes before kickoff, so the information existed.
Pull the game-day inactive list into the squad before simulating, and
re-simulate if a projected player is inactive.

**P11: rushing volume.** Check whether the engine's play calling responds to
the score enough. Grade rush-attempt band coverage across every simulated
game (needs P12) before changing anything.

**P12: sim timing.** Schedule `simulate_nfl` before the first kickoff (and
again after inactives for late games), so every game's props can be graded
next week.

---

## 2026-09-12 — NCAAF (CFBD week 2), graded 2026-09-13

80 games, all graded. Per-game table: `calibration/2026-09-12_ncaaf.md`.
"Rated" means both sides have SP+ (47 games); "proxy" means one side is an FCS
team given the flat -28 rating (33 games, never value-flagged).

### Results

| | Baseline | ML | Market |
|---|---|---|---|
| Straight up | 64/80 (80%) | 60/80 (75%) | fav won 72/80 (90%) |
| ATS, all 80 | 36-44 (45%) | 40-40 (50%) | |
| ATS, rated 47 | 23-24 (49%) | 25-22 (53%) | |
| ATS, proxy 33 | 13-20 (39%) | | |
| ATS, flagged value | 18-19 (49%) | gate off | |
| MAE, all | 14.13 | 20.57 | 10.84 |
| MAE, rated | 12.02 | | 10.87 |
| MAE, proxy | 17.13 | | 10.80 |
| Brier | 0.129 | 0.172 | |

The baseline was closer to the final margin than the market in 21 of 47 rated
games. Across the rated games, the edge correlated +0.02 with the
cover residual. The best-fit weight on the edge (actual = market + w·edge)
was **w = 0.05**, so the edge added almost nothing to the line. The 45%
headline ATS is 49% on rated games dragged down by the proxy games, which
`grade.py` currently counts even though they can never be flagged.

### Directional bias (rated games)

- Mean signed error −1.82 pts (model too low on home) vs market +0.29.
  Mean signed edge −2.11, **leaned away in 30/47**.
- Leaning away was not the problem: lean home 8-9, lean away 15-15.
- Lean favourite 6-10, lean underdog 17-14. In small-spread games (market
  under 7) the model was more extreme than the market (mean |margin| 6.1 vs
  3.5) and went 5-8. In big-spread games (17+) it was more compressed (25.5 vs
  30.6; actual 26.8) and went 10-7.
- Home field: across non-neutral games, the market-implied margin exceeded the
  SP+ difference by +4.82 and the actual results by +4.53. The model added
  +2.71 (HFA 2.4 + travel). That gap is also where stale SP+ shows up, so it is
  not a clean HFA estimate. Historically (training set, 2017-2025, both-FBS,
  n=6,441, walk-forward Elo) the market implies HFA **+3.16 (se 0.51)** and
  results imply +2.53 (se 1.25). By season: 3.7, 4.6, 4.0, 3.8, 2.3, 4.9,
  3.3, 2.6, **0.5 (2025)**. The recent decline is why P6 is only "watch".
- Travel correlated +0.27 with the cover residual (model under-weighting it),
  but it only varied with sd 0.24 pts over n=47. That's noise until it repeats.

### Injury-adjusted vs not

Not testable on this slate. One game of 80 had any injury adjustment
(Campbell @ Florida, −0.54, one WR out). It won ATS; n=1 means nothing. The
CFB injury layer is effectively inactive because ESPN's college feed listed
one player. The first real test of the injury layer is the NFL slate on
2026-09-13, where all 13 games have both sides reported. Grade it split by
|injury adj| ≥ 1.

### Confidently wrong

24 games lost ATS with |edge| ≥ 6. 15 were proxy games (not flagged, but
graded). The 9 rated "high" ones:

| Game | Edge | SP+ diff | Elo diff (pts) | Final |
|---|---|---|---|---|
| Oklahoma @ Michigan | −13.3 | −9.5 | −4.5 | 10-17 |
| UL Monroe @ UAB | +10.5 | +17.2 | +13.6 | 20-26 |
| UNLV @ North Texas | −9.6 | −15.5 | +0.0 | 6-44 |
| Georgia State @ Kennesaw State | +9.3 | +15.3 | +5.3 | 31-17 |
| Buffalo @ FIU | −9.2 | −1.9 | +0.8 | 20-33 |
| Southern Miss @ Auburn | −8.6 | +21.9 | +10.5 | 8-43 |
| Navy @ Florida Atlantic | −8.5 | −15.8 | −14.4 | 30-38 |
| Jacksonville State @ Ohio | −8.3 | −9.4 | −4.6 | 27-29 |
| California @ Syracuse | +6.0 | +6.1 | −2.4 | 21-18 |

Every one of these edges came from Layer 1. Layer 2 was a flat +2.4–3.4 in
every game, and there were no injuries. In week 2, a 9–13 point
disagreement with a 9-book consensus mostly means SP+ (still mostly
preseason) is missing something the market has seen, such as a QB change or
week-1 results. It rarely means the market is wrong.

What it says about the confidence tiers: **they don't discriminate at all.**
`_confidence` measures data completeness (a rating, 3+ books, weather), so
every rated FBS game with a line comes out "high": 47 of 47 here. The
"high" tier went 23-24; the 2-6 edge band went 13-10 and the 6-10 band 2-7. The
two signals that did separate:

- **SP+ and Elo agreeing on direction.** When the SP+-based edge had the same
  sign as an Elo-based edge, the lean went 17-14. When they disagreed, 6-10.
- **Week of season.** Historically the gap between market and walk-forward
  rating averages 10.3 pts in weeks 1-2, 8.5 in weeks 3-4, and 5.4 after week 8.
  Early-season edges are structurally inflated.

### FCS proxy

Across 33 proxy games the model's error toward the FBS side averaged −10.2
(it underrated the FBS team), against −3.3 for the market. The error runs
both ways: bad FCS teams lost by 50–84 (Wagner, Southern, Mercyhurst,
Grambling), while Montana State won at Nevada as a 4-pt dog the model had
losing by 24. One flat number cannot fit both.

### ML model (CFB)

Its margins are compressed: mean |predicted margin| 9.5 against 24.7 actual
(Georgia −27 vs market −69.5; Temple +9 vs +21.5 vs Penn State). Its 50% ATS
comes from mechanically leaning underdogs on big spreads, not from signal. A
likely suspect is the walk-forward Elo it replays live. The regression above
shows the market pricing 1.67 pts per 25 Elo points in history, so a
current-season Elo that is shrunk or stale would produce exactly this. Not
diagnosed; that's P7.

### Proposals from this slate (detail)

**P3: FCS proxy.** Options, in order of preference: (a) take the proxy
side's rating from the market (rating = FBS rating − market-implied margin
− HFA) so these games are logged but carry no fake edge; (b) tier the proxy
(around −35 default, around −15 for FCS top-25). Separately, have `grade.py`
report proxy games in their own line so they don't contaminate the ATS
headline. Their edge is excluded from flagging by design, so it shouldn't
be graded as if it were a pick.

**P4: confidence tiers.** Keep the current function but rename its output
to data completeness. Add a signal tier: demote to "low" when SP+ and Elo
disagree on the edge's direction, demote one level in weeks 1-4, and demote
when |edge| exceeds about 2× the slate's mean |edge|.

**P5: edge cap.** In weeks 1-4, show edges above ~8 as "likely stale rating"
rather than value. The 2-6 band is the only one worth watching.

**P6: HFA.** If anything, 2.4 → 2.8. The history supports 2.5–3.2, but the
2025 estimate of 0.5 argues for waiting.

---

## 2026-09-13 — NFL (week 1), pre-kickoff snapshot (graded 2026-09-14, see above)

Stored predictions and the stale-row comparison are in
`calibration/2026-09-13_nfl_pregame.md`. Grade after Monday. Two structural
issues were found while refreshing. They are logged as P1/P2 above because
they will bias whatever the NFL grade says:

**P1: stale injury rows (bug).** Injury rows are upserted and never cleared,
and `FeatureContext.injury_adjustment` reads every row for a team. A player
whose status *improves* gets dropped. The NFL ingester skips a player with
no game status and full practice, and ESPN simply stops listing him. His
older, worse row keeps being charged. At the 16:18Z refresh 29 of 242 NFL
rows were left over from Saturday's pulls, including Micah Parsons (out),
Brian Branch (out) and Joe Thuney (DNP). Dropping them moves NO @ DET's edge
from +0.8 to +2.0 and GB @ MIN's from −1.2 to −2.5, so both would become
flags, and nudges CHI @ CAR and BUF @ HOU. From week 2 on, old weeks' rows
will pile up too. The fix belongs in ingestion or feature building (latest
pull per team/week). It isn't a weighting change and doesn't need sample size.

*Applied 2026-09-13, before kickoff.* `features.latest_injury_report` keeps
only each source's most recent pull. It's used by `FeatureContext`, so both
baseline and ML, and by the dashboard export. Tests are in
`tests/test_injury_report.py`. The slate was re-run at about 16:35Z: NO @ DET
+0.8 → +2.0 (now flagged DET), GB @ MIN −1.2 → −2.5 (now flagged GB), CHI @
CAR −3.7 → −2.9, BUF @ HOU +2.7 → +3.7. 10 of 13 games are now past the
2.0-pt threshold. When grading, keep in mind these are the post-fix numbers.

**P2: unknown-snap QBs.** A listed QB with no snap-count history gets
`DEFAULT_SNAP_SHARE = 0.35`, so a rookie or backup ruled out costs his team
0.35 × 1.0 × 6.0 = **2.1 pts**. On this slate: Miller Moss, Haynes King, Zach
Wilson, Joe Fagnano, Taylen Green, Quinn Ewers, Will Howard (2.1 each) and
Riley Leonard (2.4). `STARTER_SLOTS` doesn't catch it, because when the
starter is healthy the only listed QB is the backup, who then takes the one
QB slot. Proposal: for QB, use `depth_charts` and charge only depth order 1,
or set the unknown-QB default share near 0. Test it by rebuilding the NFL
training set with the change and checking the holdout.
