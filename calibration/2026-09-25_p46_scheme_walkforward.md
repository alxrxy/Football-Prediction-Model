# P46 walk-forward: scheme features against the live baseline (research only)

Criteria fixed in calibration-log.md (2026-09-25, "P46 scoped") before this ran.

Baseline replay: 2661 REG games 2016-2025 with a line.

Set A: 2645 games with every feature (2016-2025).

### Set A: A1_off_heavy, A2_off_pressure_allowed, A3_def_pressure, A4_off_box_on_runs

| test season | games | margin MAE base | + term | gain | Brier base | + term | ATS base | ATS + term | corr(term, cover) | corr(total term, total resid) | total MAE mkt | + term |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2019 | 260 | 10.637 | 10.602 | +0.036 | 0.2267 | 0.2249 | 124-126 | 125-125 | +0.105 | -0.036 | 10.800 | 10.827 |
| 2020 | 262 | 10.560 | 10.872 | -0.312 | 0.2247 | 0.2301 | 135-127 | 126-136 | -0.086 | +0.088 | 10.269 | 10.244 |
| 2021 | 272 | 11.272 | 11.299 | -0.027 | 0.2290 | 0.2298 | 137-131 | 140-128 | -0.010 | -0.051 | 10.789 | 10.850 |
| 2022 | 271 | 9.674 | 9.685 | -0.011 | 0.2347 | 0.2350 | 131-130 | 137-124 | -0.026 | +0.006 | 10.395 | 10.398 |
| 2023 | 272 | 10.476 | 10.451 | +0.025 | 0.2321 | 0.2316 | 125-133 | 126-132 | +0.056 | +0.009 | 10.239 | 10.246 |
| 2024 | 272 | 10.531 | 10.445 | +0.086 | 0.2219 | 0.2208 | 135-133 | 135-133 | +0.050 | -0.026 | 9.730 | 9.751 |
| 2025 | 272 | 10.887 | 10.848 | +0.040 | 0.2366 | 0.2387 | 123-148 | 125-146 | +0.020 | +0.029 | 10.393 | 10.380 |
| **pooled** | 1881 | 10.577 | 10.599 | -0.022 | 0.2294 | 0.2302 | 910-928 | 914-924 | +0.009 (p 0.342) | -0.001 (p 0.515) | 10.371 | 10.383 |

| criterion | result |
|---|---|
| S1 pooled MAE gain >= 0.10 | fail |
| S1 2025 MAE gain >= 0.10 | fail |
| S2 improves in >= 5 of 7 seasons (4) | fail |
| S3 pooled Brier not worse | fail |
| E1 pooled corr(term, cover) > 0, one-sided p < 0.05 | fail |
| E2 pooled ATS with term >= baseline | **pass** |
| E3 2025 corr(term, cover) > 0 | **pass** |
| T1 pooled corr(total term, total resid) > 0, one-sided p < 0.05 | fail |
| T2 pooled total MAE gain >= 0.10 | fail |
| T3 2025 total corr > 0 | **pass** |

Coefficients per test season (margin term, standardised features, points per SD):
- 2019: A1_off_heavy +1.17, A2_off_pressure_allowed -0.07, A3_def_pressure -1.29, A4_off_box_on_runs -0.07
- 2020: A1_off_heavy +1.44, A2_off_pressure_allowed -0.06, A3_def_pressure -1.12, A4_off_box_on_runs -0.24
- 2021: A1_off_heavy +0.45, A2_off_pressure_allowed -0.08, A3_def_pressure -0.87, A4_off_box_on_runs +0.09
- 2022: A1_off_heavy +0.10, A2_off_pressure_allowed +0.07, A3_def_pressure -0.91, A4_off_box_on_runs +0.06
- 2023: A1_off_heavy +0.22, A2_off_pressure_allowed +0.29, A3_def_pressure -0.88, A4_off_box_on_runs +0.04
- 2024: A1_off_heavy +0.22, A2_off_pressure_allowed +0.37, A3_def_pressure -0.95, A4_off_box_on_runs +0.06
- 2025: A1_off_heavy +0.40, A2_off_pressure_allowed +0.36, A3_def_pressure -1.04, A4_off_box_on_runs -0.12

Set B: 1071 games with every feature (2022-2025).

### Set B: B1_off_play_action, B2_off_motion, B3_def_blitz, B4_def_box_on_runs

| test season | games | margin MAE base | + term | gain | Brier base | + term | ATS base | ATS + term | corr(term, cover) | corr(total term, total resid) | total MAE mkt | + term |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2023 | 272 | 10.476 | 10.406 | +0.071 | 0.2321 | 0.2324 | 125-133 | 133-125 | +0.068 | +0.051 | 10.239 | 10.242 |
| 2024 | 272 | 10.531 | 10.666 | -0.135 | 0.2219 | 0.2224 | 135-133 | 132-136 | -0.003 | +0.003 | 9.730 | 9.713 |
| 2025 | 272 | 10.887 | 10.944 | -0.057 | 0.2366 | 0.2382 | 123-148 | 123-148 | +0.029 | +0.083 | 10.393 | 10.494 |
| **pooled** | 816 | 10.631 | 10.672 | -0.041 | 0.2302 | 0.2310 | 383-414 | 388-409 | +0.035 (p 0.158) | +0.026 (p 0.228) | 10.121 | 10.149 |

| criterion | result |
|---|---|
| S1 pooled MAE gain >= 0.10 | fail |
| S1 2025 MAE gain >= 0.10 | fail |
| S2 improves in >= 2 of 3 seasons (1) | fail |
| S3 pooled Brier not worse | fail |
| E1 pooled corr(term, cover) > 0, one-sided p < 0.05 | fail |
| E2 pooled ATS with term >= baseline | **pass** |
| E3 2025 corr(term, cover) > 0 | **pass** |
| T1 pooled corr(total term, total resid) > 0, one-sided p < 0.05 | fail |
| T2 pooled total MAE gain >= 0.10 | fail |
| T3 2025 total corr > 0 | **pass** |

Coefficients per test season (margin term, standardised features, points per SD):
- 2023: B1_off_play_action +0.91, B2_off_motion +1.37, B3_def_blitz -0.02, B4_def_box_on_runs +0.73
- 2024: B1_off_play_action +0.74, B2_off_motion +1.02, B3_def_blitz -0.23, B4_def_box_on_runs +0.59
- 2025: B1_off_play_action +0.79, B2_off_motion -0.13, B3_def_blitz +0.49, B4_def_box_on_runs +0.65

