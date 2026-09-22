# P37 part 2 — why 2026's baseline edges are bigger, and whether the market is ahead of them

Diagnosis only. Tests and rules as scoped in calibration-log.md (2026-09-22) before running.

Replay: 2661 games, 2016-2025. 2026: 30 graded baseline picks.

### Test 1: edge size by season, weeks 1-2

The live edge without its injury term, and the same edge counting last season's form only (the gap between the line and a 2025-only rating). 2026 is shown against both the stored line it was graded on and nflverse's close, which is the line the replay uses.

| season                |   n |   mean |edge| | share >= 4   |   mean |prior-only gap| |
|-----------------------|-----|---------------|--------------|-------------------------|
| 2016                  |  32 |          2.91 | 28%          |                    2.95 |
| 2017                  |  31 |          3.06 | 26%          |                    3.17 |
| 2018                  |  32 |          4.22 | 56%          |                    4.06 |
| 2019                  |  32 |          3.35 | 34%          |                    3.41 |
| 2020                  |  32 |          4.55 | 41%          |                    4.35 |
| 2021                  |  32 |          3.86 | 41%          |                    4.09 |
| 2022                  |  32 |          3.95 | 38%          |                    3.97 |
| 2023                  |  32 |          2.92 | 22%          |                    2.89 |
| 2024                  |  32 |          4.53 | 38%          |                    4.61 |
| 2025                  |  32 |          3.91 | 44%          |                    4.04 |
| 2026 (stored line)    |  30 |          4.33 | 50%          |                    4.79 |
| 2026 (nflverse close) |  30 |          4.38 | 50%          |                    4.83 |

2026's mean |edge| (stored line, no injury term) 4.33 against the replay's highest season 4.55 (2020): **not above all ten**.

### Test 2: QB change since last season

A team has changed QB when its week-1 starter is not its most frequent starter the season before (nflverse schedules).

| replay, weeks 1-4      |   n | ATS on the lean   |   binomial p (one-sided, < 50%) |
|------------------------|-----|-------------------|---------------------------------|
| either team changed QB | 361 | 176-179-6 (50%)   |                           0.458 |
| neither changed        | 274 | 134-134-6 (50%)   |                           0.524 |

Share of |edge| >= 4 picks in QB-change games, weeks 1-2:

|   season |   picks at |edge| >= 4 | share in QB-change games   | share of all games   |
|----------|------------------------|----------------------------|----------------------|
|     2016 |                      9 | 78%                        | 53%                  |
|     2017 |                      8 | 50%                        | 45%                  |
|     2018 |                     18 | 72%                        | 75%                  |
|     2019 |                     11 | 45%                        | 44%                  |
|     2020 |                     13 | 46%                        | 47%                  |
|     2021 |                     13 | 69%                        | 66%                  |
|     2022 |                     12 | 42%                        | 50%                  |
|     2023 |                      7 | 71%                        | 66%                  |
|     2024 |                     12 | 58%                        | 62%                  |
|     2025 |                     14 | 50%                        | 66%                  |
|     2026 |                     15 | 33%                        | 37%                  |

(a) QB-change leans below 50% at p < 0.05 in the replay: **no** (p 0.458). (b) 2026's big-edge share above every replay season: **no** (33% vs max 78%).

2026 by QB change (descriptive, n small):

| 2026           |   n | ATS         |   mean |edge| |
|----------------|-----|-------------|---------------|
| QB-change game |  11 | 1-9-1 (10%) |          4.34 |
| no change      |  19 | 8-11 (42%)  |          4.63 |

### Test 3: closing line value on the 2026 leans

| statistic                                      |   value |   perm p (one-sided, < 0) |
|------------------------------------------------|---------|---------------------------|
| mean CLV on the lean (pp of cover probability) |  -0.2   |                     0.321 |
| corr(|edge|, CLV)                              |   0.146 |                     0.779 |

n = 30; the line moved toward the lean in 8, away in 10, about unchanged in 12. Basis: consensus 30.

Mean CLV at |edge| >= 4: +2.80 pp (n 15); below 4: -3.20 pp.

Descriptive: graded at the logged close instead of the stored line, the same 30 leans go 9-20-1 (31%) (stored line: 9-20-1 (31%)).

### Test 4: how accurate were the lines? Weeks 1-2

| season                |   n |   line MAE vs final margin (pts) |
|-----------------------|-----|----------------------------------|
| 2016                  |  32 |                             8.5  |
| 2017                  |  31 |                            11.56 |
| 2018                  |  32 |                             9.62 |
| 2019                  |  32 |                            11.09 |
| 2020                  |  32 |                             7.36 |
| 2021                  |  32 |                            10.44 |
| 2022                  |  32 |                             9.33 |
| 2023                  |  32 |                             8.69 |
| 2024                  |  32 |                            10.05 |
| 2025                  |  32 |                             7.06 |
| 2026 (nflverse close) |  30 |                            11.55 |
| 2026 (stored line)    |  30 |                            11.45 |

2026's closing MAE ranks 10 of 11 (1 = most accurate). Below all ten: **no**. Descriptive only at n = 30.

### Test 5: how unusual is 9-20? (noise reference)

2026 leans 9-20-1 (31%): binomial p 0.061 two-sided at 50%.

|   replay season | weeks 1-2 ATS   |
|-----------------|-----------------|
|            2016 | 20-12 (62%)     |
|            2017 | 15-15-1 (50%)   |
|            2018 | 17-14-1 (55%)   |
|            2019 | 15-16-1 (48%)   |
|            2020 | 17-15 (53%)     |
|            2021 | 15-17 (47%)     |
|            2022 | 12-19-1 (39%)   |
|            2023 | 18-12-2 (60%)   |
|            2024 | 19-12-1 (61%)   |
|            2025 | 16-16 (50%)     |

## Verdict by the pre-set rules

- **H1, 2026 rating miscalibration:** not met (size above all ten: no; QB-change test: no).
- **H2, market ahead and more so on big edges:** not met.
- **H2b, sharper line:** no (descriptive).
- **H3, noise:** stands.
