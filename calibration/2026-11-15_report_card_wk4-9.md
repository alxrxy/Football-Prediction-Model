# Report card: props and anytime TD, weeks 4-9 (2026)

Generated 2026-11-15 18:23 CT. Read-only: no model change, no re-run, no served prediction touched. Script: `calibration/report_card_wk4_9.py` (weeks 4-9 copy; some section text below still reads "weeks 4-8" from the original).



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
| All served rows (top 25 + more) | 1125 | 58 | 554-571 | 49.2 | 46-52 | 52.7 | 50.2 | -68.1 | -6.1 | -11 to -0 | usable |
| KEPT: raw gap of 0.10 or more (F2) | 697 | 57 | 370-327 | 53.1 | 49-57 | 52.8 | 50.3 | +8.3 | +1.2 | -7 to +9 | usable |
| HELD by F2: gap under 0.10 (weeks 4-7 were served; week 8 was held live) | 652 | 58 | 303-349 | 46.5 | 43-50 | 52.3 | 49.8 | -70.0 | -10.7 | -19 to -3 | usable |
| HELD as likely usage miss (gap past the cap), never served | 271 | 51 | 134-137 | 49.4 | 44-55 | 52.4 | 50.0 | -15.2 | -5.6 | -20 to +9 | thin |
| HELD as structural, never served | 5 | 3 | 4-1 | 80.0 | 38-96 | 52.7 | 49.9 | +2.6 | +52.3 | -6 to +92 | TOO SMALL |

F2 went live 10/29. For weeks 4-7 'kept' is the filter applied after the fact, and F2 was chosen on those same weeks, so only week 8 is out of sample:

| Split | n | Games | W-L | Win % | 95% CI | Break-even % | Market %  | Units | ROI % | ROI 95% CI | Trust |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Week 8 kept | 75 | 5 | 40-35 | 53.3 | 42-64 | 52.8 | 50.4 | +0.6 | +0.9 | -18 to +23 | TOO SMALL |
| Week 8 held by F2 | 60 | 5 | 29-31 | 48.3 | 36-61 | 51.8 | 49.4 | -4.3 | -7.2 | -28 to +22 | TOO SMALL |

### Splits: KEPT rows (the list as it stands today)

