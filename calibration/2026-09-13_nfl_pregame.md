# NFL 2026-09-13 — pre-kickoff snapshot (not yet graded)

Final pre-kickoff run, 2026-09-13 ~16:35Z, after the stale-injury-row fix (calibration-log P1): nflverse re-pulled, Odds API live, ESPN injuries and weather from a 16-minute cache. These are the numbers stored in `predictions` and the ones this slate will be graded against. The earlier 16:18Z run (with stale rows) is kept in the scratchpad snapshot only. Spreads are home lines.

| Kick   | Away @ Home   |   Model |   Market |   Edge | Lean   | Flag   | Home WP   | Tier   |   Inj adj | Weather   |   ML model |   ML edge | Generated   |
|--------|---------------|---------|----------|--------|--------|--------|-----------|--------|-----------|-----------|------------|-----------|-------------|
| 17:00Z | CHI @ CAR     |     5.9 |      3   |   -2.9 | CHI    | value  | 32%       | high   |      -0.8 | 85F 3mph  |        2.3 |       0.7 | 16:35Z      |
| 17:00Z | TB @ CIN      |     4.3 |     -3.5 |   -7.8 | TB     | value  | 37%       | high   |      -1.1 | 88F 5mph  |       -3.1 |      -0.4 | 16:35Z      |
| 17:00Z | NO @ DET      |    -9   |     -7   |    2   | DET    | value  | 76%       | high   |       1   | dome      |      -11.1 |       4   | 16:35Z      |
| 17:00Z | BUF @ HOU     |    -2.7 |      1   |    3.7 | HOU    | value  | 58%       | high   |       1.1 | dome      |        0.7 |       0.3 | 16:35Z      |
| 17:00Z | BAL @ IND     |    -5.9 |      3   |    8.9 | IND    | value  | 67%       | high   |       1   | dome      |        4.6 |      -1.6 | 16:35Z      |
| 17:00Z | CLE @ JAX     |   -12.2 |     -8.5 |    3.7 | JAX    | value  | 83%       | high   |      -0   | 87F 7mph  |       -8.2 |      -0.2 | 16:35Z      |
| 17:00Z | ATL @ PIT     |    -4.8 |     -6.5 |   -1.7 | ATL    | —      | 64%       | high   |       3.1 | 77F 3mph  |       -4.1 |      -2.4 | 16:35Z      |
| 17:00Z | NYJ @ TEN     |    -2.5 |     -1   |    1.5 | TEN    | —      | 58%       | high   |      -0.3 | 92F 5mph  |       -1.6 |       0.6 | 16:35Z      |
| 20:25Z | ARI @ LAC     |   -11.2 |     -9.5 |    1.7 | LAC    | —      | 80%       | high   |       2   | dome      |       -8.1 |      -1.4 | 16:35Z      |
| 20:25Z | MIA @ LV      |     3.1 |     -3   |   -6.1 | MIA    | value  | 41%       | high   |       0.4 | dome      |        6.5 |      -9.5 | 16:35Z      |
| 20:25Z | GB @ MIN      |     0.9 |     -1.5 |   -2.5 | GB     | value  | 47%       | high   |       1.7 | dome      |       -1.5 |       0   | 16:35Z      |
| 20:25Z | WAS @ PHI     |   -13   |     -6   |    7   | PHI    | value  | 84%       | high   |       0.2 | 79F 4mph  |       -5.5 |      -0.5 | 16:35Z      |
| 00:20Z | DAL @ NYG     |    -2.4 |      3   |    5.4 | NYG    | value  | 57%       | high   |       0.1 | 73F 5mph  |       -2.3 |       5.3 | 16:35Z      |

