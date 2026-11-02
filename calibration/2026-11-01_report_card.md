# Report card: props and anytime TD, weeks 4-8 (2026)

Generated 2026-11-01 18:42 CT. Read-only: no model change, no re-run, no served prediction touched. Script: `calibration/report_card.py`.

**Bottom line.** Neither product has shown it beats the market. Served props are 460-493, -73.4u (-7.7%). The rows F2 keeps are 276-249, +3.0u (+0.6%), which is break-even, and most of that sample is the data F2 was chosen on. The TD model beats a league-average baseline but is slightly behind the market on the 24 games where odds survive. **Two gaps in the data:** the eight noon games on 11/1 have no archived props list, and TD lists were never archived, so TD picks are reconstructions. SNF (PHI @ WAS) was not final and is excluded.

## 1. Props

**What is in this record.** Each game is graded from its last archived list before kickoff (P67 rule). Stake is 1 unit flat at the served price. Week 1-3 lists were never archived.

- Week 8 games with a list that are final: CAR_GB, KC_DEN, LAC_LA, NE_MIA. **The eight noon games on 11/1 have no archived list, so they are not in the props record.** Week 6 is one game (DAL @ GB).
- 13 rows void (player had no snaps or no box line). 1 game(s) with a list were not final and are skipped.
- Rank is the row's rank in the list it came from. A week with several lists can contribute more than 5 / 10 / 25 rows to a rank band.
- 'Market %' is the devigged chance of the picked side. If the model added nothing, Win % would sit near it. Break-even is what the served price needs.
- ROI intervals resample whole games, because rows in one game move together. Win % intervals are Wilson and treat rows as independent, so they are too narrow.
- **Trust labels:** TOO SMALL = under 100 rows or under 10 games. thin = 100-299 rows. usable = 300+ rows. 'usable' only means the sample is big enough to read, not that the split makes money.

### Kept vs held

| Split | n | Games | W-L | Win % | 95% CI | Break-even % | Market %  | Units | ROI % | ROI 95% CI | Trust |
|---|---|---|---|---|---|---|---|---|---|---|---|
| All served rows (top 25 + more) | 953 | 45 | 460-493 | 48.3 | 45-51 | 52.6 | 50.1 | -73.4 | -7.7 | -14 to -2 | usable |
| KEPT: raw gap of 0.10 or more (F2) | 525 | 44 | 276-249 | 52.6 | 48-57 | 52.7 | 50.1 | +3.0 | +0.6 | -9 to +10 | usable |
| HELD by F2: gap under 0.10 (weeks 4-7 were served; week 8 was held live) | 479 | 45 | 207-272 | 43.2 | 39-48 | 52.4 | 49.9 | -83.0 | -17.3 | -26 to -9 | usable |
| HELD as likely usage miss (gap past the cap), never served | 197 | 39 | 95-102 | 48.2 | 41-55 | 52.7 | 50.2 | -16.6 | -8.4 | -26 to +10 | thin |
| HELD as structural, never served | 5 | 3 | 4-1 | 80.0 | 38-96 | 52.7 | 49.9 | +2.6 | +52.3 | -6 to +92 | TOO SMALL |

F2 went live 10/29. For weeks 4-7 'kept' is the filter applied after the fact, and F2 was chosen on those same weeks, so only week 8 is out of sample:

| Split | n | Games | W-L | Win % | 95% CI | Break-even % | Market %  | Units | ROI % | ROI 95% CI | Trust |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Week 8 kept | 66 | 4 | 33-33 | 50.0 | 38-62 | 52.3 | 49.9 | -2.8 | -4.3 | -22 to +16 | TOO SMALL |
| Week 8 held by F2 | 51 | 4 | 23-28 | 45.1 | 32-59 | 51.6 | 49.2 | -6.6 | -13.0 | -35 to +16 | TOO SMALL |

### Splits: KEPT rows (the list as it stands today)

