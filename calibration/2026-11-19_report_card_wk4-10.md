# Report card: props and anytime TD, weeks 4-10 (2026)

Generated 2026-11-19 14:52 CT. Read-only: no model change, no re-run, no served prediction touched. Script: `calibration/report_card.py`.



## 1. Props

**What is in this record.** Each game is graded from its last archived list before kickoff (P67 rule). Stake is 1 unit flat at the served price. Week 1-3 lists were never archived.

- Week 8 games with a list that are final: CAR_GB, KC_DEN, LAC_LA, NE_MIA, PHI_WAS. **The eight noon games on 11/1 have no archived list, so they are not in the props record.** Week 6 is one game (DAL @ GB).
- 17 rows void (player had no snaps or no box line). 0 game(s) with a list were not final and are skipped.
- Rank is the row's rank in the list it came from. A week with several lists can contribute more than 5 / 10 / 25 rows to a rank band.
- 'Market %' is the devigged chance of the picked side. If the model added nothing, Win % would sit near it. Break-even is what the served price needs.
- ROI intervals resample whole games, because rows in one game move together. Win % intervals are Wilson and treat rows as independent, so they are too narrow.
- **Trust labels:** TOO SMALL = under 100 rows or under 10 games. thin = 100-299 rows. usable = 300+ rows. 'usable' only means the sample is big enough to read, not that the split makes money.

### Kept vs held

| Split | n | Games | W-L | Win % | 95% CI | Break-even % | Market %  | Units | ROI % | ROI 95% CI | Trust |
|---|---|---|---|---|---|---|---|---|---|---|---|
| All served rows (top 25 + more) | 1254 | 66 | 619-635 | 49.4 | 47-52 | 52.7 | 50.2 | -73.0 | -5.8 | -11 to -1 | usable |
| KEPT: raw gap of 0.10 or more (F2) | 826 | 65 | 435-391 | 52.7 | 49-56 | 52.8 | 50.3 | +3.4 | +0.4 | -6 to +7 | usable |
| HELD by F2: gap under 0.10 (weeks 4-7 were served; weeks 8-10 were held live) | 744 | 66 | 351-393 | 47.2 | 44-51 | 52.3 | 49.8 | -71.1 | -9.6 | -17 to -2 | usable |
| HELD as likely usage miss (gap past the cap), never served | 319 | 58 | 156-163 | 48.9 | 43-54 | 52.5 | 50.1 | -22.1 | -6.9 | -19 to +6 | usable |
| HELD as structural, never served | 5 | 3 | 4-1 | 80.0 | 38-96 | 52.7 | 49.9 | +2.6 | +52.3 | -6 to +92 | TOO SMALL |

F2 went live 10/29. For weeks 4-7 'kept' is the filter applied after the fact, and F2 was chosen on those same weeks, so only weeks 8, 9 and 10 are out of sample:

| Split | n | Games | W-L | Win % | 95% CI | Break-even % | Market %  | Units | ROI % | ROI 95% CI | Trust |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Week 8 kept | 75 | 5 | 40-35 | 53.3 | 42-64 | 52.8 | 50.4 | +0.6 | +0.9 | -19 to +22 | TOO SMALL |
| Week 8 held by F2 | 60 | 5 | 29-31 | 48.3 | 36-61 | 51.8 | 49.4 | -4.3 | -7.2 | -28 to +23 | TOO SMALL |

### Splits: KEPT rows (the list as it stands today)

