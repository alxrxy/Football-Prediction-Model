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
| P2 | Stop pricing unknown-snap QBs at 35% of a starter | logic | 2026-09-13 | 8/13 NFL games carry a ~2.1 pt charge for a backup/rookie QB. Graded 9/13: 5 games affected; removing the charges flips 2 leans (ATL@PIT, NO@DET), both to wins, 3-10 → 5-8 | rebuild NFL training with the change; holdout MAE vs line must not get worse | proposed; see the 2026-09-22 cross-reference "QB mismatch: one mechanism, three observations" (P2 / P9 / P37). |
| P3 | Replace the flat FCS proxy (-28); grade proxy games separately | logic + reporting | 2026-09-12 | proxy games: model MAE 17.1 vs market 10.8, ATS 13-20 | proxy-game MAE within 2 pts of the market over 100+ games | proposed |
| P4 | Make confidence tiers discriminate: SP+/Elo agreement, early-season demotion | logic | 2026-09-12 | 47/47 rated CFB games "high"; 9/13 NFL: 13/13 "high" in both models and 13/13 sims. Season: "high" = every rated game (26-34 ATS), "low" = only FCS proxies, "medium" never assigned. The agreement signal did *not* carry to NFL: baseline/ML agree 1-6, disagree 2-3 | "high" beats "medium" ATS over 200+ graded games | **RETIRED 2026-09-30 (user).** The tier (`predict_baseline._confidence`; the ML's is 3+ books) records whether every input was present, not how likely a pick is: all 124 NFL predictions are 'high' (46/46 graded per model), 'medium' is never assigned, and 'low' only ever came from college FCS proxies (gone with P58). Its bar could never be met. **Dashboard fixed the same day:** the ATS-by-confidence table (ResultsPanel, shown on the NFL Record page) and the college slate's Conf column are removed, and the game Q&A context no longer tells Claude 'confidence high'. The stored `confidence` field is unchanged. Agreement data at retirement (information): baseline and ML agreed on 23/46 NFL games; agree baseline 6-16-1 / ML 6-16-1, disagree 13-10 / 9-14. A real-signal redesign is P59 |
| P5 | Upper edge cap for early-season edges (large edge = stale rating) | threshold | 2026-09-12 | CFB rated \|edge\| 6-10 went 2-7. NFL wk 1 \|edge\| ≥ 6 went 0-4, MAE 15.6 vs market 8.1; NFL ratings are ~94% prior season this week | \|edge\|>8 (CFB) / >6 (NFL) in weeks 1-4 loses ATS over 60+ games **Criteria set with the user 2026-09-30, one question at a time (supersede the line above; NFL only):** (Q1) **claim = size-reliability:** in weeks 1-4, is a large edge less reliable ATS than a moderate one? A cap moves no lean to the other side; it only shrinks large early edges (and can drop flags). The margin-error comparison (large early edges vs the line, in points) is reported alongside, not a gate. (Q2) **bar = P37's slope test:** cap only if the weeks 1-4 lean slope (ATS result on edge size) is negative with permutation p < 0.05. (Sample, user: the P22 phase-1 walk-forward replay already run, P22 rating (A+B), weeks 1-4 of 2016-25, 635 games; rating edges, before injuries and the market blend.) **Set after the replay's numbers were visible:** lean slope +0.044 (perm p 0.858); 6+ went 30-19 (61%) vs 3-6 at 93-83 (53%, derived from the table's >=3 and >=6 rows); every candidate bar read 'no cap'. (Q3) **College split off** as P56; P5 is NFL-only. (Q4) **If 'no cap': close P5 (NFL)** on the replay; after week 4 is graded, run the same slope test on the 62 live served 2026 weeks 1-4 edges and log it as information only; reopen only if a full season of served edges shows a negative slope at p < 0.05 | **CLOSED 2026-09-30 (NFL): no cap.** P37 lean slope on the P22 replay, weeks 1-4 2016-25 (635 games): **+0.044, permutation p 0.859**; 6+ edges 30-19 (61%) vs 3-6 93-83-5 (53%). Reported, not a gate: on 6+ edges the rating's margin MAE is 11.22 vs the line's 10.03 (+1.19; 3-6 +0.57; under 3 +0.00), so large early edges are further off in points even though they won ATS. `research/p5/p5_replay.py`, results in `research/p5/p5_results.md`. **Follow-up queued (information only):** after week 4 is graded (after MNF 10/5), the same slope test on the 62 live served 2026 weeks 1-4 edges. Reopen only if a full season of served edges shows a negative slope at p < 0.05. College: see P56 **Live follow-up 2026-10-07 (information): served wks 1-4 baseline edges (old rating, n 62) lean slope -0.661, perm p 0.200; >= 6 went 7-10-2. Not significant; stays closed. See the 2026-10-07 P5 entry.** |
| P6 | CFB home field 2.4 → ~2.8 | weight | 2026-09-12 | slate: model leaned away 30/47, -2.1 pts vs market; history: market-implied HFA 3.2 (2017-25) but 0.5 in 2025 | mean signed edge on non-neutral games < -1.0 across 4+ weeks | watch |
| P7 | Do not use the CFB ML model's margins until its compression is explained | investigate | 2026-09-12 | mean \|ML margin\| 9.5 vs actual 24.7; MAE 20.6. *Correction 09-15: the "Georgia −27 vs market −69.5" example below used an in-play line (P15); DK closed −40.5* | n/a, diagnose first | investigate |
| P8 | NFL: consider the ML margin (or a blend) as the headline number | model selection | 2026-09-14 | 9/13: ML SU 10/13 vs baseline 6/13, MAE 11.46 vs 13.10, Brier 0.214 vs 0.256; ATS both poor (4-8, 3-10) | ML MAE below baseline MAE over 4+ NFL weeks (~60 games), and not worse vs market **Decision set with the user 2026-09-30, before the data (supersedes the line above):** (a) **ATS is the primary bar**; margin error and CLV are reported as context, consistent with P37, P9 and P5. (b) **Timing:** not judged against the retiring baseline. The comparison runs only after the P22 baseline (ships after MNF 10/5) has a few weeks of its own graded games; ML is compared with that baseline on those weeks only. **Set 2026-09-30, before any P22 data exists:** (c) **sample:** the first **3 weeks** of graded games under the P22 baseline, both models, same games. (d) **test:** a permutation test of ML's ATS record against the baseline's, P37's method (10,000 permutations, two-sided, |null| >= |observed|) adapted to two models as a paired label swap: each game contributes (ML ATS result - baseline ATS result), W = 1, L = 0; each permutation randomly swaps the two models' results within each game; a game where either model pushed is dropped. **ML wins only if its ATS wins exceed the baseline's and p < 0.05**; otherwise the baseline stays the headline. Games where both models lean the same side contribute 0, so the test turns on the games where they disagree (about half so far: 23 of 46). Status at the decision (weeks 1-3, 46 games, old baseline; context only): ML ATS 15-30-1 (33%) vs baseline 19-26-1 (42%); MAE 11.21 vs 12.51 (paired -1.30, 95% CI -2.65 to +0.04); CLV -0.07 pp (t -0.61, n 45) vs -0.21 pp (t -1.55, n 46) | watch; **criteria set 2026-09-30 and confirmed by the user (paired adaptation, two-sided, pushes dropped); runs after 3 graded P22 weeks** |
| P9 | NFL injury term: check its magnitude | weight | 2026-09-14 | 9/13: \|injury adj\| ≥ 1 went 0-5 ATS, MAE 12.3 vs market 8.8; corr(injury term, cover residual) −0.00. 9/14 DEN@KC: term −0.95 toward DEN (−2.63 with real snap shares, P14), market already −2.5 with the same report; lost | fitted coefficient on the injury term (actual − market ~ injury) positive and significant over 100+ games. **Exclude 2026-09-17 DET@BUF**: its term (1.56) was set before P20, which understates DET's side (Pacheco on IR uncounted), and before P10/P21 — four players priced at the flat 0.55 with the official inactives already public. The fixed code would not produce that number, so the game cannot speak to this coefficient | **closed 2026-09-22: tested, no change (user confirmed).** Injury coefficient stays 1.0. Re-open only if injury-heavy games keep losing from 2026 week 3 onward, under criteria agreed with the user and written here before any test runs; same route as the 2026-09-22 cross-reference "QB mismatch: one mechanism, three observations" (P2 / P9 / P37). History: **Re-check due after P41 (2026-09-22)**: that fix makes charges larger where it fires (PHI 2.07, PIT 1.80 pts on the week-2 report), so the coefficient must be refitted on the corrected numbers. **Re-checked 2026-09-22** (entries "P9 scoped" / "P9 findings"): Q1 magnitude beta 0.546 (CI 0.36-0.73, excludes 1.0) but the walk-forward gain is -0.040 < 0.05 bar, 4/7 seasons, 2025 and Brier worse -> **no change**; the logged edge test **passes narrowly** (gamma +0.161, one-sided p 0.034) and rests on 2024 (post-hoc, without it p 0.25); P41 moves beta by -0.0008. **Part 2 (2026-09-22), edge test:** scaling to walk-forward beta or beta_mkt fails all four edge criteria (|edge| >= 3: 47.6% / 47.4% vs 50.5% at 1.0), and neither coefficient is stable (beta: heterogeneous and rising; beta_mkt: heterogeneous). **1.0 stays.** |
| P10 | Props: apply game-day inactives before simulating | data | 2026-09-14 | DAL@NYG: 4 projected players recorded nothing (N. Harris 5.3 car, Beckham, Cambre, Abanikanda), none on the injury list; Singletary took 10 touches + TD unprojected. **Widened 2026-09-17 (DET@BUF):** this is not a sequencing problem. There is no inactives ingestion path anywhere in the pipeline, and the ESPN feed structurally cannot supply one — a full league pull at 22:50Z returned only `Active` (614), `Questionable` (134), `Injured Reserve` (40), `Out` (9), `Doubtful` (3), with no gameday inactive designation. `ingest_injuries._status` would discard one anyway (see P20, P21). Consequence at T-75 min, with the official list already public: DET@BUF still priced 4 players at the flat questionable/limited 0.55 (D.J. Reed 0.75 pts, Cole Bishop, T.J. Sanders, Ty Johnson) when each was by then resolved to 0 or 1 **Source found and confirmed 2026-09-19:** the ESPN core API per-competition roster flags inactives `didNotPlay` (DET@BUF: 8 BUF / 9 DET, incl. T.J. Sanders and Ty Johnson); 404 before posting. Week-1 payoff: 6 inactive projected players, 1.4% of projected touches (Kamara, N. Harris). See the 2026-09-19 P10 entry | acquire a real inactives source first (ESPN gameday roster endpoint or equivalent), then re-sim after it lands; track "projected, no stats" rate weekly | **LIVE since the 2026-09-20 Sunday windows** (`164fdd9`; status corrected 2026-09-29). It has run every window since, via `run_sunday` (9/20, 9/27, MNF 9/28); the `inactives` table exists upstream in Supabase (549 rows), so the paste-the-SQL note below is historical. Criteria 1-5 pass. **Criterion 6 (true posting time) is still open:** the 9/20 P33 finding showed this endpoint cannot witness a real posting time (it serves a plausible roster hours early), so it needs a different signal. Built and validated on replay 2026-09-19. The Sunday windows run as one command, `python run_sunday.py --watch` (2026-09-20 entry). New `inactives` table: paste `db/PASTE_INTO_SUPABASE.sql` to create it upstream (the local mirror is used until then). See the 2026-09-19 P10 build entry |
| P11 | Props: rushing volume bands too narrow (game script) | investigate | 2026-09-14 | DAL@NYG: rush att in the 50% band 2/8, rush yds 1/8; team rush att −8 (trailing DAL), +9 (leading NYG). DEN@KC: leading KC 38 rush att vs median 25 (p90 31), trailing DEN 15 | 50% band hit rate for rush att in 40-60% over 10+ simulated games | **engine change applied 2026-09-15** (game-script play-calling): calibration rush att by final margin 21.4 → 32.5 vs real 20.7 → 31.6, was flat 24.1 → 27.9; league totals within 3%. The band test itself still needs 10+ graded games |
| P12 | Run pregame sims before the first kickoff | process | 2026-09-14 | 12/13 week-1 sims written 23:11Z, after kickoff, so only DAL@NYG props are gradeable | n/a | **closed 2026-09-29: satisfied by the refresh process** (user confirmed). Checked against the stored `game_simulations`: weeks 2, 3 and 4 have every game's pregame sim written before kickoff (16/16 each; only week 1, before the process existed, had 12 written after kickoff). Two parts of the process do it: (1) the Tuesday first pass simulates the whole week well ahead (week 4: minimum lead 52 h), so every game has a pregame sim from early in the week; (2) window refreshes (`run_sunday`, and the manual `simulate_nfl`) pass `--upcoming-only`, so a later refresh never overwrites a game that has kicked off, and P15 stops any prediction made after kickoff from being graded. Tightest case: ATL @ GB (TNF) was re-simulated at 00:06Z by the Thursday catch-up refresh, 9 minutes before kickoff, replacing an earlier pregame sim, so it was never unsimulated. Residual, not a reason to keep this open: Thursday windows are refreshed by hand (`run_sunday` is started per date), so a missed Thursday refresh leaves the Tuesday sim in place rather than none |
| P13 | NFL prior-season rating must be QB-conditional (weight the prior by the expected starter's games, or add a QB-change term) | logic | 2026-09-15 | DEN@KC: KC's 2025 rating includes 146 backup-QB plays at −0.347 EPA; Mahomes-only prior moves KC +2.9 pts, edge −3.46 → −0.56, flag off. Scope: 11/32 teams shift ≥ 1 pt from non-primary starts (NYJ +5.1, IND +3.8, KC +2.9) | rebuild NFL training with QB-conditioned prior; holdout MAE vs line must not get worse, and weeks 1-4 MAE should improve | **tested 2026-09-15, not adopted.** Starter-games prior (≥ 4 starts): baseline wks 1-4 2016-25 MAE 10.46 → 10.56 (moved games 10.08 → 10.53); ML 2025 holdout MAE 10.08 → 10.10, wks 1-4 8.98 → 9.13. Fails both parts. Code kept behind `QB_CONDITIONAL_PRIOR=0` |
| P14 | Snap-share fallback is per dataset, not per player | bug fix | 2026-09-15 | `_snap_shares` stops at 2026 once it has > 500 rows, so teams that hadn't played and players who sat out week 1 get no share: 78/154 latest NFL injury rows; every DEN/KC row. DEN@KC injury term −0.95 → −2.63 with real shares | none needed; correctness bug | **applied 2026-09-15** (`ingest_injuries.merge_snap_shares`); NFL rows without a share 78/154 → 32/161 on the week-2 pull |
| P15 | Never grade a prediction made after kickoff; never store in-play lines | bug fix | 2026-09-15 | 19 of 80 CFB predictions on 09-12 were generated at 18:37Z, after 16:00–17:00 kickoffs, against in-play Odds API lines (Georgia −69.5 vs DK close −40.5). The old rule flagged 8 of them, 6-2. Pregame-only flagged record is 15-25, not 21-27 | none needed | **applied**: predict-side guard since 2026-09-14 (`ba6d7f3`); `ingest_odds` skips in-play events and CLV marks late leans `after_kickoff`, 2026-09-15 |
| P17 | Props: model each player's own efficiency and target share before trusting the prop ranking (research Stage 4) | logic | 2026-09-15 | Week 2, first pull (1-5 books, Tuesday): 46 props priced, top 10 gaps 17-25 pp, 15 more held out past 25 pp. One-sided pattern: star receivers under (J. Williams rec yds sim 37 vs 56.5, St. Brown rec 5 vs 7.5, Nabers rec 3 vs 5.5); QB pass yds off both ways (Goff 222 vs 265.5, Stafford 285 vs 242.5). The engine gives every player league-typical yards per play and splits targets by depth-chart share **Confirmed as a cause 2026-09-18 (week-1 actuals, n=174 receivers with 8+ games in 2025):** yards per target are drawn from league plays by situation, so efficiency is compressed toward average. Top tercile by own 2025 yds/target (9.12): sim 7.63 vs week-1 actual 8.56, yards 0.80x actual; bottom tercile (5.33): sim 6.60 vs 6.47, 1.24x. Zero-sum against calibrated team pass yards, so the priced starters lose what the low-efficiency receivers gain **Walk-forward 2026-09-19 (2025 weeks 3-18, criteria written down first):** outcome-aware crediting with shrunk per-player rates improves out-of-sample rec yds MSE −1.28% (7/8 weeks, CI touches 0) and receptions −2.91%, but narrowly fails the tercile criterion. More importantly, the current engine is already within ~3% per tercile given targets (0.97 / 1.01), so the 0.80 / 1.24 compression above does not reproduce: efficiency given targets is a 1-3% effect, not the source of the props under-bias. See the 2026-09-19 P17 entry | prop gaps centre near 0 across a week (mean \|gap\| < 8 pp), then prop CLV ≥ 0 over 65+ leans | **not building as scoped** (user, 2026-09-19): design walk-forward done, small and marginal gain, and the premise did not reproduce. The open question it raised is P30 **Next step (user, 2026-09-29): P30 is folded in here as new evidence, not rescoped as a separate item.** The 9/19 closure rests on the 2025 walk-forward (2024-25 data): given targets, the engine is within ~3% per tercile (0.97 / 1.01). The 9/29 P30 diagnosis measures the same quantity on 2026 wk 1-3 at 0.918 [0.863, 0.978] top / 1.106 [1.024, 1.198] bottom, against a 2025 wk 11-18 control of 0.968 [0.930, 1.006] (2025 wk 5-10 was also low, at 0.941). Check the closure against 2026 data before deciding whether it still holds; criteria to be set with the user and written here before that check runs. **Recheck criteria set with the user 2026-09-30 (before running):** (1) the claim tested is the *decision* claim, i.e. whether per-player efficiency modelling is worth building. The 9/19 design is re-run **frozen** (k = 100, position prior, prior season at weight 0.5, outcome-aware crediting with IPF, split by pre-week category shares): no re-tuning, each week sees only earlier data. (2) **Reopen** if the rec-yds MSE gain vs the current engine is >= 1% and it is better in >= 3 of 4 weeks; otherwise **still closed**. The bootstrap CI is reported alongside; receptions MSE and the tercile calibration are reported, not gated. A reopen reopens the design discussion; it does not build. (3) Sample: **2026 weeks 1-4** (~1,000 receiver-games), run after MNF 10/5 once week 4 is graded. Honest limit: at this size the CI is about +/-2-3 pp, so a real 1-3% effect cannot be shown significant either way; the bar is the 9/19 closure's own bar, applied to new data **Harness preserved 2026-09-30:** the frozen 9/19 design lives in `research/p17/` (`p17_walkforward.py`, already containing the disclosed harness correction; `p17_fix.py` is the patch that applied it; `p17_score.py` scores). Copied unchanged from a session scratchpad, where it was the only copy **Recheck run 2026-10-07 (2026 wks 1-4, 1,034 receiver-games, frozen): rec yds +0.65% WORSE (95% CI -1.87% to +3.27%), better in 1/4 weeks; receptions -1.94%. Rule fails: STILL CLOSED. See the 2026-10-07 P17 entry.** |
| P18 | Simulator: first-and-short (goal-to-go) conversion far below real | bug | 2026-09-16 | Engine diagnostic, `--calibrate` over 20k league-average sims: 1st & 0-2.5 converts .323 vs real .486 (y/p 0.34 vs 0.43); 1st & 2.5-5.5 .216 vs .329 (y/p 1.41 vs 2.64); 1st & 5.5-9.5 .119 vs .163. On 1st down a to-go under 10 means the ball is inside the 10, so these are almost all goal-to-go snaps. Consistent with sim TD share .196 vs real .220. At ~1% of all snaps it does **not** explain the 11% plays-per-drive shortfall, which was measured separately and traced to possession count | 1st-down conversion within 3 pp of real in each sub-10 distance bin, and sim TD share within 1 pp of real | **re-diagnosed 2026-09-25: the logged under-conversion was a measurement artifact; the real defect runs the other way.** The engine *over*-converts sub-10 1st downs by 3-5 pp, from drawing a play at a different spot than it was run from. The TD-share half of the test already passes (.223 vs .220). **Fix built and validated 2026-09-25 on branch `p18-per-yard-goal-line` (pushed, not merged); held to ship at the week-4 boundary (on or after 09-29).** **SHIPPED 2026-09-29** (merged to main; library v6; week 4 simulated on it; re-validation in the 2026-09-29 P18 entry). Criteria 2-5 pass; criterion 1 misses on one pooled bin, entirely from 4th downs (P45). See the 2026-09-25 P18 build entry |
| P16 | Baseline model weight to 0 if its NFL leans show no CLV | weight | 2026-09-15 | backfill: 75 pregame baseline leans −0.22 pp (t −1.22), but 61 are CFB and priced at an assumed −110 against DK's close; NFL n=14 | NFL lean CLV ≤ 0 at 65+ NFL leans (≈ week 5) → set `MODEL_MARKET_WEIGHT=0` for the baseline | watch |
| P19 | A partial injury pull must not retire other teams' reports: `latest_injury_report` keeps the latest pull *per source*, not per team/week as P1 intended | bug fix | 2026-09-16 | The 19:46Z week-2 nflverse pull held only BUF/DET (8 rows, the Thursday game). Because it was the newest nflverse pull, the week-1 nflverse report (91 rows) was silently dropped for the other 30 teams, which fell back to ESPN only. This time it helped by accident: the week-1 statuses were stale, e.g. Penix OUT, and CAR@ATL moved 0.60 → 4.77 when that row fell away. The same mechanism can just as easily drop a current report for most of the league in a future week, with no warning | none needed; correctness bug. Test: a pull covering 2 teams leaves every other team's latest report in force | **applied 2026-09-16** (`features.latest_injury_report`). Kept apart from the engine-change sequence because it is a data-pipeline correctness fix. For nflverse the report is now the latest week only, and within that week each team's latest pull; ESPN is unchanged (latest whole pull). Last week's statuses are deliberately not carried forward, so the 9/16 outcome (30 teams on ESPN until they file week 2) was the right one. Validated before landing: identical 137 selected rows on the live table, and injury_adj unchanged on all 16 week-2 games. The old code fails the new partial-pull test. Residual: a team whose whole report clears mid-week writes no rows, so its earlier same-week rows stay in force |
| P20 | ESPN "Injured Reserve" status is discarded, so IR'd starters vanish instead of counting as out | bug fix | 2026-09-16 | `ingest_injuries._status` keeps only out/doubtful/questionable/probable. HOU LB To'oTo'o (0.88 snaps) went to IR 09-16 and dropped out of the injury layer, instead of costing HOU ~1.06 pts. **Scope measured 2026-09-17:** the 22:50Z league-wide pull carried **40** players at `Injured Reserve`, every one of them silently dropped — this is league-wide, not a one-team case. Tonight's DET@BUF: Isiah Pacheco (DET, IR) contributed nothing to the injury layer, so DET's burden is understated and the true term favours BUF by more than the 1.56 served | none needed; correctness bug | **FIXED 2026-09-22** (see that day's P20 entry). ESPN "Injured Reserve" now maps to status `ir` at play probability 0; an IR row with no snap share for that team is not emitted; the ESPN/nflverse merge dedups on `player_key`. Validated on the cached 09-18 pull: 27 of 39 IR rows ingested, 12 teams' charges move, HOU To'oTo'o exactly the 1.06 logged. **Dormant until ESPN answers again** (site.api has 403'd since 09-20) |
| P21 | ESPN rows carry no practice participation, so every Questionable player plays at a flat 0.55 | logic | 2026-09-16 | Penix: full practice, charged 2.52 (0.80 → 1.12). Terrell: DNP, charged 0.70 (0.25 → 1.17). Burrow: "says he will play", charged 2.70. ESPN's `shortComment` states the practice level in plain text | practice-aware play probability does not worsen NFL injury-term fit (P9) | proposed (after P19) |
| P22 | NFL power rating: no opponent adjustment; defense regressed the same as offense (×0.75); prior season carries ~94% in week 2 | logic | 2026-09-16 | CIN@HOU baseline −16.37 vs market −2.5. Of the +10.93 rating gap, +12.98 is the 2025 defensive EPA gap alone, −0.98 offense, −1.08 week 1. The only value flag on the week-2 slate comes from this. See also P5, P13 | rebuild with separate off/def regression (and opponent adjustment); weeks 1-4 and holdout MAE vs line must improve. **Phase 1 bars, set with the user 2026-09-30 before running (research only):** on test seasons 2022-2025, settings frozen from 2016-2021: (1) pooled margin MAE improves >= 0.10 vs the P37 replay of the live rating, and is better in >= 3 of 4 test seasons; (2) weeks 1-4 MAE not worse; (3) no edge inflation: mean |edge| not above the replay's + 0.05, and ATS at |edge| >= 4 not more than 2 pp below the replay's; (4) implied totals MAE vs actual not worse; (5) attribution: A (opponent adjustment), B (separate off/def carry), C (garbage-time filter) each reported, and a part gaining < 0.03 is dropped; bars 1-4 judge the combination of the parts that clear it; (6) ML untouched; (7) reported, not a bar: P37's Test 2 ATS-information check on the new rating. Stop rule: bar 1 fails -> report and stop, no re-tuning. See the 2026-09-30 P22 phase-1 entry | proposed (after P19). **Phase 1 approved 2026-09-30 (research only, nothing live).** **Phase 1 PASSED 2026-09-30: candidate A+B** (opponent-adjusted ridge, penalty 300, + separate carry off 0.459 / def 0.394; the garbage filter C was dropped at -0.118). Test 2022-25 MAE 10.393 -> 10.010 (+0.383, better 4/4 seasons), weeks 1-4 10.423 -> 10.034, mean |edge| 3.63 -> 2.68, implied totals 11.103 -> 10.619; ML byte-identical. All ten seasons: +0.211 pooled, better in 8/10. Bar 7: still no significant ATS information. Nothing built; phase 2 (port to live) needs its own go. See the 2026-09-30 phase-1 results entry **Phase 2 approved 2026-09-30 (user): port A+B with the phase-1 settings frozen, no re-tuning on live results; built on a branch; ships at the boundary after MNF 10/5. Criteria 1-6 in the 2026-09-30 phase-2 entry, set before the build.** **BUILT 2026-09-30 on branch `p22-rating` (ebb4665, pushed, NOT merged).** Criteria 1(a), 1(b), 4, 5, 6 pass. Criterion 2's slate-mean clause is unmeetable by construction; criterion 3 flagged on tiny samples. See the 2026-09-30 phase-2 build entry. **User rulings 2026-09-30:** (2) the per-game clause (83%) is the test; the slate-average clause is dropped, because on a full slate it is structurally guaranteed to show zero proxy change whatever the rating's quality, so it was never a valid test. (3) Don't hold the ship. Re-measure the props shift on week 5's full slate; refit a category only if it still moves > 1.0 pp with 20+ props behind it, after week 5 is graded, on week-5 sims made with the new rating. **Merge APPROVED for after MNF 10/5, once week 4 is graded.** Ship steps: merge; rebuild ratings; re-predict and re-sim week 5; refresh props, TD picks and exports; re-check criterion 1, the props shift and the ML check on week 5, and report bar 7 on week 5 (user, 2026-09-30: the phase-1 ATS-information test, same method as P37 and phase 1, on the new rating's week-5 edges; reported, not gated, and stated plainly either way); QB sweep; log the new served numbers **Joint ship with P51 (user, 2026-09-30); full sequence, both branches merge cleanly into main and touch no common file:** (1) after MNF 10/5 is final: grade week 4 (archives it). (2) Snapshot the served state to `data/snapshots/pre-p22-p51_<date>/`. (3) 'Before' pass on current main: week-5 odds (one pull), predict both models, simulate; record margins and sim totals (criteria 1-2 'before'). (4) Merge `p22-rating`; suite; criterion 6 (ML training file and model files byte-identical). (5) Merge `p51-priced-qb`; suite. (6) Rebuild ratings. (7) Re-predict week 5, both models, same odds. (8) In the new window order: props lines pull, then simulate week 5, then props rank; TD lines pull and rank; export sims. (9) Checks before the dashboard export: criterion 1 (served before/after vs phase 1's direction), criterion 2 (sim totals, per-game clause), criterion 3 props shift on the week-5 slate so far (P51-firing games listed separately), criterion 6 again, bar 7 (information), P51 firing list, QB sweep (sim QB1 = priced QB everywhere). If criterion 1, 2 or 6 fails, stop before the export and report; the old dashboard stays up. (10) Export dashboard; log served numbers and results; push. Not part of the merge, same night once week 4 is graded: P5's live follow-up (information), then the P17 recheck, then P60 (NGS arm, after P17); P48's validation replay (ships after MNF 10/12); criterion 3's refit decision waits for week 5 to be graded. **Added 2026-10-01: P68 scoping (non-QB inactive guard) joins the post-10/5 batch, scoping and criteria with the user first, nothing built before then** **SHIPPED 2026-10-07 with P51 (merge 7047cee; the merge conflicted in `game_explain.py` with main's close-game rule, both texts kept). Criteria 1 (4.46 -> 3.49), 2 (83%), 6 (md5 + ML diff 0) pass; 3 measured (no n >= 20 category > 1.0 pp; the 9/30 phase-2 criterion-3 figures were held-out props only, corrected); bar 7 pending until week 5 is graded. See the 2026-10-07 ship entry.** |
| P23 | Usage shares: drop scrambles and kneels from carry shares (issue 2A) | bug fix | 2026-09-16 | `sim_data._usage_events` counts every `rush_attempt`, including 1,224 scrambles and 487 kneels (2025-26), while the engine separately credits every scramble to the QB. Read-only week-2 re-sim, 10k sims, 195 priced props: QB rush att 5.42 → 3.33 per team-game (real 2025 3.25), RB carries 20.54 → 22.61 (+10%), team rush att/yds and game totals/margins unchanged to 3 decimals. RB rush yds P(over) 0.329 → 0.393 vs market 0.500, about 40% of the RB gap. Receiving unchanged. See the 2026-09-16 entry | QB rush att ≈ 3.3 per team-game; RB carries up ≈ 10%; team rush totals, game totals and margins unchanged; rushing props correction re-fit with separate QB and RB offsets (P26) | **applied 2026-09-18** (moved ahead of the 9/22 plan at the user's call). Validated before landing, read-only week-2 re-sim: QB rush att 5.41 → 3.26 per team-game (real 3.25), RB carries 20.47 → 22.53 (+10.1%), team rush att/yds, game totals and margins identical to 4 decimals. See the 2026-09-18 entry |
| P24 | Usage shares: QB-specific scramble rate (issue 2B) | logic | 2026-09-16 | The engine credits scrambles at the league rate (5.9% of dropbacks) whatever the QB (Goff 0.9%, Stafford 1.2%). With P23 applied, QB rush yds split both ways: runners well under (Lamar Jackson P(over) 0.146, Daniels 0.219), pocket QBs still over (D. Jones sim 19.4 vs 8.5 line, Purdy 21.6 vs 13.5) **Design walk-forward and read-only engine prototype 2026-09-19 (criteria written down first): all pass.** Scramble rate is a stable QB trait (r 0.87). A shrunk per-QB rate cuts scramble MSE 25.8% out of sample (8/8 weeks). The per-offense sampler factor leaves dropbacks, points and margins unchanged and moves QB rush att toward real for pocket QBs (err 1.22 → 0.26) and runners (1.51 → 0.64); QB rush-yds |gap| 0.163 → 0.116. See the 2026-09-19 P24 entry | QB rush att and rush-yds P(over) move toward real and market for both running and pocket QBs, with dropbacks, points and margins unchanged (**revised 2026-09-19** from "no change to team totals": running QBs' teams are meant to swap some pass attempts for scrambles). Full criteria in the 2026-09-19 P24 entry | **applied 2026-09-19** (user-approved build): per-offense scramble factor in the sampler, pregame and live. Re-validated with the same checks: production reproduces the prototype exactly, all criteria pass. Pass-yds offset refitted (−0.0212, provisional under P29). QB rushing props still held out, pending the user's decision. See the 2026-09-19 build entry |
| P25 | Usage shares: use backups' own history beyond the playing slots; FB prior is zero (issue 1) | logic | 2026-09-16 | `blend_roles` gives players beyond QB1/RB2/WR3/TE1/FB1 only the slot average: 76 have their own red-zone share at least 2x that average (TE2s Njoku, Freiermuth, Mayer, Kmet all a flat 3.2%). D. Waller (CAR TE3, 14.1% of targets) is simulated at 2.3%, falls under `MIN_TOUCHES` and drops out of the box score. FBs are zeroed even with history (Heyward 14% of goal-line carries) | **revised 2026-09-18:** per-player target and carry shares closer to realised week-by-week shares (walk-forward, squared error). The original second clause, "starters not pushed further under their prop lines", assumed starters' shares were too low; the 2025 backtest shows they are already slightly too high (WR starters +5%, TE +3% against realised). A fix that corrects toward reality is the right direction even if it moves starters further under the market; that residual gap is the receiving investigation's to explain, not this item's | **applied 2026-09-19** as `k32+fb` (moved ahead of the 9/22 plan at the user's call): `sim_data.BACKUP_HISTORY_GAMES = 32`, and an FB with no slot prior keeps his own history. Re-validated before landing with the shipped `blend_roles`: identical shares to the 9/18 reference (max diff 0.0), and the 2025 walk-forward reproduces every locked number (tgt_all −4.5% 15/16 weeks, car_all −2.1% 8/16, tgt_rz −0.6% 15/16, car_gl −0.8% 10/16; weeks 11-18 −5.3 / −3.0 / −0.8 / −1.7). Live check: game totals, margins and team volume identical. Receiving offsets refitted (P26). See the 2026-09-19 entry |
| P26 | Props bias correction: fit offsets by position, not one per category | logic | 2026-09-16 | The single rushing offset (+0.346) hides two biases pulling in opposite directions: QB rush yds lean over (P(over) 0.649, 7/9 overs), RB rush yds lean under (0.329, 2/24). Their mean (0.416) looked like one under-bias. Receiving and passing corrections may hide the same thing, and not moving under P23 is no evidence either way | rebuild with P23: separate QB/RB rushing offsets; before trusting the receiving and passing offsets, check each by position (WR/TE/RB for receptions and rec yds; pocket vs running QBs for pass yds) and split any that disagree | **rushing half applied 2026-09-18:** RB offset +0.107 (n=39, mean-fitted, starters still under); QB rushing gets no offset and is held out of the ranking as an engine defect until P24, because a QB offset averages runners (far under) with pocket passers (far over). Receiving and passing by-position checks still open (receiving investigation, 2026-09-18). **Receiving half applied 2026-09-18 (after P27):** receptions stay one offset (+0.510, n=127; WR/TE/RB intervals overlap); receiving yards split by position (WR +0.418 n=63, TE +0.553 n=28, RB +0.212 n=28; RB's 90% CI +0.08 to +0.34 excludes the category's +0.40). **Passing refitted 2026-09-18 (evening):** −0.093 → **+0.005** (n=20, raw −0.12pp; the 9/16 fit came from the 25-prop first pull). One offset: the pocket-vs-running split was not tested, and with the category mean on the market there is nothing for it to separate yet. **Caveat 2026-09-19:** that pass-yds fit is provisional. P29 dropped about a third of starting QBs from its sample; refit after P29. **Refitted 2026-09-19 after P25:** receptions +0.5104 → +0.5517 (n=138); rec yds WR +0.4560, TE +0.5586, RB +0.2389 (RB interval +0.11 to +0.36 still excludes the category +0.43, so the split stays). **RB rushing refitted the same day at the user's call:** +0.107 → **+0.195** (n=41, raw −4.32pp, 90% CI +0.02 to +0.39), because k32+fb moves carries from RB1/RB2 to RB3+. **QB rushing offset added 2026-09-19 after P24:** −0.182 (n=21), no split needed; QB rushing props ranked again. See the 2026-09-19 QB rushing entry |
| P27 | Engine: throwaways are credited as receiver targets | bug fix | 2026-09-18 | 4.25% of library pass attempts (2023-25) have no intended receiver and are all incomplete, yet `simulate._Game._credit` gives every attempt a target. Catch rate over all attempts is 0.645 and the sim's week-1 starter catch rate is 0.643; real catch rate over true targets is 0.674 (week-1 actual 0.676). Sim team targets 32.2 vs actual 29.6. See the 2026-09-18 receiving entry. **Corrected 2026-09-18 (fix run):** the diagnosis said this accounted for the ~4-5% receptions shortfall. It cannot: a throwaway was credited as an *incomplete* target, so removing it lowers targets and nothing else. Receptions and receiving yards per player are unchanged by construction, and every priced prop's raw P(over) was unchanged (324/324). Team receiving is calibrated (sim 20.33 completions / 30.03 true targets per team-game vs 2025 20.62 / 30.70, week 1 20.47 / 29.74), so the per-player receptions shortfall is in how catches are split between players (P17, P25), not P27 | sim catch rate ≈ 0.674; team targets ≈ 95.8% of pass attempts; QB pass att/cmp/yds, team totals, game totals and margins unchanged; receiving offsets refitted | **applied 2026-09-18** (`TABLES_VERSION` 5: `targeted` library field; `_credit` still draws a receiver for every attempt, so the random stream is untouched, then drops the credit on throwaways). Validated read-only on the 15 weekend games, 10k sims, against a same-code control with the field stripped: catch rate 0.6487 → **0.6771** (library over true targets 0.6773), targets/attempt 1.000 → **0.9581**, QB pass att/cmp/yds per player, team totals, game totals and margins identical (max diff 0.0). Receiving offsets refitted (P26). See the 2026-09-18 P27 entry |
| P28 | Starter designation: when the starter is out or disputed, the sim's next QB follows the depth chart while the market prices a different passer (SEA: Lock; ATL: Cooper Rush) | investigate | 2026-09-18 | Week 2, SEA @ ARI. Books price only Lock for SEA pass yds (207.5), with no Sam Darnold line posted. The stored sim has Darnold QB1 (17.8 att, median 172 yds) and Lock QB2 (12.0 att, **median 0**, mean 93), so the raw sim reads Lock's under at 0.746 against a market 0.500, and he sits **#2 on the ranked list**. His rushing prop (6.5) is held out as QB rushing. Looks like a depth-chart / starter-designation or injury-status mismatch, distinct from the usage and efficiency items. Not diagnosed **Second team, 2026-09-19 (targeted re-pull):** with Penix now OUT, books price **Cooper Rush** as ATL's passer (183.5, 5 books) and post no Tua Tagovailoa line, while the sim starts Tua (QB2, 18.3 att, median 156) with Rush as QB3 (12.0 att, **median 0**). So it is not SEA-specific: the sim's next man up follows the depth chart, and the books' does not. Rush's pass-yds prop is currently dropped by P29, and his rushing prop is held out as QB rushing, so nothing about it shows on the page **ATL game-level check, 2026-09-19 (read-only):** inconsistent, and the CAR@ATL numbers correspond to neither QB. (1) The sim cannot disagree with the baseline at game level: `anchored_simulation` pins the margin to the baseline's; QB identity only routes box-score credit. So the question is the baseline's −5.59 Penix charge (1.0 × 0.932 snap share × 6.0, a generic starter-out value that never asks who replaces him). (2) ATL's rating is ~94% 2025 ATL offense, whose dropbacks were split Cousins 283 (−0.023 EPA/db) / Penix 303 (+0.035): mix +0.007, so the rating is only about half Penix. **Cooper Rush started ATL's week-1 game** (Penix did not play; 57 plays, −0.321 EPA/play). (3) On the same scale (EPA/db difference × 0.603 dropbacks/play × 63), relative to the rating: Tua +0.4 (2025) to +4.3 (2024-25); Rush −7.3 (2024-26, 404 db, −0.185 EPA/db, 43rd of 44). So the correct charge is about 0 if Tua starts, and about −7.3 if Rush starts. The −5.59 charged is neither. The sim's own mix (Tua 0.6 from an nflverse row with no status, Rush 0.4) implies about −0.3 to −2.7. (4) Consequence: if Rush starts (the market's view, and who started week 1), ATL is ~1.7 pts too strong, so ≈ CAR +1.5 vs the market's CAR −2.5, with no flag either way. If Tua starts, ATL is ~6-10 pts too weak and the true number is an ATL edge. The edge's sign depends on the QB, and the served number reflects neither. The ML model uses the same generic `qb_availability_loss`. **Labelled 2026-09-19 at the user's call** (see status) | the sim's QB1 for every team matches the market's priced passer (or the confirmed starter) before props are ranked; a priced QB2 with sim median 0 is flagged, not ranked | **part 2 tested and REJECTED 2026-09-20.** Replacement-value charge, k = 0.780 fitted on 2022-23 and judged on 2024-25 with real injury reports: restricted to P28's scope it loses to the flat rule on both the cover-residual correlation (+0.250 -> -0.021 on the 132 firing games) and margin MAE (11.299 -> 11.490). The market already prices QB changes, corr(term, spread) = -0.324. The flat charge stays. **Part 1 still open:** the depth chart names the wrong starter in 9.6% of team-games; nflverse schedules carry the expected starter and get SEA (Drew Lock) right today | the sim's QB1 matches the expected starter, and a priced QB2 with sim median 0 is flagged, not ranked | part 2 closed; **part 1 proposed** |
| P29 | Props: `market_view` silently drops a prop when two lines tie for most books | bug fix | 2026-09-19 | `point = median(tied modal lines)`: with an even number of tied lines, the median is a line no book posts (Cooper Rush 182.5 ×2 / 183.5 ×2 → 183.0), no book matches it, and the prop returns None: never ranked or held out, and not counted as unmatched either. **37 of 424** priced player-markets on the 2026-09-19 lines (38/398 on the 9/17 file), and they are skewed to starting QBs' pass yds (Herbert, Mayfield, Purdy, D. Jones, Willis, Stafford/Dart on 9/17). The 2026-09-18 pass-yds offset refit (n=20) and the 9/16 fits were therefore taken on a sample missing these props | every priced player-market either produces a row or is counted as a named exclusion; then refit the pass-yds offset on the full set | tie broken toward the posted line nearest the consensus; no prop that already had a line changes | **FIXED 2026-09-20.** 37 of 424 recovered (8.7%), 0 still lost, 0 lines changed; 1 test, 7 checks. Refit on the complete sample measured and logged: pass yds -0.0212 -> **+0.0732** (sign flip), QB rush -0.1818 -> -0.2564; receiving barely moves. refit **applied 2026-09-20** before the first window: 15 Stage 1 flags before and after, one swap |
| P30 | Why did 2026 week 1 show a 0.80 / 1.24 receiving-yards tercile split when the 2025 walk-forward shows 0.97 / 1.01? | investigate | 2026-09-19 | The P17 walk-forward found the current engine, given each receiver's targets and pre-week category mix, within ~3% per tercile across 2025 weeks 11-18. The 2026-09-18 week-1 check (n=138 starters, one week) measured 0.80x yards for the top tercile and 1.24x for the bottom. Candidates: one-week noise and selection; or the SIMULATED target distribution (who gets how many deep vs short targets, which the walk-forward held at each player's own historical mix) rather than efficiency. Distinct from P17 (efficiency given targets) and P25 (target volume) | to be written into this log when the diagnosis is scoped, before it runs (process rule, 2026-09-19). **Diagnosis criteria set 2026-09-29, before running:** arms B0 (raw share, must reproduce 0.881) / B1 (roles, trim off) / B2 (today's trimmed shares) / A (actual targets); B2 top-tercile 90% CI includes 1 -> closed again with the rule re-set on B2 after wk 6; below 1 -> split by A (efficiency, P17 evidence) vs target allocation (to P31); above 1 -> P31 overshoot evidence. See the 2026-09-29 criteria entry | **answered 2026-09-20: one-week noise.** Re-measured on every comparable window with a bootstrap CI; the 2026 wk 1-2 top tercile is 0.906 [0.793, 1.051], CI spanning 1.00, and pooled compression is 3-5%. Not the props bias. See the 2026-09-20 entry | **closed**. Re-check scheduled (user, 2026-09-25): re-run the same bootstrap once week 3 is fully graded (after MNF 2026-09-28), alongside P31. The rule is already set: reopen only if the 2026 top-tercile 90% CI no longer includes 1.00. **Unblocked 2026-09-29** (PHI @ CHI pbp posted) **Re-check run 2026-09-29: the reopen rule is MET.** Same harness (2025 rows reproduce to the digit): 2026 wk 1-3 top tercile **0.881 [0.812, 0.958]** (n=611), wk 1-2 re-run 0.870 [0.787, 0.970] (n=401; the 9/20 n=211 row predated most of week 2), wk 3 alone 0.910 [0.786, 1.069]. **Reopened; nothing built.** The harness uses pre-P31 shares and league yards/target, so the diagnosis is not scoped yet: criteria go into this log first, with the user. See the 2026-09-29 P30/P31 entry **Diagnosed 2026-09-29 (rule 2): the gap survives today's shares, and it is efficiency given targets.** A (actual targets, league yds/target), 2026 wk 1-3: top 0.918 [0.863, 0.978], bottom 1.106 [1.024, 1.198]; 2025 wk 11-18 control 0.968 [0.930, 1.006]. B2 (today's shares) 0.830 vs control 0.826, so no 2026 share gap. B2's absolute level is ~15% low by construction, so the pre-set comparison with 1.00 was the wrong reference. Evidence reported to P17; P17 not reopened without the user; nothing built. See the 2026-09-29 results entry **Folded into P17 (user, 2026-09-29).** No separate item; the follow-up is P17's next step |
| P31 | Receiving: the target-share vector is flattened, so priced receivers get ~0.85 of their real targets | bug fix | 2026-09-20 | Healthy priced receivers (n=124): sim/real targets 0.851, catch rate correct (0.673 vs 0.668), team pass att 0.972. By quartile of real target share (n=277) the sim/real share runs 1.065 / 0.800 / 0.803 / **0.755**. Localised to `usage_rates`, which takes each player's share over the games he appeared in: a rotational WR5 is carried at ~1.93x his per-team-game rate, the per-team vector sums to **1.131**, and `team_shares` divides it out proportionally so the biggest shares pay the most. 0.890 x 0.972 = 0.865 vs 0.851 measured end to end. This is the receiving under-bias (receptions -0.119, rec yds -0.099 raw vs market) | see the six criteria in the 2026-09-20 entry; Q4 and Q1 share ratios in 0.95-1.05 out of sample, team totals within 1%, rushing not regressed. **Partial-trim criteria set 2026-09-29, before running:** trimmed players keep alpha x raw share, alpha fitted on 2025 wk 3-10 only, tested on 2025 wk 11-18 and 2026 wk 2-3; (1) retained mass within 1.5 pts of real, (2) share MAE not worse than full trim, (3) top-2 real/sim closer to 1 than 0.934 with 95% CI incl. 1 (and CI incl. 1 on 2025), (4) pregame-quartile Q4 in 0.95-1.05 both windows and 2025 realised-quartile Q4 >= 0.90, (5) carry MAE not worse and RB1 carry ratio moves <= 0.02, (6) team totals structural; props prospective, a flip condition. Stop if alpha outside (0,1) or 3/4 fail. See the 2026-09-29 criteria entry | **ON since 2026-09-21** (flag default flipped, `BIAS_FIT` refitted). Built 2026-09-20; P10 vs P31 on the live Sunday: P10 closes 2% of the receiving gap, P31 51%. Graded against week-2 outcomes (2026-09-21 entry): props Brier improves but inside noise, RB rushing worse this week, and the trimmed players took 5.1% of real targets, not ~0, so the trim overshoots. Criteria 1 and 2 still fail **Blocked until week 3 is fully graded (after MNF 2026-09-28; earliest 2026-09-29):** the partial-trim follow-up needs week 3's graded props. Don't start early (user, 2026-09-25). P30's closing re-check runs alongside it, and the receiving-bias residual pass follows **Unblocked 2026-09-29:** week 3 final (16/16) and PHI @ CHI pbp posted on nflverse (155 plays, 27-7); started the same day **Re-grade run 2026-09-29 (read-only; see that day's P30/P31 entry):** pooled weeks 2-3, 60 team-games, by pregame-share quartile the trim moves top-2 receivers from 1.023 [0.931, 1.116] to **0.934 [0.846, 1.019]** real/sim (over-credits, the CI just includes 1), Q4 1.049 -> 0.956, Q1 0.877 -> 1.241; share MAE better in both weeks (0.0412 -> 0.0379); trimmed players took **3.8%** of real targets (5.1% wk2, 2.9% wk3) against 9.8 pts/team of share removed. Week-3 props (trim on, n=336 receiving): raw P(over) 0.462 vs actual 0.458 vs market 0.491; Brier 0.2597 vs market 0.2500. Partial-trim design NOT started: criteria to be set with the user first **Partial trim walk-forward 2026-09-29: fails, stop rule fired.** alpha fitted 0.340 (2025 wk 3-10). Passes 1 (mass), 3 (top-2 0.966 on both windows vs full trim 0.941 / 0.935) and 4-pregame (Q4 0.982 / 0.989). Fails 2 (share MAE +0.0008 / +0.0011 vs full trim), 4-realised (0.825 < 0.90; full trim 0.847 also fails) and 5 (carry MAE worse; RB1 ratio +0.032 / +0.026). Not adoptable as specified; the full trim stays live. New: the full trim's top-2 over-credit is significant out of sample on 2025 wk 11-18 (0.941 [0.894, 0.986]). See the 2026-09-29 results entry **Decision (user, 2026-09-29): partial trim REJECTED; the full trim stays live (tau 0.10, `USAGE_PARTICIPATION_TRIM` on).** Its win is on the top-2 receivers per team (104 priced props in week 3, 22 in week 4 as priced; real/sim 0.94 -> 0.97). That is outweighed by a loss on the larger rest-of-top-half group (187 priced props in week 3; moves from 1.03 / 0.99 to 1.05 / 1.03 real/sim, further under-credited) and by the carry-error loss concentrating on each team's most-priced RB (carry rank 1: 30 of 54 priced RB rush props in week 3; MAE +0.0016 / +0.0064), not on the tail. Accepted as-is with the full trim: its RB carry error, its lower-half receiving error, and its top-2 over-credit (0.941 [0.894, 0.986] on 2025 wk 11-18, 0.935 on 2026 wk 2-3). The deeper efficiency question P30 raised now sits with P17. No further P31 tuning is queued. See the 2026-09-29 prop-group entry |
| P32 | Target-category shares are computed on overlapping sets but picked on disjoint ones | bug fix | 2026-09-20 | `_usage_events` builds `tgt_deep` / `tgt_short` over **all** targets including red-zone ones, while `simulate._credit` picks rz, then non-rz deep, then non-rz short — three disjoint buckets. Red-zone targets are counted twice. Measured on 2025 (230 receivers, 25+ targets): engine/true share median 0.990 deep, 1.001 short, per-player p10-p90 0.90-1.22; effect on simulated volume 0.998 targets, 0.996 yards, and terciles 1.005 / 1.000 / 1.000. Real but minor, and **not** part of P31: stage 4 of the P31 decomposition adds nothing (0.893 vs 0.890) | engine share within 2% of the true disjoint share at p10 and p90; no change to team totals | proposed, low priority |
| P33 | Inactives: a roster read hours before kickoff is stored as a posted list | bug fix | 2026-09-20 | `ingest_inactives.fetch` treats HTTP 200 + any `didNotPlay` entry as a posted list, and `LOOKAHEAD_HOURS` asks 12 h out. On the live 9/20 slate that stored 11 late-window team lists (T-4.3h to T-8.6h) that are not inactive lists at all: **93% of their ruled-out players are missing from them** (28 ruled out, 26 absent), against 39% for the 16 genuine T-72m lists. SEA's 9-man list omits Sam Darnold, who is ruled out; DEN's list has 1 player and misses all 9. Re-polled 15 min later, every list was byte-identical, so they are stale content rather than a list still filling. **List size cannot separate them** (bogus lists run 6-9, genuine 7-12); lead time separates them perfectly, 16/16 vs 11/11. Consequence is worse than a bad list: `features.apply_inactives` treats any team with a "posted" list as resolved, so every *unlisted* questionable player is promoted to play probability 1.0 - RJ Harvey (DEN, questionable RB) was flipped questionable -> active off the 1-player list | no stored list for a game more than 2 h from kickoff; on a live Sunday the stored lists cover >= 40% of ruled-out players **in aggregate** (genuine 60.6% vs premature 7.1% on 9/20; a per-list threshold is invalid, since an IR player is never on a gameday inactive list and genuine per-team coverage runs 0-100%); the 16 genuine T-72m lists of 9/20 are unchanged by the fix | **applied 2026-09-20**: `LOOKAHEAD_HOURS` 12.0 -> 2.0 in `src/ingest_inactives.py`. Validated live at 16:17Z (16 lists / 153 rows accepted, unchanged; 7 games skipped). New test pins the gate at 8.6/4.3/2.5 h rejected vs 1.58/1.25 h accepted, against a full-looking 7-man roster so it cannot be re-derived from list size; suite 438 pass. The 11 premature lists (71 rows) deleted and the slate re-predicted, re-simmed and re-exported **Refinement queued 2026-09-27 for the week-4 boundary (with P18/P31/P47/P48):** the 2.0 h gate accepted partial lists twice on 9/27: the noon probe at 1.70 h (11/43 = 25.6% of ruled-out players listed; Daniels WAS and Simmons KC absent, KC 2 names; genuine at 1.18 h: 51/65 = 78.5%) and BAL @ DAL / LV @ NO stored at 1.52 h (3/8; grew +2 to +4 each by 1.22 h, 7/8). The 9/20 validation only covered <= 1.58 h and >= 2.5 h. Candidate fixes: (a) tighten `LOOKAHEAD_HOURS` toward ~1.5 h, or (b) add ruled-out coverage as a storage condition. **Pick whichever tests better in a proper walk-forward** over the stored 2026 reads (lead time, list, injury report at read time), measured on: stale/partial lists stored (target 0), genuine lists refused or delayed past the window's trigger, and effect on graded injury terms; criteria to be confirmed with the user before running. Nothing changed live 9/27 **Probe logger BUILT 2026-09-30 (user: stored data can't answer the question; needs per-read records):** `src/probe_inactives.py`, run every 15 min by Task Scheduler (`\FootballPredictor\P33 inactives probe`, first run Sun 10/4 00:00 CDT, then every game day). For each team in a game from T-3 h to kickoff it saves the full ESPN list at that read (names, positions, ESPN ids, HTTP status, P42 check) and coverage of the team's ruled-out players (out / doubtful / IR on the report as it stands then, IR also counted separately) to `data/inactives_probe/<date>/reads.jsonl`. **Isolation:** store wrapped read-only (writes raise); ESPN read with the uncached `_get`; athlete names in the probe's own cache, never the shared HTTP cache; `LOOKAHEAD_HOURS` untouched; outputs only in its own folder. Live dry run (clock set to T-1.25 h before PHI @ CHI wk3): inactives and injuries tables, the 773 shared cache files and the local mirror were identical before and after. The one shared resource is ESPN (about 2 roster calls per game per read). Thresholds to be set with the user after 2-3 Sundays (~10/19) **Launcher changed 2026-09-30 (user):** the task now runs `conhost.exe --headless cmd.exe /c probe_inactives.cmd` (no console window), and the .cmd writes a start and an exit line per run to `data/inactives_probe/task.log`; same fix as P61 for the 0xC000013A kill (see P61's row, including why a .vbs wrapper was not used). Manual trigger: exit 0, both lines; first scheduled pass Sun 10/4 00:00 (P61's identical launcher passed its 21:00 and 21:15 scheduled runs 9/30) |
| P34 | CLV: the fallback close is the median of American odds, which have no values between -100 and +100 | bug fix | 2026-09-20 | `clv.snapshot_close` takes `median()` over each book's American price at the consensus line. That scale is **discontinuous** - no odds exist strictly between -100 and +100 - so when the books at a line straddle the boundary the median lands in the gap and yields a price that cannot exist. CIN@HOU: away prices at -2.5 were [-108, -105, -102, +100, +100, +104], median **-1.0**, stored as -1. `market.implied(-1)` = 0.0099, so a coin-flip side reads as a 1% chance; `devig([-116, -1])` returns home 0.9819 against a true ~0.517, and with `p_market` 0.5223 that is **clv_pp +0.4596** - the stored value exactly. Correct probability-space median gives home 0.5171, so true CLV is **-0.5pp, not +46pp**. The equal-and-opposite values across models are not a side-orientation bug: the two models leaned opposite sides, so `own()` flips one corrupt number twice | a straddling price set must yield a valid price and a CLV near 0 when the line did not move; no stored close price strictly between -100 and +100; the 187 `espn:draftkings` closes must be byte-identical after any fix | **FIXED 2026-09-22** (see that day's P34 entry: all three pass criteria met; the 4 corrupt rows rewritten). Diagnosed 2026-09-20. Blast radius is 4 of 215 closed rows, all NFL, all today, all via `oddsapi_last_pregame`, 1 of them a flagged lean; the 187 `espn:draftkings` closes are immune by construction, so the CLV history before today is clean. The fix is to take the median in **probability space** (`market.implied` per book, median there, convert back), which is continuous and has no gap. **The two latent sites are in scope of the same item**, since they share the mechanism: `ingest_odds` consensus moneylines (`int(_median(ml_h))`) and `market.side_price`. Neither is firing now - 0 of 389 consensus rows hold a moneyline in the impossible range - so they are a guarded check plus the same probability-space treatment, not a second investigation |
| P35 | Live sim: no structured in-game player status, so an injured player keeps his projection | open gap | 2026-09-21 | MNF NYG@LA: Dart hurt at 1Q 11:28, Winston threw every NYG pass after it, yet the live passer stays Dart (argmax of pass attempts so far) until Winston out-throws him. Searched the core API for a structured signal: roster `active` is False and `period` 0 for all 55 entries mid-game (placeholders, not on-field status); play `participants` list only stat roles (0-5 per play), never the 11 on the field, so there is no snap participation; the only injury signal is free text ("NYG-J.Dart was injured during the play."), and most players tagged so return. 'His stats stopped updating' is not a signal either: stats move only on a touch, and healthy receivers routinely go a quarter or more without one | a structured source that marks a player out for the game, with a replayed false-positive rate near zero; until then nothing is built. Explicitly not adopted: play-text parsing, social media, or stat-silence inference, since a false 'out' corrupts live predictions worse than a stale passer | **open, nothing built.** Accepted current state: a stale passer projection until the box score catches up. Live-sim team numbers are barely affected; the injured QB's and his backup's lines are wrong meanwhile **Note 2026-09-30 (user):** P51's priced-QB promotion is pregame only; `live_sim.py` calls `team_shares` without prices, so an in-game QB switch never reaches it through P51. That stays P35's scope, unchanged; P51 is not extended to live sims |
| P36 | ATS: a zero edge (model spread = stored line) is graded as backing the away side | grading rule | 2026-09-21 | `grade.evaluate` sets `took_home = float(edge) > 0`, so edge 0 falls to the away side and gets a W/L; `export_dashboard` (`_ats`, `_graded_pick`) matches it deliberately so the Record page adds up to the grader. With no edge the model had no side, so arguably the pick should be no-action (like a push) and leave the ATS denominator. Blast radius today: **1 of 226 stored predictions** - ml-v1 on 2026_01_GB_MIN (model -1.5, line -1.5), graded L. It moves ML's season ATS by one game: 9-20-1 as graded vs 9-19-1 as no-action; baseline unaffected | decide the rule once, then apply it in `grade.evaluate`, `export_dashboard._ats` and `_graded_pick` in the same change so the grader and the page never disagree; the grader CLI and the Record page must show identical ATS totals after the change; slate reports (`calibration/analyze_nfl_slate.py` already treats edge 0 as no lean) reconciled to the same rule | **open, deferred - leave grading as-is mid-season (decision 2026-09-21).** Not urgent: one game. Note the slate-report script already disagrees with the grader here (it drops edge 0), and `calibration/2026-09-13_nfl.md` shows GB @ MIN's ML ATS as "—" (no action) where the grader and the Record page count it an L |
| P37 | Baseline ATS gets worse as its edge grows (4+ pts: 4-10-1 season, week 1 1-4, week 2 3-6-1) - why? | investigate | 2026-09-21 | Two weeks of negative best-fit weight on the edge (w = -0.64 week 1, -0.68 week 2). Overlaps P5 (stale early-season ratings), P22 (defense-heavy, unadjusted rating), P9/P2 (injury charges) | diagnosis only; the questions, tests and decision rules are in the 2026-09-21 scoping entry and were written before any test ran | **diagnosed 2026-09-21: noise, by the pre-set rules.** The 2026 gradient is not significant (slope perm p 0.27, corr p 0.11). The live Layer 1 replayed over 2016-2025 (reproduces live exactly) shows no negative early-season relation (weeks 1-4 corr +0.05, CI -0.03 to +0.13). The bigger finding: across 2,582 games the baseline edge covers **~50% at every size** (b = -0.02, CI -0.13 to +0.08), so it carries essentially no ATS information at any edge size. No fix proposed. See the 2026-09-21 findings entry **Part 2 (2026-09-22): noise still stands.** 2026's edges are at the high end of the normal range, not above it (3rd of 11 seasons). The market did not move against the big edges (CLV -0.30 pp at >= 4 vs -0.22 below, no size effect; corrected after P34). 2026's lines were among the least accurate, not sharper. Lead: QB-change games 1-9-1 (post-hoc, n = 11); see the 2026-09-22 cross-reference "QB mismatch: one mechanism, three observations" (P2 / P9 / P37). |
| P38 | Tests: every module's `check()` prints a failure but never raises, so pytest reports a failing check as passed | tooling | 2026-09-22 | Found building P34: a new `test_clv` check failed (0.5166 vs 0.5171), and `pytest -q` still printed 133 passed. `python -m tests.test_clv` printed 22 passed, 1 failed. All 14 modules in `tests/` define the same non-raising `check()`, and only their `__main__` runners count failures and exit 1 | until fixed, validation runs **each module's own runner** (`python -m tests.<module>`) as well as pytest, and reads the pass/fail count it prints; a pytest pass alone is not evidence | **FIXED 2026-09-22** by `tests/conftest.py` (see that day's P38 entry). No test module was edited. Under pytest a failed check now fails its test; the runners are unchanged |
| P39 | QB-vs-rating term: the unrestricted P28 part 2 term (margin MAE 11.557 -> 10.903 over 2024-25), tested for edge against the line and, separately, as the simulator's anchor | logic | 2026-09-22 | Set aside 2026-09-20 as out of P28's scope. The restricted form lost to the flat rule, and corr(term, market spread) = -0.324 says the market already prices QB changes. Never tested for value against the line. The sim pins its mean margin to the baseline anchor, so an accuracy gain could still pay there | see the 2026-09-22 "P39 scoped" entry, written before any run: gate 0 (the rebuild reproduces the logged term), then phase 1 (edge) and phase 2 (anchor), each with its own pass rules | **tested 2026-09-22: fails both phases by the pre-set rules; nothing built.** The 9/20 gain doesn't reproduce: against P37's verified baseline it is 10.709 -> 10.608 over 2024-25, not 11.557 -> 10.903. No edge on any arm (pooled corr with the cover residual -0.024 / -0.012 / -0.041). As the anchor, a real but small gain: identity arm pooled -0.075, 6/7 seasons; full term -0.090, 7/7; both short of the 0.10 bar. The gain is QB identity, not scale **Third observation of the same gap, 2026-10-01 (NYJ @ CHI scratch run; supporting evidence, not a reopened question; user):** with Bagent forced as CHI's starter in place of Keenum, the sim gave him Keenum's volume and efficiency (30 att, 237 vs 233.5 pass yds median) and the unanchored margin moved 8.42 -> 8.76: the engine prices a team's passing at team level, with no quarterback-quality term. Seen here from the player-props side, where it shows up as a false edge (Bagent over 200.5, sim 74% vs market 50%, +22.8 pts). It re-tests nothing about P39's margin result and changes no decision; the consequence handled is a hold (see the 2026-10-01 NYJ @ CHI entry) |
| P40 | Injury feeds: nflverse precedence can mask an ESPN "Injured Reserve" designation | logic | 2026-09-22 | `ingest_injuries.run` treats nflverse as authoritative wherever both feeds cover a player, so an ESPN `ir` row is discarded when nflverse also lists him. NYG's Paulson Adebo on the cached 09-18 pull: ESPN says Injured Reserve, nflverse carries him with no game status, so he is charged at his practice-based probability instead of 0. IR is a roster fact, not a report status | a scoped pass of its own: feed precedence per field rather than per player, measured over the cached payloads; no live row may lose a status it has today | **LIVE since 2026-09-25** (`38b5474` on main; status corrected 2026-09-29). Built and validated 2026-09-25; the row said "not yet shipped, awaiting approval", but the commit went to main with no flag, and the 9/27 06:35Z refresh used it live (TEN @ NYG +7.2 -> +4.5, Dart on IR). No explicit approval was logged; **that live 9/27 use is the approval record** (user, 2026-09-29). ESPN recovered (HTTP 200). All 4 criteria pass; the live effect is 2 rows (Dart NYG, Terrell ATL), both real IR placements. See the 2026-09-25 P40 entries |
| P41 | `score_injuries` ranks starter slots with `-(snap_share or DEFAULT)`, so a 0.0-share row sorts as 0.65 and can take a slot from a genuinely injured starter | bug fix | 2026-09-22 | `features.py:141` and `:191`. `0.0 or 0.65` is 0.65 in Python. Live today: 138 of 353 report rows sit at exactly 0.0 (the rows `apply_inactives` adds for posted inactives), and 5 teams' slots are mis-assigned, worth up to **2.07 pts** (PHI), PIT 1.80. PIT's single QB slot goes to Will Howard (0.0 snaps) instead of Mason Rudolph (0.30), so the team is charged 0 for its quarterbacks. Historically much rarer: 1,202 of 33,163 rows (3.6%), changing 16 of 5,446 team-weeks (0.3%), mean 0.23 and max 0.59 pts, and `qb_availability_loss` never changes | fix: `DEFAULT_SNAP_SHARE if share is None else share` in both sort keys; then per-team before/after on the live report, plus the historical count above; rebuild decision for training features recorded before building | **FIXED 2026-09-22** (see that day's P41 entry): `_share_or_default` in both sort keys, training rebuilt and the model retrained in the same change. Live: the 5 teams land exactly as scoped (PHI -2.07, PIT -1.80, CHI -0.40, KC -0.34, TB -0.22) and PIT's QB slot goes to Rudolph. Isolated A/B on the 2025 holdout: fundamentals MAE +0.029, with-market -0.002 -- noise from 20 changed training rows |
| P42 | Inactives: an impossible gameday list (every QB on a team marked out) is accepted as posted and flows into predictions, sims and props | data validation | 2026-09-24 | TNF ATL @ GB. ESPN's core-API game roster for ATL, read at T-10 min, flags all four ATL quarterbacks `didNotPlay` (Penix, Tagovailoa, Cooper Rush, Jack Strand) and lists no other QB on the 54-man roster; still the same when re-read at 00:13Z. The list passed the P33 lead-time gate (a genuine T-10m read), so this is not the premature-list defect. `apply_inactives` set all four to play prob 0. The baseline charged Penix's slot at the generic 5.59 pts (ATL injury total -8.00). In the sim, `box_score.passer_weights` found zero total QB weight and its silent fallback (`box_score.py:56-57`) gave depth QB1 Penix 100% of the passing: 31.0 att, 197 yds median 195. The ATL player props (London, Robinson unders in the top 25) and anytime-TD picks were ranked on that box score. Nothing in ingest -> features -> sim -> props checks a list for plausibility, and `run_sunday` reports only lists posted (2/2). Caught by manual inspection after the refresh, at T-8 min. Distinct from P28 (the sim and the books disagreeing about which healthy QB starts): here the input data itself is impossible | reject, before storage, any team list that leaves the team with no active QB; replay over every stored week-1 to week-3 list fires on tonight's ATL list and on no genuine list; a unit test pins tonight's ATL payload as rejected; `passer_weights` never falls back silently (a test asserts the warning or refusal); `run_sunday` prints each validation failure by team | **no-active-QB rule LIVE since 2026-09-25** (`86cc3ed` on main; status corrected 2026-09-29). It ran on every live window from 9/27 (e.g. the 15:45Z refresh: 18/18 lists, 0 rejected). The mechanism behind it is P49's, so the rule treats one symptom (see below). Built and validated 2026-09-25; see the 2026-09-25 P42 build entry. Logged 2026-09-24; ATL @ GB was not re-simulated (it has kicked off). **Update 9/25: Penix started** (7/7 ATL dropbacks by 2Q 11:53) after full practice with no game status: the list was wrong about him, the 5.59 baseline charge was the error, and the sim's fallback passer happened to be right. The game carries a `KNOWN_GAME_ISSUES` label. See the 2026-09-24 P42 entry **REOPENED 2026-09-28 (P49 diagnosis):** Penix has the P49 signature: flagged pregame inside the gate, not on the final injury report, on ATL's week-2 inactive list, played. ESPN's pregame `didNotPlay` carries the prior week's inactives forward; P42's no-active-QB rule treats one symptom of that mechanism. Resolve together with P49 **Correction 2026-09-28:** the 9/24 conclusion that this was a one-off ESPN feed error ('the fault is in the feed') was wrong; the mechanism is P49's stale carry-over. The shipped no-active-QB rule stays but treats one symptom |
| P43 | Injury feeds: an ESPN nickname defeats the nflverse/ESPN duplicate check, so one player is charged twice | bug fix | 2026-09-24 | Week-3 input audit. ESPN lists NYJ LB "Kiko Mauigoa"; nflverse lists "Francisco Mauigoa" (DNP Wednesday, snap share 0). The 2026 roster has one NYJ Mauigoa (Francisco, espn_id 4700136), so they are the same player. `ingest_injuries` matches the feeds on `player_key(team, name)`, the nickname misses, and both rows are kept. The ESPN copy is also stale (P44): questionable at 0.55, charged 0.19 pts on NYJ @ DET. The size of the class across all rows is unknown until measured | (1) match the feeds on a stable id first (ESPN athlete id to nflverse `espn_id` via the season roster), with the name key as fallback; (2) replay weeks 1-3: report how many ESPN rows the id join merges that the name join kept separate, and Mauigoa is among them; (3) a spot check of every newly merged pair finds no two distinct players merged; (4) suite passes | **logged 2026-09-24, not fixed** (user decision: no mid-week change; 0.19 pts). Friday's refresh clears this instance only if ESPN drops or updates Kiko's row; the name mismatch itself persists. Re-run the week-3 audit after Friday's refresh and record here whether it self-cleared. **Re-checked 9/27: not cleared; Mauigoa now charged twice at play prob 0, and 3 more live pairs found (Rob/Robert Beal Jr., JuJu/Julius Brents, Hollywood/Marquise Brown).** See the 2026-09-24 P43/P44 entry and the 2026-09-27 entry |
| P44 | Injury feeds: an ESPN in-game status ("questionable to return", "ruled out for the rest of the game") carries into the next week as a game designation | bug fix | 2026-09-24 | Week-3 input audit. ESPN keeps a player's last status until it is updated, and `ingest_espn` reads it as a status for the current week with no date check. Three non-IR rows on Sunday/Monday teams have a latest ESPN note from week 2's game, and each note is about in-game availability: Tyrique Stevenson (CHI CB, 9/20, 0.55, **0.63 pts** on PHI @ CHI), Jack Jones (SF CB, 9/20, 0.55, below the detail cut on ARI @ SF), Kiko Mauigoa (NYJ LB, 9/20, 0.55, 0.19 pts, also P43). Long-term absences with old notes are correct and must be kept: DEN's Jonathon Cooper and Nick Gargiulo (8/31, out/PUP) and SF's Brandon Aiyuk (9/21, out). Related to P21 (ESPN questionables at a flat 0.55) but distinct: P21 is about how a current status is priced, P44 is about a status that is no longer current | (1) an ESPN questionable/doubtful row whose item date is before the team's previous game ended is not treated as a current-week designation; out/IR/PUP statuses are kept whatever the date; (2) replay of the 9/24 pull: Stevenson, Jones and Kiko Mauigoa are dropped, while Cooper, Gargiulo, Aiyuk and every row dated this week are kept; (3) repeat on the week-2 pulls with the same rule and list what it would have dropped; (4) suite passes | **logged 2026-09-24, not fixed** (user decision: no mid-week change; about 0.8 pts across two games with P43). Friday's refresh should clear most of this naturally, as teams file official statuses and ESPN updates its notes. CHI plays Monday, so its designations come later and Stevenson may persist longer. Re-run the audit after Friday's refresh and record which of the three rows self-cleared. That tells us whether this needs code or only week-start timing. **Re-checked 9/27: Stevenson self-cleared; Jack Jones (SF) did not; Kiko Mauigoa's row updated to out (now P43 only).** See the 2026-09-24 P43/P44 entry and the 2026-09-27 entry |
| P45 | Simulator: a 4th-down attempt is drawn from the 3rd-down pool, which under-converts 4th & short at the goal line | engine | 2026-09-25 | Found validating P18. Inside the 10, 4th & 1-2 converts **.633 real** (n=275, 2023-25) against .540 for 3rd & 1-2, and the engine (by design, `bucket_index` clips down to 3) draws both from the 3rd-down pool: **.584 before P18, .556 after**. P18 removed an upward bias that had been partly offsetting this. Likely selection: teams go for it on 4th when they like the matchup, and the play mix differs (sneaks). Volume is small, about 92 snaps a season league-wide, about 0.17 a game | (1) measure 4th & short conversion by field zone, real vs engine, over 2023-25; (2) decide between a 4th-down pool where it has the plays, or a conversion-level adjustment; (3) at real states, 4th & 1-2 inside the 10 within 3 pp of real; no other bin moves over 1 pp | **closed 2026-09-25 as not supported** (user decision). Spot-matched, 4th-minus-3rd inside the 10 is +0.6 pp [−2.3, +3.2] over 2016-25, with the sign flipping between 2016-22 (−2.2) and 2023-25 (+6.2); no effect outside the 10; a per-yard 4th-down pool is not supportable. **Reopen trigger:** 2026's spot-matched inside-10 gap (same method) comes in positive, the fourth straight season after 2023 +5.7, 2024 +9.8, 2025 +7.5. Check after the 2026 regular season. See the 2026-09-25 P45 entries |
| P46 | Research layer: scheme / formation features (nflverse participation + FTN charting), kept separate from everything live | research | 2026-09-25 | Data diagnosis done 2026-09-25 (see the P46 scoped entry). Participation 2016-25 joins 100% to scrimmage snaps; personnel, formation and box ≥ 99%, pressure ~89% of dropbacks (2016-22), coverage from 2018. **No 2026 file, so it can't be used live.** Its formats change in 2023. FTN charting 2022-26 (2026 weeks 1-2, pulled 09-23, ~48 h lag); it is the only live-capable source | pre-set in the 2026-09-25 P46 scoped entry: margin S1-S3 + E1-E3 per feature set, totals T1-T3. Even a pass promotes nothing: the layer stays flagged unvalidated and non-live until it holds over several real weeks | **closed 2026-09-25: no out-of-sample value.** Both sets fail S1-S3, E1, T1 and T2. Pooled margin MAE is *worse* with the term (A −0.022, B −0.041), and edge corr is +0.009 (p 0.34) / +0.035 (p 0.16). Nothing promoted and nothing tracked weekly. Code stays in `research/scheme/`, which `src/` never imports (a test enforces it). See the 2026-09-25 P46 results entry **Coverage-data source search 2026-09-30 (user asked for a source beyond P46; read-only):** (1) **Free coverage shells exist only in the participation file P46 already pulled** (`defense_man_zone_type`, `defense_coverage_type`: COVER_0-9, 2_MAN, COMBO; plus per-receiver `route`), 2018-2025, posted after each season, **no 2026 file**, so never live. Testing it would be P46's data sliced differently; not proposed (user's rule). (2) **Free and live, but not coverage:** nflverse Next Gen Stats (weekly, 2026 through week 3): per receiver `avg_cushion` and `avg_separation`, per passer time to throw and air yards. How open a receiver gets, not what shell he faced; a P17 (receiver efficiency) input at most, not a coverage source. (3) **Paid, live coverage:** SIS DataHub ($99.99/month or $749.99/year NFL; leaderboards filterable by coverage scheme, man/zone and route type; manual CSV download of player-level leaderboards; API only via sales; 7-day trial shows top 20 only); FTN individual stats tool ($69.99/year, coverage splits on the web, bulk export not confirmed); FTN data licence ($3,000/year private). Big Data Bowl tracking with PFF coverage labels covers only a few competition seasons, not live. **Verdict: no free or low-cost live coverage source; nothing scoped** |
| P47 | Injury layer: play probability sees only the final practice status of the week, losing the Wed/Thu/Fri trend | data / model | 2026-09-27 | CIN @ PIT read, 9/27. nflverse `import_injuries` carries one `practice_status` per player per week (the final report), and `ingest_nfl` maps (status, that one practice level) through `ingest_injuries.PLAY_PROBABILITY`. ESPN's injury item carries the day-by-day story in `longComment`: Jamel Dean was DNP Wednesday, then limited Thursday and Friday (improving), and is stored as plain `limited` at 0.55, the same as Pittman, who was limited all three days. A trend (DNP -> LP -> LP, or LP -> FP) is lost, and the table cannot tell an improving player from a flat one. **Constraint:** `score_injuries` is shared with the ML training set (it scores historical reports with identical code); no daily history exists for past seasons in either feed, so any trend term must be live-only or validated without the ML retrain, and ESPN's comment text is free prose (parsing is fragile, and site.api 403s intermittently) | (proposed, confirm with user before building) (1) a structured per-day practice source is identified, or the ESPN text is parsed with a measured hit rate on the week-3 PIT/league rows; (2) the trend changes play probability only through a pre-set table, with the reason written before any fit; (3) replay on 2026 weeks 1-3: report how many players move and by how much, and whether graded games' injury terms improve MAE; (4) the ML training features are unchanged or retrained with a written equivalence check; (5) suite passes | **logged 2026-09-27, not built** (user decision: queue for the next week boundary alongside P18/P31; no change today). Example rows in the 2026-09-27 entry **Next step (user, 2026-09-30): verify FantasyPros, then decide.** (a) The user signs up for a free FantasyPros API test key; check whether `/nfl/injuries` returns populated per-day fields (`team_practice_1/2/3_submitted`) for real games, and how far back a request goes. $0 check before any decision to pay. (b) Start a forward-only capture of per-day practice status now: none of it can be backfilled. (c) Once there is real data to compare against, decide between the FantasyPros personal tier ($5.99/mo) and continuing to self-capture. Nothing uses this data yet. Ruled out: FootballDB (terms ban automated collection) and PFF Pro (no evidence its API has practice data). **Terms finding 2026-09-30:** the official team injury-report pages were the proposed capture source, and they are ruled out on the same grounds as FootballDB: steelers.com's Terms of Use (the team-site template) forbid "automated means, including spiders, robots, crawlers, data mining tools, or the like to download data from our Site", with exceptions only for search engines and non-commercial public archives. robots.txt doesn't block /team/, but the terms do. **Capture LIVE 2026-09-30 (user's choice: nflverse daily snapshot, via Windows Task Scheduler):** `src/capture_practice.py` saves the raw nflverse injury parquet whenever its bytes change, to `data/practice_snapshots/<season>/` (local, gitignored), and logs every check in `manifest.csv` (saved / unchanged / error), so a gap means a missed run, not a quiet day. The file is rewritten through the week with that day's `practice_status`, so successive snapshots rebuild the Wed/Thu/Fri trend. Task `\FootballPredictor\P47 practice capture` runs `capture_practice.cmd` daily at 22:00 CDT; it runs on battery and catches up after a missed start. First snapshot 08:24Z 9/30: 744 rows through week 4. Nothing reads these files. **FantasyPros free-key check 2026-09-30 (11 calls, read-only):** `/public/v2/json/nfl/injuries?year=&week=` returns per-day fields for real games: `practice_1/2/3` (DNP / Limit / Full / --), `team_practice_1/2/3_submitted`, `probability_of_playing`, `injury_update_date`, free-text `comment`. **The free tier returns 10 rows per request** (`limit: 10`, `public_api_limited: true`, `tier: free`) out of 411-471 per week (e.g. 440 for 2026 wk3), apparently the most fantasy-relevant players first, so it cannot cover a team's report; not paged around. **Depth:** per-day data exists from **2021** (team_practice_*_submitted true; 2021 wk5 4/10, 2022 8/10, 2023 10/10, 2025 wk10 6/10, 2026 wk3 9/10 rows populated; the empty rows are IR / season-ending OUT, which have no practice line); 2020, 2016 and 2012 return rows but every practice field is empty and submitted = false. So a paid tier could backfill 2021-2025 (about five seasons), which the nflverse capture cannot. Not checked: what the paid tier's row limit is (the docs page didn't render for fetch). Raw responses kept in the session scratchpad only **Sportradar NFL API checked 2026-09-30: not a per-day source.** `seasons/{y}/REG/{wk}/injuries.json` holds one entry per player (`status`, `status_date`, `practice.status`, `primary`). Week 4 today = Wednesday's report (144 players, 17 teams); finished week 3 = the final report only (294 players, 1 entry each), and Jamel Dean is `Limited Participation`, same as Pittman: the DNP -> LP -> LP trend is gone, exactly as in nflverse. A daily poll would rebuild the trend the same way the nflverse capture does, so it adds nothing over P47's live capture (a second source only if nflverse misses a day) |
| P48 | Injury layer: a player with no current-season snaps silently takes last season's snap share, with no flag that it is stale | data / model | 2026-09-27 | CIN @ PIT read, 9/27. `ingest_injuries._snap_shares` falls back player by player to the prior season (deliberate: a player hurt before week 1 has no current snaps). Joey Porter Jr. (PIT CB) has played no 2026 snaps (Q wk1, out wk2, non-injury 'other' designation wk3; ESPN: expected to make his 2026 debut wk3, possible limited workload) and is charged at his 2025 share 0.946 (0.72 pts), while PIT's 2026 corners have been Samuel 1.00, Ramsey 1.00, Dean 0.915. Nothing in the row, the breakdown or the dashboard says the share is a carry-over. Same class affects any player out since week 1 or newly signed. Partly offsetting: the team rating is still ~88% 2025 play, when Porter was on the field. Related to P41 (share ranking) and P20 (IR), distinct from both | (proposed, confirm with user before building) (1) every injury row records where its snap share came from (current season / prior season / default); (2) the breakdown and dashboard label a prior-season share; (3) decide, with the reason written first, whether a prior-season share should be discounted once the team has played N games without the player, and replay 2026 weeks 1-3 to size it before any change to a number; (4) suite passes **CONFIRMED with the user 2026-09-30, question by question (supersedes the draft above):** (Q1) two mechanisms, two rules: **M1 stale role** (a healthy backup whose 2025 share came from filling in) and **M2 absorbed absence** (a real starter out since before week 1, whose absence the rating slowly absorbs). (Q2) **M1 rule, QB only:** a QB with no 2026 snaps, on a team whose 2026 QB snap leader is not ruled out (out / doubtful / IR), gets share 0, i.e. no charge and no starter slot. Off until the team has played a 2026 game. Every logged M1 case is a QB (O'Connell, Huntley, Rattler, Stidham, and the Rush / Ehlinger slot handoffs). Rejected: all-position slot rule (zeroes injured starters like Porter) and an injury-history rule (misses O'Connell, who has been on the report). (Q3) **M2 curve:** share x (1 - w), with w the team's 2026 weight in its rating (2026 plays / (plays + 900)): about 0.94 after 1 game, 0.83 after 3, 0.64 after 8. No N, no cliff; P22 does not change w. (Q4) **Baseline only:** the baseline's injury term uses the adjusted share; the ML keeps the unadjusted share it was trained on (no retrain). ML-with-P48 is P55. (Q5) **Validation, correctness plus sizing on 2026 weeks 1-4:** M1, the zeroed QBs took no snaps in >= 95% of zeroed QB-games and none started (pbp ground truth); M2, every changed charge equals the formula; the logged cases shown before and after; margin MAE reported, not gated; labelling steps (1)-(2) as drafted; suite passes. (Q6) **Timing:** the labels (share source on every row, prior-season shares flagged on the dashboard; display only) ship as soon as built; the M1 / M2 number changes are validated once week 4 is graded and ship at the boundary after MNF 10/12, one boundary after P22 | **logged 2026-09-27, not built** (user decision: queue for the next week boundary alongside P18/P31; no change today). Step (1)-(2) are labelling only; step (3) moves numbers **Live confirmation 2026-09-27 (current week, not hypothetical):** with the 15:05 CDT window's full inactive lists, three healthy backup QBs made inactive were charged as starters from **2025** snap shares, while each team's 2026 starter had 100% of weeks 1-2 snaps: LV Aidan O'Connell 0.82 -> 4.92 pts (Cousins starts), NO Spencer Rattler 0.82 -> 4.90 (Shough starts), BAL Tyler Huntley 0.59 -> 3.56 (Lamar starts; ML `qb_loss_diff` 0.594). Served 19:15Z: **BAL @ DAL base BAL -2.3 vs ~BAL -5.9 without the Huntley charge**; LV @ NO NO +10.4 (the two charges roughly cancel). LV @ NO's earlier +13.7 carried O'Connell at Q/0.25 (3.69 pts) from the same defect. Nothing changed live (user decision). Adds to step (3): a QB (or any player) with zero current-season snaps whose team's current starter is healthy should carry ~0 charge; the replay must include these three rows **Fourth live case 2026-09-27 23:05Z:** DEN Jarrett Stidham (inactive; 2025 share 0.53, 0 snaps in 2026, Nix 100%) charged 3.18 pts; served LA @ DEN base LA by 4.0 vs ~LA by 0.9 without it (market LA -1) **Two P49 residual cases to check when P48 is built (user ruling 2026-09-29):** P49's replay (criterion 3) found two games where removing a false or P48-type QB charge passes the charged QB slot to another inactive QB whose charge is itself P48-type: **ATL @ GB wk3** (Penix −5.59, Cooper Rush +4.74 as snap leader; net −0.85 home margin) and **LA @ DEN wk3** (Stidham −3.18, Ehlinger +2.10; net +1.08). P48's replay must include both, and show what each charge becomes **Labels BUILT + shipped 2026-09-30 (steps 1-2, display only; see the 2026-09-30 P48 labels entry):** every injury row's breakdown carries `share_source` (current / prior / default); the dashboard flags prior-season shares. Numbers unchanged (16 week-4 predictions rebuilt in memory: identical but for `generated_at`). M1/M2 not built; they ship after MNF 10/12 **Clearest case yet, 2026-10-01 TNF PIT @ CLE (served 23:05Z):** CLE's emergency third QB **Taylen Green** (3QB per the Browns' official inactives article) and LB **Justin Jefferson**, both with **zero recorded snaps** in 2025 and 2026, are listed `out` by the ESPN injury feed and charged at full positional weight on `DEFAULT_SNAP_SHARE` 0.35: Green 1.0 x 0.35 x 6 = **2.10 pts, the single largest charge in the game** (CLE's starting C Elgton Jenkins is 1.50), Jefferson 0.20 x 0.35 x 6 = 0.42; together 2.52 of CLE's 4.72. Neither has a realistic chance of meaningful snaps (Watson starts, 0.997 share). Unlike the 9/27 cases this is not a stale prior-season share: there is no share at all, so the 'deliberately low' unknown-player default lands on a QB slot at full QB weight. **Recurs for CLE:** the same two rows charged the same 2.52 in the served week-1 prediction (CLE @ JAX, 9/13 16:35Z); week 2 had no row; week 3's rows were pulled 23:05Z, after CAR @ CLE kicked off, and CLE's one QB slot was held that week (and week 2) by Shedeur Sanders' P49 false flag (5.5). So nothing prevents it: it fires whenever ESPN lists them `out` before a prediction and no higher-share QB is charged, including every early-week CLE prediction made before lists post. A posted inactive list does not fix it either: `apply_inactives` keeps a reported player's own (missing) share, so 0.35 still applies. Sensitivity check logged separately (2026-10-01 'PIT @ CLE injury-layer sensitivity'); for P48's fix, not acted on |
| P49 | Inactives: a gameday list that is plausible but wrong (players flagged `didNotPlay` pregame who then play) is stored and applied, including starting QBs | data validation | 2026-09-28 | Found grading week 3 (Sun 9/27). 14 players stored as inactive from pregame reads (first seen 15:45Z / 18:50Z / 23:05Z, all inside the P33 gate, on lists that passed the ruled-out coverage test at 78.5%) recorded stats: **Sam Darnold (SEA QB1)**, **Kyler Murray (MIN QB1)**, Shedeur Sanders (CLE), Michael Pittman Jr. (PIT), Brock Bowers (LV), Zay Flowers (BAL), Jauan Jennings (MIN), RJ Harvey (DEN), Kendre Miller (NO), Ty Johnson (BUF), Tyler Goodson (DAL), Jordan Watkins (SF), Jalon Daniels (TB), Tommy DeVito (NE). Effect: `apply_inactives` set each to play prob 0; the baseline charged 10.2 pts across 8 games for players who played (Sanders 5.5, Pittman 1.16, Bowers 0.77, ...); the sim dropped them, so **SEA's sim passer was Drew Lock and MIN's was Carson Wentz**, and SEA/MIN player props and TD picks were ranked on the wrong QB. P42's rule rejects only a list with no active QB, and its entry anticipated this gap ('a list that is wrong in a plausible way'). Process gap: the morning QB sweep (sim QB1 = books-priced QB) ran before lists posted and was not re-run after each window; it would have caught Darnold and Murray. Related to P33 (lead time) and P42 (impossible list); distinct: these lists were on time and possible | (proposed, confirm with user) (1) measure the false-positive rate of pregame `didNotPlay` over every stored 2026 list against box scores; (2) decide, with the reason first, a guard: e.g. never apply an inactive flag to a player whose team's books-priced QB/starter he is, or cross-check against the official injury report (a healthy, unlisted starter flagged inactive is held, not applied); (3) replay weeks 1-3; (4) re-run the QB/starter sweep after every window refresh (process, can start now) | **logged 2026-09-28, not built** (user: nothing changes live; queued after MNF is graded). SEA @ WAS, MIN @ TB and CAR @ CLE are final; their served numbers are recorded as they were **Diagnosed 2026-09-28 (read-only):** root cause is stale carry-over. Pregame flags are the prior week's list not yet cleared plus this week's (74% of week-3 flags carried from week 2; all 14 false flags and Penix were carried; 0 of 64 new flags touched the ball). Nothing in the ESPN payload separates them. Best replayed guard: R2 (hold a flag for a player not on the final injury report or with no game status), 59/65 false caught, 29/204 genuine held; QB-only 6/6 caught. P42 reopened as the same mechanism. See the 2026-09-28 diagnosis entry **Leading candidate (user, 9/28): the QB-only precision rule**; adoption criteria **confirmed by the user 2026-09-28** (criterion 9 added: a held QB1 is cross-checked against the books-priced QB and reported as unresolved, not applied, when they differ; criterion 2 rests on 3 weeks, late scratches untested) **BUILT 2026-09-29 on branch `p49-qb-hold` (ac07bbf, pushed, NOT merged):** criteria 1, 2, 5, 6, 7, 9 pass; criterion 3 has two P48 slot shifts and criterion 4 one depth-order miss (CHI/Keenum), both awaiting the user's ruling before merge. See the 2026-09-29 P49 build entry **MERGED 2026-09-29** (user ruling: criterion 3's residual, ATL @ GB and LA @ DEN, belongs to P48 and is noted in P48's row; criterion 4's CHI miss is a depth-order problem, logged separately as P51). Suite 159 passed on main; first live use is the next window refresh (Thursday PIT @ CLE). PHI @ CHI pbp since posted: Dalton played (1 pass attempt), so criterion 1 is 11/11 **Non-QB recurrence 2026-10-01 (TNF PIT @ CLE):** ESPN's lists read at T-80m were last week's carried forward. CLE 7 = its 5 week-3 inactives + 2 new (Browns' official article, 6:45 PM ET: 5, no Campbell / Brailsford); PIT 8 = its week-3 list exactly (second source: 6, no Porter Jr. / Anderson). Campbell's roster entry byte-identical across weeks. QB-only hold did not apply. **User ruling: option (c), skip ESPN's list for the game** (`config.INACTIVES_SKIP_GAMES`, read side only, rows kept); manual file carries the Outs + Porter Jr. cleared. See the 2026-10-01 'TNF PIT @ CLE stale inactives' entry. Evidence that a non-QB guard (e.g. R2) is needed: **tracked as P68** (post-10/5 batch, scoping first) |
| P50 | Record page: a predicted game that hasn't been played yet is labelled "not predicted - kicked off before the first pipeline run" | display bug | 2026-09-28 | Found checking the dashboard 9/28: PHI @ CHI (MNF, predicted, kickoff still ahead) shows the not-predicted label in the week-3 table, and the week header reads "15 predicted". Cause: `export_dashboard._weeks` builds each week's `models` from **graded** rows only and `_game_row` sets `predicted = bool(models)`, so any ungraded game counts as unpredicted; `WeekBreakdown.jsx` then shows the kicked-off-early reason for every `!predicted` row. Display only: grading, records and every served number are unaffected; `grade.py` is not involved. Confirmed on a hand-built fixture: the Monday game comes out `predicted: False`, `n_predicted` 1 of 2 | (1) `_weeks` receives the set of game ids with a stored prediction and sets `predicted` from it, not from grading; (2) each row carries `pending` (predicted, no final, kickoff in the future or game not completed), and the page shows it as pending, not unpredicted; (3) the not-predicted label is shown only for a game with no prediction that has kicked off; (4) `tests/test_record_pending.py` passes with its `xfail(strict=True)` marker removed (today it xfails, at the missing `predicted_ids` parameter; the assertions then check the behaviour), and the graded-row guard still passes; (5) suite passes | **FIXED 2026-09-29** (user: display-only, shipped ahead of the week-4 batch). `_results` passes every stored prediction id into `_weeks`; rows carry `pending`; `WeekBreakdown.jsx` shows 'predicted — pending, not graded yet', and the kicked-off-early label only for an unpredicted game whose kickoff has passed ('not predicted yet' otherwise). Criteria 1-5 met: xfail marker removed, both tests pass, suite 149 passed; dashboard builds. Logged 2026-09-28 |
| P51 | Sim starting QB: a held (P49) QB can still be out-ranked on the depth chart by a QB the books don't price, so the sim starts the wrong QB | data / model | 2026-09-29 | Found in P49's replay (criterion 4). MNF PHI @ CHI wk3: Caleb Williams genuinely out; Case Keenum's false inactive flag is **held** by P49, but the nflverse depth chart ranks Tyson Bagent (QB2) above Keenum, so the sim still starts Bagent, whom the books don't price. Keenum started and threw 34 of CHI's passes (nflverse pbp); Bagent threw none. Distinct from P49: the flag is handled correctly; the problem is depth order when QB1 is out. Related to P28 part 1 (`QB_EXPECTED_STARTER`, OFF) and P35 | **Scope and criteria set with the user 2026-09-30, before any run (narrow rule):** in the sim's squad build (`simulate_nfl.team_shares`), when the depth-chart QB1 is ruled out (out / doubtful / IR on the report, or an applied inactive flag) and exactly one other available QB on the team is priced for this game (a pass-yds line in this week's props lines), that QB is promoted to QB1 via `_promote_starter`. No price, or more than one: depth order stands and P53's cross-check still warns. Sim only: P49's hold (`features._qb_hold`) and the injury layer (P48) are not touched. A price must come from this week's lines, and the promoted QB must not be ruled out or applied-inactive. **Validation** (replay of QB order and passer weights, weeks 2-4, pregame inputs: that day's nflverse depth chart, the stored props-line snapshots, inactives and holds; no finished week is re-simulated; truth = each team-game's starter from pbp, most dropbacks): (1) CHI wk3 comes out as Keenum; (2) no team-game flips from the right starter to the wrong one; (3) every firing case is listed; (4) every non-firing team-game is byte-identical (squad order and passer weights); (5) suite passes. Week 1 has no props snapshot and is out of the replay. **Ship is a separate decision after validation:** with P22 after MNF 10/5 or a week later is decided then, not now | **logged 2026-09-29; scoped 2026-09-30. BUILT + replayed 2026-09-30 on branch `p51-priced-qb` (52b1420, pushed, NOT merged). Criterion 1 FAILS on the pre-set input; 2, 4, 5 pass; 3 listed.** Replay `research/p51/p51_replay.py` (96 team-games, weeks 2-4; 64 with a pbp starter; roles rebuilt on each week's pre-kickoff depth chart and earlier pbp). (1) CHI wk3 stays **Bagent**: the week-3 props snapshot (pulled 9/25 00:09Z) has no CHI pass-yds line (the TD market listed Bagent); Keenum's line first appears in the MNF-day pull (9/28 23:01Z). (2) 0 right -> wrong flips. (3) 2 firing cases, both with QB1 unchanged (priced QB already next in line, room reordered): MIN wk2 (Wentz), WAS wk3 (Mariota). (4) 94/94 non-firing team-games byte-identical (squad order, shares, shifts, passer weights). (5) suite 196 on the branch. **Sensitivity (not a substitute):** with PHI @ CHI on the MNF-day lines, as P49's replay did, CHI -> Keenum (wrong -> right), 0 flips, 93/93 identical. **Why it matters live:** `run_sunday.py` simulates before it pulls props, so a window's sim never sees that window's lines; the live MNF sim had the 9/25 lines too. As the pipeline runs, the rule would not have fixed CHI. Making it work needs the window's props pull moved ahead of the sim (same pull, same quota), which is a separate process change for the user. Also noted: `live_sim.py` (in-game sims) calls `team_shares` without prices, so P51 does not reach live sims. Still wrong after the rule (reported): ATL wk2 (Tua vs Rush, no price), NYG wk2 (Dart priced, Winston started), SEA wk2 (Darnold not ruled out pregame, Lock priced and started) **Re-validated 2026-09-30 on the corrected order (user: props pull moved ahead of the sim in `run_sunday.py`, on the branch, step order pinned by a test):** each game takes its latest saved pull stamped before kickoff. (1) CHI wk3 -> **Keenum** (his line is in the MNF-day pull, 9/28 23:01Z) **pass**; (2) 0 right -> wrong flips **pass**; (3) 3 firing: CHI wk3 (Bagent -> Keenum, wrong -> right), MIN wk2 and WAS wk3 (QB1 unchanged); (4) 93/93 identical **pass**; (5) suite 197 on the branch **pass**. **The three week-2 residuals are not an ordering issue.** The replay's report input missed them: stored injury rows re-pulled after kickoff fall out of the 'before kickoff' filter, so ATL and SEA had no QB statuses at all. The official final report (nflverse) has ATL Penix Out, Tua Doubtful (and flagged inactive), SEA Darnold Out. With it filling the gaps (`--official-report`): ATL -> Rush and SEA -> Lock from depth order and statuses alone (SEA fires, QB1 unchanged); criteria still pass (CHI Keenum, 0 flips, 4 firing, 92/92 identical). NYG wk2 is outside P51 entirely: Dart started (NYG's first 5 dropbacks) and Winston replaced him in-game; the 'most dropbacks' truth marks the sim wrong, but the pregame starter was right (in-game changes are P35). Branch `p51-priced-qb` holds the rule and the reorder; **not merged. Ships with P22 at the boundary after MNF 10/5** (user, 2026-09-30: a QB-selection and process fix, not a rating change; its promotions are recorded per game in the sim's `input_warnings`, so they can be told apart from P22's effects). Sequence in P22's row. Follow-ups: P57 (replay report gaps), P35 (in-game switches, unchanged) **Sportradar depth chart checked 2026-09-30:** its week-3 chart (generated 9/29) orders CHI QBs Williams, Bagent, Keenum, the same as nflverse, so it would not have fixed CHI; ATL, SEA and WAS also match the nflverse order **SHIPPED 2026-10-07 with P22 (merge c2c18dc). Fired once on week 5: CHI @ GB, Williams out, Bagent promoted. QB sweep: TB and BAL mismatches are not P51 cases (QB1 not ruled out); held and labelled by user ruling. See the 2026-10-07 ship entry.** |
| P52 | Dashboard: show each NFL game's line movement (spread and total) since first tracked and since the week reopened, labelled as line movement, not bet percentages | display | 2026-09-29 | `odds_snapshots` is append-only and already holds NFL history from 2026-09-15 (weeks 2-4, 48 games): median 9 pulls per game (6-17), 9 books, first pull ~11.5 days out for weeks 3-4, last ~1.2 h before kickoff; 38 of 48 spreads moved 0.5+ pt first to last. College has 1 pull per game, so no movement. Early pulls are look-ahead lines taken before the previous week's games: SEA @ WAS +2.5 on 9/16, reopened +7 on 9/23. The book set changes between pulls (SEA @ WAS first pull: 2 books) | the ten criteria in the 2026-09-29 P52 entry (same-book medians, reopen point, sign convention, null on a single pull, fixed label, no model / schema / quota change, hand check on SEA @ WAS plus two games before shipping) | **shipped 2026-09-29** (user); display only; NFL only until college odds are pulled more than once a week |
| P53 | Storage: `SupabaseStore.select` pages with OFFSET and no ORDER BY, so a read spanning two pages can skip or repeat rows | bug fix | 2026-09-29 | Week-4 refresh, 9/29. The injuries table holds 1,070 NFL rows (two 1,000-row pages). Two reads shortly after the 19:47Z injury upsert saw no WAS QB row at all: the pipeline's `simulate_nfl` run (it started Jayden Daniels, who is out at play prob 0, while the books price Mariota) and a diagnostic `FeatureContext` built minutes later. Every later read (6 selects, 4 contexts) was complete (1,070 unique rows) and gave Mariota. No other writer touched the table after 19:47Z. Postgres guarantees no row order without ORDER BY, so OFFSET pages can overlap after heavy updates. **Leading explanation, not proven** (not reproduced after the fact). Re-running the sim step from stored data changed more than WAS: props priced 108 -> 110, held out 11 -> 17, unmatched names 1 -> 0. The stored baseline predictions match a fresh read on 16/16 games | (proposed, confirm with user) (1) `select` orders every paged read by the table's key (`TABLE_KEYS`); (2) a test pins the ORDER BY on a multi-page read; (3) after the change, 20 back-to-back reads of injuries, odds and depth_charts return identical key sets; (4) suite passes. **Safety net chosen by the user 2026-09-29, built before the root-cause fix. Criteria, set before the build:** (S1) a multi-page `SupabaseStore.select` whose unique-key count or row count differs from the server's exact count is retried up to 3 times, then raises `IncompleteRead`; partial data is never returned silently, and `select_merged` does not mistake it for a missing table; (S2) tests: an overlapping read (one row repeated, one skipped) and a short read are both caught, a retry that comes back complete returns the full rows, and a single-page read makes no count call; (S3) the sim warns loudly, and records it in the stored sim's `input_warnings`, when a team's sim QB1 is not the books-priced QB (pass-yds line, same season/week) or is out/IR (play prob 0) in an independent second injury read; a test replays the WAS case (warning raised) and a clean case (no warning); (S4) no served number changes: a re-sim of week 4 gives 0 warnings, matching the 9/29 sweep; suite passes. The user's first proposal (fall back when a QB read returns zero rows) was set aside: the WAS read dropped Daniels' injury row, so he looked healthy rather than missing, and that guard would not have fired | **Safety net SHIPPED 2026-09-29** (user-approved). `SupabaseStore.select` checks multi-page reads against an exact server count by unique key, retries 3x, then raises `IncompleteRead` (`select_merged` re-raises it). `simulate_nfl` cross-checks each sim QB1 against a second injury read and the books-priced QB, printing `[warn]` and storing it in `input_warnings`. S1-S4 pass: `tests/test_p53.py` 10 tests, suite 177; week-4 re-sim gives 0 warnings and all 16 sims are byte-identical to the stored ones (box scores included); the check's inputs are live (219-row second read, 16/16 games with week-4 lines, 7 with a pass-yds QB line). **Root cause REPRODUCED 2026-09-29, no longer only the leading explanation:** the first live use of the check caught a read of injuries returning 1,070 rows with only 1,004 unique (66 repeated, 66 skipped); the retry came back complete. Unordered pages overlap often, not just after one write. The root-cause fix (ORDER BY by `TABLE_KEYS` on paged reads, criteria (1)-(4) of this row's first draft) was queued for the week boundary. **Pulled forward and scoped 2026-09-29 (user); NOT built, awaiting approval.** *Diagnosis:* Postgres guarantees no row order without ORDER BY, and PostgREST's OFFSET pages are separate queries. Measured on injuries (1,070 NFL rows, 2 pages): unordered, 1 of 30 two-page reads was incomplete and page 0 came back with 2 different contents; then 0 variants in 300 page-0 reads, so it comes in bursts. **Every captured event (4: the 9/29 sim, the check's first live read, the experiment, a validation run) overlapped by exactly 66 rows.** That is consistent with one heap page's worth of rows visited in a different position (a scan starting at a different block, or a plan change), not with random loss. Not confirmable from here: EXPLAIN is disabled on the project (PGRST107) and there is no direct DB connection. Ordered by the primary key: 30/30 complete, 1 page-0 content. *Fix proposed:* `_pages` adds `.order(k)` for each `TABLE_KEYS[table]` column. All 15 `TABLE_KEYS` equal the schema's primary keys, so the order is total, and served by the PK index. Keep the count check: ordering cannot stop rows being inserted or deleted between page requests. *Validation already run (read-only, ordered pages patched in vs today's count-checked reads):* all 15 tables return identical rows; features + baseline for all 272 2026 NFL games, 0 value differences (baseline margins changed: 0); week-4 sims 16/16 identical; dashboard export (NFL + CFB) 0 value differences. The only changes are the order of ties, which become deterministic: equal-point injuries in a team's list (51 lists), the per-book moneyline list (142 games), games sharing a kickoff on the dashboard, and flagged games on the Record page. *Build criteria, proposed:* (R1) the order is applied to every paged read (test); (R2) 100 back-to-back two-page reads of injuries, 0 incomplete; (R3) a full refresh with no `[P53]` retry line; (R4) the validation above re-run on the built code, same result; (R5) suite passes **FIXED 2026-09-29 (user go): `_pages` orders every paged read by `TABLE_KEYS` (= the primary key); the count check stays.** R1 pass: a new test pins every page's ORDER BY to the full key. R2 pass: 100 back-to-back two-page reads of injuries, 0 incomplete (1,070 = server count each time). R3 pass: full week-4 refresh (`run_pipeline`, sim, props, TD, exports; odds quota 306 -> 253), 0 `[P53]` retry lines and 0 QB cross-check warnings. One unrelated failure in that run: the sim's Supabase write hit a transient `ConnectError` and fell back to the local mirror; re-run straight away, all 16 rows written to Supabase (logged as P54). R4 pass: pre-fix unordered reads vs the built code, all 15 tables identical, 0 of 272 baseline margins changed, week-4 sims 16/16 identical, exports 0 value differences; the only differences are runtime `generated_at` stamps and the (now fixed) order of ties. R5 pass: suite 178 |
| P54 | Storage fallback: any failed Supabase write of `game_simulations` is reported as "table missing, paste the schema SQL" and silently diverts the rows to the local mirror | bug fix | 2026-09-29 | P53's R3 refresh: a transient `ConnectError` during the sim upsert printed "game_simulations is missing from supabase ... Paste db/PASTE_INTO_SUPABASE.sql" (the table exists), and the 16 fresh sims went to local SQLite while Supabase kept the older rows, so the stores diverged until the sim was re-run. `simulate_nfl.run` catches every exception as "missing table"; `db.upsert_or_mirror` does the same for other tables | (proposed, confirm with user) (1) a connection or timeout error is retried, then fails loudly, never mirrored; (2) only a genuine missing-table error mirrors, and the message names the real error; (3) tests for both; (4) suite passes | **FIXED 2026-09-30 (user go).** `db.is_missing_table` (PostgREST `PGRST205`, the code Supabase returned for a probed nonexistent table; Postgres `42P01`) and `db.is_transient` (`httpx.TransportError`: connect, timeout, protocol). `SupabaseStore._execute` retries transient errors 3x (2 s, 5 s), then raises `StoreUnavailable` ("not falling back to the local mirror"); every read, count and write goes through it. `upsert_or_mirror`, `select_merged`, `export_sims._read_all` and the live tracker mirror only on a missing table and re-raise everything else. The sim write now uses `upsert_or_mirror`. The live tracker's write logs `[ERROR]` and keeps the cycle in live.json without switching the session to the mirror; its read fails the cycle, and the loop retries next cycle. Criteria: (1) pass: live, a store pointed at an unreachable host retried 3x on read and on write, raised `StoreUnavailable`, nothing mirrored; (2) pass: missing table mirrors, and the message names the code; (3) pass: `tests/test_p54.py` 7 tests (classification; retry then success; retries exhausted; missing table not retried; write and read paths for both failure kinds); (4) pass: suite 185. Normal operation unchanged: live read 272 games, sim write to Supabase |
| P55 | ML injury features with P48's adjusted snap shares | model | 2026-09-30 | P48 was scoped baseline-only (user, 2026-09-30, P48 Q4): the ML's `injury_diff` / `qb_loss_diff` keep the unadjusted share they were trained on, so the ML still carries the stale-share over-charge (e.g. O'Connell). Doing it properly means mirroring P48 in `build_training`'s historical shares, rebuilding the training file and retraining | (proposed) the historical shares mirror P48 exactly; retrain; 2025 holdout MAE not worse than the current model; train and serve use identical share logic | **logged 2026-09-30, not scheduled**; after P48 ships, and not while P8's decision is pending |
| P56 | College: upper edge cap for early-season edges (split from P5) | threshold | 2026-09-30 | Split from P5 (user, 2026-09-30). 2026 live: 80 graded college games, all week 2 (week 1 and weeks 3-4 were never predicted; 3 week-3 predictions sit ungraded); 31 had \|edge\| > 8 and went 9-22 ATS. One week, one slate. No college replay exists | (to be set with the user) tested only on a college walk-forward replay or a full college season of predictions | **logged 2026-09-30, open**; the pipeline is not currently predicting college weekly |
| P57 | Replays of a finished week: stored pregame injury rows go missing once re-pulled after kickoff | process | 2026-09-30 | Found in P51's replay. `injuries` is upserted per (player, team, season, week), and a pull after kickoff restamps `pulled_at`, so a 'rows pulled before kickoff' filter drops them: ATL and SEA week 2 had no QB statuses at all (Penix Out, Tua Doubtful, Darnold Out on the official final report), and the replay started Tua and Darnold. P49's replay used the same filter | **Standard practice (user, 2026-09-30):** any replay of a finished week fills gaps in the stored pregame report from that week's official final report (nflverse `import_injuries`), states that it did, and reports how many rows it filled; as P51's `--official-report` option does. A shared helper for this, and re-checking P49's replay with it, whenever there's time | **logged 2026-09-30; practice adopted; helper not built** |
| P58 | Remove NCAAF entirely (code, ingestion, predictions, props, TD, dashboard tab); archive its data | removal | 2026-09-30 | User decision: full removal, not a pause. Mapped 2026-09-30 (read-only; suite 194 on main). **College-only, delete:** `src/ingest_cfbd.py`; `calibration/analyze_slate.py`; `dashboard/src/SlateTable.jsx`, `GradedSlate.jsx`; the 118 `cfbd_*` and college ESPN/odds caches in `data/cache`. **Shared, remove only the college branches:** `run_pipeline.py` (CFBD import + step; `--sport` default ncaaf -> nfl; drop `both`); `config.py` (CFBD_API_KEY, CFBD_BASE, ESPN_CFB); `ingest_odds.py` (college sport key, default sport; keep `match_events`); `names.py` (college alias table only; keep `similarity`/`norm`, used by NFL odds matching, ESPN team matching and props); `market.py` (ncaaf window; keep `median_price`, the P34 fix, which `ingest_cfbd` only calls); `clv.py` (college ESPN base, move cap, event-id branch, FCS-proxy check; keep the Elo check); `grade.py` (college score ingest; default loop -> NFL); `features.py` (college HFA, FCS proxy, sigma, injury scale, CFBD consensus source; FeatureContext default -> nfl; keep Elo); `predict_baseline.py` (FCS proxy, college slate day, default sport; keep the Elo branch); `predict_ml.py` / `train_model.py` / `build_training.py` (college paths; keep the `both_fbs` column and `elo_diff` on NFL rows so `training_nfl.csv` stays byte-identical); `ingest_injuries.py` / `ingest_weather.py` (college ESPN endpoint, 0.65 college default share, default sport); `export_dashboard.py` (college tab/slate logic; default sports -> NFL; keep always-empty NFL fields); dashboard `App.jsx` / `GameDetail.jsx` (college view, tab bar, college text, proxy and college-injury notes, `cfbd:` prefix); `tests/test_clv.py` (3 college checks); schema files (comments only; keep `conference`, `is_conference`, `sp_plus`); README, architecture, `no-key-data-sources.md`, dashboard README, `.env.example` (NFL-only). **Hidden dependencies:** `build_training.py` imports `ingest_cfbd` at top level and `run_pipeline.py` imports it; `run_sunday` calls `export_dashboard.run()` and `grade.run()` relies on the both-sports default, so both become NFL-only (NFL output unchanged). **Data (Supabase college rows):** games 331, predictions 166 (160 graded), clv_log 166, odds 1,859 + 69 orphans, odds_snapshots 555, weather 237, venues 806, teams 138, team_ratings 276, injuries 1; same in the SQLite mirror; plus `data/training_ncaaf.csv` and `models/ncaaf_margin.*` | **User decisions 2026-09-30:** (1) archive every college row (per table) plus the training file and model to `data/archive/ncaaf_2026/` (local, OneDrive-backed, NOT committed: public repo, third-party API data), verify the archive's row counts match the counts above, then delete college rows from Supabase and the mirror (irreversible; runs only after the archive check). (2) College history stays: calibration-log entries, `calibration/2026-09-12_ncaaf.md`, the Stage 1 report and script; P6, P7 and P56 closed as 'retired: college removed' with a dated removal entry naming the archive. (3) Own branch, after the 10/5 P22/P51 boundary lands (only overlap: `src/config.py` with P22). (4) CFBD_API_KEY in `.env` and its revocation: user, separately. (5) Always-empty NFL fields (`conference`, `is_conference`, `sp_plus`, `both_fbs`) left alone. **Verification (NFL must be identical):** suite before (194) and after (only the 3 college checks go); baseline + ML predictions rebuilt in memory identical apart from timestamps; NFL section of an in-memory dashboard export identical; `match_events` on cached NFL odds gives the same assignments; every module imports, `build_training`/`train_model --sport nfl` load, `run_pipeline`/`run_sunday --help` run; dashboard builds and NFL pages render with no console errors | **planned 2026-09-30; nothing run.** Executes on its own branch after P22 + P51 ship at the 10/5 boundary |
| P59 | Idea: confidence tiers from a real signal (model agreement, edge size, or injury uncertainty) | idea | 2026-09-30 | Split from P4 when it was retired (user): the old tier only measured input completeness and never varied in the NFL. Candidate signals: baseline/ML agreement, edge size, early season, how unsettled the injury picture is. Unscoped | (none yet) | **idea only; not scoped, not scheduled** |
| P60 | Receiver efficiency: add Next Gen Stats (separation, cushion, air yards; QB time to throw) to P17's design | research | 2026-09-30 | User asked whether NGS, which measures how open a receiver got, improves receiver-efficiency prediction. Data diagnosis 2026-09-30 (read-only, no outcomes looked at): nflverse NGS receiving and passing 2016-2026, updated weekly (2026 weeks 1-3 posted, week 3 by 9/30). **Weekly rows exist only for receivers with 5+ targets in that game** (passers: 15+ attempts): about 28% of receiver-games but about 56% of targets (2024, 2025, 2026 alike); 86% of 5+-target receiver-games join to our pbp; target counts agree 96%. So it can only act on high-volume receivers (where props are priced), and separation is only measured in games where the receiver was featured | **Criteria set with the user 2026-09-30, before running.** Arm A = P17's frozen 9/19 design (`research/p17/`: k = 100, position prior, prior season at 0.5, outcome-aware crediting with IPF). Arm B = identical except each receiver's shrinkage prior is informed by his as-of NGS profile (separation, cushion, intended air yards, his QB's time to throw), the mapping fitted on earlier seasons only, every choice fixed on 2025 weeks 3-10. Judged on 2025 weeks 11-18 (the 9/19 window); 2026 weeks 1-4 reported, not gated. Bars: (1) rec-yds MSE >= 1% better than arm A and better in >= 6 of 8 weeks, CI reported; (2) the same bar on NGS-covered receivers alone; (3) receptions MSE not worse than arm A; (4) receivers with no NGS history byte-identical to arm A; (5) stop rule: no re-tuning on judged weeks; a gain under 1% stops the test and is reported as such. A pass reopens the design discussion; it does not build. Expectation stated up front: P17's whole player-efficiency effect was ~1.3% on yards (CI touching 0), so NGS can at best sharpen a 1-3% effect | **criteria set 2026-09-30; runs after P17's recheck (after MNF 10/5); results reported either way** **Run 2026-10-07 (arm B specified in the log first): arm A reproduced 9/19 exactly; B vs A on 2025 wks 11-18 +0.12% worse (95% CI -0.29% to +0.54%), 3/8 weeks; profiled +0.21%, 4/8; 2026 wks 1-4 +1.01% worse (CI excludes 0). Bars 1-2 fail, stop rule fires: CLOSED. Bar 4 cannot hold at output level under IPF (noted before running).** |
| P61 | Props: capture each game's closing prop line (Sportradar Odds Comparison Player Props) so prop CLV can be measured at all | data / validation | 2026-09-30 | Nothing in the repo computes prop CLV, yet P17's adoption test is "prop CLV >= 0 over 65+ leans"; our last Odds API props pull comes hours or days before kickoff. Sportradar's per-game props carry, per book, the current line and the opening line (`total`, `open_total`, `odds_*`, `open_odds_*`), and kept last week's ended PHI @ CHI with every line flagged `removed` (174 book lines, 39 player-markets). Against our stored week-3 MNF-day pull: 35 player-markets matched, 15 differ from Sportradar's last line (Keenum pass yds 170.5 vs 164.5, Lemon rec yds 28 vs 23.5; book mixes differ). **Retention is short:** the schedule held only that MNF game, none of week 3's Sunday games (ended 9/27), so closing lines must be captured within about a day, not backfilled. **Caveat, not yet checked:** that "removed" means pulled at kickoff and not earlier | (proposed, confirm with user) (1) a pull of each game's props at T-15 min, plus one after kickoff that keeps the `removed` lines, stored raw (same pattern as P47's capture), about 32 calls/week; (2) on two windows, measure how often the post-kickoff line differs from the T-15 pull (the kickoff caveat); (3) prop CLV = the move from our priced line to the close, in the direction of our lean, reported per market; no model change; (4) suite passes | **Capture STARTED 2026-09-30 (user: passive, no prediction impact, does not wait for the P22/P51 boundary); criteria below set before the first capture.** `src/capture_prop_closes.py`, run every 15 min by Task Scheduler (`\FootballPredictor\P61 prop closes`, `capture_prop_closes.cmd`). Per game, one pull at each checkpoint (minutes from kickoff): t-60, t-45, t-30, t-15, t+0, t+15, t+120, t+24h; a window that passes without a pull is logged `missed`. Schedule cached, re-read every 12 h; a quiet pass makes no call. Raw responses + `manifest.csv` (lines, removed, live, event status per pull) in `data/prop_closes/` (local, gitignored); nothing reads them. Budget ~130 prop + ~14 schedule calls/week (~610/month, KEY1). Tests `tests/test_capture_prop_closes.py` (13); suite 206. Live dry run (clock T-10 before PIT @ CLE, output in a scratchpad): 372 book lines, **10 already `removed` more than a day before kickoff**, so `removed` also marks lines pulled mid-week, not only at kickoff. **Validation of the capture point (first two windows: TNF 10/1 PIT @ CLE and the Sunday 10/4 early window; unit = one book's line for one player-market; `is_live` markets excluded):** (V1) capture: every game has its t-15 and a post-kickoff pull, <= 1 missed pre-kickoff checkpoint per window; (V2) not early: of the lines live at t-30, >= 95% are still live (not `removed`) at t-15; (V3) frozen after kickoff: >= 95% of lines have the same total and price at t+0, t+15 and t+120 (lines still changing after kickoff would mean in-play updates, not a close); (V4) removed at kickoff: >= 95% of the lines live at t-15 are `removed` by t+15; (V5) retention: report whether the game is still returned at t+120 and t+24h. **Decision rule:** V2-V4 pass -> the close is the last post-kickoff (`removed`) line, and the kickoff point is confirmed to the 15-min resolution of the pulls. V3 fails -> the close is the t-15 pull (last pre-kickoff), with the t-15 -> t+0 change reported as the unmeasured last-15-min move. V2 fails (lines pulled early) -> each line's close is its last live value, and how early is reported. V4 fails -> report what `removed` means from the data; no close defined until it is understood. Always reported: distribution of t-15 -> close changes; mid-week `removed` share; calls used. No prop CLV is computed until V1-V4 are read **Task check 2026-09-30:** first scheduled pass (17:30 CDT) was terminated (0xC000013A, console closed or interrupted) after writing its start stamp and before any call; a manual run of the wrapper and the 17:45 scheduled pass both exited 0 ('nothing due'). Cause not confirmed; a repeat inside a checkpoint window would show as `missed` in the manifest and count against V1 **Cause and fix, 2026-09-30 (user: confirm before Sunday):** Task Scheduler history was disabled, so no record exists; by elimination: no sleep, power, crash or logoff event at 17:30 (System / Application logs), on AC, no battery or idle stop; no Sportradar call logged, so it died between its start stamp (22:30:01.7Z) and its first call's response. 0xC000013A is a console control event (Ctrl+C / Ctrl+Break / window close); the task ran 'only when user is logged on', so each pass opened a visible console in the user's session for 1-2 s. Most likely that window was closed or received a keystroke; not provable without history. **Fix 1 (applied):** the task now starts `capture_prop_closes.vbs`, which runs the .cmd with no window; the .cmd writes a start and an exit line per run (a start with no exit = killed). Manual trigger 17:51: exit 0, both lines. **Fix 2 (needs the user, elevated):** 'run whether logged on or not' (S4U) was refused without elevation (Access denied); a script tests the mode with a throwaway task, then converts P61, and enables Task Scheduler history. Note: neither mode runs while the laptop sleeps (battery: sleep after 10 min; AC: never; WakeToRun off); `run_sunday --watch` is a terminal process, not a task, and needs the same. P33's probe (first run Sun 10/4) has the old visible-console setup **Fix 1 FAILED; replaced 2026-09-30 20:48 (user: keep fix 2 for later, move P33 to the same launcher):** the .vbs wrapper never ran under the scheduler. Every scheduled pass from 18:00 to 20:45 left no start line in `task.log`, and the 20:45 `wscript.exe` was still alive with its only thread in state `Suspended` and no child process: created, never resumed, so the script never executed (P61 captured nothing for ~3 h; no checkpoint was due, so no `missed`). The same command line runs fine from a shell, and a manual `Start-ScheduledTask` reproduced the hang on P33; the 17:51 manual trigger that passed was not representative. Cause not found. **Fix 1b (applied to P61 and P33):** both tasks now run `conhost.exe --headless cmd.exe /c <name>.cmd` with the project folder as working directory (no window, no wscript; the .cmd is called by bare name because headless conhost mis-parses a quoted path with spaces). .vbs files removed. Manual triggers: P61 and P33 both exit 0 with start + exit lines. **Verified on scheduled passes (not manual):** P61 at 21:00:01 and 21:15:01 each wrote a start and an `exit 0` line, task result 0, no process left behind. P33's first scheduled pass is Sun 10/4 00:00 (same launcher; manual triggers only so far). Fix 2 (elevated, S4U + history) stays with the user, not before Sunday |
| P62 | Props source: Sportradar as the primary pull for the four priced markets, The Odds API kept as fallback, to end the quota-driven coverage gaps | data | 2026-09-30 | Odds API quota 200 after the 9/30 pull (184 after TD), ~64 credits per 4-market pull + 16 for TD. Sportradar, 2 week-4 games (PIT @ CLE, ATL @ NO) against this week's Odds API file: **the same players on all four markets** (pass 2/2, rush 5/5 and 6/6, rec yds 12/12 and 10/10, receptions 12/12 and 10/10), 1 call per game for every market. Books differ: Sportradar has MGM, DraftKings, FanDuel, BetRivers, Caesars (WilliamHillNJ), plus a `consensus`; Odds API had betonline and bovada as well (6 books PIT @ CLE, 3 ATL @ NO; Sportradar 5-6 and 4-5). 13 extra markets (carries, attempts, completions, pass TD, longest reception, rush+rec, kicking...), none of them priced by us today. Anytime TD **is** posted (**corrected 2026-09-30**: first read as absent because the check only read `players_props`; scorer markets sit in the separate `players_markets` block): PIT @ CLE 29 players, ATL @ NO 25, DraftKings / FanDuel / Caesars + consensus, alongside first / last / 2+ / 3+ TD scorer | (proposed, confirm with user) (1) over one full week, per game and market, player coverage >= the Odds API's; (2) median line within 0.5 of the Odds API's on the same books at the same pull; (3) the props ranking built from each source differs only where lines differ (list every change); (4) Odds API calls per week drop, reported; (5) trial terms and the post-trial price are known before anything depends on it (a trial key expires) | **Phase 1 criteria S1-S8 CONFIRMED 2026-09-30 (user, one at a time); Phase 1 shadow BUILT 2026-09-30; **validation WINDOW OPEN 2026-10-01T03:22Z -> 2026-10-15T03:22Z** (NFL weeks 4 and 5, TNF 10/1 to MNF 10/12); S7(a) cleared: Sportradar trial ends **2026-10-30** (user, from the Sportradar account page: 'one month from today' read on 9/30 CDT), after the window; no switch decision.** **S8(c) props-page section built and approved 2026-10-01 (S5 unmeasured on the page by design).** Quota approved: ~825 of 950 calls/month on KEY1 (P61 + shadow). KEY1 only, no rotation, stop at the margin (S7b; P65). Switch gates outside Phase 1: S6(b) Sportradar-primary fallback built and tested; S7(d) terms written with sources; S5(c) record-marking scheme agreed. See the 2026-09-30 'P62 Phase 1 criteria confirmed' entry. Earlier: **scoped 2026-09-30 (user: scope before deciding); nothing built, no decision.** See the 2026-09-30 'P62 scoped' entry: what reads the lines, what a switch requires, what could break (QB selection by name is the serious one), and a shadow-only Phase 1 with criteria S1-S8, to be confirmed with the user. Swapping the source changes no model; coverage and quota only **10/7 rulings (user): S2 excludes a game with no market on either source (reported); S5 'not graded: did not play' (snap-count check); window extended to 2026-10-20T12:00Z (through MNF 10/19); S3 and S4 need >= 6 gameday pull pairs; KEY1 90 calls in October, ~450 projected to 10/19. See the 2026-10-07 P68 / P62 entry.** **Gameday minimum of 6 pairs CONFIRMED (user, 10/7).** |
| P63 | Game side: real bet-% / money-% splits (Sportradar Betting Splits) as a cross-check on value flags | investigate | 2026-09-30 | **No access.** All five Sportradar keys return 401 on the documented endpoint (`api.radar360.sportradar.com/insights/v2/bettingsplits/nfl/en/game/{sr:match id}`, both header styles); the docs say the splits token is separate from the sports-API key and that trial access is arranged through a sales rep; v2 is retired 9/30 for v3, whose path is not public. So nothing could be compared with P52. Prior against it: P37 found the baseline edge carries no ATS information at any size, and closing-line CLV runs slightly negative, so a signal that must beat the close is starting from a weak model side. **Also a design limit:** splits appear to be current values only, so there is no history to walk forward; any test needs forward capture | (if access is obtained; set before any capture) hypothesis: flagged games where money % exceeds bet % on the flagged side by >= 15 pp (sharper money) cover more than flagged games against it. Capture splits at each odds pull, forward only; test on >= 65 flagged games (most of a season at the current flag rate), bar = the P37 / baseline trust rule (52.4%, p < 0.05). Display-only until then | **blocked 2026-09-30: no key.** Get a splits token (sales) first, and its terms, before scoping further |
| P64 | Injuries: a hand-transcribed injury/practice file (read from report screenshots) merged into the live injury layer before a refresh | data | 2026-09-30 | No scraped source is allowed or affordable for the official team reports (P47: team pages banned by terms; FantasyPros free tier 10 rows/request), and nflverse/ESPN can lag a team's report on game day. The user can read reports from screenshots. The live layer uses only (game status, one practice level) through `ingest_injuries.PLAY_PROBABILITY`; no per-day logic exists (P47 not built) | see the 2026-09-30 P64 entry: C1-C8, set before the build | **BUILT 2026-09-30, C1-C8 pass; not yet used live** (first use: whenever a `data/manual_injuries/<season>-wk<NN>.csv` is present at a refresh; none exists, so nothing has changed). `src/manual_injuries.py`; merge in `ingest_injuries.run`; read side in `features.latest_injury_report`; `run_sunday` stops the refresh on an invalid file. See the 2026-09-30 P64 entry's results. Days 1-2 are kept in the file but unused (user: not folded into P47's trend-table decision; revisit when P47 is scoped) |
| P65 | Sportradar: P61's live capture runs through the rotating key manager, whose multi-key use has not been checked against Sportradar's trial terms | terms / data | 2026-09-30 | Raised during P62's S7 review (user, 9/30): P62's shadow is restricted to KEY1 with no rotation until the multi-key terms are known, because five trial keys used to extend quota may breach a one-trial-per-person term. P61 (`capture_prop_closes`, live since 9/30) calls through `sportradar.KeyManager`, which moves to the next of `SPORTRADAR_API_KEY1..5` when a key reaches `MONTHLY_QUOTA - QUOTA_MARGIN` (1000 - 50) calls for a product in a UTC month. **Checked 2026-09-30 (`data/sportradar/usage.jsonl`, 28 calls):** no `switch` event yet; all P61 calls on KEY1; KEY2-5 have 2 calls each, all from the 9/30 diagnosis (every key tested on Betting Splits and the NFL / props APIs), not rotation. P61's ~610 calls/month plus P62's ~215 stay under 950 on KEY1, so rotation is not expected in October, but nothing stops it | (proposed, confirm with user) (1) Sportradar's terms on holding and using multiple trial keys are found and cited (account page, terms, or a written answer); (2) until then, P61 and P62 use KEY1 only and stop with a log line at the margin instead of rotating; (3) any past rotation is listed from `usage.jsonl` (none as of 9/30) | **logged 2026-09-30, nothing changed** (user: check separately whether P61 has been operating within confirmed terms). Belongs with P62 S7(d), which needs the same terms |
| P66 | Scenarios: for a game whose starting QB is genuinely unresolved, show the prediction under each realistic starter, on demand | display / tooling | 2026-10-01 | IND @ WAS (Daniels questionable, books price Mariota) and NYJ @ CHI (sim Keenum, books Bagent) are served on one assumed starter; the 10/1 manual Bagent-vs-Keenum scratch run showed what the alternative looks like. Nothing repeatable exists | (proposed, confirm with user before building) see the 2026-10-01 'P66 scoped' entry | **LIVE 2026-10-01: panel approved as final (user, `b42a408`); wired into `run_sunday` for qualifying games (user)**, after the props ranking, merged into `scenarios.json`; also on demand (`python -m src.scenarios --publish`). See the 2026-10-01 'P66 built' entry. Criteria confirmed 2026-10-01 as proposed (user) |
| P67 | Props record: grade the served top 25 / top 50 each week against actual outcomes (W-L-push, hit rate, by category), from an archive of every served ranking | process / validation | 2026-10-01 | No graded record of the served props list exists. `props.json` is overwritten at every ranking; before 10/1 only ad-hoc snapshots survive. Backfill checked 2026-10-01 (read-only): **week 1** no list ever existed (the ranking was added 9/15); **week 2** only the Thu/Fri lists (lines 9/17 23:00Z) survive, the Sat/Sun lists after the 2A / k32 / PENALTY_REPLAY changes were overwritten; **week 3** the TNF list is saved exactly (ATL @ GB, generated 00:09Z, kickoff 00:15Z), the Sun/Mon lists were not: each game's last lines and stored pregame sim survive, so its prices can be rebuilt but not its rank (each window's list also held later games whose sims were re-run since); **week 4** every ranking since 10/1 03:47Z exists only as P62 shadow snapshots (`rank_*/props.json`), which depend on Sportradar pairing and stop at the 10/15 window close. Reusable: `p62_compare.grade` (player match + W/L/push on the four markets) and `_actual` (ESPN finals, cached); nflverse as fallback | Phase A (archive) A1-A5 and phase B (record) B1-B8 in the 2026-10-01 'P67 scoped' entry, set before any build | **scoped 2026-10-01; user decisions: record starts at week 4, no backfill into it; each game graded from its own last list served before kickoff (S5's rule), with the real row count per week shown beside the top-25 / top-50 numbers; week 2's Friday list and week 3's TNF game only as a labelled 'pre-record / reconstructed' footnote, never counted; phase A (archive) built before Sunday 10/4's early window.** **Phase A BUILT 2026-10-01** (`src/props_archive.py`, hooked in `props.run`): A1, A2, A3, A5 pass; **A4 PASS 2026-10-01 23:06:58Z** (TNF refresh: archive bytes == `props.json` == public copy; index sha and lines match; the P62 shadow failed that run, so this archive is the only copy). Phase B not started |
| P68 | Inactives: extend P49's scrutiny to non-QB positions; ESPN's pregame lists carry last week's inactives forward for every position, and only QBs are held today | data validation | 2026-10-01 | **TNF PIT @ CLE, read at T-80m (inside the P33 gate):** two stale carry-over cases on one game, both non-QB starters. CLE's list = its 5 week-3 inactives + 2 new; Tyson Campbell (CB, 0.875 snaps) and Parker Brailsford flagged though the Browns' official article (6:45 PM ET) lists neither; Campbell's roster entry byte-identical to week 3's. PIT's list = its week-3 list exactly (8/8); Joey Porter Jr. (CB, 0.946) and Spencer Anderson (G, 0.98) flagged though a second source lists neither. Porter Jr. also had a stale ESPN **injury-feed** `out` row (a second path, not the inactive list). Handled for that game only, by hand (`INACTIVES_SKIP_GAMES` + manual file; c536e27). Prior evidence: P49's 9/28 diagnosis measured an all-positions guard on weeks 1-3: R2 (not on the final report, or no game status) caught 59/65 false flags and wrongly held 29/204 genuine; R3 (on the prior week's list and not ruled out this week) 52/65 and 23/204; the all-positions version was parked until the cost of a wrong hold on a skill player is measured. R2 and R3 would both have held all four flags tonight. New tonight: a whole team list identical to the prior week's (PIT) is a list-level signal P49 did not test | to be set with the user at scoping, before any replay (process rule). Questions the scoping must answer: (1) rule: R2 / R3 / both / a list-level 'identical to last week' test, per position group; (2) the cost of a wrong hold on a non-QB (a genuine inactive kept active: sim usage to a player who is out; baseline charge missed), measured on graded games, against the cost of a false flag applied; (3) what a held flag does to the P33 rule that promotes a posted team's unlisted questionables to 1.0 (a team with held flags may not count as fully posted); (4) the ESPN injury-feed path (a stale `out` with no official-report entry), in or out of scope; (5) store the raw roster responses (today only parsed rows are kept, so a disputed read cannot be re-examined); (6) replay over every stored week 1-4 list incl. tonight's, with the per-position catch / wrong-hold table; (7) how `INACTIVES_SKIP_GAMES` retires once a guard ships | **proposed 2026-10-01 (user: a real tracked item, not built); queued for the post-10/5 batch, scoping first.** Until then nothing automatic covers non-QB carry-overs: a starter flagged inactive with no official-report status is checked by hand against the prior week's list and an official team source before a refresh, as on 10/1 **10/7: decision 1 set (four-candidate replay per group, selection fixed in advance, >= 10 false flags per group else pooled non-QB rule, simpler rule within noise, list-identical as a team-level flag with its false-alarm rate measured first). Decision 5 BUILT: raw roster responses logged (`src/inactives_raw.py`), byte-identical outputs on / off / failing. Decisions 2-4, 6, 7 open. See the 2026-10-07 P68 entry.** **Decision 2 DECIDED 10/7: option (b): points decide OL and defense; skill must not lose on points or sim usage, disagreement goes to the user.** **Decision 3 DECIDED 10/7: B + D (held player keeps report probability; team-level identical-list flag applies nothing and promotes no one), D only if its false-alarm rate is low and promotion loss is costed, B only if it beats A by more than noise on held-player Brier, QBs reported separately and changed live only after their own validation at a boundary.** **Decision 4 DECIDED 10/7: C (report-only log of ESPN-only out/doubtful rows for players who played last week; persistent file incl. later snap outcome; byte-identical on/off; not built until approved) + B as replay candidate needing >= 5 stale charged cases, closed if < 5 by end of week 10.** **Decision 6 DECIDED 10/7: replay now (wks 2-3 + PIT @ CLE) and again on wks 5-6; false-flag range (any pregame read / latest stored read), a candidate must win under both; genuine = no snaps + post-game did-not-play, else third bucket; ships only if the wk 5-6 re-run picks the same rule.** **Replay run 10/7 (read-only): defense/ST -> R3 under both bounds (lower margin +0.01 pts); skill, OL keep today's behaviour; QBs stay on P49; D does not qualify (its one firing vs the post-game list, PIT wk4, was genuine); B vs A within noise (A stays); 0 stale ESPN-feed cases. Ships only if the wk 5-6 re-run agrees. Also: 3 of the 4 flags the 10/1 PIT @ CLE skip treated as stale were genuine by snaps.** **STATUS 10/7 (user): no guard supported on weeks 2-4 evidence; weeks 5-6 re-run decides; C running to build the case count. Decision 7 done (PIT @ CLE skip retired; week-4 outputs identical). C built, report-only (`src/espn_feed_report.py`).** |

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

## 2026-10-07 — TNF TB @ DAL: starting-QB decision rule, written before any official data exists

Set by the user on 10/7, before TB's official week-5 report, the books' window prices or any inactive list exist.
Today: the simulation starts Baker Mayfield (did not practise, no game status, play probability 0.60) in about 60% of
games and Jalon Daniels in the rest; the books price only Daniels; Mayfield's and Daniels' QB props and TD picks are
held, and the game carries a QB label (now built at each export from that refresh's sim split and priced QB, bfb02c9).

**Sources.** Mayfield's status comes from the NFL's official injury report (via nflverse, or a `2026-wk05.csv` row the
user transcribes from it). **A QB inactive flag clears only after the Buccaneers' own official inactive article has been
read and omits the player** (standing rule, 10/7); otherwise the flag stays and the doubt is noted.

**The rule, by Mayfield's official status:**
- **(a) Out:** remove Mayfield's holds (props and TD). **Keep Jalon Daniels' holds, as unreliable** (the 10/1 Bagent
  precedent: the simulation gives any starter the team's passing, so a backup's line measures the missing
  quarterback-quality term, not the player). P51 promotes Daniels in the sim. The label's note says so.
- **(b) Active with no game status:** remove Mayfield's holds **only if the books price him** in the window's props
  pull; otherwise no change. Daniels' holds stay.
- **(c) Questionable or Doubtful:** **no change**; the holds stay until the starter is confirmed by an official source.

**Applying it.** Only on the user's OK. The edits are prepared in advance as patches (not applied); an edit applied after
the 18:00 CDT refresh needs a props / TD re-rank to take effect. BAL @ ATL is not part of Thursday's window and its holds
are unchanged.

---

## 2026-10-07 — P58 (NCAAF removal) built on its own branch; every NFL check identical; NOT merged, nothing deleted from Supabase

**Where it lives.** Branch `p58-ncaaf-removal` in the worktree `Football Predictor p58`: **16dcd12** (the removal) and
**2240b11** (NFL suspect-line test, committed by the user). **main stays at b74bf9c**, untouched. Nothing merged;
nothing deleted from Supabase or the mirror.

**Archive (done, read-only on every store).** `data/archive/ncaaf_2026/` (local, OneDrive-backed, not committed; 81 MB):
every college row from Supabase and, separately, from the SQLite mirror, plus `training_ncaaf.csv`,
`models/ncaaf_margin.json` / `.meta.json` and the college cache files; `manifest.json` has per-table row counts and
sha256. **Supabase matches the P58 counts exactly:** games 331, predictions 166, clv_log 166, odds 1,859 + 69 orphans,
odds_snapshots 555, weather 237, venues 806, teams 138, team_ratings 276, injuries 1.

**Code removal, as scoped.** Deleted: `src/ingest_cfbd.py`, `calibration/analyze_slate.py`, `dashboard/src/SlateTable.jsx`,
`GradedSlate.jsx`. College branches stripped from `run_pipeline.py` (NFL default, `--sport` kept as `nfl` only),
`config.py`, `ingest_odds.py`, `names.py` (alias table emptied; `similarity` / `norm` kept), `market.py` (`median_price`
kept), `clv.py` (Elo check kept), `grade.py` (NFL default), `features.py` (Elo fallback kept), `predict_baseline.py`,
`predict_ml.py`, `train_model.py`, `build_training.py` (`both_fbs` column kept), `ingest_injuries.py`, `ingest_weather.py`,
`export_dashboard.py`, dashboard `App.jsx` (no tab bar, NFL hub only) and `GameDetail.jsx`. Hidden imports fixed
(`build_training.py`, `run_pipeline.py`). Schema file `db/PASTE_INTO_SUPABASE.sql`: **comments only**; every column kept.
README, architecture, `no-key-data-sources.md`, dashboard README and `.env.example` made NFL-only, with college sections
kept as dated history.

**Checks (NFL must be identical).**

| check | result |
|---|---|
| suite | main **280**; branch **280** (the college CLV test was replaced by an NFL test of the suspect-line cap: a 5.5-pt move is `suspect_line`, a 4-pt move counts) |
| week-5 baseline predictions, 15 games, in memory | **identical** before / after (sha) |
| week-5 ML predictions, 15 games | **identical** |
| NFL section of an in-memory dashboard export | **identical** (sha) |
| `match_events` on 4 cached NFL odds / events files (31 / 32 / 31 / 8 events) | **identical** assignments, 0 misses |
| imports | 52 -> 51 modules (only `ingest_cfbd` gone), 0 failures |
| commands | `run_pipeline` / `run_sunday` and 10 module `--help`s exit 0; `train_model.load('nfl')` 3,060 rows |
| `training_nfl.csv` and `models/nfl_margin.*` | on-disk sha **identical** before / after; a full rebuild gives the **same sha** with branch and main code (3,092 rows) |
| front-end build | **passes** (57 modules) |
| NFL pages render, no console errors (preview on port 5175) | **pass** (user, Edge InPrivate, extensions off): games, a game page, props, record and past weeks render with **no console errors**. The only 404 is `/favicon.ico`, the same on main (neither tree has a favicon or an icon link; P58 did not touch `index.html`). Red errors seen first in a normal window came from a browser extension (`all.js`, "Extension context invalidated") and were gone in InPrivate. Also served over HTTP, all 200: the page, both built assets, `data.json` (`sports: ['nfl']`, 15 games), `sims.json`, `props.json`, `sims_archive/index.json`, `p62_compare.json`, `scenarios.json` |

The harness ran each tree's code against main's `.env` and data, read-only; it was run twice on the untouched tree and
gave identical hashes, so it is deterministic.

**Judgment calls (for review before the merge).** (1) `SLATE_START_UTC_HOUR` (11:00Z) **kept**, only its comment changed:
NFL slate windows depend on it (00:15Z night games, the 13:30Z London game). (2) `fcs_proxy_applied_to` **kept** in the
NFL rating detail, always None, so NFL prediction components keep one shape (removing it would change NFL output).
`calibration/stage1_before_after.py` is kept as history, as decided, and can no longer be re-run for college.

**Findings.** **Cache files: 116 found against 118 planned.** By name the cache holds exactly 116 college files (34
`cfbd_`, 80 `espn_summary_ncaaf_`, 1 `espn_inj_ncaaf_`, 1 `odds_ncaaf_`), all archived; a wider pattern's 3 extra hits
are NFL `espn_athlete_` files whose hash contains "cfb". The 9/30 count was not saved as a list, so the two are most
likely files overwritten or expired since; nothing on the branch reads any college cache file. **The SQLite mirror is
stale, not 'the same':** it holds fewer college rows (games 260, predictions 160, clv_log 160, odds 991, odds_snapshots
0, weather 166, team_ratings 138; venues 806, teams 138, injuries 1 and orphans 69 equal). Nothing on the branch reads
those rows today: `db.select_merged` adds a mirror row only when Supabase lacks its key, and every college row is still
in Supabase; `grade` reads CLV filtered to NFL. The one unfiltered read, `python -m src.clv --report` without `--sport`,
would surface the mirror's 160 college CLV rows **if Supabase's college rows were deleted first**.

**All checks pass.** **Open items.** (1) Browser console check: done 10/7 (above). (2) **Merge only after the TNF window (10/8) and the raw-roster
check.** (3) **Mirror cleanup together with or before the Supabase delete.** (4) **Supabase delete only after a stable
game week and the user's explicit OK.** (5) P6, P7, P56 closed as 'retired: college removed' and the CFBD key revocation
(user) at the merge, as decided 9/30.

---

## 2026-10-07 — Correction: the 10/1 PIT @ CLE skip cleared three genuine absences; standing rule for manual overrides; skip retired

**Correction (user, 10/7).** Three of the four flags the 10/1 skip treated as stale were genuine absences by snap counts:
**Joey Porter Jr. (PIT CB), Spencer Anderson (PIT G), Parker Brailsford (CLE OL) took no snaps in week 4; only Tyson
Campbell (CLE CB) played** (71 defensive + 3 special-teams snaps). The 10/1 clearing relied on a **projection and an
aggregator list, not an official Steelers inactive list**. On CLE, the Browns' official article was read: it omitted
Campbell (who played) and Brailsford, who took no snaps and is did-not-play on ESPN's post-game roster, so he may have
dressed unused; by snaps alone he counts as an absence here, and that one case is not settled by an official source. The 10/1 sensitivity figure 'PIT by ~1.7' is
**superseded**. **Week 4 stays graded as served** (PIT by 3.2; CLE won 27-24).

**Sensitivity re-run (read-only, same `score_injuries`, served inputs otherwise).** Pre-injury margin +0.04 (home).

| scenario | CLE | PIT | net | margin |
|---|---|---|---|---|
| served (re-scored; reproduces exactly) | -4.72 | -1.52 | -3.20 | **PIT by 3.2** |
| **corrected:** Porter Jr. 1.59 + Anderson 1.18 charged out, Brailsford out (no snap share on record, so 0, as the pipeline charges him), Campbell active, Green and Jefferson's phantom charges removed | -2.20 | -4.29 | +2.09 | **CLE by 2.1** |
| corrected + PIT's list genuine, so its unlisted Questionables (Ramsey, Black, Echols) promoted to 1.0 | -2.20 | -3.22 | +1.02 | CLE by 1.1 |

Market PIT -2.5; final CLE by 3. The served number had the wrong side; the corrected inputs put the baseline on CLE's side.

**Standing rule (user, 10/7).** A manual override clears an inactive flag **only when the team's own official inactive
article has been read and omits the player**; otherwise the flag stays and the doubt is noted. **Every
`INACTIVES_SKIP_GAMES` entry cites that source in this log and expires once the game is graded.**

**P68 decision 7 DONE (user, 10/7): the PIT @ CLE skip is retired** (`config.INACTIVES_SKIP_GAMES` now empty; the standing rule is in its comment). Only `features.apply_inactives` (current week only, now week 5) and `scenarios` (upcoming games only) read it. Checked before and after, skip on vs off: the week-4 archive (`data/` and public copies), `index.json`, `dashboard.json` / public `data.json`, the 32 graded week-4 rows, and in-memory rebuilds of the week-4 archive payload and the Record page weeks are **identical** (sha256). Suite 275 before, 275 after.

**P68 C BUILT (user-approved 10/7), report-only.** `src/espn_feed_report.py`, called from `ingest_injuries.run` after the rows are stored, with copies. Flags ESPN-only `out` / `doubtful` rows for players not on the official (nflverse) report who played last week (any snap), prints them, and keeps `data/espn_feed_flags/flags.csv` (one row per season / week / team / player: first / last flagged, times, estimated charge, then the served baseline charge and the snap outcome once posted). Stale charged case = served charge > 0 and played. `ESPN_FEED_REPORT=0` off; every failure caught and printed. `tests/test_espn_feed_report.py` (4): stored rows and return value identical with C on, off, failing inside and raising at the call site; flag logic (IR, questionable, no last-week snaps, official players excluded); file, served charge and outcome fill; inputs never mutated. Tests write to a temp folder (conftest). Suite 279. **Dry run on stored week-5 rows (scratch folder, not the real file):** 13 flagged, 0 stale cases; midweek the official report covers 11 rows, so 'not on the official report' holds for almost every team and most of the 13 are likely genuine new injuries (they cannot count as stale unless charged and then played). Open: restrict C to teams whose official report has posted (a spec change for the user).

**P68 status (user, 10/7): no guard supported on weeks 2-4 evidence; weeks 5-6 re-run decides; C running to build the case count.** No non-QB guard is built.

**P68 C, `official_report_posted` (user, 10/7; definition written before C's file reads any week-5 data).** C keeps logging every flagged row (no filtering at the source) and records, at flag time, `official_report_posted` = **true if the flagged player's team has at least one row, of any status or none, in the current week's official (nflverse) injury report as pulled in that same refresh** (the rows `ingest_nfl` returns for that season and week, before the ESPN merge and the manual file); false otherwise, including when the nflverse pull failed. Set once, at first flag; a later refresh does not rewrite it. The midweek review list printed at each refresh shows only rows with the column true, plus a separate count of false rows. B's stale-charged-case count is reported three ways (posted true, posted false, total); **the minimum of 5 applies to the total.** Report-only as before. Disclosure: the 10/7 dry run (scratch folder) read the stored week-5 rows before this definition existed; it wrote nothing to the real file.
Built the same day: column `official_report_posted` in `flags.csv` (set at first flag, kept on later flags); the printed list shows posted rows only with a count of the rest; stale cases printed as posted / not posted / total. New test `test_official_report_posted_column`; the on / off / failing / raising identity test still passes. Suite 280.

---

## 2026-10-07 — P68 replay run (read-only): defense/ST selects R3 under both bounds (lower margin +0.01 pts); skill, OL, QB keep today's behaviour; D does not qualify; 10/1 PIT @ CLE premise was 3/4 wrong

Run as decided (decisions 1-6, logged first). `research/p68/p68_replay.py`; output `research/p68/p68_replay_results.md`.
Sample: weeks 2-3 + week 4 PIT @ CLE, 487 pregame-seen flags (upper) / 424 on the latest stored read (lower). Truth:
snaps (any) vs post-game ESPN did-not-play; third bucket **1** (skill), unknown 0. Nothing stored or served.

| group | false / flags (upper) | (lower) | weeks 3-4 result (upper) | (lower) | selected |
|---|---|---|---|---|---|
| skill | 29 / 92 | 14 / 77 | R3 eligible: caught 7/7, wrong 9/26, net +1.19 pts, usage removed 0.35 vs added 0.20; R2 and R2&R3 split (to user) | none eligible (1 false flag; every rule nets -0.7 to -0.8 pts) | **none: today's behaviour** |
| OL | 16 / 96 | 8 / 88 | none eligible (false flags carry ~0 pts; wrong holds 2.4-3.6 pts) | none | **none: today's behaviour** |
| defense/ST | 59 / 213 | 21 / 175 | R3: caught 24/25, wrong 26/55, net +7.62 pts (R2 +5.17, R2&R3 +6.25) | R3 only eligible: caught 5/5, wrong 26/55, net **+0.01** pts | **R3 (both bounds)** |
| QB (own line) | 12 / 86 | 10 / 84 | every rule nets -13.7 to -18.5 pts | -14.7 to -19.5 | stays on P49 |

- **(i) D:** against the stored prior-week pregame list (as run) no list is identical (0 of 20), so D holds nothing.
  Sensitivity against the prior week's **post-game** list (what ESPN carries forward): 1 of 34 identical, **week 4
  PIT, a genuine list (0 false flags)**, so D's only firing is a false alarm. **D does not qualify** (decision 3
  condition 1); its promotion cost is moot (0 Questionables affected as run).
- **(iii) Decision 3, B vs A:** only R3 holds players with a game status (non-QB, n 9 upper / 5 lower). Brier A 0.222 /
  B 0.171 (upper), 0.400 / 0.177 (lower); B-A 90% CI -0.252..+0.130 and -0.550..+0.072: **within noise, A (today)
  stays**. QBs: no held QB with a game status under any rule.
- **(iv) Decision 4:** 42 C-flaggable ESPN-only rows; **0 stale charged cases** (B needs 5 by the end of week 10).
- **Read:** defense/ST R3 wins under both bounds, but the lower-bound margin (+0.01 pts) is a tie with doing nothing,
  so this is the thinnest possible pass. Per decision 6 (3) **nothing ships unless the weeks 5-6 re-run picks R3 for
  defense/ST again**; every other group keeps today's behaviour.
- **Approximations (disclosed):** the points cost ignores the starter-slot filter and the 8-pt team cap; skill usage
  is a play-by-play share proxy (targets + carries over earlier 2026 games, 2025 if none), because the stored sims
  applied the flags and do not carry flagged players; 'played' counts special-teams-only snaps; the lower bound can
  include an in-game re-read; R3 and D exist only on weeks 3-4.
- **Finding on the 10/1 ruling (PIT @ CLE skip):** by snap counts, Joey Porter Jr., Spencer Anderson and Parker
  Brailsford took **no snaps** in week 4; only Tyson Campbell played (71 defensive snaps). Three of the four flags
  treated as stale were genuine. The skip (and the manual clear of Porter Jr.'s injury-feed `out`) removed real
  absences from the served TNF numbers; the 10/1 sensitivity entry had the skip moving the margin little (Campbell 1.47
  against Porter Jr. 1.59 + Anderson 1.18). Week 4 is graded and stays as served; nothing changed.

---

## 2026-10-07 — P68 decision 1 set; P68 raw roster storage built (logging only); P62 rulings and window extension; capture gaps 10/4-10/6

**P68 decision 1 (user, 10/7): rule per position group = a four-candidate replay, selection rule fixed in advance.**
Groups: skill (RB / WR / TE), offensive line, defense + special teams; QBs stay on P49's rule. Candidates per group:
R2 (not on the final report, or no game status), R3 (on the prior week's list and not ruled out this week), R2 and R3,
and **"whole team list identical to last week's" as a team-level flag** (applies to every flag on that list); its
false-alarm rate on genuine lists is measured **first**, before it can be a candidate. **Selection, fixed now:** per
group, the candidate catching the most false flags whose wrong-hold cost is no more than the false-flag cost it removes
(cost unit = decision 2). **A group needs >= 10 false flags in the replay**, otherwise it inherits the pooled non-QB
rule. **Candidates within noise: the simpler rule wins** (order: R2 or R3 alone < R2 and R3 < team-level).
Decision 2 next.

**P68 decision 2 DECIDED (user, 10/7): cost unit = option (b).** Offensive line and defense + special teams: baseline points decide (the injury charge wrongly missed by a wrong hold, or wrongly applied by a false flag: weight x share x (1 - play prob) x 6). Skill (RB / WR / TE): points **and** sim usage (the share of team targets and carries given to an absent player, or taken from a present one, in the stored pregame sims); a candidate must not lose on either unit, and **if the two disagree the group goes to the user**, not decided automatically.

**P68 decision 3 DECIDED (user, 10/7): held flags vs P33's promotion rule = B + D, with three conditions.** Evidence (read-only, weeks 2-3, 60 team lists): unlisted Questionables promoted to 1.0 played 55/57 (96%); every one of the 60 lists has at least one R2-holdable flag (healthy scratches are never on the report), so C (any held flag = team not posted) would end promotion everywhere and is out; flagged Questionables applied as out played 6/34. Today (A), a P49-held QB is dropped from the list while the team stays posted, so a held Questionable is promoted to 1.0. **B:** the team stays posted; a held player keeps his injury-report probability (not promoted); other unlisted Questionables are still promoted. **D:** a team-level 'list identical to last week' flag applies nothing on that list and promotes no one on that team. **Conditions:** (1) D competes only if its false-alarm rate on genuine lists, measured first (decision 1), is low, and the replay counts the cost of teams losing the promotion under D. (2) B replaces A only if B's Brier on held players' play probability against snaps is better than A's by more than noise; within noise, today's behaviour (A) stays. (3) QBs are reported on their own line; B changes P49's live QB path, so if the QB part is not supported on its own, QBs keep today's handling, and any live QB change waits for its own validation and a boundary.

**P68 decision 4 DECIDED (user, 10/7): ESPN injury-feed rows = C now (report only, NOT built until the user approves) + B as a replay candidate.** Evidence (read-only, weeks 2-4, served baseline charges vs final official report and snap counts): ESPN-only rows charged in served predictions: IR 39 (34.5 pts), out 52 (40.2 pts), questionable 2 (0.5 pts); **none of those players played**; the one known stale case (Porter Jr., 10/1) was cleared by the manual file before serving. 11 ESPN-only 'out' and 35 of 50 ESPN-only questionables did play but carried no served charge. Caveat: stored rows keep only the last pull (P57). **C:** each refresh lists ESPN-only `out` / `doubtful` rows for players not on the official report who played last week (snap counts). **B (replay candidate):** hold such a row; IR never held. **Conditions:** (1) C writes every flagged row to a persistent file with date, player, team, charge and the later snap outcome, so B's minimum can be counted. (2) **B needs >= 5 stale charged cases; it closes as not supported if fewer than 5 exist by the end of week 10.** (3) C is report-only: served outputs byte-identical with it on and off, and a failed save cannot stop a refresh.

**Raw roster storage, test isolation fix (10/7).** The first suite runs after the build wrote 24 fixture reads (fake game `g1`, and a P42 ATL @ GB fixture) into `data/inactives_raw/`, because existing tests call `fetch`. Removed (all 24 were test artifacts written at the two suite runs, 09:26Z and 09:31Z; no live read had happened). `tests/conftest.py` now points the raw logger at each test's temp folder (autouse); suite 275, nothing written under `data/`. Still open on decision 5: a check on the first live window (files and index rows match that window's reads), like P67's A4.

**P68 decision 6 DECIDED (user, 10/7): the replay, read-only, run now on weeks 2-3 + PIT @ CLE (all pregame-seen flags), re-run on weeks 5-6 (raw per-read lists) before any build.** Order: (i) false-alarm rate of the 'identical to last week' list flag on genuine lists; (ii) the four candidates per group (skill, OL, defense/ST; QBs on their own line), costed per decision 2; (iii) decision 3's B vs A Brier on held players' play probability, QBs separate; (iv) decision 4's count of stale charged ESPN-feed cases. R3 needs a prior-week list, so it exists from week 3 on. **Conditions, set before running:** (1) each group's false-flag count is a range: upper = every flag seen at any pregame read, lower = the flags on the latest stored read; **a candidate is selected only if it wins under both**. (2) **genuinely inactive = no snaps AND the post-game ESPN roster shows did-not-play**; no snaps but active on the post-game roster goes in a **third bucket** that counts for neither side, its size reported per group; played = any snap (nflverse). (3) **a guard ships only if the weeks 5-6 re-run picks the same rule for that group; a split keeps today's behaviour.** No builds.

**P68 decision 5 BUILT (user, 10/7): raw roster responses stored; logging only.** `src/inactives_raw.py`; called from
`ingest_inactives.fetch` right after each roster `_get`, before any parsing. Writes the HTTP status and the body as
received, with game, team, event, URL, read time, lead to kickoff and origin (live / replay), to
`data/inactives_raw/<season>_w<WW>/<game_id>/<team>_<stamp>.json` + `index.csv` (entries, flagged). Append-only;
`INACTIVES_RAW=0` turns it off; nothing reads it (a test pins that only the writer and its caller name it). Every
failure is caught inside `save()` and again at the call site, printed as one warning, never raised.
- **Identity, real data:** the 32 week-4 roster responses recorded once, then replayed through `fetch` with a pinned
  clock: storage on, off, and failing on every save (target path blocked) all give 247 rows and the same sha256 of
  rows + log (`b8ce4e6e...`). A first live comparison differed only in the printed log's hours-to-kickoff (wall clock,
  runs ~40 s apart); the 247 stored rows were identical field for field.
- `tests/test_inactives_raw.py` (5): identical on / off / failing inside / raising at the call site; the file equals
  the response (a 404 stored as null); append-only; off writes nothing; no reader. Suite 272 at this point.

**P62 rulings (user, 10/7), criteria otherwise unchanged:**
- **S2:** a game with no market on either source (no Odds API lines and no Sportradar event) is **excluded and
  reported, not a stop**; Odds API lines with no Sportradar event stay a stop. (Week 5 MIN @ NO, 10/7 08:13Z.)
- **S5:** a top-25 prop whose player did not play is **"not graded: did not play"**, not a failure. Implemented as: no
  snap row that week for that team in nflverse snap counts while the team-week is posted; if the snaps are not posted,
  it stays a failure. (Week 4 Noah Fant.)
- **Window extended through MNF 10/19:** `WINDOW_END` 2026-10-15T03:22Z -> **2026-10-20T12:00Z**.
- **S3 and S4 need >= 6 gameday pull pairs** before they can pass (**6 CONFIRMED by the user, 10/7**). A gameday pair = a shadow pull with a paired game kicking off within 3 h after it (a window refresh).
  Below the minimum a passing S3 / S4 reads `INSUFFICIENT (passing so far; k of 6 ...)`; a FAIL / STOP still shows at
  once. Weeks 5-6 offer ~10 window refreshes (TNF, Sun early, Sun late, SNF, MNF), if they run.
- Report on the saved pulls after the rulings: S1 PASS, S2 PASS (MIN @ NO excluded), **S3 / S4 INSUFFICIENT (0 of 6
  gameday pairs: both saved pulls are midweek)**, S5 PASS (Fant not graded: did not play). Tests: 3 new
  (`test_p62_compare.py`); the existing comparison tests run with the minimum at 1. Suite 275.
- **KEY1 budget through 10/19:** October so far **90 calls** (props product only: 45 P61, 32 shadow, 13 schedule),
  against the 950 switch point. Projected to 10/19 with every capture running: P61 <= ~240 (30 games x 8
  checkpoints) + ~25 schedule, shadow ~90 (two weeks of window + midweek pulls): **~450, about half the margin**;
  through 10/31 (week 7 P61) ~600. Within the approved ~825.

**Capture gaps 10/4-10/6 (read-only finding).** P33's probe and P61's capture ran on every pass while the laptop was
awake (143 starts / 143 exits) but it was down or asleep 10/3 08:31Z -> 10/4 20:46Z (London, early and late Sunday
windows) and 10/5 20:33Z -> 10/6 01:18Z (MNF kickoff). P33: 24 reads for DET @ CAR only, none for the other 14 games.
P61: 83 checkpoints missed, 41 saved, 4 Sportradar 500s; only SNF has pregame closes (t-15 errored). Cause on the
machine: the tasks have WakeToRun off (wake timers enabled on AC, disabled on battery), and **five blue screens since
9/17, all `0x50` in `nvlddmkm.sys` (NVIDIA driver 32.0.16.1742) at the same offset** (minidumps 9/17, 9/22, 10/4,
10/5, 10/6), plus one forced power-button shutdown 10/5. No settings changed.

---

## 2026-10-07 — P60 results: the NGS-informed prior makes receiving yards slightly worse, not better. Fails bars 1 and 2; closed

Run as specified in the entry below (written first) against the 9/30 bars. `research/p60/p60_ngs_arm.py`; output
`research/p60/p60_results.txt`. Nothing live touched. **Arm A reproduces the 9/19 run exactly** (weeks 11-18:
engine 260.5, A 257.2), so the comparison sits on the same harness. Mapping fitted on 88,023 profiled targets
(2018-2024); about 57% of scored receiver-games have a profile.

- **Choice on 2025 weeks 3-10:** every C was worse than arm A there (C 0.01 +0.54%, 0.1 +0.52%, 1.0 +0.52%);
  C = 0.1 taken as the least bad, per the rule.

| 2025 weeks 11-18, B vs A | n | rec yds MSE | weeks better | 95% CI (team-game bootstrap) | receptions |
|---|---|---|---|---|---|
| (1) all receivers | 1,961 | **+0.12% (worse)** | 3/8 | -0.29% to +0.54% | -0.43% |
| (2) profiled receivers | 1,173 | **+0.21% (worse)** | 4/8 | -0.30% to +0.74% | -0.61% |

- **Bars:** (1) FAIL, (2) FAIL, (3) receptions not worse: pass, (5) stop rule: the gain is below 1% (it is negative), so
  the test stops here. **(4)** priors of unprofiled receivers are identical by construction, but 0 of 788 unprofiled
  receivers' *predictions* are identical, because IPF couples every team-category cell and no judged team-game was
  without a profiled receiver. As noted before running, bar 4 cannot hold at output level under this design; it does
  not affect the verdict.
- **2026 weeks 1-4 (reported, not gated; mapping refitted on 2019-2025):** B vs A **+1.01% worse** (95% CI +0.36%
  to +1.70%, 0/4 weeks better); profiled receivers +1.26% (95% CI +0.42% to +2.15%).
- **Read:** an as-of NGS profile (separation, cushion, intended air yards, QB time to throw) carries no usable signal
  about a receiver's outcome mix beyond his position and his own shrunk history; on 2026 it hurts. **P60 closed** by
  its pre-set bars. Together with P17's recheck: player efficiency given targets is not where the props gap is.

---

## 2026-10-07 — P60 arm B specified (written before running; the bars are the 2026-09-30 ones in P60's row, unchanged)

The 9/30 criteria fix the bars and say arm B's prior is "informed by his as-of NGS profile, the mapping fitted on
earlier seasons only, every choice fixed on 2025 weeks 3-10". The mapping itself was not written down; this is it,
before any result exists.

- **Arm A:** P17's frozen design, the harness's own code (`p17_walkforward.py` functions, executed from source):
  k = 100, position prior, prior season at 0.5, IPF crediting, pre-week category shares. 2025 weeks 3-18.
- **Profile** (receiver, season s, week w): target-weighted means over his NGS weekly rows (regular season, week >= 1)
  from season s-1 and season s weeks < w, of avg separation, avg cushion, avg intended air yards, and his team's
  main passer's avg time to throw in those same games (the passing row with most attempts for that team-week). No
  rows = no profile.
- **Mapping:** per target category (red zone / deep / short), a multinomial logistic regression of the harness's
  outcome bin (incomplete, < 5, 5-9, 10-19, 20+) on position (WR / TE / RB) + the four standardised features, fitted on
  targets from the seven seasons before s (2018-2024 for 2025), each with its own as-of profile; profiled receivers only.
- **Arm B prior** for a profiled receiver: arm A's position prior multiplied bin-wise by P_map(bin | pos, his profile)
  / P_map(bin | pos, the position's mean profile), renormalised. So the NGS profile can only move a player off his
  position's mix; it never replaces the arm-A mix. Unprofiled receivers get arm A's prior exactly.
- **The only choice, fixed on 2025 weeks 3-10:** L2 strength C in {0.01, 0.1, 1.0}, lowest rec-yds MSE vs arm A.
  Nothing else is tuned; k, priors, weights stay frozen. Judged on weeks 11-18. 2026 weeks 1-4 reported (mapping
  refitted on 2019-2025, same C), not gated.
- **Bar 4 as it can be checked:** an unprofiled receiver's *prior* is byte-identical by construction; his
  *prediction* can still move, because IPF re-balances each team-category cell, so a profiled teammate's change
  shifts him too. Output-level identity is therefore checked on team-games with no profiled receiver. Reported
  both ways; if the user reads bar 4 as output-level for every unprofiled receiver, it fails by construction.
- Bars 1-3, 5 as logged: (1) yds MSE >= 1% better than arm A, better in >= 6 of 8 weeks, CI reported; (2) the same on
  profiled receivers alone; (3) receptions MSE not worse; (5) gain under 1% stops and is reported.

---

## 2026-10-07 — P17 recheck (2026 weeks 1-4, frozen 9/19 design): yards worse by 0.65%, better in 1 of 4 weeks. STILL CLOSED

Run against the criteria set with the user 2026-09-30 (P17 row), unchanged. `research/p17/p17_recheck_2026.py`
executes the harness's own `rates` / `ipf` / `predict` source from `p17_walkforward.py` with one edit, the
prior-season literal (2024 -> 2025, asserted to occur once); frozen k = 100, position prior, prior season at weight
0.5; each week sees only 2025 + earlier 2026 weeks. 1,034 receiver-games (253 / 255 / 266 / 260). Identity holds
(team totals, max error 6e-14). Output: `research/p17/p17_recheck_2026_results.txt`. Nothing live touched.

| arm | rec yds MSE | vs engine | weeks better | per week (1 / 2 / 3 / 4) | receptions MSE |
|---|---|---|---|---|---|
| current engine | 278.9 | | | | 0.731 |
| position prior only | 283.1 | +1.52% | 1/4 | -0.39 / +1.99 / +0.56 / +3.56% | 0.725 (-0.72%) |
| **frozen design** | **280.7** | **+0.65% (worse)** | **1/4** | -1.11 / +1.01 / +0.24 / +2.20% | 0.717 (-1.94%) |

- **Bootstrap (team-game, 1,000):** yards change +0.65%, **90% CI -1.48% to +2.89%; 95% CI -1.87% to +3.27%.**
  The interval spans both a ~1.5% gain and a ~3% loss; as stated up front, this sample cannot show a 1-3% effect
  either way. The point estimate is on the wrong side.
- **Decision rule (>= 1% better and better in >= 3 of 4 weeks): fails on both clauses. P17 STILL CLOSED.**
- Reported, not gated: receptions improve 1.94% (as in 2025, mostly position-level catch rate: the prior alone gives
  0.72%). Terciles (20+ prior targets, n 237 each), predicted/actual yards: engine bottom 1.014 / top 0.948; design
  0.994 / 0.966, both nearer 1.00. Given actual targets, 2026's compression is ~5% at the top, not the 0.918 / 1.106
  P30 measured on 9/29; that gap is consistent with P30's diagnosis lying outside efficiency-given-targets.

---

## 2026-10-07 — Week-4 QB holds and labels retired (IND @ WAS, NYJ @ CHI); display leak of old holds onto week 5 fixed

**How they were keyed (checked before removing).** `props.PROP_HOLDOUTS` is applied by (game_id, books' name,
market) (`props.rank`), `td_props.PLAYER_HOLDOUTS` by (game_id, books' name), `export_dashboard.KNOWN_GAME_ISSUES`
by game_id. So no hold could fire on a week-5 game. **But one display path was not game-scoped:** `props.run` wrote
every `PROP_HOLDOUTS` entry into `props.json`'s `structural_holdouts`, so the week-5 props page listed the week-4
WAS and CHI notes (including "WAS's starting QB is unresolved until the official week-4 report posts", with WAS
playing in week 5). Now filtered to the games in the ranked lines; `tests/test_holdout_scope.py` pins every key to
one game id and checks no week-4 entry remains. Suite 263 before, 267 after.

**Finished game pages.** A past game's page is built from the week archive (`data/sims_archive/2026_w04.json`), which
never carried `known_issue`; the label only ever reached the page through `data.json`'s current slate. So no stored
copy exists to keep, and the week-4 labels were not shown on finished pages before or after this change. (The
week-3 `2026_03_ATL_GB` entry is in the same position: in the table, never served for a finished game; left as is.)

**The record of what was held and why (as served, verbatim):**
- **IND @ WAS** (labelled 9/30): props pass + rush yds for Marcus Mariota and Jayden Daniels, TD picks for both:
  "Held out: WAS's starting QB is unresolved until the official week-4 report posts (the simulation starts Daniels in
  ~55% of games; the books price Mariota)." The game label set out the 55% Daniels split, his 2.09-pt questionable
  charge vs 4.65 as out, and that the lines, sim and WAS passing all rested on it. Outcome: Mariota started and was
  replaced in-game by Kaliakmanis (P35-type).
- **NYJ @ CHI** (labelled 10/1): Case Keenum pass + rush yds and TD ("CHI's starting QB is unresolved (the simulation
  starts Keenum; the books price Bagent)"); Tyson Bagent pass + rush yds and TD ("Held out as unreliable: the
  simulation gives any CHI starter the same team-level passing, so a Bagent line measures the missing
  quarterback-quality term, not the player. Stays held even if the inactive list confirms him."). The game label set
  out the forced-Bagent run (same volume as Keenum, ~1/3 pt). Outcome: Bagent started (268 pass yds).

**Re-rank:** same lines and sims. The first re-rank was run with `--no-explain` by mistake and was served for ~16 s
without the props explanations (P67 archive `20261007T090959Z`); re-ranked with explanations at
`20261007T091015Z`. Both rankings are identical to `090307Z` in every rank, pick, line and probability, and in the
held-out set; only `structural_holdouts` changed (week-5 entries only). Nothing else re-exported: week-4 games are
not on the current slate.

---

## 2026-10-07 — P5 live follow-up (information only): served weeks 1-4 lean slope negative, not significant; P5 stays closed

The queued check from the 2026-09-30 P5 entry: P37's lean slope (`lean_slope` / `perm_p` from
`research/p22/p22_phase1.py`, verbatim; seed 37, 10,000 permutations) on the **62 served 2026 weeks 1-4 baseline
edges**, as stored (edge = served margin + line; residual = actual margin + stored line). These are **old-rating
edges**: every one was served before P22 shipped today, so this is not a test of the rating P5's replay judged.

- **Baseline: lean slope -0.661, permutation p 0.200.** Negative (bigger served edges did worse), not significant.
  Per week, no test: wk1 +0.23, wk2 -0.86, wk3 -2.96, wk4 +0.51.

| abs edge (served) | n | ATS | model MAE | line MAE | model - line |
|---|---|---|---|---|---|
| < 3 | 25 | 12-13-0 (48%) | 9.28 | 9.00 | +0.28 |
| 3 to < 6 | 18 | 7-11-0 (39%) | 13.31 | 12.22 | +1.09 |
| >= 6 | 19 | 7-10-2 (41%) | 11.99 | 7.92 | +4.07 |
| all | 62 | 26-34-2 (43%) | 11.28 | 9.60 | +1.67 |

- ML for reference (not part of P5): slope +0.655, p 0.362.
- **Read:** unlike the replay (+0.044, large edges 30-19), the live large edges lost and sat 4.07 pts further from
  the result than the line, the stale-rating signature P5 was opened on. 62 games cannot separate that from noise
  (p 0.20), and P22 has since cut exactly those edges (week 5: mean abs edge 4.46 -> 3.49). **No action, P5 stays
  closed**; the pre-set reopen rule (a full season of served edges, negative slope at p < 0.05) is unchanged and
  now runs on P22-rating edges from week 5.

---

## 2026-10-07 — P22 + P51 SHIPPED (P22's ten-step sequence). Criteria 1, 2, 6 pass; TB and BAL QB props held; dashboard exported

Run in the order on P22's row. Odds API quota checked before the week-5 pull (free `/sports` call): **410** remaining
(90 used); after the odds, props and TD pulls, **352**.

- **(2) Snapshot** `data/snapshots/pre-p22-p51_2026-10-07/`: served JSON (`data/` + `dashboard/public/`, also a copy
  from before week 4's `export_sims`), 2026 `team_ratings`, ML file md5s, main HEAD, and a hash of every stored week-4
  row (`wk4_fingerprint_before.json`).
- **(3) 'Before' pass on main (old rating):** `run_pipeline --sport nfl --model both --date 2026-10-08 2026-10-11
  2026-10-12 --fresh-odds` (one odds pull, 29 events), then `simulate_nfl` on the same dates `--upcoming-only`. 15 games;
  baseline mean |model - line| 4.46; one baseline flag (LV @ NE). Recorded in `before_wk5.json`.
- **(4) Merged `p22-rating` (7047cee).** Not clean, against the row's expectation: `src/game_explain.py` conflicted
  with main's close-game rule (e933f2f, 10/1). Resolved by keeping both: P22's rating sentence ("describe how it is
  built only as a caveat does") and main's close-game paragraph, both unchanged in wording. Suite 259 passed.
  Criterion 6 (files): `build_training.py`, `training_nfl.csv`, `nfl_margin.json` / `.meta.json` md5-identical. (The
  phase-1 snapshot recorded no hashes; these files were last written 9/22, before phase 1, and are compared to today's
  pre-ship md5s.)
- **(5) Merged `p51-priced-qb` (c2c18dc)**, clean. Suite 262.
- **(6) Ratings rebuilt** (`ingest_nflverse`, flag on). Recomputing in memory with the flag off reproduces the
  pre-ship stored week-5 ratings exactly (max diff 0.000).
- **(7) Re-predicted week 5, both models, same odds** (`--skip-ingest`). **(8)** props lines pull (15/15 games, 100
  players) -> simulate -> props rank (187 priced, top 25; P67 archive `2026_w05/20261007T081609Z`) -> TD pull and rank
  (418 players priced, 271 ranked) -> `export_sims`. QB scenarios (P66) were not run; they are not in the sequence.

**(9) Checks** (`ship_checks.json` in the snapshot; all in memory).

| # | check | result | verdict |
|---|---|---|---|
| 1 | served baseline before -> after, same odds | mean abs(model - line) **4.46 -> 3.49** (15 games); 6 games move > 3 pts, 5 toward the line | **pass** |
| 2 | sim median totals vs the proxy, per-game clause | 12 games with proxy move >= 1: **10 same direction (83%)**; 9/11 without the P51 game | **pass** |
| 3 | props raw P(over) shift, week-5 slate (information) | non-P51 games: pass yds +0.92 pp (n 20), rec yds -0.65 (58), receptions -0.32 (58), RB rush +0.44 (24), QB rush -0.06 (13). P51 game (CHI @ GB) alone: pass yds -3.59 (n 2), rec yds -1.86 (6), receptions -0.83 (6) | no category with n >= 20 over 1.0 pp; refit decision after week 5 is graded, as ruled |
| 6 | ML untouched | files md5-identical; ML week-5 predictions before vs after max diff **0.0** | **pass** |
| 7 | ATS-information test on week-5 edges (reported, not gated) | **not computable yet**: it needs results (cover residuals). Runs once week 5 is graded | pending |

Criterion 1, games moving > 3 pts (home margin before -> after; parts in points, home minus away):
HOU @ TEN -13.59 -> -4.30 (def carry +4.59, off carry +1.92, off adjust +1.97); LV @ NE +15.35 -> +7.48 (off carry
-4.36, def carry -2.06; **the 'before' flag is gone**); DET @ ARI -5.33 -> -0.25 (off adjust +2.33, def carry +1.75; line ARI +5.5, so this one moves *away* from the line,
abs edge 0.17 -> 5.25: the model now has ARI close, the market DET by 5.5);
CLE @ NYJ -3.83 -> +0.17 (def carry +4.27; abs edge 5.83 -> 1.83); PHI @ JAX +11.84 -> +8.34; SF @ SEA +8.76 -> +5.43. After the merge: **no baseline flags** on week 5.

**Correction to the 9/30 phase-2 criterion-3 numbers.** The phase-2 check script (and my first run today) read
`props.rank`'s output under `props` / `more`, keys that only exist in the served file; `rank` returns `ranked`. So the
9/30 figures (n 16 / 8 / 4 / 1 / 1) were held-out props only. Today's numbers above use `ranked` + `held_out`
(187 props, before and after). The ruling (re-measure on week 5, refit only n >= 20 and > 1.0 pp) is unaffected.

**P51 firing list:** one case. CHI @ GB: depth QB1 Caleb Williams ruled out (ESPN `out`); the books price only Tyson
Bagent, promoted to QB1.

**QB sweep: two mismatches, neither a P51 case** (QB1 not ruled out, so the rule correctly does not fire):
- **TB @ DAL (TNF):** sim QB1 Baker Mayfield (no week-5 status; nflverse row carries no status, play prob 0.6); the
  books price only Jalon Daniels (TB QB2).
- **BAL @ ATL:** sim QB1 Lamar Jackson (ESPN questionable, 0.55); the books price only Tyler Huntley (depth QB3;
  Cooper Rush is QB2). Jackson left week 4 early (Huntley threw 63 yds).
- The served top 25 carries both books-priced QBs at sim median 0: **Huntley pass yds under 174.5 (rank 11)** and
  **Jalon Daniels pass yds under 181.5 (rank 18)**, the P28 'priced backup at median 0' signature. `props.run`
  writes `dashboard/public/props.json` directly, so these rows are on the local props page now. Not held: the user decides
  (the 9/30 IND @ WAS precedent: label + holdouts).

**Week 4 untouched.** Nothing in the sequence re-predicted, re-simulated or rewrote a week-4 prediction, sim, odds
snapshot, CLV row, injury, inactive or rating row (hashes identical, before vs after), and `2026_w04.json` is
byte-identical. Three tables show re-stamped week-4 rows, content unchanged: `games` (`pulled_at` from the nflverse
ingest; scores match the graded rows), `odds` (the 16 `nflverse_close` rows, rewritten by the same ingest), `weather`
(4 dome games re-pulled by the weather ingest: every value null both times, only `pulled_at` changed).

**User ruling (10/7), before the export:** hold TB's and BAL's QB props and TD picks, and label both games in the
IND @ WAS / NYJ @ CHI form; each label says the hold comes off once the official report confirms the starter.
`props.PROP_HOLDOUTS` (pass + rush yds: Mayfield, Jalon Daniels, Jackson, Huntley), `td_props.PLAYER_HOLDOUTS` (same
four), `export_dashboard.KNOWN_GAME_ISSUES["2026_05_TB_DAL" / "2026_05_BAL_ATL"]`. Re-ranked on the same lines and
sims (no pulls): props 187 priced, Huntley pass yds and Jalon Daniels pass + rush yds now held (P67 archive
`2026_w05/20261007T090307Z`); TD 6 held (was 4). Remove all of these once each official report confirms the starter.

**(10) Exported** (`export_dashboard`, with explanations: 15 game notes, ~$0.11; props explanations ~$0.08 per ranking,
two rankings today). **Checked after the export:** the Record page JSON's weeks 1-3 (NFL) and the college week are
byte-identical to before (bar the new `note` field, null on them); week 4 is new with exactly the graded numbers
(baseline SU 11/16, ATS 7-8-1, flagged 1-0; ML SU 11/16, ATS 10-5-1) and its note; the week-4 fingerprint is unchanged;
the props archive index's four week-4 rows are byte-identical (two week-5 rows appended). Nothing outside week 5 changed.

**Served week 5 (new rating, same odds as the 'before' pass; home margin, + = home):**

| Game | Line | Baseline (before) | Baseline | ML | Sim median (away-home) |
|---|---|---|---|---|---|
| TB @ DAL (TNF) | DAL -8.5 | +1.44 | +1.62 | +1.73 | 23-24 |
| PHI @ JAX (13:30Z) | JAX -7.5 | +11.84 | +8.34 | +3.40 | 17-26 |
| CHI @ GB | GB +3 | +1.63 | +2.57 | +3.32 | 21-24 |
| CIN @ MIA | MIA +7 | -0.77 | +0.85 | -1.40 | 23-23 |
| CLE @ NYJ | NYJ -2 | -3.83 | +0.17 | -0.47 | 20-20 |
| HOU @ TEN | TEN +7.5 | -13.59 | -4.30 | -5.56 | 23-19 |
| IND @ PIT | PIT -2.5 | -0.04 | +1.27 | +3.58 | 23-24 |
| LV @ NE | NE -3.5 | +15.35 (flag) | +7.48 | +8.03 | 17-24 |
| MIN @ NO | NO +2 | -0.99 | +0.99 | -5.25 | 20-20 |
| NYG @ WAS | WAS -3.5 | -4.24 | -2.76 | -0.61 | 23-20 |
| DEN @ LAC | LAC +3.5 | -4.73 | -3.22 | -3.96 | 23-19 |
| DET @ ARI | ARI +5.5 | -5.33 | -0.25 | -4.60 | 23-23 |
| SF @ SEA | SEA -3 | +8.76 | +5.43 | +3.67 | 20-26 |
| BAL @ ATL (SNF) | ATL -3.5 | +4.16 | +5.87 | -1.38 | 17-24 |
| BUF @ LA (MNF) | LA -3 | +4.72 | +4.42 | -5.80 | 22-27 |

Baseline mean abs(model - line) 3.49 (was 4.46); no baseline flag (was LV @ NE); ML never flags. These are Wednesday
numbers: week-5 official reports and inactive lists are still to come, so the window refreshes will move them.

---

## 2026-10-07 — Week 4 graded and archived (16/16). No Sunday or Monday window refresh: 15 games graded on the 10/1 predictions

**Week 4 is marked (user, 10/7), on the Record page and here: predicted 3–5 days before kickoff, before designations and
inactive lists, except PIT @ CLE.** No number changes.

**What was served (user, 10/7):** the Sunday and Monday window refreshes were not run, so the stored predictions are
the ones served and are graded as they stand. No finished game was re-predicted or re-simulated.

**Stored-state audit (before grading, read-only).** 16 games; one baseline and one ML row each; every row predates kickoff.
- **PIT @ CLE (TNF):** predictions 10/1 23:05-23:06Z, sim 23:06Z, T-1.1h (the TNF window refresh).
- **The other 15 (Sun + Mon): no final-window refresh.** Predictions from 10/1 03:30-03:32Z (ATL @ NO ML 03:52Z), sims
  03:41-03:44Z: 82h (IND @ WAS, 13:30Z kickoff) to 117h (ATL @ NO) before kickoff. They carry the 10/1 03:30Z lines and
  injury data (before Thursday/Friday designations, no inactive lists). The 23:05Z TNF refresh re-pulled odds and
  injuries for every team but re-predicted only PIT @ CLE.
- **Written after kickoff:** only `live_tracking` (82) and `live_simulations` (81) rows for PIT @ CLE (the live
  tracker). Grading reads neither. No odds, snapshot, inactives, weather, prediction or sim row is post-kickoff.
- **Unusable: none.** Two served games carried a QB label: IND @ WAS (books priced Mariota; Mariota started and was
  replaced in-game by Kaliakmanis, a P35-type case) and NYJ @ CHI (sim QB Keenum; Bagent started, as the books priced).
  Both are graded as served.

**Graded** (`grade --sport nfl --refresh --since 2026-10-01`, then `export_sims` -> `data/sims_archive/2026_w04.json`:
16/16 with actual result and both pregame predictions). Independent recount from the predictions table matches.
CLV closes: all 32 from ESPN/DraftKings (no stale-snapshot fallback).

| Model | Straight up | ATS | Flagged | MAE (line 7.47) |
|---|---|---|---|---|
| baseline-v1 | 11/16 | 7-8-1 | 1-0 (JAX @ CIN, JAX) | 7.73 |
| ml-v1 | 11/16 | 10-5-1 | none flagged | 6.90 |

Push: LAC @ SEA (SEA -7, won by 7). Season to date (62 graded per model): baseline SU 35/62, ATS 26-34-2, flagged 4-10;
ML SU 41/62, ATS 25-35-2, never flagged. 30 graded ATS results this week: noise, as always.

**P67 week 4 (ad hoc, by the B1/B2 rules; phase B's record builder is still not built).** Every game's last pregame list is
the 10/1 23:06:58Z live ranking (commit 9590d0c); it ranked all 16 games. Sun/Mon rows were priced on the 10/1 03:44Z
lines pull (only PIT @ CLE's lines were refreshed at 23:06Z). Top 25: 25 rows, **11-12-0** (47.8%, avg break-even
0.527), 2 not graded. Top 50: 50 rows, **28-19-0** (59.6%, break-even 0.523), 3 not graded. Top 25 by category:
pass yds 0-3, rush yds 2-1, rec yds 3-5, receptions 6-3; over 3-1, under 8-11. Not graded (B2 check: did not play, not
name failures): Noah Fant (NO TE2, ranks 14 and 24; no 2026 snap row in any week) and Jadarian Price (SEA RB1, rank 26;
no week-4 snap row). Fant being priced and ranked with no snaps all season is a P68/P31-type observation; nothing changed.

---

## 2026-10-01 — PIT @ CLE injury-layer sensitivity (informational, for P48; nothing changed)

Served baseline (23:05Z): **PIT by 3.2** (-3.16 home). Ratings -1.92 + home field +1.90 + travel +0.05 + rest 0 =
+0.03 before injuries; injuries CLE -4.72, PIT -1.52, net **-3.20**, so the lean is entirely the injury layer. Market
PIT -2.5; ML PIT by 1.4; the 03:41Z sim had CLE by 1.0 (home WP 0.505), tonight's 0.40. The earlier *baseline* number
was not stored (one prediction row per game), so "before" below is rebuilt with today's code and ratings.

Per player, as served (weight x share x (1 - play prob) x 6): **CLE** Green QB 2.10 (default share), E. Jenkins C 1.50,
Jefferson LB 0.42 (default share), T. Jenkins G 0.38 (2025 share), Wallace WR 0.32. **PIT** Ramsey CB 0.76 (Q), Dowdle
RB 0.45, Black DE 0.25 (Q), Echols CB 0.06 (Q).

| Scenario (same `score_injuries`) | CLE | PIT | Net | Margin |
|---|---|---|---|---|
| Feeds only, before tonight's manual file / skip (Porter Jr.'s stale ESPN out live) | -3.31 | -2.28 | -1.03 | PIT 1.0 |
| Stale ESPN lists applied (no skip) | -6.19 | -3.22 | -2.97 | PIT 2.9 |
| **Served** | -4.72 | -1.52 | -3.20 | **PIT 3.2** |
| Served minus Green and Jefferson | -2.20 | -1.52 | -0.68 | PIT 0.7 |
| Served, Ramsey / Echols / Black active (as the real lists say) | -4.72 | -0.45 | -4.27 | PIT 4.2 |
| **Both: phantom charges removed and the three Questionables active** | -2.20 | -0.45 | -1.75 | **PIT ~1.7** |

**SUPERSEDED 2026-10-07 (see the 10/7 correction entry): three of the four flags this entry treated as stale were genuine absences by snap counts; the corrected re-run gives CLE by 2.1 (CLE by 1.1 with PIT's Questionables promoted).** Read: removing the two zero-snap charges and counting PIT's three Questionables as active per the real lists moves the
baseline from PIT by 3.2 to roughly **PIT by 1.7**, much closer to the market's 2.5. The skip itself moved the
margin little (2.9 -> 3.2: Campbell 1.47 against Porter Jr. 1.59 + Anderson 1.18 largely offset); the manual file's
certain Outs and the removal of Porter Jr.'s stale Out account for most of the 1.0 -> 3.2 move. Real-football notes:
CLE losing two interior OL (starting C + a G) is charged additively (1.88) with no term for a line missing two starters
together, so that part may be under-weighted, but nothing measured supports a number; Teven Jenkins and Dowdle were
already out last week, so their charges partly double-count recent form (the offset P48 notes).

**Informational only, for P48's eventual fix (evidence for its step 3: a player with zero current snaps behind a
healthy starter should carry ~0).** Not acted on: the served edge is -0.66 pts / -2.4 pp vs break-even, no value flag
either way, and the ~1.7 is a sensitivity rerun, not a validated number. See P48's row (Green / Jefferson).

---

## 2026-10-01 — TNF PIT @ CLE: ESPN's inactive lists were last week's; skipped for the game (user ruling)

**CORRECTED 2026-10-07:** by nflverse snap counts, Joey Porter Jr., Spencer Anderson and Parker Brailsford took no snaps in week 4 (genuine absences); only Tyson Campbell played (71 defensive snaps). The PIT clearing relied on a projection and an aggregator list (the 'second source'), not an official Steelers inactive list. See the 2026-10-07 correction entry.

**Found** at the 22:54Z ingest (T-80m) while checking the week-4 manual file: ESPN flagged CLE CB Tyson Campbell inactive,
while the official report had him FP with no status. User asked for a diagnosis before any change.

- **Read:** `sports.core.api.espn.com/.../events/401872964/competitions/401872964/competitors/5/roster`; raw responses
  are not stored by `ingest_inactives` (only parsed rows). Re-pulled 22:59:18Z: still `didNotPlay: true`.
- **Carry-over:** CLE week 4 = all 5 of its week-3 inactives (Brailsford, Campbell, Green, Jefferson, T. Jenkins) + E.
  Jenkins, Wallace; Campbell's entry byte-identical to week 3's. PIT week 4 = its week-3 list exactly (8/8). Campbell's
  week-3 flag was real (no stat line in CAR @ CLE).
- **Independent sources:** Browns' official inactives article (Oct 1, 6:45 PM ET): Green, Wallace, Jefferson, E. Jenkins,
  T. Jenkins. PIT per the user's second source: Allar, Howard, Heidenreich, Dowdle, Rubio, Jobity. ESPN's extras
  (Campbell, Brailsford, Porter Jr., Anderson) are exactly the week-3 carry-overs.
- **Ruling (user): option (c).** `config.INACTIVES_SKIP_GAMES = {"2026_04_PIT_CLE"}`: `apply_inactives` and the P66
  'list posted' check ignore the game's rows (still stored as evidence); both teams use the injury report incl. the
  manual file. A stale ESPN injury-feed `out` row for Porter Jr. (0.946 snaps) was also live; at the user's choice he was
  added to the manual file with no status (cleared). Manual file fix: Delpit `SAF` -> `S` (validator).
- **Served (refresh 23:07Z):** charged for the game: CLE E. Jenkins, T. Jenkins, Wallace (manual), Jefferson, Green
  (ESPN feed) out; PIT Dowdle out; Ramsey, Echols, Black 0.55. Not charged: Campbell, Brailsford, Porter Jr., Anderson.
  Baseline 3.2 / ML 1.4 vs market 2.5. **Cost of (c):** without a posted list, Ramsey / Echols / Black stay at 0.55
  though active. The archive row for this ranking records commit 9590d0c; the skip was uncommitted at run time.
- **P62 shadow failed** (Sportradar 500 on the schedule call); the P67 archive kept the TNF ranking (A4 PASS, bytes equal).
- **Follow-up: P68** (non-QB inactive scrutiny), proposed the same night; queued for the post-10/5 batch, scoping first, nothing built.

---

## 2026-10-01 — P67 scoped: weekly props record from an archive of every served ranking (nothing built)

**Why.** The served props list has never been graded as a list. The 9/21 and 9/29 props grading (P31) graded every
priced prop, rebuilt from saved lines, which says nothing about the top of the ranking the page actually shows.

**What survives (checked 2026-10-01, read-only).** Only `props.run` writes `props.json`, and it overwrites it at every
ranking. Saved copies:

| Week | Saved | In the record? |
|---|---|---|
| 1 | nothing: the ranking was added 9/15 (99128c6), after week 1 was played | no; no list ever existed |
| 2 | `data/snapshots/pre-2A_2026-09-18/` (list 06:15Z 9/18, TNF still ranked after kickoff, pre-dates the `started` filter) and `pre-friday_2026-09-18/` (list 21:41Z 9/18, TNF under `started`); both on lines pulled 9/17 23:00Z | no; the Sat/Sun lists that followed the 9/18-9/19 engine changes (2A, k32, PENALTY_REPLAY) were overwritten. Friday list = footnote only |
| 3 | `pre-sunday_2026-09-27/props.json` is the TNF list (generated 00:09Z 9/25, ATL @ GB kicked off 00:15Z; 4 of its top 25); `wk3-props_2026-09-28/props_lines.json` has the last pregame lines of the other 15 games, but its `props.json` was regenerated after the games (411 `started`) | no; TNF = footnote only. Sun/Mon prices could be rebuilt from lines + stored pregame sims, ranks cannot: each window's list also ranked later games on sims since re-run, so a rebuilt top 25 is a list nobody was shown |
| 4 | P62 shadow `data/props_sr/pulls/*/rank_*/props.json`: the served payload at each paired ranking since 10/1 03:47Z | yes, the first week; phase A removes the dependence on Sportradar pairing |

**User decisions (2026-10-01).** (1) The record starts at week 4, with no backfill into it. Week 2's Friday list and
week 3's TNF game appear only in a separate footnote labelled **pre-record / reconstructed**, explicitly not part of
the graded track record and never in any total. (2) Each game is graded from **its own last list served before its
kickoff**, the same rule as P62 S5; the actual row count per week is reported beside the top-25 / top-50 numbers,
since Thursday, Sunday and Monday games come from different lists and a week can exceed 25 / 50 rows. (3) Phase A,
the archive, is built before Sunday 10/4's early window (17:00Z), so week 4's record does not depend on the shadow.

**Phase A: archive of every served ranking (build now).**
- **A1 complete.** Every `props.run` that writes `props.json` also writes one archive file
  `data/props_archive/<season>_w<WW>/<generated_at stamp>.json` holding the **exact bytes** written to `props.json`,
  and appends one row to `data/props_archive/index.csv`: stamp, week, generated_at, lines_pulled_at, git commit,
  line source (`odds_api`), sha256 of the served file and of the `props_lines.json` it ranked, top / more / held /
  started counts, and an origin tag (`live`). The ranked lines file is kept once per distinct sha
  (`lines/<sha12>.json`).
- **A2 isolated.** Served outputs (`props.json`, `dashboard/public/props.json`) are byte-identical with the archive on
  or failing; an archive error prints a warning and the ranking completes. The archive runs after the served file is
  written. Unit tests for both.
- **A3 append-only.** No archive file is overwritten; a stamp collision gets a suffix. Nothing reads the archive except
  the record builder.
- **A4 live.** Before 17:00Z Sunday 10/4, a real ranking has produced an archive file whose bytes equal
  `data/props.json` at that moment, with a correct index row. Reported.
- **A5 seed.** The three week-4 P62 rankings already saved (10/1 03:47Z, 04:14Z, 07:34Z) are copied in with origin
  `p62_shadow`, after a check that each equals what was served (the shadow wrote it through `json.dumps(..., default=str)`;
  any byte difference is reported, not normalised away). Suite passes.
- `data/` is gitignored: the archive is local and OneDrive-backed, like the P58 archive, not committed.

**Phase A built 2026-10-01** (`src/props_archive.py`; `props.run` calls `archive()` right after `props.json` and its
public copy are written, inside its own try/except; `tests/test_props_archive.py`, 20 checks; suite 255 passed).
- A1 PASS (tests): archive file = the bytes on disk in `props.json`; index row with week, generated_at, lines_pulled_at,
  git commit, `odds_api`, both sha256s, counts, origin; lines kept once per sha.
- A2 PASS (tests): `props.run` with the archive raising still writes `props.json` and an identical public copy, prints
  `[warn] P67: ranking NOT archived`, and serves the same content as with the archive working (compared bar
  `generated_at`, which is the clock).
- A3 PASS (tests): a stamp collision gets `_2`; the first file is untouched.
- A5 PASS (live): the three week-4 shadow rankings (10/1 03:47:05Z, 04:14:10Z, 07:34:53Z) seeded with origin
  `p62_shadow`, git commit `unknown (seeded)`; **all three re-serialise byte-identically**, and the newest equals the
  served `data/props.json` byte for byte. Their lines are the pull's `odds.json` (byte-identical to what was ranked,
  by the shadow's own match rule).
- **A4 pending:** no real ranking has run since the hook went in. Not forced: a re-rank now would replace the served
  list (and call the explanations API) without a reason. The Thursday TNF refresh is the first live test; checked
  with `python -m src.props_archive --status` and a byte compare against `data/props.json`, before 17:00Z 10/4.

**Phase B: the record (criteria set now; build after phase A; first run once week 4's TNF is final, full week after
MNF 10/5).**
- **B1 list rule.** Per game: the archived list with the latest `generated_at` before kickoff that ranks the game. Its
  rows for that game with rank <= 25 form the top-25 set, rank <= 50 the top-50 set (ranks as served, from `props` and
  `more`). Held-out and started rows are never graded. A game with no archived pregame list is reported as **no list**,
  never filled from another source.
- **B2 grading.** `p62_compare.grade`'s matching and W / L / push (actual vs line on the picked side). Hit rate =
  W / (W + L); pushes shown, not in the rate. A row with no box-score line is not graded and is listed by name (did
  not play, or a name failure: each is checked; a name failure is a defect to fix, then the week is re-graded).
- **B3 output per week and season-to-date.** Rows graded (the real count) and games covered; top 25 and top 50 each
  with W-L-push and hit rate, overall and by category: passing (pass yds), rushing (rush yds), receiving (rec yds),
  receptions; over / under split reported. Written to `calibration/props_record.md` (+ machine-readable JSON),
  regenerated from the archive, so a re-run gives the same numbers.
- **B4 markers.** Each graded row carries its list's generated_at, git commit, line source and bias-fit date. Known
  boundaries are shown as splits in the season-to-date, not blended silently: the P22/P51 merge (after MNF 10/5,
  week 5 on), any props refit, and any line-source switch (P62 S5c's record-marking gate).
- **B5 actuals.** ESPN final box scores (cached finals); nflverse weekly stats as the fallback; the source per game
  recorded. A game that is not final is reported as pending, not graded.
- **B6 footnote.** Week 2 Friday list (`pre-friday_2026-09-18/props.json`, Sunday/Monday games; TNF excluded as
  started) and week 3 TNF (`pre-sunday_2026-09-27/props.json`, ATL @ GB rows only), graded by the same code in a
  separate section headed **pre-record / reconstructed, not counted**, each with why it is not the record (week 2:
  not the last pregame list, two engine changes and two days stale; week 3: one game).
- **B7 no claims.** Hit rates are reported with the average break-even of the prices taken, for context only; no
  "validated" or "profitable" wording; anything shown on the dashboard later carries `UNVALIDATED_TEXT`. A
  dashboard view is not in scope until the user decides.
- **B8 tests.** List rule (latest pregame list wins; post-kickoff lists ignored; no-list games reported), grading
  (W / L / push, pushes outside the rate, no-box-line rows listed), category split, footnote never in totals; suite
  passes.

---

## 2026-10-01 — P66 built: QB scenarios; all criteria pass; panel awaiting the user's review

`src/scenarios.py` (on demand: `python -m src.scenarios [--game ID] [--publish]`), `dashboard/src/ScenarioPanel.jsx`
(on the game page under the known-issue box), `data/scenarios.json` + `dashboard/public/scenarios.json`,
`tests/test_scenarios.py` (14 checks). The store is wrapped read-only (writes raise). Scenarios run at the served sim's
count (10,000), so the control can reproduce it and differences from it aren't sampling noise.

**Week 4 candidates (found from existing signals, nothing hand-picked):** IND @ WAS (Daniels questionable; books price
Mariota), NYJ @ CHI (Williams doubtful; sim Keenum; books Bagent), TEN @ BAL (Lamar Jackson questionable, from the
report; no known-issue label on this game).

| Game | Scenario | Baseline | Home win | Sim QB (att, yds) |
|---|---|---|---|---|
| IND @ WAS | as served | IND by 11.3 | 17% | Daniels/Mariota mix 23, 137 |
| | Daniels plays | IND by 9.2 | 23% | Daniels 30, 207 |
| | Daniels out (Mariota, the books' QB) | IND by 12.3 (cap binds) | 15% | Mariota 32, 214 (props unreliable) |
| NYJ @ CHI | as served | CHI by 11.6 | 83% | Keenum 30, 234 |
| | Williams plays | CHI by 15.9 | 90% | Williams 29, 245 |
| | Williams out (Keenum) | CHI by 11.6 (cap binds) | 82% | Keenum 31, 243 |
| | Bagent starts (the books' QB) | CHI by 11.6 (cap binds) | 83% | Bagent 30, 235 (props unreliable) |
| TEN @ BAL | as served | BAL by 10.5 | 81% | Jackson 21, 140 |
| | Jackson plays | BAL by 13.2 | 86% | Jackson 28, 217 |
| | Jackson out (Huntley) | BAL by 9.5 (cap binds) | 78% | Huntley 28, 208 |

"Cap binds": the team's injury charge is already at the 8-point cap (`INJURY_MAX_POINTS`), so ruling the QB out moves
the margin little or not at all (CHI: Williams 5.02 -> 5.58 pts, total 8.78 -> 9.34, both capped at 8.0). Not a bug;
the panel tags it so a flat row doesn't read as an error.

**Criteria (confirmed 2026-10-01), all pass:**
- **C1 control reproduces the served sim:** IND @ WAS, NYJ @ CHI, TEN @ BAL all True at 10,000 sims. The first
  validation run reported False for all three; the field-by-field diff showed only stamps (`generated_at`, the anchor's
  label, `td_scorers.depth_chart_as_of`, a file timestamp) and number formatting (the store returns 20 where a fresh run
  has 20.0). The comparison now normalises those and compares every produced value; a test pins that a produced value
  differing still fails.
- **C2 margin == baseline re-run by hand** (served components with only that team's charge recomputed through
  `score_injuries`): 7/7 scenarios within 0.01.
- **C3 served outputs unchanged:** the served data and dashboard files byte-identical; `predictions`,
  `game_simulations`, `injuries` rows unchanged (counts and hashes).
- **C4** caveat on every game; backup-QB props (Mariota, Bagent) marked unreliable.
- **C5** suite 247 passed.

**Not done, by design:** not wired into `run_sunday` (on demand until the user approves the panel); scenarios are
published only by `--publish`. The published week-4 file was generated 07:50Z and retires per game when its inactive
list posts or at kickoff.

**Approved and wired in, 2026-10-01 (user).** Panel approved as final (`b42a408`; `dashboard/public/scenarios.json`
gitignored like the other generated dashboard files). `run_sunday` now runs a non-critical "QB scenarios" step after
the props ranking for the window's games that qualify. Publishing **merges**: games computed in the window replace their
entry, a game that no longer qualifies is removed, other windows' games are kept, kicked-off games are dropped.
**Retirement is per team:** a team whose inactive list has posted gets no scenarios, unless P49 held a QB flag on that
list as unresolved (the list may be wrong). Note on timing: `run_sunday` refreshes each window at ~T-75, usually after
the lists post, so in a normal window the step mostly retires that window's scenarios; they are produced by refreshes
made before the lists post. One-line summary per run; a control that fails to reproduce the served sim is printed.
Live check (TNF window, PIT @ CLE): 1 game checked, none qualifies, the other three games' entries untouched. Tests
16 (merge/retire added); suite 248.

---

## 2026-10-01 — P66 scoped: QB scenarios for games with an unresolved starter (nothing built)

**What it is.** A read-only, repeatable version of the 10/1 NYJ @ CHI scratch run: for a game flagged with an unresolved
starting QB, compute the prediction under each realistic starter and show them beside the served number, labelled as
comparison data. Never written to `predictions` / `game_simulations`, never read by the ranking, props, TD or grading.

**What a scenario can and cannot change (the honest limit, set by P39 and the 10/1 run).** Two layers move:
1. **Team margin:** through the injury charge only. A scenario sets the QB's play probability (1 = plays, 0 = out)
   and re-runs the baseline (`FeatureContext.build` + `predict_game`, both pure) on a copy of the injury list. For
   IND @ WAS that is the difference between Daniels charged 2.09 (questionable) and 4.65 (out). The sim is then
   anchored to the scenario's margin, as the served sim is to the served one.
2. **Players:** who takes the passer slot (`_promote_starter` / play probability), so the QB's own props and the
   distribution of targets.
What does **not** move: quarterback quality. The engine gives any starter the team's passing (the 10/1 run: Bagent got
Keenum's 30 att / ~235 yds; the generic QB charge is "not a comparison with the quarterback who replaces him").
Every scenario therefore carries that caveat, and a backup QB's own props in a scenario are shown as unreliable, not
as picks (the NYJ @ CHI ruling). Fixing the quality term itself is the rejected P28/P39 work and is out of scope.

**Which scenarios are worth covering (QB only to start):**
- (a) **as served** (reproduced, as the control: must match the served sim exactly, as run A did on 10/1);
- (b) **the books' priced QB starts**, when it differs from the sim's QB1 (the P53 warning; NYJ @ CHI);
- (c) **the questionable / doubtful starter plays** (play probability 1) and (d) **is out** (0), when the sim's QB1
  or the priced QB carries a game status (IND @ WAS: Daniels plays / Daniels out = Mariota starts).
At most three scenarios per game, usually two. **Not covered:** non-QB questionable players (combinatorial, and P9
found the injury coefficient has no edge to show), weather, coaching. Can be widened later on evidence.

**How it triggers.** Candidate games are found from data already produced: the P53 warning (sim QB1 != priced QB,
stored in the sim's `input_warnings`), a starting QB with a game status on the current report, or a P49 'unresolved'
hold. (1) On demand: `python -m src.scenarios --game 2026_04_NYJ_CHI` prints the table. (2) Optionally at each
refresh, after the sim step, for candidate games only, written to `data/scenarios.json` and a "Scenarios
(unvalidated, comparison only)" panel on the game page using the existing unvalidated label. A game's scenarios
retire when its inactive list posts (the starter is then known) or at kickoff.

**Cost.** No Odds API, Sportradar or Claude calls (an optional one-line Claude note per game would be ~$0.01; not
proposed). Compute only: the nflverse inputs load once per run (~1-2 min, already paid by the refresh if run inside
it); then ~20-40 s per scenario at 10,000 sims (the 10/1 runs: two 10k CHI runs and a full baseline rebuild in a few
minutes). A typical week (2-3 flagged games x 2-3 scenarios) adds ~2-6 minutes to a refresh, or runs on demand.

**What building it would require:** a `src/scenarios.py` (candidate detection, scenario specs, the baseline re-run on
a copied injury list, the sim with the scenario anchor and starter, the summary table: win %, margin, total, QB line,
the props whose sim P(over) moves most); `data/scenarios.json`; a game-page panel; tests. Proposed criteria, to be
confirmed before building: scenario (a) byte-identical to the served sim; each scenario's margin equals the baseline
re-run by hand with the same injury change; served outputs byte-identical with scenarios on vs off; every scenario
shows the no-QB-quality caveat and backup-QB props as unreliable; suite passes.

---

## 2026-10-01 — Explanations regenerated after the API credit top-up; close-game rule added to the game notes

User request. The Claude API credit had run out during the 03:30Z refresh (prop and game explanations skipped). After the
top-up: prop explanations for the top 25 (~$0.08) and game notes for all 16 week-4 games (~$0.13) regenerated; the number
guard dropped none. **Game-note prompt change (display only, no new logic):** a game whose served baseline win
probability rounds to 45-55% is marked "close game" in its prompt line, and the note must say why it is close
(the factors favouring the lean and those offsetting them) rather than only state the lean. Week 4: PIT @ CLE 52%,
ARI @ NYG 52%, ATL @ NO 48%, DEN @ SF 45%, LA @ PHI 45% (44.6% rounds in). Test added; suite 239. The ask-a-question
panel was checked live through the running servers: one transient connection error, then a correct answer (~$0.01).

---

## 2026-10-01 — NYJ @ CHI: QB-mismatch label and holds; scratch run with Bagent forced as the starter

**Why.** The week-4 refresh (03:30Z) raised a P53 warning: CHI's sim QB1 is Case Keenum (nflverse depth QB2; Caleb
Williams doubtful on ESPN's feed, play probability 0.10), while the books price Tyson Bagent. Bagent's lines have no sim
player to match, so they drop out of the ranking unmatched. Baseline CHI by 11.64, ML CHI by 7.91, market CHI -3.5.

**Scratch run (read-only, nothing stored or served).** `simulate_one` called directly, same seed and anchor as the
served run, with Bagent made QB1 through the sim's own expected-starter path (`_promote_starter`, the QB room reordered;
no injury rows changed, so CHI's injury charge is unchanged). Run A (Keenum) reproduced the served sim exactly.

| | Served (Keenum) | Bagent forced |
|---|---|---|
| CHI win probability | 82.9% | 83.0% |
| Margin p50 / total p50 | CHI by 11 / 45 | CHI by 11 / 44 |
| Unanchored engine margin | CHI +8.42 | CHI +8.76 |
| CHI QB (att, pass yds p50) | Keenum 30, 233.5 | Bagent 30, 237 (p25-p75 197-279), 2 TD |

CHI's pass-catchers and NYJ's players moved by a yard or less. The only ranking change: Bagent's pass yds becomes
matched and ranks first in the game (over 200.5, sim 74% vs market 50%, gap +22.8). That gap is the missing
quarterback-quality term (third observation; see P39), not a signal.

**Applied (user):** `KNOWN_GAME_ISSUES["2026_04_NYJ_CHI"]` label; `PROP_HOLDOUTS` for Keenum and Bagent pass and rush yds;
`td_props.PLAYER_HOLDOUTS` for both. **When the inactive list posts:** if Keenum starts, remove both; if Bagent starts,
keep Bagent's held as unreliable (it never ranks as a pick) and drop Keenum's. The served sim stays Keenum-led (P51,
which would promote the priced QB, stays unmerged until after MNF). Props and TD re-ranked and the dashboard re-exported
at 04:14Z with no change to lines or sims; neither CHI QB was rankable at the time (Bagent unmatched, Keenum unpriced),
so the holds take effect if either becomes rankable.

---

## 2026-09-30 — P62 Phase 1 criteria confirmed (S1-S8), quota approved; shadow build starts

Confirmed with the user one criterion at a time, before any code. Phase 1 is **shadow only**: after each Odds API props
pull is written, a Sportradar pull for the same games is converted to the `props_lines.json` schema and written to
`data/props_lines_sr.json` (plus raw responses and a manifest). Nothing in the model, sims, ranking or served dashboard
reads it. Window: two full weeks, starting when the pre-window checks below are done and reported.

**Quota (user, 9/30):** approved, ~825 of 950 calls/month on KEY1 (P61 ~610 + shadow ~215). **KEY1 only**: the shadow
does not rotate keys; at the 950 margin it stops with a log line (the gap shows under S6a). P61's own use of the
rotating key manager is logged separately as P65.

**Pull pairs.** Unit of comparison = an Odds API pull and the shadow pull made right after it; a pair more than 10
minutes apart is excluded and reported. `consensus` and lines flagged `removed` are dropped before any count.

- **S1 coverage.** At each pull pair: (a) no Odds API player in the ranked top N is absent from Sportradar; (b) >= 98% of
  all Odds API game x market x player entries are covered; (c) every miss is listed as **absent** (no similar name in
  that game's payload) or **misnamed** (fuzzy match >= 0.88 under another name), with its books; misnamed go to S2.
  Matching is after conversion, with `props.pnorm`.
- **S2 names and game identity (stop).** Over every pull pair: (a) every game maps 1:1 to a Sportradar event (teams +
  kickoff); (b) every Sportradar player-market matched by `props.match_player` resolves to the same sim player as the
  Odds API's; (c) per game, the priced-QB sets used by P49, P53 (and P51 if live) are identical; (d) every live
  `PROP_HOLDOUTS` / `KNOWN_DEFECTS` entry resolves to the same rows in both files. **Any failure is a stop.** A converter
  fix is allowed mid-window only if S2 then passes re-run over all saved pulls. (d) is a stop condition only: no `pnorm`
  change to those lookups now; if (d) stops, that becomes its own item with the evidence (user).
- **S3 lines.** On books mapped and carried by both at that pull, per book x game x market x player: (a) total identical
  in >= 95%; (b) where totals match, Shin-devigged P(over) within 0.02 in >= 95%; (c) every difference listed with book,
  market, minutes apart, tagged **lag** (one side equals the other's previous pull), **gap** (> 5 min apart) or
  **unexplained**. The book map is fixed and checked against a real pull from each source before the window.
- **S4 ranking.** At each pull pair, both files ranked against the **same** `sims.json`. Every prop that enters or leaves
  the top 25 (`props.TOP_N`) or flips side anywhere is listed and attributed in order: book mix (disappears when
  Sportradar is restricted to shared books), line (an S3 difference), coverage (an S1 absence), else **unexplained**.
  **Zero unexplained** (an unexplained change is a stop; the fix must pass on all saved pulls). Moves >= 5 places within
  the top 25 reported only; counts by cause per pull, no bar.
- **S5 record.** (a) Every top-25 prop of the Sportradar ranking at the last pull before each game resolves to a
  box-score player and grades; **any name-match failure in grading is a stop** (fix re-grades all saved pulls).
  (b) Both weeks graded per list (W-L-push, hit rate by market); props in both lists at different lines listed with
  both results; reported only, explicitly not evidence for either source. (c) The served record stays Odds API-only in
  Phase 1; shadow grades kept separately. **Switch gate:** a per-prop `line_source` field and the record-marking scheme
  (split at the switch, or combined with a marker) agreed and logged before any switch.
- **S6 failure.** (a) Phase 1: for each forced Sportradar failure (bad key, 401/403, 429, timeout, malformed JSON,
  empty, partial, key over budget), served outputs (`props_lines.json`, ranking, sims, dashboard) are byte-identical to
  shadow off, the refresh continues, and the failure is logged in the shadow manifest and printed in `run_sunday`. Unit
  tests plus one live forced failure. The shadow runs only after the Odds API pull is written. (b) **Switch gate:** the
  Sportradar-primary fallback to the Odds API (full and per-game, same schema) is built and tested before any switch;
  not a Phase-1 bar.
- **S7 quota and terms.** (a) Before the window: the trial end date found and logged; if it falls inside the window,
  decide with the user first. (b) KEY1 only, no rotation, stop with a log line at the margin. (c) Weekly: Sportradar
  calls by job (P62 shadow, P61, schedule), Odds API props credits used, and the hypothetical saving under a switch,
  labelled hypothetical. (d) **Switch gate:** trial end, post-trial price (Odds Comparison Player Props), multi-key
  terms and permitted use written in the log with sources; a failure stops P62.
- **S8 no effect.** (a) Shadow on and succeeding: served outputs (`props_lines.json`, `props.json`, `sims.json`,
  dashboard data outside the new section) byte-identical to shadow off on a live dry run. (b) At each Sunday window,
  sim inputs rebuilt with the Sportradar file in a scratch folder give identical sim QBs and a byte-identical
  `sims.json` (sims are seeded per game); any difference is a stop. (c) The comparison section on the props page uses
  the existing unvalidated label (`flagTrust.js` `UNVALIDATED_TEXT`), reads only saved shadow files, makes no live
  call, and leaves the rest of the props page unchanged; the user reviews it before it is final. (d) Suite passes,
  with new converter, map and failure-case tests.

TD is out of scope for Phase 1.

**Built 2026-09-30 (Phase 1 shadow; window NOT started).** `src/shadow_props_sr.py`, called at the end of
`ingest_props.run` after `props_lines.json` is written, for the games the Odds API fetched **live** that run (a cached
re-run is not a new pull and would make a false pair; nothing is added to `props_lines.json` to track this). Writes
`data/props_lines_sr.json` (same schema; keeps the Odds API `event_id` for `--alts`, adds `sr_event_id`), and per pull
`data/props_sr/pulls/<stamp>/` with `odds.json` (a copy of the paired Odds API file, which every pull overwrites),
`sr.json` and the raw responses, so S1-S5 can be re-run over every saved pull. `manifest.csv` has one row per game per
pull (result, minutes after the Odds API pull, book lines, removed, consensus / live dropped, unmapped books,
ambiguous). KEY1 only via `KeyManager(names=[KEY1])`: it cannot rotate and refuses at the margin. `P62_SHADOW=0`
turns it off. Book map: DraftKings, FanDuel, MGM -> betmgm, BetRivers, WilliamHillNewJersey -> williamhill_us;
`consensus` and unmapped books excluded and counted. Event map by team codes + kickoff within 3 h (all 32 Sportradar
codes equal ours, LA and WAS included, from the cached 9/30 schedule).

**Pre-window checks:**
- **S8d / S6a tests:** `tests/test_shadow_props_sr.py`, 63 checks: converter (real PIT @ CLE response as fixture, trimmed
  to the four markets), exclusions, event map, saved pair; every S6(a) failure (timeout, 403, 429 give-up, malformed
  JSON, empty, schedule failure, KEY1 over budget, partial pull) logs and never raises, and `props_lines.json` is
  untouched; a KEY1-only manager over budget refuses with no call and no other key; `ingest_props.run` returns
  normally and writes a **byte-identical** `props_lines.json` with the shadow off, failing, raising or succeeding.
  Suite 223 passed.
- **S3 book map, against real pulls** (saved 9/30 22:10Z Sportradar vs 9/30 16:02Z Odds API, PIT @ CLE, 6 h apart, so a
  mapping check, not an S3 measurement): all 31 Odds API player-markets present after conversion; on the four shared
  books 85/108 totals equal (DraftKings 24/31, FanDuel 29/31, BetRivers 10/17, MGM 22/29), consistent with real
  movement over 6 h rather than a crossed map. `williamhill_us` (Caesars) is Sportradar-only in this pull, so S3 cannot
  compare it unless the Odds API carries it.
- **S8a / S6a live (2026-10-01 03:03Z):** a real shadow pull on KEY1 of PIT @ CLE and LA @ PHI against the current
  `props_lines.json`, output to a scratchpad: 2/2 saved (15 and 9 players, 0 unmapped books, 0 ambiguous; 1 and 7
  removed lines). A forced bad key (isolated ledger, so the real KEY1 is not marked refused) logged a 403 and raised
  nothing. `props_lines.json`, `props.json`, `sims.json`, `dashboard.json` hashes identical before and after.
  3 KEY1 calls. Preview only (pair 11 h apart, outside S1's 10 min): LA @ PHI Davante Adams (2 markets) on the Odds API
  only, Puka Nacua on Sportradar only.
- **S7a: OPEN, blocks the window.** The trial end date is not in the log and the API does not expose it; it needs the
  user's Sportradar account page.
- **Not built yet:** the S1-S5 comparison script over saved pulls, the S8(b) scratch sim rebuild (needed at each Sunday
  window inside the two weeks), and the S8(c) props-page section (user review before final).

**Measurement tools built 2026-10-01 (user: ready before the window can open; user is checking the trial end date).**
- **Shadow bookkeeping added:** each pull also saves `holdouts.json` (the live `PROP_HOLDOUTS` / `KNOWN_DEFECTS` keys for
  its games; they are code and change between a pull and its comparison, S2d). `props.run` saves the sims its ranking
  used, plus the served `props.json`, to `rank_<stamp>/` beside the pull whose `odds.json` is byte-identical to the lines
  ranked: `game_simulations` keeps one row per game (62 rows, overwritten), so S4's "same sims" cannot be rebuilt
  later. Both are wrapped; neither can change what is served. Shadow calls now carry `"job": "p62_shadow"` in the
  Sportradar ledger (S7c); P61's code is untouched, so its calls stay untagged.
- **`python -m src.p62_compare --since <window start>`:** S1-S5 over every saved pull, each reported PASS / FAIL / STOP
  or UNMEASURED with the reason. Pairs: a game counts only when its shadow pull is <= 10 min after its own Odds API pull;
  both files are restricted to paired games before ranking. S1 classes a miss as misnamed on a fuzzy match >= 0.88
  **or a word-order swap** (an unconverted "Last, First" scores low on the ratio and would otherwise pass as a
  coverage gap); misnamed entries go to S2 and do not count against S1(b). S2: manifest mapping problems,
  `match_player` resolving to the same sim player, priced-QB sets by `player_key` (the set P49 / P53 / P51 all build),
  hold-table entries by exact name. S3 tags lag / gap / unexplained. S4 attributes in the confirmed order (book mix by
  re-ranking Sportradar on shared books, line, coverage, else unexplained). S5 grades the last pull before each game
  from ESPN's final box score (`export_sims.actual_result`; no W-L grader for ranked props existed) and matches names by
  `player_key` on the books' name. S7(c) reports shadow pulls and the hypothetical credit saving (labelled).
- **`python -m src.p62_sim_check --pull <stamp> --sims 2000`:** S8(b). Runs the pull's games A (Odds API file at the two
  read points: `features.qb_context`, `simulate_nfl.qb_check_inputs`), B (Sportradar file), A' (Odds API again), with
  `store_results=False`. A == A' is the control (else INCONCLUSIVE); B == A byte-identical with the same sim QBs, else
  STOP. Sims are seeded per game, so 2,000 sims answer it as well as 10,000; ~1.5 min a game for the three runs.
- **Checks:** `tests/test_p62_compare.py` (32 checks): identical files pass; > 10 min excluded; nothing paired is
  UNMEASURED, not PASS (a bug found by the smoke run and fixed); word-order swap is misnamed and stops S2; priced-QB
  difference stops S2; raw-name hold lookup stops S2 while S1 stays covered (first run of this test caught misnamed
  entries being counted against S1(b); fixed); line difference attributed to line; Sportradar-only books attributed to
  book mix; lag tag; grading W / push / unmatched; S8(b)'s swap reaches both read points. Suite 234 passed.
  **Live:** S8(b) on the 9/30 dry-run pull (PIT @ CLE, LA @ PHI, 2,000 sims): PASS, identical, sim QBs Watson / Rodgers
  and Hurts / Stafford, 3 min. Comparison smoke run on the same real payloads with the pair window widened in a scratch
  copy (11 h apart, so not evidence): runs end to end; S1 flags Davante Adams (LA @ PHI) as a top-25 absence; S3 tags all
  66 differences `gap`. S5's box-score fetch graded PHI @ CHI (Keenum 247 pass yds) correctly.
- **Still to build:** the S8(c) props-page comparison section (user review before final).

**S7(a) cleared and window opened, 2026-10-01 03:22Z (user).** Sportradar trial end: **2026-10-30**, source the user's
Sportradar account page (read 2026-09-30 CDT as "one month from today"; the exact day as shown on the page was not
quoted, so 10/30 is the user's reading of it). It falls 15 days after the window closes, so the window runs as planned.
The post-trial price and multi-key terms (S7d) remain a switch gate. **Window: 2026-10-01T03:22Z to
2026-10-15T03:22Z**, covering NFL weeks 4 and 5 whole (TNF 10/1 through MNF 10/12). Measure with
`python -m src.p62_compare --since 2026-10-01T03:22Z --until 2026-10-15T03:22Z`; S8(b) with `src.p62_sim_check` at each
Sunday window. Pulls before the start (the 9/30 dry runs, in a scratchpad) do not count.

**First window pull, 2026-10-01 03:45Z (full week-4 refresh, user):** 16/16 games saved from Sportradar 0.2 min after
the Odds API pull; ranking sims kept (`rank_20261001T034705Z`). `p62_compare` (no grading yet): **S3 PASS** (totals
1077/1079 = 99.8%; P(over) 1076/1076 within 0.02). **S2 STOP:** TEN @ BAL priced QBs differ, Odds API "Cam Ward" vs
Sportradar "Cameron Ward". Reported S1 FAIL (400/409 = 97.8%) and S4 STOP (6 unexplained), but **both numbers are wrong
in a way the tool has to be fixed for, pending the user's ruling:**
- S1: 3 of the 4 "absent" players are the same player under another name form: Cam / Cameron Ward, Cam / Cameron
  Skattebo, Woody / Jo'Quavious Marks. The classifier catches suffixes and word order, not nicknames, so they were
  counted as coverage instead of name failures (S2). Only Jacory Croskey-Merritt (IND @ WAS, rush yds) is truly
  absent: 408/409 = 99.8%.
- S4: the book-mix test restricts only Sportradar to the books the Odds API carried (the confirmed wording). A change
  caused by an Odds-API-only book (BetOnline, Bovada) cannot disappear that way: Kyren Williams rush yds flips because
  the Odds API has BetOnline at 55.5 and Sportradar has Caesars at 56.5, so the most-posted line differs; it was
  classed unexplained.
Nothing served depends on either; the window keeps collecting.

**User rulings and converter fix, 2026-10-01 (user confirmed explicitly):**
1. **Measurement fixes, both applied to `p62_compare`:** (a) a name that shares only the last name with exactly one
   unclaimed Sportradar player in the game is **misnamed** (S2), not absent (S1); (b) S4's book-mix test cuts **both**
   files to the books both carry for that player-market, so a change caused by an Odds-API-only book (BetOnline,
   Bovada) is book mix. Tests pin both (37 checks). The nickname rule also showed Jacory Croskey-Merritt was never
   absent: Sportradar writes him "Jacory Merritt".
2. **Converter fix (S2's mid-window rule: must pass re-run over every saved pull):** `NameResolver` maps each Sportradar
   player to the nflverse weekly-roster `player_name` (the form the sim, P49, P53, P51 and the books use) **only** when
   the team matches, the last name matches (or one part of a hyphenated roster surname), and the Sportradar first name
   equals that player's legal first name, football name or display first name, with exactly one such player.
   Otherwise the Sportradar name is kept and counted as unresolved or ambiguous; every resolution is written to the
   pull's `names.json`. Saved pulls are re-converted from their raw responses (`reconvert_pull`; the first version kept
   as `sr_v1.json`). **False-match checks:** unit tests show no merge across teams, none on the same team and last name
   with a different first name, a two-candidate case reported as ambiguous and not guessed, and the hyphen rule still
   needing the first name. On every saved raw payload (TNF window pull 16 games, 10/01 dry run 2, 9/30 diagnosis 2;
   281 player entries): 277 exact, 4 alias, **0 unresolved, 0 ambiguous, 0 collisions** (no two Sportradar ids turned
   into one name), and **every name change in a pull with a paired Odds API file matches the Odds API's own spelling**
   (16/16 in the window pull: Cam Ward, Cam Skattebo, Woody Marks, Jacory Croskey-Merritt, plus suffixes and
   capitals such as Michael Penix Jr., Chris Godwin Jr., DeMario Douglas). Suffixes now match the hold tables' raw
   books' names too (S2d). **Status: validated by S2's rule on every saved pull; the evidence is small (4 alias cases in
   one window pull), so it is re-tested at every pull through the window (`p62_compare` S2), not taken as settled.**
   Live pulls resolve names from the nflverse roster from now on; if the roster can't be read, names stay as
   Sportradar writes them and `names.json` says so.

**Before / after on the TNF window pull** (measurement fixes on in both): S1 PASS 409/409 -> PASS 409/409; **S2 STOP
(9 misnamed entries, TEN priced QBs Cam Ward vs Cameron Ward) -> PASS (0 misnamed, priced sets identical)**; S3 PASS
1077/1079 totals, 1076/1076 prices -> PASS 1107/1109, 1106/1106 (the renamed entries are now compared); S4 PASS
(8 changes, all book mix) in both.

3. **S8(b) on the TNF pull (2,000 sims, A / B / A'):** the first run died on an nflverse download timeout: the tool
   reloaded the inputs once per game (48 downloads). Rebuilt to load them once and call `simulate_one` per game (same
   steps as `run()`, nothing stored). **Pre-fix files: PASS, 16/16 identical; post-fix files: PASS, 16/16 identical**,
   same sim QBs in both. The pre-fix pass despite S2's stop is expected: P53 compares only priced names found in the
   team's QB room, so "Cameron Ward" was silently dropped rather than warned on, and P49 / P51 act only when a QB is
   flagged inactive or ruled out. The name failure was latent this week and would have reached the sims only in a week
   Ward was flagged, which is why S2 is a separate stop.


**S8(c) built and approved, 2026-10-01 (user reviewed the running page).** Props page, last card under "More props":
"Odds source check · Sportradar vs The Odds API" (`dashboard/src/P62Compare.jsx`), collapsed, S1-S5 status badges in
its header, labelled with `flagTrust.js` `UNVALIDATED_TEXT`. Inside: one status line per criterion with its numbers;
the S4 ranking changes (each source's rank, side and line, the change and its cause); line-by-line S3 differences
behind an expander. Data: `python -m src.p62_compare --export` writes `dashboard/public/p62_compare.json` over the
validation window from saved shadow files only; `props.run` calls it after each ranking in its own try/except (a
failure leaves every served file as it was). **S5 stays UNMEASURED on the page by design (user, 10/1): grading reads
ESPN and the no-live-call rule is intentional; S5 comes from the full report (`python -m src.p62_compare`).** A prop
off one source's ranking is shown as held out (gap / structural, line and side kept), started, or not priced (user
ruling: "not ranked" was too vague). On the TNF pull both former "not ranked" cells were gap hold-outs, not missing
lines: Shough pass yds (Odds API #3 U 254.5; Sportradar 256.5 held) and Malik Washington rush yds (Odds API 5.5 held;
Sportradar #13 U 4.5), both attributed to book mix. Missing file: the section does not render, the rest of the page is
unchanged (checked live). Tests: 3 new (export = report verdict, no socket opened; window filter; held vs not priced);
suite 251 passed. S8 now complete for Phase 1 apart from the per-Sunday S8(b) runs.

---

## 2026-09-30 — P64 scoped: manual injury/practice file. Format, ingestion and criteria set before the build

**Why.** The user can read official team injury reports from screenshots. P64 lets that transcription go into the
live injury layer before a refresh. It changes play probability exactly as the existing table would for the same
report, and nothing else: no new table values, no trend term. Days 1 and 2 are recorded but unused (user decision
9/30; that belongs to P47's own scoping).

**Format.** One CSV per week at `data/manual_injuries/<season>-wk<NN>.csv` (gitignored, like all of `data/`).
`#` lines are comments; one comment must carry `season=<yyyy> week=<n>`. Columns:
`team,player,pos,injury,d1,d2,d3,game`. `team` = store codes (Rams `LA`); `pos` = a key of
`features.STARTER_SLOTS`; `d1..d3` = `DNP` / `LP` / `FP` / `-` (also `Limit`, `Full`); `game` = `Out` /
`Doubtful` / `Questionable` / `IR` / blank. No `Probable` (the table has no entry; it would fall back to 0.50).
Practice used = the last day that isn't `-`; play probability = `ingest_injuries.play_probability(game, practice)`.

**Ingestion.** `ingest_injuries.run` reads the file for the run's season/week if present. The whole file is
validated before any use. A matched player (`player_key`) has the feed row's status, practice and play probability
replaced; an unmatched player is added with the usual snap-share lookup; merged rows carry `source="manual"`. The
merge happens before storage, as for ESPN. `latest_injury_report` counts `manual` rows only when they come from the
most recent ingest run, so a stale override never sits beside newer feed rows. `run_sunday` checks the file as its
own step before the refresh and stops the refresh if it is invalid.

**Criteria (all must pass before first live use):**
- **C1 replay, week 3.** A hand-made week-3 file (>= 8 rows covering: status change, practice-only change, a
  Questionable cleared to no status + FP, a player absent from the feeds, a suffixed name, a QB) merged into the
  week-3 nflverse final report in memory (no store writes; finished week, nothing re-simulated). Play probability
  changes for exactly the file's matched/added players and equals the table value for their row; every other row
  is unchanged in every field.
- **C2 no double-charging.** After the merge, no `player_key` appears twice in the run's rows. Across two runs (one
  with the file, a later one without it), `latest_injury_report` returns no duplicate `player_key` and no `manual`
  rows. Each team's `score_injuries` charge equals the charge computed from the feed rows with the manual values
  substituted by hand.
- **C3 no quiet skipping.** Every malformed line (unknown team, bad position, bad practice value, bad or `Probable`
  status, wrong column count, a player listed twice) and a missing or wrong `season`/`week` header raises, and **all**
  errors are listed with line numbers in one message, not just the first. Nothing is written to the store on an
  invalid file. A row that fails to match a feed row is reported as added, never dropped.
- **C4 week scoping.** A file whose header week differs from the run's week is rejected (C3). Manual rows from an
  earlier run stop applying once a later ingest run has written.
- **C5 no file, no change.** With no file present, the ingest rows are identical to the pre-P64 code's.
- **C6 days 1-2 inert.** Changing `d1`/`d2` alone changes no output field.
- **C7 printed.** Each run prints rows read, overrides, additions, and every play-probability change
  (`team player old -> new`).
- **C8** full suite passes.

**Design detail found while building (C2).** Merging at ingest is not enough on its own. If an override moves a team's
only nflverse row to `manual`, that run has no nflverse rows for the team, and `latest_injury_report` falls back to the
team's previous nflverse pull, which still lists the player: charged twice. The same fallback would revive a cleared
player. So the read side also lets current manual rows win over every other current row for the same `player_key`, and
healthy manual rows (play probability 1.0) act only as clears: they suppress the player and are then dropped, so they
never take a starter slot the nflverse ingest (which skips healthy players) would not have given them. An unmatched IR
player with no snaps for the team is not added (P20's rule) and is printed as `not added`.

**Results (2026-09-30), all pass:**
- **C1** replay on the 2026 week-3 nflverse final report, in memory (writes discarded; nothing re-simulated), hand-made
  file of 10 rows: 7 overrides, 1 cleared (BUF Ed Oliver), 1 added (SEA Jaxon Smith-Njigba, 0.25), 1 healthy with no
  feed row (no effect). 8 of 8 feed players matched, including `Marvin Mims` / `Rob Beal` against `Jr.` in the feed.
  The 140 unlisted rows are identical in every field; each listed player is one `manual` row at the table value.
  Team charges moved: BAL -1.795 -> -1.979, BUF -2.419 -> -2.483, CIN -1.610 -> -1.361, DEN -0.355 -> -0.486,
  SEA -2.013 -> -2.819. CHI unchanged: Bagent 0.80 -> 0.55 is QB2 behind the Out Caleb Williams, who holds the slot.
- **C2** no `player_key` twice in the run or in `latest_injury_report` over a plain t0 pull + the manual t1 run; every
  team's `score_injuries` equals the hand-substituted rows; a later run without the file leaves no `manual` rows
  (unit test).
- **C3** a bad file lists every error with line numbers in one message (unit test: 6 bad lines, 6 errors); `run`
  raises before `ingest_nfl` is called or anything is written; `check_manual` raises, which `run_sunday` treats as a
  critical stop.
- **C4** a wrong-week file is refused; stale manual rows drop out once a newer run writes.
- **C5** on the live injuries table (1,165 rows), the pre-P64 `latest_injury_report` and the new one return identical
  output; `ingest_nfl` / `ingest_espn` / `merge_feeds` are untouched, and no file means no merge.
- **C6** changing d1/d2 alone gives identical merged rows.
- **C7** each run prints rows read, counts by action, and `team player old -> new action` per row.
- **C8** suite 215 passed (9 new in `tests/test_manual_injuries.py`).

Live check: `check_manual` for week 4 reports no file, feeds only. A template is at
`data/manual_injuries/_TEMPLATE.csv` (local; `data/` is gitignored).

---

## 2026-09-30 — P62 scoped: what switching the primary props source would take (no decision, nothing built)

P62 is a coverage and quota change, not an accuracy change: the model, the sims and the ranking logic stay as they
are. What it can change is which lines the ranking is scored against, so it is scoped with the same care.

**What reads the props lines today** (`data/props_lines.json`, written by `ingest_props`):
- `props.rank` / `props.run`: the yardage ranking; `market_view` takes the most-posted line and the mean Shin-devigged
  P(over) across books; `fetch_alternates` pulls alt lines from the Odds API for the top N (~1 credit per pair).
- `features.py` (P49 hold): the set of QBs with a `player_pass_yds` line per game, matched **by name**.
- `simulate_nfl.qb_check_inputs` (P53 cross-check), and P51's promotion on its branch: the priced QB, **by name**.
- `run_sunday.py` (props pull before the sim since P51's reorder), the dashboard's props page (book names, best price),
  `api_server.py`, and research replays that read saved snapshots.
- TD (`ingest_td_props` -> `td_props_lines.json` -> `td_props`) is a separate pipeline, also on the Odds API.

**What a switch requires:** a Sportradar fetcher that writes the **same** `props_lines.json` schema, so nothing
downstream changes: (a) map each Sportradar event to our `game_id` by teams and kickoff (its abbreviations include
`LA` and `WAS`; check all 32 against ours); (b) names from "Last, First" to the Odds API's "First Last", suffixes
included; (c) market names to the four `player_*` keys (Sportradar's say "incl. overtime"; confirm the Odds API's
settle the same way); (d) book names to our lowercase keys, **excluding `consensus`**, which is not a book and
would be double-counted in `market_view`'s mean and best price; (e) drop lines flagged `removed` (10 of 372 in the
9/30 PIT @ CLE pull were removed mid-week); (f) string odds and totals to numbers; (g) keep `pulled_at`,
`refreshed_games`, `--only-missing` and `--games`; (h) the Odds API stays as an automatic fallback with the same schema;
(i) alternates stay on the Odds API or are dropped (no alt lines were seen in the Sportradar payload).

**What could break:**
1. **QB selection, silently.** P49's priced set, P53's check and P51's promotion all match names. A Sportradar name
   that doesn't match the depth chart makes a priced QB look unpriced: P51 stops firing, P53 warns falsely or not at
   all. This is the most serious risk because it changes sims, not only the props page.
2. Ranking drops: a player whose name no longer matches the sim falls out of the ranking without an error.
3. Book mix: Sportradar has MGM, BetRivers and Caesars where the Odds API has BetOnline and Bovada. The most-posted
   line and the mean P(over) move for reasons that have nothing to do with the model, so props enter or leave the
   list, and the graded props record mixes two sources mid-season unless the source is recorded per line.
4. Team or event mapping gaps: a game with no lines at all.
5. The fallback path rots if it never runs; and **a trial key expires**. A primary source on a trial can vanish
   mid-season, and the post-trial price is unknown.
6. Quota: P61 already uses ~610 calls/month on KEY1; a shadow pull at the current pull cadence (~3 a week x 16
   games + schedule) adds ~215, ~825 in all, under the 950 switch point but with little room.

**Code checks (done 2026-09-30, read-only, at the user's request during scoping):**
- **Name matching, two different matchers.** (1) The yardage and TD rankings use `props.match_player`: `pnorm`
  (casefold, punctuation and Jr/Sr/II-V suffixes removed), exact match, else the best `SequenceMatcher` ratio >= 0.88
  (`NAME_MATCH`) across both teams' sim players. A miss is only counted (`unmatched`); the player drops out of the
  ranking with no error. (2) P49's hold (`features._qb_hold`), P53's check and P51's promotion (`simulate_nfl`) use
  `ingest_injuries.player_key(team, name)`: lowercased, diacritics, suffixes and punctuation stripped, **exact match,
  no fuzzy step, word order kept**. So an unconverted Sportradar name ("Keenum, Case" -> "keenum case" vs
  "case keenum") fails both, and in (2) it empties **every** game's priced-QB set: P49 stops holding a priced QB's false
  inactive flag (the flag applies and the QB leaves the sim), P53 warns on every game, P51 never fires. Suffix and
  punctuation differences are tolerated by both; word order is not. Risk 1 is confirmed and is the gate: the
  converter must produce "First Last", and S2 must show identical priced-QB sets.
- **Known-issue tables are keyed by the raw books' name string.** `PROP_HOLDOUTS` by (game_id, books' name, market)
  and `KNOWN_DEFECTS` by (game_id, books' name) or (game_id, "team:XXX"), looked up with the exact string from
  `props_lines.json`, no normalization. Any character difference ("Michael Penix Jr." vs "Michael Penix") silently
  drops the hold or label. One entry is live now: IND @ WAS, Mariota and Daniels, pass and rush yds (held until WAS's
  week-4 report). `STRUCTURAL_HOLDOUTS` (market, position) is unaffected. Either the lookups move to `pnorm`
  (a small change of its own, testable on today's entries) or S2 adds: every live entry resolves against the new file.
- **Alternates: not in the Sunday loop.** `props.run` has `with_alts=False` by default; `run_sunday` calls it without
  alts; they are pulled only by a manual `python -m src.props --alts`. A switch need not replace them, but
  `fetch_alternates` looks up each game's Odds API `event_id` in `props_lines.json` and silently skips games without
  one, so a Sportradar-sourced file must carry the Odds API event id or `--alts` quietly returns nothing.

**Validation, proposed (confirm with the user before anything is built):**
- Phase 1, **shadow only**: the Sportradar fetcher writes `props_lines_sr.json` at the same moments as each Odds API
  pull, and nothing reads it. Two full weeks.
- (S1) coverage: per game and market, Sportradar's players include every Odds API player; every miss listed.
- (S2) names: `props.rank` run on both files ranks the same players; P49's priced-QB set and P53's `books` sets are
  identical per game. **Any difference is a stop.**
- (S3) lines: on the books both carry (DraftKings, FanDuel, BetRivers, MGM), the same line at the same pull in >= 95%
  of player-markets; differences listed.
- (S4) ranking: every prop that enters or leaves the top N, or flips side, between the two files is listed and traced
  to a line or book difference, not a parsing error.
- (S5) record: a finished week graded against both files, with the difference reported; decide before any switch how
  the season record marks the change of source.
- (S6) fallback: a forced Sportradar failure (bad key, 403, timeout) produces an Odds API pull with the same schema
  (test).
- (S7) quota and terms: Odds API credits saved per week reported; Sportradar's trial end date, post-trial price and
  multi-key terms known.
- (S8) sims byte-identical with either file (follows from S2), and the suite passes.
- **Decision after Phase 1**, not before. If S2 or S7 fails, P62 stops there: a cheaper fix for the quota gaps is
  pulling fewer times or using `--only-missing` more. TD is out of scope for Phase 1 and would be scoped separately.

## 2026-09-30 — Sportradar: three products checked against P47, P52 and the props feed; key manager built (not wired)

Diagnosis only; no prediction, sim, prop or dashboard output changed. 25 Sportradar calls in all (24 probe calls from a
session scratchpad plus 1 through the new client), all logged in `data/sportradar/usage.jsonl`.

**Keys.** `.env` holds five keys (`SPORTRADAR_API_KEY1..5`). All five open the NFL API and the player-props API, and
none opens Betting Splits. Sportradar sends no quota headers, so usage is counted locally. `src/sportradar.py`: KEY1 is
primary; one key is active at a time; every call is logged by key *name*, product, path and status; before each call
the active key is the first in order below `SPORTRADAR_MONTHLY_QUOTA - SPORTRADAR_QUOTA_MARGIN` (default 1000 - 50)
calls this UTC month on every product and not refused this month. A move to the next key writes a `switch` line
(time, from, to, reason) and prints it. A 403 quota or inactive refusal moves on and retries once; a 429 is the
1-call-per-second limit and retries on the same key. Calls are spaced 1.5 s across processes (two back-to-back
processes hit a 429). A new month returns to KEY1. `python -m src.sportradar --status` shows usage. Tests:
`tests/test_sportradar.py` (13 checks); suite 199. **Open questions for the user:** the 1,000/month figure is
the usual trial allowance, not confirmed for these keys; whether quota is per product (counted that way here, and the
switch fires on the busiest product); and, since all five keys open the same products, whether Sportradar's trial
terms allow using several keys to extend one project's quota. Check that before relying on keys 2-5.

**1. NFL API (P47, P51).** Injuries carry one current status per player, no per-day history (detail in P47's row).
Depth charts are per week, by slot (LWR / RWR / SWR, TE, RB, QB...) with `depth`; week 3's CHI QB order is the same
wrong order as nflverse (P51's row). Verdict: no accuracy hypothesis beyond what nflverse and P47's capture give.

**2. Betting Splits (P52).** No access (401 on all five keys; separate token through sales; v2 retired today). P52's
line movement could not be compared with real splits. Hypothesis and test pre-written in P63 in case access comes.

**3. Player props (Odds API).** Same players on the four priced markets for PIT @ CLE and ATL @ NO; 1 call per game
for every market against 4 credits per game; per-book opening lines; ended games kept briefly with their last lines;
anytime TD is posted too, in the `players_markets` block (corrected the same day; first read as absent). Two items: P61 (closing lines, so prop CLV can be measured) and P62 (source swap for
quota). Of the three products, P61 is the one with a direct link to accuracy work: it does not change a prediction,
but it gives P17 and every later props change the CLV test they are written against and currently cannot run.

## 2026-09-30 — Wednesday refresh; IND @ WAS labelled and WAS QB props held (starting QB unresolved)

Refresh ~16:00Z on main (old rating; P22 / P51 untouched): fresh odds, injuries, depth, weather; both models re-predicted;
week 4 re-simulated; fresh props (13/16 games) and TD lines (16/16); dashboard exported 16:03Z (P48 labels live: 13
prior-season charges across 7 games). Odds quota 184 (resets 10/1).

**The QB cross-check fired on IND @ WAS.** nflverse's week-4 file so far covers only CLE and PIT, and last week's
official statuses are not carried over (P19), so WAS runs on ESPN's feed: Jayden Daniels questionable (0.55), charged
2.09 (4.65 as out in last night's numbers, from the week-3 report). The sim starts him in ~55% of games; the books price
Marcus Mariota. Baseline moved IND by 12.2 -> IND by 10.0 (market IND -3.5).

**User decision:** label the game and hold WAS's QB props until the official report posts; re-check then (expected by
Thursday morning); re-run nothing else. Done: `export_dashboard.KNOWN_GAME_ISSUES["2026_04_IND_WAS"]`;
`props.PROP_HOLDOUTS` for Mariota and Daniels passing and rushing yards (Mariota's two priced props held); new
`td_props.PLAYER_HOLDOUTS` holds Mariota's anytime-TD prop. Props and TD re-ranked on the same lines and the dashboard
re-exported (16:09Z). **Remove all three once WAS's official report is in and the sim's QB matches the books.**

---

## 2026-09-30 — P5 (NFL) run against its pre-set criteria: no cap; closed

Criteria in P5's row, set with the user before this ran (and after the P22 replay's numbers were visible, as noted
there). `research/p5/p5_replay.py` rebuilds the frozen P22 candidate (A+B: ridge penalty 300, carry off 0.459 /
def 0.394, recomputed with the harness's own `carry_factors`, no tuning) and first reproduced the published weeks 1-4
row exactly: n 635, >= 3 at 123-102-5, >= 6 at 30-19, lean slope +0.044.

- **Gate (P37 lean slope, weeks 1-4):** +0.044, permutation p 0.859 (10,000 permutations; the published 0.858 used
  the harness's shared random stream). Not negative, so **no cap. P5 (NFL) closed.**
- **Reported, not a gate:**

| abs edge, weeks 1-4 | n | ATS | model MAE | line MAE | model - line |
|---|---|---|---|---|---|
| < 3 | 405 | 212-186-7 (53%) | 9.49 | 9.49 | +0.00 |
| 3 to < 6 | 181 | 93-83-5 (53%) | 11.14 | 10.57 | +0.57 |
| >= 6 | 49 | 30-19 (61%) | 11.22 | 10.03 | +1.19 |
| all | 635 | 335-288-12 (54%) | 10.10 | 9.84 | +0.25 |

  The points story and the ATS story disagree: large early edges are further from the result than the line (the
  stale-rating mechanism P5 was built on), yet they won ATS. A cap would shrink exactly the leans that won. 49 games
  is a small bucket, so the 61% is not a finding either; it only rules out the loss P5 needed.
- **Queued (information only):** the same slope test on the 62 live served 2026 weeks 1-4 edges once week 4 is
  graded (after MNF 10/5). It does not reopen P5; a full season of served edges with a negative slope at p < 0.05 does.
- College is P56, open.

---

## 2026-09-30 — P48 labels shipped (steps 1-2, display only); no number changed

Built against P48's confirmed Q6: the labels ship as soon as built, and the M1/M2 number changes wait for the boundary
after MNF 10/12.

- **Where the tag lives.** `ingest_injuries.share_sources` rebuilds `merge_snap_shares` one season at a time, so each
  (team, player) maps to (source, the exact share charged). `features.share_source` tags a row `current`, `prior` or
  `default` (share None -> DEFAULT_SNAP_SHARE). A tag is given only when the row's share matches that season's value
  (within the breakdown's 3-dp rounding), so a share read at a different time, or a failed snap feed, stays
  unlabelled rather than mislabelled. `FeatureContext.injury_adjustment` tags rows in memory, and `score_injuries`
  carries the tag into the breakdown stored in `predictions.components` (jsonb).
- **No schema change.** A `share_source` column on `injuries` would have needed the Supabase SQL re-pasted before the
  next ingest, or every injury write would fail. The breakdown already records each charged row, so the tag is there.
- **Who fetches.** Only `predict_baseline` fills the sources (one nflverse snap read per run). The live tracker, the
  sim and the ML don't fetch, and their rows are unlabelled. The export uses the breakdown's tag. Predictions made
  before this (the served week-4 ones) are looked up in the snap feed at export time, and the feed is fetched only
  if some row needs it.
- **Dashboard.** Prior-season rows show "2025 share" (warn colour), default rows "default share" (dim) and current
  rows no label. Each game with a prior-season charge gets a one-line note saying the numbers are unchanged (P48).
- **Checks.** (a) No number changes: the 16 week-4 baseline predictions were rebuilt in memory with the old code and
  the new, nothing written; they are identical apart from `generated_at` once the tag is removed. (b) Predict and
  export paths agree: 139 current / 14 prior / 9 default on both. The first export pass left 2 rows unlabelled
  (Lance 0.3775 and Brinson 0.3725, rounded half-way); the tolerance was widened by 1e-9 and a test added.
  (c) Spot check: Porter, Parsons, Josh Simmons and Chamarri Conner have no 2026 snap rows (weeks 1-3), so their
  prior tags are real. (d) `tests/test_share_source.py` 29 checks; suite 191 passed.
- **Week-4 prior-season charges now labelled (14):** O'Connell LV QB 3.69, Josh Simmons KC 1.68, Parsons GB 1.40,
  Conner KC 1.05, Lance LAC QB 1.02, T.J. Sanders BUF 0.75, Porter PIT 0.72, Okada SEA 0.71, Sewell CHI 0.61,
  Stewart HOU 0.56, Charbonnet SEA 0.50, Brinson GB 0.49, Turner CHI 0.42, Jenkins CLE 0.38.
- **Not done:** the live dashboard JSON was not re-exported (a `--no-explain` export clears the Claude game notes).
  The labels appear at the next normal export.

---

## 2026-09-29 — P30 diagnosed (efficiency, not shares); P31 partial trim fails its criteria. Read-only, nothing built

Run against the criteria in the entry below, which were committed first (3a85fb7). Scripts are in
`research/p30_p31_wk3/`: `roles_asof.py` (point-in-time production roles vectors, 21 cutoffs), `p30_diag.py`,
`p31_partial.py`, `p31_rq.py`. No production code touched.

### P30: the gap survives today's engine, and it is efficiency given targets

**Check:** B0 reproduces the 9/29 re-check exactly (2026 wk 1-3 top tercile 0.881 [0.812, 0.958], n=611, and every
other window to the digit), because the bootstrap draws are taken in the same order.

| window | n | B0 raw share | B1 roles, trim off | **B2 today's shares** | A actual targets | Ax actual buckets |
|---|---|---|---|---|---|---|
| 2025 wk 3-4 | 374 | 0.996 [0.901, 1.114] | 0.837 | 0.891 [0.803, 0.994] | 0.956 [0.875, 1.049] | 0.983 |
| 2025 wk 5-10 | 1051 | 0.906 [0.853, 0.971] | 0.759 | 0.809 [0.764, 0.865] | 0.941 [0.897, 0.989] | 0.950 |
| **2025 wk 11-18 (control)** | 1642 | 0.969 [0.919, 1.020] | 0.779 | **0.826 [0.785, 0.870]** | **0.968 [0.930, 1.006]** | 0.974 |
| 2026 wk 1-2 | 401 | 0.870 [0.787, 0.970] | 0.734 | 0.815 [0.736, 0.907] | 0.924 [0.853, 1.003] | 0.926 |
| 2026 wk 3 | 210 | 0.910 [0.786, 1.069] | 0.784 | 0.853 [0.739, 0.993] | 0.922 [0.835, 1.030] | 0.912 |
| **2026 wk 1-3** | 611 | 0.881 [0.812, 0.958] | 0.752 | **0.830 [0.767, 0.902]** | **0.918 [0.863, 0.978]** | 0.917 |

Top tercile, yards B/actual, 90% CI. The 2026 wk 1-3 bottom tercile on A is 1.106 [1.024, 1.198]. The top tercile's
targets/actual are 0.958 (B0), 0.905 (B2) and 0.855 (B2 control). 8 of 611 rows are not in the roles vector.

**By the letter, rule 2 fires:** B2's CI (0.767-0.902) is below 1.00. **But the rule used the wrong reference, and
that is my error in setting it.** B2 sits at 0.826 in the 2025 control window as well, where nothing is wrong. The
roles vector is normalised to team volume. The harness keeps only player-games with a target and 20+ prior targets,
so the mass the vector puts on everyone else is missing from the population, and B2 reads about 15% low in this
harness by construction. Against its own control, **2026 B2 (0.830) is where 2025 wk 11-18 was (0.826). Today's
shares carry no 2026-specific gap.** The allocation piece (targets/actual 0.905 vs control 0.855) is no worse either.

**What survives is efficiency given targets.** A holds actual targets fixed and uses league yards per target. It is
free of the selection problem and sits on 1.00 in the control (0.968, CI includes 1). In 2026 wk 1-3 it is 0.918
[0.863, 0.978] at the top and 1.106 [1.024, 1.198] at the bottom. Both CIs exclude 1, so this is compression. Ax uses
the player's actual bucket counts and agrees (0.917), so it is not the category mix. Of B0's 0.881, about 4 points is
target share and about 8 is efficiency. The trim does not touch efficiency, so **the gap is still there under today's
engine.** It is not an artefact of the old harness. 2025 wk 5-10 showed the same pattern (A 0.941, excluding 1), and
it had faded by wk 11-18.

**Outcome under rule 2:** the efficiency evidence goes to P17 and is reported here. **P17 is not reopened** without the
user. The allocation arm hands nothing new to P31. P30's question is answered: the 2026 split is efficiency
compression (the P17 mechanism), not the share vector. Nothing built.

### P31 partial trim: fitted alpha 0.340; fails criteria 2, 4 (realised clause) and 5. Stop rule fires

**Check:** at alpha = 1 / 0 the harness reproduces the 9/29 part-A rows for each week (wk 2: raw sum 1.131 -> 1.034,
MAE 0.0422 -> 0.0390, Q4 1.017 -> 0.926, trimmed take 4.8%; wk 3: 1.149 -> 1.049, 0.0402 -> 0.0369, Q4 1.079 -> 0.984,
2.9%). The pooled full trim is MAE 0.0379, Q4 0.957, top-2 0.935 [0.849, 1.022], against 0.934 [0.846, 1.019] on 9/29
(a different bootstrap draw).

**alpha**, fitted on 2025 wk 3-10 (234 team-games): trimmed players took 2.38% of real targets while the trim removes
6.6 pts. **alpha = 0.3403**, inside (0, 1).

| | 2025 wk 11-18: no trim | full trim | **alpha 0.34** | 2026 wk 2-3: no trim | full trim | **alpha 0.34** |
|---|---|---|---|---|---|---|
| 1. trimmed mass kept vs real (pts) | 7.1 vs 3.7 | 0 vs 3.7 | **2.6 vs 3.7** | 8.6 vs 3.8 | 0 vs 3.8 | **3.1 vs 3.8** |
| 2. target-share MAE | 0.0429 | 0.0404 | **0.0412** | 0.0412 | 0.0379 | **0.0390** |
| 3. top-2 real/sim (95% team-clustered) | 1.014 [0.964, 1.063] | 0.941 [0.894, 0.986] | **0.966 [0.919, 1.012]** | 1.024 [0.931, 1.117] | 0.935 [0.849, 1.022] | **0.966 [0.877, 1.054]** |
| 4. pregame-quartile Q1 / Q4 | 0.760 / 1.032 | 1.020 / 0.956 | 0.907 / **0.982** | 0.878 / 1.050 | 1.243 / 0.957 | 1.079 / **0.989** |
| 4. realised-quartile Q4 (see note) | 0.787 | 0.847 | **0.825** | 0.732 | 0.804 | 0.777 |
| 5. carry-share MAE | 0.0385 | 0.0350 | **0.0360** | 0.0321 | 0.0302 | **0.0308** |
| 5. RB1 carries real/sim | 1.039 | 0.947 | **0.979** (+0.032) | 1.151 | 1.076 | **1.102** (+0.026) |
| 6. per-team shares sum to 1 | yes | yes | yes | yes | yes | yes |

| criterion | verdict |
|---|---|
| 1. retained mass within 1.5 pts | **pass** (1.1 and 0.7 pts short) |
| 2. share MAE not worse than full trim | **fail** on both windows (+0.0008, +0.0011); MAE falls steadily as alpha -> 0 |
| 3. top-2 closer to 1 than 0.934, CI incl. 1 on both windows | **pass** (0.966 on both) |
| 4. pregame Q4 in 0.95-1.05 on both windows | **pass** (0.982, 0.989) |
| 4. realised-quartile Q4 >= 0.90 on 2025 | **fail** (0.825); the live full trim fails it too (0.847) |
| 5. carry MAE not worse; RB1 carry ratio moves <= 0.02 | **fail** on both parts, both windows |
| 6. team totals | **pass**, structural |

**Note on the realised-quartile row.** The 9/20 walk-forward script is gone and its table does not reproduce. The
closest definition (per player, pooled over the window, real share 2%+) gives no-trim Q1-Q4 1.269 / 0.993 / 0.913 /
0.787, against 1.255 / 0.953 / 0.979 / 0.801 on 9/20. Its full-trim Q4 is 0.847 against 9/20's 0.919, probably
because production `snap_participation` (rookie denominator) differs from the 9/20 replica. It is reported under the
closest definition, not re-defined after the fact.

**Stop rule fires** (criterion 4's realised clause). No second alpha, no per-position alpha, no tau change. **Not
adoptable as specified.** The live full trim stays.

**What the numbers say, for the user's review:**
- The partial trim does what it was sized to do at the top of the vector. On pregame shares it moves top-2 from 0.94
  to 0.97 and Q4 from 0.956 to ~0.985, on **both** windows. That is where the priced props live.
- **The full trim's top-2 overshoot is now significant out of sample:** 2025 wk 11-18, 0.941 [0.894, 0.986], over
  245 team-games. The 9/21 and 9/29 re-grades pointed that way on 2026 alone; it now also holds in the window the
  trim was validated on.
- It pays for that in per-player MAE and carries, where the many small shares dominate and the full trim, which zeroes
  fringe players, is closer. The criteria pull in opposite directions. Which matters more for props is the user's
  call, and props themselves can only be measured prospectively.

---

## 2026-09-30 — P22 phase 2 built on `p22-rating` (not merged): four criteria pass, two need the user's ruling

Branch `p22-rating`, commit ebb4665, pushed; main unchanged. Checks: `research/p22/p22_phase2_checks.py`, week 4, all in
memory; nothing stored, served or exported changed.

**What was built.** `compute_ratings` fits play EPA on offense + defense + home and solves the ridge exactly (numpy,
penalty 300, neutral sites from the schedule, intercept unpenalised). It keeps last season at 0.459 offense /
0.394 defense (0.75 before). The 900-play weight is unchanged. Behind `RATING_OPPONENT_ADJUST` (default on);
off restores the old rating exactly (tested). **One deviation from the harness, recorded:** phase 1 used
scikit-learn's `Ridge`, which on sparse input solves iteratively (`sparse_cg`) and lands within 6e-6 EPA
(<= 0.0004 rating points) of the exact answer. Live uses the exact solve. Criterion 1(a) is therefore checked
against the harness with its solver made exact.

| # | criterion | result | verdict |
|---|---|---|---|
| 1(a) | port fidelity vs the phase-1 harness | week 4, 32 teams: max difference 0.0 EPA; flag-off recompute equals the stored live ratings (max 0.000) | **pass** |
| 1(b) | mean abs(model - line) falls, as phase 1 predicted | week 4: **4.85 -> 3.30** over 16 games; 9 games move > 3 pts, all toward the line, each decomposed below | **pass** |
| 2 | sim totals follow the proxy | 10 of 12 games with a proxy move >= 1 pt move the same way (83%); slate mean: sim -0.25, proxy 0.00 | **per-game clause passes; slate clause fails by construction** (see below) |
| 3 | props raw P(over) shift <= 1.0 pp per category | receptions +0.05 (n 16), rec yds -0.44 (n 8), RB rush -1.27 (n 4), QB rush -0.25 (n 1), pass yds -2.00 (n 1) | **flagged by the letter, on 1-4 props** (see below) |
| 4 | tests pin the settings | `tests/test_p22.py`: constants, flag default, opponent adjustment credits the harder schedule, neutral coding, flag off = old rating; `test_game_explain` covers both caveats; suite 189 | **pass** |
| 5 | text matches | the prompt no longer forbids "opponent-adjusted"; the caveat (flag on): "still lean about X% on last season's play, but last season is shrunk well toward average, and each team's numbers are adjusted for the opponents it has faced"; one regenerated explanation (KC @ LV) carries it; nothing else says "not adjusted" | **pass** |
| 6 | ML untouched | ML files md5-identical to the phase-1 snapshot; ML predictions identical with old vs new ratings (first run; the ML never reads `team_ratings`); the second run's ML step hit a network timeout, so this is re-run at ship | **pass** (re-check at ship) |

**1(b), the week-4 moves over 3 pts** (margin old -> new; the parts are home minus away, in points):
TEN @ BAL +14.58 -> +6.09 (offense carry -3.01, offense adjustment -3.65); KC @ LV -13.77 -> -6.40 (offense carry
+3.81, offense adjustment +3.02); NYJ @ CHI +11.05 -> +3.99 (offense carry -3.01, defense carry -2.20); JAX @ CIN
-11.57 -> -5.18 (defense carry +4.05; this was the week's only value flag); LAC @ SEA +12.99 -> +8.06; MIA @ MIN
+10.36 -> +5.90; DET @ CAR -7.08 -> -3.12; DAL @ HOU +7.63 -> +3.92 (defense carry -6.10, offense +2.0 / +2.8); IND @ WAS
-12.16 -> -9.00. Carry is the larger part in most games, as phase 1 found.

**Ruling (user, 2026-09-30): the slate clause is dropped; the per-game clause is the test (passes, 83%).** It was
structurally guaranteed to show zero proxy change on a full slate, whatever the rating's quality, so it was never a
valid test. **Criterion 2's slate clause was badly specified (my error).** The proxy is measured against the week's league mean
rating. On a full slate every team plays exactly once, so its slate-mean change is exactly 0 by construction, and "the
same sign" cannot hold. The per-game clause (>= 75% same direction) is the meaningful test, and it passes (83%). The
sim's medians are whole points, so moves of +/-1 are near the noise floor.

**Criterion 3 flagged, on tiny samples.** Only 7 of 16 week-4 games have props lines yet (33 matched props). The two
categories over 1.0 pp rest on 1 pass-yds prop and 4 RB rush props. By the letter the refit goes to the user before
shipping. Proposed plan: re-measure at ship on week 5's full props slate (several hundred props once lines post). If a
category with n >= 20 still moves > 1.0 pp, refit that category's offset after week 5 is graded, on week-5 pregame
new-rating sims (the 9/21 method), showing the current offsets in the meantime. The user decides.

**Run note.** The first check run hit a transient snap-count fetch failure, which silently ran both arms without the
P31 trim. The script now aborts when participation is missing, and the numbers above are from the clean re-run
(participation 100%).

---

## 2026-09-30 — P22 phase 2 scoped: port A+B to the live rating. Criteria set before the build

User approval 2026-09-30. Port A+B into `ingest_nflverse.compute_ratings` with phase 1's settings frozen. Nothing is
re-tuned on live results. Built on branch `p22-rating`, and merged only at the week boundary after MNF 10/5, once
week 4 is graded, like every engine change. The garbage filter (C) is not ported.

**What B actually is (user-requested note, for the caveat text).** B's gain comes mostly from carrying *less* of last
season overall: the prior-season factor goes from 0.75 to about 0.42 on average. The offense/defense split itself is
small (0.459 vs 0.394), and phase 1 did not separate the two effects. So the caveat and explanation text describe the
change as "last season's numbers are shrunk further toward average, and ratings are adjusted for the opponents
faced", not as a defense-specific fix.

**Frozen settings, pinned in code.** Ridge penalty 300; carry off 0.459, def 0.394 (phase 1's values, as logged to 3
dp); 900-play weight unchanged; home coded +1 / -1, 0 at a neutral site from the schedule; intercept unpenalised;
adjusted mean = intercept + team coefficient. Behind an env flag, `RATING_OPPONENT_ADJUST` (on at merge), so it can be
rolled back.

**Criteria:**
1. **Served numbers vs phase 1's direction.** (a) Port fidelity: on the week-4 slate, the live code's off/def ratings
   equal the phase-1 harness's A+B ratings (same pinned settings, same plays) to 1e-9. (b) Direction: on the week-4
   slate (16 games; week 5 re-checked at ship), baseline margins before vs after, in memory. Mean |model - line| falls,
   as phase 1 predicted (3.63 -> 2.68 on the test seasons). Every game whose margin moves > 3 pts is listed with the
   rating part (offense / defense, carry / adjustment) that moved it. (c) Reported, not gated: 2026 weeks 1-3 replayed
   MAE before vs after.
2. **Sim totals follow phase 1's totals proxy.** Week-4 sims before vs after, in memory. In every game where the proxy's
   implied total moves >= 1 pt, the sim median total moves the same way in >= 75% of them, and the slate-level mean
   change has the same sign as the proxy's.
3. **Props bias correction: measured, not assumed.** Week-4 props re-priced on the before and after sims, in memory.
   If any category's mean raw P(over) moves > 1.0 pp (P18's shifts were <= 0.45 pp and needed no refit), `BIAS_FIT` is
   flagged as needing a refit. The refit plan (it needs graded props priced on new-rating sims, so earliest after week
   5) goes to the user before shipping. Under 1.0 pp everywhere: no refit, recorded.
4. **Tests pin the frozen settings:** the constants (300, 0.459, 0.394, flag default); a small synthetic ridge fit
   with a known answer (a team that faced only strong defenses is rated above its raw mean); neutral-site coding; the
   flag off reproduces the old rating exactly. Suite passes.
5. **Text matches what happens.** The explanation prompt no longer forbids "opponent-adjusted". The caveat says the
   ratings are adjusted for opponents faced and that last season is shrunk further toward average (share still shown).
   No text anywhere still says "not adjusted for opponents" or "not opponent-adjusted". A regenerated explanation is
   checked on at least one game.
6. **ML untouched, confirmed again before shipping:** `build_training.py` (incl. `RollingEpa`), `training_nfl.csv` and
   `models/nfl_margin.*` md5-identical to the phase-1 snapshot, and the week's ML predictions identical before and
   after, in memory.

**Ship steps at the boundary:** merge; rebuild the ratings; re-predict, re-sim, props, TD and exports for week 5;
re-run criterion 1(b) and the QB sweep on week 5; log the served numbers.

---

## 2026-09-30 — P22 phase 1 results: opponent adjustment + separate carry passes all bars. Research only, nothing built

Run against the entry below (bars committed first, cf01c4c; R0 target corrected before any arm ran, f8ca478).
Script and full output: `research/p22/p22_phase1.py`, `research/p22/p22_phase1_results.md`. Nothing live touched.

**R0 reproduces the corrected P37 replay exactly:** 2,661 games, ATS 1294-1302-65, corr -0.002; against P37's own
`replay()` on the same pbp, all 2,693 games match to 7e-15.

**Frozen settings (2016-2021 only).** A: ridge penalty 1000 by the 1-SE rule (minimum at 300). B: carry off 0.458 /
def 0.386, against the live 0.75 for both. C: filter at wp 0.10 / 0.90. Candidate A+B, re-tuned on training: penalty
300, carry off 0.459 / def 0.394.

| arm | train MAE | test MAE | gain | test by season 22/23/24/25 | test wk 1-4 | mean abs edge | ATS% at abs edge >= 4 | implied-total MAE |
|---|---|---|---|---|---|---|---|---|
| R0 (live) | 10.523 | 10.393 | - | 9.67 / 10.48 / 10.53 / 10.89 | 10.423 | 3.63 | 45.1 | 11.103 |
| A | 10.540 | 10.138 | +0.255 | 9.08 / 10.42 / 10.48 / 10.57 | 10.008 | 3.09 | 49.7 | 10.629 |
| B | 10.359 | 10.003 | +0.390 | 9.07 / 10.35 / 10.16 / 10.43 | 10.071 | 2.62 | 50.4 | 10.764 |
| C | 10.638 | 10.511 | -0.118 | 9.79 / 10.63 / 10.58 / 11.04 | 10.472 | 3.86 | 45.9 | 11.172 |
| ABC | 10.480 | 10.044 | +0.349 | 9.04 / 10.43 / 10.27 / 10.42 | 10.049 | 2.74 | 49.2 | 10.599 |
| **A+B** | 10.430 | **10.010** | **+0.383** | 9.00 / 10.36 / 10.23 / 10.44 | 10.034 | 2.68 | 51.6 | 10.619 |

The line on the test games: margin MAE 9.494, total MAE 10.189.

| bar | result | verdict |
|---|---|---|
| 5 attribution (>= 0.03) | A +0.255 kept, B +0.390 kept, C -0.118 dropped | candidate A+B |
| 1 pooled gain >= 0.10, >= 3/4 seasons | +0.383, 4/4 | **pass** |
| 2 weeks 1-4 not worse | 10.034 vs 10.423 | **pass** |
| 3 no edge inflation | mean abs edge 2.68 vs 3.63; ATS at >= 4 51.6% vs 45.1% | **pass** |
| 4 implied totals not worse | 10.619 vs 11.103 | **pass** |
| 6 ML untouched | `build_training.py`, `training_nfl.csv`, `nfl_margin.json` / `.meta.json` md5-identical; only `research/p22/` written | **pass** |

**Reported for scale, not a bar: all ten seasons, A+B vs R0.** Better in **8 of 10** (worse in 2019 -0.006 and 2021
-0.047). Pooled 2016-25 gain **+0.211** (R0 10.470, line 9.778), which closes about 30% of the gap to the line; the test
seasons' +0.383 is the high end. Gains by season: 0.05, 0.05, 0.11, -0.01, 0.40, -0.05, 0.68, 0.11, 0.30, 0.44. Every
arm gained more in 2022-25 than in 2016-21, so a live gain nearer +0.2 than +0.4 is the honest expectation. Candidate
selection (bar 5) read the test seasons, as the bars specify. ABC, which involves no selection, passes bar 1 on its own
(+0.349).

**Bar 7 (reported, not a bar): the new rating's edge still carries no significant ATS information.** All ten seasons,
all weeks: corr -0.014 (-0.05, +0.02), ATS at >= 4 325-313-13 (51%), lean-slope permutation p 0.27. Test seasons: corr
-0.044, p 0.15. The live rating's figures are -0.002 / 448-465 / p 0.56. The one lead, not a finding: weeks 1-4 across
all ten seasons went 335-288-12 (54%, two-sided binomial p 0.065), but the correlation there (+0.051, p 0.20) and the
lean slope (p 0.86) show nothing. The answer did not move. What changed is edge *size*: the new rating sits much
closer to the line (mean abs edge 2.68 vs 3.63, and 249 test games at >= 4 pts vs 403).

**Observations for phase 2 (not tested here):** most of B's gain is from carrying *less* of last season overall (0.75
-> ~0.42); the offense/defense difference itself is modest (0.46 vs 0.39), and nothing here separates the two. A alone
was flat in the training seasons (10.540 vs 10.523) and strong in the test seasons, so its value varies by season.
2026's 32 rows (weeks 1-2, reported only): MAE 13.62 -> 12.30, ATS unchanged 10-21-1.

**Next, if the user wants it: phase 2** ports A+B into `compute_ratings` with the frozen settings, pins them with tests,
and ships at a week boundary (after MNF 10/5), with its own criteria for the served-number changes, the sim's totals
and the props bias correction. The ML port stays a separate item.

---

## 2026-09-30 — P22 phase 1 scoped: opponent-adjusted rating, walk-forward. Design and bars set before running

User approval 2026-09-30: phase 1 only, research, nothing live touched. Everything below was fixed before any number
was produced. The harness goes in `research/p22/`.

**Baseline (R0).** P37's replay of the live Layer 1 (`compute_ratings`): per week, the season's earlier regular-season
pass/run plays blended with the whole previous season (x0.75, 900-play weight), plus the live HFA / rest / travel /
wind, graded against `training_nfl.csv` (`market_spread`, `target_margin`). **R0 must reproduce P37 before anything
else is read:** 2,582 games, all-weeks ATS 1249-1270-63, corr(edge, cover residual) -0.008. **Corrected before any arm ran:** those
are P37's 9/21 numbers from *before* its 9/22 fix (OAK/SD/STL games dropped). The harness stopped itself on them,
because it gave 2,661 games. Checked two ways: without the mapping it gives n 2,582 and corr -0.008 (ATS off by one
game, 1250-1269-63, most likely a revised EPA flipping one near-zero edge); and against P37's own `replay()`, run on
the same pbp, every one of 2,693 games (2016-2026) matches to 7e-15. The check now targets the corrected replay the
later work used (P9 and P46): n 2,661, ATS 1294-1302-65, corr -0.002. No arm, penalty or bar changed. No injury term, as in P37
and P39.

**Arms.** Each changes only the rating; everything else is identical to R0.
- **A, opponent adjustment only.** Each season's team means come from a ridge fit on play-level EPA,
  `epa ~ offense_team + defense_team + home` (home coded +1 / -1, 0 at a neutral site; intercept unpenalised).
  Adjusted offense = intercept + offense coefficient, adjusted defense = intercept + defense coefficient (neutral-site).
  They go into the live blend unchanged (x0.75, 900 plays, raw play counts). The current season is fit on its
  earlier weeks; the prior season on all of it.
- **B, separate offense/defense carry only.** Raw means as live. The prior-season factor is split into r_off and r_def,
  each estimated on 2016-2021 as the through-origin slope of a team's regular-season mean EPA on its previous season's
  (league-centred, pooled over the season pairs 2015->16 ... 2020->21). The 900-play weight is unchanged.
- **C, garbage-time filter only.** As live, but plays in the 4th quarter with the offense's win probability below 0.10
  or above 0.90 are dropped from both seasons. The threshold is fixed, not tuned; plays with no wp are kept.
- **ABC** all three, with B's factors re-estimated on the same A+C means; plus **the candidate**, the combination of
  the parts that clear bar 5.

**Tuning, on 2016-2021 only.** Ridge penalty from {10, 30, 100, 300, 1000, 3000}. Pick the one with the lowest
training margin MAE, then take the largest penalty whose MAE is within one standard error (sd(|error|)/sqrt(n)) of
that minimum, leaning toward more shrinkage. B's factors are estimated, not tuned. Everything is frozen before the
test seasons are read.

**Test:** 2022-2025. **Reported, not gated:** training seasons, and 2026's rows in the training file.

**Bars** (as in P22's row):
1. The candidate's pooled test margin MAE improves >= 0.10 on R0, and it is better in >= 3 of the 4 test seasons.
2. Test weeks 1-4 MAE not worse than R0.
3. No edge inflation: test mean |edge| <= R0's + 0.05, and the ATS win % at |edge| >= 4 no more than 2 pp below R0's.
4. Totals: implied total MAE vs actual not worse than R0's. The implied total is
   `2 L + 63 x [(off_h - off_bar) + (off_a - off_bar) + (def_h - def_bar) + (def_a - def_bar)]`, with L the previous
   season's league points per team-game and the bars the week's league means of that arm's ratings. This is a proxy
   for the sim's totals, since finished weeks are never re-simulated.
5. Attribution: A, B and C each vs R0 on test MAE. A part gaining < 0.03 is dropped. Bars 1-4 judge the candidate.
   If no part clears 0.03, P22 fails.
6. ML untouched: `build_training.py`, `RollingEpa`, `training_nfl.csv` and the model files are byte-identical before and
   after, and no file outside `research/p22/` is written.
7. **Reported, not a bar (user addition):** P37's Test 2 on the candidate and on R0: ATS by |edge| at 0/2/3/4/6,
   corr(edge, cover residual) with 95% CI, and the through-origin slope b, for all weeks and weeks 1-4, on the test
   seasons and on all ten. Plus P37's permutation test on the lean slope. Stated plainly whichever way it comes out.

**Stop rule.** If bar 1 fails: report and stop. No second penalty grid, no threshold change, no re-tuning after the
test seasons are seen.

---

## 2026-09-29 — Week-4 refresh; a flaky paged read (P53); misses review of four week-3 games. Nothing built

**Refresh (user request).** `run_pipeline --sport nfl --model both --date 2026-10-01 2026-10-04 2026-10-05 --fresh-odds`
(nflverse incl. depth charts, weather, odds, injuries, both models) -> `simulate_nfl --upcoming-only` -> `export_sims` ->
`ingest_props --fresh` -> `props` -> `ingest_td_props --fresh` -> `td_props` -> `export_dashboard`. Odds quota 347 -> 306.
- **Injuries: no week-4 report yet** (nflverse posts from Wednesday), so the week-3 designations still apply (219 rows,
  87 ruled out). ESPN IR over nflverse applied once (P40). 11 ESPN-IR vs official-"out" conflicts were kept as official.
  No inactive lists (normal on a Tuesday).
- **Odds:** the 19:47Z pull is the first since MNF, so LA @ PHI and NYJ @ CHI now have a reopen point (P52). It is
  also the latest pull, so their since-reopen row appears from the next pull.
- **Predictions:** one flag, JAX @ CIN (baseline JAX by 11.6 vs CIN -2.5; layer 1, as noted in the first pass).
  Large gaps with a known cause: KC @ LV (baseline LV +13.8 vs +4.25) carries **Aidan O'Connell 3.69 pts**
  (questionable, 2025 snap share 0.82): a live P48 case on the report path, which P49 does not cover. IND @ WAS
  charges Jayden Daniels out 4.65 from the week-3 report; the books price Mariota, so the charge agrees with the market.
- **QB sweep failed on the first sim:** WAS's sim QB1 was Daniels, against the books' Mariota and his own out row.
  Traced to a read that saw no WAS QB row at all; see **P53**. The sim step and everything after it were re-run from
  stored data (no API calls): 32/32 team-sims now match the books-priced QB (or none is priced), and WAS starts
  Mariota. The stored baseline predictions match a fresh in-memory read on 16/16 games.
- Props 110 priced (7 games still unposted); TD 274 players across 15 games.

**Misses review (user request): SEA @ WAS, PHI @ CHI, LA @ DEN, ATL @ GB (week 3).** Home margin = home minus away.
The market is the last pregame consensus we pulled; the close is nflverse `spread_line` (ESPN/DraftKings in
`clv_log` agrees).

| game | final (home margin) | baseline | ML | market at our last pull | close | who missed |
|---|---|---|---|---|---|---|
| ATL @ GB | ATL 35-14 (GB -21) | GB +12.9 (err 33.9) | GB +8.4 (29.4) | GB -4.5 (25.5) | GB -4.5 (25.5) | **all three**, same wrong winner; market least wrong. Baseline carried the false Penix charge (~5.6, P42/P49); without it ~28, still worse than the market |
| SEA @ WAS | WAS 33-31 (WAS +2) | SEA by 16.0 (18.0) | SEA by 12.2 (14.2) | SEA -8.5 (10.5) | SEA -8.5 (10.5) | **all three**, same wrong winner; model far worse. Mostly layer 1 (rating SEA by 15.5) |
| PHI @ CHI | CHI 27-7 (CHI +20) | PHI by 2.9 (22.9) | PHI by 3.7 (23.7) | PHI -3.5 (23.5) | PHI -3.5 (23.5) | **all three, equally.** Keenum was flagged inactive pregame and played (P49 criterion-9 case), so the sim started Bagent |
| LA @ DEN | DEN 30-26 (DEN +4) | LA by 4.05 (8.05) | DEN by 1.85 (**2.15**) | LA -1 (5.0) | **DEN -1.5** (2.5) | baseline and our pull missed the winner; ML right. The market flipped ~2.5 pts to DEN in the last 75 min after our last pull (23:05Z). The baseline carried Stidham 3.18 (P48) |

Read: the market missed all four too: wrong winner in three, and at our last pull in the fourth. The models did not
beat it in any of the three blowouts. ML beat both the baseline and the market only on LA @ DEN. Two of the baseline's
four misses carry a known data defect in the model's own direction (Penix false charge, Stidham P48). Removing them leaves errors of ~28 (ATL @ GB, market 25.5) and ~4.9
(LA @ DEN, market 5.0 at our pull), so neither defect explains the miss.

---

## 2026-09-29 — P52 logged: line movement per game (display only). Criteria set before the build

User decision: log it and build it. It is display only: no model input, no schema change, no new API calls. The
reopen-point logic is shown to the user on real games (SEA @ WAS plus two others) before it ships.

**Acceptance criteria:**
1. **Scope.** Each NFL game in the dashboard export carries a `line_movement` block for spread and total: the
   first-tracked value, the reopen value, the current value, the move since each, the direction ("toward <team>"),
   timestamps, and the books compared.
2. **Same-book movement.** A move is the median, over books priced at both ends, of each book's own change. The
   end values shown are those same books' medians at each end. Fewer than 2 common books -> that comparison is null.
   A change in which books are listed must not register as movement.
3. **Reopen point.** The first pull at or after the previous week's last kickoff + 4 h (its game is over), and before
   this game's kickoff. None -> reopen is null. If it is the first tracked pull, only one comparison is shown.
4. **Single pull** (every college game today) -> `line_movement` is null, and the UI shows nothing for it.
5. **Thresholds.** A move under 0.5 pt reads "no meaningful move". A spread move through 3 or 7 is noted.
6. **Label.** Fixed text on the display: line movement, not bet percentages; no handle or ticket data; a move can
   reflect sharp money, injury or other news, or book risk management.
7. **Sign convention.** `spread` is the home-team line; a more negative spread = movement toward the home team.
   Covered by a test.
8. **No side effects.** Predictions, simulations and props are unchanged; no schema change; no Odds API call added.
9. **Tests.** Unit tests for 2, 3, 4, 5 and 7; the full suite passes.
10. **Hand check before shipping.** The export's numbers are shown against the raw snapshots for SEA @ WAS and two
    other games, and the user confirms they read correctly.

**Amended during the hand check (same day, before shipping; confirmed by the user, who approved shipping):**
- **Criterion 3, reopen point.** The build first keyed the reopen to the previous week's last kickoff (MNF). ARI @ NYG
  showed this is wrong: neither team played MNF, its line moved -2.5 -> +1.0 on Sunday night, and it had no reopen
  point at all. Books re-post after each team's own game. **Amended:** the first pull at or after the later of the two
  teams' previous kickoffs + 4 h. A team with no earlier game (week 1) gives no reopen.
- **Criterion 2, the move.** The median of per-book changes did not equal to - from, and the display read wrong
  (SEA @ WAS "+7.0 -> +8.5, moved 2.0"). **Amended:** from and to are the medians of the books priced at both ends,
  and the move is to - from. A change in the book set still cannot register as movement (tested).
- **Known display trade-off.** A same-book comparison can differ from the headline consensus when few books are
  common. ARI @ NYG since first tracked uses 4 books: -2.5 -> 0.0, while the 9-book current median is +1.0. The book
  count is shown on every row.

**Hand check (criterion 10), from the raw snapshots:**

| game | first tracked | reopen (pull) | current | since first | since reopen |
|---|---|---|---|---|---|
| SEA @ WAS (wk 3) | WAS +2.0, Wed 9/16 (2 books) | WAS +7.0, Wed 9/23 05:02Z | WAS +8.5 | 6.5 toward SEA, through 3 and 7 | 1.5 toward SEA (9 books); O/U 40 -> 40.5 |
| PHI @ CHI (wk 3) | CHI -1.5, Wed 9/16 | CHI +4.5, Wed 9/23 | CHI +3.5 | 5.0 toward PHI, through 3; O/U 48 -> 42.5 | 1.0 toward CHI (8 books); O/U 41.5 -> 42.5 |
| ARI @ NYG (wk 4) | NYG -2.5, Wed 9/23 | NYG +1.0, Mon 9/28 23:00Z | NYG +1.0 | 2.5 toward ARI (4 books) | no meaningful move |
| PIT @ CLE (wk 4) | CLE +2.5, Wed 9/23 | CLE +2.5, Sun 9/27 23:05Z | CLE +2.5 | no meaningful move; O/U up 1.0 | no meaningful move; O/U up 0.8 |

Tests: `tests/test_line_movement.py` (7 tests; criteria 2, 3, 4, 5 and 7, plus post-kickoff pulls ignored); suite 166
pass. Dashboard compiles. **Shipped 2026-09-29** (user go): exported; the export differs from the previous one only by `line_movement` and the explanations' `generated_at` stamps, with the text unchanged (criterion 8). **Fix at ship time:** the first export left LA @ PHI and NYJ @ CHI blank. Their latest pull (9/29 03:27Z) priced 1 book, so nothing had 2 common books. Pulls pricing fewer than 2 books are now skipped when choosing first / reopen / current (test added; suite 167). All 16 week-4 games now carry the block. LA @ PHI and NYJ @ CHI show only since-first-tracked: PHI and CHI played MNF, and no pull has come after it yet. Rendered in the browser on ARI @ NYG and LA @ PHI with no console errors.

---

## 2026-09-29 — P31 partial trim: which priced props sit where it wins and loses (user request). Read-only

The user leans toward the partial trim (alpha 0.34) because it wins where props are priced. Before deciding, they
asked for the priced props counted by the group where the trim wins or loses. Groups come from the trim-off pregame
shares, per team-week. Targets: T1 top-2 per team; T2 rest of the upper half of 2%+ shares; T3 lower half; T4 under
2%. Carries: C1 carry rank 1, C2 rank 2, C3 the rest. Script: `research/p30_p31_wk3/p31_prop_groups.py`.

**Walk-forward error by group, full trim -> partial:**

| group | 2025 wk 11-18 real/sim | MAE change | 2026 wk 2-3 real/sim | MAE change |
|---|---|---|---|---|
| T1 top-2 | 0.941 -> **0.966** | -0.0001 | 0.935 -> **0.966** | -0.0005 |
| T2 upper half | 1.028 -> 1.053 | -0.0004 | 0.995 -> 1.026 | +0.0003 |
| T3 lower half | 0.955 -> 0.918 | +0.0008 | 1.103 -> 1.030 | +0.0011 |
| T4 < 2% | 1.270 -> 0.782 | **+0.0023** | 1.575 -> 0.869 | **+0.0024** |
| C1 carry rank 1 | 0.939 -> 0.971 | +0.0016 | 1.071 -> 1.097 | **+0.0064** |
| C2 carry rank 2 | 1.026 -> 1.060 | -0.0006 | 0.743 -> 0.761 | -0.0033 |
| C3 rest | 1.110 -> 0.947 | +0.0011 | 1.187 -> 1.041 | +0.0005 |

**Priced props by group:**

| group | week 3, full slate (444) | week 4 as priced now (56, 3 games) |
|---|---|---|
| receiving T1 top-2 | 104 | 22 |
| receiving T2 upper half | 187 | 16 |
| receiving T3 lower half | 45 | 2 |
| receiving T4 < 2% | 0 | 0 |
| rush, RB carry rank 1 | 30 | 6 |
| rush, RB carry rank 2 | 22 | 0 |
| rush, other (QBs 27 / 4, RBs 2 / 0) | 29 | 4 |
| pass yds (no share effect) | 27 | 6 |

Read:
- **The share-MAE loss is almost all in T4 and T3, which carry no priced props and 45 of 444 respectively.** On that
  point the user's premise holds.
- **T1 (104 props) is a clean win.** Calibration moves 0.94 -> 0.97 on both windows at no cost in MAE.
- **T2 is the largest priced group (187) and it does not win.** The partial trim takes a little share from every kept
  player. T2 was on the mark or slightly under-credited under the full trim (1.028, 0.995), and it moves further
  under (1.053, 1.026). MAE is flat.
- **The carry loss is not in the far tail.** It is concentrated in RB1s (C1), who carry 30 of the 54 priced RB rush
  props in week 3 and all 6 in week 4. The C1 level improves in 2025 (0.939 -> 0.971) and worsens in 2026 (1.071 ->
  1.097). MAE is worse in both windows, by +0.0064 in 2026.
- **The shifts are small at prop scale.** Mean T1 share on week 3 moves 0.206 -> 0.199 (about 3%), and T2 0.111 -> 0.107.

**Decision (user, same day): partial trim rejected, full trim stays live.** Reasons and accepted weaknesses are in P31's tracker row.

---

## 2026-09-29 — P30 diagnosis and P31 partial trim: criteria set before either runs (user-approved scope)

User decision, 2026-09-29: run P30's diagnosis first, on today's trimmed target shares, then walk-forward a P31
partial trim sized to what the trimmed players actually take. P48, the P33 refinement and P51 stay on hold.
Everything below was written before any number was produced. Read-only research, no production code change.

### P30: does the 2026 top-tercile gap survive the shares today's engine uses?

**Method, fixed.** The 9/29 harness unchanged except for the share. Population: player-games with 1+ target and
20+ prior targets, terciles by own prior yards/target, team's actual bucket counts, pre-week league yards/target by
bucket, player-game bootstrap (2000 draws, seed 7, 90% CI). Four arms on the same rows:
- **B0**: raw `usage_rates` share (the 9/29 harness). Must reproduce 2026 wk 1-3 top tercile 0.881 [0.812, 0.958],
  n=611, or the run stops.
- **B1**: the production roles vector (`player_roles` -> `blend_roles`), trim off, normalised within team per bucket
  as `team_shares` does with no injuries. A player not in the vector gets 0 (that is what the engine does); he stays
  in the population, and the count of such rows is reported.
- **B2**: B1 with the trim on (tau 0.10), i.e. today's engine shares.
- **A**: the player's actual targets x league yards/target (efficiency only, given targets).
Point in time: pbp, snap counts and depth chart cut at each week's first kickoff (so every game of the week is
scored). Control: 2025 wk 11-18 on B2, built the same way (dated nflverse depth charts).

**Decision rules, fixed:**
1. B2 top-tercile 90% CI includes 1.00 -> the reopened gap belongs to the pre-trim share. P30 goes back to closed, and
   the same reopen rule is re-set on B2, to be re-run once week 6 is graded.
2. B2 CI below 1.00 -> the gap survives today's shares. It is split with A: A's top-tercile CI below 1 = efficiency
   given targets (P17 evidence, reported; P17 is not reopened without the user); B2 targets/actual targets below 1
   for the top tercile = target allocation (handed to the P31 partial-trim work and the receiving pass).
3. B2 CI above 1.00 -> over-credit; reported as evidence on the P31 trim overshoot.
Nothing is built under P30 whatever the outcome.

### P31: partial trim, sized to what the trimmed players take

**Design, fixed.** Same trim rule (skill player outside his position's playing slots, participation < 0.10), but a
trimmed player keeps **alpha x his raw share** in every category instead of 0. One alpha, fitted on **2025 weeks 3-10
only**, true walk-forward, as the value at which the trimmed players' normalised expected targets equal the real
targets they took. Frozen, then tested on **2025 weeks 11-18** (the 9/20 walk-forward window and method: dated depth
chart before each week, usage and snaps from prior weeks only) and **2026 weeks 2-3 pooled** (the 9/29 part-A method
and cutoffs). An alpha grid (0, 0.25, 0.5, 0.75, 1) is reported on the test windows for context only; the verdict
uses the fitted alpha. The full trim (alpha = 0) and no trim (alpha = 1) are the two reference arms.

**Criteria, all on the test windows:**
1. **Retained mass:** trimmed players' normalised expected share of team targets within 1.5 pts of the share they
   actually took, on each window (full trim: 0 vs 3.8% on wk 2-3). Replaces the old "per-team raw sum within 0.02 of
   1.00", which a partial trim fails by design.
2. **Share MAE** (targets, per player vs real share) not worse than the full trim on either window (wk 2-3 full trim
   0.0379).
3. **Top-2 receivers per team, real/sim:** on 2026 wk 2-3 pooled, point estimate closer to 1.00 than the full trim's
   0.934 and the 95% team-clustered CI includes 1.00; on 2025 wk 11-18, the CI includes 1.00.
4. **Q4 by pregame-share quartile** in 0.95-1.05 on both windows. The 9/20 realised-share quartile table is also
   reported on 2025 wk 11-18 for comparison, and its Q4 must not fall below 0.90 (the 9/20 stop-rule band).
5. **Rushing:** carry-share MAE (car_all vs real carry share) not worse than the full trim on either window, and the
   RB1 real/sim carry ratio moves by no more than 0.02.
6. **Team totals:** structural (normalisation and play stream unchanged); checked by per-team shares summing to 1.
**Props** (the old criterion 6) cannot be measured here without re-simulating finished weeks (standing rule). If the
walk-forward passes, both arms run on the next unplayed week's pregame sims and are graded afterwards; that is a
condition for flipping, not for this walk-forward.

**Stop rule:** if the fitted alpha falls outside (0, 1), or criterion 3 or 4 fails, report. No second alpha, no
per-position alpha, no tau change in this step. Nothing ships without the user.

---

## 2026-09-29 — P30 re-check reopens P30; P31 re-graded on weeks 2-3 pooled. Read-only, nothing built

Both were blocked until week 3 was fully graded. PHI @ CHI pbp posted on nflverse (see the entry below), so both ran
the same day. No production code touched. Scripts are kept under `research/p30_p31_wk3/`.

### P30: the pre-set reopen rule is met

The rule (set 2026-09-25): re-run the same bootstrap once week 3 is graded; reopen only if the 2026 top-tercile 90%
CI no longer includes 1.00. The harness is the 9/20 `p30_control.py` (engine-style share x team bucket counts x league
yards per target, top tercile by own prior yds/target, 20+ prior targets, player-game bootstrap, seed 7). The 2025
rows reproduce the 9/20 table to the digit, so the harness is unchanged.

| window | n | top tercile B/actual (90% CI) | bottom tercile | all |
|---|---|---|---|---|
| 2025 wk 1-2 | 391 | 1.073 [0.971, 1.196] | 1.075 [0.936, 1.245] | 1.070 |
| 2025 wk 3-4 | 374 | 0.996 [0.901, 1.114] | 1.066 [0.930, 1.234] | 1.056 |
| 2025 wk 5-10 | 1051 | 0.906 [0.853, 0.971] | 1.074 [0.987, 1.165] | 0.983 |
| 2025 wk 11-18 | 1642 | 0.969 [0.919, 1.020] | 0.976 [0.912, 1.048] | 0.993 |
| 2026 wk 1-2 (re-run) | 401 | 0.870 [0.787, 0.970] | 1.075 [0.950, 1.233] | 0.972 |
| 2026 wk 3 | 210 | 0.910 [0.786, 1.069] | 1.159 [0.951, 1.441] | 1.018 |
| **2026 wk 1-3** | **611** | **0.881 [0.812, 0.958]** | 1.098 [0.989, 1.232] | 0.988 |

**P30 is reopened.** Two caveats for scoping the diagnosis, not reasons to set the rule aside:
- **The 9/20 closure rested on a partial week 2.** Its "2026 wk 1-2" row had n=211. It ran on 9/20 before most of week 2
  was played. The same window with the full week is n=401 and already excludes 1.00 (0.870). The closure was
  premature on its own terms.
- **The harness is not today's engine.** It uses raw `usage_rates` shares (before the P31 trim, ON since 9/21) and
  league yards per target by bucket (no player efficiency, P17 parked). A top tercile by own yards/target is mostly
  high-share WR1s, the players both the flattening (P31) and the efficiency compression (P17) hit. The 2025 wk 5-10
  row (0.906, CI excluding 1) shows the same size of gap has appeared before and faded. So the first diagnosis
  question is how much of 0.881 survives today's shares. Criteria to be written here, with the user, before it runs.

### P31: re-graded on weeks 2-3 pooled (the 9/21 entry's open item 2)

**Part A, the roles vector** (method as 9/21: production `player_roles` and `_participation_trim`; pbp, snaps and depth
chart cut at the cutoff; quartiles by the pregame trim-off share, 2%+, cut within each week). Week 2's cutoff is
9/20 15:48:41Z, as before. Week 3's is 9/27 15:45Z (the noon window; depth chart as of 12:56:55Z). Evaluated on every
game after the cutoff, i.e. Sunday + MNF, 15 games each. **Check:** week 2 Sunday-only reproduces the 9/21 table
exactly (1.131 / 1.032, Q4 1.016 / 0.924, MAE 0.0413 / 0.0382, 43 targets = 5.1%). The top-2 CI differs in the third
decimal (0.805 vs 0.809) from a different team-clustered bootstrap draw.

| | wk 2 (30 teams) off -> on | wk 3 (30 teams) off -> on | **pooled (60 team-games) off -> on** |
|---|---|---|---|
| 1. raw share sum (bar: within 0.02 of 1.00) | 1.131 -> 1.034 | 1.149 -> 1.049 | 1.140 -> **1.042** (fail) |
| 2b. real/sim by pregame quartile, Q1 | 1.125 -> 1.569 | 0.645 -> 0.926 | 0.877 -> **1.241** |
| Q2 | 0.808 -> 0.903 | 1.062 -> 1.134 | 0.938 -> 1.025 |
| Q3 | 1.151 -> 1.053 | 0.992 -> 0.920 | 1.068 -> 0.985 |
| Q4 | 1.016 -> 0.926 | 1.078 -> 0.983 | 1.049 -> **0.956** |
| top-2 receivers per team, real/sim (95% team-clustered) | 1.010 -> 0.922 [0.810, 1.039] | 1.035 -> 0.945 [0.814, 1.071] | 1.023 [0.931, 1.116] -> **0.934 [0.846, 1.019]** |
| 3. share MAE | 0.0422 -> 0.0390 | 0.0402 -> 0.0369 | 0.0412 -> **0.0379** (pass) |
| trimmed players' share of real targets | 4.8% (139 players) | **2.9%** (142) | **3.8%** (281), vs ~9.8 pts/team of share removed |

Read: the direction of 9/21 holds on two weeks. The trim improves per-player share error both weeks. It over-credits
the top two receivers by 6-7% both weeks, where the untrimmed vector sat near 1. Pooled, the trim's top-2 CI just
includes 1 (upper 1.019), so the overshoot is consistent but not yet significant. Week 3's trimmed players took even
less than week 2's (2.9%), so the "removes ~10 points, should remove ~4-5" gap is about 6 points of share per team.
That is the size a partial trim would have to close. Criterion 1's residual (1.04, not 1.00) points the same way.

**Part B, props, week 3** (trim on only: the stored pregame sims re-priced against the saved week-3 lines,
`data/snapshots/wk3-props_2026-09-28/props_lines.json`, with `props.rank`; 444 priced, all graded against nflverse pbp).
**No trim-off arm for week 3:** it would need a re-sim of a finished week, and `load_inputs` has no as-of cutoff
(standing rule). The 9/20 week-2 arms (`full_on.json` / `full_off.json`) were in a session scratchpad that is gone,
so week 2 is carried from the 9/21 entry's aggregates.

| group | n | raw P(over) | market | actual over rate | Brier sim | Brier market |
|---|---|---|---|---|---|---|
| all receiving | 336 | 0.462 | 0.491 | 0.458 | 0.2597 | 0.2500 |
| receptions | 166 | 0.449 | 0.483 | 0.428 | 0.2548 | 0.2497 |
| rec yds | 170 | 0.475 | 0.499 | 0.488 | 0.2644 | 0.2503 |
| RB rush yds | 54 | 0.547 | 0.500 | 0.500 | 0.2367 | 0.2502 |
| QB rush yds | 27 | 0.577 | 0.498 | 0.556 | 0.2498 | 0.2540 |
| pass yds | 27 | 0.508 | 0.500 | 0.593 | 0.2780 | 0.2502 |

Receiving Brier, sim minus market: +0.0097, game-clustered 95% CI [−0.0124, +0.0312]. Excluding the three wrong-QB
sims (SEA @ WAS, MIN @ TB, PHI @ CHI; P49/P51) changes little: receiving 0.459 / 0.493 / 0.458, Brier gap +0.0068.
Week 2 (9/21): raw 0.453 vs actual 0.464, Brier 0.2753 vs market 0.2471. **Two weeks, n-weighted (~625 receiving
props):** raw 0.458, actual 0.461, market ~0.49; Brier ~0.267 vs ~0.249. On the mean, the raw trim-on sim now sits on
the realised over rate. The market still sits higher and still wins on Brier (per-prop ordering, not level). No
pooled CI: the week-2 rows weren't kept.

**Not done, by design:** no partial-trim design, no tau change, no refit. The 9/21 entry's open item 1 (a trim that
removes share only down to what those players actually take) is the next P31 step. Its criteria go into this log
with the user before anything runs.

---

## 2026-09-29 — P49 merged; criterion 3's residual assigned to P48; P51 logged (depth order); P30/P31 unblocked

**P49 merged** into main (`git merge --no-ff p49-qb-hold`), after P18, one change at a time at the week-4 boundary.
Suite **159 passed** on main. No week-4 lists exist yet, so no served number changed; the next window refresh
(Thursday PIT @ CLE) is the first live use. Rulings (user, 2026-09-29):
- **Criterion 3:** the two residual slot shifts, **ATL @ GB** (Penix −5.59, Rush +4.74; net −0.85) and **LA @ DEN**
  (Stidham −3.18, Ehlinger +2.10; net +1.08), are P48 effects. They are noted in P48's row, to be checked when P48 is built.
- **Criterion 4:** the CHI miss is out of P49's scope. **Logged as P51**: when QB1 is out, the depth chart can rank a held
  QB (Keenum) below a QB the books don't price (Bagent), so the sim still starts the wrong one. It's a depth-order
  problem, not an inactive-flag problem. Not built (user: not tonight).

**PHI @ CHI pbp is on nflverse** (155 plays, 4 quarters, 27-7). Passers: Keenum 34, Hurts 27, **Dalton 1**. Dalton was
held by P49 and did play, so criterion 1 is **11/11**. The pbp shows Bagent had no pass attempts.

**Still on hold for the user's review:** P48 and the P33 refinement.

---

## 2026-09-29 — P49 QB-only rule built and replayed on weeks 2-3; on branch `p49-qb-hold`, NOT merged (two criteria need a ruling)

**Rule as built** (`features._qb_hold`, called from `apply_inactives`; flag `INACTIVES_QB_HOLD`, default on). A
pregame-flagged QB whose final report gives him out / IR / doubtful / questionable is applied as before. Otherwise:
1. the books price him for this game → **hold**;
2. he is the projected starter (top QB on the nflverse depth chart that the report doesn't rule out, i.e. the
   simulator's own QB order) **or** his team's snap-share leader → **unresolved**: flag applied, reported for review
   (whether the books price another QB or price none);
3. anyone else → **hold** (backup).
`run_sunday` prints every hold and unresolved flag per window. If the depth chart can't be loaded, every flagged QB
goes through the price check (priced → hold, else unresolved).

**Two design changes forced by the replay, both toward caution:**
- The `depth_charts` table cannot name a starter. It ranks by snap share carried from last season (P48): Drew Lock
  over Darnold, McCarthy and Wentz over Murray, and Watson/Flacco over Sanders. The rule uses nflverse's daily depth
  chart instead (`sim_data.current_depth`). The table is used only to add the snap-leader cross-check.
- **A projected starter with no books price is unresolved, not held.** Week 2's Penix was on PUP (so off the weekly
  report), top of the chart, and the books priced no ATL QB; holding him would have started him in the sim. Of 83
  replayed flags he was the only one on that path.

**Replay** (`research/p49_replay.py`): 83 pregame QB flags on 50 team lists, weeks 2-3. Per game: list as first seen
pregame, report as of kickoff, nflverse depth chart as of the week, books-priced QBs from the saved `props_lines`
snapshots (the raw props cache is mostly empty early pulls), snap leader = 2026 dropback leader in earlier weeks.
Played = nflverse pbp; PHI @ CHI has no pbp yet, so only Keenum is confirmed (scoring plays), the rest are unknown.
A first pass read Monday's injury pull for every week-3 game and so saw Mayfield's in-game "out"; the as-of-kickoff
report fixes that (P44 pattern).

| # | Criterion | Result | |
|---|---|---|---|
| 1 | every flagged QB who played is held | **10/10**: Darnold, Murray, Sanders, DeVito, Jalon Daniels, Penix (wk3), Keenum (MNF), and week 2's Bagent, Rudolph, Strand. Dalton (MNF) held, not yet confirmed as played | pass |
| 2 | no starter wrongly held | 63 genuine (didn't play) QBs held; none books-priced, none a snap leader. Cooper Rush (ATL's weeks 1-2 starter, genuine week-3 inactive) is unresolved/applied via the snap-leader check. Rests on 2 weeks of lists (week 1 has none stored); late scratches untested, as recorded | pass |
| 3 | every served change > 0.5 explained | Every change traces to a removed false starter flag (Penix wk3, Sanders wk3, Darnold) or a removed P48 backup charge (Mills 4.23 x2, Huntley 3.56 x2, Rattler 4.90 x2, McCarthy 5.50 x2, Sanders wk2 5.50, O'Connell 4.92, Stidham 3.18, Leonard 2.36 x2, Lance 2.27, McKee 2.07, Rudolph 1.80). **Two exceptions: the one charged QB slot passes to another inactive QB whose charge is itself P48-type.** ATL @ GB: Penix −5.59 but Rush +4.74 (net −0.85 home margin; he's applied because he's the snap leader). LA @ DEN: Stidham −3.18 but Ehlinger +2.10 (net +1.08). Largest net moves: CLE @ TB wk2 −5.50, CAR @ CLE +5.50, MIN @ TB −5.50, CIN @ HOU +4.23 (baseline; ML similar) | **needs a ruling** |
| 4 | sim QB1 = books-priced QB | served mismatches 3 → 1 after the rule (SEA Darnold and MIN Murray fixed). **Remaining: PHI @ CHI**: Keenum is held, but the depth chart ranks Bagent (QB2) above him, so with Williams out the sim still starts Bagent. That's depth order (P28-type), outside this rule. (The check uses today's rosters, so it's exact only for recent weeks) | **needs a ruling** |
| 5 | ruled-out QBs applied | all applied (3 by status; every other genuinely out starter comes out unresolved, which is applied) | pass |
| 6 | ML consistency | rule only in `apply_inactives` (live path); `score_injuries`, `build_training` and training features untouched (`build_training` never calls `apply_inactives`) | pass |
| 7 | tests | `tests/test_qb_hold.py` (10): Darnold/Murray/Penix held; ruled-out applied; backup held + logged; non-QB untouched; late scratch unresolved; no-price starter unresolved; snap leader unresolved; QB1 out passes the start to QB2; no depth chart falls back to the books; flag off. Suite 159 passed | pass |
| 9 | a held QB1 is never applied silently | a projected starter is never held unless the books price him; every other case is applied and printed as unresolved | pass |
| 10 | ship discipline | not merged. No week-4 lists exist yet, so merging changes no current number; first live use would be Thursday's PIT @ CLE window (books price Rodgers and Watson, so the cross-check has data) | pending |

**Decisions for the user before merge:** (a) accept criterion 3's two slot shifts as P48 effects (P48 stays open for
them), or hold P49 until P48 is fixed; (b) accept criterion 4's CHI miss as out of scope (depth order), or widen
the rule. Merge = `git merge p49-qb-hold` on main, then the next window refresh applies it; nothing to re-simulate.

---

## 2026-09-29 — P18 shipped at the week-4 boundary; re-validated against its original criteria

**Order at this boundary (one change at a time):** P50 (display only, 256a4bd) → **P18 (engine)** → P49 (next,
not yet shipped). Week 3 is final (16/16 graded) before any of it.

**Ship steps done:** merged `p18-per-yard-goal-line` into main (suite 149 passed); the library rebuilt as v6;
week-4 first pass on the v6 engine: `run_pipeline --sport nfl --model both --date 2026-10-01 2026-10-04 2026-10-05
--fresh-odds` → `simulate_nfl` (16/16) → `export_sims` → `ingest_props --fresh` (3/16 games posted) → `props` →
`ingest_td_props --fresh` (12/16) → `td_props` → `export_dashboard`. Odds quota 350. Week-3 props/TD files were
snapshotted first to `data/snapshots/wk3-props_2026-09-28/` (the pull overwrites them). Week 3 archives on the
first `export_sims` run after 06:15Z.

| # | Criterion (pre-set 9/25) | Re-validation 9/29 | |
|---|---|---|---|
| 1 | real states inside the 10, within 1.5 pp per bin with 100+ snaps | Rebuilt the real-state check (the 9/25 script wasn't kept): 10 of 11 bins pass; 1st & 0-2.5 .491 / .491. Same single miss: pooled 3rd/4th & 0-2.5 −1.96 pp (9/25: −1.85); 3rd alone +0.48, 4th alone −7.71 (identical), i.e. P45 (closed; reopen trigger unchanged). The rebuilt script counts 2,880 sub-10 1st downs vs 2,902, so small reconstruction differences are expected | miss, explained (as 9/25) |
| 2 | `--calibrate` sub-10 1st-down conversion within 3 pp | 20k sims on merged main: output **byte-identical** to the 9/25 validation run. .476 / .347 / .157 vs .486 / .329 / .163 | pass |
| 3 | TD share within 1 pp; FG made closer than .148; points within 0.3 | TD .219 vs .220; FG .149; points 22.38 vs 22.63 | pass |
| 4 | no other bin or drive outcome regresses > 1 pp; volume within 1% | vs the v5 run: worst bin change +0.40 pp (3rd & 10); drive outcomes ≤ 0.4 pp; pass/rush att +0.17% / +0.15% | pass |
| 5 | suite; sims and `BIAS_FIT` re-checked | Suite 149 passed. Week 4: stored v6 sims vs v5 re-simulated in memory (same inputs/seeds): median margin mean shift +0.00 (max 1.0, rounding of an anchored median), median total −0.44, props raw P(over) −0.45 / +0.22 / −0.05 / +0.15 pp (pass yds n=6 / rec yds / receptions / rush yds), anytime TD −0.24 pp. **`BIAS_FIT` needs no refit** | pass |
| 6 | ships only at a week boundary | after week 3 was fully graded, before any week-4 kickoff | pass |

**Week-4 first pass, noted (not P18 effects; provisional, no week-4 injury report yet):** one baseline flag, JAX @ CIN
(model JAX by 11.0 vs market CIN −2.5), which is all layer 1 (power rating −11.26), not injuries; KC @ LV carries
O'Connell 3.69 (the P48 pattern); IND @ WAS charges Jayden Daniels out (4.65) from the week-3 report.

---

## 2026-09-28 — MNF PHI @ CHI window (unattended run): a live P49 criterion-9 case on CHI's QB. Report only; nothing changed

**Run.** The watch (`run_sunday.py --watch --date 2026-09-28 --fresh-odds`) was restarted at 22:37Z after the earlier
session closed, and refreshed at 23:00-23:02Z: grade, injuries + inactives (2/2 lists posted at T-1.2 h), weather,
odds (quota 382), predict (baseline PHI by 2.9, ML PHI by 3.7, market PHI by 3.5; stored home margins -2.9 / -3.7; no flag), simulate, props (33 priced,
top 25), export. The ruled-out coverage check came to 11/14 = 78.6% (PASS). The TD lines were then re-pulled fresh for
PHI_CHI (30 players, quota 377) and re-ranked by hand (16 priced), and the dashboard was re-exported at 00:03Z.
Read-only re-checks every 5 min from 23:04Z to 00:03Z: **the ESPN lists never changed** (17 players, identical), so
no second refresh ran. The served numbers are the 23:02Z refresh.

**QB check (report only, P49 criterion 9 case, NEEDS A DECISION after grading):**
- Books price **Case Keenum** (CHI) and Jalen Hurts (PHI). The sim's CHI passer is **Tyson Bagent** (31 att), and
  PHI's is Hurts (30 att).
- CHI's list flags three QBs: Caleb Williams (on the final report as **out**, DNP, so genuine), **Case Keenum** and
  Miller Moss. Keenum and Moss are **not on the final injury report** and **were both on CHI's week-2 list**. Six of
  CHI's 7 names equal its week-2 list, which is the P49 carry-over signature. A priced starter is listed inactive
  (Keenum), so the sim starts Bagent, whom the books aren't pricing. CHI player props and CHI TD picks were ranked on
  a Bagent-QB sim.
- PHI: Andy Dalton (QB), Elijah Moore and Micah Morris are also listed but not on the final report, and all three were
  on PHI's week-2 list (R2 contradictions: 5 of 17).
- The served baseline charges Caleb Williams 5.58 (genuine) and **Cole Payton 2.10** (PHI QB, out on the ESPN report,
  snap share 0.35; that looks like the P48 prior-season-share pattern for a backup QB; not verified).
- Decision to record after grading: who actually started for CHI (Keenum or Bagent) scores this case for the
  QB-only rule's criterion 9 and the late-scratch question (criterion 2).
- **Early in-game read (00:22Z, 1st qtr 10:52):** live_tracker's live-resume box score has **Keenum as CHI's passer**
  (32 att projected), and Bagent only rushing. So Keenum appears to have started: the ESPN flag was a false P49
  carry-over, and the pregame CHI sim, props and TD picks used the wrong QB. Confirm from the final box score when
  grading.
- **Final (03:12Z): CHI 27, PHI 7.** Keenum played: a 41-yd TD pass to Kalif Raymond and a 1-yd TD run (live play log).
  **The pregame Keenum flag was a false P49 carry-over.** Criterion 9 would have held it as unresolved (priced QB
  flagged). Pregame favourite PHI by 2.9 (sim median PHI 23-20); CHI won by 20. **Graded 2026-09-29 03:19:57Z** (both models, 27-7 stored). Baseline leaned CHI +3.5: ATS W, SU
  wrong. ML leaned PHI: ATS L, SU wrong. **Week 3 final, 16/16 predicted and graded:** baseline SU 9/16, ATS 10-6;
  ML SU 8/16, ATS 6-10; no flagged edges. Only scoring plays are in the live play log: they show Keenum played, but
  can't clear or confirm the other R2 names (Moss, Dalton, E. Moore, M. Morris). Check the nflverse box score next
  refresh.

---

## 2026-09-28 — P42 closure corrected; QB-only precision rule is the leading P49 candidate (adoption criteria CONFIRMED by the user, with criterion 9 added)

**P42 correction.** P42 is **reopened** (see the tracker). Its 9/24 diagnosis concluded "the fault is in the feed, not
in our join or player matching", which treated ATL's list as a one-off ESPN feed error, and the fix shipped on that
basis (86cc3ed: reject a list with no active QB). **That diagnosis was wrong.** The P49 diagnosis shows the flag is
systematic: ESPN's pregame `didNotPlay` carries the prior week's inactives forward until they are cleared, and
Penix fits that signature exactly (on ATL's week-2 list, not on the final report, started). The no-active-QB rule
stays (an impossible list is still worth refusing), but it guards one symptom; the cause is P49's.

**Leading candidate for the week-4 boundary: the QB-only precision rule** (user decision 9/28; not built).
Definition: when a pregame inactive list flags a **QB** who is **not on that week's final injury report, or is on
it with no game status** (not out / doubtful / questionable / IR), the flag is **held**, not applied: he keeps his
report-based play probability, and the hold is logged by team and player and printed by `run_sunday`. Ruled-out QBs
are applied as now. Other positions are unchanged.

**Adoption criteria (confirmed by the user 2026-09-28, criterion 9 added by the user; nothing built or run yet):**
1. **Recall on real false flags, 100%.** Replay every stored 2026 list (weeks 1-3). Ground truth: ESPN's post-game
   roster plus nflverse play-by-play. Every QB flagged pregame who then played is held: at least Darnold, Murray,
   Sanders, DeVito, Jalon Daniels (week 3) and Penix (TNF), plus any found in weeks 1-2.
2. **No starter wrongly held.** Every genuine inactive QB the rule holds is a non-starter: not the books-priced QB,
   not the team's current-season snap leader. Week 3 had 15 such holds out of 34 genuine QB flags, all healthy
   backups; the replay lists each. **Limit (recorded at the user's request):** this criterion rests on three weeks
   of 2026 data. No genuine late scratch of a starter occurred in them, so the late-scratch case is **untested on
   real history, not proven safe**; criterion 9 exists to cover it.
3. **Served-number effect is explained.** Report the baseline and ML margin change per replayed game. Any change
   over 0.5 pts must trace to one of: a false starter flag removed, or a P48-type backup charge removed (e.g.
   Huntley, Rattler, O'Connell, Stidham). Anything else blocks adoption.
4. **Sim QB matches the books.** After the replay, the sim's QB1 equals the books-priced QB in every game where one is
   priced (week 3 today fails SEA @ WAS and MIN @ TB).
5. **Ruled-out QBs still applied, 100%.** Every QB with out / doubtful / IR on the final report stays applied.
6. **ML consistency.** The rule sits in `apply_inactives` (live path); `score_injuries` and the ML training features
   are unchanged. Confirm no historical feature moves.
7. **Tests.** Pin: Darnold / Murray / Penix held; a ruled-out QB applied; a healthy backup held and logged;
   non-QB flags untouched. Suite passes.
9. **A held QB1 is never applied silently (user addition).** When the rule would hold a team's projected starter
   (QB1), the hold is logged as needing review and cross-checked against the QB the books price for that game. If
   the books price a different QB than the one the rule would start, the hold is **unresolved**: reported, not
   applied (the flag stays as posted until reviewed). Test: a genuine late scratch, a starter flagged inactive, not
   on the final injury report, with the books pricing his backup, must come out unresolved and reported, never
   silently held.
10. **Ship discipline.** At the week-4 boundary with the other queued items, one change at a time, re-simulating
   only games not yet kicked off. Interaction to report: it removes the QB cases of P48, while P48 stays open for
   other positions and for the snap-share label.

The broader all-positions version (R2: 59/65 false caught, 29/204 genuine held) waits until the cost of a wrong
hold on a skill player (sim usage given to a healthy scratch) is measured.

---

## 2026-09-28 — P49 diagnosis results: ESPN's pregame `didNotPlay` carries the prior week's inactives forward; P42 reopened (same signature). Read-only; nothing changed

Against the criteria entry above. Sources: `inactives` (Supabase), nflverse 2026 week-3 play-by-play (independent of
ESPN), ESPN's post-game rosters (`fetch(include_final=True)`, nothing stored), the P42 pregame fixture.

**Q1 Read history: wrong from the first read, all 14.** Every one is on his team's list at that team's first stored
read (T-1.57 h or T-1.24 h), pregame. None was added later. Per-read contents are not persisted beyond
`first_seen_at` / last `pulled_at`, but the last-pulled times still tell something: Darnold, Pittman Jr. and Ty
Johnson were last upserted at 15:45Z, so the in-game re-reads no longer flagged them (the flag cleared after kickoff);
Sanders, DeVito (T+2.2 h) and Jalon Daniels (T+3.0 h) were still flagged in-game.

**Q2 Played: all 14 confirmed by nflverse play-by-play.** Darnold 45 dropbacks + 1 rush, Murray 32 + 2, Bowers 13
targets, Harvey 9, Flowers 7, Goodson 7, K. Miller 7, DeVito 6, Pittman Jr. 5, Ty Johnson 4, J. Daniels 4, Jennings 2,
Watkins 2, Sanders 1.

**Q3 P42 signature: match.** Penix was flagged pregame inside the gate, was not on the final injury report, and played
(started). He was also on ATL's week-2 inactive list, like every P49 player. **P42 reopened**: its no-active-QB rule
treats one symptom of the P49 mechanism.

**Q4 What the pregame flag represents: H2 (stale carry-over mixed with the real list) is supported.**
- (b) Carry-over: 183 of 247 week-3 pregame flags (74%) were on the same team's week-2 list, and 80% of week-2
  inactives were re-flagged. Of the 183 carried flags, **14 recorded an offensive touch and 57 were gone from the
  post-game list**; of the 64 flags new this week, **0 touched the ball and 2 were gone** post-game.
- (a) Post-game: of 288 stored pregame flags, 218 are still flagged on the post-game rosters, 70 were dropped, 7 are
  new; all 14 P49 players and Penix are unflagged post-game. So on finished games the flag tracks reality; pregame it
  is last week's list not yet cleared plus this week's.
- (c) Size: week-3 pregame lists ran 7-13 (median 9), above a normal gameday count, consistent with extras.
- (d) Payload: a roster entry carries only `didNotPlay`, `displayName`, `playerId`, `position`. **Nothing in the
  payload separates a stale flag from a real one**; only history (prior-week list) and the injury report do.
- Why P33's coverage test passed these lists: coverage measures recall (are ruled-out players listed?), and the real
  inactives are there; the defect is precision (extra players listed).

**Correction to my 9/28 status table:** Darnold and Harvey were **off** Sunday's final injury report. The "no status,
limited" rows I showed came from the stale 9/25 pull, not the final report.

**Q5 Replay of candidate precision checks** (week-3 Sunday lists, 269 flags; "false" = gone from ESPN's post-game
list, 65; "genuine" = still flagged, 204):

| Rule (hold for review instead of applying) | Holds | False caught | Genuine wrongly held | P49 caught | Precision after (before 76%) |
|---|---|---|---|---|---|
| R1 no game status + full/limited practice (as first proposed) | 0 | 0/65 | 0/204 | 0/14 | 76% |
| R2 not on the final report, or no game status | 88 | 59/65 | 29/204 | 11/14 | 97% |
| R3 on the prior-week list and not ruled out this week | 75 | 52/65 | 23/204 | 13/14 | 93% |
| R2 and R3 | 66 | 47/65 | 19/204 | – | – |
| QB only, R2 | 21 | 6/6 | 15/34 | Darnold, Murray, Sanders, DeVito, J. Daniels | – |
| QB only, R3 | 19 | 6/6 | 13/34 | same | – |

R1 holds nothing because a player who practises with no status drops off the final report entirely; the useful
version of the contradiction is R2 ("listed inactive but not on the final injury report"). Every genuine QB it
wrongly holds is a healthy scratch (QB3s; also Huntley, Rattler, Stidham, O'Connell), and holding a healthy backup
costs ~0, so for QBs the wrong holds are nearly free, and they would also remove today's P48 backup-QB charges.
The cost of a wrong hold elsewhere (a healthy-scratched RB/WR given usage in the sim) is not measured yet.

**Proposal for the week-4 boundary (not built; adoption criteria to confirm with the user):** apply a pregame
`didNotPlay` flag only when the player is ruled out on the final report or new since the prior week's list; hold the
rest (R2, QB first, then all positions), and log every held flag for review. Replay requirement before adopting:
weeks 1-3, false flags caught >= 90%, wrong holds measured by their effect on sim usage and graded margins.

---

## 2026-09-28 — P49 diagnosis: criteria (written before running; read-only, no fixes)

Scope: the 14 players stored as week-3 pregame inactives who recorded stats (P49 row). Nothing is written to any
table; outputs are read-only queries, the saved P42 fixture, ESPN reads and nflverse.

**Q1 Read history.** For each player: `first_seen_at` and last `pulled_at` from `inactives`, plus every other
recorded read of that team's list (run_sunday logs with per-team counts; the 15:18Z, 15:49Z, 18:53Z and 19:12Z
read-only checks). Classify **wrong from the first read** if he is on the list at the first recorded read of that
team; **changed between reads** if an earlier recorded read did not have him. Known limit, stated up front: the
table upserts `pulled_at`, so per-read list contents are not persisted; where a read can't be reconstructed, say so
rather than infer.

**Q2 Who played.** "Played" = at least one recorded stat or snap in week 3. Confirm each of the 14 in ESPN's
post-game box score and, where available, nflverse week-3 play-by-play. A player confirmed by neither is reported
as unconfirmed and dropped from the count.

**Q3 P42 signature.** Signature = flagged `didNotPlay` in a pregame read inside the P33 gate, **no game status** on
the official injury report, and **recorded stats**. If Penix (ATL, 9/24) meets all three, P42 is reopened and its row
records that P42 and P49 may share a root cause (P42's no-active-QB rule then treats one symptom).

**Q4 What the pregame flag represents.** Hypotheses: H1, a real inactive list with scattered ESPN errors; H2, a
placeholder/stale state (e.g. carried from the prior week, or "not yet active") mixed into the real list. Tests:
(a) post-game flags vs box scores (the flag should match reality on finished games); (b) overlap of each false flag
with the same team's **prior-week** inactive list (H2 predicts high overlap); (c) list size vs the NFL's gameday
inactive count (53-man roster, 48 active: lists well above ~7 carry extras); (d) any other roster-payload field that
separates false flags from true ones. Conclude only what the evidence separates; otherwise report "not separable".

**Q5 Proposal (week-4 boundary, not built).** A precision check, e.g. a player listed inactive with **no game status**
and **full or limited practice** is a contradiction and is held for review rather than applied (QB first). Report
its replay on every stored 2026 list: false flags it would hold (want: all 14 + Penix), genuine inactives it would
wrongly hold (want: ~0), and the resulting coverage. Criteria for adopting it to be confirmed with the user.

---

## 2026-09-28 — Week 3 Sunday graded (14 games); P49 logged: pregame inactive lists carried players who played, including two starting QBs

**Graded** (`grade --sport nfl --refresh`, ~04:05Z), then `export_sims` + `export_dashboard`. Week 3 so far,
15 of 16 games (ATL @ GB + 14 Sunday; **PHI @ CHI Monday night still to play**). Dashboard figures match an independent
recount from the predictions table:

| Model | Straight up | ATS | Flagged edges |
|---|---|---|---|
| baseline-v1 | 9/15 | 9-6-0 | none flagged (0-0) |
| ml-v1 | 8/15 | 6-9-0 | none flagged (0-0) |

Season to date (45 graded per model): baseline SU 24/45, ATS 18-26-1; ML SU 30/45, ATS 15-29-1. Finished game pages
show pregame projection vs actual (checked LA @ DEN in the browser).

**P49 (new, see tracker):** 14 players stored as pregame inactives recorded stats, including Darnold (SEA) and
Murray (MIN), whose teams' sims then started Drew Lock and Carson Wentz. 10.2 pts charged across 8 games for
players who played. Not changed (user decision); queued after MNF is graded.

**Needs a user decision:**
1. **Supabase `live_simulations` gap.** At 19:40Z a transient ReadError made `live_tracker` fall back to the local
   SQLite mirror for the rest of its run: 481 week-3 rows (19:40Z-03:53Z) exist only in `football.db`
   (`live_tracking` kept writing to Supabase). A whole-table `sync_to_supabase --tables live_simulations` would also
   push the stale mirror's old rows; the safe backfill is week-3 rows polled after 19:40:49Z only. Not run.
   **Done 2026-09-28 (user-approved, narrowly scoped):** dry run 481 candidates (week 3, polled 19:43:15Z-03:53:07Z),
   0 duplicate keys, 0 overlap with Supabase, all JSON decodes; backed up the full Supabase table (1,150 rows) and the
   local mirror to `data/snapshots/pre-backfill_2026-09-28/`; upserted exactly those rows. After: 1,631 rows (1,150 +
   481, so nothing was overwritten), week 3 1,074, 0 duplicate keys, all 481 present when matched on parsed timestamps
   (a string match found 423: Postgres trims trailing microsecond zeros).
2. P49 guard design (above). P33 refinement and P48 remain as logged 9/27.

**MNF set up (unattended):** `run_sunday.py --watch --fresh-odds --date 2026-09-28` started 04:1xZ (refresh 23:00Z);
`live_tracker` launches at 13:00Z (it exits immediately when no kickoff is within 12 h); after the refresh:
the TD step by hand, the list coverage check, and the QB/starter sweep (the P49 process fix). User added 9/28:
also report every listed-inactive player whose injury report contradicts the flag (R2: not on the final report or no
game status; plus whether the flag is carried over from week 2). Report only, change nothing.

Not touched: P18, P31, P30's re-check, P47, P48, P33 refinement.

---

## 2026-09-27 — 19:20 CDT window (LA @ DEN): lists genuine; a fourth live P48 backup-QB charge (nothing changed)

Scheduled `run_sunday` refresh 23:05-23:07Z, clean ("All windows done"; the watch then exited normally). Both lists
read at T-1.2 h (DEN 9, LA 9); 6/7 ruled-out players listed (miss: Jonah Coleman, an ESPN-IR / official-out row).
TD lines re-pulled and re-ranked by hand after the window (no TD step in `run_sunday`). Odds quota 389.

**P48 again:** DEN backup Jarrett Stidham is inactive and charged **3.18 pts** at a **2025** share of 0.53 (2 games
in 2025; 0 snaps in 2026, where Bo Nix has 100%). Served: **LA @ DEN base LA by 4.0** (ML: DEN by 1.9), market LA -1. Without the Stidham charge the baseline is ~LA by 0.9.
Added to the P48 row. Kickoff 00:20Z; not changed (user decision: nothing live today).

---

## 2026-09-27 — 15:05 CDT window: partial early lists re-read; P48 live on three backup QBs (NEEDS USER DECISION, nothing changed)

**Window refresh 18:52Z** (scheduled, clean). ARI @ SF and MIN @ TB lists read at T-1.19 h; BAL @ DAL and LV @ NO at
**T-1.52 h** and thin: 3/8 of those four teams' ruled-out players listed (Stanley BAL, Stukes LV, Durant DAL absent).
Read-only re-read at 19:12Z (T-73 min): all four lists had grown (+2 to +4 each, nothing dropped), coverage 7/8.
**Re-ran the window once** (`run_sunday.py --date 2026-09-27 --fresh-odds`, 19:12-19:15Z, clean; the 20:05Z games
unaffected: their lists were byte-identical). Second instance today of an early read (>= ~1.5 h) being partial;
see the noon-window entry: same decision on `LOOKAHEAD_HOURS` / a coverage storage gate.

Side finding (logged, not changed): the window-2 inactives fetch also re-reads games already **in progress** (state
"in" is not skipped, only "post"). It upserted the 9 noon games' rows (0 new rows, no prediction or sim of a started
game regenerated), so harmless today; `fetch` should skip started games.

**P48 is live, and bigger than the Porter case.** With the full lists, three backup QBs made inactive are charged as
starters, from **2025** snap shares; each team's 2026 starter has taken 100% of weeks 1-2 snaps:

| Team | Inactive QB | Share used (2025) | Charge | 2026 starter (100%) |
|---|---|---|---|---|
| LV | Aidan O'Connell | 0.82 | 4.92 | Kirk Cousins |
| NO | Spencer Rattler | 0.82 | 4.90 | Tyler Shough |
| BAL | Tyler Huntley | 0.59 | 3.56 | Lamar Jackson |

Served at 19:15Z: **LV @ NO base NO +10.4** (the two charges roughly cancel; estimate without them ~+10.4) and
**BAL @ DAL base BAL -2.3** (estimate without the Huntley charge ~BAL -5.9; ML `qb_loss_diff` 0.594 for BAL is the
same error). Earlier today LV @ NO +13.7 carried O'Connell at Q/0.25 (3.69 pts), the same defect.
**Correction:** the 9/27 morning report (and the LV note in the late-Friday entry) said O'Connell had "82% of LV's
2026 snaps". Wrong: that is his 2025 share; he has no 2026 snaps. Cousins has started throughout.
**Decision for the user:** nothing was changed (P48 is queued for the week-4 boundary). Options: leave as served and
fold into P48 (a QB with zero current-season snaps whose team's starter is healthy should carry ~0 charge), or
label BAL @ DAL / LV @ NO. Both games kick off 20:25Z, before the user is back, so this is for the record and P48.

---

## 2026-09-27 — Noon-window inactives: 15:18Z lists were stale; 15:45Z lists genuine (P33 time gate + content bar both pass)

Read-only checks (`ingest_inactives.fetch`, nothing stored by the check) around the 10:45 CDT `run_sunday` window.

| Read | Lead | Teams returning a list | Ruled-out players on the lists | P33 content bar (>= 40%) | Verdict |
|---|---|---|---|---|---|
| 15:18Z (pre-refresh probe) | T-1.70 h | 18/18 | 11/43 = **25.6%** (≈31% excluding IR) | fail | stale: Daniels (WAS) and Simmons (KC) absent, KC list 2 names |
| 15:45Z refresh stored / 15:49Z re-check | T-1.18 h | 18/18, 0 rejected (P42) | 51/65 = **78.5%** | pass | genuine; 172 rows stored, matching posted counts |

**Finding for P33:** the lead-time gate alone (<= 2 h) would have accepted the 15:18Z stale lists: 1.70 h is inside
the gate but before the ~T-90 min posting. P33's validation covered <= 1.58 h (genuine) and >= 2.5 h (stale) only.
The scheduled `run_sunday` trigger (T-75 min) is safe; an early manual run between T-2 h and ~T-90 min is not.
**Needs a user decision (not changed today):** tighten `LOOKAHEAD_HOURS` toward 1.5 h, or add the ruled-out
coverage check as a storage gate. The 14 misses at 15:49Z are expected: 7 IR players (never on a gameday list:
Hancock, Pipkins, Cherelus, Harper, Pierce, Iosivas, Hutchins), 2 P43 name duplicates whose twin is listed
(Francisco Mauigoa, Rob Beal Jr.), and 5 others (Stewart, Hummel, Dunker, Charbonnet, Schooler).

Also: `run_sunday` has no anytime-TD step; TD lines were re-pulled (`ingest_td_props --fresh`) and re-ranked by
hand after the window (15:50Z, 15/15 games). Odds quota 446.

---

## 2026-09-27 — Late Friday refresh + Sunday pre-game update; P43/P44 re-check; game explanations added (display only)

**Friday refresh had not run** (every table's latest `pulled_at` was the 9/25 00:07-00:09Z TNF catch-up; ATL @ GB
ungraded). Run 2026-09-27 06:35-06:48Z (Sun 01:35 CDT, i.e. late Saturday night). Pre-refresh state: `data/snapshots/pre-sunday_2026-09-27/`.
Steps: `run_pipeline --sport nfl --model both --grade --fresh-odds --date 2026-09-27 2026-09-28` (nflverse, weather,
odds, injuries + depth charts, grade, both models) -> `simulate_nfl --upcoming-only` -> `ingest_props --fresh` ->
`ingest_td_props --fresh` -> `props` -> `td_props` -> `export_sims` -> `export_dashboard`. Odds quota 98 -> 23.

- **Graded:** ATL @ GB (ATL 35-14). 31 NFL games per model. Baseline ATS 9-21-1, ML ATS 9-21-1.
- **Injuries:** official Friday designations, 32/32 teams, 184 rows, 81 out. No inactive lists (gate opens T-2h).
- **Re-predicted (15 games), no value flags.** Biggest moves: TEN @ NYG +7.2 -> +4.5 (Dart on IR now counts, P40),
  SEA @ WAS -13.4 -> -16.4 (Daniels out), LV @ NO +11.4 -> +13.7 (O'Connell questionable/DNP, 0.25), PHI @ CHI
  -2.1 -> -4.2 (Caleb Williams out). Anchor drift after the re-sim: 0.000 on all 15.
- **Impossible-state sweep: none.** Every sim QB1 is the QB the books price (Mariota WAS, Bagent CHI with Keenum
  6 att, Winston NYG, Cousins LV). No out/IR player gets touches in any sim.
- **P44 re-check:** Stevenson (CHI) **self-cleared** (CHI now on the official report only). **Jack Jones (SF) did
  not**: still an ESPN questionable at 0.55 with no official row behind it. Kiko Mauigoa's ESPN row is now `out`
  (updated, no longer stale), which moves him from P44 to P43 only. So P44 is timing for 2 of 3 rows, code for 1.
- **P43 re-check: not cleared, and the class is bigger.** Mauigoa is now charged twice at play prob 0 (nflverse
  Francisco out + ESPN Kiko out). Three more nickname pairs are live on this slate: Rob / Robert Beal Jr. (MIA DE,
  0.63 + 0.53), JuJu / Julius Brents (MIA CB) and Hollywood / Marquise Brown (PHI WR, 0.46 + 0.29). Not fixed
  (standing decision: no mid-week change); each is labelled on its game's explanation.
- LV note for the record: O'Connell is charged 3.69 at 0.25; the sim and the books both start Cousins. **(Corrected
  later 9/27: the 0.82 share is his 2025 share, not 2026; he has no 2026 snaps. This is P48, a data error; see the
  15:05 CDT window entry.)**

**New, display only: a "why the model leans X" note per game** (`src/game_explain.py`, called from
`export_dashboard`; `--no-explain` skips it, and `run_sunday --no-explain` passes through). It changes no number.
Guards, each covered by `tests/test_game_explain.py`:
- the factors (rating gap, home field, rest, travel, injuries, weather compression) must add back to the served
  baseline margin within 0.05, or the game gets no note; all 15 reconcile today
- every figure in Claude's text must appear in its inputs (as given or rounded), or the note is dropped and retried
  once for that game only
- games that have kicked off get no note
- factors are handed to Claude as "X toward TEAM", not signed home-team numbers: the first draft's signed input
  produced a wrong-direction claim on PHI @ CHI (rating gap "favours the Bears"; it is 1.3 toward PHI)
- caveats are built in code: rating is ~90% prior season and **not opponent-adjusted** (P22 is still proposed, so the
  notes never call it opponent-adjusted); generic QB charge (named player); flat-55% questionables (named);
  possible P43 duplicate pairs; any `KNOWN_GAME_ISSUES` text
Manual check of today's 15 notes: every player status stated matches its input (31 named players); the guard
dropped one note (KC @ MIA, cited 2.7) and the retry passed. Cost today ~$0.21 across the drafts; a re-export with
unchanged numbers is cached and free.

**Logged later 9/27 from the CIN @ PIT injury read (not built; queued for the week-4 boundary with P18/P31):**
**P47** (final-day practice status only; Dean DNP -> LP -> LP stored as `limited`) and **P48** (Porter charged at his
2025 snap share 0.946 with no 2026 snaps, unflagged). Also fixed that day, text only (3f25fdf): the explanation's
"flat 55% default" caveat had been attached to questionable + limited-practice players, whose 0.55 comes from the
practice table; it now fires only with no practice report. Export diff: 5,752 numbers identical.

**Not touched (blocked until MNF is graded):** P18, P31, P30's re-check, receiving-bias pass.

---

## 2026-09-25 — P46 results: neither scheme feature set adds out-of-sample value. Closed by the pre-set rules; nothing promoted

Run: `python -m research.scheme.walkforward calibration/2026-09-25_p46_scheme_walkforward.md` (full tables
and per-season coefficients are in that file). Criteria and outcome rules are from the "P46 scoped" entry
below, written before this ran.

**Gate.** The baseline was re-assembled from P37's own `ratings()` / `situational()` to keep game ids. It
reproduces P37's `replay()` exactly on all 2,661 REG games 2016-2025: identical edges, max difference 0.0.

**Feature sanity.** 32 teams every season; plausible ranges (pressure about 25-30%, play-action about 21%,
box 6.5-7.0, motion rising league-wide from 0.38 in 2022 to 0.52 in 2025). A team's week-1 value
correlates 0.76-0.95 with its prior-season value (0.42 for FTN box on runs). The null result below isn't a
construction bug.

| | Set A, participation, test 2019-25 (n=1,881) | Set B, FTN, test 2023-25 (n=816) |
|---|---|---|
| margin MAE, baseline → + term (pooled) | 10.577 → 10.599 (**−0.022, worse**) | 10.631 → 10.672 (**−0.041, worse**) |
| 2025 MAE gain | +0.040 | −0.057 |
| seasons improved | 4 of 7 | 1 of 3 |
| Brier (pooled) | 0.2294 → 0.2302 (worse) | 0.2302 → 0.2310 (worse) |
| ATS, baseline → + term | 910-928 → 914-924 | 383-414 → 388-409 |
| corr(term, cover residual) | +0.009, p 0.34 | +0.035, p 0.16 |
| corr(total term, total residual) | −0.001, p 0.52 | +0.026, p 0.23 |
| total MAE, market → + term | 10.371 → 10.383 (worse) | 10.121 → 10.149 (worse) |

**Criteria.** Both sets **fail S1, S2, S3, E1, T1 and T2.** Both "pass" only E2, E3 and T3, the sign-only
checks, by margins a coin flip produces (ATS +4 and +5 wins on 1,838 and 797 decisions). By the outcome
rule, fail-everything on the criteria that carry weight means: **P46 closes as "no out-of-sample value".**
Set B does not become a tracking layer, and nothing is computed weekly.

**Reading the coefficients** (in the results file). Set A's largest weight is defensive pressure, at a
stable −0.9 to −1.3 points per SD. Its sign runs *against* the intuition (more home pressure, lower
residual), which reads as overlap with the defensive EPA already in the baseline rather than new
information. Set B's weights swing between seasons (motion +1.37 → −0.13). Both patterns fit "the EPA
ratings already carry what these rates know."

**What this doesn't rule out.** Coverage-shell features, route-level data and player-level scheme
(receiver usage by personnel grouping for props) were out of scope by design. The one live-capable source
(FTN) gives only three test seasons, so its test is weak: its CIs are wide, not tight around zero. A props
angle (target share by personnel) is a different question from game margins. It would need its own scope,
and would sit next to P31 / the receiving residual, not here.

**Where things stand.** Code stays in `research/scheme/` for reference. `tests/test_research_isolation.py`
keeps `src/` and the pipeline entry points from importing it. Raw pulls are cached in
`data/cache/research/` (gitignored). Nothing live changed.

---

## 2026-09-25 — P46 scoped: a scheme / formation research layer. Data diagnosis, design and pass criteria (written before running)

**Constraint set by the user.** A separate, **non-live** research layer from day one. It must not touch any
live prediction, simulation or prop until it is walk-forward validated and shown to help, the same bar P39
was held to. The architecture idea comes from a reference project (Alphakiller1/nfl-model, which has no
licence; studied for ideas only, nothing copied). Its own scheme module is likewise unproven and kept out of
its live model.

### 1. Data diagnosis (real pulls, 2026-09-25)

Read straight from the nflverse release files, the same files `nflreadpy.load_participation` /
`load_ftn_charting` read. `nflreadpy` isn't installed and isn't needed; `nfl_data_py` 0.3.3 has
`import_ftn_data` but no participation loader.

**Participation (`pbp_participation_{season}`): published 2016-2025; 2026 returns 404.** The 2025 file
appeared 2026-02-10, so it is post-season only. Joined to our play-by-play on (game_id, play_id): **100% of
pass/run snaps join** in every season. Fill on scrimmage snaps:

| field | 2016-17 | 2018-22 | 2023-25 |
|---|---|---|---|
| offense / defense personnel | 1.00 | 1.00 | 1.00 |
| offense formation | 0.99 | 0.99-1.00 | 1.00 |
| defenders in box | 0.999 | 0.999 | 1.00 |
| pass rushers (dropbacks) | 0.96 | 0.99 | 1.00 |
| was_pressure (dropbacks) | 0.90 | 0.89 | 1.00 |
| route (dropbacks) | 0.89 | 0.85-0.87 | 0.85 |
| man/zone, coverage type (dropbacks) | **0** | 0.89 | 1.00 |

**Format changes in 2023** that any feature must normalise across:

- Personnel strings change from "1 RB, 1 TE, 3 WR" to "1 C, 2 G, 1 QB, 1 RB, 2 T, 1 TE, 3 WR". Counts of
  RB / TE / WR are stable; the strings are not.
- Formation goes from 7 labels (SHOTGUN, SINGLEBACK, I_FORM, EMPTY, PISTOL, JUMBO, WILDCAT) to 3 (SHOTGUN,
  UNDER CENTER, PISTOL). Only shotgun vs not is comparable.
- Route names change vocabulary ("GO", "HITCH" becomes "HITCH/CURL", "QUICK OUT"), so they aren't
  comparable across 2023 without a mapping.
- `was_pressure` becomes filled (False) on runs from 2023.

**FTN charting (`ftn_charting_{season}`): 2022-2026 only; 404 for 2016-2021.** Complete where present:
play-action, motion, screen, RPO, no-huddle, box count, blitzers, pass rushers, QB out of pocket, QB sneak,
drops. **2026: weeks 1-2, 32 games, pulled 2026-09-23 21:03Z**, consistent with the ~48 h lag. FTN has no
personnel grouping, no pressure flag and no coverage.

### 2. What can be live, and what cannot

- **Participation can't feed live predictions.** At most, last season's values could act as a stale prior.
- **FTN is the only live-capable scheme source.** It covers: box count (a substitute for
  `defenders_in_box`), pass rushers and blitzers, play-action, motion, screens, RPO, no-huddle. It can't
  substitute for personnel groupings, pressure or coverage.
- Shotgun and no-huddle are already in live play-by-play (`shotgun`, `no_huddle`), so they need neither
  source.
- **Consequence for validation:** FTN starts in 2022, so FTN features can't be walk-forward tested on
  2019-2025. Their test seasons are **2023-2025**: the 2022 features are built from the current season only,
  since there is no prior FTN season. Participation features are tested on 2019-2025 as asked.

### 3. Design: small, team-level, leak-free

Every feature is a per-team rate built exactly as Layer 1 builds a rating as of week w: that season's
REG-season snaps before week w, blended with the prior season regressed ×0.75, with current-season weight
n/(n+900). A matchup feature is home minus away. Standardised on training seasons only.

- **Set A, participation (historical only), test 2019-2025:**
  - A1 offense heavy-personnel rate (≥ 2 TE or ≥ 2 RB)
  - A2 offense pressure-allowed rate (dropbacks)
  - A3 defense pressure rate (dropbacks)
  - A4 average box faced on the offense's runs
- **Set B, FTN (live-capable), test 2023-2025:**
  - B1 offense play-action rate
  - B2 offense motion rate
  - B3 defense blitz rate (dropbacks with n_blitzers > 0)
  - B4 defense average box on runs

No coverage-shell classification (man/zone, Cover 0-6); that is out of scope to start.

**Model.** For each test season, OLS on training seasons only (every earlier season with features) of the
residual `actual margin − baseline margin` on that set's matchup features. The baseline is **P37's exact
replay** of live Layer 1 plus HFA/rest/travel/wind (no injury term, as in P37 and P39). The line is nflverse's
near-close `spread_line`. **Totals:** the live baseline has **no total model** (it passes the market total
through), so there is no "baseline total MAE". The totals test is an edge test: OLS of `actual total − market
total` on the sums (home + away) of each set's features.

### 4. Pass criteria (each set judged separately; all must hold)

**Margin, accuracy (as P39 phase 2):**

- **S1:** walk-forward margin MAE improves by **≥ 0.10 pts** pooled over the test seasons **and** in 2025.
- **S2:** it improves in **≥ 5 of 7** test seasons (set A) or **≥ 2 of 3** (set B).
- **S3:** win-probability Brier (normal, the live NFL margin sigma) is not worse, pooled.

**Margin, edge against the line (as P39 phase 1):**

- **E1:** pooled corr(term, cover residual) > 0 at one-sided p < 0.05.
- **E2:** pooled ATS of the lean with the term added is not below the baseline's.
- **E3:** 2025 corr(term, cover residual) > 0 (sign only).

**Totals (edge only):**

- **T1:** pooled corr(total term, actual − market total) > 0 at one-sided p < 0.05.
- **T2:** pooled MAE of (market total + term) beats the market total by ≥ 0.10.
- **T3:** 2025 sign positive.

**Multiple tests.** Two sets × two targets. A single marginal pass (p between 0.0125 and 0.05) is reported as
such, not as evidence.

**Outcome rules.**

- Fail everything: P46 closes as "no out-of-sample value", and the code stays in `research/` for reference.
- Pass on set A only: a historical finding with no live path (participation is post-season). Recorded, not
  promoted.
- Pass on set B: it becomes an **unpromoted research layer**, flagged unvalidated like the baseline flags.
  It is computed weekly from FTN for tracking only and fed into nothing, until it holds over several real
  weeks under criteria set in advance.

**Isolation.** Code in `research/scheme/`. Nothing in `src/` imports it, and a test asserts that. Raw pulls
go to `data/cache/research/` (gitignored with `data/`).

---

## 2026-09-25 — P45 closed as not supported; reopen trigger set

User decision: no change to the engine. Before the trigger was recorded, the matched inside-10 gap was split
by season, since the +6.2 pp above is pooled over 2023-25 (same method: each 4th & 1-2 attempt against
the 3rd-down rate at its exact yard line and to-go; bootstrap 90% CI):

| season | n | gap | 90% CI |
|---|---|---|---|
| 2016 | 62 | −4.1 | [−15.3, +7.5] |
| 2017 | 54 | −4.6 | [−15.2, +6.5] |
| 2018 | 74 | +1.4 | [−8.2, +10.8] |
| 2019 | 64 | +4.8 | [−6.4, +16.3] |
| 2020 | 92 | −3.3 | [−12.0, +4.9] |
| 2021 | 101 | +4.5 | [−4.2, +13.3] |
| 2022 | 84 | −5.0 | [−14.5, +4.1] |
| 2023 | 84 | +5.7 | [−3.5, +14.7] |
| 2024 | 73 | +9.8 | [+0.1, +19.4] |
| 2025 | 118 | +7.5 | [−0.5, +15.1] |

2023-25 is the longest same-sign run in the ten seasons (before it: at most two in a row, 2018-19). A single
season's CI is about ±9 pp, so the trigger reads the sign of the run, not any one season's size.

**Reopen trigger:** 2026's gap, measured this way after the 2026 regular season, comes in **positive**,
making four straight seasons (2023-26) in the same direction. If it does, P45 reopens with the walk-forward
test described in the diagnosis entry as its first step.

---

## 2026-09-25 — P45 diagnosed: the 4th-down goal-line gap is not stable across seasons. Nothing built

**Question.** Should 4th-and-short inside the 10 stop borrowing the 3rd-down pool? P45 was logged from the
P18 validation: 4th & 1-2 inside the 10 converts .633 real (2023-25, n=275) against the engine's .556,
which draws from the 3rd-down pool at the same spot.

**Data available** (go attempts, no-play penalties excluded; conversion = to-go gained or TD):

- 4th & 1-2 inside the 10: **275 attempts in 2023-25** (the engine's library seasons; 231 outside the
  late-game rule), **807 in 2016-25**.
- By yard line over all 10 seasons: the 1 has 329 and the 2 has 150; every other yard line has **31 to 49**.
  A 4th-down pool on P18's per-yard cells (50-play minimum) would exist only at the 1 and the 2, and only by
  reaching back to 2016. Older seasons carry a different go-for-it environment. **A direct 4th-down pool is
  not supportable.**

**Is there a 4th-down effect to model?** Each real 4th-down attempt was compared with the 3rd-down conversion
rate at its exact yard line and to-go (inside the 10), or its field band and to-go (outside), with a
bootstrap 90% CI:

| window | inside the 10 | outside the 10 |
|---|---|---|
| 2016-22 | **−2.2 pp** [−5.9, +1.2], n=532 | −1.7 [−3.5, +0.2], n=1,830 |
| 2023-25 | **+6.2 pp** [+1.3, +10.9], n=275 | −0.1 [−2.5, +2.2], n=1,125 |
| 2016-25 | **+0.6 pp** [−2.3, +3.2], n=807 | −1.1 [−2.5, +0.3], n=2,955 |

- **Outside the 10 there is no 4th-down effect** in any window: 4th and 3rd convert alike at the same spot.
- **Inside the 10 the sign flips between windows.** The 2023-25 gap that P45 was logged on (+6.2, CI
  excluding zero) follows seven seasons at −2.2. Pooled over ten it is +0.6 with a CI spanning zero. That is
  either a recent regime change or a noisy three-season window; this data can't separate them.
- Unmatched raw comparisons overstate it. The logged ".633 vs .540" compares 4th downs with a 3rd-down mix
  at different spots; matched, the recent gap is +6.2, not +9.3.
- Year by year, the 4th-minus-3rd gap for 4th & 1-2 anywhere on the field runs −4.4 to +5.7 pp (2016-25).
  The last three seasons are +2.7, +3.7 and +2.0.
- **Stakes.** About 92 goal-line 4th & 1-2 attempts a season league-wide, about 0.17 a game. Even taking
  the 2023-25 gap at face value, the effect on scoring is about 0.07 points a game.

**Candidate fixes, weighed:**

1. **Own 4th-down pool:** rejected on sample size (above).
2. **A conversion uplift for 4th & short inside the 10** (the 3rd-down pool, reweighted toward successful
   plays until it matches an estimated gap): possible, but the gap to target is not stable. Used only if a
   walk-forward shows that a trailing estimate predicts the next season better than no uplift.
3. **No change:** the engine already matches real 4th-down conversion everywhere outside the 10, and inside
   it the long-run gap is +0.6 pp.

**Decision needed before anything is built.** Proposed walk-forward (criteria to be written here first if
chosen): for each test season 2019-2025, estimate the matched inside-10 gap from the three prior seasons,
apply it to the 3rd-down spot rates, and score that season's real 4th & 1-2 attempts inside the 10 (Brier)
against no uplift. Adopt only if the uplift wins pooled **and** in at least 5 of the 7 seasons. On the
windows above it would likely fail: a trailing estimate going into 2023 is negative.

---

## 2026-09-25 — P18 built: per-yard sampling inside the 10. Validated; held on a branch for the week-4 boundary

**Change** (branch `p18-per-yard-goal-line`, pushed, not merged; `main` still runs library v5):

- `sim_data.ZONE_EDGES`: each yard line 1-10 is its own zone, then 11-20, 21-50, 51-80, 81-99 (14 zones,
  210 buckets). `TABLES_VERSION` 5 to 6, so the two engines' cached libraries never collide.
- **Thin-cell rule.** A goal-line cell needs 50 plays (150 elsewhere). One short of that borrows **only
  from inside the 10**, with the existing cost ordering: distance first, then yard line, then down. The
  yard line is what has to match, since conversion is tested against the real to-go while yardage and TD
  come from the spot the play was run from. All 16 thin cells in use borrow **at the same yard line**, e.g.
  2nd & 1-2 at the 5 (16 plays) from 2nd & 3-5 at the 5 (259), and post-penalty 1st & 3-5 at the 7 (3
  plays) from 1st & 6-9 at the 7 (297).

**Criteria** (pre-set in the P18 scope entry above):

| # | Criterion | Result | |
|---|---|---|---|
| 1 | at real states inside the 10, within 1.5 pp in every down × distance bin with 100+ snaps | 10 of 11 bins pass, most at ≤ 0.6 pp (1st & 0-2.5: .491 / .491). **Miss: pooled 3rd/4th & 0-2.5, -1.85 pp.** Split: 3rd down **+0.63** (was +3.42), 4th down **-7.71** (was -4.87). 4th downs are drawn from the 3rd-down pool by design; the old cross-spot bias was partly offsetting that. Logged as **P45** rather than widened into P18 | **miss, explained** |
| 2 | calibrate: 1st-down conversion within 3 pp, sub-10 bins | .476 / .347 / .157 vs .486 / .329 / .163 (−1.0 / +1.8 / −0.6) | pass |
| 3 | TD share within 1 pp; FG made closer than .148; points within 0.3 | TD .219 vs .220 (TDs/team 2.511 vs 2.513); FG made .149 (closer by 0.1 pp only; the FG deficit is the known late-half clock issue); points 22.38 vs 22.63 (−0.25, was +0.01) | pass (points and FG noted) |
| 4 | no regression over 1 pp in any other bin or drive outcome, or over 1% in volume | every other bin within 1 pp, most closer to real; drive outcomes within 0.4 pp; pass/rush attempts +0.2% | pass |
| 5 | suite; stored sims and props `BIAS_FIT` re-checked | 139 pass (two tests had hard-coded the 6-zone layout and now compute it; new check: each yard line 1-10 gets its own bucket). **No "stored-sim fingerprint" tool exists**; the criterion was written assuming one. Substituted: the 15 upcoming week-3 games simulated in memory on the new engine vs their stored sims, same inputs and seeds. Median margin unchanged (anchored); median total −0.4; props mean raw P(over) moves −0.22 / −0.15 / −0.05 / −0.08 pp (pass yds / rec yds / receptions / rush yds), so **`BIAS_FIT` needs no refit**; anytime-TD mean −0.20 pp (19.86% to 19.65%), toward the market | pass (substituted check) |

**Ship steps, week-4 boundary (on or after 09-29, after week 3 is graded).** Merge the branch; the first
run rebuilds the library as v6. Then `simulate_nfl` for week 4, `export_sims`, `props` and `td_props`.
Nothing in `BIAS_FIT` changes. It ships alone or alongside whatever else lands at that boundary; record
the order if more than one engine change goes in.

---

## 2026-09-25 — P18 re-diagnosed: the goal-line "under-conversion" was a measuring error; the engine over-converts inside the 10. Fix scoped, not built

**Starting point.** P18 (09-16, with PENALTY_REPLAY off): 1st & 0-2.5 converts .323 in the sim against .486
real, plus the other two sub-10 bins, and sim TD share .196 against .220.

**Step 1: re-measure on today's engine** (PENALTY_REPLAY on since 09-19), `--calibrate`, 20k sims:
1st-down conversion .315 / .278 / .119 against real .486 / .329 / .163. **TD drive share .223 against .220,
so the second half of P18's test already passes.** The penalty fix closed it.

**Step 2: the diagnostic is at fault.** Both sides test conversion as yards ≥ to-go, but the sim side reads
the library's `net_yards` (yard line minus the *next* play's spot). For 432 of 4,071 library offensive TD
plays (10.6%) the next play is a try from a spot other than the goal line, so the stored yards fall short
of it: median 2 short, worst 20. The engine scores these plays on their TD flag, so it is unaffected, but
the diagnostic counted them as failed conversions. Real play-by-play records a TD as the full distance.
Fixed in the tracking code only (`simulate._scrimmage`, `track_drives` block: a TD counts as the full
distance). Every non-diagnostic calibration line is identical before and after.

**Step 3: corrected numbers.** The sign flips:

| 1st & | sim | real | gap |
|---|---|---|---|
| 0-2.5 | .532 | .486 | **+4.6** |
| 2.5-5.5 | .379 | .329 | **+5.0** |
| 5.5-9.5 | .194 | .163 | **+3.1** |

2nd & 0-2.5 (+3.1) and 3rd-down short yardage are also a little high. This fits the drive outcomes: TD .223
vs .220 and FG made .148 vs .158, meaning red-zone drives that should kick finish as TDs.

**Step 4: the mechanism.** Every real snap inside the 10 was scored two ways: its own outcome, and the
probability that a play drawn from its engine bucket converts at that spot.

- **At the play's own spot the engine agrees with reality on 2,902 of 2,902 sub-10 1st downs.** Yardage,
  penalties and TD logic are all consistent.
- Drawing across spots inside a bucket gives .534 / .380 / .194, the calibration gap exactly, so the sim's
  field-position mix is not the cause.
- The cause is `otd = off_td | (new <= 0)` applied **away from the spot the play was run from**. A 1-yard
  TD from the 1 drawn at the 2 still scores on its flag, and a 1-yard gain from the 2 drawn at the 1 scores
  on yardage. "TD if it would have scored at either spot" is biased upward, and the goal-line zones are
  wide (1-5 and 6-10).
- **Scoring on yardage alone is not a fix.** Crediting a TD play with exactly its distance to the goal
  under-converts by 6-8 pp (1st & 0-2.5: .416 vs .491), because a TD's yardage is capped at the goal line,
  so what it would have gained from a deeper spot is unknowable. Reality sits between the two rules.
- **Also noted, and inert today:** the 432 short-stored TD plays are a library data defect. The engine never
  reads their yards because the flag decides, but any rule that scores on yardage would inherit it.

**Proposed fix: exact-spot sampling inside the 10.** Give each yard line from 1 to 10 its own zone, so a
drawn play always comes from the spot it is applied at, and each draw matches reality by construction.
Library counts per (down, distance bin, yard line) over 2023-25: 62 cells populated, 50 with 30 or more
plays, and the 12 thin cells hold 171 of 8,315 plays. Many cells fall below today's `MIN_BUCKET_PLAYS =
150`, so the borrowing rule inside the 10 needs its own design: the nearest yard line at the same down and
distance before any change of distance, and a lower minimum there. That is a build decision, recorded here.

**Adoption test (pre-set):**

1. At real states inside the 10, engine conversion within **1.5 pp** of real in every down × distance bin
   with 100+ snaps.
2. `--calibrate` on the corrected diagnostic: 1st-down conversion within **3 pp** of real in each sub-10
   bin (P18's original test).
3. TD drive share within 1 pp of real; FG-made share closer to real than .148; points per team within
   0.3 of real.
4. No regression over 1 pp in any other down × distance bin or drive outcome, and none over 1% in team
   pass or rush volume.
5. Suite passes; the stored-sim fingerprint and the props `BIAS_FIT` re-checked (an engine change moves
   every simulation).
6. **Ships only at a week boundary.** It is an engine change: re-sim, `export_sims` and a props re-rank
   follow, so it goes after week 3 is graded (MNF 2026-09-28), never mid-week (standing rule).

---

## 2026-09-25 — P40 built: ESPN IR now applies over an unlabelled nflverse row. Validated, not shipped

`ingest_injuries.merge_feeds(nfl_rows, espn_rows)` now does the merge `run` used to do inline, with the
IR exception scoped in the entry below. `run` prints how many IR designations were applied and each
conflict it kept on nflverse.

| Criterion | Result | |
|---|---|---|
| 1. every changed row is None to `ir` | Both payloads (00:05Z and 10:05Z) against the week-3 nflverse report: **2 rows changed, both None to `ir`**. **Jaxson Dart** (NYG QB): ESPN says "officially placed on injured reserve Thursday" (9/24 20:44Z); nflverse's Wednesday report has him DNP with no status, so today he is charged at 0.6. **A.J. Terrell Jr.** (ATL CB): placed on IR Tuesday (9/22 17:09Z); same situation | pass |
| 2. no row with a status loses or changes it | 0 of 221 / 217 merged rows. 0 conflicts on either payload | pass |
| 3. live effect per team | **NYG −2.91 to −4.93 injury points (2.02)**, which moves TEN @ NYG on its next re-predict. ATL −7.34 to −7.85; ATL @ GB is final and is **not** re-predicted | reported |
| 4. Adebo pinned; conflict tested; suite passes | `test_espn_ir_overrides_an_unlabelled_nflverse_row`: Adebo applied with nflverse practice, position and snap share kept; an official status is kept over IR and reported; other ESPN statuses still defer; ESPN-only rows added as before; inputs not mutated. 139 passed | pass |

**Notes.**

- Training is unaffected. `build_training` scores history from nflverse alone, with no ESPN rows, so no
  retrain is needed and the training/live rule is untouched.
- Dart's 2.02 is the QB-slot charge: his snap share makes him NYG's charged QB even though Winston started
  week 2. That is the generic starter-charge question (P2 / P28 part 2 / P39), not P40's. P40 only makes his
  IR status count.
- Tonight's ATL @ GB carried the same miss: Terrell at 0.6 rather than 0, about 0.5 pts, on top of P42.
  The game is final and is recorded here, not re-run.

---

## 2026-09-25 — P40 scoped: an ESPN "Injured Reserve" designation overrides nflverse only where nflverse gives no game status (criteria written before running)

**Why now.** ESPN's site.api injuries endpoint is answering again: HTTP 200 at 10:05Z today, 32 teams, 26 IR
rows. It had been failing since 09-20, and tonight's 00:05Z pull also succeeded. That makes P20's IR
handling live, so P40's masking now has effect.

**The rule (precedence per field, not per player).** When both feeds cover a player
(`player_key(team, name)`):

- ESPN `ir` + nflverse **no game status** (`status` None, whatever the practice level): the merged row takes
  `status = "ir"`, play prob 0, and keeps nflverse's `practice_trend`, `position` and snap share. IR is a
  roster fact, and the official weekly report doesn't carry it.
- ESPN `ir` + nflverse **with a game status** (out / doubtful / questionable): **nflverse kept, conflict
  printed.** A current official designation is newer evidence than an ESPN IR flag, which can be stale
  after an activation. This is the P44 staleness in another form.
- Every other ESPN status where nflverse covers the player: nflverse kept, as today.

**Adoption test** (all must pass):

1. On both ESPN payloads available (00:05Z and 10:05Z on 2026-09-25) against the week-3 nflverse report,
   every changed row is **None to `ir`**, and the count is reported.
2. **No row that has a status today loses it or has it changed.** Zero tolerance.
3. The live effect on the week-3 injury term is reported per team, in points.
4. The 09-18 NYG Adebo case is pinned in a unit test. That payload has since been overwritten in the cache,
   and Adebo is absent from both current payloads, so the case can no longer be replayed from real data.
   The conflict case gets its own test. Suite passes.

---

## 2026-09-25 — P42 built: an inactive list with no active QB is rejected before storage; the sim flags an all-zero QB room. Validated, not shipped

**What changed.**

- `ingest_inactives.impossible_list(entries)` returns a reason when the roster identifies at least one QB
  and every QB is `didNotPlay`. The QB position comes from each entry's own position `$ref` (id 8), so no
  extra calls are needed. When no entry carries a QB position the list cannot be judged, so it passes.
- `fetch` runs it on every posted list. A rejected list is **not stored**, so the team stays on its injury
  report exactly as if the list had not posted. `run` prints a `[reject]` line naming the team and the rule.
- `box_score.no_available_qb(squad)` is true when QBs are present and every one is explicitly at play
  prob 0. Missing probabilities don't count. `passer_weights` keeps its depth-QB1 fallback, which is right
  for missing data, but `simulate_nfl` now prints a `[warn]` and records `components.input_warnings` on the
  stored simulation whenever it fires for this reason.

**Validation** (criteria from the 2026-09-24 P42 entry):

| Criterion | Result | |
|---|---|---|
| (a) replay weeks 1-3 fires on the ATL list and nothing else | **Arm A**: all 32 stored pre-game pulls (28 week-2 lists, 2 repeat CLE/TB pulls, ATL and GB week 3). Flags were rebuilt exactly from the stored rows onto today's game roster; all 263 stored flags are on it. **Fires once: ATL week 3.** **Arm B**: every roster ESPN serves now, through the real `fetch` path: week 1 32/32, week 2 32/32, week 3 2/2 judged, **0 rejected** | pass |
| (b) unit test pinned to tonight's ATL data | `tests/fixtures/atl_2026w3_roster_pregame.json`: the 54-entry game roster with the 9 stored pre-game flags, matching the 00:13Z direct read (54 entries, 9 flagged, 4 QBs flagged). `test_impossible_list_is_rejected`: rejected with the reason; ESPN's post-game correction (Penix active) passes; a position-less roster passes; through `fetch`, ATL is not stored while GB's list in the same call is kept | pass |
| (c) the fallback is no longer silent | `test_no_available_qb` (all-zero flagged; partial, missing, no-column and no-QB cases not flagged; fallback unchanged). Wiring: a `--no-store` dry run of ATL @ GB on its stored inputs prints the P42 warning; a dry run of the 15 remaining week-3 games prints none | pass |
| (d) suite passes | 138 passed (136 plus the 2 new tests). The one new warning is a pandas/numpy deprecation inside pandas | pass |

**Limits, stated plainly.**

- Week 1 is covered only by arm B, and arm B reads ESPN's rosters as they stand now. ESPN corrected ATL's
  list after the game (Penix no longer flagged; 7 flagged, not 9), so arm B can show the rule doesn't fire
  on good lists but can't show it catches bad ones. Arm A is the detection evidence, and it rests on the 30
  lists we stored before kickoff.
- The rule covers exactly one impossible state. A list that is wrong in a plausible way (a genuine starter
  flagged while a healthy backup is not) passes, as ATL's would have if ESPN had left Tua unflagged. The
  broader rules from the P42 entry (roster-share or position-group thresholds) are not built; as P33 found,
  list size alone doesn't separate good lists from bad ones.
- `run_sunday`'s count counts stored lists, so a rejected team appears there as "not posted". The
  `[reject]` line printed just above it says why.

---

## 2026-09-24 — Week-3 input audit (15 games not yet kicked off): no impossible states; P43 and P44 logged, nothing changed

Read-only, after the P42 find. For each team: freshness of the injury and inactive rows, whether any
position is left with no available player (the P42 check), whether the sim's QB1 matches the depth chart,
last week's actual passer and the QB the books price, whether any ruled-out or IR player still gets
touches, and whether every sim player is on that team's 2026 roster.

- **Impossible states: none.** Every team has an available QB. No out or IR player gets touches in the sim.
  309 of 310 sim players are on their 2026 roster; the other is a name variant (Joshua / Josh Palmer, BUF).
- **Starters.** Each sim QB1 matches the QB the books price wherever they price one. The genuine changes
  are all reflected: MIN Kyler Murray (back from a week-2 concussion), SEA Darnold (limited, 0.85), NYG
  Winston (Dart DNP). WAS runs Daniels/Mariota 60/40 on Daniels' Wednesday DNP; the books price Mariota,
  and Friday's status settles it. CHI runs Bagent/Keenum with Caleb Williams doubtful (ESPN, Thursday), and
  the books price no CHI QB yet.
- **Freshness.** The nflverse injuries file was last modified Thu 12:41Z, so it holds Wednesday's practice
  report only. Sunday teams' official statuses post Friday. ESPN is current (latest entry 9/24 23:51Z).
  PHI and CHI (Monday night) have no nflverse report yet, which is expected, and run on ESPN rows alone.
  No inactive lists are stored for any Sunday or Monday game, which is correct: the gate opens at T-2h.
- **Defects: P43** (nickname duplicate: Kiko / Francisco Mauigoa, 0.19 pts NYJ @ DET) **and P44** (week-2
  in-game ESPN statuses read as week-3 questionables: Stevenson 0.63 pts PHI @ CHI, Jack Jones, Mauigoa).
  Neither is fixed this week (user decision). Friday's refresh should clear most of the staleness
  naturally. **Follow-up:** re-run the audit after that refresh and record in both rows which instances
  self-cleared.
- **Stale but inert.** The stored `depth_charts` table (snap-share rank) still places players on
  their old teams (Murray on ARI, Tua on MIA). Nothing that feeds a prediction reads it.

---

## 2026-09-24 — P42 logged: ATL's TNF inactive list marked all four quarterbacks out, and nothing checked it

**What happened.** The TNF window refresh (`run_sunday.py --date 2026-09-24 --fresh-odds --no-explain`) ran
00:05-00:06Z for ATL @ GB (kickoff 00:15Z). Both inactive lists had posted: GB 10 players, ATL 9, read at
+0.2 h, well inside the P33 two-hour gate. ATL's list flags **every quarterback on its game roster**
`didNotPlay`: Michael Penix Jr., Tua Tagovailoa, Cooper Rush and Jack Strand. The same 54-entry roster
lists no other QB. A team cannot play without dressing a quarterback, so the list is wrong. Either ESPN
mis-flagged at least one QB, or ATL's starter is missing from the roster. A direct re-read of the endpoint at 00:13Z returned
the same four flags, so the fault is in the feed, not in our join or player matching.

**What it did downstream.**

| Layer | Effect |
|---|---|
| `features.apply_inactives` | all four ATL QBs at play prob 0, status "inactive" |
| baseline (injury term) | Penix's slot charged the generic starter-out 5.59 pts; ATL injury total -8.00, term +4.82 to GB. Baseline GB -12.8 vs market -4.5 (no flag) |
| ML | GB -8.4, built on the same injury report |
| sim | anchored to the baseline margin (12.85). `box_score.passer_weights` saw zero total QB weight and fell back, silently, to depth QB1: Penix throws 100% (31.0 att, median 195 yds) |
| props / TD | ATL receivers and backs were ranked on that box score (Drake London rec yds under #2, Bijan Robinson rush yds under #14 in the pre-kickoff top 25); ATL anytime-TD picks likewise |

The team-level number may also be wrong, not only the player numbers. The charge is a generic starter-out
value that ignores who replaces Penix. Last week's P28 check put the gap between ATL's possible starters at
about 11 points (Tua about 0 to +4 against ATL's rating, Rush about -7). Who actually started is not known
at the time of writing. Record it here once the box score is in, because it tells us which way the line
was off.

**Why it wasn't caught before kickoff.**

1. No layer checks a list for plausibility. `ingest_inactives.fetch` accepts any 200 with `didNotPlay`
   entries inside the lead-time gate. P33 gates on *when* a list was read, never on *what* it says.
2. The sim's failure is silent. The `passer_weights` fallback exists so that a squad with no play
   probabilities still has a passer. Here it turned "no QB can play" into "the injured starter plays", and
   printed nothing.
3. The refresh reports counts only ("2/2 team lists posted"), which reads as success.
4. Timing. The lists were first readable at about T-10 min, so the refresh finished at T-9 with no review
   window. It was found by manually reading the stored sim after the refresh, at T-8, too late to fix and
   validate before kickoff. By rule, a game is never re-simulated after kickoff (no as-of cutoff), so ATL @ GB
   stands as simulated.

**Why this is not P28.** P28 is a disagreement between valid inputs: the depth chart and the market name
different healthy starters. P42 is an impossible input, which should be rejected before it reaches any
model. A P28 fix (starter identity) would not have caught this, and a P42 check would not fix P28.

**What the fix would take** (not built; scope for approval):

- **Where the rule lives.** In `ingest_inactives.fetch`, per (game, team), before rows are stored. The full
  game roster is in hand there (`entries`, each with a position and `didNotPlay`). Nowhere downstream still
  has the actives.
- **Rule 1: at least one QB who is not `didNotPlay`.** This is an NFL roster requirement, so it cannot fire
  on a genuine list, and the 2023 emergency-third-QB rule doesn't change that (the emergency QB is listed
  inactive while two QBs are active). A failing team list is **not stored**. That team falls back to the
  injury report's play probabilities, exactly as if its list had not posted, and the run prints a
  `[reject]` line naming the team and the rule.
- **Other rules worth considering, same shape:** a list covering an implausible share of the roster, or a
  position group emptied. Only rule 1 is a hard league rule; the others would need thresholds from stored
  lists. As P33 found, list size alone does not separate good lists from bad.
- **Downstream guard.** `passer_weights` should warn, and record it on the simulation, when it falls back
  with QBs present but every one of them has play prob 0. That is the "impossible input got through anyway"
  case. Keep the fallback for the genuinely missing-data case (play prob absent).
- **Reporting.** `run_sunday` prints each rejection. The dashboard labels any game whose list was rejected,
  so the flat-probability fallback is visible.
- **Adoption test.** (a) Replay over every stored week-1 to week-3 list: the rule fires on this ATL list and
  on no other. The raw rosters are needed for that; check whether they are cached, and if not, apply the rule
  to future lists only and say so. (b) A unit test pins tonight's ATL payload as rejected. (c) A test
  asserts `passer_weights` warns rather than silently falling back when every QB is at 0. (d) The suite still
  passes.

**Actions tonight.** No fix, no re-simulation. ATL @ GB carries a `KNOWN_GAME_ISSUES` label (`2026_03_ATL_GB`)
that marks its player-level numbers as unreliable and notes the team-level line may be affected. The stale
`2026_02_CAR_ATL` (P28) label was removed; that game is graded. An earlier read in the same session said the
sim "ignores inactives at QB". That was wrong: it applies them, then falls back.

**Update, 2026-09-25 01:10Z (in game, 2Q 11:53, ATL 7-7 GB): Penix started.** From ESPN's core-API
play-by-play (site.api summary still 403s), every ATL dropback so far is his: 7 of 7, starting with the
first at 1Q 14:22 (`M.Penix pass short left to Bi.Robinson ... for 17 yards`). This is an early sample,
but it is the starter. ATL's official week-3 report (nflverse) lists Penix at **full practice with no game
status**, and Tua at full practice too. ESPN's injury feed lists only Rush and Strand as out. So:

- **The inactive list was wrong about Penix at least.** Whether it was also wrong about Tua cannot be told
  from the play-by-play, so it isn't claimed here.
- **The baseline charge was the error, not the sim's passer.** The 5.59-pt Penix charge came entirely from
  the bad list; without it the official report charges him nothing. ATL's injury term was about 5.6 pts too
  harsh. Very roughly, and assuming the term enters the margin linearly, baseline GB -12.8 would have been
  about GB -7.2 (market -4.5). ML's injury features were built on the same report.
- **The sim's passer was right by accident.** The `passer_weights` fallback picked depth QB1, which happened
  to be the real starter. The ATL player props and TD picks were therefore not QB-contaminated, although the
  sim's score was anchored to the over-charged baseline margin.
- **For the proposed fix:** rejecting ATL's list (rule 1) would have left ATL on its official report: Penix
  uncharged and the sim unchanged. That is the right answer here, which supports the rule as scoped.

---

## 2026-09-22 — P9 part 2 findings: scaling the injury term down makes edges worse, not better; neither candidate coefficient is stable. 1.0 stays

Script `calibration/p9b_injury_edge.py`, full output `calibration/2026-09-22_p9b_injury_edge.md`. The rules are in the entry below and were fixed before running. **Nothing built; no coefficient change proposed.**

**Walk-forward coefficients used:**
- beta (arm B): 0.34-0.51.
- beta_mkt (arm M): 0.30-0.39.

**Edges, 2019-25, 1,881 games:**

| arm | all leans | \|edge\| >= 3 | \|edge\| >= 4 | slope resid on edge |
|---|---|---|---|---|
| **L, c = 1.0 (live)** | 50.9% | **485-475 (50.5%)** | 49.7% | +0.060 |
| B, walk-forward beta | 51.0% | 425-468 (47.6%) | 46.9% | +0.024 |
| M, walk-forward beta_mkt | 51.2% | 427-473 (47.4%) | 47.1% | +0.021 |
| 0, no term (reference) | 49.5% | 425-479 (47.0%) | 47.7% | -0.005 |

**Both candidates fail all four edge criteria:**

| | B | M |
|---|---|---|
| E1: on games where the lean flips | 87-86, p 0.50 | 105-100, p 0.39 |
| E2: at \|edge\| >= 3 | 47.6% vs L's 50.5% | 47.4% vs 50.5% |
| E3: injury-heavy games | 50.9% vs L's 51.9% | 51.3% vs 51.9% |
| E4: 2025 | 49.1% vs L's 49.4% | 46.9% vs 49.4% |

Arm 0 against L on flipped games went **148-174**: over ten seasons, the full-size term picks the right side slightly more often than no term. No arm clears 52.4% at |edge| >= 3 (the best is L, p 0.89 against it), which is consistent with P37.

**What this says about the original P9 evidence.** The 2026 cells (|adj| >= 1 0-5, >= 2 0-7) are **not reproduced historically**. At full size, the injury term's big edges cover at 50.5%, the best of the four arms. The part 1 arithmetic ("edges about 4x the information behind them") holds on average, but shrinking the term mostly removes correct sides along with the wrong ones. It doesn't turn losing edges into winners. So 2026's losses in injury-heavy games look like the same small-sample noise as the QB-mismatch cells (cross-reference entry).

**Stability. Neither candidate coefficient is a stable number:**

| | S1 heterogeneity | S2 trend | S3 leave-one-out | S4 walk-forward path |
|---|---|---|---|---|
| beta (outcome) | **fail**: Q 25.8/9 df, p 0.002, I² 65% | **fail**: +0.080/season (CI +0.018 to +0.143) | pass: max 0.109 (drop 2024) | **fail**: 0.337-0.507 (already known, disclosed) |
| beta_mkt (market) | **fail**: Q 24.5/9 df, p 0.004, I² 63% | pass: +0.015 (CI -0.006 to +0.036) | pass: max 0.027 | pass: 0.304-0.387 |

- **The outcome-implied value varies by season and is rising.** Single seasons run -0.04 to +1.56, with 2024 (1.56) and 2025 (0.86) the two highest.
- **Caveat on the trend:** its CI is the fixed-effect interval. With I² at 65% it is too narrow, so read the trend as "suggestive", not established.
- **Either way, a fixed 0.5 would be tuned to 2016-23**, while the latest two seasons point closer to 1.0. That is exactly "wrong at 0.5, just less obviously".
- **The market's own sizing is steadier** (no trend, a tight path, 0.30-0.39) but still varies between seasons beyond noise (0.14 in 2023 to 0.56 in 2022).

**Verdict by the pre-set rules:**
- **B** fails the edge test and three of four stability criteria.
- **M** fails the edge test and S1.
- **1.0 stays on this evidence.**
- The part 1 in-sample beta of 0.55 is not a number to adopt: it doesn't improve edges, it isn't stable, and the recent seasons disagree with it.

**P9 disposition: closed as tested, no change (user confirmed 2026-09-22).** Re-open only if 2026 week 3+ injury-heavy games keep losing, under criteria agreed with the user and written into this log before any test runs. That is the same route as the QB-mismatch cross-reference: new games only, never the 2026 weeks 1-2 cells that prompted P9.

---

## 2026-09-22 — P9 part 2 scoped: a scaled-down injury coefficient, judged on betting edges, with a stability test on the coefficient itself (design and criteria, written before running)

**Question.** Does scaling the injury term below 1.0 make the baseline's edges against the line better, and is the scaled coefficient a stable number or just a different wrong one? This follows the findings entry below: outcomes support about 0.55 per point of the term, the line prices about 0.39, the model applies 1.0.

**Which coefficient is right for edges, in principle.** The injury part of an edge is `(c - beta_mkt) x term`. Its true information about the cover is `(beta - beta_mkt) x term`.
- `c = beta` makes that part calibrated.
- `c = beta_mkt` removes it: defer to the line on injuries.
- `c = 1.0` overshoots by `(1 - beta) x term`.

Both candidates are tested. **Neither is chosen by the full-sample numbers** (0.546, 0.385), which were fitted on the games being judged.

**Arms.** Each is walk-forward for seasons 2019-2025, with the coefficient fitted on 2016..Y-1 only. The edge is `baseline + c x term + market_spread`, with the same baseline, term and line as part 1.
- **L:** c = 1.0 (live).
- **B:** c = walk-forward beta (outcome-implied, part 1 Q1).
- **M:** c = walk-forward beta_mkt (market-implied, part 1 Q3).
- **0:** c = 0 (no term). Reference only, not a candidate: part 1 Q1 shows the term carries real information about the margin.

**Why edge size, not the live flag.** At -110 the live flag needs about 11.3 points of disagreement with a 50/50 line (`market.points_to_flag(13.0)`, weight 0.15, buffer 0.03). The historical line has no prices, so the replay would flag almost nothing. The flag count is reported, but ATS is judged by edge size (P37's thresholds 0, 2, 3, 4, 6) and on the games where the arms disagree. Pushes are excluded, and a zero edge leans away, as in `grade.evaluate` / P37.

**Edge criteria. B and M are each judged against L on pooled 2019-25, and a candidate needs all four to pass:**
- **E1, the paired test:** on games where the candidate and L lean opposite ways, the candidate's side covers in more than half, one-sided binomial p < 0.05. These are exactly the games where the term's size decided the side.
- **E2:** ATS at |edge| >= 3 is not below L's.
- **E3:** on the injury-heavy games (|term| >= 2, raw, so the subset is the same for every arm), all-lean ATS is not below L's.
- **E4:** 2025 alone, all-lean ATS is not below L's.

**Stability criteria for the coefficient each candidate uses (beta for B, beta_mkt for M), a pass needs all four:**
- **S1, heterogeneity:** Cochran's Q over the ten single-season estimates (2016-25, HC1 SEs), p >= 0.05. No evidence that the true value moves by season.
- **S2, trend:** the inverse-variance-weighted slope of the single-season estimate on season has a 95% CI that includes 0. A drifting coefficient would be wrong going forward even if the average is right.
- **S3, leave-one-season-out:** the full-sample estimate with any one season dropped stays within +/- 0.15 of the full-sample value.
- **S4, walk-forward path:** the prior-seasons fit used for 2019 through 2025 stays within +/- 0.15 of the 2025 value.
- **Tolerance:** +/- 0.15 is about 0.3 pts on the average |term| (2.14) and 0.75 pts on a 5-pt term. Past that, "0.5" would be as wrong as 1.0 on the games that matter.

**Already seen, so not new evidence. Disclosed now.** For beta, part 1 already showed:
- the single-season values (-0.04 to +1.56);
- the walk-forward path (0.337 to 0.507, so **S4 is already known to fail for B**);
- the fit without 2024 (0.438, inside S3's band for that one season).

The thresholds above are set by what "stable" should mean, not tuned to these. Nothing about beta_mkt's per-season behaviour has been looked at.

**Verdict:**
- **Passes E1-E4 and S1-S4:** a coefficient change is worth proposing to the user. Nothing is built from this entry.
- **Passes E, fails S:** better than 1.0 but not a stable number. Report which S failed and how. No proposal of a fixed value.
- **Fails E:** 1.0 stays on this evidence.
- **If both B and M pass:** prefer fewer S failures, then the stronger E1.
- **If arm 0 beats both candidates on E1-E4:** that is recorded as a finding, not adopted.

**Also reported (no pass/fail):** ATS by edge threshold for every arm, per season; the slope of cover residual on edge per arm (P37's statistic); whether any arm clears 52.4% at p < 0.05 at |edge| >= 3. That last one is the bar the baseline flag trust rule uses. **Beating L isn't the same as being profitable.** P37 found the rating-only edge about 50% at every size.

**Stop.** Findings go to the user first.

---

## 2026-09-22 — P9 findings: the term is about 45% too large for outcomes, but correcting it doesn't pay out of sample; the logged edge test passes narrowly, on 2024 alone

Script `calibration/p9_injury_coefficient.py`, full output `calibration/2026-09-22_p9_injury_coefficient.md`. The rules are in the entry below and were fixed before running. **Nothing built; no coefficient change proposed yet. Findings go to the user first.**

**Gate 0: pass.** The regenerated post-P41 term matches the training file on 3,060/3,060 rows (max diff 1e-15). The pre-P41 regeneration differs on exactly 20 rows, max 0.588. Fit sample: 2,661 games; 16 of the 20 P41 rows fall inside it. 320 of 6,041 team-weeks hit the 8.0 cap.

**Q1, magnitude: statistically off, immaterial. By the pre-set verdict, no change.**

| | result | verdict |
|---|---|---|
| M1: full-sample beta, 2016-25 | **+0.546** (95% CI +0.359 to +0.734) | **pass**: 1.0 is outside |
| M2: walk-forward beta (0.34-0.51) vs 1.0, pooled 2019-25 MAE | 10.541 -> 10.501, **-0.040** (bar 0.05) | fail |
| M2: seasons improved | 4/7 | fail |
| M2: 2025 | +0.068 (worse) | fail |
| M2: Brier | 0.2259 -> 0.2268 (worse) | fail |

Per-season beta swings from -0.04 (2023) to +1.56 (2024), and the two most recent seasons are the highest (2024 1.56, 2025 0.86). So a walk-forward beta fitted on older seasons (about 0.4) under-shoots exactly where it's applied last. In sample the term is too harsh by about half. Out of sample, shrinking it gains 0.04 pts and loses on Brier.

**M3, the component split (diagnostic):** QB part beta **+0.704** (+0.435 to +0.973), non-QB **+0.418** (+0.170 to +0.666). Both exclude 1.0, so by the pre-set rule this is **not** a position-weight finding: both parts are too large, the non-QB part more so. Their CIs overlap.

**M4, P41: no effect on the fit, as expected.** Beta pre +0.547, post +0.546, delta -0.0008. **This confirms, rather than resolves, the limit stated up front.** P41's live effect comes from 2026-only inactive rows, which history can't test.

**Q2, P9's logged adoption test: passes, narrowly.** gamma **+0.161** (-0.012 to +0.335), one-sided p **0.034**, 2,655 games with a non-zero term. By the logged criterion P9's edge test is met.
- **Read with care.** Signs by season split 5+/5-, and 2024 alone is +1.09 (p < 0.001).
- **Post-hoc, not a criterion:** dropping 2024 gives gamma +0.062, p 0.25 (and beta 0.438).
- The QB-part correlation with the cover residual is **+0.119 in 2024-25** (P28 measured +0.124 there) but **+0.022 over all ten seasons**. P28's revision of P9 was a 2024-25 property, not a stable one.
- By the rule in the scoped entry, this pass changes no coefficient, and any flag use falls under the baseline flag trust rule.

**Q3, market-implied size (descriptive):** beta_mkt **+0.385** (+0.323 to +0.448); QB part +0.549, non-QB +0.252.

**How the three fit together (arithmetic, not a new test).** Q2's gamma is exactly Q1's beta minus Q3's beta_mkt (0.546 - 0.385 = 0.161), because the cover residual is the difference of the two dependent variables.
- Outcomes support about 0.55 points per point of the term.
- The line moves about 0.39.
- The model applies 1.0.

So on a game where the term is X, the model disagrees with the line by about **0.61 X**, and only about **0.16 X** of that is supported by outcomes. That is the mechanism behind the filing evidence (|adj| >= 1 went 0-5, >= 2 went 0-7): the baseline's injury-driven edges are about 4x larger than the information behind them. It is also why the M2 fix doesn't help much on MAE (the term is small next to game noise) while it could matter for **edges**. Edge effects weren't a pre-set criterion here, so that is a question for a new, pre-registered test, not a finding.

**2026, descriptive:** 29 games (DET@BUF excluded), mean |term| 1.67, corr with the cover residual +0.040, in-sample beta +0.62 (CI -2.7 to +4.0). No information.

**Status.** By the pre-set rules: Q1 gives no change, Q2 passes (fragile), and P41 is irrelevant to the historical fit. Next step is the user's call. The obvious candidate is a pre-registered test of the baseline's **edge** with the term scaled toward beta_mkt or beta. It would need its own criteria written here first.

---

## 2026-09-22 — P9 scoped: what the injury-term check actually asks, and the refit after P41 (diagnosis and criteria, written before running)

**What P9 is about.** The Layer 2 injury term is `position weight x snap share x (1 - play prob) x 6.0` per player, summed per team (capped at 8.0), home minus away. `predict_baseline.predict_game` adds it to the margin with an implicit coefficient of **1.0**. P9 was opened on 2026-09-14 from `|injury adj| >= 1` going 0-5 ATS, corr(term, cover residual) = -0.00, and DEN@KC, where the line had already moved for the same report.

**The logged test measures something other than the title.** The title asks whether the term is the right *size*. The adoption test (`actual - market ~ injury`, positive and significant) asks whether it knows something *the line doesn't*. Those are different questions and can give opposite answers:
- a term of exactly the right size that the line already prices fully gives a coefficient of 0 and **fails the logged test forever**;
- a term twice too large that the line only half-prices can **pass** it.

The filing evidence (0-5, "market already priced it") is really about the second question, double counting against the line. Both questions are legitimate, so each gets its own test here. **The logged test is kept exactly as written** (Q2) and not replaced.
- **Q1, magnitude:** `actual - baseline without injury = a + beta x term`. beta is the coefficient the model should be applying; the live model applies 1.0. beta < 1 means the term is too harsh.
- **Q2, edge (P9's logged test):** `actual + market_spread = a + gamma x term`.
- **Q3, market-implied size (descriptive):** `-market_spread - baseline without injury = a + beta_mkt x term`. This is how far the line moves per point of the term, and it's a low-noise cross-check on Q1.

**Already on record, which this has to square with.** P28's re-test (2026-09-20) measured the flat QB charge at **+0.124 cover correlation over 512 games in 2024-25, +0.250 on the 132 where it fires**. That had already revised P9's -0.00 and is a Q2 result for the QB part only. P39 found a QB *identity* term market-redundant. Those two don't obviously agree, and the component split below is where that shows.

**What the historical refit can and can't say about P41. Stated now so a null isn't over-read later.** P41 moved **20 of 3,060** training rows (max 0.588), so the historical coefficient can barely move. P41's large live charges (PHI -2.07, PIT -1.80) come from **posted-inactive rows entered at snap share 0.0**, and inactive lists exist only in 2026. **History can't validate P41's live magnitude.** 2026 has about 31 gradable games, under P9's 100. Also, those games were graded on terms computed before P20, P41 and P10, so they aren't the corrected numbers either. Two other known differences between history and live:
- history is practice-aware (nflverse practice status), while live ESPN rows are a flat 0.55 for Questionable (P21);
- a player already out for weeks is partly inside the EPA rating, which would pull beta below 1 for long absences. That's noted but not tested here.

**Data and method.**
- **Games:** `data/training_nfl.csv` (rebuilt 2026-09-22 after P41), 2016-2025, weeks <= 18, line present. 2026 is excluded from every fit.
- **Baseline without injury:** P37's replay of live Layer 1 plus HFA / rest / travel, x wind (it matches live 30/30). **Term** = `injury_diff x wind factor`, since live applies wind to the sum.
- **Components:** QB part = `6.0 x qb_loss_diff x wf`, and the non-QB part is the remainder. The count of team-weeks where the 8.0 cap binds is reported, since the split is approximate there.
- **Pre-P41 variant:** `build_training._nfl_injury_features` is re-run with the old sort key `-(snap_share or DEFAULT_SNAP_SHARE)` patched in. That is scoring only; ratings and lines are unchanged.
- **Fits:** OLS with intercept, HC1 robust standard errors. **Walk-forward:** for each season Y in 2019-2025, beta is fitted on 2016..Y-1 and applied to Y. The headline is pooled 2019-25, with 2025 reported alone.

**Gate 0: the inputs are what they claim to be.** The regenerated post-P41 injury term matches the training file on every row (|diff| < 1e-9), and the pre-P41 regeneration differs from it on exactly the 20 logged rows (max 0.588). If either fails, stop and report; nothing below runs.

**Q1, magnitude. Pass or fail each:**
- **M1, is 1.0 wrong?** The full-sample (2016-25) beta's 95% CI excludes 1.0.
- **M2, does it matter out of sample?** Replacing 1.0 with the walk-forward beta improves pooled 2019-25 baseline margin MAE by **>= 0.05 pts**, improves it in **>= 5 of 7** seasons, 2025 is not worse, and pooled win-probability Brier (sigma 13.0) is not worse.
- **Verdict:**
  - **M1 and M2 pass:** miscalibrated and material. A coefficient change is worth proposing to the user; nothing is built from this entry.
  - **M1 passes, M2 fails:** statistically off, immaterial. No change.
  - **M1 fails:** consistent with 1.0. No change.
- **M3, component split (diagnostic, no pass/fail):** beta separately for the QB and non-QB parts, with CIs. If one excludes 1.0 and the other doesn't, it's recorded as a position-weight finding (the scale is one number shared by both), not a scale change.
- **M4, P41 sensitivity:** full-sample beta pre vs post P41. Expected |delta beta| < 0.02. Anything larger is investigated before any other result is read.

**Q2, edge, P9's logged adoption test, unchanged:** full-sample gamma > 0 at one-sided p < 0.05, over >= 100 games with a non-zero term. Reported per season, and for the QB and non-QB components. A pass is **not** a magnitude result: it says the line under-prices injury reports. It changes no coefficient by itself, and any flag use falls under the baseline flag trust rule (2026-09-22).

**Q3, market-implied size:** beta_mkt with its CI, descriptive only.

**2026, descriptive only:** weeks 1-2 graded NFL games with their stored term, excluding DET@BUF (P20 caveat), n about 31. Report corr(term, cover residual) and residual against term. No decision.

**Stop.** Findings go to the user first. No coefficient change is proposed or built from this entry.

---

## 2026-09-22 — P41 built: known-zero snap shares no longer take starter slots. Training rebuilt, model retrained

Built to the design in the entry below. `features._share_or_default` replaces `(share or DEFAULT_SNAP_SHARE)` in both sort keys (`score_injuries`, `qb_availability_loss`): unknown still falls back to 0.65, a known 0.0 now ranks last.

**The scoped live cases land exactly.**

| team | before | after | delta (scoped) |
|---|---|---|---|
| PHI | -0.61 | -2.68 | **-2.07** (-2.07) |
| PIT | -3.91 | -5.71 | **-1.80** (-1.80) |
| CHI | -2.72 | -3.12 | -0.40 (-0.40) |
| KC | -2.94 | -3.28 | -0.34 (-0.34) |
| TB | -1.78 | -2.00 | -0.22 (-0.22) |

PIT's single QB slot now holds **Mason Rudolph** (0.30 snaps, 1.80 pts) instead of Will Howard (0.0), and PIT's `qb_availability_loss` goes 0.0 -> 0.30. No other team's charge moves.

**The training file on disk was stale, which the rebuild exposed.** It held 2,761 rows built on 2026-09-12; the rebuild wrote **3,060**, and `elo_diff` / `epa_diff` moved on almost every row (max 205 Elo). That is everything shipped since 09-12 (k32 among them) reaching the training set for the first time, **not** P41. The model that had been serving was trained on the 09-12 features.

**So P41 was isolated with a second rebuild** on the same code with the fix reverted. Against the P41 build, on identical game sets: `injury_diff` differs on **20 of 3,060 rows** (max 0.588), `qb_loss_diff` on **0**, `elo_diff` / `epa_diff` on 0. That is P41's entire footprint in training.

**A/B on the 2025 holdout (same code, same 3,060 rows, fix off vs on; `save=False`):**

| | closing line | fundamentals MAE | with-market MAE | ATS all leans (fundamentals / with market) |
|---|---|---|---|---|
| fix off | 9.670 | 10.080 | 9.606 | 143/285, 151/285 |
| **fix on** | 9.670 | **10.109** (+0.029) | **9.604** (-0.002) | 140/285, 153/285 |

Mixed and tiny, as 20 rows of 3,060 should be: **no regression, and no gain**. P41 is a correctness fix, not an accuracy change.

**Against the model that was serving** (trained 09-12, stale features): fundamentals 10.152 -> **10.109**, with-market 9.602 -> 9.604, ATS all leans 137/285 -> 140/285. The newly trained model is not worse overall.

**Saved model:** `nfl_margin.json` retrained on the rebuilt file, holdout 2025 as before, `trained_at` 2026-09-22T17:53Z. `models/*.json` and `data/` are gitignored, so the commit carries the code and this entry; the artifacts are local. The previous model and training file are backed up outside the repo for this session.

**Tests:** pytest 136 passed (135 + 1 new regression test pinning PIT's QB slot); every module runner 0 failed.

**P9 is now due a re-check.** The fix makes charges larger wherever it fires, which is the direction P9 is watching. P9's criterion (a fitted coefficient on the injury term, positive and significant over 100+ games) should be re-run against the corrected numbers rather than the ones logged before today.

---

## 2026-09-22 — P41 scoped: the 0.0-share slot-ranking bug, and what fixing it does to ML training features

**Diagnosis.** `features.score_injuries` picks which reported players can occupy a position's starter slots with

    group.sort(key=lambda r: -(r.get("snap_share") or DEFAULT_SNAP_SHARE))

and `qb_availability_loss` (`features.py:191`) does the same. In Python `0.0 or 0.65` is `0.65`, so **a row whose snap share is exactly 0.0 is ranked as if it were a 0.65 regular** and can take the slot from a genuinely injured starter, who is then charged nothing. The `or` is correct for `None` (share unknown) and wrong for `0.0` (share known to be zero).

**Correction to the premise.** P20 does **not** make this fire more often: its IR rows with no snap share are skipped, not emitted at 0.0. The 0.0 rows come from `apply_inactives`, which adds a posted inactive nobody reported at `snap_share or 0.0`, and from snap counts where a player's offensive and defensive percentages are both zero (special-teams only).

**How often it bites, measured.**

| | rows at exactly 0.0 | team-weeks affected | points moved |
|---|---|---|---|
| live report today (week 2 + posted inactives) | **138 of 353** (29 teams) | **5 teams' slots change** | PHI **-2.07**, PIT -1.80, CHI -0.40, KC -0.34, TB -0.22 |
| history 2016-2025 (nflverse reports, as training scores them) | 1,202 of 33,163 (3.6%) | 16 of 5,446 (0.3%) | mean 0.23, median 0.215, max 0.588; one case above 0.5 |

The live rate is far higher than the historical one because inactive lists only exist in 2026, and every unreported inactive enters at 0.0. **PIT is the clearest case:** all three quarterbacks are inactive, the single QB slot goes to Will Howard (0.0 snaps) instead of Mason Rudolph (0.30), and the team is charged nothing at quarterback.

**Proposed fix.** In both sort keys, `-(DEFAULT_SNAP_SHARE if r.get("snap_share") is None else r["snap_share"])`. Unknown still falls back to 0.65; known-zero now ranks last, which is what "he takes no snaps" means. Nothing else changes: the cost arithmetic already treats 0.0 correctly, so only *which* rows occupy slots moves.

**What it means for ML training features.** `build_training._nfl_injury_features` scores historical reports with this same function, and the docstring's rule is that training and live must score identically. So the fix moves training features too, by the amounts in the table: **16 team-weeks of 5,446 (0.3%), at most 0.588 pts**, and `qb_availability_loss` is unchanged in every one of the 5,446. Two ways to land it:
- **Fix and rebuild:** change the code, rebuild `data/training_nfl.csv` and retrain, so training and live agree exactly. Correct by the docstring's rule; costs a rebuild and a retrain, and the retrained model is not bit-identical to the one now serving.
- **Fix live only, rebuild at the next scheduled retrain:** the live pipeline is right immediately, and training keeps a 0.3% / <=0.6 pt mismatch on a feature the model weights lightly, until the next rebuild.

**Interaction to note before building.** The fix makes charges **larger** (every live delta above is more negative), and P9 is an open question about whether the injury term is already too harsh. P41 is a correctness fix, not a magnitude change, but it moves the term in the direction P9 is watching, so the P9 re-check should be run after it, not before.

**Not built yet: the build-now-or-queue decision is the user's.**

---

## 2026-09-22 — P20 fixed: IR players count as out. Validated on the cached 09-18 ESPN pull

Built to the design in the entry below. Code: `src/ingest_injuries.py` (`_status`, `play_probability`, `ingest_espn`, the merge in `run`) and `src/features.py` (`PLAY_PROBABILITY`). **Not yet committed when this entry was written; nothing else in the pipeline changed.**

| criterion | result |
|---|---|
| 1. `ir` at play probability 0; other statuses unchanged; unknown still dropped | **pass** (unit tests in `test_injury_report`) |
| 2. cached 09-18 payload: only IR rows with a snap share ingested, all at play probability 0 | **pass**: 27 of 39, 12 skipped for no share |
| 3. no `(team, player_key)` twice in the merged report | **pass**: 0 duplicates in 254 rows |
| 4. posted inactive lists leave IR rows out and add no second row | **pass**: 28 teams posted, 26 IR rows unchanged, 0 duplicates |
| 5. effect measured per team, no charge past the cap | **pass**: 12 of 32 teams move, largest CLE -3.37 (Dillon Gabriel, QB, 0.562 snaps), worst team charge -8.00 = the cap, none beyond |
| 6. full suite green | **pass**: pytest 135 passed (133 + 2 new), every module runner 0 failed |

**The logged case reproduces exactly.** HOU's Henry To'oTo'o, 0.88 snaps, comes out at **1.06 pts**, the number P20 predicted on 09-16. **DET's Pacheco could not be checked**: he isn't in the cached 09-18 payload at all (that example came from the 09-17 22:50Z pull, which isn't cached), so criterion 5's second named case is untested rather than passed.

**Finding, not fixed, needs a decision: nflverse precedence can mask an IR designation.** The merge treats nflverse as authoritative where both feeds cover a player. NYG's Paulson Adebo is on ESPN's IR list and also on nflverse's report with no game status, so his nflverse row wins and he is charged at his practice-based probability instead of 0. IR is a roster fact rather than a report status, so arguably ESPN should win for `ir` specifically. One case in this payload. **Left as is**, because reversing feed precedence is a wider change than P20 scoped.

**Scope reminders.** The fix cannot change today's numbers: ESPN's injuries endpoint has been 403ing since 09-20, the newest stored ESPN rows are from 09-19 00Z, and no other feed carries IR. Wiring a second IR source (nflverse weekly rosters carry a reserve status) is the follow-up and is not built. The 0.0-share slot-ranking bug noted in the scoping entry is still open and untouched.

---

## 2026-09-22 — P20 scoped: count IR players in the injury layer (design and criteria, written before the fix)

**Diagnosis.** `ingest_injuries._status` (src/ingest_injuries.py:96) returns a status only for out / doubtful / questionable / probable. Every other value becomes `None`, and the ESPN path drops those rows outright (`:262-264`). "Injured Reserve" is one of them, so an IR'd player never reaches `injuries` and never reaches `features.score_injuries`. The nflverse weekly report doesn't list IR players, so **ESPN is the only feed that carries them**: 39 IR rows in the cached 2026-09-18 pull (with Active 636, Questionable 64, Out 56, Doubtful 5), all silently dropped.

**Design**
1. `_status` maps "injured reserve" to a new status **`ir`**, kept distinct from `out` rather than folded into it, because `features.GAME_STATUSES` already excludes IR by name from the inactive-list logic and the breakdown should say why a player is missing.
2. `play_probability` returns **0.0** for `ir`, as it does for `out`, and `features.PLAY_PROBABILITY` gains `"ir": 0.0` for the status-only fallback the ML training path uses.
3. **An IR row with no snap share for that team is not emitted at all.** 12 of the 39 have none (4 have snaps for a different team, 8 have none anywhere). The fallback `DEFAULT_SNAP_SHARE` of 0.65 was written for college players; applied here it would price a camp-body rookie like a rotation regular. The principled reason to drop rather than charge them: the injury charge removes a contributor the *rating* contains, and a player with no snaps for this team is not in it. The four with snaps elsewhere are left uncharged too, which understates a traded starter hurt before he played; that is a known limitation, not a silent one.
4. **Dedup by `player_key`, not by raw name.** The ESPN merge in `run()` keys `seen` on the exact `(team, player)` string, so "Michael Penix" and "Michael Penix Jr." are two people. With IR rows added, a player listed Out by nflverse and IR by ESPN could be charged twice; `player_key` already exists for exactly this and is what `apply_inactives` matches on.

**Why this can't double-count with P10 / P33 inactives.** `apply_inactives` matches on `player_key` and *replaces* a matched report row rather than appending, so an IR player who also appears on a posted list stays one row. `GAME_STATUSES` is questionable / doubtful / probable, so an `ir` row is never flipped to "active" by a list that omits him — which is right, since IR players are not on the game roster and so cannot appear on an inactive list as an omission.

**Validation criteria, fixed before running**
1. `_status("Injured Reserve")` is `ir` with play probability 0.0; out / doubtful / questionable / probable are unchanged; an unknown status is still dropped.
2. On the cached 2026-09-18 payload: exactly the IR rows with a snap share for their team are ingested (27 of 39), each with `play_probability` 0.0.
3. No `(team, player_key)` appears twice in the merged nflverse + ESPN rows.
4. Applying the stored week-2 inactive lists to a report containing IR rows leaves every IR row at play probability 0 and adds no second row for the same `player_key`.
5. The effect is measured and reported per team, with the two logged cases named: HOU To'oTo'o (about 1.06 pts) and DET Pacheco. No team's charge exceeds `INJURY_MAX_POINTS`.
6. Full suite green: pytest and every module runner, 0 failed.

**Out of scope, stated up front.**
- **The fix is dormant until ESPN answers again.** `site.api.espn.com` has been 403ing since 2026-09-20 and still is, so no new IR row can arrive; the store's newest ESPN rows are from 09-19 00Z. A second IR source (nflverse weekly rosters carry a reserve status) is the obvious follow-up and is **not** built here.
- The same `DEFAULT_SNAP_SHARE` fallback still applies to ESPN out / questionable rows; unchanged here.
- **Latent bug found, not fixed:** `score_injuries` and `qb_availability_loss` rank slots with `-(r.get("snap_share") or DEFAULT_SNAP_SHARE)`, so a row whose share is exactly **0.0** sorts as if it were 0.65 and can take a starter slot from a genuinely injured player. It bites the 0.0-share rows `apply_inactives` adds for healthy scratches today. Fixing it would move ML training features, so it needs its own item and its own before/after.

---

## 2026-09-22 — P38 fixed: a failed check() now fails its test under pytest

**Fix.** A new `tests/conftest.py` wraps `pytest_runtest_call`. It reads the module's own failure counter before and after each test (`FAIL`, or `len(FAILED)` in `test_qb_prior`) and fails the test if it rose. **None of the 14 test modules was edited**, so `python -m tests.<module>` behaves exactly as before. Every check in a failing test still runs and prints, so all of its failures show, not just the first. A module that defines `check()` without a counter the hook recognises raises an error rather than silently passing, so a new module can't opt out. This was chosen over editing all 14 `check()` helpers to raise, which would stop each test at its first failure.

**Before and after on the real suite: no regressions.** pytest 133 passed both times, and every module runner showed 0 failed (box_score 48, clv 23, export_edges 7, game_script 16, grade 29, injury_report 34, live 65, live_sim 37, market 42, props 64, qb_prior all passed, simulate 57, sunday 13, td_props 26).

**Proof that it catches failures** (temporary probes, deleted afterwards):
- A counter-style test with 2 failing checks out of 3 fails with "2 check(s) failed". The check between the two failures still ran.
- A list-style test fails and names the failed label.
- A module with `check()` but no counter errors.
- Breaking one real expectation in `test_market` (`implied(-110)` vs 0.6) gives **pytest: 1 failed, 8 passed**. Before this fix pytest reported that as a pass. The runner still says 41 passed, 1 failed, exit 1. The file was restored with `git checkout`.

**Scope note.** P38 guards the unit tests only. It wouldn't have caught P39's 9/20 baseline problem, which came from an ad-hoc analysis script that wasn't kept.

---

## 2026-09-22 — P39 findings: the QB-vs-rating term carries no edge, and as the sim anchor it gains less than the 0.10 bar

Script `calibration/p39_qb_rating_term.py`, full output `calibration/2026-09-22_p39_qb_rating_term.md`. Arms and rules as scoped in the entry below, fixed before running. **Nothing built; no production code.**

**Gate 0: the 9/20 headline doesn't reproduce, and the reason is its baseline.** Rebuilt to the logged formula over 2,661 games, 0 dropped. Split exactly: max |U - I - S| is 2e-15.

| 2024-25, k fitted on 2022-23 | logged 9/20 | rebuild |
|---|---|---|
| margin MAE without the term | 11.557 | **10.709** |
| margin MAE with the term | 10.903 | **10.608** |
| k | 0.780 | 0.548 (0.831 on 2024-25 itself) |
| corr(term, spread) | -0.324 | +0.108 |

The rebuild's baseline is P37's replay, which matches live Layer 1 exactly (30/30). The 9/20 baseline was 0.85 pts worse on the same seasons, so it wasn't the live model; its script wasn't kept, so the difference can't be pinned down. **The 0.65-pt gain was measured against a weaker baseline. Against the real one the term is worth about 0.10.** Both phases run on the rebuild, as scoped.

**Phase 1, edge: fails on every arm, clearly.** Pooled 2019-25 walk-forward, 1,881 games, k refitted each season on the seasons before it:

| arm | corr(term, cover residual) | one-sided p | ATS without -> with |
|---|---|---|---|
| U, full term | -0.024 | 0.85 | 911-927 -> 910-928 |
| I, identity | -0.012 | 0.70 | 911-927 -> 909-929 |
| S, scale | -0.041 | 0.96 | 911-927 -> 905-933 |

The identity arm correlates -0.187 with the spread (-0.336 in 2025): **the line already prices QB changes**, which is the 9/20 finding in a cleaner form. The term is market-redundant, so it is not to be used for baseline edges or Stage-1 flags.

**Phase 2, the sim anchor: a real, consistent gain below the pre-set bar.**

| arm | pooled MAE change | 2025 | seasons better | Brier |
|---|---|---|---|---|
| U, full term | **-0.090** | -0.193 | 7/7 | 0.2295 -> 0.2274 |
| I, identity | **-0.075** | -0.185 | 6/7 | 0.2295 -> 0.2268 |
| S, scale | +0.014 | +0.002 | 4/7 | worse |

**S1 fails for U and I:** 2025 clears the >= 0.10 bar, but the pooled change doesn't (0.090 and 0.075). S2 and S3 pass for both. **By the rules set in advance, phase 2 fails.** The bar is not moved after the fact. For scale: the line's own MAE on these games is 9.813 against the baseline's 10.578, so the term closes about 12% of that gap.

**S4: the gain is QB identity, not scale.** Arm S is about zero or harmful (k -0.07 to +0.40, unstable). So the 9/20 worry that the term might just be undoing the x 0.75 prior regression doesn't hold. What there is comes from "a different quarterback than the one in the rating".

**Caveats that make these numbers an upper bound for live.**
- The starter is nflverse's *actual* starter. Live would use the *expected* starter, which is wrong in about 9.6% of team-games (P28 part 1; `QB_EXPECTED_STARTER` is still off).
- The baseline has no injury term. Live, the flat QB charge already prices part of the same event (+0.250 cover correlation where it fires, P28), so the identity arm's incremental value on top of it would be smaller than measured here.

**What it means.** Nothing here is a production change by the pre-set rules. The honest summary is "a small, consistent anchor accuracy gain (about 0.08-0.09 pts), no edge, and an overlap with the live injury charge that wasn't tested". If it is ever revisited, it's as a sim-anchor-only change, with a new pre-set bar and the injury-overlap test, not by relaxing this one.

---

## 2026-09-22 — P39 scoped: the QB-vs-rating term, tested for edge first and then as the sim anchor (design and validation only, written before running)

**What the term is (re-derived from the 2026-09-20 P28 entry; its script wasn't kept, so it is rebuilt here).** For each team-game, `k x (E[EPA/db of the QB who plays] - rating-implied EPA/db) x 0.603 dropbacks/play x 63 plays`. Home minus away, added to the baseline margin. Rebuilt with pre-kickoff data only:
- **Starter:** nflverse schedules `home_qb_id` / `away_qb_id`. For a completed game this is the actual starter, known at kickoff.
- **Q (the starter's EPA/db):** all his REG-season dropbacks (`qb_dropback == 1`), for any team, in the prior season plus the current season before this week. Shrunk to the league mean dropback EPA over the same window by 200 dropbacks, as in the P28 diagnosis.
- **R (rating-implied EPA/db):** the team's dropback EPA, blended exactly as Layer 1 blends offence. Weight on the current season `w = plays/(plays + 900)`; the prior season is regressed x 0.75.
- **k:** fitted through the origin on (actual margin - baseline margin) against the term, on training seasons only.
- **Baseline margin:** P37's exact replay of live Layer 1 plus HFA/rest/travel/wind. There is no injury term, since the live injury layer has no leak-free history. **Line:** nflverse `spread_line` (near-close, as in P37).

**Design question the arms answer.** R is regressed x 0.75 and Q isn't, so `Q - R` mixes two things. Arm U is split exactly into:
- **arm I (identity):** Q of the starter minus the rating-weighted mix of Q over the quarterbacks whose dropbacks are inside R (same blend weights). It is about 0 when the starter is the rating's quarterback and fires on a QB change.
- **arm S (scale):** that rating-weighted Q mix minus R. It is non-zero for every team. It measures how much the rating's regression and shrinkage understate or overstate passing, whoever starts.

If arm S carries the gain, the finding is about the rating's prior regression and belongs to P22 / P5, not a QB term.

**Placement, if anything passes.** The term is additive in Layer 2, next to HFA and rest; it doesn't replace Layer 1. It has no interaction with k32+fb, P24 or PENALTY_REPLAY on the baseline side: they are simulator-only, and the baseline imports nothing from the simulator (P37). In the simulator they only shape the distribution, because `anchored_simulation` re-solves the mean margin to the anchor. **Known overlap, not testable here:** when the expected starter is a backup because the starter is injured, arm I and the live flat injury QB charge price the same event. A production design must charge it once. That needs its own test against the real 2022-25 injury reports (the P28 reconstruction) before any build.

**Gate 0: the rebuild must be the logged term.** Fit k on 2022-23, judge 2024-25, arm U. Logged: k 0.780; MAE 11.557 -> 10.903; mean |term| 4.17; corr(term, spread) -0.324. **Reproduced** if both MAEs are within 0.10 and k within 0.10. If not, the rebuild is labelled "not an exact rebuild", with the differences stated, and both phases still run on it.

**Walk-forward for both phases.** For each season 2019-2025, k is fitted on every prior season from 2016 and judged on that season. The headline is 2025; pooled means 2019-25. Every arm (U, I, S) is reported. The pass rules below are applied to each arm separately.

**Phase 1, edge against the line (a pass requires all three):**
- **E1:** pooled corr(term, cover residual) > 0 at one-sided p < 0.05. The cover residual is actual margin minus the line's margin, so a positive value means the term knows something the line doesn't.
- **E2:** pooled ATS of the lean with the term added is not below the baseline's ATS.
- **E3:** in 2025 alone, corr(term, cover residual) > 0 (sign only).
- **Fail on every arm:** the term is market-redundant, it is never used for baseline edges or Stage-1 flags, and phase 2 decides the rest.

**Phase 2, the sim anchor (runs whatever phase 1 finds; a pass requires S1-S3, and S4 decides what the gain is):**
- **S1:** walk-forward margin MAE improves by >= 0.10 pts in 2025 **and** pooled over 2019-25.
- **S2:** it improves in >= 5 of the 7 walk-forward seasons.
- **S3:** the win-probability Brier score (normal, the live NFL margin sigma) is not worse, pooled.
- **S4:** if arm S delivers >= 2/3 of arm U's pooled MAE gain, the result is recorded as a rating-regression finding for P22 / P5, not built as a QB term. Only an arm I gain counts as a QB-vs-rating gain.
- **Limit stated up front:** full historical simulations are not run. `load_inputs` has no as-of cutoff, so a replayed sim would leak outcomes. Phase 2 judges the anchor the sim is pinned to, which fixes the sim's mean margin; it doesn't measure knock-on effects on props.

**Stop.** Report the results to the user either way; write no production code from this entry.

---

## 2026-09-22 — P34 fixed: prices are medianed in probability space at all four sites

**Change.** A new `market.median_price()` turns each book's American price into implied probability, takes the median there, and converts back with `to_american`. Probability is continuous, so the result can't land in the -100..+100 gap. It replaces the price-space median at the three logged sites: `clv.snapshot_close`, the `ingest_odds` consensus moneyline and `market.side_price`. It also covers a **fourth site found while building this**, the `ingest_cfbd` college consensus moneyline, which has the identical `int(_median(...))`. No other median in `src/` runs over American prices; the rest are over lines, totals or probabilities.

**Validation.** Every closed CLV row (219), every side price at every quoted line (1,546) and every consensus moneyline (432 games) was recomputed from stored data with the old code and the new. The old code reproduced all 219 stored CLV rows exactly, so the comparison is faithful.

| pass criterion (from the tracker) | result |
|---|---|
| the 187 `espn:draftkings` closes byte-identical | **met**: same hash of the recomputed values before and after, and equal in value to the stored rows |
| no stored close price strictly between -100 and +100 | **met**: 0 after (4 before) |
| a straddling set gives a valid price and CLV near 0 on an unmoved line | **met**: regression tests in `test_market` and `test_clv` |

**The 4 corrupt rows, recomputed and rewritten in `clv_log`** (the originals are saved outside the repo):

| row | close price (home/away) | CLV |
|---|---|---|
| CIN@HOU baseline / ml | -116/**-1** -> -116/**-101** | +45.96 / -45.96 pp -> **-0.50 / +0.50 pp** |
| CLE@TB baseline / ml | **-2**/-118 -> **-102**/-118 | -44.93 / +44.93 pp -> **-0.25 / +0.25 pp** |

CIN@HOU lands on the -0.5 pp the 9/20 diagnosis predicted. The NFL CLV report's baseline spread is now sd 0.91 pp (it was 12.39 with these rows). **This changed P37 part 2 test 3**, which had read the corrupt rows; it's corrected in that entry.

**Side effects.**
- `side_price`: 0 of 1,546 values change; no current data straddles even money. Stage-1 edges are untouched.
- Consensus moneylines: 20 of 432 games change. One is a gap fix. The rest are rounding: an even count now takes its midpoint in probability space, at most 0.41 pp of implied probability, on long-shot prices. A lone `+100` becomes `-100`, which is the same probability. Nothing in the model reads consensus moneylines; market win probability uses the per-book `oddsapi:` rows.

**Stored consensus rows.** The 9/20 check found 0 of 389 `oddsapi_consensus` rows in the gap. By 9/22 **2 were**, so the `ingest_odds` site was live, not latent. The **3 `cfbd_consensus` rows** in the gap were recomputed from their own per-book rows, which were pulled at the same time, and rewritten with their original timestamps: 401856682 -116/-4 -> -116/-104; 401860884 -122/2 -> -122/102; 401864508 -114/-6 -> -114/-106. **Two `oddsapi_consensus` rows are left as stored**: 2026_03_MIN_TB (away 0) and 401858469 (away 0). They're unread, and the next odds pull rewrites them with the fixed code.

**Tests.** 133 pass under pytest (131 before, plus 2 new). Every module's own runner shows 0 failed. That second check is needed because of **P38**: a failing `check()` passes under pytest.

---

## 2026-09-22 — Cross-reference: "QB mismatch: one mechanism, three observations" (P2 / P9 / P37). Noise for now; nothing to patch

**Why this entry exists.** Three separate log items keep finding bad results in the same kind of game: one where the quarterback on the field is not the one whose play the baseline rating was built on. Each is too small to test alone, and as separate entries they would drift apart. This keeps them together until there is enough data to test the shared mechanism properly.

**The mechanism (a hypothesis, not a finding).** Layer 1 rates a team on its play-by-play EPA, which in the early season is mostly last season's, earned with last season's QB. When the QB changes, the rating either doesn't see it at all (an offseason change) or tries to correct it with a separate term (the injury layer's QB charge, P2 / P9). If either is mispriced relative to the market, leans in those games go wrong in a consistent direction.

**The three observations (2026 weeks 1-2, baseline leans vs the stored line)**

| where logged | cell | ATS |
|---|---|---|
| P9 (injury-term magnitude); P37 part 1 test 5 | \|injury adj\| >= 2 | 0-7 |
| P2 (unknown-snap QB charges); P37 part 1 test 5 | starting QB charged >= 2.5 pts | 1-6 |
| P37 part 2 (post-hoc) | either team's week-1 QB differs from its most frequent 2025 starter | 1-9-1 |

**They are mostly the same games.** Across the 30 graded picks the three cells cover **14 distinct games**, not 25: injury >= 2 and QB charge share 6 of 7, and QB change shares 5 with each. Together they went **2-11-1**; the other 16 picks went **7-9**. So this is one weak signal seen three ways, not three independent confirmations. The overlap is also why the mechanism is plausible.

**Evidence against, already in hand.** In the ten-season replay, leans in QB-change games went 176-179-6 (50%) in weeks 1-4. The replay has no injury term, though. It tests the offseason-change route only, not the QB-charge route that P2 and P9 are about.

**Status: noise, by the standing rules. No patch, no weight change.** All three cells were found by slicing after seeing the data, with n = 7-14.

**When this is tested properly, the test has to be set in advance, not reused from these cells.** It should use one pooled "QB mismatch" definition (the union of the three above), fixed before looking, and new games only: 2026 week 3 onward, never the 14 games that suggested it. It has to separate the two routes (offseason change vs in-season charge), since the replay already clears the first. Sample size and decision rule: **not set yet; to be agreed with the user before any test runs**, and written here when they are. Until then, P2 and P9 keep their own proposals and criteria as logged; this entry only links them.

---

## 2026-09-22 — P37 part 2 findings: noise still stands; neither rating miscalibration nor a sharper market explains 2026

Script `calibration/p37b_edge_size_market.py`, full output `calibration/2026-09-22_p37b_edge_size_market.md`. Tests and rules as scoped in the entry below, fixed before running. **Diagnosis only; nothing changed in the model.**

**Correction to part 1: 2026's edges are big, not unprecedented.** Part 1 compared 2026 with the ten replayed seasons pooled (4.52 vs 3.73). Season by season, 2026's no-injury mean |edge| of 4.33 ranks **3rd of 11**, behind 2020 (4.55) and 2024 (4.53); 2018 had a larger share at >= 4 (56% vs 50%). Against nflverse's close it's 4.38, so the stored line isn't the cause. One descriptive column stands out: the gap between the line and a rating built on 2025 form alone is 4.79, the largest of the 11 seasons (next is 2024 at 4.61). The early current-season update pulls that back to an ordinary edge.

**H1, 2026 rating miscalibration: not met.** Size is not above all ten seasons. QB change carries no information in the replay: leans in games where either team changed QB since last season went 176-179-6 (50%) in weeks 1-4, the same as the rest (134-134-6). And 2026 has *fewer* QB-change games than any replayed season (37% of games; 33% of big edges, the lowest share).

**H2, the market ahead of the model: not met.** *Corrected 2026-09-22 after P34.* The first run read `clv_log` while it still held the two corrupt baseline rows (CIN@HOU +46 pp, CLE@TB -45 pp), and they drove its edge-size numbers. Re-run on the corrected rows: mean CLV on the 30 graded leans is **-0.26 pp** (perm p 0.08), and corr(|edge|, CLV) is **+0.02** (p 0.52). Big and small edges are alike: **-0.30 pp at >= 4** (n 15), -0.22 pp below. **Withdrawn:** "the line moved toward the big-edge leans (+2.8 pp)" was an artifact of the corrupt rows. The market neither ran from the big edges nor chased them. It drifted slightly against the leans overall, not significantly and with no size effect. Graded at the logged close instead of the stored line, the record is the same 9-20-1. The leans lost on the field.

**H2b, a sharper line: no, the opposite.** The 2026 weeks 1-2 closing line missed final margins by 11.55 pts, 10th of 11 (only 2017 was worse, 11.56; 2025 was 7.06). Games landed further from every line than usual, which is what makes records swing.

**H3, noise: stands.** 9-20-1 is binomial p 0.06 two-sided. In the replay, 2022 went 12-19-1 over weeks 1-2 with the same formula, and the formula averages ~50% over ten seasons.

**Lead, not a finding (post-hoc slice, n = 11): 2026 leans in QB-change games went 1-9-1**, against 8-11 in the rest. The replay says that cell is ~50% over 361 games, so without more 2026 data this reads as noise. It sits alongside part 1's leads (|injury adj| >= 2 0-7, starting-QB charge 1-6), which probably share games. All three point at games where the QB on the field isn't the one the rating's EPA was earned with, which is P2 / P9 territory. Worth re-checking as weeks accumulate, not acting on.

**Part-1 script defects found (fixed 2026-09-22, no effect on its verdict).**
- The replay dropped the **79** training games involving OAK, SD or STL: the training file uses the old codes, pbp the current ones. With them restored (2,661 games), every row is unchanged in substance (weeks 1-2 53% / 51% / 53% / 53% at >= 0/2/4/6; all weeks corr -0.002).
- The pbp recipe in its docstring now fails for 2016-2025 unless `game_id` is among the requested columns.

**What it means.** Neither explanation offered holds. The ratings aren't unusually far from the market by the replay's standard, and the market didn't know better before kickoff. 2026's weeks 1-2 were simply high-variance games (line MAE 10th of 11) for a near-zero-information edge, at the larger end of its normal size range. No fix is proposed. The standing trust rule (entry below) is unaffected.

---

## 2026-09-22 — P37 part 2 scoped: why 2026's baseline edges are bigger, and whether the market is ahead of them (diagnosis only, written before running)

**The question, restated against what part 1 found.** Part 1 did not establish that bigger edges do worse in 2026: that slope has permutation p 0.27. Three things are 2026-specific and real. Edges are bigger than in any replayed start (mean |edge| 4.52 vs 3.73; 4.33 without the injury term). Half the picks are at >= 4 points against 37%. And the leans are 9-20 overall (binomial p 0.06 two-sided). Part 2 asks why the edges are bigger, and whether the market knew something the ratings didn't. Four candidate explanations:
- **H1, ratings miscalibrated for 2026.** Weeks 1-2 ratings are almost entirely 2025 form (x 0.75). If 2026 teams changed more than usual, or changed in ways the market prices and EPA can't see (a new QB above all), the ratings sit further from the line.
- **H2, the market is ahead.** The line moved away from the model's lean before kickoff, so the model's disagreement is information the market had and corrected.
- **H2b, a sharper line.** 2026's early lines were unusually accurate.
- **H3, noise.** A near-zero-information edge, made larger by the inputs, swinging harder over 30 games. This is the default verdict unless another rule is met.

**Tests** (NFL; replay = the part-1 exact rebuild of live Layer 1 plus situational terms, no injury term)
1. **Edge size by season.** Mean |edge|, weeks 1-2, each replay season 2016-2025, against 2026 without the injury term. The same for the gap between the line and a rating built from prior season only, to show how far lines have moved from last-season form.
2. **QB change (H1).** A team has "changed QB" when its week-1 starter (nflverse schedules `home_qb_id` / `away_qb_id`) is not its most frequent starter the season before. (a) Replay, weeks 1-4: ATS of the model's lean in games where either team changed QB, against the rest, with a binomial p against 50%. (b) The share of |edge| >= 4 picks in QB-change games: 2026 against each replay season.
3. **CLV on the 30 graded 2026 leans (H2).** `clv_log`, all 30 closed. Report the mean `clv_pp` on the lean side (sign-flip permutation p, one-sided < 0) and corr(|edge|, `clv_pp`) (permutation p, one-sided < 0). Descriptive only: the same 30 graded at the closing line rather than the stored line.
4. **Line accuracy (H2b).** Closing-line MAE against results, weeks 1-2, 2026 against each replay season (`spread_line`).
5. **Noise reference (H3).** The binomial p for 9-20, and the replay seasons' own weeks 1-2 records, to show how often a start this bad happens.

**Decision rules, fixed now**
- **H2 (market ahead, and more so on big edges):** mean lean CLV < 0 at p < 0.05 **and** corr(|edge|, CLV) < 0 at p < 0.05. If only the mean is significant: the market is ahead of the model in general, with no effect by edge size.
- **H1 (2026-specific rating miscalibration):** 2026's mean |edge| is above all ten replay seasons, **and** both parts of test 2 hold: QB-change leans cover < 50% at p < 0.05 in the replay, and 2026's big-edge share in QB-change games is above every replay season. Size alone, without test 2, reads as "the inputs moved further than usual", which is not a miscalibration finding.
- **H2b (sharper line):** 2026's closing MAE is below all ten seasons. With n = 30, descriptive only; it can't carry a verdict on its own.
- **H3 (noise)** stands if none of the rules above is met.
- As in part 1, anything added after seeing results is marked post-hoc and read as a lead only. No fix is proposed from this.

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