| Split | n | Games | W-L | Win % | 95% CI | Break-even % | Market %  | Units | ROI % | ROI 95% CI | Trust |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | 525 | 44 | 276-249 | 52.6 | 48-57 | 52.7 | 50.1 | +3.0 | +0.6 | -9 to +10 | usable |
| Receiving yds | 183 | 43 | 104-79 | 56.8 | 50-64 | 52.6 | 49.8 | +14.4 | +7.9 | -4 to +20 | thin |
| Receptions | 201 | 43 | 106-95 | 52.7 | 46-60 | 52.6 | 50.5 | +4.3 | +2.1 | -12 to +18 | thin |
| Rush yds | 106 | 40 | 47-59 | 44.3 | 35-54 | 52.7 | 50.0 | -16.7 | -15.8 | -32 to +1 | thin |
| Pass yds | 35 | 28 | 19-16 | 54.3 | 38-70 | 53.1 | 50.0 | +0.9 | +2.7 | -30 to +33 | TOO SMALL |
| Receiving yds over | 48 | 29 | 24-24 | 50.0 | 36-64 | 52.4 | 49.7 | -2.3 | -4.9 | -27 to +20 | TOO SMALL |
| Receiving yds under | 135 | 43 | 80-55 | 59.3 | 51-67 | 52.7 | 49.9 | +16.8 | +12.4 | -1 to +26 | thin |
| Receptions over | 48 | 27 | 25-23 | 52.1 | 38-66 | 52.7 | 50.6 | +1.5 | +3.1 | -25 to +32 | TOO SMALL |
| Receptions under | 153 | 42 | 81-72 | 52.9 | 45-61 | 52.6 | 50.5 | +2.8 | +1.8 | -14 to +18 | thin |
| Rush yds over | 68 | 34 | 29-39 | 42.6 | 32-54 | 52.6 | 50.0 | -12.8 | -18.8 | -38 to -1 | TOO SMALL |
| Rush yds under | 38 | 25 | 18-20 | 47.4 | 32-63 | 52.9 | 50.0 | -3.9 | -10.4 | -39 to +18 | TOO SMALL |
| Pass yds over | 15 | 13 | 9-6 | 60.0 | 36-80 | 53.0 | 50.0 | +2.0 | +13.2 | -33 to +55 | TOO SMALL |
| Pass yds under | 20 | 17 | 10-10 | 50.0 | 30-70 | 53.1 | 50.0 | -1.0 | -5.1 | -47 to +33 | TOO SMALL |
| Over | 179 | 42 | 87-92 | 48.6 | 41-56 | 52.6 | 50.1 | -11.6 | -6.5 | -22 to +9 | thin |
| Under | 346 | 44 | 189-157 | 54.6 | 49-60 | 52.7 | 50.2 | +14.6 | +4.2 | -5 to +15 | usable |
| Rank top 5 | 35 | 15 | 19-16 | 54.3 | 38-70 | 52.8 | 50.3 | +1.4 | +3.9 | -20 to +39 | TOO SMALL |
| Rank top 10 | 72 | 27 | 39-33 | 54.2 | 43-65 | 53.6 | 51.1 | +1.7 | +2.4 | -18 to +29 | TOO SMALL |
| Rank top 25 | 170 | 35 | 83-87 | 48.8 | 41-56 | 53.3 | 50.8 | -12.7 | -7.5 | -24 to +14 | thin |
| Rank 26+ | 355 | 41 | 193-162 | 54.4 | 49-59 | 52.4 | 49.8 | +15.7 | +4.4 | -7 to +15 | usable |
| Gap 0.10-0.15 | 195 | 44 | 101-94 | 51.8 | 45-59 | 52.9 | 50.3 | -3.5 | -1.8 | -19 to +15 | thin |
| Gap 0.15-0.20 | 192 | 43 | 98-94 | 51.0 | 44-58 | 52.5 | 50.0 | -2.3 | -1.2 | -14 to +12 | thin |
| Gap 0.20-0.25 | 138 | 37 | 77-61 | 55.8 | 47-64 | 52.6 | 50.1 | +8.8 | +6.4 | -10 to +25 | thin |
| Week 4 | 151 | 16 | 81-70 | 53.6 | 46-61 | 52.6 | 49.9 | +5.2 | +3.4 | -16 to +23 | thin |
| Week 5 | 137 | 11 | 65-72 | 47.4 | 39-56 | 53.2 | 50.6 | -14.9 | -10.9 | -33 to +6 | thin |
| Week 6 | 23 | 1 | 11-12 | 47.8 | 29-67 | 55.2 | 52.7 | -2.2 | -9.6 | - | TOO SMALL |
| Week 7 | 148 | 12 | 86-62 | 58.1 | 50-66 | 52.1 | 49.6 | +17.7 | +12.0 | -2 to +24 | thin |
| Week 8 | 66 | 4 | 33-33 | 50.0 | 38-62 | 52.3 | 49.9 | -2.8 | -4.3 | -22 to +16 | TOO SMALL |