| Split | n | Games | W-L | Win % | 95% CI | Break-even % | Market %  | Units | ROI % | ROI 95% CI | Trust |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | 826 | 65 | 435-391 | 52.7 | 49-56 | 52.8 | 50.3 | +3.4 | +0.4 | -6 to +7 | usable |
| Receiving yds | 296 | 64 | 161-135 | 54.4 | 49-60 | 52.7 | 49.9 | +9.5 | +3.2 | -5 to +12 | thin |
| Receptions | 313 | 64 | 171-142 | 54.6 | 49-60 | 52.9 | 50.8 | +15.5 | +4.9 | -6 to +16 | usable |
| Rush yds | 168 | 59 | 76-92 | 45.2 | 38-53 | 52.7 | 50.0 | -23.6 | -14.1 | -27 to -1 | thin |
| Pass yds | 49 | 41 | 27-22 | 55.1 | 41-68 | 53.0 | 50.0 | +2.0 | +4.2 | -24 to +30 | TOO SMALL |
| Receiving yds over | 79 | 43 | 42-37 | 53.2 | 42-64 | 52.5 | 49.9 | +1.0 | +1.2 | -18 to +22 | TOO SMALL |
| Receiving yds under | 217 | 63 | 119-98 | 54.8 | 48-61 | 52.7 | 49.9 | +8.6 | +3.9 | -7 to +15 | thin |
| Receptions over | 75 | 40 | 41-34 | 54.7 | 43-65 | 52.6 | 50.5 | +6.8 | +9.0 | -13 to +32 | TOO SMALL |
| Receptions under | 238 | 63 | 130-108 | 54.6 | 48-61 | 53.0 | 50.9 | +8.7 | +3.7 | -8 to +16 | thin |
| Rush yds over | 106 | 52 | 49-57 | 46.2 | 37-56 | 52.6 | 50.0 | -12.8 | -12.0 | -28 to +4 | thin |
| Rush yds under | 62 | 43 | 27-35 | 43.5 | 32-56 | 52.9 | 49.9 | -10.8 | -17.5 | -39 to +5 | TOO SMALL |
| Pass yds over | 19 | 17 | 11-8 | 57.9 | 36-77 | 53.0 | 50.0 | +1.7 | +9.1 | -34 to +49 | TOO SMALL |
| Pass yds under | 30 | 26 | 16-14 | 53.3 | 36-70 | 53.0 | 50.0 | +0.3 | +1.0 | -33 to +33 | TOO SMALL |
| Over | 279 | 63 | 143-136 | 51.3 | 45-57 | 52.6 | 50.1 | -3.3 | -1.2 | -14 to +11 | thin |
| Under | 547 | 65 | 292-255 | 53.4 | 49-58 | 52.9 | 50.4 | +6.7 | +1.2 | -7 to +9 | usable |
| Rank top 5 | 65 | 29 | 34-31 | 52.3 | 40-64 | 52.5 | 50.1 | +0.9 | +1.4 | -19 to +26 | TOO SMALL |
| Rank top 10 | 131 | 44 | 72-59 | 55.0 | 46-63 | 53.1 | 50.7 | +6.7 | +5.2 | -10 to +22 | thin |
| Rank top 25 | 289 | 55 | 146-143 | 50.5 | 45-56 | 53.1 | 50.6 | -12.2 | -4.2 | -17 to +9 | thin |
| Rank 26+ | 537 | 59 | 289-248 | 53.8 | 50-58 | 52.6 | 50.1 | +15.6 | +2.9 | -5 to +11 | usable |
| Gap 0.10-0.15 | 320 | 65 | 169-151 | 52.8 | 47-58 | 53.1 | 50.5 | -0.8 | -0.3 | -11 to +11 | usable |
| Gap 0.15-0.20 | 301 | 64 | 155-146 | 51.5 | 46-57 | 52.5 | 50.0 | -2.1 | -0.7 | -10 to +9 | usable |
| Gap 0.20-0.25 | 205 | 57 | 111-94 | 54.1 | 47-61 | 52.8 | 50.3 | +6.4 | +3.1 | -9 to +17 | thin |
| Week 4 | 151 | 16 | 81-70 | 53.6 | 46-61 | 52.6 | 49.9 | +5.2 | +3.4 | -15 to +24 | thin |
| Week 5 | 137 | 11 | 65-72 | 47.4 | 39-56 | 53.2 | 50.6 | -14.9 | -10.9 | -33 to +6 | thin |
| Week 6 | 23 | 1 | 11-12 | 47.8 | 29-67 | 55.2 | 52.7 | -2.2 | -9.6 | - | TOO SMALL |
| Week 7 | 148 | 12 | 86-62 | 58.1 | 50-66 | 52.1 | 49.6 | +17.7 | +12.0 | -2 to +25 | thin |
| Week 8 | 75 | 5 | 40-35 | 53.3 | 42-64 | 52.8 | 50.4 | +0.6 | +0.9 | -18 to +23 | TOO SMALL |
| Week 9 | 163 | 12 | 87-76 | 53.4 | 46-61 | 53.0 | 50.6 | +1.8 | +1.1 | -12 to +16 | thin |
| Week 10 | 129 | 8 | 65-64 | 50.4 | 42-59 | 52.7 | 50.2 | -4.9 | -3.8 | -13 to +6 | TOO SMALL |