| Game      |   Away inj pts | Away top charged                                                                                |   Home inj pts | Home top charged                                                                            |
|-----------|----------------|-------------------------------------------------------------------------------------------------|----------------|---------------------------------------------------------------------------------------------|
| CHI @ CAR |           -5.9 | Miller Moss QB out (2.1); Kyler Gordon CB out (1.1); Jamree Kromah DE out (0.6)                 |           -6.7 | Haynes King QB out (2.1); Taylor Moton OT out (1.6); Patrick Jones II LB out (0.8)          |
| TB @ CIN  |           -3.2 | Jalen McMillan WR doubtful (0.6); Ayden Garnes CB out (0.6); Justin Skule T doubtful (0.6)      |           -4.3 | Shemar Stewart DE doubtful (0.9); Myles Hinton OT out (0.6); Connor Lew C out (0.5)         |
| NO @ DET  |           -5   | Zach Wilson QB out (2.1); Cameron Jordan LB out (0.6); Mason Murphy OT out (0.6)                |           -4   | Kerby Joseph S out (1.1); Ahmed Hassanein DE out (0.6); Mekhi Wingo DT out (0.6)            |
| BUF @ HOU |           -4.6 | Dorian Strong CB out (0.7); Mike Danna DE out (0.6); Jude Bowry OT out (0.6)                    |           -3.5 | Nate Thomas OT out (0.6); Collin Wright CB out (0.6); Will Anderson Jr. DE dnp (0.5)        |
| BAL @ IND |           -5.6 | Joe Fagnano QB out (2.1); Teddye Buchanan LB out (0.8); Nnamdi Madubuike DT out (0.8)           |           -4.6 | Riley Leonard QB out (2.4); Johnathan Edwards CB out (0.6); George Gumbs Jr. LB out (0.4)   |
| CLE @ JAX |           -5.6 | Taylen Green QB out (2.1); Toriano Pride Jr. CB out (0.6); Noah Igbinoghene CB out (0.6)        |           -5.6 | Quinn Ewers QB out (2.1); Anton Harrison T dnp (0.7); Bryan Thomas Jr. DE out (0.6)         |
| ATL @ PIT |           -8   | Michael Penix Jr. QB out (5.6); Billy Bowman Jr. CB out (1.4); Jake Matthews T dnp (0.7)        |           -4.9 | Will Howard QB out (2.1); Joey Porter Jr. CB questionable (0.7); Gabriel Rubio DE out (0.6) |
| NYJ @ TEN |           -2.8 | Joseph Ossai DE out (0.6); D'Angelo Ponds CB doubtful (0.5); Tim Patrick WR out (0.5)           |           -3.1 | Cedric Gray LB out (1.1); Jackie Marshall DT out (0.5); Owen Pappoe LB out (0.4)            |
| ARI @ LAC |           -3.4 | Garrett Williams CB out (1.4); Isaiah Adams G out (0.8); Dadrion Taylor-Demerson S out (0.6)    |           -1.4 | Isaiah World OT out (0.6); Tuli Tuipulotu DE questionable (0.6); Deane Leonard CB out (0.1) |
| MIA @ LV  |           -1.2 | Storm Duck CB out (0.6); Darrell Baker Jr. CB out (0.6)                                         |           -0.8 | Brock Bowers TE out (0.8)                                                                   |
| GB @ MIN  |           -2.4 | Josh Jacobs RB out (0.6); Warren Brinson DT out (0.5); Aaron Banks G questionable (0.5)         |           -0.7 | Christian Darrisaw T dnp (0.6); Harrison Smith S limited (0.1)                              |
| WAS @ PHI |           -1   | Deatrich Wise Jr. DE out (0.7); Daron Payne DT limited (0.1); K'Lavon Chaisson LB limited (0.1) |           -0.7 | Jonathan Greenard LB out (0.4); Eli Stowers TE out (0.3)                                    |
| DAL @ NYG |           -0.3 | Malik Davis RB out (0.2); Luke Schoonmaker TE dnp (0.1)                                         |           -0.2 | Malik Nabers WR questionable (0.2)                                                          |