### Splits: All served rows

| Split | n | Games | W-L | Win % | 95% CI | Break-even % | Market %  | Units | ROI % | ROI 95% CI | Trust |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | 953 | 45 | 460-493 | 48.3 | 45-51 | 52.6 | 50.1 | -73.4 | -7.7 | -13 to -1 | usable |
| Receiving yds | 360 | 43 | 172-188 | 47.8 | 43-53 | 52.7 | 49.9 | -33.6 | -9.3 | -19 to +1 | usable |
| Receptions | 342 | 43 | 169-173 | 49.4 | 44-55 | 52.4 | 50.3 | -14.3 | -4.2 | -15 to +7 | usable |
| Rush yds | 173 | 43 | 73-100 | 42.2 | 35-50 | 52.8 | 50.0 | -34.6 | -20.0 | -33 to -7 | thin |
| Pass yds | 78 | 44 | 46-32 | 59.0 | 48-69 | 52.9 | 50.0 | +9.0 | +11.6 | -10 to +33 | TOO SMALL |
| Receiving yds over | 138 | 40 | 60-78 | 43.5 | 35-52 | 52.7 | 49.9 | -24.1 | -17.4 | -31 to -3 | thin |
| Receiving yds under | 222 | 43 | 112-110 | 50.5 | 44-57 | 52.7 | 49.9 | -9.5 | -4.3 | -17 to +9 | thin |
| Receptions over | 111 | 39 | 51-60 | 45.9 | 37-55 | 50.9 | 48.8 | -6.3 | -5.6 | -24 to +14 | thin |
| Receptions under | 231 | 43 | 118-113 | 51.1 | 45-57 | 53.1 | 51.0 | -8.0 | -3.5 | -16 to +9 | thin |
| Rush yds over | 109 | 40 | 42-67 | 38.5 | 30-48 | 52.7 | 50.1 | -29.2 | -26.8 | -41 to -14 | thin |
| Rush yds under | 64 | 35 | 31-33 | 48.4 | 37-60 | 52.9 | 50.0 | -5.4 | -8.4 | -32 to +16 | TOO SMALL |
| Pass yds over | 36 | 26 | 24-12 | 66.7 | 50-80 | 53.0 | 50.0 | +9.3 | +25.9 | -6 to +58 | TOO SMALL |
| Pass yds under | 42 | 29 | 22-20 | 52.4 | 38-67 | 52.9 | 50.0 | -0.3 | -0.7 | -30 to +28 | TOO SMALL |
| Over | 394 | 44 | 177-217 | 44.9 | 40-50 | 52.2 | 49.7 | -50.3 | -12.8 | -23 to -3 | usable |
| Under | 559 | 45 | 283-276 | 50.6 | 46-55 | 52.9 | 50.3 | -23.2 | -4.1 | -13 to +5 | usable |
| Rank top 5 | 35 | 15 | 19-16 | 54.3 | 38-70 | 52.8 | 50.3 | +1.4 | +3.9 | -20 to +40 | TOO SMALL |
| Rank top 10 | 72 | 27 | 39-33 | 54.2 | 43-65 | 53.6 | 51.1 | +1.7 | +2.4 | -19 to +29 | TOO SMALL |
| Rank top 25 | 176 | 35 | 87-89 | 49.4 | 42-57 | 53.2 | 50.7 | -10.8 | -6.1 | -22 to +15 | thin |
| Rank 26+ | 777 | 44 | 373-404 | 48.0 | 45-52 | 52.5 | 49.9 | -62.6 | -8.1 | -15 to -1 | usable |
| Gap 0.00-0.05 | 237 | 41 | 106-131 | 44.7 | 39-51 | 52.5 | 50.0 | -34.2 | -14.4 | -26 to -3 | thin |
| Gap 0.05-0.10 | 191 | 37 | 78-113 | 40.8 | 34-48 | 52.5 | 49.9 | -42.3 | -22.1 | -35 to -8 | thin |
| Gap 0.10-0.15 | 195 | 44 | 101-94 | 51.8 | 45-59 | 52.9 | 50.3 | -3.5 | -1.8 | -19 to +15 | thin |
| Gap 0.15-0.20 | 192 | 43 | 98-94 | 51.0 | 44-58 | 52.5 | 50.0 | -2.3 | -1.2 | -14 to +12 | thin |
| Gap 0.20-0.25 | 138 | 37 | 77-61 | 55.8 | 47-64 | 52.6 | 50.1 | +8.8 | +6.4 | -12 to +25 | thin |
| Week 4 | 324 | 16 | 161-163 | 49.7 | 44-55 | 52.3 | 49.7 | -12.5 | -3.9 | -14 to +7 | usable |
| Week 5 | 234 | 12 | 101-133 | 43.2 | 37-50 | 53.0 | 50.5 | -43.8 | -18.7 | -32 to -7 | thin |
| Week 6 | 35 | 1 | 16-19 | 45.7 | 30-62 | 54.6 | 52.1 | -4.5 | -12.7 | - | TOO SMALL |
| Week 7 | 294 | 12 | 149-145 | 50.7 | 45-56 | 52.4 | 49.9 | -9.8 | -3.3 | -13 to +7 | thin |
| Week 8 | 66 | 4 | 33-33 | 50.0 | 38-62 | 52.3 | 49.9 | -2.8 | -4.3 | -22 to +16 | TOO SMALL |