### Splits: All served rows

| Split | n | Games | W-L | Win % | 95% CI | Break-even % | Market %  | Units | ROI % | ROI 95% CI | Trust |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | 1254 | 66 | 619-635 | 49.4 | 47-52 | 52.7 | 50.2 | -73.0 | -5.8 | -11 to -1 | usable |
| Receiving yds | 473 | 64 | 229-244 | 48.4 | 44-53 | 52.7 | 49.9 | -38.5 | -8.1 | -16 to +0 | usable |
| Receptions | 454 | 64 | 234-220 | 51.5 | 47-56 | 52.6 | 50.5 | -3.1 | -0.7 | -10 to +8 | usable |
| Rush yds | 235 | 62 | 102-133 | 43.4 | 37-50 | 52.7 | 50.0 | -41.5 | -17.7 | -29 to -7 | thin |
| Pass yds | 92 | 57 | 54-38 | 58.7 | 48-68 | 53.0 | 50.0 | +10.1 | +11.0 | -10 to +30 | TOO SMALL |
| Receiving yds over | 169 | 54 | 78-91 | 46.2 | 39-54 | 52.7 | 50.0 | -20.8 | -12.3 | -25 to +2 | thin |
| Receiving yds under | 304 | 63 | 151-153 | 49.7 | 44-55 | 52.7 | 49.9 | -17.8 | -5.8 | -16 to +4 | usable |
| Receptions over | 138 | 52 | 67-71 | 48.6 | 40-57 | 51.2 | 49.1 | -1.0 | -0.7 | -18 to +17 | thin |
| Receptions under | 316 | 64 | 167-149 | 52.8 | 47-58 | 53.2 | 51.1 | -2.1 | -0.7 | -11 to +10 | usable |
| Rush yds over | 147 | 58 | 62-85 | 42.2 | 34-50 | 52.7 | 50.1 | -29.3 | -19.9 | -33 to -7 | thin |
| Rush yds under | 88 | 53 | 40-48 | 45.5 | 35-56 | 52.8 | 49.9 | -12.3 | -13.9 | -34 to +7 | TOO SMALL |
| Pass yds over | 40 | 30 | 26-14 | 65.0 | 50-78 | 53.0 | 50.0 | +9.1 | +22.7 | -8 to +53 | TOO SMALL |
| Pass yds under | 52 | 38 | 28-24 | 53.8 | 41-67 | 52.9 | 50.0 | +1.1 | +2.0 | -25 to +28 | TOO SMALL |
| Over | 494 | 65 | 233-261 | 47.2 | 43-52 | 52.3 | 49.8 | -41.9 | -8.5 | -18 to +1 | usable |
| Under | 760 | 66 | 386-374 | 50.8 | 47-54 | 53.0 | 50.4 | -31.1 | -4.1 | -11 to +4 | usable |
| Rank top 5 | 65 | 29 | 34-31 | 52.3 | 40-64 | 52.5 | 50.1 | +0.9 | +1.4 | -19 to +27 | TOO SMALL |
| Rank top 10 | 131 | 44 | 72-59 | 55.0 | 46-63 | 53.1 | 50.7 | +6.7 | +5.2 | -10 to +23 | thin |
| Rank top 25 | 295 | 55 | 150-145 | 50.8 | 45-57 | 53.1 | 50.6 | -10.3 | -3.5 | -15 to +10 | thin |
| Rank 26+ | 959 | 62 | 469-490 | 48.9 | 46-52 | 52.6 | 50.0 | -62.7 | -6.5 | -13 to -0 | usable |
| Gap 0.00-0.05 | 237 | 41 | 106-131 | 44.7 | 39-51 | 52.5 | 50.0 | -34.2 | -14.4 | -26 to -3 | thin |
| Gap 0.05-0.10 | 191 | 37 | 78-113 | 40.8 | 34-48 | 52.5 | 49.9 | -42.3 | -22.1 | -35 to -8 | thin |
| Gap 0.10-0.15 | 320 | 65 | 169-151 | 52.8 | 47-58 | 53.1 | 50.5 | -0.8 | -0.3 | -11 to +11 | usable |
| Gap 0.15-0.20 | 301 | 64 | 155-146 | 51.5 | 46-57 | 52.5 | 50.0 | -2.1 | -0.7 | -10 to +9 | usable |
| Gap 0.20-0.25 | 205 | 57 | 111-94 | 54.1 | 47-61 | 52.8 | 50.3 | +6.4 | +3.1 | -10 to +16 | thin |
| Week 4 | 324 | 16 | 161-163 | 49.7 | 44-55 | 52.3 | 49.7 | -12.5 | -3.9 | -14 to +8 | usable |
| Week 5 | 234 | 12 | 101-133 | 43.2 | 37-50 | 53.0 | 50.5 | -43.8 | -18.7 | -32 to -7 | thin |
| Week 6 | 35 | 1 | 16-19 | 45.7 | 30-62 | 54.6 | 52.1 | -4.5 | -12.7 | - | TOO SMALL |
| Week 7 | 294 | 12 | 149-145 | 50.7 | 45-56 | 52.4 | 49.9 | -9.8 | -3.3 | -13 to +7 | thin |
| Week 8 | 75 | 5 | 40-35 | 53.3 | 42-64 | 52.8 | 50.4 | +0.6 | +0.9 | -19 to +23 | TOO SMALL |
| Week 9 | 163 | 12 | 87-76 | 53.4 | 46-61 | 53.0 | 50.6 | +1.8 | +1.1 | -12 to +16 | thin |
| Week 10 | 129 | 8 | 65-64 | 50.4 | 42-59 | 52.7 | 50.2 | -4.9 | -3.8 | -13 to +6 | TOO SMALL |

