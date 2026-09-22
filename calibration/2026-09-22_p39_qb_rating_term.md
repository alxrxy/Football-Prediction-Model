# P39 — the QB-vs-rating term: edge first, then the sim anchor

Design and validation only. Tests, arms and pass rules as scoped in calibration-log.md (2026-09-22) before running.

2661 games 2016-2025 with a line, both ratings and both starters' terms (0 dropped for a missing starter or team). Arm U = I + S exactly: max |U - I - S| = 2.00e-15.

## Gate 0: is the rebuild the logged term? (arm U, k fitted 2022-23, judged 2024-25)

| quantity                             |   logged 2026-09-20 | rebuild     |
|--------------------------------------|---------------------|-------------|
| k (fitted 2022-23)                   |               0.78  | 0.548       |
| k on 2024-25 itself                  |               0.727 | 0.831       |
| margin MAE without the term, 2024-25 |              11.557 | 10.709      |
| margin MAE with the term, 2024-25    |              10.903 | 10.608      |
| mean |term| (k applied / raw)        |               4.17  | 1.25 / 2.29 |
| corr(term, market spread)            |              -0.324 | +0.108      |

**Not an exact rebuild** by the pre-set tolerance (both MAEs within 0.10, k within 0.10). n = 544 games.

## Phase 1: edge against the line (walk-forward, k refitted each season on 2016 to the season before)

### Arm U, unrestricted (as logged)

| season         | k          | corr(term, cover residual)   | ATS without     | ATS with        |   corr(term, spread) |
|----------------|------------|------------------------------|-----------------|-----------------|----------------------|
| 2019           | +0.693     | -0.090                       | 124-126 (49.6%) | 132-118 (52.8%) |                0.277 |
| 2020           | +0.597     | -0.005                       | 135-127 (51.5%) | 140-122 (53.4%) |                0.19  |
| 2021           | +0.636     | -0.017                       | 137-131 (51.1%) | 133-135 (49.6%) |               -0.181 |
| 2022           | +0.623     | -0.084                       | 131-130 (50.2%) | 129-132 (49.4%) |                0.2   |
| 2023           | +0.602     | +0.027                       | 125-133 (48.4%) | 126-132 (48.8%) |                0.04  |
| 2024           | +0.611     | -0.045                       | 136-132 (50.7%) | 130-138 (48.5%) |                0.183 |
| 2025           | +0.610     | +0.046                       | 123-148 (45.4%) | 120-151 (44.3%) |                0.034 |
| pooled 2019-25 | per season | -0.024 (p 0.849)             | 911-927 (49.6%) | 910-928 (49.5%) |                0.096 |

E1 pooled corr > 0 at p < 0.05: **no**. E2 ATS not worse: **no**. E3 2025 corr > 0: **yes** (+0.046). Phase 1 for arm U: **fail**.

### Arm I, identity (QB change)

| season         | k          | corr(term, cover residual)   | ATS without     | ATS with        |   corr(term, spread) |
|----------------|------------|------------------------------|-----------------|-----------------|----------------------|
| 2019           | +0.881     | -0.068                       | 124-126 (49.6%) | 130-120 (52.0%) |                0.018 |
| 2020           | +0.772     | -0.009                       | 135-127 (51.5%) | 136-126 (51.9%) |               -0.099 |
| 2021           | +0.799     | -0.033                       | 137-131 (51.1%) | 134-134 (50.0%) |               -0.435 |
| 2022           | +0.667     | -0.095                       | 131-130 (50.2%) | 128-133 (49.0%) |               -0.037 |
| 2023           | +0.648     | -0.009                       | 125-133 (48.4%) | 123-135 (47.7%) |               -0.254 |
| 2024           | +0.614     | +0.036                       | 136-132 (50.7%) | 133-135 (49.6%) |               -0.058 |
| 2025           | +0.672     | +0.075                       | 123-148 (45.4%) | 125-146 (46.1%) |               -0.336 |
| pooled 2019-25 | per season | -0.012 (p 0.703)             | 911-927 (49.6%) | 909-929 (49.5%) |               -0.187 |

E1 pooled corr > 0 at p < 0.05: **no**. E2 ATS not worse: **no**. E3 2025 corr > 0: **yes** (+0.075). Phase 1 for arm I: **fail**.

### Arm S, scale (rating regression)

| season         | k          | corr(term, cover residual)   | ATS without     | ATS with        |   corr(term, spread) |
|----------------|------------|------------------------------|-----------------|-----------------|----------------------|
| 2019           | -0.059     | -0.065                       | 124-126 (49.6%) | 123-127 (49.2%) |                0.566 |
| 2020           | -0.074     | +0.006                       | 135-127 (51.5%) | 134-128 (51.1%) |                0.637 |
| 2021           | +0.039     | +0.041                       | 137-131 (51.1%) | 136-132 (50.7%) |                0.64  |
| 2022           | +0.297     | -0.002                       | 131-130 (50.2%) | 133-128 (51.0%) |                0.428 |
| 2023           | +0.278     | +0.065                       | 125-133 (48.4%) | 128-130 (49.6%) |                0.535 |
| 2024           | +0.395     | -0.183                       | 136-132 (50.7%) | 131-137 (48.9%) |                0.551 |
| 2025           | +0.108     | -0.042                       | 123-148 (45.4%) | 120-151 (44.3%) |                0.572 |
| pooled 2019-25 | per season | -0.041 (p 0.961)             | 911-927 (49.6%) | 905-933 (49.2%) |                0.307 |