| Split | n | Games | W-L | Win % | 95% CI | Break-even % | Market %  | Units | ROI % | ROI 95% CI | Trust |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | 697 | 57 | 370-327 | 53.1 | 49-57 | 52.8 | 50.3 | +8.3 | +1.2 | -7 to +9 | usable |
| Receiving yds | 249 | 56 | 138-111 | 55.4 | 49-61 | 52.7 | 49.9 | +12.9 | +5.2 | -4 to +15 | thin |
| Receptions | 263 | 56 | 143-120 | 54.4 | 48-60 | 53.0 | 50.9 | +11.5 | +4.4 | -8 to +17 | thin |
| Rush yds | 142 | 51 | 66-76 | 46.5 | 38-55 | 52.7 | 50.0 | -16.5 | -11.6 | -26 to +3 | thin |
| Pass yds | 43 | 36 | 23-20 | 53.5 | 39-67 | 53.0 | 50.0 | +0.5 | +1.1 | -27 to +28 | TOO SMALL |
| Receiving yds over | 66 | 36 | 34-32 | 51.5 | 40-63 | 52.4 | 49.8 | -1.3 | -2.0 | -23 to +19 | TOO SMALL |
| Receiving yds under | 183 | 56 | 104-79 | 56.8 | 50-64 | 52.7 | 49.9 | +14.2 | +7.8 | -4 to +19 | thin |
| Receptions over | 64 | 34 | 35-29 | 54.7 | 43-66 | 52.9 | 50.8 | +5.3 | +8.3 | -16 to +33 | TOO SMALL |
| Receptions under | 199 | 55 | 108-91 | 54.3 | 47-61 | 53.0 | 50.9 | +6.2 | +3.1 | -10 to +16 | thin |
| Rush yds over | 88 | 44 | 42-46 | 47.7 | 38-58 | 52.6 | 50.0 | -7.9 | -9.0 | -28 to +9 | TOO SMALL |
| Rush yds under | 54 | 35 | 24-30 | 44.4 | 32-58 | 52.9 | 50.0 | -8.6 | -15.9 | -39 to +8 | TOO SMALL |
| Pass yds over | 19 | 17 | 11-8 | 57.9 | 36-77 | 53.0 | 50.0 | +1.7 | +9.1 | -34 to +49 | TOO SMALL |
| Pass yds under | 24 | 21 | 12-12 | 50.0 | 31-69 | 53.0 | 50.0 | -1.2 | -5.2 | -43 to +29 | TOO SMALL |
| Over | 237 | 55 | 122-115 | 51.5 | 45-58 | 52.7 | 50.2 | -2.2 | -0.9 | -14 to +13 | thin |
| Under | 460 | 57 | 248-212 | 53.9 | 49-58 | 52.9 | 50.4 | +10.5 | +2.3 | -6 to +11 | usable |
| Rank top 5 | 55 | 24 | 30-25 | 54.5 | 42-67 | 52.7 | 50.3 | +2.8 | +5.0 | -14 to +29 | TOO SMALL |
| Rank top 10 | 111 | 37 | 62-49 | 55.9 | 47-65 | 53.4 | 51.0 | +6.7 | +6.1 | -11 to +24 | thin |
| Rank top 25 | 242 | 47 | 125-117 | 51.7 | 45-58 | 53.3 | 50.8 | -5.5 | -2.3 | -16 to +14 | thin |
| Rank 26+ | 455 | 52 | 245-210 | 53.8 | 49-58 | 52.5 | 50.0 | +13.8 | +3.0 | -6 to +12 | usable |
| Gap 0.10-0.15 | 264 | 57 | 138-126 | 52.3 | 46-58 | 52.9 | 50.4 | -2.6 | -1.0 | -14 to +12 | thin |
| Gap 0.15-0.20 | 255 | 56 | 133-122 | 52.2 | 46-58 | 52.6 | 50.1 | +0.9 | +0.4 | -11 to +11 | thin |
| Gap 0.20-0.25 | 178 | 49 | 99-79 | 55.6 | 48-63 | 52.9 | 50.4 | +10.0 | +5.6 | -8 to +20 | thin |
| Week 4 | 151 | 16 | 81-70 | 53.6 | 46-61 | 52.6 | 49.9 | +5.2 | +3.4 | -17 to +23 | thin |
| Week 5 | 137 | 11 | 65-72 | 47.4 | 39-56 | 53.2 | 50.6 | -14.9 | -10.9 | -33 to +7 | thin |
| Week 6 | 23 | 1 | 11-12 | 47.8 | 29-67 | 55.2 | 52.7 | -2.2 | -9.6 | - | TOO SMALL |
| Week 7 | 148 | 12 | 86-62 | 58.1 | 50-66 | 52.1 | 49.6 | +17.7 | +12.0 | -1 to +24 | thin |
| Week 8 | 75 | 5 | 40-35 | 53.3 | 42-64 | 52.8 | 50.4 | +0.6 | +0.9 | -19 to +23 | TOO SMALL |
| Week 9 | 163 | 12 | 87-76 | 53.4 | 46-61 | 53.0 | 50.6 | +1.8 | +1.1 | -12 to +15 | thin |

### Splits: All served rows