### Splits: HELD by F2

| Split | n | Games | W-L | Win % | 95% CI | Break-even % | Market %  | Units | ROI % | ROI 95% CI | Trust |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | 479 | 45 | 207-272 | 43.2 | 39-48 | 52.4 | 49.9 | -83.0 | -17.3 | -26 to -8 | usable |
| Receiving yds | 201 | 43 | 80-121 | 39.8 | 33-47 | 52.7 | 50.0 | -49.1 | -24.4 | -37 to -12 | thin |
| Receptions | 158 | 43 | 70-88 | 44.3 | 37-52 | 51.8 | 49.7 | -21.8 | -13.8 | -32 to +5 | thin |
| Rush yds | 74 | 35 | 29-45 | 39.2 | 29-51 | 52.8 | 50.1 | -19.1 | -25.9 | -45 to -8 | TOO SMALL |
| Pass yds | 46 | 32 | 28-18 | 60.9 | 46-74 | 52.9 | 50.0 | +7.0 | +15.2 | -15 to +45 | TOO SMALL |
| Receiving yds over | 97 | 38 | 40-57 | 41.2 | 32-51 | 52.8 | 50.0 | -21.0 | -21.7 | -41 to -2 | TOO SMALL |
| Receiving yds under | 104 | 38 | 40-64 | 38.5 | 30-48 | 52.6 | 49.9 | -28.0 | -27.0 | -45 to -8 | thin |
| Receptions over | 69 | 35 | 29-40 | 42.0 | 31-54 | 49.0 | 47.0 | -6.8 | -9.8 | -39 to +19 | TOO SMALL |
| Receptions under | 89 | 41 | 41-48 | 46.1 | 36-56 | 53.9 | 51.8 | -15.0 | -16.9 | -38 to +5 | TOO SMALL |
| Rush yds over | 44 | 28 | 13-31 | 29.5 | 18-44 | 52.9 | 50.2 | -19.5 | -44.3 | -65 to -23 | TOO SMALL |
| Rush yds under | 30 | 19 | 16-14 | 53.3 | 36-70 | 52.7 | 49.9 | +0.3 | +1.2 | -33 to +38 | TOO SMALL |
| Pass yds over | 23 | 19 | 16-7 | 69.6 | 49-84 | 52.9 | 50.0 | +7.2 | +31.4 | -10 to +71 | TOO SMALL |
| Pass yds under | 23 | 18 | 12-11 | 52.2 | 33-71 | 52.8 | 49.9 | -0.3 | -1.1 | -44 to +42 | TOO SMALL |
| Over | 233 | 42 | 98-135 | 42.1 | 36-48 | 51.7 | 49.1 | -40.1 | -17.2 | -33 to -1 | thin |
| Under | 246 | 44 | 109-137 | 44.3 | 38-51 | 53.1 | 50.6 | -43.0 | -17.5 | -30 to -5 | thin |
| Rank top 5 | 0 | 0 | 0-0 | - | - | - | - | +0.0 | - | - | TOO SMALL |
| Rank top 10 | 0 | 0 | 0-0 | - | - | - | - | +0.0 | - | - | TOO SMALL |
| Rank top 25 | 6 | 2 | 4-2 | 66.7 | 30-90 | 51.7 | 49.5 | +1.9 | +31.2 | -10 to +114 | TOO SMALL |
| Rank 26+ | 422 | 41 | 180-242 | 42.7 | 38-47 | 52.5 | 50.0 | -78.3 | -18.6 | -28 to -9 | usable |
| Gap 0.00-0.05 | 260 | 45 | 115-145 | 44.2 | 38-50 | 52.3 | 49.8 | -39.3 | -15.1 | -26 to -4 | thin |
| Gap 0.05-0.10 | 219 | 41 | 92-127 | 42.0 | 36-49 | 52.6 | 50.0 | -43.8 | -20.0 | -32 to -7 | thin |
| Week 4 | 173 | 16 | 80-93 | 46.2 | 39-54 | 52.1 | 49.5 | -17.7 | -10.2 | -28 to +7 | thin |
| Week 5 | 97 | 12 | 36-61 | 37.1 | 28-47 | 52.8 | 50.3 | -28.9 | -29.8 | -49 to -11 | TOO SMALL |
| Week 6 | 12 | 1 | 5-7 | 41.7 | 19-68 | 53.3 | 50.8 | -2.2 | -18.7 | - | TOO SMALL |
| Week 7 | 146 | 12 | 63-83 | 43.2 | 35-51 | 52.7 | 50.3 | -27.5 | -18.9 | -27 to -8 | thin |
| Week 8 | 51 | 4 | 23-28 | 45.1 | 32-59 | 51.6 | 49.2 | -6.6 | -13.0 | -35 to +16 | TOO SMALL |

