# P68 replay (read-only), weeks 2-3 + PIT @ CLE

post-game rosters read: wk2 32 teams, wk3 32 teams, wk4 32 teams

## Bound: upper (every flag seen at any pregame read)
flags 487: genuine 370, false 116, third 1

| group | flags | false | genuine | third bucket | unknown |
|---|---|---|---|---|---|
| QB | 86 | 12 | 74 | 0 | 0 |
| skill | 92 | 29 | 62 | 1 | 0 |
| OL | 96 | 16 | 80 | 0 | 0 |
| defense/ST | 213 | 59 | 154 | 0 | 0 |

(i) identical-to-last-week lists: 0 of 20 lists with a prior week; on genuine lists (no false flag): 0 of 2 = 0.0% false-alarm rate

(ii) candidates, weeks 3-4 (R3 and D need a prior list). Points / usage removed (false flags held) vs added (genuine held)
| group | candidate | caught / false | wrong holds / genuine | pts removed | pts added | net pts | use removed | use added | eligible |
|---|---|---|---|---|---|---|---|---|---|
| skill | R2 | 5/7 | 13/26 | 1.03 | 0.79 | +0.24 | 0.19 | 0.46 | SPLIT (to user) |
| skill | R3 | 7/7 | 9/26 | 1.88 | 0.69 | +1.19 | 0.35 | 0.20 | yes |
| skill | R2&R3 | 5/7 | 9/26 | 1.03 | 0.69 | +0.34 | 0.19 | 0.20 | SPLIT (to user) |
| skill | D | 0/7 | 0/26 | 0.00 | 0.00 | +0.00 | 0.00 | 0.00 | holds nothing |
| OL | R2 | 6/6 | 21/30 | 0.00 | 3.60 | -3.60 | 0.00 | 0.00 | no |
| OL | R3 | 5/6 | 20/30 | 0.00 | 2.42 | -2.42 | 0.00 | 0.00 | no |
| OL | R2&R3 | 5/6 | 20/30 | 0.00 | 2.42 | -2.42 | 0.00 | 0.00 | no |
| OL | D | 0/6 | 0/30 | 0.00 | 0.00 | +0.00 | 0.00 | 0.00 | holds nothing |
| defense/ST | R2 | 20/25 | 36/55 | 8.30 | 3.14 | +5.17 | 0.00 | 0.00 | yes |
| defense/ST | R3 | 24/25 | 26/55 | 10.53 | 2.91 | +7.62 | 0.00 | 0.00 | yes |
| defense/ST | R2&R3 | 19/25 | 24/55 | 8.20 | 1.95 | +6.25 | 0.00 | 0.00 | yes |
| defense/ST | D | 0/25 | 0/55 | 0.00 | 0.00 | +0.00 | 0.00 | 0.00 | holds nothing |
| QB | R2 | 7/7 | 28/29 | 12.11 | 30.63 | -18.52 | 0.00 | 0.00 | no |
| QB | R3 | 7/7 | 26/29 | 12.11 | 25.83 | -13.72 | 0.00 | 0.00 | no |
| QB | R2&R3 | 7/7 | 26/29 | 12.11 | 25.83 | -13.72 | 0.00 | 0.00 | no |
| QB | D | 0/7 | 0/29 | 0.00 | 0.00 | +0.00 | 0.00 | 0.00 | holds nothing |
context, R2 on weeks 2-4 (non-QB): caught 90/104, wrong holds 192/296, net pts +4.56

## Bound: lower (flags on the latest stored read)
flags 424: genuine 370, false 53, third 1

| group | flags | false | genuine | third bucket | unknown |
|---|---|---|---|---|---|
| QB | 84 | 10 | 74 | 0 | 0 |
| skill | 77 | 14 | 62 | 1 | 0 |
| OL | 88 | 8 | 80 | 0 | 0 |
| defense/ST | 175 | 21 | 154 | 0 | 0 |

(i) identical-to-last-week lists: 0 of 20 lists with a prior week; on genuine lists (no false flag): 0 of 12 = 0.0% false-alarm rate