| Split | n | Games | W-L | Win % | 95% CI | Break-even % | Market %  | Units | ROI % | ROI 95% CI | Trust |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | 1125 | 58 | 554-571 | 49.2 | 46-52 | 52.7 | 50.2 | -68.1 | -6.1 | -11 to -0 | usable |
| Receiving yds | 426 | 56 | 206-220 | 48.4 | 44-53 | 52.7 | 49.9 | -35.1 | -8.2 | -17 to +1 | usable |
| Receptions | 404 | 56 | 206-198 | 51.0 | 46-56 | 52.6 | 50.6 | -7.1 | -1.8 | -11 to +8 | usable |
| Rush yds | 209 | 54 | 92-117 | 44.0 | 37-51 | 52.8 | 50.0 | -34.4 | -16.5 | -28 to -4 | thin |
| Pass yds | 86 | 52 | 50-36 | 58.1 | 48-68 | 52.9 | 50.0 | +8.6 | +10.0 | -11 to +30 | TOO SMALL |
| Receiving yds over | 156 | 47 | 70-86 | 44.9 | 37-53 | 52.7 | 50.0 | -23.0 | -14.8 | -28 to -1 | thin |
| Receiving yds under | 270 | 56 | 136-134 | 50.4 | 44-56 | 52.7 | 49.9 | -12.1 | -4.5 | -15 to +6 | thin |
| Receptions over | 127 | 46 | 61-66 | 48.0 | 40-57 | 51.2 | 49.2 | -2.5 | -1.9 | -20 to +16 | thin |
| Receptions under | 277 | 56 | 145-132 | 52.3 | 46-58 | 53.3 | 51.2 | -4.7 | -1.7 | -13 to +10 | thin |
| Rush yds over | 129 | 50 | 55-74 | 42.6 | 34-51 | 52.7 | 50.0 | -24.4 | -18.9 | -33 to -5 | thin |
| Rush yds under | 80 | 45 | 37-43 | 46.2 | 36-57 | 52.9 | 50.0 | -10.0 | -12.5 | -33 to +10 | TOO SMALL |
| Pass yds over | 40 | 30 | 26-14 | 65.0 | 50-78 | 53.0 | 50.0 | +9.1 | +22.7 | -8 to +54 | TOO SMALL |
| Pass yds under | 46 | 33 | 24-22 | 52.2 | 38-66 | 52.9 | 50.0 | -0.5 | -1.1 | -29 to +27 | TOO SMALL |
| Over | 452 | 57 | 212-240 | 46.9 | 42-52 | 52.3 | 49.8 | -40.8 | -9.0 | -19 to +1 | usable |
| Under | 673 | 58 | 342-331 | 50.8 | 47-55 | 53.0 | 50.4 | -27.3 | -4.1 | -12 to +4 | usable |
| Rank top 5 | 55 | 24 | 30-25 | 54.5 | 42-67 | 52.7 | 50.3 | +2.8 | +5.0 | -14 to +29 | TOO SMALL |
| Rank top 10 | 111 | 37 | 62-49 | 55.9 | 47-65 | 53.4 | 51.0 | +6.7 | +6.1 | -12 to +24 | thin |
| Rank top 25 | 248 | 47 | 129-119 | 52.0 | 46-58 | 53.3 | 50.8 | -3.6 | -1.5 | -15 to +14 | thin |
| Rank 26+ | 877 | 55 | 425-452 | 48.5 | 45-52 | 52.5 | 50.0 | -64.5 | -7.3 | -14 to -0 | usable |
| Gap 0.00-0.05 | 237 | 41 | 106-131 | 44.7 | 39-51 | 52.5 | 50.0 | -34.2 | -14.4 | -26 to -3 | thin |
| Gap 0.05-0.10 | 191 | 37 | 78-113 | 40.8 | 34-48 | 52.5 | 49.9 | -42.3 | -22.1 | -35 to -8 | thin |
| Gap 0.10-0.15 | 264 | 57 | 138-126 | 52.3 | 46-58 | 52.9 | 50.4 | -2.6 | -1.0 | -14 to +12 | thin |
| Gap 0.15-0.20 | 255 | 56 | 133-122 | 52.2 | 46-58 | 52.6 | 50.1 | +0.9 | +0.4 | -11 to +12 | thin |
| Gap 0.20-0.25 | 178 | 49 | 99-79 | 55.6 | 48-63 | 52.9 | 50.4 | +10.0 | +5.6 | -8 to +21 | thin |
| Week 4 | 324 | 16 | 161-163 | 49.7 | 44-55 | 52.3 | 49.7 | -12.5 | -3.9 | -14 to +7 | usable |
| Week 5 | 234 | 12 | 101-133 | 43.2 | 37-50 | 53.0 | 50.5 | -43.8 | -18.7 | -32 to -7 | thin |
| Week 6 | 35 | 1 | 16-19 | 45.7 | 30-62 | 54.6 | 52.1 | -4.5 | -12.7 | - | TOO SMALL |
| Week 7 | 294 | 12 | 149-145 | 50.7 | 45-56 | 52.4 | 49.9 | -9.8 | -3.3 | -13 to +8 | thin |
| Week 8 | 75 | 5 | 40-35 | 53.3 | 42-64 | 52.8 | 50.4 | +0.6 | +0.9 | -19 to +23 | TOO SMALL |
| Week 9 | 163 | 12 | 87-76 | 53.4 | 46-61 | 53.0 | 50.6 | +1.8 | +1.1 | -12 to +15 | thin |