### Splits: HELD by F2

| Split | n | Games | W-L | Win % | 95% CI | Break-even % | Market %  | Units | ROI % | ROI 95% CI | Trust |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | 744 | 66 | 351-393 | 47.2 | 44-51 | 52.3 | 49.8 | -71.1 | -9.6 | -17 to -2 | usable |
| Receiving yds | 313 | 64 | 146-167 | 46.6 | 41-52 | 52.7 | 50.0 | -35.8 | -11.5 | -23 to -0 | usable |
| Receptions | 255 | 63 | 119-136 | 46.7 | 41-53 | 51.5 | 49.5 | -21.9 | -8.6 | -22 to +5 | thin |
| Rush yds | 106 | 53 | 46-60 | 43.4 | 34-53 | 52.8 | 50.0 | -18.9 | -17.8 | -34 to -2 | thin |
| Pass yds | 70 | 51 | 40-30 | 57.1 | 45-68 | 52.9 | 50.0 | +5.6 | +7.9 | -16 to +31 | TOO SMALL |
| Receiving yds over | 145 | 55 | 68-77 | 46.9 | 39-55 | 52.7 | 50.1 | -15.9 | -11.0 | -28 to +5 | thin |
| Receiving yds under | 168 | 57 | 78-90 | 46.4 | 39-54 | 52.6 | 49.9 | -19.9 | -11.9 | -26 to +1 | thin |
| Receptions over | 111 | 53 | 47-64 | 42.3 | 34-52 | 49.0 | 47.0 | -9.5 | -8.5 | -32 to +14 | thin |
| Receptions under | 144 | 59 | 72-72 | 50.0 | 42-58 | 53.5 | 51.4 | -12.4 | -8.6 | -23 to +6 | thin |
| Rush yds over | 65 | 43 | 22-43 | 33.8 | 24-46 | 52.9 | 50.1 | -23.5 | -36.1 | -54 to -18 | TOO SMALL |
| Rush yds under | 41 | 28 | 24-17 | 58.5 | 43-72 | 52.7 | 49.9 | +4.6 | +11.1 | -18 to +40 | TOO SMALL |
| Pass yds over | 37 | 32 | 23-14 | 62.2 | 46-76 | 52.9 | 50.0 | +6.5 | +17.4 | -15 to +49 | TOO SMALL |
| Pass yds under | 33 | 28 | 17-16 | 51.5 | 35-67 | 52.9 | 49.9 | -0.9 | -2.7 | -37 to +32 | TOO SMALL |
| Over | 358 | 63 | 160-198 | 44.7 | 40-50 | 51.6 | 49.1 | -42.4 | -11.8 | -24 to +1 | usable |
| Under | 386 | 65 | 191-195 | 49.5 | 45-54 | 53.0 | 50.5 | -28.7 | -7.4 | -17 to +2 | usable |
| Rank top 5 | 0 | 0 | 0-0 | - | - | - | - | +0.0 | - | - | TOO SMALL |
| Rank top 10 | 0 | 0 | 0-0 | - | - | - | - | +0.0 | - | - | TOO SMALL |
| Rank top 25 | 6 | 2 | 4-2 | 66.7 | 30-90 | 51.7 | 49.5 | +1.9 | +31.2 | -10 to +114 | TOO SMALL |
| Rank 26+ | 422 | 41 | 180-242 | 42.7 | 38-47 | 52.5 | 50.0 | -78.3 | -18.6 | -28 to -9 | usable |
| Gap 0.00-0.05 | 404 | 65 | 201-203 | 49.8 | 45-55 | 52.0 | 49.5 | -15.7 | -3.9 | -13 to +5 | usable |
| Gap 0.05-0.10 | 340 | 62 | 150-190 | 44.1 | 39-49 | 52.7 | 50.2 | -55.4 | -16.3 | -26 to -6 | usable |
| Week 4 | 173 | 16 | 80-93 | 46.2 | 39-54 | 52.1 | 49.5 | -17.7 | -10.2 | -28 to +7 | thin |
| Week 5 | 97 | 12 | 36-61 | 37.1 | 28-47 | 52.8 | 50.3 | -28.9 | -29.8 | -48 to -11 | TOO SMALL |
| Week 6 | 12 | 1 | 5-7 | 41.7 | 19-68 | 53.3 | 50.8 | -2.2 | -18.7 | - | TOO SMALL |
| Week 7 | 146 | 12 | 63-83 | 43.2 | 35-51 | 52.7 | 50.3 | -27.5 | -18.9 | -28 to -7 | thin |
| Week 8 | 60 | 5 | 29-31 | 48.3 | 36-61 | 51.8 | 49.4 | -4.3 | -7.2 | -28 to +23 | TOO SMALL |
| Week 9 | 164 | 12 | 90-74 | 54.9 | 47-62 | 52.0 | 49.6 | +10.7 | +6.5 | -5 to +19 | thin |
| Week 10 | 92 | 8 | 48-44 | 52.2 | 42-62 | 52.2 | 49.8 | -1.1 | -1.2 | -21 to +19 | TOO SMALL |

