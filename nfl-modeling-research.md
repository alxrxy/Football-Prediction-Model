# Building an Accurate Free/Open-Source NFL Prediction System: Best Practices (2025–2026)

## TL;DR
- The ~45% ATS result is the expected outcome of a naive "my number ≠ market number → bet" system, not a bug in one module: the NFL closing line is highly efficient (Joseph Buchdahl of Pinnacle Odds Dropper notes that "for very popular [markets] like the English Premier League or the NFL, there is ample evidence to show that the closing line/odds provide a reasonable measure of the true outcome probabilities"), break-even at −110 is 52.38% (110/210, with 4.76% vig on a −110/−110 market), and the fix is to (a) recalibrate probabilities against the market as a Bayesian prior, (b) track closing line value (CLV) rather than win-rate as the primary success metric, and (c) only flag edges that survive vig and a realistic error band.
- The highest-leverage technical upgrades are: replace rolling-average opponent adjustment with a single ridge/mixed-model regression that solves offense + defense + HFA simultaneously; make play-calling in the Monte Carlo engine an explicit function of win probability and score differential (game script); and blend model output with the market line in log-odds space rather than treating them as independent.
- Player props are where public-data edge is most achievable (books price them less sharply than sides/totals); model them as a hierarchical chain — P(active) → snap share → opportunities (carries/targets) → efficiency per opportunity → distribution — and always output a full distribution (negative binomial for counts, lognormal for yards), not a point estimate.

## Key Findings

1. **Opponent adjustment**: The public state of the art is a single regularized regression (ridge/L2 or a multilevel/mixed model) with one coefficient per offense, one per defense, plus a home-field term, fit on play-level EPA. This is strictly better than the older rolling-average "subtract opponent's lagged EPA from league mean" approach because it solves all teams simultaneously and shrinks small samples toward the mean.
2. **Game script**: Play-calling is a strong, well-documented function of score differential and time; the correct primitive is Pass Rate Over Expected (PROE), where expected pass rate is modeled from down, distance, score differential, time and field position. The simulation engine should condition run/pass on the *simulated* live win-probability state, and props should be projected as the average over simulated game scripts, not a static volume assumption.
3. **Calibration**: Use Brier score and log loss (both strictly proper scoring rules) plus reliability diagrams, and decompose Brier into reliability/resolution/uncertainty. Recalibrate with Platt scaling (works on small samples) rather than isotonic (needs 500–1000+ points).
4. **Edge detection**: The dominant lesson from r/algobetting and open-source repos is that beating the closing line is the only trustworthy evidence of edge, genuine edge from public data is thin, and most models "work" in backtests and die live from overfitting, ignoring vig, and undersized samples.
5. **Props**: Model usage share and redistribute it on injuries; weight recent games more but keep a long career prior with shrinkage; red-zone/goal-line share is the key TD-scorer signal; always express uncertainty as a distribution.
6. **Live WP / rest-of-game**: The nflfastR XGBoost WP model is open-source, well-calibrated, and directly usable; "rest of game" is best done by continuing the same drive-based Monte Carlo from the current game state rather than from pregame priors.

## Details

### 1. Opponent adjustment methodology

