# Calibration log

Running record of graded slates and the model changes they suggest. **Nothing
in here has been applied to the model** unless its status says so. One slate is
far too few games to recalibrate on, so each proposal is logged with the
evidence behind it and the test it has to pass, and evidence is added to it
week by week.

Newest entry first. Per-game tables live in `calibration/<date>_<sport>.md`.

## How to add an entry

```bash
python -m src.grade --sport ncaaf --refresh          # pull finals, fill actual_* columns
python calibration/analyze_slate.py 2026-09-19 calibration/2026-09-19_ncaaf.md
```

Then add a dated section below and update the tracker: add the slate's
evidence to each proposal, and flip a status only when its adoption test is
met.

## Proposal tracker

| ID | Proposal | Kind | First seen | Evidence so far | Adoption test | Status |
|----|----------|------|------------|-----------------|---------------|--------|
| P1 | Charge only injury rows from the latest pull per team/week | bug fix | 2026-09-13 | 29 stale NFL rows; would flip 2 of 13 value flags today | none needed; it's a correctness bug | **applied 2026-09-13** (`features.latest_injury_report`); NFL slate re-run before kickoff |
| P2 | Stop pricing unknown-snap QBs at 35% of a starter | logic | 2026-09-13 | 8/13 NFL games carry a ~2.1 pt charge for a backup/rookie QB | rebuild NFL training with the change; holdout MAE vs line must not get worse | proposed |
| P3 | Replace the flat FCS proxy (-28); grade proxy games separately | logic + reporting | 2026-09-12 | proxy games: model MAE 17.1 vs market 10.8, ATS 13-20 | proxy-game MAE within 2 pts of the market over 100+ games | proposed |
| P4 | Make confidence tiers discriminate: SP+/Elo agreement, early-season demotion | logic | 2026-09-12 | 47/47 rated games were "high"; edge vs Elo disagree 6-10, agree 17-14 | "high" beats "medium" ATS over 200+ graded games | proposed |
| P5 | Upper edge cap for early-season CFB (large edge = stale rating) | threshold | 2026-09-12 | rated \|edge\| 6-10 went 2-7; weeks 1-2 market-vs-rating gap is 2x later weeks historically | \|edge\|>8 in weeks 1-4 loses ATS over 60+ games | proposed |
| P6 | CFB home field 2.4 → ~2.8 | weight | 2026-09-12 | slate: model leaned away 30/47, -2.1 pts vs market; history: market-implied HFA 3.2 (2017-25) but 0.5 in 2025 | mean signed edge on non-neutral games < -1.0 across 4+ weeks | watch |
| P7 | Do not use the CFB ML model's margins until its compression is explained | investigate | 2026-09-12 | mean \|ML margin\| 9.5 vs actual 24.7; MAE 20.6 | n/a, diagnose first | investigate |

Not proposed: **raising VALUE_EDGE_THRESHOLD on its own.** On this slate the
baseline's edge had essentially no relationship to the cover result (see
below), and a higher threshold keeps the flag's error while firing less
often. The threshold only becomes meaningful after P3–P5 remove the edges that
are just rating error.

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

## 2026-09-13 — NFL (week 1), pre-kickoff snapshot, not yet graded

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