### Naive baselines for props

| Baseline, same rows | Served rows | Kept rows |
|---|---|---|
| Bet every row's under at -110 | 52.5% under, ROI +0.2% | 53.5% under, ROI +2.2% |
| Our picks at served prices | 48.3% win, ROI -7.7% | 52.6% win, ROI +0.6% |
| Market's own view of our side | 50.1% | 50.1% |

**Verdict: props.** Not beating the market. As served, the list wins 48.3% against a 52.6% break-even and a 50.1% market estimate, and the ROI interval (about -14% to -1%, the two bootstrap runs differ slightly) excludes zero, so this is a real loss, not bad luck. It also trails the dumbest baseline here: taking every row's under at -110 returns +0.2% on the same rows. The one signal that holds up is gap size. Rows with a gap under 0.10 went 207-272 (43.2%) against 276-249 (52.6%) above it, and week 8, the only data F2 did not see, leans the same way (33-33 kept, 23-28 held), though four games prove nothing. Kept rows are break-even (+0.6%, interval -9% to +10%) and still trail the under baseline on those rows (+2.2%). Ranking adds little: kept rows inside the top 25 win 48.8%, rows ranked 26+ win 54.4%, so the headline list is not the best part of the board. Rush yards is the weakest market (42.2% served; rush overs 38.5%). Kept receiving-yard unders (80-55, +12.4%) look best, but that split was picked after the fact and its interval (-1% to +26%) touches zero. **Too small to trust:** every split labelled TOO SMALL, which means pass yards, all rank 5 and rank 10 bands, weeks 6 and 8, and most over/under-by-market cells. Pass yds overs at 24-12 are the likeliest to fool us. **To trust it:** from week 8 on only, no after-the-fact filters, 300+ kept rows over 30+ games, with the game-bootstrap ROI interval above zero and ROI beating the under-at-110 baseline. Prop closing lines would be a faster test, but none are usable under the amended P61 definitions.

