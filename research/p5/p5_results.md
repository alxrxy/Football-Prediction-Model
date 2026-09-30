# P5 (NFL): large early-season edges on the P22 rating (research only)

Frozen A+B rebuilt: penalty 300, carry off 0.459 / def 0.394 (published 0.459 / 0.394).
Reproduces the published weeks 1-4 row (n, >=3, >=6, lean slope): (635, (123, 102, 5), (30, 19, 0), 0.044) vs (635, (123, 102, 5), (30, 19, 0), 0.044): **YES**

## Gate: P37 lean slope, weeks 1-4 (cap only if negative with permutation p < 0.05)

- lean slope **+0.044**, permutation p **0.859** (10,000 permutations) -> **NO CAP**

## Reported, not a gate

| abs edge, weeks 1-4 | n | ATS | model MAE | line MAE | model - line |
|---|---|---|---|---|---|
| < 3 | 405 | 212-186-7 (53%) | 9.49 | 9.49 | +0.00 |
| 3 to < 6 | 181 | 93-83-5 (53%) | 11.14 | 10.57 | +0.57 |
| >= 6 | 49 | 30-19 (61%) | 11.22 | 10.03 | +1.19 |
| all | 635 | 335-288-12 (54%) | 10.10 | 9.84 | +0.25 |


Margin error: `model MAE` is the rating's margin against the result; `line MAE` is the closing line's.
