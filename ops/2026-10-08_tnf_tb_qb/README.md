# TNF TB @ DAL (2026-10-08): starting-QB branch edits, prepared and NOT applied

The decision rule is logged in `calibration-log.md` ("TNF TB @ DAL: starting-QB decision rule", 10/7), written before
any official data existed. Apply a patch only on the user's OK, from the repo root on `main`. Each touches TB @ DAL
entries only, in three places: `src/props.py` (yardage-prop holds), `src/td_props.py` (TD-pick holds) and
`src/export_dashboard.py` (the label's note; the label's QB split and priced QB are built at each export).

| Mayfield on the official report | Patch | Effect |
|---|---|---|
| (a) **Out** | `a_mayfield_out.patch` | Mayfield's holds removed; Jalon Daniels' kept, as unreliable (10/1 Bagent precedent) |
| (b) **No game status, and the books price him** in the window's props pull | `b_mayfield_active_priced.patch` | Mayfield's holds removed; Daniels' kept as the backup |
| (b) no status but **not priced** | none | no change |
| (c) **Questionable / Doubtful** | none | no change: holds stay until an official source confirms the starter |

A QB inactive flag clears only after the Buccaneers' own official inactive article has been read and omits the player.

```bash
git apply --check ops/2026-10-08_tnf_tb_qb/a_mayfield_out.patch     # or b_...; prints nothing when it applies
git apply ops/2026-10-08_tnf_tb_qb/a_mayfield_out.patch
python -m pytest -q                                                   # suite must still pass
git commit -am "TB @ DAL: branch (a) applied per the 10/7 rule"       # then the refresh / re-rank below
```

Before 18:00 CDT the window's refresh ranks with it. After the refresh, re-rank to take effect:
`python -m src.props` then the TD step below, then `python -m src.export_dashboard`.
Undo before committing: `git apply -R ops/2026-10-08_tnf_tb_qb/<patch>`.

Tested 10/7 in memory on scratch copies of `src/` (nothing served changed; served files byte-identical before/after):
with no branch applied the in-memory ranking equals the served one; (a) and (b) leave only Daniels held; a synthetic
Mayfield pass-yds line is held with no branch applied and ranked under (a) or (b). On today's lines the ranking is the
same in all three, because the books price no Mayfield line yet.

## Anytime-TD step, after the window refresh (not part of `run_sunday`)

```bash
python -m src.ingest_td_props --fresh --games TB_DAL   # 1 Odds API credit (one market, one game)
python -m src.td_props                                  # ranks every game in the TD lines file, honours
                                                        # td_props.PLAYER_HOLDOUTS, publishes to dashboard/public
```
