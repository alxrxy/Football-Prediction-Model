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
| P10 | Props: apply game-day inactives before simulating | data | 2026-09-14 | DAL@NYG: 4 projected players recorded nothing (N. Harris 5.3 car, Beckham, Cambre, Abanikanda), none on the injury list; Singletary took 10 touches + TD unprojected. **Widened 2026-09-17 (DET@BUF):** this is not a sequencing problem. There is no inactives ingestion path anywhere in the pipeline, and the ESPN feed structurally cannot supply one — a full league pull at 22:50Z returned only `Active` (614), `Questionable` (134), `Injured Reserve` (40), `Out` (9), `Doubtful` (3), with no gameday inactive designation. `ingest_injuries._status` would discard one anyway (see P20, P21). Consequence at T-75 min, with the official list already public: DET@BUF still priced 4 players at the flat questionable/limited 0.55 (D.J. Reed 0.75 pts, Cole Bishop, T.J. Sanders, Ty Johnson) when each was by then resolved to 0 or 1 **Source found and confirmed 2026-09-19:** the ESPN core API per-competition roster flags inactives `didNotPlay` (DET@BUF: 8 BUF / 9 DET, incl. T.J. Sanders and Ty Johnson); 404 before posting. Week-1 payoff: 6 inactive projected players, 1.4% of projected touches (Kamara, N. Harris). See the 2026-09-19 P10 entry | acquire a real inactives source first (ESPN gameday roster endpoint or equivalent), then re-sim after it lands; track "projected, no stats" rate weekly | **built and validated on replay 2026-09-19; committed 2026-09-20 (`164fdd9`); not yet run live.** Criteria 1-5 pass; criterion 6 (posting time) needs a live Sunday. The Sunday windows run as one command, `python run_sunday.py --watch` (2026-09-20 entry). New `inactives` table: paste `db/PASTE_INTO_SUPABASE.sql` to create it upstream (the local mirror is used until then). See the 2026-09-19 P10 build entry |
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
| P28 | Starter designation: when the starter is out or disputed, the sim's next QB follows the depth chart while the market prices a different passer (SEA: Lock; ATL: Cooper Rush) | investigate | 2026-09-18 | Week 2, SEA @ ARI. Books price only Lock for SEA pass yds (207.5), with no Sam Darnold line posted. The stored sim has Darnold QB1 (17.8 att, median 172 yds) and Lock QB2 (12.0 att, **median 0**, mean 93), so the raw sim reads Lock's under at 0.746 against a market 0.500, and he sits **#2 on the ranked list**. His rushing prop (6.5) is held out as QB rushing. Looks like a depth-chart / starter-designation or injury-status mismatch, distinct from the usage and efficiency items. Not diagnosed **Second team, 2026-09-19 (targeted re-pull):** with Penix now OUT, books price **Cooper Rush** as ATL's passer (183.5, 5 books) and post no Tua Tagovailoa line, while the sim starts Tua (QB2, 18.3 att, median 156) with Rush as QB3 (12.0 att, **median 0**). So it is not SEA-specific: the sim's next man up follows the depth chart, and the books' does not. Rush's pass-yds prop is currently dropped by P29, and his rushing prop is held out as QB rushing, so nothing about it shows on the page **ATL game-level check, 2026-09-19 (read-only):** inconsistent, and the CAR@ATL numbers correspond to neither QB. (1) The sim cannot disagree with the baseline at game level: `anchored_simulation` pins the margin to the baseline's; QB identity only routes box-score credit. So the question is the baseline's −5.59 Penix charge (1.0 × 0.932 snap share × 6.0, a generic starter-out value that never asks who replaces him). (2) ATL's rating is ~94% 2025 ATL offense, whose dropbacks were split Cousins 283 (−0.023 EPA/db) / Penix 303 (+0.035): mix +0.007, so the rating is only about half Penix. **Cooper Rush started ATL's week-1 game** (Penix did not play; 57 plays, −0.321 EPA/play). (3) On the same scale (EPA/db difference × 0.603 dropbacks/play × 63), relative to the rating: Tua +0.4 (2025) to +4.3 (2024-25); Rush −7.3 (2024-26, 404 db, −0.185 EPA/db, 43rd of 44). So the correct charge is about 0 if Tua starts, and about −7.3 if Rush starts. The −5.59 charged is neither. The sim's own mix (Tua 0.6 from an nflverse row with no status, Rush 0.4) implies about −0.3 to −2.7. (4) Consequence: if Rush starts (the market's view, and who started week 1), ATL is ~1.7 pts too strong, so ≈ CAR +1.5 vs the market's CAR −2.5, with no flag either way. If Tua starts, ATL is ~6-10 pts too weak and the true number is an ATL edge. The edge's sign depends on the QB, and the served number reflects neither. The ML model uses the same generic `qb_availability_loss`. **Labelled 2026-09-19 at the user's call** (see status) | the sim's QB1 for every team matches the market's priced passer (or the confirmed starter) before props are ranked; a priced QB2 with sim median 0 is flagged, not ranked | **part 2 tested and REJECTED 2026-09-20.** Replacement-value charge, k = 0.780 fitted on 2022-23 and judged on 2024-25 with real injury reports: restricted to P28's scope it loses to the flat rule on both the cover-residual correlation (+0.250 -> -0.021 on the 132 firing games) and margin MAE (11.299 -> 11.490). The market already prices QB changes, corr(term, spread) = -0.324. The flat charge stays. **Part 1 still open:** the depth chart names the wrong starter in 9.6% of team-games; nflverse schedules carry the expected starter and get SEA (Drew Lock) right today | the sim's QB1 matches the expected starter, and a priced QB2 with sim median 0 is flagged, not ranked | part 2 closed; **part 1 proposed** |
| P29 | Props: `market_view` silently drops a prop when two lines tie for most books | bug fix | 2026-09-19 | `point = median(tied modal lines)`: with an even number of tied lines, the median is a line no book posts (Cooper Rush 182.5 ×2 / 183.5 ×2 → 183.0), no book matches it, and the prop returns None: never ranked or held out, and not counted as unmatched either. **37 of 424** priced player-markets on the 2026-09-19 lines (38/398 on the 9/17 file), and they are skewed to starting QBs' pass yds (Herbert, Mayfield, Purdy, D. Jones, Willis, Stafford/Dart on 9/17). The 2026-09-18 pass-yds offset refit (n=20) and the 9/16 fits were therefore taken on a sample missing these props | every priced player-market either produces a row or is counted as a named exclusion; then refit the pass-yds offset on the full set | tie broken toward the posted line nearest the consensus; no prop that already had a line changes | **FIXED 2026-09-20.** 37 of 424 recovered (8.7%), 0 still lost, 0 lines changed; 1 test, 7 checks. Refit on the complete sample measured and logged: pass yds -0.0212 -> **+0.0732** (sign flip), QB rush -0.1818 -> -0.2564; receiving barely moves. refit **applied 2026-09-20** before the first window: 15 Stage 1 flags before and after, one swap |
| P30 | Why did 2026 week 1 show a 0.80 / 1.24 receiving-yards tercile split when the 2025 walk-forward shows 0.97 / 1.01? | investigate | 2026-09-19 | The P17 walk-forward found the current engine, given each receiver's targets and pre-week category mix, within ~3% per tercile across 2025 weeks 11-18. The 2026-09-18 week-1 check (n=138 starters, one week) measured 0.80x yards for the top tercile and 1.24x for the bottom. Candidates: one-week noise and selection; or the SIMULATED target distribution (who gets how many deep vs short targets, which the walk-forward held at each player's own historical mix) rather than efficiency. Distinct from P17 (efficiency given targets) and P25 (target volume) | to be written into this log when the diagnosis is scoped, before it runs (process rule, 2026-09-19) | **answered 2026-09-20: one-week noise.** Re-measured on every comparable window with a bootstrap CI; the 2026 wk 1-2 top tercile is 0.906 [0.793, 1.051], CI spanning 1.00, and pooled compression is 3-5%. Not the props bias. See the 2026-09-20 entry | **closed** |
| P31 | Receiving: the target-share vector is flattened, so priced receivers get ~0.85 of their real targets | bug fix | 2026-09-20 | Healthy priced receivers (n=124): sim/real targets 0.851, catch rate correct (0.673 vs 0.668), team pass att 0.972. By quartile of real target share (n=277) the sim/real share runs 1.065 / 0.800 / 0.803 / **0.755**. Localised to `usage_rates`, which takes each player's share over the games he appeared in: a rotational WR5 is carried at ~1.93x his per-team-game rate, the per-team vector sums to **1.131**, and `team_shares` divides it out proportionally so the biggest shares pay the most. 0.890 x 0.972 = 0.865 vs 0.851 measured end to end. This is the receiving under-bias (receptions -0.119, rec yds -0.099 raw vs market) | see the six criteria in the 2026-09-20 entry; Q4 and Q1 share ratios in 0.95-1.05 out of sample, team totals within 1%, rushing not regressed | **ON since 2026-09-21** (flag default flipped, `BIAS_FIT` refitted). Built 2026-09-20; P10 vs P31 on the live Sunday: P10 closes 2% of the receiving gap, P31 51%. Graded against week-2 outcomes (2026-09-21 entry): props Brier improves but inside noise, RB rushing worse this week, and the trimmed players took 5.1% of real targets, not ~0, so the trim overshoots. Criteria 1 and 2 still fail |
| P32 | Target-category shares are computed on overlapping sets but picked on disjoint ones | bug fix | 2026-09-20 | `_usage_events` builds `tgt_deep` / `tgt_short` over **all** targets including red-zone ones, while `simulate._credit` picks rz, then non-rz deep, then non-rz short — three disjoint buckets. Red-zone targets are counted twice. Measured on 2025 (230 receivers, 25+ targets): engine/true share median 0.990 deep, 1.001 short, per-player p10-p90 0.90-1.22; effect on simulated volume 0.998 targets, 0.996 yards, and terciles 1.005 / 1.000 / 1.000. Real but minor, and **not** part of P31: stage 4 of the P31 decomposition adds nothing (0.893 vs 0.890) | engine share within 2% of the true disjoint share at p10 and p90; no change to team totals | proposed, low priority |
| P33 | Inactives: a roster read hours before kickoff is stored as a posted list | bug fix | 2026-09-20 | `ingest_inactives.fetch` treats HTTP 200 + any `didNotPlay` entry as a posted list, and `LOOKAHEAD_HOURS` asks 12 h out. On the live 9/20 slate that stored 11 late-window team lists (T-4.3h to T-8.6h) that are not inactive lists at all: **93% of their ruled-out players are missing from them** (28 ruled out, 26 absent), against 39% for the 16 genuine T-72m lists. SEA's 9-man list omits Sam Darnold, who is ruled out; DEN's list has 1 player and misses all 9. Re-polled 15 min later, every list was byte-identical, so they are stale content rather than a list still filling. **List size cannot separate them** (bogus lists run 6-9, genuine 7-12); lead time separates them perfectly, 16/16 vs 11/11. Consequence is worse than a bad list: `features.apply_inactives` treats any team with a "posted" list as resolved, so every *unlisted* questionable player is promoted to play probability 1.0 - RJ Harvey (DEN, questionable RB) was flipped questionable -> active off the 1-player list | no stored list for a game more than 2 h from kickoff; on a live Sunday the stored lists cover >= 40% of ruled-out players **in aggregate** (genuine 60.6% vs premature 7.1% on 9/20; a per-list threshold is invalid, since an IR player is never on a gameday inactive list and genuine per-team coverage runs 0-100%); the 16 genuine T-72m lists of 9/20 are unchanged by the fix | **applied 2026-09-20**: `LOOKAHEAD_HOURS` 12.0 -> 2.0 in `src/ingest_inactives.py`. Validated live at 16:17Z (16 lists / 153 rows accepted, unchanged; 7 games skipped). New test pins the gate at 8.6/4.3/2.5 h rejected vs 1.58/1.25 h accepted, against a full-looking 7-man roster so it cannot be re-derived from list size; suite 438 pass. The 11 premature lists (71 rows) deleted and the slate re-predicted, re-simmed and re-exported |
| P34 | CLV: the fallback close is the median of American odds, which have no values between -100 and +100 | bug fix | 2026-09-20 | `clv.snapshot_close` takes `median()` over each book's American price at the consensus line. That scale is **discontinuous** - no odds exist strictly between -100 and +100 - so when the books at a line straddle the boundary the median lands in the gap and yields a price that cannot exist. CIN@HOU: away prices at -2.5 were [-108, -105, -102, +100, +100, +104], median **-1.0**, stored as -1. `market.implied(-1)` = 0.0099, so a coin-flip side reads as a 1% chance; `devig([-116, -1])` returns home 0.9819 against a true ~0.517, and with `p_market` 0.5223 that is **clv_pp +0.4596** - the stored value exactly. Correct probability-space median gives home 0.5171, so true CLV is **-0.5pp, not +46pp**. The equal-and-opposite values across models are not a side-orientation bug: the two models leaned opposite sides, so `own()` flips one corrupt number twice | a straddling price set must yield a valid price and a CLV near 0 when the line did not move; no stored close price strictly between -100 and +100; the 187 `espn:draftkings` closes must be byte-identical after any fix | **diagnosed 2026-09-20, NOT fixed; queued for the week of 2026-09-22.** Blast radius is 4 of 215 closed rows, all NFL, all today, all via `oddsapi_last_pregame`, 1 of them a flagged lean; the 187 `espn:draftkings` closes are immune by construction, so the CLV history before today is clean. The fix is to take the median in **probability space** (`market.implied` per book, median there, convert back), which is continuous and has no gap. **The two latent sites are in scope of the same item**, since they share the mechanism: `ingest_odds` consensus moneylines (`int(_median(ml_h))`) and `market.side_price`. Neither is firing now - 0 of 389 consensus rows hold a moneyline in the impossible range - so they are a guarded check plus the same probability-space treatment, not a second investigation |
| P35 | Live sim: no structured in-game player status, so an injured player keeps his projection | open gap | 2026-09-21 | MNF NYG@LA: Dart hurt at 1Q 11:28, Winston threw every NYG pass after it, yet the live passer stays Dart (argmax of pass attempts so far) until Winston out-throws him. Searched the core API for a structured signal: roster `active` is False and `period` 0 for all 55 entries mid-game (placeholders, not on-field status); play `participants` list only stat roles (0-5 per play), never the 11 on the field, so there is no snap participation; the only injury signal is free text ("NYG-J.Dart was injured during the play."), and most players tagged so return. 'His stats stopped updating' is not a signal either: stats move only on a touch, and healthy receivers routinely go a quarter or more without one | a structured source that marks a player out for the game, with a replayed false-positive rate near zero; until then nothing is built. Explicitly not adopted: play-text parsing, social media, or stat-silence inference, since a false 'out' corrupts live predictions worse than a stale passer | **open, nothing built.** Accepted current state: a stale passer projection until the box score catches up. Live-sim team numbers are barely affected; the injured QB's and his backup's lines are wrong meanwhile |
| P36 | ATS: a zero edge (model spread = stored line) is graded as backing the away side | grading rule | 2026-09-21 | `grade.evaluate` sets `took_home = float(edge) > 0`, so edge 0 falls to the away side and gets a W/L; `export_dashboard` (`_ats`, `_graded_pick`) matches it deliberately so the Record page adds up to the grader. With no edge the model had no side, so arguably the pick should be no-action (like a push) and leave the ATS denominator. Blast radius today: **1 of 226 stored predictions** - ml-v1 on 2026_01_GB_MIN (model -1.5, line -1.5), graded L. It moves ML's season ATS by one game: 9-20-1 as graded vs 9-19-1 as no-action; baseline unaffected | decide the rule once, then apply it in `grade.evaluate`, `export_dashboard._ats` and `_graded_pick` in the same change so the grader and the page never disagree; the grader CLI and the Record page must show identical ATS totals after the change; slate reports (`calibration/analyze_nfl_slate.py` already treats edge 0 as no lean) reconciled to the same rule | **open, deferred - leave grading as-is mid-season (decision 2026-09-21).** Not urgent: one game. Note the slate-report script already disagrees with the grader here (it drops edge 0), and `calibration/2026-09-13_nfl.md` shows GB @ MIN's ML ATS as "—" (no action) where the grader and the Record page count it an L |
| P37 | Baseline ATS gets worse as its edge grows (4+ pts: 4-10-1 season, week 1 1-4, week 2 3-6-1) - why? | investigate | 2026-09-21 | Two weeks of negative best-fit weight on the edge (w = -0.64 week 1, -0.68 week 2). Overlaps P5 (stale early-season ratings), P22 (defense-heavy, unadjusted rating), P9/P2 (injury charges) | diagnosis only; the questions, tests and decision rules are in the 2026-09-21 scoping entry and were written before any test ran | **diagnosed 2026-09-21: noise, by the pre-set rules.** The 2026 gradient is not significant (slope perm p 0.27, corr p 0.11). The live Layer 1 replayed over 2016-2025 (reproduces live exactly) shows no negative early-season relation (weeks 1-4 corr +0.05, CI -0.03 to +0.13). The bigger finding: across 2,582 games the baseline edge covers **~50% at every size** (b = -0.02, CI -0.13 to +0.08), so it carries essentially no ATS information at any edge size. No fix proposed. See the 2026-09-21 findings entry |

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