### Naive baselines for props

| Baseline, same rows | Served rows | Kept rows |
|---|---|---|
| Bet every row's under at -110 | 51.6% under, ROI -1.5% | 51.8% under, ROI -1.1% |
| Our picks at served prices | 49.4% win, ROI -5.8% | 52.7% win, ROI +0.4% |
| Market's own view of our side | 50.2% | 50.3% |



## 2. Anytime TD

**What is in this record.** TD lists have never been archived and the tab was not wired until 10/29, so there is no complete record of what was shown.

- **Player-game grading:** the simulation's scorer lists (top 8 per team), 1536 player-games in 95 games. Week 8 uses the final 11/1 games and TNF; the eight noon sims date from the 10/29 PRELIMINARY run, before the official reports. Players outside those lists are not graded.
- **Market comparison and picks:** rebuilt with `td_props.rank` from stored raw odds and archived sims: 473 priced players in 25 games (weeks 4, 6, 7, 10). No week 5 or week 8 odds were stored for final games. These are reconstructions, not served lists, though week 7 matches its logged result (17 yes leans, 4 scored).
- A player with snaps but no stat line counts as not scoring; no snaps is void. The week-7 log entry dropped those rows (123 rows, Brier 0.183 vs 0.178). With them it is 134 rows.
- Market probabilities are estimates: books post Yes only, so they are scaled to the game total. Yes-side ROI uses the best Yes price stored.