## 2. Anytime TD

**What is in this record.** TD lists have never been archived and the tab was not wired until 10/29, so there is no complete record of what was shown.

- **Player-game grading:** the simulation's scorer lists (top 8 per team), 1088 player-games in 68 games. Week 8 uses the final 11/1 games and TNF; the eight noon sims date from the 10/29 PRELIMINARY run, before the official reports. Players outside those lists are not graded.
- **Market comparison and picks:** rebuilt with `td_props.rank` from stored raw odds and archived sims: 454 priced players in 24 games (weeks 4, 6, 7). No week 5 or week 8 odds were stored for final games. These are reconstructions, not served lists, though week 7 matches its logged result (17 yes leans, 4 scored).
- A player with snaps but no stat line counts as not scoring; no snaps is void. The week-7 log entry dropped those rows (123 rows, Brier 0.183 vs 0.178). With them it is 134 rows.
- Market probabilities are estimates: books post Yes only, so they are scaled to the game total. Yes-side ROI uses the best Yes price stored.

### Yes picks vs how often they scored (rebuilt)

| Group | Picks | Games | Scored | Hit % | 95% CI | Sim % | Market % | Break-even % | Units | ROI % | ROI 95% CI | Trust |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Top-25 yes picks | 38 | 15 | 7 | 18.4 | 9-33 | 30.0 | 19.4 | 22.3 | -3.6 | -9.5 | -69 to +45 | TOO SMALL |
| All ranked yes picks | 244 | 24 | 46 | 18.9 | 14-24 | 21.5 | 16.7 | 19.1 | +29.7 | +12.2 | -24 to +54 | thin |
| Top-25 yes, week 4 | 11 | 7 | 2 | 18.2 | 5-48 | 33.9 | 19.0 | 21.8 | -2.9 | -25.9 | -100 to +122 | TOO SMALL |
| Top-25 yes, week 6 | 10 | 1 | 1 | 10.0 | 2-40 | 20.8 | 17.6 | 20.8 | +2.0 | +20.0 | - | TOO SMALL |
| Top-25 yes, week 7 | 17 | 7 | 4 | 23.5 | 10-47 | 32.9 | 20.8 | 23.5 | -2.8 | -16.2 | -83 to +68 | TOO SMALL |

**As logged at the time:** week 5 BUF @ LA 5-10 plus 2 ungraded no-line rows (5-12 at zero), not in the table above; week 6 DAL @ GB 1-9, +2.00u; week 7 noon 4-13, -2.75u.

### Hit rate by position (all graded player-games)

| Position | Player-games | Scored | Hit % | 95% CI | Sim % | Naive % | Trust |
|---|---|---|---|---|---|---|---|
| RB | 297 | 100 | 33.7 | 29-39 | 30.7 | 28.4 | thin |
| WR | 472 | 97 | 20.6 | 17-24 | 21.9 | 21.7 | usable |
| TE | 206 | 45 | 21.8 | 17-28 | 18.9 | 22.0 | thin |
| QB | 110 | 18 | 16.4 | 11-24 | 13.9 | 15.3 | thin |