### Splits: HELD by F2

| Split | n | Games | W-L | Win % | 95% CI | Break-even % | Market %  | Units | ROI % | ROI 95% CI | Trust |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | 652 | 58 | 303-349 | 46.5 | 43-50 | 52.3 | 49.8 | -70.0 | -10.7 | -18 to -3 | usable |
| Receiving yds | 272 | 56 | 123-149 | 45.2 | 39-51 | 52.7 | 50.0 | -38.5 | -14.2 | -26 to -2 | thin |
| Receptions | 220 | 55 | 105-115 | 47.7 | 41-54 | 51.6 | 49.5 | -13.3 | -6.1 | -20 to +8 | thin |
| Rush yds | 98 | 48 | 40-58 | 40.8 | 32-51 | 52.8 | 50.0 | -22.3 | -22.7 | -39 to -5 | TOO SMALL |
| Pass yds | 62 | 45 | 35-27 | 56.5 | 44-68 | 52.9 | 50.0 | +4.1 | +6.6 | -18 to +33 | TOO SMALL |
| Receiving yds over | 124 | 47 | 58-66 | 46.8 | 38-56 | 52.8 | 50.1 | -13.9 | -11.2 | -29 to +7 | thin |
| Receiving yds under | 148 | 50 | 65-83 | 43.9 | 36-52 | 52.6 | 49.9 | -24.6 | -16.6 | -31 to -2 | thin |
| Receptions over | 96 | 46 | 44-52 | 45.8 | 36-56 | 48.8 | 46.9 | -0.5 | -0.5 | -24 to +23 | TOO SMALL |
| Receptions under | 124 | 51 | 61-63 | 49.2 | 41-58 | 53.7 | 51.6 | -12.8 | -10.3 | -27 to +6 | thin |
| Rush yds over | 58 | 38 | 17-41 | 29.3 | 19-42 | 52.9 | 50.1 | -26.0 | -44.7 | -63 to -25 | TOO SMALL |
| Rush yds under | 40 | 27 | 23-17 | 57.5 | 42-71 | 52.7 | 49.9 | +3.7 | +9.2 | -21 to +39 | TOO SMALL |
| Pass yds over | 32 | 27 | 20-12 | 62.5 | 45-77 | 52.9 | 50.0 | +5.8 | +18.1 | -17 to +52 | TOO SMALL |
| Pass yds under | 30 | 25 | 15-15 | 50.0 | 33-67 | 52.8 | 49.9 | -1.7 | -5.5 | -43 to +30 | TOO SMALL |
| Over | 310 | 55 | 139-171 | 44.8 | 39-50 | 51.6 | 49.1 | -34.6 | -11.2 | -24 to +2 | usable |
| Under | 342 | 57 | 164-178 | 48.0 | 43-53 | 53.0 | 50.5 | -35.4 | -10.3 | -21 to -0 | usable |
| Rank top 5 | 0 | 0 | 0-0 | - | - | - | - | +0.0 | - | - | TOO SMALL |
| Rank top 10 | 0 | 0 | 0-0 | - | - | - | - | +0.0 | - | - | TOO SMALL |
| Rank top 25 | 6 | 2 | 4-2 | 66.7 | 30-90 | 51.7 | 49.5 | +1.9 | +31.2 | -10 to +114 | TOO SMALL |
| Rank 26+ | 422 | 41 | 180-242 | 42.7 | 38-47 | 52.5 | 50.0 | -78.3 | -18.6 | -28 to -9 | usable |
| Gap 0.00-0.05 | 353 | 58 | 173-180 | 49.0 | 44-54 | 52.1 | 49.7 | -18.4 | -5.2 | -15 to +4 | usable |
| Gap 0.05-0.10 | 299 | 54 | 130-169 | 43.5 | 38-49 | 52.6 | 50.0 | -51.6 | -17.3 | -29 to -6 | thin |
| Week 4 | 173 | 16 | 80-93 | 46.2 | 39-54 | 52.1 | 49.5 | -17.7 | -10.2 | -27 to +7 | thin |
| Week 5 | 97 | 12 | 36-61 | 37.1 | 28-47 | 52.8 | 50.3 | -28.9 | -29.8 | -50 to -11 | TOO SMALL |
| Week 6 | 12 | 1 | 5-7 | 41.7 | 19-68 | 53.3 | 50.8 | -2.2 | -18.7 | - | TOO SMALL |
| Week 7 | 146 | 12 | 63-83 | 43.2 | 35-51 | 52.7 | 50.3 | -27.5 | -18.9 | -28 to -8 | thin |
| Week 8 | 60 | 5 | 29-31 | 48.3 | 36-61 | 51.8 | 49.4 | -4.3 | -7.2 | -28 to +23 | TOO SMALL |
| Week 9 | 164 | 12 | 90-74 | 54.9 | 47-62 | 52.0 | 49.6 | +10.7 | +6.5 | -5 to +19 | thin |