### Yes picks vs how often they scored (rebuilt)

| Group | Picks | Games | Scored | Hit % | 95% CI | Sim % | Market % | Break-even % | Units | ROI % | ROI 95% CI | Trust |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Top-25 yes picks | 48 | 16 | 9 | 18.8 | 10-32 | 27.9 | 18.6 | 21.3 | -0.0 | -0.1 | -54 to +44 | TOO SMALL |
| All ranked yes picks | 254 | 25 | 48 | 18.9 | 15-24 | 21.4 | 16.6 | 19.0 | +33.2 | +13.1 | -22 to +51 | thin |
| Top-25 yes, week 4 | 11 | 7 | 2 | 18.2 | 5-48 | 33.9 | 19.0 | 21.8 | -2.9 | -25.9 | -100 to +122 | TOO SMALL |
| Top-25 yes, week 6 | 10 | 1 | 1 | 10.0 | 2-40 | 20.8 | 17.6 | 20.8 | +2.0 | +20.0 | - | TOO SMALL |
| Top-25 yes, week 7 | 17 | 7 | 4 | 23.5 | 10-47 | 32.9 | 20.8 | 23.5 | -2.8 | -16.2 | -83 to +65 | TOO SMALL |
| Top-25 yes, week 10 | 10 | 1 | 2 | 20.0 | 6-51 | 19.9 | 15.4 | 17.4 | +3.5 | +35.5 | - | TOO SMALL |

**As logged at the time:** week 5 BUF @ LA 5-10 plus 2 ungraded no-line rows (5-12 at zero), not in the table above; week 6 DAL @ GB 1-9, +2.00u; week 7 noon 4-13, -2.75u.

### Hit rate by position (all graded player-games)

| Position | Player-games | Scored | Hit % | 95% CI | Sim % | Naive % | Trust |
|---|---|---|---|---|---|---|---|
| RB | 423 | 137 | 32.4 | 28-37 | 30.4 | 29.2 | usable |
| WR | 665 | 142 | 21.4 | 18-25 | 21.8 | 21.6 | usable |
| TE | 290 | 59 | 20.3 | 16-25 | 18.8 | 21.8 | thin |
| QB | 153 | 24 | 15.7 | 11-22 | 14.0 | 15.3 | thin |

### Calibration by band

| Band | Player-games | Predicted % | Actual % | 95% CI | Diff pp | Trust |
|---|---|---|---|---|---|---|
| 0-10% | 191 | 8.3 | 9.4 | 6-14 | +1.2 | thin |
| 10-20% | 563 | 14.6 | 15.1 | 12-18 | +0.5 | usable |
| 20-30% | 406 | 24.6 | 26.6 | 23-31 | +2.0 | usable |
| 30-40% | 216 | 34.3 | 34.7 | 29-41 | +0.4 | thin |
| 40%+ | 160 | 48.6 | 48.1 | 41-56 | -0.5 | thin |

### Brier and log loss

Lower is better. A negative diff means the first model is better. Intervals resample whole games.