E1 pooled corr > 0 at p < 0.05: **no**. E2 ATS not worse: **no**. E3 2025 corr > 0: **no** (-0.042). Phase 1 for arm S: **fail**.

## Phase 2: the sim anchor (walk-forward margin accuracy)

### Arm U, unrestricted (as logged)

| season   |    n |     k |   MAE without |   MAE with |   change |
|----------|------|-------|---------------|------------|----------|
| 2019     |  260 | 0.693 |        10.639 |     10.542 |   -0.098 |
| 2020     |  262 | 0.597 |        10.558 |     10.42  |   -0.138 |
| 2021     |  272 | 0.636 |        11.278 |     11.228 |   -0.049 |
| 2022     |  271 | 0.623 |         9.676 |      9.627 |   -0.049 |
| 2023     |  272 | 0.602 |        10.474 |     10.388 |   -0.086 |
| 2024     |  272 | 0.611 |        10.534 |     10.516 |   -0.017 |
| 2025     |  272 | 0.61  |        10.884 |     10.691 |   -0.193 |
| pooled   | 1881 |       |        10.578 |     10.488 |   -0.09  |

Brier (sigma 13.0) 0.2295 -> 0.2274. The line's own MAE on these games: 9.813. S1 (>= 0.10 better in 2025 and pooled): **no** (2025 -0.193). S2 (better in >= 5 of 7): **yes** (7/7). S3 (Brier not worse): **yes**.

### Arm I, identity (QB change)

| season   |    n |     k |   MAE without |   MAE with |   change |
|----------|------|-------|---------------|------------|----------|
| 2019     |  260 | 0.881 |        10.639 |     10.571 |   -0.068 |
| 2020     |  262 | 0.772 |        10.558 |     10.423 |   -0.135 |
| 2021     |  272 | 0.799 |        11.278 |     11.345 |    0.067 |
| 2022     |  271 | 0.667 |         9.676 |      9.638 |   -0.038 |
| 2023     |  272 | 0.648 |        10.474 |     10.464 |   -0.01  |
| 2024     |  272 | 0.614 |        10.534 |     10.378 |   -0.155 |
| 2025     |  272 | 0.672 |        10.884 |     10.699 |   -0.185 |
| pooled   | 1881 |       |        10.578 |     10.503 |   -0.075 |

Brier (sigma 13.0) 0.2295 -> 0.2268. The line's own MAE on these games: 9.813. S1 (>= 0.10 better in 2025 and pooled): **no** (2025 -0.185). S2 (better in >= 5 of 7): **yes** (6/7). S3 (Brier not worse): **yes**.

### Arm S, scale (rating regression)

| season   |    n |      k |   MAE without |   MAE with |   change |
|----------|------|--------|---------------|------------|----------|
| 2019     |  260 | -0.059 |        10.639 |     10.639 |   -0     |
| 2020     |  262 | -0.074 |        10.558 |     10.564 |    0.006 |
| 2021     |  272 |  0.039 |        11.278 |     11.275 |   -0.003 |
| 2022     |  271 |  0.297 |         9.676 |      9.676 |   -0     |
| 2023     |  272 |  0.278 |        10.474 |     10.448 |   -0.026 |
| 2024     |  272 |  0.395 |        10.534 |     10.65  |    0.116 |
| 2025     |  272 |  0.108 |        10.884 |     10.886 |    0.002 |
| pooled   | 1881 |        |        10.578 |     10.591 |    0.014 |

Brier (sigma 13.0) 0.2295 -> 0.2300. The line's own MAE on these games: 9.813. S1 (>= 0.10 better in 2025 and pooled): **no** (2025 +0.002). S2 (better in >= 5 of 7): **no** (4/7). S3 (Brier not worse): **no**.

**S4, what the gain is:** arm U pooled gain +0.090, arm S -0.014, arm I +0.075. Arm S carries >= 2/3 of arm U: **no**.

## Verdict by the pre-set rules

- Gate 0: not an exact rebuild (see gate 0).
- Arm U, unrestricted (as logged): phase 1 fail; phase 2 fail (S1 False, S2 True, S3 True).
- Arm I, identity (QB change): phase 1 fail; phase 2 fail (S1 False, S2 True, S3 True).
- Arm S, scale (rating regression): phase 1 fail; phase 2 fail (S1 False, S2 False, S3 False).
- S4: the gain is not mostly scale.
