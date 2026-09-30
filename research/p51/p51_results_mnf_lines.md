# P51 validation replay (research only) - SENSITIVITY: PHI @ CHI on the MNF-day lines

- week 2: depth chart as of 2026-09-17T12:34:29Z (before first kickoff 2026-09-18 00:15Z); props snapshot pre-friday_2026-09-18
- week 3: depth chart as of 2026-09-24T12:42:08Z (before first kickoff 2026-09-25 00:15Z); props snapshot pre-sunday_2026-09-27
- week 4: depth chart as of 2026-09-30T06:02:36Z (before first kickoff 2026-10-02 00:15Z); props snapshot data

Team-games replayed: 96 (weeks 2-3 with a pbp starter: 64; week 4 unplayed: 32)

| # | criterion | result | verdict |
|---|---|---|---|
| 1 | CHI week 3 comes out as Keenum | before Tyson Bagent, after Case Keenum (pbp starter C.Keenum) | **pass** |
| 2 | no team-game flips right -> wrong | 0 flips; 1 wrong -> right | **pass** |
| 3 | every firing case listed | 3 firing (below) | **listed** |
| 4 | every non-firing team-game byte-identical | 93/93 identical (squad order, shares, shifts, passer weights) | **pass** |
| 5 | suite passes | run separately | see log |

## Firing cases

| week | game | team | QB1 before | QB1 after | pbp starter | priced | right before -> after |
|---|---|---|---|---|---|---|---|
| 2 | 2026_02_MIN_CHI | MIN | Carson Wentz | Carson Wentz | C.Wentz | Carson Wentz | True -> True |
| 3 | 2026_03_PHI_CHI | CHI | Tyson Bagent | Case Keenum | C.Keenum | Case Keenum | False -> True |
| 3 | 2026_03_SEA_WAS | WAS | Marcus Mariota | Marcus Mariota | M.Mariota | Marcus Mariota | True -> True |

Reported, not a criterion: team-games where the sim's QB1 is still not the pbp starter after the rule: 3
- wk2 2026_02_CAR_ATL ATL: sim Tua Tagovailoa, pbp C.Rush, priced -
- wk2 2026_02_NYG_LA NYG: sim Jaxson Dart, pbp J.Winston, priced Jaxson Dart
- wk2 2026_02_SEA_ARI SEA: sim Sam Darnold, pbp D.Lock, priced Drew Lock