(ii) candidates, weeks 3-4 (R3 and D need a prior list). Points / usage removed (false flags held) vs added (genuine held)
| group | candidate | caught / false | wrong holds / genuine | pts removed | pts added | net pts | use removed | use added | eligible |
|---|---|---|---|---|---|---|---|---|---|
| skill | R2 | 1/1 | 13/26 | 0.00 | 0.79 | -0.79 | 0.04 | 0.46 | no |
| skill | R3 | 1/1 | 9/26 | 0.00 | 0.69 | -0.69 | 0.04 | 0.20 | no |
| skill | R2&R3 | 1/1 | 9/26 | 0.00 | 0.69 | -0.69 | 0.04 | 0.20 | no |
| skill | D | 0/1 | 0/26 | 0.00 | 0.00 | +0.00 | 0.00 | 0.00 | holds nothing |
| OL | R2 | 2/2 | 21/30 | 0.00 | 3.60 | -3.60 | 0.00 | 0.00 | no |
| OL | R3 | 2/2 | 20/30 | 0.00 | 2.42 | -2.42 | 0.00 | 0.00 | no |
| OL | R2&R3 | 2/2 | 20/30 | 0.00 | 2.42 | -2.42 | 0.00 | 0.00 | no |
| OL | D | 0/2 | 0/30 | 0.00 | 0.00 | +0.00 | 0.00 | 0.00 | holds nothing |
| defense/ST | R2 | 2/5 | 36/55 | 1.50 | 3.14 | -1.63 | 0.00 | 0.00 | no |
| defense/ST | R3 | 5/5 | 26/55 | 2.92 | 2.91 | +0.01 | 0.00 | 0.00 | yes |
| defense/ST | R2&R3 | 2/5 | 24/55 | 1.50 | 1.95 | -0.45 | 0.00 | 0.00 | no |
| defense/ST | D | 0/5 | 0/55 | 0.00 | 0.00 | +0.00 | 0.00 | 0.00 | holds nothing |
| QB | R2 | 6/6 | 28/29 | 11.09 | 30.63 | -19.54 | 0.00 | 0.00 | no |
| QB | R3 | 6/6 | 26/29 | 11.09 | 25.83 | -14.74 | 0.00 | 0.00 | no |
| QB | R2&R3 | 6/6 | 26/29 | 11.09 | 25.83 | -14.74 | 0.00 | 0.00 | no |
| QB | D | 0/6 | 0/29 | 0.00 | 0.00 | +0.00 | 0.00 | 0.00 | holds nothing |
context, R2 on weeks 2-4 (non-QB): caught 37/43, wrong holds 192/296, net pts -11.86

## Selection (decision 1 rule; must win under both bounds; within noise the simpler rule wins)
Noise: 90% game-bootstrap CI of the difference in net points between the top candidate and each simpler eligible one.
- **skill**: upper -> most caught: R3; lower -> none eligible. **no rule wins under both bounds: today’s behaviour**
- **OL**: upper -> none eligible; lower -> none eligible. **no rule wins under both bounds: today’s behaviour**
- **defense/ST**: upper -> most caught: R3; lower -> most caught: R3. **SELECTED R3**

## (iii) Decision 3: B (held player keeps report probability) vs A (promoted to 1.0), Brier vs played
- upper non-QB R2: no held player with a game status (A and B identical)
- upper non-QB R3: n 9, Brier A 0.222, B 0.171, B-A 90% CI -0.252..+0.130 -> within noise: A (today) stays
- upper non-QB R2&R3: no held player with a game status (A and B identical)
- upper QB R2: no held player with a game status (A and B identical)
- upper QB R3: no held player with a game status (A and B identical)
- upper QB R2&R3: no held player with a game status (A and B identical)
- lower non-QB R2: no held player with a game status (A and B identical)
- lower non-QB R3: n 5, Brier A 0.400, B 0.177, B-A 90% CI -0.550..+0.072 -> within noise: A (today) stays
- lower non-QB R2&R3: no held player with a game status (A and B identical)
- lower QB R2: no held player with a game status (A and B identical)
- lower QB R3: no held player with a game status (A and B identical)
- lower QB R2&R3: no held player with a game status (A and B identical)

- D's promotion cost: unlisted Questionables on identical-list teams: 0 (0 played)

## (iv) Decision 4: ESPN-only out/doubtful rows, not on the official report, played the prior week, charged, then played
- C-flaggable rows: 42; stale charged cases (charged and played): 0 
- B's minimum is 5 by the end of week 10 (decision 4): 0 so far.

## Sensitivity (run after, reported, selection unchanged): D against the prior week's POST-GAME ESPN list

The replay compares each list with the prior week's stored pregame list, which still holds that week's stale flags, so
D never fires. ESPN carries forward the prior week's post-game list, so the sensitivity compares against that:
34 lists have a prior post-game list; **1 is identical: week 4 PIT (8 flags, 0 false by snap counts)**; genuine lists
identical: 1 of 2 (upper) / 1 of 23 (lower). D's only firing is a false alarm. 20 of 34 upper lists contain all of last
week's post-game list plus new names (the carry-over signature), but only exact matches trigger D.

Week 4 PIT @ CLE by snap counts: Joey Porter Jr., Spencer Anderson, Parker Brailsford: no snap row (did not play);
Tyson Campbell: 71 defensive + 3 special-teams snaps (played). Of the four flags the 10/1 ruling treated as stale, three
were genuine.
