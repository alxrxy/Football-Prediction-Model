# DEN @ KC post-mortem (NFL week 1, Monday 2026-09-14), written 2026-09-15

Diagnosis only. No weights, thresholds or code were changed.

## What happened

| | Value |
|---|---|
| Final (A-H) | DEN 10 – KC 31 (home margin **+21**) |
| Baseline (baseline-v1) | KC −1.46 → home margin −1.46, WP KC 45.5%, edge **−3.46**, **flagged DEN** |
| ML (ml-v1) | KC −0.92 → home margin +0.92, WP KC 52.9%, edge −1.08 (lean DEN, gate off) |
| Simulation (sim-v1) | anchored to −1.46; median 21–23 DEN, KC 45.6%, margin 80% band −18 to +16 |
| Market at prediction time (09-14 20:37Z) | consensus KC −2 (9 books, −1 to −2.5), total 43, ML −130/+110 |
| DraftKings open → close (ESPN pickcenter) | KC −2.5 (−120) → KC −2.5 (−108); ML −155/+130 → −130/+110 |
| ESPN pregame WP | KC 59.7% |
| Result vs line | KC covered by 18.5. Flag lost; ML lean lost; ML picked the winner |

The flagged side got a worse number than the close (DEN +2 consensus vs DEN
+2.5 at DraftKings), so the flag would have had slightly negative CLV as well
as losing.

## Which input caused the miss

Each input was replaced with a corrected value, one at a time, holding
everything else at what was stored:

| Input | Stored | Corrected | Effect on edge |
|---|---|---|---|
| **Layer 1 power rating** | KC +2.83, DEN +5.50 → L1 **−2.67** | KC +5.68 with 2025 prior built from Mahomes' starts only → L1 **+0.25** | **+2.90 toward KC**: edge −3.46 → −0.56, **no flag** |
| Injury term | −0.95 (KC −1.79, DEN −0.84) | −2.63 with the players' real 2025 snap shares (bug, below) | −1.68, i.e. *further toward DEN* |
| Situational (HFA 1.9, travel +0.25, rest 0, wind ×0.997) | +2.15 toward KC | unchanged | none; right direction |
| ML read | +0.92 (lean DEN by 1.08) | n/a | not flagged; same lean for the same reason (Elo) |
| Sim / game script | centred on −1.46 by construction | n/a | cannot move the side; see props note |

**Most responsible: Layer 1, the team-strength rating, not any of the four
candidate layers.** In week 1 the NFL power rating is ~100% last season,
regressed 25% to the mean. KC's 2025 offense was +0.097 EPA/play in the 14
games Mahomes started (902 plays) and −0.347 in weeks 16-18 without him (146
plays). The rating averages both: KC off EPA 0.0349 × 0.75 = 0.0262, which
matches the stored 0.02616 exactly. Weight the prior by Mahomes' starts and
KC's rating rises 2.9 points, which accounts for 2.9 of the 3.46-point edge.
In spirit it's an injury problem (last December's ACL tear leaking into this
September's rating), but the injury *layer* didn't cause it. The layer that
failed is the one that doesn't know who the quarterback is.

The ML model leaned DEN for a related reason. Its largest feature, walk-forward
Elo, had DEN +120.6 Elo (~4.8 pts), and that gap was built partly on KC losing
the backup-QB games. Its EPA feature favoured KC (+0.66), which is why it
landed nearer the market than the baseline did.

## The injury layer, and a data bug found on the way

Every DEN and KC injury row was charged at the 0.35 default snap share,
including Josh Simmons (2025 share 0.93), Chamarri Conner (0.97) and Chris
Jones (0.73). Across the latest NFL injury pull, **78 of 154 rows have no snap
share**. The cause is `ingest_injuries._snap_shares`:

```python
for year in (season, season - 1):
    ...
    if year == season and len(df) > 500:
        break  # enough current-season data; no need for last year
```

By Monday, 2026 week-1 snap counts had 1,397 rows for the 30 teams that had
played, so the loop never loaded 2025. That drops every player on the two
teams that hadn't played yet, and also every injured player who sat out week
1, who by definition has no 2026 snaps. So it drops exactly the players the
injury layer exists to price. The fallback needs to be per player, not per
dataset. It's a correctness bug (logged as P14), not a weighting change. It
also touches the 09-13 slate (68 of 96 ESPN rows that morning had no share).

With the real shares the injury term would have been −2.63, not −0.95. If
both corrections are applied together, the edge is −2.23, **still a DEN flag at
the current 2.0 threshold**. The market already had KC −2.5 with those
injuries known, so this is P9 again: the books read the same injury report.

## Game script and the simulation

The simulation is anchored to the baseline margin, so it inherited the lean
and can't be blamed for the side. As in DAL @ NYG, it missed on volume once
one team led:

| KC team line | Sim median (p10–p90) | Actual |
|---|---|---|
| Rush att | 25 (19–31) | **38** |
| Pass att | 34 (27–42) | 27 |
| Rush yds | 109 (67–164) | **220** |

KC led from late in the second quarter on and ran 38 times. DEN trailed and
ran 15. The engine draws plays by down × distance × field zone, and the only
team-level shift is a static PROE. Score doesn't enter the run/pass choice.
Another data point for P11. The +21 margin is above the sim's 90th percentile
(+16).

## How much was the input and how much was the game

The input problem explains the **flag**. It doesn't explain the size of the
miss. The market closed KC −2.5 and missed by 18.5 too. DEN averaged 3.7
yards/play (176 total) to KC's 5.9 (392). The turnovers were 2-1 against DEN:
an interception on the opening drive and a fumble that led to KC's third-
quarter touchdown. Even the corrected baseline (−0.56) still leans DEN, so the
lean loses ATS either way. What the correction removes is a flag calling it
value.

## Scope of the Layer 1 mechanism (context, not a fitted result)

Recomputing each team's 2025 offensive rating from its primary starter's
games only shifts **11 of 32** teams by 1 point or more: NYJ +5.1, IND +3.8,
KC +2.9, WAS +2.3, CIN +2.3, LV +1.4, CLE −1.4, MIN +1.4, GB +1.1, LAC +1.1,
ATL +1.1. The 2025 primary starter is not always the 2026 starter (a team that
changed quarterbacks needs the new one's number, not the old one's), so this
measures how big the mechanism can be. It isn't a correction. It's one graded
game plus a mechanism that plausibly touches a third of the league in weeks
1-4, and that overlaps P5 (stale early-season ratings).

## Not done

- Nothing was re-weighted or re-run. The DB still has DEN @ KC as
  `completed = false`. `python -m src.grade --sport nfl --refresh` will record
  it.
- The P13/P14 counterfactuals above are single-game arithmetic, not a
  backtest.
