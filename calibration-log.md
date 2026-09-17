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
| P10 | Props: apply game-day inactives before simulating | data | 2026-09-14 | DAL@NYG: 4 projected players recorded nothing (N. Harris 5.3 car, Beckham, Cambre, Abanikanda), none on the injury list; Singletary took 10 touches + TD unprojected. **Widened 2026-09-17 (DET@BUF):** this is not a sequencing problem. There is no inactives ingestion path anywhere in the pipeline, and the ESPN feed structurally cannot supply one — a full league pull at 22:50Z returned only `Active` (614), `Questionable` (134), `Injured Reserve` (40), `Out` (9), `Doubtful` (3), with no gameday inactive designation. `ingest_injuries._status` would discard one anyway (see P20, P21). Consequence at T-75 min, with the official list already public: DET@BUF still priced 4 players at the flat questionable/limited 0.55 (D.J. Reed 0.75 pts, Cole Bishop, T.J. Sanders, Ty Johnson) when each was by then resolved to 0 or 1 | acquire a real inactives source first (ESPN gameday roster endpoint or equivalent), then re-sim after it lands; track "projected, no stats" rate weekly | proposed; **queued for the week of 2026-09-22** alongside 2A/P23 |
| P11 | Props: rushing volume bands too narrow (game script) | investigate | 2026-09-14 | DAL@NYG: rush att in the 50% band 2/8, rush yds 1/8; team rush att −8 (trailing DAL), +9 (leading NYG). DEN@KC: leading KC 38 rush att vs median 25 (p90 31), trailing DEN 15 | 50% band hit rate for rush att in 40-60% over 10+ simulated games | **engine change applied 2026-09-15** (game-script play-calling): calibration rush att by final margin 21.4 → 32.5 vs real 20.7 → 31.6, was flat 24.1 → 27.9; league totals within 3%. The band test itself still needs 10+ graded games |
| P12 | Run pregame sims before the first kickoff | process | 2026-09-14 | 12/13 week-1 sims written 23:11Z, after kickoff, so only DAL@NYG props are gradeable | n/a | proposed |
| P13 | NFL prior-season rating must be QB-conditional (weight the prior by the expected starter's games, or add a QB-change term) | logic | 2026-09-15 | DEN@KC: KC's 2025 rating includes 146 backup-QB plays at −0.347 EPA; Mahomes-only prior moves KC +2.9 pts, edge −3.46 → −0.56, flag off. Scope: 11/32 teams shift ≥ 1 pt from non-primary starts (NYJ +5.1, IND +3.8, KC +2.9) | rebuild NFL training with QB-conditioned prior; holdout MAE vs line must not get worse, and weeks 1-4 MAE should improve | **tested 2026-09-15, not adopted.** Starter-games prior (≥ 4 starts): baseline wks 1-4 2016-25 MAE 10.46 → 10.56 (moved games 10.08 → 10.53); ML 2025 holdout MAE 10.08 → 10.10, wks 1-4 8.98 → 9.13. Fails both parts. Code kept behind `QB_CONDITIONAL_PRIOR=0` |
| P14 | Snap-share fallback is per dataset, not per player | bug fix | 2026-09-15 | `_snap_shares` stops at 2026 once it has > 500 rows, so teams that hadn't played and players who sat out week 1 get no share: 78/154 latest NFL injury rows; every DEN/KC row. DEN@KC injury term −0.95 → −2.63 with real shares | none needed; correctness bug | **applied 2026-09-15** (`ingest_injuries.merge_snap_shares`); NFL rows without a share 78/154 → 32/161 on the week-2 pull |
| P15 | Never grade a prediction made after kickoff; never store in-play lines | bug fix | 2026-09-15 | 19 of 80 CFB predictions on 09-12 were generated at 18:37Z, after 16:00–17:00 kickoffs, against in-play Odds API lines (Georgia −69.5 vs DK close −40.5). The old rule flagged 8 of them, 6-2. Pregame-only flagged record is 15-25, not 21-27 | none needed | **applied**: predict-side guard since 2026-09-14 (`ba6d7f3`); `ingest_odds` skips in-play events and CLV marks late leans `after_kickoff`, 2026-09-15 |
| P17 | Props: model each player's own efficiency and target share before trusting the prop ranking (research Stage 4) | logic | 2026-09-15 | Week 2, first pull (1-5 books, Tuesday): 46 props priced, top 10 gaps 17-25 pp, 15 more held out past 25 pp. One-sided pattern: star receivers under (J. Williams rec yds sim 37 vs 56.5, St. Brown rec 5 vs 7.5, Nabers rec 3 vs 5.5); QB pass yds off both ways (Goff 222 vs 265.5, Stafford 285 vs 242.5). The engine gives every player league-typical yards per play and splits targets by depth-chart share | prop gaps centre near 0 across a week (mean \|gap\| < 8 pp), then prop CLV ≥ 0 over 65+ leans | proposed |
| P18 | Simulator: first-and-short (goal-to-go) conversion far below real | bug | 2026-09-16 | Engine diagnostic, `--calibrate` over 20k league-average sims: 1st & 0-2.5 converts .323 vs real .486 (y/p 0.34 vs 0.43); 1st & 2.5-5.5 .216 vs .329 (y/p 1.41 vs 2.64); 1st & 5.5-9.5 .119 vs .163. On 1st down a to-go under 10 means the ball is inside the 10, so these are almost all goal-to-go snaps. Consistent with sim TD share .196 vs real .220. At ~1% of all snaps it does **not** explain the 11% plays-per-drive shortfall, which was measured separately and traced to possession count | 1st-down conversion within 3 pp of real in each sub-10 distance bin, and sim TD share within 1 pp of real | proposed; **deliberately deferred 2026-09-16** so it does not pull focus from the punt / three-and-out investigation |
| P16 | Baseline model weight to 0 if its NFL leans show no CLV | weight | 2026-09-15 | backfill: 75 pregame baseline leans −0.22 pp (t −1.22), but 61 are CFB and priced at an assumed −110 against DK's close; NFL n=14 | NFL lean CLV ≤ 0 at 65+ NFL leans (≈ week 5) → set `MODEL_MARKET_WEIGHT=0` for the baseline | watch |
| P19 | A partial injury pull must not retire other teams' reports: `latest_injury_report` keeps the latest pull *per source*, not per team/week as P1 intended | bug fix | 2026-09-16 | The 19:46Z week-2 nflverse pull held only BUF/DET (8 rows, the Thursday game). Because it was the newest nflverse pull, the week-1 nflverse report (91 rows) was silently dropped for the other 30 teams, which fell back to ESPN only. This time it helped by accident: the week-1 statuses were stale, e.g. Penix OUT, and CAR@ATL moved 0.60 → 4.77 when that row fell away. The same mechanism can just as easily drop a current report for most of the league in a future week, with no warning | none needed; correctness bug. Test: a pull covering 2 teams leaves every other team's latest report in force | **applied 2026-09-16** (`features.latest_injury_report`). Kept apart from the engine-change sequence because it is a data-pipeline correctness fix. For nflverse the report is now the latest week only, and within that week each team's latest pull; ESPN is unchanged (latest whole pull). Last week's statuses are deliberately not carried forward, so the 9/16 outcome (30 teams on ESPN until they file week 2) was the right one. Validated before landing: identical 137 selected rows on the live table, and injury_adj unchanged on all 16 week-2 games. The old code fails the new partial-pull test. Residual: a team whose whole report clears mid-week writes no rows, so its earlier same-week rows stay in force |
| P20 | ESPN "Injured Reserve" status is discarded, so IR'd starters vanish instead of counting as out | bug fix | 2026-09-16 | `ingest_injuries._status` keeps only out/doubtful/questionable/probable. HOU LB To'oTo'o (0.88 snaps) went to IR 09-16 and dropped out of the injury layer, instead of costing HOU ~1.06 pts. **Scope measured 2026-09-17:** the 22:50Z league-wide pull carried **40** players at `Injured Reserve`, every one of them silently dropped — this is league-wide, not a one-team case. Tonight's DET@BUF: Isiah Pacheco (DET, IR) contributed nothing to the injury layer, so DET's burden is understated and the true term favours BUF by more than the 1.56 served | none needed; correctness bug | proposed (after P19); **queued for the week of 2026-09-22** alongside 2A/P23 |
| P21 | ESPN rows carry no practice participation, so every Questionable player plays at a flat 0.55 | logic | 2026-09-16 | Penix: full practice, charged 2.52 (0.80 → 1.12). Terrell: DNP, charged 0.70 (0.25 → 1.17). Burrow: "says he will play", charged 2.70. ESPN's `shortComment` states the practice level in plain text | practice-aware play probability does not worsen NFL injury-term fit (P9) | proposed (after P19) |
| P22 | NFL power rating: no opponent adjustment; defense regressed the same as offense (×0.75); prior season carries ~94% in week 2 | logic | 2026-09-16 | CIN@HOU baseline −16.37 vs market −2.5. Of the +10.93 rating gap, +12.98 is the 2025 defensive EPA gap alone, −0.98 offense, −1.08 week 1. The only value flag on the week-2 slate comes from this. See also P5, P13 | rebuild with separate off/def regression (and opponent adjustment); weeks 1-4 and holdout MAE vs line must improve | proposed (after P19) |
| P23 | Usage shares: drop scrambles and kneels from carry shares (issue 2A) | bug fix | 2026-09-16 | `sim_data._usage_events` counts every `rush_attempt`, including 1,224 scrambles and 487 kneels (2025-26), while the engine separately credits every scramble to the QB. Read-only week-2 re-sim, 10k sims, 195 priced props: QB rush att 5.42 → 3.33 per team-game (real 2025 3.25), RB carries 20.54 → 22.61 (+10%), team rush att/yds and game totals/margins unchanged to 3 decimals. RB rush yds P(over) 0.329 → 0.393 vs market 0.500, about 40% of the RB gap. Receiving unchanged. See the 2026-09-16 entry | QB rush att ≈ 3.3 per team-game; RB carries up ≈ 10%; team rush totals, game totals and margins unchanged; rushing props correction re-fit with separate QB and RB offsets (P26) | proposed; **first engine change for the week of 2026-09-22**, measured on its own before `PENALTY_REPLAY` is switched on |
| P24 | Usage shares: QB-specific scramble rate (issue 2B) | logic | 2026-09-16 | The engine credits scrambles at the league rate (5.9% of dropbacks) whatever the QB (Goff 0.9%, Stafford 1.2%). With P23 applied, QB rush yds split both ways: runners well under (Lamar Jackson P(over) 0.146, Daniels 0.219), pocket QBs still over (D. Jones sim 19.4 vs 8.5 line, Purdy 21.6 vs 13.5) | QB rush att and rush yds P(over) centre near market for both running and pocket QBs, with no change to team totals | proposed (after P23 and `PENALTY_REPLAY`); low confidence |
| P25 | Usage shares: use backups' own history beyond the playing slots; FB prior is zero (issue 1) | logic | 2026-09-16 | `blend_roles` gives players beyond QB1/RB2/WR3/TE1/FB1 only the slot average: 76 have their own red-zone share at least 2x that average (TE2s Njoku, Freiermuth, Mayer, Kmet all a flat 3.2%). D. Waller (CAR TE3, 14.1% of targets) is simulated at 2.3%, falls under `MIN_TOUCHES` and drops out of the box score. FBs are zeroed even with history (Heyward 14% of goal-line carries) | per-player target and carry shares closer to realised week-by-week shares, and starters not pushed further under their prop lines | proposed (after P23 and `PENALTY_REPLAY`, alongside P24); risk: re-creating the demoted-starter problem |
| P26 | Props bias correction: fit offsets by position, not one per category | logic | 2026-09-16 | The single rushing offset (+0.346) hides two biases pulling in opposite directions: QB rush yds lean over (P(over) 0.649, 7/9 overs), RB rush yds lean under (0.329, 2/24). Their mean (0.416) looked like one under-bias. Receiving and passing corrections may hide the same thing, and not moving under P23 is no evidence either way | rebuild with P23: separate QB/RB rushing offsets; before trusting the receiving and passing offsets, check each by position (WR/TE/RB for receptions and rec yds; pocket vs running QBs for pass yds) and split any that disagree | proposed (with P23). **Until then the current correction stays displayed unchanged; read rushing yards with extra caution** |

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