| Group | n | Games | Actual % | Sim Brier | Sim log loss | Naive pos Brier | Naive pos log loss | Naive pos+depth Brier | Naive pos+depth log loss |
|---|---|---|---|---|---|---|---|---|---|
| All graded player-games | 1536 | 95 | 23.6 | 0.1669 | 0.5092 | 0.1786 | 0.5491 | 0.1712 | 0.5359 |
| RB | 423 | 95 | 32.4 | 0.1950 | 0.5696 | 0.2216 | 0.6362 | 0.2016 | 0.5882 |
| WR | 665 | 95 | 21.4 | 0.1642 | 0.5069 | 0.1683 | 0.5196 | 0.1653 | 0.5264 |
| TE | 290 | 95 | 20.3 | 0.1543 | 0.4786 | 0.1623 | 0.5059 | 0.1591 | 0.4932 |
| QB | 153 | 93 | 15.7 | 0.1240 | 0.4082 | 0.1344 | 0.4427 | 0.1338 | 0.4378 |

| Group | n | Games | Actual % | Sim Brier | Sim log loss | Market Brier | Market log loss | Naive pos Brier | Naive pos log loss |
|---|---|---|---|---|---|---|---|---|---|
| Priced players (market rows) | 473 | 25 | 22.2 | 0.1625 | 0.4992 | 0.1589 | 0.4880 | 0.1696 | 0.5425 |
| Week 4 | 298 | 16 | 21.8 | 0.1556 | 0.4822 | 0.1532 | 0.4779 | 0.1677 | 0.5141 |
| Week 6 | 22 | 1 | 18.2 | 0.1444 | 0.4523 | 0.1386 | 0.4438 | 0.1520 | 0.4788 |
| Week 7 | 134 | 7 | 22.4 | 0.1698 | 0.5154 | 0.1643 | 0.4921 | 0.1704 | 0.6054 |
| Week 10 | 19 | 1 | 31.6 | 0.2397 | 0.7051 | 0.2338 | 0.6694 | 0.2142 | 0.6174 |

| Comparison | n | Games | Brier diff | 95% CI | Log-loss diff | 95% CI  |
|---|---|---|---|---|---|---|
| Sim vs naive position rate, all | 1536 | 95 | -0.0118 | -0.0170 to -0.0066 | -0.0399 | -0.0628 to -0.0211 |
| Sim vs naive position + depth, all | 1536 | 95 | -0.0043 | -0.0084 to -0.0003 | -0.0267 | -0.0498 to -0.0078 |
| Sim vs market, priced players | 473 | 25 | +0.0036 | -0.0022 to +0.0095 | +0.0112 | -0.0058 to +0.0287 |
| Sim vs naive position, priced players | 473 | 25 | -0.0071 | -0.0167 to +0.0023 | -0.0433 | -0.1037 to +0.0025 |
| Market vs naive position, priced players | 473 | 25 | -0.0107 | -0.0217 to +0.0003 | -0.0545 | -0.1181 to -0.0050 |

### Best and worst 10 picks (rebuilt ranked yes picks)

**Best: largest wins.**

| Wk | Player | Team | Pos | Sim | Market | Price | Scored | Units |
|---|---|---|---|---|---|---|---|---|
| 4 | Jaleel McLaughlin | CLE | RB | 0.055 | 0.050 | +2000 | 1 | +20.00 |
| 4 | Elijah Higgins | ARI | TE | 0.091 | 0.065 | +1700 | 1 | +17.00 |
| 4 | Kimani Vidal | LAC | RB | 0.101 | 0.055 | +1600 | 1 | +16.00 |
| 4 | Sean Tucker | TB | RB | 0.111 | 0.069 | +1600 | 1 | +16.00 |
| 4 | Efton Chism III | NE | WR | 0.055 | 0.051 | +1400 | 1 | +14.00 |
| 7 | Drew Sample | CIN | TE | 0.090 | 0.070 | +1100 | 1 | +11.00 |
| 6 | Jordan Love | GB | QB | 0.109 | 0.083 | +1100 | 1 | +11.00 |
| 10 | Drew Sample | CIN | TE | 0.084 | 0.082 | +950 | 1 | +9.50 |
| 4 | Tory Horton | SEA | WR | 0.108 | 0.087 | +850 | 1 | +8.50 |
| 4 | Theo Johnson | NYG | TE | 0.156 | 0.103 | +800 | 1 | +8.00 |

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