### Calibration by band

| Band | Player-games | Predicted % | Actual % | 95% CI | Diff pp | Trust |
|---|---|---|---|---|---|---|
| 0-10% | 135 | 8.4 | 9.6 | 6-16 | +1.2 | thin |
| 10-20% | 403 | 14.7 | 14.1 | 11-18 | -0.5 | usable |
| 20-30% | 279 | 24.6 | 28.7 | 24-34 | +4.1 | thin |
| 30-40% | 157 | 34.5 | 36.3 | 29-44 | +1.8 | thin |
| 40%+ | 114 | 48.9 | 47.4 | 38-56 | -1.5 | thin |

### Brier and log loss

Lower is better. A negative diff means the first model is better. Intervals resample whole games.

| Group | n | Games | Actual % | Sim Brier | Sim log loss | Naive pos Brier | Naive pos log loss | Naive pos+depth Brier | Naive pos+depth log loss |
|---|---|---|---|---|---|---|---|---|---|
| All graded player-games | 1088 | 68 | 24.0 | 0.1675 | 0.5103 | 0.1804 | 0.5562 | 0.1731 | 0.5465 |
| RB | 297 | 68 | 33.7 | 0.2006 | 0.5833 | 0.2273 | 0.6487 | 0.2076 | 0.6027 |
| WR | 472 | 68 | 20.6 | 0.1585 | 0.4917 | 0.1637 | 0.5093 | 0.1604 | 0.5214 |
| TE | 206 | 68 | 21.8 | 0.1605 | 0.4936 | 0.1709 | 0.5254 | 0.1682 | 0.5149 |
| QB | 110 | 66 | 16.4 | 0.1261 | 0.4130 | 0.1393 | 0.4550 | 0.1389 | 0.4513 |

| Group | n | Games | Actual % | Sim Brier | Sim log loss | Market Brier | Market log loss | Naive pos Brier | Naive pos log loss |
|---|---|---|---|---|---|---|---|---|---|
| Priced players (market rows) | 454 | 24 | 21.8 | 0.1593 | 0.4906 | 0.1557 | 0.4804 | 0.1677 | 0.5393 |
| Week 4 | 298 | 16 | 21.8 | 0.1556 | 0.4822 | 0.1532 | 0.4779 | 0.1677 | 0.5141 |
| Week 6 | 22 | 1 | 18.2 | 0.1444 | 0.4523 | 0.1386 | 0.4438 | 0.1520 | 0.4788 |
| Week 7 | 134 | 7 | 22.4 | 0.1698 | 0.5154 | 0.1643 | 0.4921 | 0.1704 | 0.6054 |

| Comparison | n | Games | Brier diff | 95% CI | Log-loss diff | 95% CI  |
|---|---|---|---|---|---|---|
| Sim vs naive position rate, all | 1088 | 68 | -0.0130 | -0.0196 to -0.0066 | -0.0459 | -0.0742 to -0.0218 |
| Sim vs naive position + depth, all | 1088 | 68 | -0.0056 | -0.0103 to -0.0007 | -0.0363 | -0.0682 to -0.0110 |
| Sim vs market, priced players | 454 | 24 | +0.0035 | -0.0025 to +0.0095 | +0.0101 | -0.0086 to +0.0295 |
| Sim vs naive position, priced players | 454 | 24 | -0.0085 | -0.0182 to +0.0009 | -0.0488 | -0.1121 to -0.0032 |
| Market vs naive position, priced players | 454 | 24 | -0.0120 | -0.0231 to -0.0008 | -0.0589 | -0.1317 to -0.0086 |

### Best and worst 10 picks (rebuilt ranked yes picks)

**Best: largest wins.**