**Rolling-average approach (baseline, what many hobby models use).** Jonathan Goldberg's Open Source Football post "Adjusting EPA for Strength of Opponent" (2020) computes each team's weekly offensive and defensive EPA/play, takes a 10-game moving average of opponents faced, lags it by one week (so you only use information available up to that point), and adds an adjustment factor = (league mean − opponent's lagged EPA) to each team's raw EPA. In his test this improved game-outcome prediction accuracy only marginally (adjusted 64.0% vs unadjusted 63.5%). The follow-up "Exploring Rolling Averages of EPA" found that (a) splitting into pass vs rush EPA and adjusting each against the opponent's corresponding defense is better than adjusting holistically; (b) weighting recent games more heavily increases predictive power; and (c) adjusting *defense* for opponent offense slightly *decreased* predictive power ("defenses are a product of the offenses they face").

**Ridge / mixed-model approach (state of the art for public data).** The stronger and now-standard method is to fit a single regression with a dummy per offense, a dummy per defense, and a home-field term, using play-level EPA as the response:
`EPA ~ offense_team + defense_team + home_field`
using ridge (L2) regularization. The CollegeFootballData blog ("Opponent Adjusted Stats using Ridge Regression") documents this exact recipe: L2 penalty tuned by cross-validation, home-field coded +1/−1/0, drop mismatched (FBS-vs-FCS) games and undefined-EPA plays. The Open Source Football post "Estimating Team Ability From EPA" (Baldwin, 2021) does the multilevel version and returns "regularized, opponent-adjusted measures of offensive and defensive EPA/play for each team." The regularization is essential: an amateur analyst who used lambda.min in cross-validation found it "punished good teams and benefitted bad teams," and lambda.1se (more shrinkage) gave more sensible ratings.

Key implementation notes for the existing system:
- **The regularization/shrinkage is the fix for "performance against weak opponents overweighted."** Solving offense and defense simultaneously means a big EPA day against a bad defense is automatically discounted because that defense's coefficient absorbs it.
- MetricGate's "Context-Adjusted EPA" documents an intermediate approach: regress raw EPA on down, yards-to-go, score differential, and game seconds remaining, and use the residual — this strips 10–25% of variance and roughly doubles year-over-year stability (context-adjusted EPA is ~1.5× as repeatable as raw EPA).
- DVOA's proprietary refinements worth emulating in open code: opponent adjustments only kick in after ~Week 4 (small-sample protection), performance in the fourth quarter of blowouts is downweighted (garbage-time filter), and interceptions/fumbles are handled at a fixed value to reduce turnover noise.
- **Do NOT opponent-adjust with a rolling average if you can afford one regression per week.** Rebuild ratings point-in-time each week (only earlier weeks' data) to avoid leakage.

### 2. Game-script / win-probability-conditioned play-calling

The core public metric is **Pass Rate Over Expected (PROE)**. Expected pass rate is modeled per play from down, distance, score differential, time remaining, and field position (this is nflfastR's open `xpass` model); PROE = actual − expected. This matters because raw run/pass splits are dominated by game script: trailing teams pass, leading teams run, and the effect intensifies each quarter (documented as strongest in the 4th quarter). The neutral-script filter analysts use is: score within one score, first/second down, win probability roughly 20–80%, outside the final two minutes of each half.

For a simulation engine, the DraftKings Engineering write-up "Modeling Football" (Ian Dorward, 2024) is the best public blueprint. Their play-by-play engine:
- Uses a **team-specific binary classifier for run vs pass** at each play, taking quarter, field position, yards-to-go, down, and *score difference* as inputs — i.e., game script is built into the decision.
- Applies adjustments in **logit space** so probabilities stay in [0,1] when shifting (e.g., a 3rd-and-1 gets a run-probability bump added in log-odds, then converted back).
- Chains multinomial classifiers: play type → yards attempted → outcome (complete/incomplete/INT/sack) → yards after catch → fumble, updating game state after each play.
- Has a **separate 4th-down layer** whose first decision is "will they go for it" — and crucially notes they model whether a team *will* go for it (descriptive), not whether they *should* (normative). This is the correct choice for a prediction engine.
- Includes an explicit **time-runoff model** (seconds elapsed as a function of score difference, period, clock, timeouts) so game script feedback loops emerge naturally.

Implementation recommendation: the run/pass probability at each simulated play should be a function of the *current simulated* score differential and time (and therefore implicitly win probability), so that when a team falls behind in a given simulation, its pass rate rises, which raises QB/WR volume and lowers RB volume in that simulation. Player-prop projections should then be the *distribution across simulations*, which automatically bakes in game-script correlation (e.g., a WR's yards and his team trailing are positively correlated).

### 3. Calibration methodology

**Metrics.** Use both strictly-proper scoring rules:
- **Brier score** = mean squared error between predicted probability and 0/1 outcome; range [0,1], lower is better. For NFL win prediction, Brier < 0.20 is good; always-0.5 gives 0.25.
- **Log loss** (cross-entropy); punishes confident wrong predictions harshly.
- **Reliability diagram**: bin predictions (equal-width or equal-count), plot mean predicted probability vs observed frequency; the 45° line is perfect. Report the number of bins and binning scheme.
- **Brier / Murphy decomposition** into reliability (calibration gap — recalibration reduces this), resolution (class separation — only a better model improves this), and uncertainty (base rate p(1−p), a property of the data). Two models with the same Brier can differ a lot in the reliability/resolution mix — this is why diagnostic plots matter and why a single number is insufficient.
- ECE is useful but is *not* a proper scoring rule; pair it with Brier/log loss.

**Recalibration.** The standard fix for a model whose ranking is fine but whose probabilities are off ("good rankings, wrong probabilities") is a post-hoc calibration map fit on a held-out set:
- **Platt scaling** (logistic regression on the raw scores): 2 parameters, works with as few as ~50 calibration examples, monotonic so it preserves AUC/ranking. Best choice for the NFL because of small samples.
- **Beta calibration**: 3 parameters, stable at ~100–200 examples, contains the identity map.
- **Isotonic regression**: nonparametric, needs ~500–1000+ points or it overfits and produces jagged probabilities.
Use a held-out calibration split (e.g., 50/25/25 train/calibrate/test) or out-of-fold predictions; in-sample ECE is biased downward.

**How much data before recalibrating.** NFL has only ~272 regular-season games/year, so per-season samples are tiny; this is the binding constraint. Practical guidance from the sources: prefer the low-parameter methods (Platt) given the sample; recalibrate on rolling multi-season windows rather than within a single season; and validate on a genuinely held-out season. On the betting side, there is a sharp asymmetry between validating a win-rate edge and validating CLV: Buchdahl estimates that for a 5% even-money edge "it might take several thousand bets before I would confidently rule out chance," whereas because CLV has a much smaller standard deviation (~0.1 vs ~1.0 for even-money P/L), statistical significance on CLV can appear in "as few as just 50" bets (he computed "only 65 bets" for one sample). The r/algobetting consensus reflects the same point in reverse: declaring a win-rate victory after ~60 bets is a named failure mode. One open-source system (the-algo) sets its blend-weight adaptation to drift at most ±0.02/week and requires a floor of 30 picks before adjusting.

### 4. Value/edge detection against sportsbook lines

**Why the naive approach yields ~45% ATS.** The NFL closing line is one of the most efficient markets in sports — it already incorporates injuries, weather, and sharp money. Academic tests repeatedly fail to reject market efficiency, finding only "isolated" and "transient" inefficiencies (e.g., Oswald, "Testing the efficiency of the NFL betting market," 2022, UNI ScholarWorks Honors Thesis); Szalkowski & Nelson (2012, arXiv:1211.4000) found that only ~20% of their 2,560 games (2002–2011) moved more than one point from open to close. Break-even at standard −110 juice is **52.38%** (110/210), with 4.76% vig on a −110/−110 market; at −115 the break-even rises. Note one commonly-cited "beatable" result to keep expectations realistic: Szalkowski & Nelson found home teams beat the spread only 47% of the time overall, but a narrow strategy of betting home underdogs over 2002–2011 would have returned 53.5% — just above the 52.38% break-even — the kind of thin, backward-looking, possibly-arbed edge that is typical of what the literature turns up.

A model that simply bets whenever its number differs from the market's, with no calibration to the market, will (a) bet mostly on its own noise, and (b) systematically fade the sharpest available estimate — which is exactly how you land *below* 50%. The-algo repo (an unusually honest open-source NFL model) reports its 27-feature model walk-forward validated at exactly **50.0%** against the closing spread and its authors refuse to publish model picks because a model measured at 50% "is measurably worse than predicting 0.5." They also A/B-tested adding injury/availability features to full-game spreads and found it moved Brier by 0.0001 and accuracy by −0.3pp (noise), because "books read the same injury report hours earlier."

**Closing Line Value (CLV) as the real success metric.** CLV = the difference between the (vig-free) probability implied by the price you bet and the vig-free probability implied by the closing price. Consistently beating the closing line is the single most reliable predictor of long-term profit — Buchdahl reports that across "nearly 20,000 bets in my Wisdom of the Crowd betting system, the actual profit over turnover of 3.4% compares closely to the expected value of 4.0%," i.e., beating the close translated into realized profit. Critical implementation detail: compute CLV against a **vig-free (devigged) closing line**, not the raw price. The magnitude is real and measurable — of 952 +EV bets Buchdahl flagged, 756 "saw either price shortening or no price movement… with an average price shortening of 3.94%." Devig method matters: he calls the "equal margin method" (proportional/multiplicative) "rather crude and frankly inaccurate" and recommends odds-ratio, logarithm, or Shin methods. Caveat from Unabated: CLV is only a valid proxy in an *efficient* market (like NFL sides/totals); in inefficient markets it can mislead.

**What actually works (from the sources):**
- **Line shopping / devigged consensus** is a real edge that doesn't require out-forecasting anyone: devig many books (multiplicative, additive, power, or Shin methods), build a sharp-anchored consensus fair price, and bet only where a book offers better than that consensus. The-algo runs exactly this and treats it as its entire live signal. (Buchdahl separately identifies Pinnacle as the sharpest reference book to anchor a consensus on.)
- **Blend model with market**, don't replace it. Combine your model probability with the market's implied probability in **log-odds (logit) space** with weight w on the model; start w near 0 and only increase it as the model demonstrates positive CLV. This treats the market as a strong Bayesian prior and is the mathematically correct way to avoid betting on your own noise.
- **Require edge beyond vig + an error band.** Only flag a bet when model probability exceeds the vig-free implied probability by a margin (e.g., 3+ percentage points is a commonly cited threshold) large enough to survive the model's own calibration error.
- **Fractional Kelly** for sizing, with correlation haircuts for correlated bets (same-game props).

**How much edge is realistically achievable.** The honest answer across r/algobetting write-ups: real but thin — enough that the reward for a winning model is getting limited by the book, not a jackpot. On props, edge is more achievable because books price them less sharply.

### 5. Player prop modeling techniques

**Architecture (hierarchical chain).** The best public/open-source pattern (used by the-algo's prop design and Unabated's tutorial) is a conditional chain, multiplied together:
1. **P(active)** — does the player play at all. This is where practice-participation/injury signal actually pays off (the-algo measured +0.054 AUC on P(active) from practice participation, and notes this is a *prop* input, not a spread input).
2. **Snap share given active.**
3. **Opportunities** — carries / targets / pass attempts, driven by game script (spread magnitude, implied total, pace).
4. **Per-opportunity outcome** — yards per carry / per target, completion, YAC — the matchup-adjusted efficiency layer.
5. **Compose the distribution** and add cross-prop correlation (e.g., a Gaussian copula for same-team players, as in the Brandon-Kimberly fantasy sim).

**Usage rate & recency weighting.** Weight recent games more, but keep a long prior with shrinkage. The nfl-player-props repo (iens126) uses an exponential decay where weights **halve every 6 games** (a half-life) and each offseason counts as ~8 extra games of decay, reading a player's whole career rather than a fixed last-N window — "recent form leads; a proven career never drops to zero." A common simpler public choice (willyjo423, several tools) is a recency-weighted **last-4-game** window times an opponent multiplier (defense-vs-position allowed relative to league average), clipped to ±25% so one fluky game doesn't distort the projection. With little history, **shrink the spread toward a league-typical value** so a thin sample yields a *wider* projection, not false precision.

**Red-zone / goal-line usage for TD scorers.** Anytime-TD is the market most systematically mispriced. The key signals are red-zone target share (WR/TE) and red-zone/inside-the-10/inside-the-5 carry share (RB). Razzball's TD share tool identifies players with anomalously high/low TD rates over a rolling 18-week window (min 4 games) and regresses them, using position-specific models on overall and red-zone shares. Elite RB1s score in ~50–60% of games, RB2s ~35–45% — use these as sanity priors. TD props are essentially binary with high variance; size accordingly.

**Injury / depth-chart redistribution.** When a player is ruled out, redistribute his projected usage (carries, targets, red-zone touches) to the backups explicitly rather than just zeroing him. The-algo notes a real pitfall here: "a backup start currently corrupts a team's rating for weeks" without QB-conditional ratings, and that bust probability should not be a fixed player constant. Redistribution should be role-aware (goal-line back inherits goal-line carries; slot WR's targets flow to the next slot, not the outside WR).

**Distributions & uncertainty.** Match the distribution to the stat:
- **Counts** (carries, targets, receptions, attempts): **negative binomial** — its variance μ + μ²/k exceeds the mean, handling the overdispersion real usage shows (Poisson, with variance = mean, underestimates spread).
- **Yards**: **lognormal** or zero-inflated lognormal (yards are non-negative, right-skewed, with a spike at zero for players who don't get a touch).
- Report a full distribution and hit-probability, and use a "pass" call when the projection sits near the line — a tool that always finds an edge is overfitting.

### 6. In-game live win probability and "rest of game" projection

**The open-source WP model to use is nflfastR's.** It is an XGBoost binary-logistic model, documented in full by Ben Baldwin ("nflfastR EP, WP, CP xYAC, and xPass models," 2020; "NFL win probability from scratch using xgboost in R," 2021). The production **spread-adjusted** model (the source of nflfastR's `vegas_wp`, `vegas_home_wp`, `vegas_wpa` columns) uses these features:
`receive_2h_ko, spread_time, home, half_seconds_remaining, game_seconds_remaining, Diff_Time_Ratio, score_differential, down, ydstogo, yardline_100, posteam_timeouts_remaining, defteam_timeouts_remaining` (the no-spread model drops `spread_time`).

Two engineered features (both created by `nflfastR:::prepare_wp_data()`) do most of the work:
- **Diff_Time_Ratio** = point_differential · e^(4·(3600 − game_seconds_remaining)/3600) — a time-weighted score differential whose weight grows late in the game. Baldwin calls score differential and this ratio "the most important features."
- **spread_time** = posteam_spread · e^(−4·(3600 − game_seconds_remaining)/3600) — the pregame spread, decayed toward zero as the game progresses.

Production hyperparameters (spread model): booster gbtree, objective binary:logistic, eval_metric logloss, nrounds=534, eta=0.05, gamma=0.79012017, subsample=0.9224245, colsample_bytree=5/12, max_depth=5, min_child_weight=7, with monotone_constraints `(0, 0, 0, 0, 0, 1, 1, -1, -1, -1, 1, -1)` — forcing WP to increase in Diff_Time_Ratio, score_differential, and posteam timeouts, and decrease in down, ydstogo, yardline_100, and defteam timeouts (receive_2h_ko, spread_time, home, and the two raw time features are unconstrained). The monotone constraints are important for sensible end-game behavior — they make it "impossible for increasing the size of a team's lead to result in a decrease in win probability." Receive/defer is handled by the binary `receive_2h_ko` feature; the two timeout features are separate (posteam +1, defteam −1). (The no-spread teaching model uses nrounds=65, eta=0.2, max_depth=4 and no constraints; do not conflate the two parameter sets — the production model is the 534/0.05 one.)

Calibration is excellent: leave-one-season-out (LOSO) calibration error of **0.0066** for the Vegas-line model vs **0.0397** for the older nflscrapR model (the no-spread nflfastR model is 0.0055). Incorporating the spread cut classification error from 27% to 23% and log loss from 0.52 to 0.44. Adding the over/under, or removing the home indicator, both worsened calibration. Overtime is excluded ("overtime is hard"). Lock & Nettleton (2014, random forest) and Yurko et al. (2019, GAM in nflscrapR) are the peer-reviewed antecedents; the single most important feature in all of them is score differential.

**ESPN comparison.** An independent comparison (arXiv 2602.09982) found ESPN's WP model outscored the Open Source Football (nflfastR) model on log loss, Brier, and a "Kelly credibility" metric for the four example games examined — so if you want a second calibrated reference, ESPN's is competitive, but nflfastR's is the one you can fully reproduce and self-host.

**"Rest of game" projection.** The right design is to run the *same* drive-based Monte Carlo engine but **seed each simulation with the current game state** (score, possession, down, distance, field position, time, timeouts) instead of the opening kickoff, then simulate only the remaining plays. This gives a distribution of final scores and remaining player stats conditioned on reality, which is strictly better than scaling a pregame projection. For a lightweight cross-check, a Poisson/enumeration model over remaining scoring drives gives a fast analytic WP that avoids Monte Carlo noise. For in-progress player props, prorate remaining production by time left (e.g., remaining = projected_remaining · max(0, 1 − elapsed/game_length)), and handle missing live data by degrading to an explicit "unavailable" state rather than guessing zero (this pattern is exactly what the riskittogetthebrisket repo implements for rest-of-season/rest-of-game player projection).

### 7. General pitfalls and lessons learned

From r/algobetting, open-source repos, and the analytics literature:
1. **Overfitting is the #1 killer.** A model that nails the last three seasons has usually memorized noise. Keep the model simple; be suspicious of great backtests.
2. **Backtest fantasy / leakage.** Validating on the same data used for tuning; letting a game's plays appear in both train and validation folds (nflfastR explicitly warns to split folds by *game*, not by play, and ideally by season). Rebuild ratings point-in-time.
3. **Ignoring the vig.** 52% at −110 still loses money. Edge lives *after* the juice.
4. **No CLV tracking.** Without it you can't tell a real edge from a hot streak until the bankroll is gone.
5. **Undersized samples.** Declaring a win-rate victory after ~60 bets; sports variance needs hundreds–thousands (whereas CLV can be validated in ~50–65).
6. **Data quality beats model complexity.** Clean inputs matter more than neural-net-vs-logistic. The #1 bug in this class of system is silent player-name mismatches between the odds feed and nflverse IDs — quarantine unresolved names, never fuzzy-match silently.
7. **Train/serve skew.** Use a single source-of-truth feature spec imported by both training and live-serving code; a hash mismatch should refuse to serve. Skew "produces confident garbage that no metric will catch."
8. **Bitemporal storage.** Store *when you learned* each fact (Wednesday vs Friday injury report), so a model predicting at Wednesday-time never sees Friday's data — otherwise you leak future info into backtests.
9. **Winning gets you limited.** The reward for a working model is the book cutting your stakes — plan for line-shopping across many books from day one.
10. **LLMs don't emit probabilities.** If you add an LLM layer, use it to gather/evaluate evidence and *downgrade* (veto) bets, never to produce a number — "a number you cannot backtest is a number you cannot bet."

## Recommendations

**Stage 1 — Fix calibration and edge logic first (this is what's causing 45% ATS):**
1. Stop flagging edges on raw model-vs-market differences. Devig the market line (avoid the crude equal-margin method; use odds-ratio, logarithm, or Shin), and only compare your probability to the *vig-free* implied probability.
2. Blend model and market in log-odds space with a small model weight w (start w≈0.1–0.2), and require edge > vig + a calibration-error band (start ~3 percentage points) before flagging.
3. Instrument **CLV tracking** immediately: capture your bet's devigged probability and the closing devigged probability (anchored on a sharp book such as Pinnacle) for every flagged bet. This becomes your real scoreboard, and because CLV's standard deviation is ~10× smaller than P/L's, it becomes statistically meaningful in ~50–65 bets rather than thousands. Set the go/no-go benchmark: publish/act on picks only once you log positive CLV over ~65+ bets.
4. Add Platt scaling on a held-out season to recalibrate the moneyline/WP probabilities; measure Brier, log loss, and a reliability diagram before/after.

**Stage 2 — Upgrade the team-strength core:**
5. Replace rolling-average opponent adjustment with a weekly ridge (or mixed-model) regression: `EPA ~ offense + defense + home`, tuned by CV (use more shrinkage / lambda.1se), rebuilt point-in-time, with a garbage-time filter and opponent adjustments delayed until ~Week 4.
6. Feed these opponent-adjusted offense/defense ratings into the Monte Carlo drive engine's per-play parameters.

**Stage 3 — Game-script-aware simulation:**
7. Make the engine's run/pass decision (and time runoff) an explicit function of the current simulated score differential, time, down/distance and field position — via nflfastR's `xpass` plus a team PROE term. This is the single change that most improves both totals and props.
8. Derive props as distributions across the 10,000 simulations so game-script correlation is automatic.

**Stage 4 — Prop engine as a hierarchical chain:**
9. Implement P(active) → snap share → opportunities → per-opportunity efficiency → distribution, with negative-binomial counts and lognormal yards, recency weighting (half-life ~6 games) with career shrinkage, red-zone share for TDs, and explicit role-aware usage redistribution on injuries. Prioritize props over sides/totals — this is where public-data edge is most achievable.

**Stage 5 — Live:**
10. Reuse the drive engine seeded from live game state for rest-of-game projections; expose nflfastR `vegas_wp` as a calibrated cross-check; prorate in-progress player stats by time remaining.

**Benchmarks that change the plan:** if after ~65+ logged bets your CLV is negative, keep model weight w at 0 and rely only on line-shopping (this is a legitimate edge). If Brier on a held-out season isn't below 0.25 (the always-0.5 baseline), the model has no signal and should not be bet at any weight. If prop backtests beat closing prop lines on CLV while sides/totals don't, concentrate on props.

## Caveats
- **Market efficiency is the hard ceiling.** Multiple academic studies (e.g., Oswald 2022; Szalkowski & Nelson 2012) and the most credible open-source projects conclude that beating the NFL closing line on sides/totals with public data is very hard; the-algo's honest 50.0% result is the base-rate expectation. Treat any backtest above ~53% ATS with suspicion until confirmed by live CLV.
- **Many cited betting-education/prop-tool pages are commercial** (PropsBot, Propeller, Unabated, SportBot) and some quote self-reported win rates (e.g., "73.9% win rate," "21,066 props graded") that are marketing claims, not independently verified — use them for methodology, not as evidence of achievable ROI.
- **Small NFL samples** (~272 games/season) make single-season calibration noisy; use multi-season rolling windows and low-parameter recalibration.
- The nflfastR injury data source ceased after the 2024 season; live injury feeds now require Sleeper/ESPN scraping, which use undocumented endpoints that change without notice.
- Numbers presented for the nflfastR WP model are from the model author's own posts (primary source) and are the production values as of the 2020/2021 documentation; verify against the current `fastrmodels` package version before implementation.