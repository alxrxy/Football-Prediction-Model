# P37 — why bigger baseline edges cover less often (diagnosis only)

## Part A — the 30 graded 2026 baseline picks

### Test 1: significance

| statistic                                      | value                          |   perm p (one-sided, < 0) |   perm p (two-sided) |
|------------------------------------------------|--------------------------------|---------------------------|----------------------|
| slope of lean-direction cover margin on |edge| | -0.42 pts per pt of edge       |                     0.272 |                0.638 |
| corr(edge, home cover residual)                | -0.231 (95% CI -0.55 to +0.14) |                     0.108 |                0.221 |

All picks 9-20 (31%): binomial P(<= 9 of 29 | 50%) = 0.031 (one-sided), 0.061 two-sided.
>= 4 pts 4-10: binomial P(<= 4 of 14 | 50%) = 0.090 (one-sided). **Descriptive only**: the cut-off was chosen after seeing the data.

### Test 4: scale (2026)

home cover residual = b x edge: **b = -0.61** (95% CI -1.50 to +0.27). b < 0 means the edge points the wrong way; 0 < b < 1 means right way, too large.
Mean |edge| 2026: 4.52 pts (median 4.03).

### Test 3: decomposition (2026)

| part of the edge                 |   sd | corr with cover residual (95% CI)   |   perm p (< 0) | ATS leaning on it alone   | ATS where |part| >= 4   |
|----------------------------------|------|-------------------------------------|----------------|---------------------------|-------------------------|
| full edge                        | 5.3  | -0.231 (-0.55 to +0.14)             |          0.108 | 9-20-1 (31%)              | 4-10-1 (29%)            |
| rating + situational (no injury) | 5.19 | -0.258 (-0.57 to +0.11)             |          0.084 | 11-18-1 (38%)             | 4-10-1 (29%)            |
| injury term only                 | 2.29 | +0.050 (-0.32 to +0.40)             |          0.608 | 12-17-1 (41%)             | 2-3 (40%)               |

### Test 5: concentration (exploratory, n too small to test)

| split                              |   n | ATS          | ATS at |edge| >= 4   |   mean |edge| |
|------------------------------------|-----|--------------|----------------------|---------------|
| leaned the favourite               |  18 | 7-10-1 (41%) | 3-5-1 (38%)          |           4.5 |
| leaned the underdog                |  12 | 2-10 (17%)   | 1-5 (17%)            |           4.5 |
| leaned home                        |  18 | 6-12 (33%)   | 3-6 (33%)            |           4.2 |
| leaned away                        |  12 | 3-8-1 (27%)  | 1-4-1 (20%)          |           5   |
| |injury adj| >= 2                  |   7 | 0-7 (0%)     | 0-5 (0%)             |           5.8 |
| |injury adj| < 2                   |  23 | 9-13-1 (41%) | 4-5-1 (44%)          |           4.1 |
| a starting QB charged (>= 2.5 pts) |   7 | 1-6 (14%)    | 0-4 (0%)             |           4.2 |
| no QB charge                       |  23 | 8-14-1 (36%) | 4-6-1 (40%)          |           4.6 |
| week 1                             |  14 | 3-11 (21%)   | 1-4 (20%)            |           4.2 |
| week 2                             |  16 | 6-9-1 (40%)  | 3-6-1 (33%)          |           4.8 |

## Part B — the live Layer 1 replayed, 2016-2025 (no injury term)

2582 regular-season games with a line. Each week's ratings use only that season's earlier weeks plus the previous season, exactly as the live `compute_ratings` does.

Replay vs stored live Layer 1 on 2026 weeks 1-2: n = 30, median |diff| 0.00 pts, max 0.00.

### Test 2: ATS by |edge| and corr(edge, cover residual), by part of the season

| games      |    n |   mean |edge| | >= 0               | >= 2             | >= 3             | >= 4             | >= 6            | corr (95% CI)                 | b (95% CI)           |
|------------|------|---------------|--------------------|------------------|------------------|------------------|-----------------|-------------------------------|----------------------|
| weeks 1-2  |  309 |          3.73 | 158-144-7 (52%)    | 102-97-3 (51%)   | 78-75-2 (51%)    | 60-52-2 (54%)    | 29-27-1 (52%)   | +0.068 (-0.04, +0.18) p=0.236 | +0.16 (-0.14, +0.45) |
| weeks 1-4  |  615 |          3.6  | 298-305-12 (49%)   | 199-191-6 (51%)  | 148-153-5 (49%)  | 107-108-4 (50%)  | 54-55-3 (50%)   | +0.047 (-0.03, +0.13) p=0.249 | +0.13 (-0.10, +0.35) |
| weeks 5-18 | 1967 |          3.48 | 951-965-51 (50%)   | 583-607-38 (49%) | 429-468-26 (48%) | 326-342-16 (49%) | 155-178-4 (47%) | -0.027 (-0.07, +0.02) p=0.239 | -0.07 (-0.20, +0.05) |
| all weeks  | 2582 |          3.51 | 1249-1270-63 (50%) | 782-798-44 (49%) | 577-621-31 (48%) | 433-450-20 (49%) | 209-233-7 (47%) | -0.008 (-0.05, +0.03) p=0.672 | -0.02 (-0.13, +0.08) |

### Test 3 on the replay: which part of the edge carries the sign? (weeks 1-4)

| part (points, home minus away)   |   sd |   coef on cover residual | 95% CI           |
|----------------------------------|------|--------------------------|------------------|
| pri_off                          | 5.24 |                    0.031 | (-0.174, +0.235) |
| pri_def                          | 4    |                    0.158 | (-0.108, +0.424) |
| cur_off                          | 1.35 |                   -0.375 | (-1.174, +0.424) |
| cur_def                          | 1.3  |                   -0.516 | (-1.338, +0.307) |
| sit                              | 0.43 |                   -2.297 | (-4.732, +0.138) |

A positive coefficient means that part of the rating knows something the line does not; zero means the line already has it; negative means leaning on it loses. All five parts enter the edge with weight 1.

### Edge size: 2026 against the replay

Mean |edge|: 2026 weeks 1-2 **4.52** (with the injury term), 4.33 without it; replayed weeks 1-2 3.73. Share of picks at |edge| >= 4: 2026 50%, replay 37%.

### Post-hoc (not in the scoped plan): home vs away leans, and the home-field term

| games     | ATS leaning home   | ATS leaning away   |   mean home cover residual (pts) |
|-----------|--------------------|--------------------|----------------------------------|
| weeks 1-4 | 152-172-7 (47%)    | 146-133-5 (52%)    |                            -0.24 |
| all weeks | 651-691-40 (49%)   | 598-579-23 (51%)   |                            -0.04 |

Added after seeing Test 3's situational coefficient; read as a lead, not a result.

### Per-season corr(edge, cover residual), weeks 1-4

|   season |   n |   corr | ATS           |
|----------|-----|--------|---------------|
|     2016 |  55 |  0.027 | 28-27 (51%)   |
|     2017 |  59 | -0.043 | 29-29-1 (50%) |
|     2018 |  59 |  0.117 | 33-25-1 (57%) |
|     2019 |  59 |  0.112 | 30-28-1 (52%) |
|     2020 |  63 |  0.045 | 32-31 (51%)   |
|     2021 |  64 | -0.083 | 27-37 (42%)   |
|     2022 |  64 | -0.082 | 28-33-3 (46%) |
|     2023 |  64 |  0.073 | 31-28-5 (53%) |
|     2024 |  64 |  0.195 | 34-29-1 (54%) |
|     2025 |  64 | -0.006 | 26-38 (41%)   |