| Wk | Player | Team | Pos | Sim | Market | Price | Scored | Units |
|---|---|---|---|---|---|---|---|---|
| 4 | Jaleel McLaughlin | CLE | RB | 0.055 | 0.050 | +2000 | 1 | +20.00 |
| 4 | Elijah Higgins | ARI | TE | 0.091 | 0.065 | +1700 | 1 | +17.00 |
| 4 | Sean Tucker | TB | RB | 0.111 | 0.069 | +1600 | 1 | +16.00 |
| 4 | Kimani Vidal | LAC | RB | 0.101 | 0.055 | +1600 | 1 | +16.00 |
| 4 | Efton Chism III | NE | WR | 0.055 | 0.051 | +1400 | 1 | +14.00 |
| 7 | Drew Sample | CIN | TE | 0.090 | 0.070 | +1100 | 1 | +11.00 |
| 6 | Jordan Love | GB | QB | 0.109 | 0.083 | +1100 | 1 | +11.00 |
| 4 | Tory Horton | SEA | WR | 0.108 | 0.087 | +850 | 1 | +8.50 |
| 4 | Theo Johnson | NYG | TE | 0.156 | 0.103 | +800 | 1 | +8.00 |
| 4 | Darnell Washington | PIT | TE | 0.139 | 0.126 | +650 | 1 | +6.50 |

**Worst: biggest sim-over-market gaps that did not score, each -1u.**

| Wk | Player | Team | Pos | Sim | Market | Price | Scored | Units |
|---|---|---|---|---|---|---|---|---|
| 7 | Chris Godwin Jr. | TB | WR | 0.415 | 0.232 | +270 | 0 | -1.00 |
| 7 | Woody Marks | HOU | RB | 0.661 | 0.486 | -120 | 0 | -1.00 |
| 4 | Rashod Bateman | BAL | WR | 0.388 | 0.225 | +285 | 0 | -1.00 |
| 7 | Braelon Allen | NYJ | RB | 0.614 | 0.452 | -105 | 0 | -1.00 |
| 4 | MarShawn Lloyd | GB | RB | 0.395 | 0.236 | +280 | 0 | -1.00 |
| 4 | Davis Allen | LA | TE | 0.235 | 0.077 | +1000 | 0 | -1.00 |
| 4 | Dontayvion Wicks | PHI | WR | 0.342 | 0.186 | +360 | 0 | -1.00 |
| 7 | Julius Chestnut | TEN | RB | 0.180 | 0.026 | +3500 | 0 | -1.00 |
| 4 | Colston Loveland | CHI | TE | 0.376 | 0.227 | +290 | 0 | -1.00 |
| 4 | Seth McGowan | IND | RB | 0.233 | 0.089 | +850 | 0 | -1.00 |

**Verdict: anytime TD.** It beats a naive baseline but not the market. Against the league rate by position it is clearly better (Brier -0.0130, interval -0.0196 to -0.0066), and it also beats position plus depth (-0.0056, interval -0.0103 to -0.0007), so the usage model carries real information. Calibration is decent: all five bands contain their prediction, and the largest miss is the 20-30% band, 24.6% predicted against 28.7% actual. Against the devigged market on 454 priced players it is slightly worse (Brier 0.1593 vs 0.1557, log loss 0.4906 vs 0.4804), and both intervals include zero, so it is not proven worse, but nothing suggests it is better. The picks show why that matters: on its top-25 yes picks the sim said 30.0% and they scored 18.4% (7 of 38), below the 22.3% break-even and level with the 19.4% market. A big gap against the market has meant the sim is wrong, not that the book is. The all-ranked-yes line of +29.7u is not evidence: it rests on longshots at the best stored price, its interval is -24% to +54%, and without the three biggest wins (+2000, +1700, +1600) it is -23.3u. **The 'experimental' label should stay.** **To trust it:** archive every TD list first, since no served TD record exists. Then 150+ forward yes picks at stored prices, top-25 hit rate at or above break-even, and Brier better than the market with an interval excluding zero over 40+ games. The market side is an estimate because books post Yes only, so a real No price or closing price would make this test stronger. Also note: the tab's note says the 30-40% band hits 28.8% (weeks 1 and 3-6); over weeks 4-8 it hit 36.3%. The note was left alone because this pass changes nothing served.