## 2026-09-22 — Standing rule: baseline flags are "not yet statistically validated" (display only)

**Decision (user, 2026-09-22), closing the checkpoint's open policy question.** Baseline value flags are not treated as trustworthy. They stay on the dashboard for tracking, labelled "not yet statistically validated", and are not presented as an actionable signal. Basis: P37 (the replayed baseline edge covers ~50% at every size) and baseline flags 3-10 over weeks 1-2.

**Re-trust condition (corrected before adoption).** The first wording, "until the P37 slope test clears p < 0.05", was dropped: that test is one-sided for slope < 0, so passing it would confirm the problem. The condition adopted is positive evidence that the flags win:
- count every graded baseline flag from 2026 week 1, pushes excluded, per sport;
- at least **50** decided flags; and
- one-sided binomial P(wins >= observed | p = 0.524) **< 0.05**. At 50 that means 33-17 or better, at 75 it's 47-28, and at 100 it's 62-38.

It's checked automatically on every dashboard load from the exported flag record (`dashboard/src/flagTrust.js`), and the label comes off by itself when the condition is met. The P37 script is still re-run weekly as a diagnostic, but it no longer controls this label. Given the ten-season replay, the condition may never be met with Layer 1 as it stands.

**Scope: display and trust labelling only.** No change to the edge calculation, Layer 1/2, the Stage-1 blended test, `is_value`, `clv_log` or grading. The flag is still computed, stored and graded exactly as before. The rule covers `baseline-v1` flags only (ml-v1's value gate is separately shut) and applies to NCAAF baseline flags too (18-19 to date).

---

## 2026-09-21 — CHECKPOINT (session paused). Next session: read this entry before taking any action

**State when paused**
- Everything is committed and pushed to `origin/main`. The working tree is clean except `cross-sport-research.md`, which is untracked, predates this work and was deliberately left alone.
- Nothing is running or waiting on a timer. The live tracker exited by itself after MNF (03:12Z). The Q&A server started this session was stopped. A dashboard dev server on :5174 that predates this session was left running.
- Week 2 is fully graded (16/16). The Record page shows flagged picks and ATS by edge size, season beside each week.

**P37: diagnosed, no code bug.** Neither the injury term, the prior-season ratings nor P22's defence concern explains the 2026 "bigger edge = worse ATS" gradient. By the pre-set rules it's noise: 2026 slope permutation p 0.27, and the replayed live Layer 1 covers ~50% at every edge size over 2016-2025 (2,582 games). Full findings are in the entry below.

**Open question: a policy decision, not a fix.** Should baseline edges drive value flags at all? Baseline flags are **3-10** across weeks 1-2 (week 1 3-8, week 2 0-2), and the ten-season replay says the baseline edge carries ~no ATS information at any size. Relates to P5 and the Stage-1 gate.

**Small-sample leads, not conclusions.** |injury adj| >= 2 went **0-7**; games charging a starting QB (>= 2.5 pts) went **1-6** (n = 7 each, 2026). These reinforce **P9** (injury-term magnitude) and **P2** (unknown-snap QB charges). They are not findings on their own.

**Recommendation on the table (a standing decision, no code change):** stop treating baseline-flagged edges as trustworthy. Re-run `calibration/p37_edge_diagnosis.py` weekly.
- **The re-trust condition needs correcting before it's adopted.** As first worded ("until the 2026 slope test clears p < 0.05"), it points the wrong way. That test asks whether bigger edges do significantly *worse*, so reaching p < 0.05 would confirm the problem, not clear it. The condition for trusting flags again has to be evidence the edge **helps**: for example, a significantly *positive* edge-vs-cover relation, or flagged picks beating the 52.4% break-even over a pre-set sample. It has to be judged against the replay, where ten seasons showed no positive relation, so re-trust may never come from Layer 1 as it stands. **To be decided with the user; not yet set.**

## 2026-09-21 — P37 findings: the 2026 gradient is noise, but the baseline edge carries ~no ATS information at any size

Script `calibration/p37_edge_diagnosis.py`, full output `calibration/2026-09-21_p37_edge_diagnosis.md`. Tests and rules as scoped in the entry below, fixed before running. **Diagnosis only; nothing changed in the model.**

**Ruled out by construction: PENALTY_REPLAY and P24.** Confirmed by grep: `predict_baseline`, `features`, `market`, `clv` import nothing from `simulate`, `sim_data` or `live_sim`. Simulator changes can't move a baseline edge.

**Test 1, significance (2026, n = 30).** Slope of the lean-direction cover margin on |edge| is -0.42 pts per point of edge: permutation p **0.27** one-sided, 0.64 two-sided. corr(edge, cover residual) is -0.23 (95% CI -0.55 to +0.14), permutation p **0.11** one-sided. >= 4 pts 4-10, binomial p 0.09 (descriptive only, since the cut-off was picked after seeing the data). **Bigger edges have not done significantly worse than smaller ones.** What stands out is the overall 9-20 (binomial p 0.06 two-sided): the leans lose at every size, not only the big ones.

**Test 2, replay (2016-2025, 2,582 regular-season games).** The live Layer 1 rebuilt week by week matches the stored 2026 values **exactly** (30/30, max difference 0.00), so the replay is the live formula. Adding the live HFA / rest / travel / wind terms (no injury term):

| games | n | >= 0 | >= 2 | >= 4 | >= 6 | corr(edge, cover resid) | b |
|---|---|---|---|---|---|---|---|
| weeks 1-2 | 309 | 52% | 51% | 54% | 52% | +0.07 (-0.04, +0.18) | +0.16 (-0.14, +0.45) |
| weeks 1-4 | 615 | 49% | 51% | 50% | 50% | +0.05 (-0.03, +0.13) | +0.13 (-0.10, +0.35) |
| weeks 5-18 | 1967 | 50% | 49% | 49% | 47% | -0.03 (-0.07, +0.02) | -0.07 (-0.20, +0.05) |
| all weeks | 2582 | 50% | 49% | 49% | 47% | -0.01 (-0.05, +0.03) | -0.02 (-0.13, +0.08) |

There is no early-season anti-information: weeks 1-2 and 1-4 lean slightly positive, and not significantly so. Per-season weeks 1-4 correlations run -0.08 to +0.20. Two of ten seasons (2021, 2025) went 41-42% ATS in weeks 1-4, so a bad 30-game start is ordinary for this edge. **The edge is close to zero-information at every size and every point of the season.** Caveat: nflverse's `spread_line` is close to a closing line, sharper than the line the live model is graded against, so the replay is a somewhat harsher benchmark.

**Test 3, decomposition.** 2026: the injury term is not the driver (corr +0.05, CI -0.32 to +0.40). The rating-plus-situational part carries the negative sign (-0.26, perm p 0.08, not significant). Replay, weeks 1-4, cover residual regressed on the parts: prior-season offence +0.03 and prior-season defence +0.16, current-season offence -0.38 and defence -0.52, situational -2.30, **every 95% CI spanning 0**. No part is negative in both 2026 and the replay, so **no component passes the component-driven rule.** P22's defence-heavy concern doesn't show up as a harmful part historically: prior-season defence is, if anything, slightly positive.

**Test 4, scale.** 2026 b = -0.61 (CI -1.50 to +0.27). Replay all-weeks b = -0.02 (CI -0.13 to +0.08). The rule's "inside (0, 1)" is **not met**. There's no sign of an edge that points the right way but is too large; there's barely any edge. **2026 edges are larger than usual, though:** mean |edge| 4.52 vs 3.73 in replayed weeks 1-2, with 50% of picks at >= 4 pts vs 37%. That holds without the injury term (4.33), and the replay is exact, so it's the inputs (how far the 2026 lines have moved from 2025 form), not code. Larger swings from a near-zero-information signal make the visible records swing harder.

**Test 5, concentration (exploratory).** |injury adj| >= 2 went 0-7, and games charging a starting QB went 1-6. Leaned-underdog went 2-10 vs leaned-favourite 7-10-1. With n = 7-12 per cell, these are leads for P9 / P2, not findings. Post-hoc check (not in the plan) on the replay's situational coefficient: leaning home went 47% in weeks 1-4 vs 52% leaning away (z about -1.1), and the mean home cover residual is -0.24 pts, so HFA 1.9 looks about right. Nothing there.

**Verdict by the pre-set rules**
- **Noise: yes.** The 2026 gradient's permutation p is above 0.05 and the replay shows no significant negative relation in weeks 1-4.
- **Early-season structural: no.** The replayed weeks 1-4 correlation and b are both positive, CIs spanning 0.
- **Scale / overconfidence: no.** The replay's b CI spans 0 rather than sitting inside (0, 1).
- **Component-driven: no.** No part is negative in both 2026 and the replay.

**What it means (no fix proposed).** The pattern on the Record page is what a near-zero-information edge produces in 30 games: long-run ~50% at every edge size, with a bad start inside the range seen in past seasons. There's nothing in the edge calculation to patch for a gradient. The question the evidence does raise is upstream: across ten seasons, the baseline's disagreement with the line has not been where value is, at any size. That bears on P5, and on whether baseline edges should drive Stage-1 flags at all. It's a decision about the gate, not a bug fix, and is left open here.

**Re-run each week:** `python calibration/p37_edge_diagnosis.py <pbp_dir> <out.md>` (the pbp pull is in the script's docstring). What would change the verdict: the 2026 slope's permutation p falling below 0.05 as weeks accumulate, which would make this a 2026-specific input problem worth tracing.

## 2026-09-21 — P37 scoped: why bigger baseline edges cover less often (diagnosis only, written before running)

**Question.** Across the 30 graded 2026 NFL games, the baseline's ATS record gets worse as its edge over the stored line grows (all picks 9-20-1, >= 4 pts 4-10-1, >= 6 pts 1-6-1), in both weeks. Is that (a) noise, (b) something built into early-season ratings, (c) one component of the edge (ratings, injuries, situational terms) pushing the wrong way, or (d) a scale problem, meaning edges too large for the information behind them? **No fix is proposed until this reports.**

**Ruled out before testing: PENALTY_REPLAY and P24.** Both change only the simulator. `predict_baseline` and `features` import only `clv`, `config`, `db`, `market`. Baseline edges come from Layer 1 (EPA power rating) plus Layer 2 (HFA, rest, travel, wind, injuries) minus the line, with no simulator input. I'll confirm this by grep in the report, not by test.

**Tests**
1. **Significance on 2026 (n = 30 baseline picks).** Stat: the slope of the lean-direction cover residual on |edge|, plus corr(edge, home cover residual), each with a permutation p-value (10,000 shuffles of results against edges). Also the binomial p for >= 4 pts at 50%. **Caveat stated up front:** the >= 4 cut-off was chosen after seeing the data, so its p-value is descriptive, not a test.
2. **Historical replay, 2016-2025.** Rebuild the live Layer 1 exactly (`ingest_nflverse` formula: prior season x 0.75 regression, 900-play blend, centred on the league) as of each week from nflverse pbp, add HFA 1.9 (0 neutral) and the live rest/travel terms with their caps; no injury term (the live injury layer has no historical equivalent). Edge = model margin - (-line), graded against the training file's line. Report ATS by |edge| bucket and corr(edge, cover residual) for weeks 1-2, weeks 1-4 and weeks 5+.
3. **Decomposition on 2026.** Split each edge into rating-plus-situational (Layer 1 + HFA/rest/travel - line) and the injury term. For each part: corr with the cover residual, and the >= 4 record with that part removed. Split the Layer 1 gap of the big-edge games into prior-season vs current-season, and offence vs defence (P22).
4. **Scale.** Fit actual margin = -line + b x edge on 2026 and on the replay, with a 95% CI on b. b < 0 means the edge points the wrong way; 0 < b < 1 means it points the right way but is too large. Also compare the size of 2026 edges against replayed weeks 1-2 edges.
5. **Concentration (exploratory, n too small to test).** Split 2026 results by leaning the favourite vs the dog, leaning home vs away, |injury adj| >= 2, and QB-change games.

**Decision rules (fixed now)**
- **Noise:** test 1 permutation p > 0.05 **and** replayed weeks 1-4 show no significantly negative relation (corr's 95% CI includes 0 or is above it).
- **Early-season structural:** replayed weeks 1-4 (or 1-2) corr(edge, cover residual) < 0 with p < 0.05, **or** b < 0 with its 95% CI below 0. This reads on the replay, not on 2026 alone.
- **Scale / overconfidence:** replay b's CI lies inside (0, 1). The edge carries information but is too big.
- **Component-driven:** one component has a clearly negative corr with the cover residual in 2026 **and** is also negative in the replay where it can be replayed (the injury term cannot be). 2026-only component findings are labelled exploratory.
- More than one can hold. If 2026 shows it and the replay doesn't, the verdict is "2026-specific input, not structural", and the 2026 inputs that differ from the replay are the next place to look.

## 2026-09-21 — MNF: live box score restored through the core API; in-game injury status is an open gap (P35)

site.api.espn.com still refused every request (403) tonight, and the summary endpoint is on that host, so the live simulation had **no box score at all**: projected player lines were the simulated remainder only (no so-far), the usage blend had nothing to blend, the passer was unknown, and touchdowns / field goals so far read zero. `live_tracker.core_summary` now rebuilds the two parts the live sim reads (`boxscore.players` from per-athlete roster statistics, `scoringPlays` from the plays feed) whenever the summary call fails, so `live_sim.game_usage` and `scoring_so_far` run unchanged. About 25 calls per poll, run in parallel, taking 1-2 s. If any line can't be read, the whole rebuild is dropped rather than understate that player. The live start state (`drives`) is still not rebuilt, so it reads as a coin-flip kickoff while site.api is down.

Validated at 1Q 7:46 against the play-by-play, every field exact: NYG Skattebo 4-14, Singletary 2-7, T. Johnson 3 tgt, Dart 3/5 20, Winston 0/1; LA K. Williams 1-3 rush + 1/1 rec, Adams 1 tgt, Stafford 1/2. One `--once` cycle wrote a live row with usage opportunities NYG 6 tgt / 6 car, LA 2 / 1. A DPI-nullified Winston throw at 7:06 was correctly **absent** from the stats, a case play-feed counting would have had to handle by hand.

In-game player status: searched and **not available in structured form** (see P35). Nothing built. A false "out" would corrupt the live prediction, which is worse than the current stale-passer state.

## 2026-09-21 — P31 flipped ON. The six criteria against real week-2 outcomes: partly matches the dry run

`USAGE_PARTICIPATION_TRIM` now defaults to on (`config.py`), and `BIAS_FIT` is refitted with it on.
This follows the 9/20 P10-vs-P31 recommendation. **Week 2's stored `game_simulations` were NOT re-simulated.**
By the time of the flip, nflverse pbp held all 15 played week-2 games, and `load_inputs` has no as-of cutoff.
A re-sim would have fed week-2 usage, PROE, scramble rates and schedule QB ids into week-2 sims, and it would
have overwritten the pregame rows that grading and CLV read. The before/after below uses the 9/20 pregame
in-memory runs instead (same seeds, P10 applied, 12:00 CDT lines, 14 Sunday games), graded against the box
scores. Only the one unplayed week-2 game (NYG @ LA, MNF) was re-simulated and stored with the trim on. Props
were regenerated from those sims. The 23:00Z MNF refresh will redo it with inactives, flag on by default.

**Method.** Criteria 1-3 rebuild the roles vector through the production functions (`player_roles`,
`_participation_trim`), point-in-time at the 15:48:41Z production run. Pbp and snap counts are cut to games
that kicked off before then, and the depth chart to snapshots before then (latest 12:14:30Z). The vectors are
scored against real week-2 targets in the 14 Sunday games (28 teams, 837 targets, 439 pool players). Criteria
4-6 use the pregame runs. Box lines come from nflverse pbp, because ESPN site.api was refusing. Names are
matched through week-2 weekly rosters. All 391 paired props were matched. Six priced TEs who were active (ACT,
not on the inactives table) with no touch are graded as 0, not void.

| # | criterion | dry run 9/20 (off → on) | week-2 outcome (off → on) | verdict on outcomes |
|---|---|---|---|---|
| 1 | per-team raw target-share sum within 0.02 of 1.00 | 1.132 → 1.032 | 1.131 → 1.032 | **fail**, same as dry run (a pregame property) |
| 2 | Q4 *and* Q1 share ratio in 0.95-1.05 | Q4 0.889 → 0.978, Q1 1.086 → 1.118 | by **realised**-share quartile: Q4 0.623 → 0.678, Q1 1.537 → 1.544 | **fail**; this definition is unusable on one week (see below) |
| 2b | same, by **pregame**-share quartile, real/sim | — | Q4 1.016 → **0.924**, Q1 1.024 → 1.464; top-2 receivers per team 1.016 [0.890, 1.157] → **0.926 [0.809, 1.057]** | **differs from dry run**: this week the trim over-credits the top |
| 3 | share MAE not worse | 0.0251 → 0.0265 (fail) | 0.0413 → **0.0382** | **pass**, 7.5% better |
| 4 | team totals within 1% | 0.000% | 0.000% | **pass** (the play stream is identical) |
| 5 | rushing not regressed | RB gap −0.045 → −0.001, QB +0.084 → +0.094 | RB Brier 0.2698 → **0.2918**, actual over rate **0.292** (n=48); QB 0.2530 → 0.2541 | **pass vs market, fail vs outcome** this week |
| 6 | receiving raw P(over) toward ~0.50 | 0.405 → 0.453 (51% closed) | mean 0.407 → 0.453 vs actual over rate **0.464**; Brier 0.2782 → 0.2753, on−off −0.0029, game-clustered 95% CI [−0.0131, +0.0059] | **pass on direction, inside noise** |

Market Brier on the same props: receiving 0.2471, RB rush 0.2503, QB rush 0.2555, pass yds 0.2492 (sim 0.2509
either way). The market beats both arms on every group except QB rushing.

**Criterion 2 as written cannot be read on one week.** Ranking players by their *realised* one-week share
selects on the outcome. The top realised quartile holds the players who beat their share that week, so
regression to the mean alone puts Q4 far under 1 and Q1 far over, whatever the model does. The 2025
walk-forward pooled eight weeks, which is why it was usable there. Row 2b bins by the pregame share instead,
which does not select on the outcome.

**What differs from the dry run, and why it matters.** The trim removes 2.76 of raw share mass across these 28
teams (0.099 per team, 132 players). Those players took **43 of 837 real targets (5.1%)**, and 20 of them
caught at least one. The largest was Germie Bernard (PIT, 8 targets), one of the two priced players the trim
zeroes while active. So the premise is only half right: the pool carries about 5 points of excess share,
not 10. The trim deletes all of it, and the top-2 receivers end up 7-8% over-credited against the week's
reality, where the untrimmed vector was on the mark (1.016). The CIs overlap and neither excludes 1, so one
week cannot separate the two. It is the opposite sign from the market comparison, though. It fits criterion
1's residual (1.032, not 1.00) and the Q2/Q3 overshoot already logged. RB rushing looks worse because RB unders
swept week 2 (29% hit the over, against a market 0.500). The trim moved backs from 0.456 to 0.500, onto the
market, so that one is mostly the week, not the trim.

**Refit.** Same method, fitted on the trim-on pregame sims of this sample:

| offset | committed (9/19 sims, trim off) | same method, trim off, this sample | **new (trim on)** | n | raw bias on |
|---|---|---|---|---|---|
| receptions | +0.5522 | +0.4662 | **+0.2315** | 144 | −5.13pp |
| rec yds WR | +0.4342 | +0.3512 | **+0.1605** | 73 | −3.64pp |
| rec yds TE | +0.5417 | +0.4813 | **+0.2771** | 36 | −6.31pp |
| rec yds RB | +0.2668 | +0.2982 | **+0.1296** | 36 | −3.11pp |
| rush yds RB | +0.1929 | +0.1989 | **+0.0036** | 48 | −0.08pp |
| rush yds QB | −0.2564 | −0.3539 | **−0.4005** | 26 | +9.41pp |
| pass yds | +0.0732 | −0.0486 | **+0.0732, kept** | 28 | +1.16pp |

The control column is the same method on the trim-off sims of the same sample, and it lands up to ~0.09 from
the committed fit. That is the refit's sampling noise from changing samples alone. Pass yds is bit-identical
with the trim on or off, so it keeps its n=32 fit rather than moving on noise.

**Open, not closed by this:**
1. **Overshoot.** The trimmed pool still took 5.1% of targets. A trim that removes share only down to what those
   players actually take (or a lower tau, or a floor share for trimmed players who are active) would sit between
   the two arms. Criteria 1 and 2b point the same way. Worth a walk-forward, not a guess.
2. **Re-grade after week 3.** One week of outcomes cannot confirm or overturn the 2025 walk-forward (Q4 0.801 →
   0.919 over eight weeks). Pool weeks 2-3 on row 2b and the props Brier before tuning anything.
3. `load_inputs` has no as-of cutoff. Any re-sim of a finished week leaks that week. Needed if past slates are
   ever to be re-simulated honestly.

Scratch: `p31_flip_eval.py`, `p31_extra.py` (session scratchpad). 129 tests pass.

---

## 2026-09-20 — P34 diagnosed: the CLV fallback close medians American odds, which have a hole in the middle

Found while checking why the CLV report's spread jumped from sd 1.05 pp this morning to **sd 12.39 pp** this
evening. Diagnosis only; nothing changed.

**The bug.** `clv.snapshot_close` builds a consensus close by taking `median()` of each book's American price at
the consensus line. American odds are **discontinuous**: they run ... -102, -101, +100, +101 ... and *no value
exists strictly between -100 and +100*. When the books at a line straddle that boundary - which is normal at a
near-pick'em price - the median falls into the gap and produces a price that cannot exist.

**Worked through, CIN@HOU.** Books at -2.5 priced the away side [-108, -105, -102, **+100**, **+100**, **+104**].

| step | value |
|---|---|
| `median(away)` | **-1.0**, stored as `-1` |
| `market.implied(-1)` | **0.0099** - a coin flip read as a 1% chance |
| `devig([-116, -1])` home | **0.9819** |
| stored `p_market` | 0.5223 |
| `clv_pp` = 0.9819 - 0.5223 | **+0.4596** - exactly the stored value |
| probability-space median instead | home **0.5171** -> true CLV **-0.005**, i.e. **-0.5 pp** |

So a lean whose line never moved (-2.5 to -2.5) was recorded as +46 pp of closing line value. The chain closes
on the stored number exactly, so this is the mechanism and not a guess.

**The equal-and-opposite pattern was a red herring.** baseline-v1 and ml-v1 leaned opposite sides of the same
game, so `own()` flips the *same* corrupt probability twice and prints +0.4596 and -0.4596. That looked like a
side-orientation bug in `apply_close`. It is not: `apply_close` is behaving correctly on a poisoned input.

**Blast radius: 4 rows, and the history is clean.**

| | rows |
|---|---|
| `clv_log` total | 225 |
| with a close | 215 |
| close from `espn:draftkings` | **187** |
| close from `oddsapi_last_pregame` | 28 |
| **with an impossible close price** | **4** (all NFL, all 2026 week 2, 1 of them a flagged lean) |

The ESPN path is immune by construction: it reads one book's own two prices, so there is no cross-book median to
fall in the gap. **Every CLV close before today came from that path**, so the concern that earlier-week judgment
calls were distorted does not hold - they were not. `snapshot_close` is only reached when `espn_close` fails, and
ESPN only started failing at about 15:47Z today (the 403 block, see below), so this code path had barely run
before.

What *was* wrong is the **printed summary**: 4 rows carrying +/-46 pp dragged the reported sd from ~0.1 pp to
12.39 pp and produced the "flagged, mean -22.34 pp" line. The aggregate was wrong; the per-row history behind it
was not.

**Queued for the week of 2026-09-22, not built.** Take the median in **probability space** -
`market.implied` each book's price, median those, convert back (or devig the pair of medians) - because
probability is continuous and has no gap.

Pass criteria, as logged in the tracker row:
1. A straddling set like [-108, -105, -102, +100, +100, +104] yields a valid price and a CLV near 0 when the
   line did not move.
2. No stored close price falls strictly between -100 and +100.
3. **The 187 `espn:draftkings` closes reproduce byte-identical**, which is the guard that the fix touches only
   the consensus path.

**The same pattern exists in two more places, and they are part of this item rather than a separate one**, since
the mechanism is identical: `ingest_odds` medians moneylines across books (`int(_median(ml_h))`) and
`market.side_price` medians spread prices at a line. Checked: **0 of 389** `oddsapi_consensus` rows currently
hold a moneyline in the impossible range, so both are latent. That makes them a guarded check plus the same
probability-space treatment, not a second investigation - but they should land together, because fixing only the
CLV path would leave the identical trap live in the odds pipeline.

### Known limitation of today's CLV numbers specifically

Logged as a limitation, not a defect, since the cause is the ESPN block and nothing here can fix it: with
`pickcenter` unreachable, every close captured today came from `snapshot_close`, i.e. **our own last pregame odds
snapshot at about T-72 minutes** rather than an actual closing line. Today's CLV is therefore "value against a
72-minute-early line", which is a weaker and slightly noisier measure than it is labelled. The 24 rows from that
path that are *not* corrupted by P34 are still measured against that early line, and should be read with that in
mind. They will not be recoverable after the fact; the closing prices are gone once the games end.

---

## 2026-09-20 — live_tracker: a core-API fallback, after site.api.espn.com started refusing every request

`site.api.espn.com` is the only host the live tracker reads, and from about 15:47Z it answered every request with
an Akamai **403 "Access Denied"**. That is not a network failure, though `safe_get_json` reports it as a
`FetchError`, which is what made it look like flaky connectivity for a while. Confirmed by hand: a plain request
and a full browser set (Chrome UA, `Accept`, `Accept-Language`, `Referer`, `Origin: espn.com`) both return 403,
so it is an edge block rather than a user-agent check. DNS resolves normally.

`sports.core.api.espn.com` - the host `ingest_inactives` already uses - kept serving 200 throughout. That split
explains the whole day: P10's inactives worked all morning while the injuries feed, `export_sims`' scoreboard
call and the tracker all warned or died.

**The fix.** `live_tracker.core_scoreboard()` rebuilds a scoreboard-shaped payload from the core API and hands it
to the **unchanged** `parse_scoreboard`, so no parsing, no `LiveState` and nothing downstream had to change. It
runs only when the site-API call fails, announces the switch once, and returns to the single call the moment that
host recovers. Team abbreviations are read out of the `$ref` URL and cached, since teams do not change.

`situation` is deliberately left empty: the core API carries down, distance and possession on a separate drives
feed, and an absent situation already reads as "no live spot known" to every consumer, whereas a half-built one
would be taken as fact.

**Cost.** About four calls a game against the site API's one (event, status, two scores), so ~57 a cycle for a
14-game Sunday against 1. Acceptable for an outage fallback, which is why it is a fallback and not the default.

**Validated** with a single `--once` cycle before it was allowed to run: 14 events parsed, 0 skipped, matching
reality exactly - seven finals, CLE@TB delayed, the late games in the second quarter, IND@KC still `pre`. Six
live games then tracked with pace and margin percentiles and live win probabilities against the pregame sims.
Tests: live 59, live_sim 37, both unchanged.

**Known gap, not fixed.** The `summary` endpoint is also on the blocked host, so **scoring-play alerts are
unavailable**: each live game logs a warning and the tracker continues without them. Scores, clock, pace, margin
and win probability all work; "who just scored" does not. The core API exposes a plays feed that returns 200, so
this is fixable; deliberately deferred rather than start a second integration mid-slate.

---

## 2026-09-20 — Sunday windows: the 15:05 refresh was MISSED. 19:20 ran. ESPN's site API blocked all afternoon

Operational record for the day, so the week-2 grading is read against what actually happened rather than the
schedule.

**The 12:00 CDT window ran on time** (15:45Z trigger, refresh 15:46-15:49Z): 16/16 inactive lists, odds at
15:47:33Z, 14 games simulated, props pulled and ranked. Those eight games' pregame numbers are sound.

**The 15:05 CDT window was missed.** Its refresh was due at 18:50Z and nobody ran it; the day's single pass had
already been spent on the 12:00 window (`run_sunday.py` without `--watch` refreshes one window and exits). The
five games - JAX@DEN, LV@LAC, SEA@ARI, WAS@DAL, MIA@SF - therefore went to kickoff on the **16:20Z** pregame
state: odds from 15:47Z and, worse, **no inactive lists**, because at 15:47Z every one of them was outside the
new P33 two-hour gate. Their questionable players were priced at the flat 0.55 rather than resolved.

**Deliberately not corrected.** Re-running them at 21:00Z would have overwritten a pregame prediction with
mid-game inputs, which is the exact failure `slate_games` and `upcoming_only` exist to prevent. They are left as
they stand and should be graded as a **degraded window**: pregame numbers built without gameday inactives. Any
prop or flag from those five games is weaker evidence than the 12:00 window's and should not be pooled with it
without noting this.

**The 19:20 window (IND@KC) ran at 21:05Z**, about two hours early, and the protections all held:

- odds: `6 game(s) already under way: kept their pregame line`
- predict: `13 game(s) already kicked off; keeping their stored pregame predictions`
- simulate: `skipping 13 game(s) already kicked off`, 1 game re-simulated
- props: 397 of 447 rows `from games already kicked off, not ranked`

So exactly one game was touched. **IND@KC still has no inactive list** - at 21:05Z it was 3.25 h from kickoff,
correctly outside the P33 gate, and the run said so: *"no inactive list has posted for this window yet... Re-run
closer to kickoff."* **It needs one more refresh after 22:20Z** to pick the list up.

A side effect worth recording: that run re-pulled inactives for the six games then in progress and **replaced the
premature lists P33 had deleted** with the real ones (92 players, 12 teams, all at negative lead times). Those
games' predictions were not re-run, so this corrects the stored record only.

**ESPN's `site.api.espn.com` has been Akamai-403 blocked since about 15:47Z** ("Access Denied", not a network
error; `sports.core.api.espn.com` kept serving throughout). Consequences today:
- the ESPN injuries source was skipped at both refreshes - other sources covered it, 31/32 teams;
- **`grade` could not reach the scoreboard**, so today's finals are ungraded until the block lifts or grading is
  pointed at another source;
- `live_tracker` was dead for ~3.5 h until a core-API fallback was built (see the entry above).

---

## 2026-09-20 — Anytime-TD tab wired in, on the live engine, with its caveats rewritten to what is actually broken

The TD list has been unreachable since 2026-09-18, waiting on the usage fixes. Those have all shipped, so it is
live at `#/nfl/props/td`. Display and data only; the engine and the stored simulations are untouched.

**It did not need the old engine.** `td_props` is a pure consumer of stored simulation box scores plus its own
lines file - no separate prediction path - so it reads whatever the last run produced. That is today's 16:19Z
sims, carrying k32+fb (P25), P24, PENALTY_REPLAY, P27 and P10. No re-simulation was needed and there was no
"built against an older engine" problem to solve. The blocker was the lines, not the engine: the file still held
the 4-game 09-17 sample, three of which kicked off at 17:00Z today.

**Lines re-pulled** for the six games still to play - 6 live calls, quota 254 -> 248. The file now holds 9 games
(6 fresh, 3 carried forward from the same week).

**A missing filter, found on the way.** `td_props.rank` had no started-game hold-back, though `props.rank` has
had one all along. On the first run **12 of the top 25 sat on games kicking off within the minute**. It now
shares `props._kicked_off` and returns a `started` bucket: 127 players priced across the 6 live games, 60 rows
held back, 1 held out on gap. `games_covered` counts only games still being ranked, with `games_started`
reported separately, so the header and the sample line can no longer contradict the board beneath them.

**The caveats were rewritten to the ones that are real today**, in all three places that carry them - the module
docstring, the `NOTE` served in the JSON, and the banner in `TdPropsPage.jsx`, which held its own hardcoded copy
and would otherwise have kept showing the old text whatever the backend said:

| was said | now |
|---|---|
| "the replay-the-down fix is switched off this week" | **removed.** PENALTY_REPLAY has been on since 09-19; the 09-16 drive-length gap is closed |
| Waller and the fullbacks missing from the box score | **removed.** Fixed by P25 / k32+fb. Verified in today's sim, not taken from the log: Darren Waller appears as CAR TE3 with anytime_td 0.0434 |
| pocket QBs scrambling at the league rate | **removed.** Fixed by P24 (pocket-QB rush-attempt error 1.22 -> 0.26) |
| - | **added: P18.** First-and-goal converts .323 against a real .486. Diagnosed 09-16, deferred, still open, and the defect that matters most for a market settled at the goal line |
| - | **added: the TD-level bias.** The engine now runs **~8.3% hot** on touchdowns (5.14 offensive TDs a game against the 4.75 the market totals imply, over this week's slate). No bias correction is fitted for this market, so it is raw in every number |

Re-flagging the two fixed bugs was considered and rejected: a caveat that names a defect which no longer exists
is as misleading as one that hides a live defect. Both are recorded in code comments as deliberately dropped, so
they are not quietly re-added later.

Note the bias is the **opposite sign** to the 09-16 measurement the list was built under (sim TD share .196 vs
real .220 then). PENALTY_REPLAY is the obvious cause - more possessions and plays - but that is an inference, not
a measurement, and nothing has been fitted against it. On the live board the two sides sit close in aggregate:
sim 19.1% against a devigged market 18.2%, sim lower on 43% of 127 players.

**Honest summary of the tab's status.** On the engine side it is the best the project can currently do: it runs
on the freshest state, and the two defects it shipped with are genuinely gone. It is still labelled
`exploratory`, because P18 is open and the ~8.3% TD-level bias is uncorrected. It is not "fixed", it is
"differently caveated", and the page says so.

**Explanations deliberately not built.** `td_props` has no Claude explanation path; adding one needs its own
`_describe`, a TD-specific prompt and page wiring. Held as a separate scoped task; the tab is live without it.

### Stale hand-written labels cleared the same day

Both 2026 week-2 entries in `props.KNOWN_DEFECTS` described situations the gameday reports had already resolved,
and a stale caveat is worse than none:

- **CAR@ATL (team-wide).** Said the simulation "splits the passing 60/40 Tua/Cooper Rush". Tua, Michael Penix Jr.
  and Jack Strand are all on ATL's posted inactive list, so Cooper Rush takes **100%** of it - 31 attempts, 225
  yards median. Resolved by P10 that morning, not by any model change.
- **SEA Drew Lock**, and its `PROP_HOLDOUTS` companion. Both asserted Lock simulates at a median of 0 behind
  Darnold. Darnold is ruled out; Lock is SEA's only passer at **236 passing yards**, with 2 carries for 13
  rushing yards, so there was nothing left to hold out.

Both dicts are now empty, with comments recording why.

**No starter-value override was applied, and none should be.** The request was to hand ATL a manual adjustment
for Rush being the confirmed starter. That is P28 part 2, tested and rejected earlier today: it fails criteria 3,
5 and 6, and the flat rule it would replace correlates **+0.250** with the cover residual against the proposal's
**-0.021**. `corr(QB term, market spread) = -0.324` - the market already prices quarterback changes, and ATL's
is public. Separately, `QB_EXPECTED_STARTER` would have made this game **worse**: nflverse names **Tua** as ATL's
expected week-2 starter, and he is inactive. The flag being off is what protected CAR@ATL today.

Tests: 438 pass across 13 files. Dashboard build clean (55 modules).

---

## 2026-09-20 — P33 found and FIXED on the live Sunday: rosters read hours early were stored as posted inactive lists

Found while auditing the 12:00 CDT refresh for the P10/P31 comparison. The refresh reported "27 team lists
posted", but only 16 of them are real.

**What the feed actually returns.** `ingest_inactives.fetch` asks every game within `LOOKAHEAD_HOURS = 12.0`
of kickoff and calls a team "posted" on HTTP 200 plus **any** entry flagged `didNotPlay`. At 15:47Z that
produced 16 lists for the 17:00Z games (T-72m, genuine) and 11 more for games 4.3-8.6 h away.

The late ones are not inactive lists. Checked against each team's own injury report:

| group | teams | ruled-out players | missing from the "posted" list |
|---|---|---|---|
| genuine, T-72m | 16 | 33 | 13 (**39%**) |
| premature, T-4.3h to T-8.6h | 11 | 28 | 26 (**93%**) |

SEA's 9-man list omits **Sam Darnold**, who is ruled out. DEN's list contains one player and misses all nine
of its ruled-out players. LAC 3/3 missing, MIA 3/3, DAL 2/2, WAS 2/2. The 39% residual on the genuine lists is
expected — an IR player is not on the gameday inactive list because he is not on the active roster.

Re-polled read-only at 16:02Z, 15 minutes later: **every one of the 27 lists was identical**, so these are not
lists still filling in. They are some other roster state the endpoint serves early.

**Why the obvious gate does not work.** Premature lists run 1, 6, 6, 6, 7, 7, 7, 7, 7, 8, 9; genuine ones run
7, 7, 7, 8, 8, 8, 9, 10, 10, 10, 11, 11, 11, 12, 12, 12. A minimum-size rule at 7 would still accept LAC's 7,
MIA's 7 and SEA's 9 — all bogus — while rejecting three 6s that may be real on a healthier week. **Lead time
separates them perfectly: 16/16 genuine inside T-120m, 11/11 bogus outside it.**

**Why it matters more than a wrong list.** `features.apply_inactives` treats any team with a posted list as
*resolved*: a questionable player **not** on the list is promoted from the flat 0.55 to play probability 1.0.
So a bogus list does not merely add false inactives, it silently clears the whole team's injury doubt.
Confirmed on today's data: **RJ Harvey (DEN, questionable RB) flipped questionable → active** on the strength
of the one-player list.

**Proposed fix (not built).** `LOOKAHEAD_HOURS = 12.0` → **2.0**, plus its comment. One constant. The 12 h
value was provisional — the docstring says "generous until `first_seen_at` has measured it on a real Sunday",
and this is that Sunday. Nothing else changes: the "no one flagged" path already writes nothing, and
`--replay` bypasses the window check via `include_final`, so the replay validation is unaffected.

It strands no window, because `run_sunday.py` already refreshes once per kickoff cluster at T-75m:

| window | refresh fires | each game's lead at that moment |
|---|---|---|
| 12:00 CDT | 15:45Z | 17:00Z games at 1.25 h |
| 15:05 CDT | 18:50Z | 20:05Z at 1.25 h, 20:25Z at 1.58 h |
| 19:20 CDT | 23:05Z | 00:20Z at 1.25 h |

All inside 2 h. Applying a later game's list during an earlier window was never needed — that game's own
refresh collects it.

**Known residue if adopted.** The 11 bogus lists are already stored. `apply_inactives` takes the latest pull
per (game, team), so each is replaced the moment its own window re-polls: the 15:05 games self-heal at 18:50Z.
**IND@KC does not** — at 18:50Z it is 5.5 h out, outside the new gate, so its bogus 6-man list stands until the
23:05Z refresh. Either accept that (the SNF refresh corrects it before kickoff) or delete the 11 premature
rows as part of the change.

**Adoption test.** No stored list for a game more than 2 h from kickoff; the stored lists cover >= 40% of
ruled-out players **in aggregate**; the 16 genuine T-72m lists of 9/20 come back unchanged.

A *per-list* coverage threshold would be wrong and is deliberately not used: an IR player is not on the active
roster and so never appears on a gameday inactive list, and genuine per-team coverage on 9/20 runs the whole
range 0-100% (CHI's real 8-man list covers neither of its two ruled-out players). Only the aggregate
separates the two populations, 60.6% against 7.1%.

**APPLIED 2026-09-20.** `LOOKAHEAD_HOURS = 12.0 -> 2.0` in `src/ingest_inactives.py`, with the comment rewritten
to carry this evidence. One constant; no other code changed.

**Validated against the live feed** at 16:17Z, read-only, with the gate in place: **16 lists accepted, 153 rows —
exactly the 16 genuine T-72m teams and exactly their original row count** (7+7+7+8+8+8+9+10+10+10+11+11+11+12+12+12
= 153). Seven games skipped as outside the window: JAX@DEN, LV@LAC, SEA@ARI, WAS@DAL, MIA@SF, IND@KC, NYG@LA.
Zero "not posted" responses, so nothing genuine was lost to the change.

**Tests.** New `test_inactives_ignore_rosters_read_early` pins the gate at 8.6 h, 4.3 h and 2.5 h out (rejected)
against 1.58 h and 1.25 h (accepted) — the two leads the Sunday schedule actually produces — and asserts
`--replay` is still ungated. The roster it feeds is a full-looking 7-man list, so the test fails if anyone
re-derives the gate from list size. `test_inactives_fetch_not_posted_writes_nothing` needed its clock moved from
22:00Z to 23:00Z: its 2.25 h lead was inside the old window and is correctly outside the new one. Full suite
**438 pass, 0 fail** across 13 files.

**Stored rows cleaned up.** The 11 premature lists (71 rows) were deleted from `inactives`, backed up first. The
table now holds 153 rows across the 16 genuine teams, and **RJ Harvey (DEN) is back to questionable / 0.55** from
the false active / 1.0. Predictions, simulations, props and both exports were re-run afterwards on the corrected
data — no re-ingest, so no odds or props quota was spent.

**What this does not close.** P10's criterion 6 (how long before kickoff a list really posts) is *less*
measurable now, not more: `first_seen_at` was already bounded by when we poll, and today showed the endpoint
serves a plausible-looking roster hours early, so it cannot witness a true posting time at all. Measuring that
needs a different signal than this endpoint's `didNotPlay` flag.

**Affected right now, pending the fix** — distrust inactives and any questionable-player pricing for:
DEN, JAX, LAC, LV, ARI, DAL, MIA, SEA, SF, WAS (all 15:05 CDT) and IND (19:20 CDT). The eight 12:00 CDT
games are clean. The P10/P31 comparison below is unaffected: its 8-game clean slice agrees with the full sample.

---

## 2026-09-20 — P10 vs P31 measured on the live Sunday. P31 earns its place; recommend flipping it after today

The comparison the P31 build entry called for, run on the 12:00 CDT window's refresh. **Neither flag was
flipped:** every arm re-simulated the slate in memory with `simulate_nfl.run(store_results=False)`, so the
stored `game_simulations` remain the trim-off production run (15:48:41Z). `USAGE_PARTICIPATION_TRIM` is read
inside `load_inputs`, so each arm ran in its own process with the env var already set.

**Method.** 14 games, 10,000 sims, identical per-game seeds (`zlib.crc32(game_id)`, independent of either
flag), against the prop lines pulled at 15:47Z. Raw P(over) **without** the `BIAS_FIT` offsets, over every
priced prop including the held-out ones, since the bias is a property of the simulation and not of the
shortlist. A third arm monkeypatches `features.apply_inactives` to a no-op, because "does P10 alone close
enough of the gap" cannot be read without a no-P10 control on the same sample.

| arm | receptions (n=144) | rec yds (n=145) | all receiving (n=289) | gap closed |
|---|---|---|---|---|
| no P10, no P31 | 0.392 (−0.106) | 0.418 (−0.084) | 0.405 (**−0.095**) | — |
| P10 only (production today) | 0.396 (−0.102) | 0.417 (−0.084) | 0.407 (**−0.093**) | **2.1%** |
| P10 + P31 | 0.447 (−0.051) | 0.460 (−0.042) | 0.453 (**−0.046**) | **51.0%** |

Market 0.498 / 0.501 / 0.500. Paired per-prop |gap| improvement from the trim: mean **+0.0197** (sd 0.0488,
t **+6.87**, n=289); 201 props closer, 81 further, 7 unchanged. On the 8-game 12:00 window alone — the only
lists past the NFL's 90-minute deadline, see the P33 entry above — the answer is the same: −0.094 → −0.050, 46.8% closed.

**The two are near-orthogonal, and the code says why.** `apply_inactives` sets an inactive player's play
probability to 0, and `team_shares` then *carries his share down the depth chart*: the per-team vector sum is
conserved, so the flattening P31 attacks survives P10 untouched. P31 *deletes* share before `team_shares`
normalises. P10 fixes **who** is credited; P31 fixes **the denominator**. Measured on today's chart: only
**19.1%** of the trim's 8.27 raw target-share mass sits on players P10 marks inactive, and 111 of the 132
trimmed players are not inactive at all.

**Side effects, same seeds, same slate.**

| check | trim off | trim on | verdict |
|---|---|---|---|
| 4. team totals (28 team-sides: pass att/yds, rush att/yds) | — | — | **pass, exactly 0.000% drift on all four**; the trim changes who is credited, not the play stream |
| 5. RB rush yds raw gap | −0.045 | **−0.001** | improves |
| 5. QB rush yds raw gap | +0.084 | +0.094 | already outside the 0.02 criterion before the trim; QBs are not in `TRIM_POSITIONS`, they gain only from the smaller denominator. Separate defect |
| pass yds raw gap | +0.012 | +0.012 | unchanged |

**What it costs.** Two priced players are trimmed while active: Germie Bernard (PIT WR4, participation 0.040),
whose two props left the board entirely because a trimmed player gets no projection, and LaJohntay Wester
(BAL WR5, 0.074), who moves from 0.535 to 0.157 against a market 0.381. Both sit just under the 0.10 cliff.
2 of 291 priced receiving props.

**Recommendation: turn `USAGE_PARTICIPATION_TRIM` on, after today's games finish.** The objection that held it
off — that P10 might make it redundant — is now measured and false: P10 closes 2% of the receiving gap where
P31 closes 51%, and they work on different halves of the defect. Flipping mid-Sunday would leave the eight
in-progress early games' stored sims inconsistent with the rest of the slate, so the flip belongs after the
slate completes, with `game_simulations` and the props regenerated and `BIAS_FIT` refitted afterwards.

**Two caveats that stand, and are not closed by this result:**
1. **Per-team sum overshoot.** Criterion 1 wants the raw per-team target-share sum within 0.02 of 1.00. The
   trim takes it from 1.132 to **1.032** — a large improvement, still 0.012 outside. The pool is smaller than
   the chart but not yet the right size.
2. **Q1 overcorrection.** Criterion 2 wants Q4 *and* Q1 in 0.95-1.05. Q4 goes 0.889 → **0.978** and passes;
   Q1 goes 1.086 → **1.118** and does not, with Q2 and Q3 overshooting to 1.09 and 1.11. Trimming lifts
   everyone who remains, so the low and middle quartiles are now priced above their real share, and share MAE
   is 5.6% worse (0.0251 → 0.0265). The trim is a net win on the quartile that carries the priced props, not
   a clean fix of the share vector.

A residual **−0.046** remains on receiving after P31, so roughly half the original bias is still something
else (P17 / P25 territory) and is not P31's to fix.

**Nothing built or changed by this run.** Scratch harness only; `git status` clean.

---

## 2026-09-20 — P29 fixed: tied lines no longer vanish. Corrections refitted; the refit is NOT applied yet

Item 3. The line-selection bug is fixed and committed. The refitted offsets are measured and recorded here but
**not yet written into `BIAS_FIT`**, because they change which props pass Stage 1 on a slate that is already
under way.

**The bug.** `market_view` took `point = median(tied modal lines)`. With an even number tied, the median lands
between two real lines — 182.5 twice and 183.5 twice gives 183.0 — no book matches it, `fair` comes back empty and
the prop returns None. It was never ranked, never held out, and not counted as unmatched either: it simply
disappeared.

**Scope, measured on the stored lines file (424 priced player-markets):** 37 lost, **8.7%**. By market: rush yds 14,
receiving yds 13, pass yds 7, receptions 3.

**The fix.** The tie is broken toward the tied line nearest the consensus of every book, which is always a line
somebody posts. A median that already lands on a real line is left alone. Measured on the same file: **37
recovered, 0 still lost, and 0 props whose line changed** — deliberately targeted so nothing that already worked
moves. 1 new test, 7 checks.

**The refit, on the complete 423-prop sample.** Same method as before: one log-odds offset per category, fitted so
mean simulated P(over) matches the market's, in sample.

| market | pos | n | sim | market | raw pp | old | refitted |
|---|---|---|---|---|---|---|---|
| pass yds | all | 32 | 0.4835 | 0.5003 | -1.69 | -0.0212 | **+0.0732** |
| receiving yds | RB | 36 | 0.4372 | 0.5006 | -6.34 | +0.2124 | +0.2668 |
| receiving yds | TE | 38 | 0.3770 | 0.5015 | -12.46 | +0.5369 | +0.5417 |
| receiving yds | WR | 81 | 0.4020 | 0.5007 | -9.88 | +0.4469 | +0.4342 |
| receptions | all | 154 | 0.3754 | 0.4962 | -12.07 | +0.5242 | +0.5522 |
| rush yds | QB | 27 | 0.5503 | 0.4936 | +5.67 | -0.1818 | **-0.2564** |
| rush yds | RB | 55 | 0.4575 | 0.5001 | -4.26 | +0.2181 | +0.1929 |

**Two of them move materially, and they are the two the bug was skewed toward.**
- **Passing yards changes sign**, -0.0212 to +0.0732, on n 23 -> 32. The 2026-09-18 entry called this offset
  "provisional under P29, the tied-line bug drops about a third of starting QBs from its sample". That was right,
  and the missing third was carrying the sign.
- **QB rushing grows 41%**, -0.1818 to -0.2564, on n 21 -> 27.

The receiving offsets barely move (TE +0.005, WR -0.013), which is consistent: the bug took mostly quarterbacks.

**Applied 2026-09-20 at the user's call, before the first window.** The reason for hesitating was that
`passes_stage1` is built from the corrected probability, so these offsets decide which props carry a value flag,
and the slate was already under way. Measured before applying: over 389 props the flag count is **15 before and 15
after**, with a single swap — MarShawn Lloyd's rushing yards out, his receptions in. The blast radius is one prop,
so the mid-slate risk the caution was about does not really arise here.

Re-fitting on the same sample after applying reproduces the same numbers exactly, which is the consistency check
that the fit converged rather than chasing its own output.

Note for whoever applies it: these offsets are fitted on the sims stored 2026-09-19, with `USAGE_PARTICIPATION_TRIM`
and `QB_EXPECTED_STARTER` both off. Either flag changes simulated output and both would require another refit.

---

## 2026-09-20 — P28 part 1 built behind `QB_EXPECTED_STARTER`. Validated, NOT live

Part 2 stays rejected (entry below). This is the starter-identity half only: it changes who is credited with the
passing, and touches no injury charge, no rating and no margin.

**Built.**
- `sim_data.expected_starters(season)` -> `{(week, team): gsis id}` from nflverse schedules' `home_qb_id` /
  `away_qb_id`. That field is the actual starter for a finished game and the expected one for a game still to
  play, so reading it before kickoff adds no lookahead. Carried on `SimInputs.starters`, loaded once per run.
- `simulate_nfl._promote_starter` moves that quarterback to rank 1 within his team, with the rest of the room
  keeping its relative order behind him. `passer_weights` walks quarterbacks in depth order, so this is all it
  takes; every other position is untouched.
- `props._starter_mismatch`: **any** quarterback the books price whose simulation has him at a median of 0 is held
  out of the ranking with a note. That is the general form of the hand-written `PROP_HOLDOUTS` entry added for
  Drew Lock on 2026-09-19, so it no longer needs one row per quarterback per week.

**Validation, today's slate (32 teams).** 3 changed, 29 already agreed, 0 had no expected starter:

| team | depth chart | expected starter |
|---|---|---|
| SEA | Sam Darnold | **Drew Lock** — the market's priced passer, the original P28 case |
| MIN | Kyler Murray | **Carson Wentz** — not previously identified |
| ATL | Michael Penix Jr. | Tua Tagovailoa |

3 of 32 is 9.4%, against the 9.6% measured historically (52 of 544 team-games in 2025), so today is an ordinary
week for this defect rather than an unusual one.

**MIN is new.** It was not in P28's write-up, which had SEA and ATL. Kyler Murray leads MIN's depth chart and
Carson Wentz is expected to start, so MIN's passing props and box score carry the same defect SEA's did and nobody
had noticed. Found by the fix, not by the original investigation.

**ATL is improved but not resolved.** The chart says Penix (who is OUT), nflverse says Tua, the books price Cooper
Rush. The fix moves the sim from Penix to Tua, which is better, and still disagrees with the market. Today's
inactive list settles it. The `KNOWN_GAME_ISSUES` caveat on CAR@ATL stays.

**Not shipped.** `QB_EXPECTED_STARTER` is off, so today's slate is untouched, and the props holdout is gated on the
same flag. 1 new test (6 checks); 127 pass.

---

## 2026-09-20 — P28 replacement-value design TESTED AND REJECTED. Part 1 still stands. Nothing built

Validated against the seven criteria in the entry below. **The design fails and is not being built.** This entry
also corrects the headline of that entry.

### Correction first

That entry said the flat charge is "about 3.7 points too harsh". **That number was wrong**, and the error was the
baseline it measured against. It compared a starter to *the team's own quarterback mix over its other games*. The
model does not charge against that; it charges against **what is already inside the team rating**, which blends the
current season by volume with the prior season regressed 0.75. Rebuilt against the rating-implied baseline, with
everything taken from before kickoff:

- `k` (actual = k x predicted) is **0.780** fitted on 2022-23, 0.727 on the judging seasons — not 0.28.
- The flat rule's bias on the severe cases is **+1.46**, not +3.66.

So the EPA arithmetic is roughly right after all, and the flat rule is much less wrong than reported. The earlier
claim should not be relied on.

### The design, and how it did

`qb_charge = k x (E[EPA/db of who plays] - rating-implied EPA/db) x dropback rate x 63`, k = 0.780 fitted on
2022-23 and never refitted, judged on 2024-25 (1024 team-games, 512 games). The current rule was reconstructed from
the **real** nflverse injury reports for those seasons, so the comparison is like for like.

| criterion | result | verdict |
|---|---|---|
| 1. form, k fitted on 22-23 and judged on 24-25 | k = 0.780 | done |
| 2. bias within +/- 1.5 on drops worse than 2 pts | proposed **+0.06**, flat +1.46 | **pass** |
| 3. band monotonicity, held out | the -2..-1 band comes out +0.94 actual, out of order (se 1.45) | **fail** |
| 4. games with no QB on the report unchanged | holds for the restricted form by construction | pass |
| 5. baseline margin MAE not worse | see below | **fail in scope** |
| 6. correlation with the cover residual not worse | see below | **fail** |
| 7. sim QB1 from the expected starter | not built | n/a |

**Stop rule did not fire** (k is nowhere near one standard error of 0), but the criteria settle it anyway.

**The unrestricted term looks good and is out of scope.** Applied to every game it improves baseline margin MAE
11.557 -> 10.903 over 2024-25. But it fires everywhere, not just on injuries: it is a general "this quarterback
versus the one in the rating" adjustment, mean |term| 4.17 points against the flat rule's 1.02. That is a different
and much larger change than P28 asked for, and it **violates criterion 4**.

**Restricted to P28's scope — a quarterback actually on the injury report — it loses to the rule it replaces:**

| | corr with cover residual (132 firing games) | margin MAE (firing games) |
|---|---|---|
| no QB term | — | 11.771 |
| **current flat rule** | **+0.250** | **11.299** |
| restricted proposal | -0.021 | 11.490 |

Both criteria fail, and not narrowly. Clipping the charge does not rescue it: the correlation stays at -0.07 to
-0.08 at every cap from 2 to 99 points.

**Why.** `corr(QB term, market spread) = -0.324`: the market already prices quarterback changes. A term that
re-derives what the market knows adds nothing to the residual, and the more confident it is the more it double
counts. The flat rule's crudeness is doing less harm than a sharper number aimed at the same target.

**This also revises P9.** P9 recorded corr(injury term, cover residual) = -0.00 over a small sample. Over
2024-25 with real reports the flat quarterback charge is **+0.124 across 512 games and +0.250 on the 132 it fires
on**. The injury term is not inert; on quarterbacks it is the most useful piece of it. Reducing or replacing it
would have thrown that away.

### What is still worth doing

**P28 part 1 stands on its own evidence.** The depth chart names the wrong starting quarterback in 9.6% of
team-games (52 of 544 in 2025, reconstructed from the dated snapshots that preceded each game). nflverse schedules
carry the expected starter and get SEA right today (Drew Lock, the market's priced passer) where the depth chart
says Darnold. That is a starter-identity fix for the simulator and the props page. It does not touch the injury
charge, so none of the above applies to it.

Part 2 is closed as tested and rejected. The flat charge stays.

---

## 2026-09-20 — P28 diagnosed (SUPERSEDED: see the entry above; the 3.7-point headline was measured against the wrong baseline)

Item 2. Read-only. **This changes the priority order and is flagged to the user.** It is a game-level error on every
team with a quarterback injury, not a props problem, and it is larger than anything found in item 1.

**Part 1: the depth chart names the wrong starting quarterback in 9.6% of team-games.** Reconstructed from the dated
nflverse depth-chart snapshots that preceded each 2025 game (544 team-games): 52 misses, and they are exactly the
injury cases — Purdy/Mac Jones, Lamar Jackson/Cooper Rush, Kyler Murray/Brissett, McCarthy/Wentz.

nflverse schedules carry `home_qb_id` / `away_qb_id`, the expected starter for an upcoming game. For today's slate
it names **Drew Lock for SEA**, which is the market's priced passer and the one the sim gets wrong. It names **Tua
for ATL**, where the books price Cooper Rush, so it fixes SEA and not ATL; the two sources genuinely disagree there
and today's inactive list settles it. Switching the sim's QB1 to this field is a real improvement on the depth
chart, not a complete answer.

**Part 2, the larger finding: the flat charge over-penalises by about 3.7 points.**

The current rule charges position weight 1.0 x snap share x (1 - play probability) x 6.0, so a starter ruled out
costs about **5.58 points whoever replaces him**. Measured against what actually happened, over 2022-2025, 2174
team-games. For each, the starter's EPA per dropback (leave-one-out, shrunk by 200 dropbacks) minus the team's own
dropback-weighted quarterback mix over its other games, converted at 0.603 dropbacks per play x 63 plays:

| predicted drop | n | predicted pts | actual pts | se |
|---|---|---|---|---|
| < -4 | 149 | -5.57 | **-2.88** | 1.07 |
| -4 to -2 | 206 | -2.80 | -1.23 | 0.84 |
| -2 to -1 | 175 | -1.50 | +0.37 | 0.85 |
| -1 to +1 | 847 | +0.19 | +0.41 | 0.37 |
| > +1 | 797 | +2.10 | +0.34 | 0.42 |

Directionally right and monotone where it matters, but **the EPA arithmetic overstates by roughly 3.5x**. Fitting
actual = k x predicted through the origin:

| sample | n | k |
|---|---|---|
| fit on 2022-23 | 1086 | 0.183 +/- 0.145 |
| held out 2024-25 | 1088 | 0.379 +/- 0.160 |
| all four seasons | 2174 | **0.281 +/- 0.108** |

k is about 0.28, different from zero (t = 2.6) and a long way from 1.

On the 355 team-games where the predicted drop is worse than 2 points — the cases the flat rule exists for:

| charge | bias | MAE |
|---|---|---|
| current flat -5.58 | **+3.66** | 10.40 |
| EPA difference, unshrunk | +2.04 | 9.99 |
| EPA difference x 0.18 | **-1.20** | 9.78 |

(MAE is ~10 because a single game's EPA residual is very noisy; the bias is the meaningful column.)

So the model has been charging about 5.6 points for a quarterback who is out when the true average cost is about
2.9 at worst and near zero when the replacement is competent. The naive EPA fix the 2026-09-19 ATL note proposed
(-7.3 for Cooper Rush) would have been **worse than the flat rule**, not better. That is the correction this entry
exists to make.

**This connects to P9**, which found the injury term had no relationship with the cover residual and that
`|injury adj| >= 1` went 0-5 ATS. An over-penalty of this size on the biggest single component is a candidate
explanation.

**Pass criteria for the P28 fix, written down before anything is built:**
1. Quarterback charge = `k x (E[EPA/db of who plays] - rating-implied EPA/db) x dropback rate x 63`, replacing the
   flat position-weight term for QB only. `k` fitted on 2022-23 and **judged on 2024-25**, not refitted.
2. On held-out 2024-25 team-games with a predicted drop worse than 2 points, the charge's bias against realised
   points is within +/- 1.5, against +3.66 for the flat rule.
3. Band monotonicity: predicted and actual stay ordered across the five bands on held-out data.
4. Games with no quarterback on the injury report are unchanged, exactly.
5. Baseline margin MAE over 2024-25 games with a quarterback change does not get worse.
6. P9's check re-run: correlation between the injury term and the cover residual does not get worse.
7. The sim's QB1 comes from the nflverse expected starter where it exists, and a priced QB2 with a sim median of 0
   is flagged rather than ranked (the original P28 criterion).

**Stop rule.** If `k` on held-out data is within one standard error of 0, drop the EPA term and simply reduce the
flat charge to the measured average instead.

---

## 2026-09-20 — P31 built behind `USAGE_PARTICIPATION_TRIM`, tau = 0.10. Validated, NOT live

Built to the design in the entry below, at the threshold the user chose. **The flag is off.** It stays off until
today's Sunday windows have run with real P10 inactives, so the two can be compared: P10 and P31 attack the same
defect (a player who will not play holding target share) from different sides, and P10 may already close part of it.

**What it does.** `sim_data.snap_participation(season)` reads nflverse offensive snap counts for the prior and
current season and returns each player's snaps per team game, keyed `(team, player_key)`. The denominator runs from
his **first appearance for that team**, so a rookie who has played every snap of two games is at 1.0 rather than
2/19 — the walk-forward ran on weeks 11-18 and never exposed that, but it would have trimmed week-one starters.
`player_roles` attaches it as a `participation` column, and `simulate_nfl._participation_trim` zeroes the raw share
of any skill player below `USAGE_MIN_PARTICIPATION` before `team_shares` normalises.

Two guards, both tested:
- a player **inside his position's playing slots is never trimmed**, whatever the feed says, so a missing snap row
  cannot remove a starter;
- a player missing from a **covered** team reads as 0 (he has taken no snap, which is the case the trim exists
  for), while a team absent from the feed altogether reads as unknown and is left alone, so a broken pull cannot
  empty a pool.

**Effect on the production roles vector** (today's slate, 495 skill players): 148 trimmed, **8.9%** of target-share
mass removed.

| | per-team raw sum | Q1 | Q2 | Q3 | Q4 | share MAE |
|---|---|---|---|---|---|---|
| flag off | 1.132 | 1.086 | 1.011 | 1.011 | **0.889** | 0.0251 |
| flag on | 1.032 | 1.118 | 1.093 | 1.109 | **0.978** | 0.0265 |

**Against the six criteria, measured on the production code:**

| criterion | result | verdict |
|---|---|---|
| 1. per-team sum within 0.02 of 1.00 | 1.132 -> 1.032 | **fail**, 0.012 outside; was 0.132 outside |
| 2. Q4 *and* Q1 in 0.95-1.05 | Q4 0.889 -> **0.978** passes; Q1 1.086 -> 1.118 does not | **half**, as forecast at the design stage |
| 3. share MAE not worse | 0.0251 -> 0.0265 | **fail**, 5.6% worse |
| 4. team totals within 1% | worst drift across 4 re-simmed games **0.000000%** | **pass**, exactly: the trim changes who is credited, not the play stream, so the random draw and every game outcome are identical |
| 5. rushing not regressed | rush yds +1.63%, rush att +1.77% over 4 games | **pass**; rushing sat 1.7pp under the market, so a small lift helps |
| 6. receiving moves toward the market | receptions sim/line **0.845 -> 0.944**, receiving yds **0.910 -> 1.017**, 39 and 38 priced props in those games | **pass** |

So it does what it was built to do on the quartile and the props that live there, and it does not pay for it in team
totals or rushing. It does not fix the low quartile, and share MAE is marginally worse because trimming lifts
everyone who remains — Q2 and Q3 overshoot to 1.09 and 1.11.

**Not shipped.** 4 new tests (11 checks); 126 pass. Flipping the flag changes simulated output, so stored
`game_simulations` and any props ranked against them go stale and must be regenerated.

**Next, after today's windows:** re-measure the receiving raw P(over) gap with P10 inactives applied and the flag
still off, then with the flag on, and compare. Decide from that whether P31 earns its place on top of P10.

---

## 2026-09-20 — P31 design stage: the pool, not the share maths. Validated out of sample; nothing built

Follows the diagnosis entry below, whose six criteria were written down first and are not changed here.

**The diagnosis needed correcting, and the correction is the finding.** The first reading blamed `usage_rates`'
denominators (each player's share taken over the games he appeared in). Three candidate rewrites were tested on a
walk-forward and **all of them overcorrected**: weighting by availability put the top quartile at 1.12, a common
per-team-game denominator at 1.11, harder shrinkage was worse than doing nothing.

The test that settled it: restrict each week's vector to the players who **actually took an offensive snap**, using
real snap counts, and score the *current* share maths. The top quartile comes out at **0.973**. The share maths is
right. What is wrong is who is in the pool.

On the production roles vector for today's slate: **10.1% of every team's target share sits on depth-chart players
who have never taken an offensive snap this season**, 153 of 495 skill players. The vector sums to 1.131,
`team_shares` divides that out proportionally, and the players with the most share to lose pay the most of it.

**A graded weight is the wrong shape.** Multiplying each share by the player's participation rate overshoots badly
(top quartile 1.16 at participation^0.25, rising to 1.55 at participation^1.0), because a starter's participation is
~0.9 and a fringe player's ~0.2, so it redistributes far more than the dead weight. The signal is binary: will he
play.

**True walk-forward.** 2025 weeks 11-18, production pipeline replayed on **the depth chart as it actually stood**
before each week's games (nflverse publishes dated snapshots), usage from prior weeks only, participation from
prior snap counts only. Ratio of predicted to realised target share, by quartile of realised share:

| design | per-team raw sum | Q1 | Q2 | Q3 | Q4 | MAE |
|---|---|---|---|---|---|---|
| current | 1.172 | 1.255 | 0.953 | 0.979 | **0.801** | 0.0430 |
| drop participation < 0.05 | 1.059 | 1.255 | 0.947 | 1.022 | 0.876 | **0.0414** |
| drop participation < 0.10 | **0.996** | 1.162 | 0.885 | 1.053 | 0.919 | 0.0424 |
| drop participation < 0.15 | 0.922 | 1.076 | 0.815 | **0.971** | 0.0441 |
| drop participation < 0.20 | 0.832 | 0.844 | 0.776 | 1.104 | 1.026 | 0.0476 |

(Q3/Q4 columns for the 0.15 row: 1.066 / 0.971.)

**Against the six criteria, honestly: no single threshold passes all of them.**

1. per-team sum within 0.02 of 1.00 — **passes at 0.10** (0.996), fails elsewhere.
2. Q4 *and* Q1 both in 0.95-1.05 — **fails at every threshold**. 0.15 puts Q4 at 0.971 but Q1 at 1.076; 0.20 puts Q4
   at 1.026 but Q1 at 0.844. The low-share quartile cannot be fixed by trimming, because trimming is what pushes its
   remaining players up.
3. MAE not worse than current — **passes at 0.05 and 0.10** (0.0414, 0.0424 vs 0.0430), fails from 0.15 up.
4-6 (team totals, rushing, raw P(over)) — not yet measurable; they need a production run.

**The stop rule does not fire.** It was "stop if the best design leaves Q4 outside 0.90-1.10": 0.10 gives 0.919 and
0.15 gives 0.971, both inside.

**What is on offer.** A binary participation trim recovers roughly 60% of the top-quartile gap out of sample
(0.801 -> 0.919 at tau = 0.10), brings the per-team sum to 1.00, and slightly improves MAE. It does not close Q1 or
Q2. tau = 0.15 buys another 5 points of Q4, which is the quartile the priced props live in, and pays for it in Q2
(0.815) and MAE (0.0441).

**Caveat worth keeping.** The walk-forward models no injuries, no inactives and no questionable players. P10 and P21
act on exactly the same defect from the other side — a player who will not play holding share — so live behaviour
with P10 running should be better than these figures. That also means part of the residual gap is not P31's to fix.

Nothing built. The threshold is the user's call.

---

## 2026-09-20 — Receiving under-bias: root cause found (P30 answered, P31 opened). Read-only, nothing built

Item 1 of the accuracy backlog. No production code touched. All measurements read-only.

**Where the bias stands now**, on the 2026-09-19 lines and the stored week-2 sims (raw = uncorrected sim, before
the fitted offsets):

| market | n | raw P(over) | market | gap |
|---|---|---|---|---|
| receptions | 138 | 0.378 | 0.497 | **-0.119** |
| receiving yds | 129 | 0.402 | 0.501 | **-0.099** |
| rush yds | 62 | 0.482 | 0.499 | -0.017 |
| pass yds | 23 | 0.505 | 0.500 | +0.005 |

Rushing and passing are effectively fixed (P23/P24/P26). The bias is now **receiving only**, and it is the same
size for WR (-0.113), TE (-0.125) and RB (-0.127), so it is not a position effect.

**P30 is answered: it was one-week noise.** The 0.80 / 1.24 tercile split was re-measured with the same harness on
every comparable window, bootstrapped by player-game (90% CI):

| window | n | top tercile predicted/actual |
|---|---|---|
| 2025 wk 1-2 | 391 | 1.073 [0.971, 1.196] |
| 2025 wk 3-4 | 374 | 0.996 [0.901, 1.114] |
| 2025 wk 5-10 | 1051 | 0.906 [0.853, 0.971] |
| 2025 wk 11-18 | 1642 | 0.969 [0.919, 1.020] |
| 2026 wk 1-2 | 211 | 0.906 [0.793, 1.051] |

The 2026 CI spans 1.00. Efficiency compression is real but small and unstable, 3-5% pooled, which agrees with the
P17 walk-forward's 1-3%. **It is not the props under-bias.** P30 closes; P17 stays parked.

**What it actually is: the target-share vector is flattened.** Healthy priced receivers (not on the injury report,
n=124), sim against their own real per-game rates over 2025-26:

- sim targets / real targets **0.851**
- sim receptions / real receptions **0.857**
- sim catch rate 0.673 vs real 0.668 — **correct**, P27 did its job
- market line / real receptions 0.962 — the market prices close to the player's own rate

So it is volume, not conversion. Decomposed against the team totals, team volume is fine
(sim pass att / real 0.972) and the share distribution is not, by quartile of real target share (n=277):

| quartile | real share | sim share | sim/real |
|---|---|---|---|
| Q1 low | 0.046 | 0.049 | **1.065** |
| Q2 | 0.088 | 0.070 | 0.800 |
| Q3 | 0.144 | 0.115 | 0.803 |
| Q4 high | 0.231 | 0.174 | **0.755** |

**Localised to the first stage of the pipeline.** Ratio to real share after each step (n=216, players with a real
share of 2%+):

| quartile | 1 own history | 2 after blend_roles | 3 normalised | 4 bucket-weighted |
|---|---|---|---|---|
| Q1 low | 1.927 | 1.231 | 1.087 | 1.076 |
| Q2 | 1.478 | 1.143 | 1.012 | 1.012 |
| Q3 | 1.275 | 1.139 | 1.012 | 1.014 |
| Q4 high | 1.063 | 1.005 | **0.890** | 0.893 |

`usage_rates` takes each player's share over **the games he appeared in** (a deliberate choice, so a receiver who
missed half a season is not read as a part-timer). A rotational WR5 is therefore carried at his when-active rate,
which is nearly 2x his per-team-game rate. Every player on the depth chart is then put in one vector, and it sums
to **1.131**, not 1. `team_shares` divides by that sum, so the excess the part-timers contributed is taken out of
everyone **proportionally**, and the players with the most share to lose pay the most of it. The top quartile
lands at 0.890, the bottom at 1.087.

0.890 (share) x 0.972 (team volume) = 0.865, against the 0.851 measured end to end. The chain closes.

Stage 4 adds nothing (0.893 vs 0.890), so the separate partition defect below is not part of this.

**Logged as P31** (the flattening) and **P32** (the partition mismatch, minor, found on the way).

**A second, severe effect on a small population.** Splitting the receiving props by injury status:

| group | n | raw P(over) | market | gap |
|---|---|---|---|---|
| not on the report | 240 | 0.399 | 0.496 | -0.096 |
| on the report, no status | 23 | 0.333 | 0.526 | -0.193 |
| **status = questionable** | 4 | **0.122** | 0.520 | **-0.399** |

This is P21 (ESPN rows carry no practice detail, so every Questionable player is priced at a flat 0.55) measured on
props for the first time. Puka Nacua: his share of LA's targets should be ~0.265, the sim gives him 0.153, and
0.265 x 0.55 = 0.146. It halves a star's projection while the market prices him as playing. It explains only 4 of
the 352 priced props this week, so it is not the main bias, but on those 4 it is the largest single distortion in
the system. P10 resolves it on gameday once a list posts; P21 remains the fix for the rest of the week.

**A naive fix does not work.** Weighting each player's share by his historical availability (games played / team
games) before normalising overcorrects: the per-team sum falls to 0.633 and the top quartile goes from 0.890 to
1.411. Recorded so it is not retried.

**Pass criteria for a P31 fix, written down before the design is built:**
1. Per-team sum of raw role target shares within 0.02 of 1.00, against 1.131 now.
2. Quartile ratio to real share: **Q4 in 0.95-1.05 and Q1 in 0.95-1.05**, judged out of sample on a walk-forward
   over 2025 weeks 11-18 (shares from data before each week), against 0.890 / 1.087 now.
3. Per-player target MAE against real share not worse than the current 0.0251.
4. Team totals unchanged: simulated team targets and pass attempts within 1% of the current engine.
5. Rushing must not regress: RB and QB rush-yds raw P(over) stay within 0.02 of market, which they now meet.
6. Receiving raw P(over) moves from 0.378 / 0.402 toward the market's ~0.50 **without** the fitted offsets, and
   the offsets are refitted afterwards.

**Stop rule.** If the best design leaves Q4 outside 0.90-1.10 out of sample, report rather than chain further fixes.

---

## 2026-09-20 — P10 committed; the Sunday windows are one command

P10 committed and pushed (`164fdd9`), unchanged from the replay-validated build. Criterion 6 (posting time) is still
open and can only close on a live Sunday; `first_seen_at` records it without anyone watching for it.

**`run_sunday.py`.** The build note left three manual refreshes a Sunday, one per kickoff window, each to be run
after that window's lists post and before its games start. That is now `python run_sunday.py --watch`.

- Windows are **clustered from the day's actual kickoff times**, not hardcoded to 13:00 / 16:05 / 20:20 ET. Kickoffs
  more than 75 min apart start a new window, so today's slate reads as 8 / 5 / 1, the 20:05 and 20:25 games stay one
  refresh, and a London 9:30 or a flexed start needs no special case.
- The refresh fires at **kickoff − 75 min**, off the *earliest* kickoff in the window. The posting deadline is 90 min,
  so this leaves the list time to appear and the refresh time to finish. Earlier than that is a wasted run, not a
  harmful one: a list that has not posted 404s and writes nothing.
- Per window: grade → injuries (inactives ride along) → weather → odds → re-predict → re-simulate → props → exports.
  A step that fails warns and the rest continue, except `predict`, which the sim and props need. nflverse is not
  re-ingested; its play data only changes after games finish and it is the slowest step.
- **`simulate_nfl.run(upcoming_only=True)`** (also `--upcoming-only`) is the one upstream change. `--date` simulated
  every game on the slate, so the 13:50 refresh would have re-run the eight early games in progress and overwritten
  each pregame row with a post-kickoff one. The anchor pinning meant the number would not have moved much, but the
  row would no longer be the one published before kickoff, and it cost eight games of compute per window.
- It reports **how many of the window's 2N team lists have posted**, and warns plainly when none have — that being
  the case where the refresh runs but every Questionable player keeps the flat 0.55.
- 10 new checks in `tests/test_sunday.py` covering the clustering, the trigger time and the posted-list count; 122
  pass.

Still manual: `db/PASTE_INTO_SUPABASE.sql` has not been run upstream, so inactives rows go to the local SQLite
mirror and are read back from there.

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