### Naive baselines for props

| Baseline, same rows | Served rows | Kept rows |
|---|---|---|
| Bet every row's under at -110 | 51.7% under, ROI -1.2% | 52.1% under, ROI -0.6% |
| Our picks at served prices | 49.2% win, ROI -6.1% | 53.1% win, ROI +1.2% |
| Market's own view of our side | 50.2% | 50.3% |



## 2. Anytime TD

**What is in this record.** TD lists have never been archived and the tab was not wired until 10/29, so there is no complete record of what was shown.

- **Player-game grading:** the simulation's scorer lists (top 8 per team), 1344 player-games in 83 games. Week 8 uses the final 11/1 games and TNF; the eight noon sims date from the 10/29 PRELIMINARY run, before the official reports. Players outside those lists are not graded.
- **Market comparison and picks:** rebuilt with `td_props.rank` from stored raw odds and archived sims: 454 priced players in 24 games (weeks 4, 6, 7). No week 5 or week 8 odds were stored for final games. These are reconstructions, not served lists, though week 7 matches its logged result (17 yes leans, 4 scored).
- A player with snaps but no stat line counts as not scoring; no snaps is void. The week-7 log entry dropped those rows (123 rows, Brier 0.183 vs 0.178). With them it is 134 rows.
- Market probabilities are estimates: books post Yes only, so they are scaled to the game total. Yes-side ROI uses the best Yes price stored.

### Yes picks vs how often they scored (rebuilt)

| Group | Picks | Games | Scored | Hit % | 95% CI | Sim % | Market % | Break-even % | Units | ROI % | ROI 95% CI | Trust |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Top-25 yes picks | 38 | 15 | 7 | 18.4 | 9-33 | 30.0 | 19.4 | 22.3 | -3.6 | -9.5 | -66 to +45 | TOO SMALL |
| All ranked yes picks | 244 | 24 | 46 | 18.9 | 14-24 | 21.5 | 16.7 | 19.1 | +29.7 | +12.2 | -26 to +54 | thin |
| Top-25 yes, week 4 | 11 | 7 | 2 | 18.2 | 5-48 | 33.9 | 19.0 | 21.8 | -2.9 | -25.9 | -100 to +122 | TOO SMALL |
| Top-25 yes, week 6 | 10 | 1 | 1 | 10.0 | 2-40 | 20.8 | 17.6 | 20.8 | +2.0 | +20.0 | - | TOO SMALL |
| Top-25 yes, week 7 | 17 | 7 | 4 | 23.5 | 10-47 | 32.9 | 20.8 | 23.5 | -2.8 | -16.2 | -83 to +68 | TOO SMALL |

**As logged at the time:** week 5 BUF @ LA 5-10 plus 2 ungraded no-line rows (5-12 at zero), not in the table above; week 6 DAL @ GB 1-9, +2.00u; week 7 noon 4-13, -2.75u.

