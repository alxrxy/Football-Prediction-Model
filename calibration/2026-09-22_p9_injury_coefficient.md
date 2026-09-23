# P9 — the NFL injury term's coefficient, re-checked after P41 (diagnosis only)

Rules fixed in calibration-log.md (2026-09-22, "P9 scoped") before this ran.

## Gate 0 — inputs

| check                                                     | result                        | verdict   |
|-----------------------------------------------------------|-------------------------------|-----------|
| regenerated post-P41 matches training (every row, < 1e-9) | 3060/3060 (max diff 9.99e-16) | pass      |
| pre-P41 differs on exactly the 20 logged rows, max 0.588  | 20 rows, max 0.588            | pass      |


Games: **2661** (2016-2025, weeks <= 18, line present). Team-weeks at the 8.0 cap: **320** of 6041 scored (the QB / non-QB split is approximate only there).

Gate rows are the whole training file (3060), as P41's 20 were counted; 16 of the 20 fall inside the fit sample.

## Q1 — magnitude: actual - baseline(no injury) = a + beta x term

| sample              |    n | beta (95% CI)             | vs 1.0           |
|---------------------|------|---------------------------|------------------|
| full sample 2016-25 | 2661 | +0.546 (+0.359 to +0.734) | **excludes 1.0** |
| 2016                |  260 | +0.006 (-0.467 to +0.478) |                  |
| 2017                |  260 | +1.139 (+0.410 to +1.869) |                  |
| 2018                |  260 | +0.180 (-0.387 to +0.747) |                  |
| 2019                |  260 | +0.083 (-0.448 to +0.613) |                  |
| 2020                |  262 | +0.430 (-0.189 to +1.049) |                  |
| 2021                |  272 | +0.501 (-0.046 to +1.048) |                  |
| 2022                |  271 | +0.667 (+0.174 to +1.161) |                  |
| 2023                |  272 | -0.038 (-0.615 to +0.540) |                  |
| 2024                |  272 | +1.562 (+0.906 to +2.218) |                  |
| 2025                |  272 | +0.858 (+0.258 to +1.458) |                  |


**M1: pass** — the live coefficient 1.0 is outside the full-sample 95% CI.

### M2 — walk-forward: beta fitted on 2016..Y-1, applied to Y, against the live 1.0

| season             |    n |   beta (fit on prior) |   MAE at 1.0 |   MAE at beta | change     |
|--------------------|------|-----------------------|--------------|---------------|------------|
| 2019               |  260 |                 0.414 |       10.916 |        10.721 | -0.195     |
| 2020               |  262 |                 0.337 |       10.708 |        10.573 | -0.136     |
| 2021               |  272 |                 0.355 |       11.257 |        11.219 | -0.038     |
| 2022               |  271 |                 0.385 |        9.493 |         9.516 | +0.023     |
| 2023               |  272 |                 0.433 |       10.626 |        10.45  | -0.176     |
| 2024               |  272 |                 0.379 |       10.174 |        10.34  | +0.166     |
| 2025               |  272 |                 0.507 |       10.632 |        10.7   | +0.068     |
| **pooled 2019-25** | 1881 |                       |       10.541 |        10.501 | **-0.040** |


| M2 part         | verdict                              |
|-----------------|--------------------------------------|
| pooled >= 0.05  | fail                                 |
| >= 5/7 seasons  | fail                                 |
| 2025 not worse  | fail                                 |
| Brier not worse | fail                                 |
| (detail)        | improved 4/7; Brier 0.2259 -> 0.2268 |


**M2: fail. Q1 verdict: statistically off, immaterial: no change.**

### M3 — component split (diagnostic): QB part and non-QB part, jointly

| component               |   games non-zero | beta (95% CI)             |
|-------------------------|------------------|---------------------------|
| QB (6.0 x qb_loss_diff) |              757 | +0.704 (+0.435 to +0.973) |
| non-QB (remainder)      |             2661 | +0.418 (+0.170 to +0.666) |


Mean |term|: all 2.14, QB part 0.89, non-QB 1.67.

### M4 — P41 sensitivity: full-sample beta, pre vs post

|          | beta                      |
|----------|---------------------------|
| pre-P41  | +0.547 (+0.360 to +0.735) |
| post-P41 | +0.546 (+0.359 to +0.734) |
| delta    | -0.0008                   |


**M4: as expected** (|delta| 0.0008 vs the < 0.02 expectation).

## Q2 — edge (P9's logged adoption test): actual + market_spread = a + gamma x term

| sample              |    n | gamma (95% CI)            |   one-sided p |
|---------------------|------|---------------------------|---------------|
| full sample 2016-25 | 2661 | +0.161 (-0.012 to +0.335) |         0.034 |
| 2016                |  260 | -0.215 (-0.653 to +0.224) |         0.831 |
| 2017                |  260 | +0.709 (+0.049 to +1.370) |         0.018 |
| 2018                |  260 | -0.112 (-0.655 to +0.431) |         0.657 |
| 2019                |  260 | -0.206 (-0.718 to +0.306) |         0.785 |
| 2020                |  262 | +0.127 (-0.510 to +0.764) |         0.348 |
| 2021                |  272 | -0.034 (-0.564 to +0.497) |         0.549 |
| 2022                |  271 | +0.113 (-0.338 to +0.563) |         0.312 |
| 2023                |  272 | -0.173 (-0.699 to +0.354) |         0.74  |
| 2024                |  272 | +1.088 (+0.534 to +1.642) |         0     |
| 2025                |  272 | +0.334 (-0.215 to +0.884) |         0.116 |


| component (joint)   | gamma (95% CI)            |   one-sided p |
|---------------------|---------------------------|---------------|
| QB                  | +0.155 (-0.094 to +0.405) |         0.111 |
| non-QB              | +0.166 (-0.064 to +0.396) |         0.078 |


Cross-check with P28's re-test: corr(QB part, cover residual) = +0.022 over all 2661 games, +0.040 over the 757 where it fires. 2024-25 only: +0.119.

**Q2: pass** (gamma +0.161, one-sided p 0.034, 2655 games with a non-zero term).

## Q3 — market-implied size: -market_spread - baseline = a + beta_mkt x term (descriptive)

|                     | beta_mkt (95% CI)         |
|---------------------|---------------------------|
| term                | +0.385 (+0.323 to +0.448) |
| QB part (joint)     | +0.549 (+0.456 to +0.642) |
| non-QB part (joint) | +0.252 (+0.172 to +0.331) |


## 2026 weeks 1-2, descriptive only (stored terms, pre-P20/P41/P10)

|                                       | value                     |
|---------------------------------------|---------------------------|
| games                                 | 29                        |
| mean |term|                           | 1.67                      |
| corr(term, cover residual)            | +0.040                    |
| corr(term, actual - no-injury margin) | +0.093                    |
| beta (in-sample, no decision)         | +0.624 (-2.728 to +3.976) |