### Hit rate by position (all graded player-games)

| Position | Player-games | Scored | Hit % | 95% CI | Sim % | Naive % | Trust |
|---|---|---|---|---|---|---|---|
| RB | 369 | 119 | 32.2 | 28-37 | 30.5 | 29.0 | usable |
| WR | 579 | 123 | 21.2 | 18-25 | 21.9 | 21.6 | usable |
| TE | 257 | 55 | 21.4 | 17-27 | 18.6 | 21.9 | thin |
| QB | 135 | 19 | 14.1 | 9-21 | 14.0 | 15.4 | thin |

### Calibration by band

| Band | Player-games | Predicted % | Actual % | 95% CI | Diff pp | Trust |
|---|---|---|---|---|---|---|
| 0-10% | 169 | 8.3 | 9.5 | 6-15 | +1.2 | thin |
| 10-20% | 491 | 14.6 | 14.3 | 11-18 | -0.4 | usable |
| 20-30% | 354 | 24.6 | 28.0 | 24-33 | +3.4 | usable |
| 30-40% | 189 | 34.3 | 34.9 | 28-42 | +0.6 | thin |
| 40%+ | 141 | 48.7 | 46.8 | 39-55 | -1.9 | thin |

### Brier and log loss

Lower is better. A negative diff means the first model is better. Intervals resample whole games.

| Group | n | Games | Actual % | Sim Brier | Sim log loss | Naive pos Brier | Naive pos log loss | Naive pos+depth Brier | Naive pos+depth log loss |
|---|---|---|---|---|---|---|---|---|---|
| All graded player-games | 1344 | 83 | 23.6 | 0.1664 | 0.5080 | 0.1784 | 0.5494 | 0.1706 | 0.5367 |
| RB | 369 | 83 | 32.2 | 0.1939 | 0.5677 | 0.2214 | 0.6360 | 0.2007 | 0.5871 |
| WR | 579 | 83 | 21.2 | 0.1646 | 0.5074 | 0.1677 | 0.5183 | 0.1648 | 0.5276 |
| TE | 257 | 83 | 21.4 | 0.1586 | 0.4883 | 0.1683 | 0.5196 | 0.1643 | 0.5044 |
| QB | 135 | 81 | 14.1 | 0.1126 | 0.3790 | 0.1231 | 0.4148 | 0.1227 | 0.4103 |

| Group | n | Games | Actual % | Sim Brier | Sim log loss | Market Brier | Market log loss | Naive pos Brier | Naive pos log loss |
|---|---|---|---|---|---|---|---|---|---|
| Priced players (market rows) | 454 | 24 | 21.8 | 0.1593 | 0.4906 | 0.1557 | 0.4804 | 0.1677 | 0.5393 |
| Week 4 | 298 | 16 | 21.8 | 0.1556 | 0.4822 | 0.1532 | 0.4779 | 0.1677 | 0.5141 |
| Week 6 | 22 | 1 | 18.2 | 0.1444 | 0.4523 | 0.1386 | 0.4438 | 0.1520 | 0.4788 |
| Week 7 | 134 | 7 | 22.4 | 0.1698 | 0.5154 | 0.1643 | 0.4921 | 0.1704 | 0.6054 |

| Comparison | n | Games | Brier diff | 95% CI | Log-loss diff | 95% CI  |
|---|---|---|---|---|---|---|
| Sim vs naive position rate, all | 1344 | 83 | -0.0120 | -0.0177 to -0.0062 | -0.0414 | -0.0657 to -0.0213 |
| Sim vs naive position + depth, all | 1344 | 83 | -0.0042 | -0.0084 to +0.0000 | -0.0287 | -0.0552 to -0.0071 |
| Sim vs market, priced players | 454 | 24 | +0.0035 | -0.0023 to +0.0095 | +0.0101 | -0.0084 to +0.0288 |
| Sim vs naive position, priced players | 454 | 24 | -0.0085 | -0.0179 to +0.0006 | -0.0488 | -0.1144 to -0.0011 |
| Market vs naive position, priced players | 454 | 24 | -0.0120 | -0.0230 to -0.0011 | -0.0589 | -0.1291 to -0.0068 |

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



