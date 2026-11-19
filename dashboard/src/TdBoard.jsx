import { Fragment, useEffect, useMemo, useState } from 'react'
import { TeamLogo } from './ui.jsx'

// TD board, from td_board.json (python -m src.td_board).
// EXPERIMENTAL / UNVALIDATED, display only: every simulated player's chance of
// 1+ and 2+ touchdowns, sortable, with a click-through explanation per player.
// 2+ TD is new and has never been graded. Nothing here feeds a prediction.

const pc = (v, d = 0) => (v == null ? '—' : `${(v * 100).toFixed(d)}%`)
const price = (p) => (p == null ? '—' : p > 0 ? `+${p}` : `${p}`)
const pts = (g) => (g == null ? '—' : `${g >= 0 ? '+' : '−'}${Math.abs(g * 100).toFixed(1)}`)
const num = (v, d = 1) => (v == null ? '—' : Number(v).toFixed(d))

const SORTS = [
  ['one', 'Most likely 1+ TD'],
  ['two', 'Most likely 2+ TD'],
  ['edge', 'Edge vs market'],
]

const sorted = (rows, key) => {
  const r = [...rows]
  if (key === 'edge') return r.sort((a, b) => (a.edge == null) - (b.edge == null) || (b.edge ?? 0) - (a.edge ?? 0))
  const f = key === 'two' ? 'p_two' : 'p_one'
  return r.sort((a, b) => (b[f] ?? 0) - (a[f] ?? 0))
}

export default function TdBoard({ compact = false }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [sort, setSort] = useState('one')
  const [game, setGame] = useState('all')
  const [open, setOpen] = useState(null)
  const [all, setAll] = useState(!compact)
  useEffect(() => {
    fetch(`./td_board.json?ts=${Date.now()}`, { cache: 'no-store' })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(setData)
      .catch((e) => setError(e.message))
  }, [])

  const rows = useMemo(() => {
    if (!data) return []
    const live = data.players.filter((p) => !p.started && (game === 'all' || p.game_id === game))
    return sorted(live, sort)
  }, [data, sort, game])

  if (error || !data) {
    return (
      <section className={`td-board card${compact ? ' compact' : ''}`}>
        <h3>Touchdown board</h3>
        <p className="muted">
          {error ? 'No TD board yet. Run ' : 'Loading… '}
          {error ? <code>python -m src.td_board</code> : null}
        </p>
      </section>
    )
  }
  const shown = all ? rows : rows.slice(0, 12)
  const h = data.history
  const key = (p) => `${p.game_id}|${p.team}|${p.player}`

  return (
    <section className={`td-board card${compact ? ' compact' : ''}`} aria-label="Touchdown board">
      <div className="tdb-head">
        <h3>
          Touchdown board <span className="tag unvalidated">EXPERIMENTAL · UNVALIDATED</span>
        </h3>
        <p className="muted small">
          Week {data.week} · {data.counts.players} players in {data.counts.games} games · {data.counts.priced} with a market
          price. {data.method}
        </p>
        <p className="tdb-warn">
          <strong>Don&rsquo;t bet this.</strong> {data.two_plus_note}{' '}
          {h ? (
            <>
              Graded record of the archived lists (weeks {h.forward_weeks.join(', ')}): top-25 &ldquo;yes&rdquo; picks scored{' '}
              <strong>
                {h.yes_scored} of {h.yes_picks}
              </strong>{' '}
              ({pc(h.yes_scored / Math.max(1, h.yes_picks), 1)}) against {h.yes_predicted_pct}% predicted and{' '}
              {h.yes_market_pct}% market; the market&rsquo;s Brier score beat the simulation&rsquo;s ({h.market_brier} vs{' '}
              {h.sim_brier}). {h.history_note}
            </>
          ) : (
            'Earlier graded history: anytime-TD top-25 picks went 7 of 38 against 30% predicted.'
          )}
        </p>
      </div>
      <div className="tdb-controls">
        <div className="segmented" role="group" aria-label="Sort">
          {SORTS.map(([k, label]) => (
            <button key={k} className={sort === k ? 'active' : ''} onClick={() => setSort(k)}>
              {label}
            </button>
          ))}
        </div>
        <select value={game} onChange={(e) => setGame(e.target.value)} aria-label="Game">
          <option value="all">All games</option>
          {data.games
            .filter((g) => g.simulated && !g.started)
            .map((g) => (
              <option key={g.game_id} value={g.game_id}>
                {g.away} @ {g.home}
              </option>
            ))}
        </select>
      </div>
      <div className="table-wrap">
        <table className="tdb-table">
          <thead>
            <tr>
              <th>Player</th>
              <th>Game</th>
              <th className="num">1+ TD</th>
              <th className="num">
                2+ TD <span className="tdb-new">new</span>
              </th>
              <th className="num">Market</th>
              <th className="num">Edge (pts)</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((p) => {
              const k = key(p)
              const isOpen = open === k
              return (
                <Fragment key={k}>
                  <tr
                    className={`tdb-row${isOpen ? ' open' : ''}`}
                    onClick={() => setOpen(isOpen ? null : k)}
                    tabIndex={0}
                    onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), setOpen(isOpen ? null : k))}
                    aria-expanded={isOpen}
                  >
                    <td>
                      <span className="tdb-player">
                        <TeamLogo abbr={p.team} size={20} />
                        <strong>{p.player}</strong>
                        <em>
                          {p.team} {p.position}
                          {p.depth_rank ? p.depth_rank : ''}
                        </em>
                      </span>
                    </td>
                    <td className="muted">{p.game}</td>
                    <td className="num">
                      <strong>{pc(p.p_one)}</strong>
                    </td>
                    <td className="num">{pc(p.p_two, 1)}</td>
                    <td className="num">
                      {p.p_market == null ? (
                        <span className="muted">no price</span>
                      ) : (
                        <>
                          {pc(p.p_market)} <span className="muted">({price(p.yes_price)})</span>
                        </>
                      )}
                    </td>
                    <td className={`num ${p.edge == null ? 'muted' : p.edge >= 0 ? 'pos' : 'neg'}`}>
                      {pts(p.edge)}
                      {p.edge != null && Math.abs(p.edge) > 0.2 ? (
                        <span className="tdb-new" title="Gaps past 20 points are held out of the ranked list as likely usage or depth-chart misses, not edges">
                          likely usage miss
                        </span>
                      ) : null}
                    </td>
                  </tr>
                  {isOpen ? (
                    <tr className="tdb-explain">
                      <td colSpan={6}>
                        <Explain p={p} through={data.facts_through_week} />
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
      {rows.length > 12 ? (
        <button className="tdb-more" onClick={() => setAll(!all)}>
          {all ? 'Show top 12' : `Show all ${rows.length} players`}
        </button>
      ) : null}
      <p className="muted small">Click a player for the reasons. {compact ? 'Full list and the ranked market list: Props → Anytime TD.' : ''}</p>
    </section>
  )
}

function Explain({ p, through }) {
  const e = p.explain || {}
  const t = e.team_profile
  const o = e.opponent_allows
  const u = e.usage_season
  const s = e.game_script || {}
  const sim = e.usage_sim_shares || {}
  const role = e.role_injuries || []
  const mates = e.teammates_out_or_questionable || []
  return (
    <div className="tdb-why">
      <div>
        <h4>{p.team} scoring profile</h4>
        {t ? (
          <p>
            {num(t.td_per_game, 2)} offensive TDs a game through week {through} ({num(t.rush_td_per_game, 2)} rushing,{' '}
            {num(t.pass_td_per_game, 2)} passing). {num(t.rz_trips_per_game, 1)} red-zone trips a game,{' '}
            {t.rz_td_rate == null ? '—' : pc(t.rz_td_rate)} of them end in a touchdown.
          </p>
        ) : (
          <p className="muted">No team data.</p>
        )}
      </div>
      <div>
        <h4>What {p.opponent} allows</h4>
        {o && o.per_game != null ? (
          <p>
            {num(o.per_game, 2)} TDs a game to {o.group}s, rank {o.rank_most_allowed} of {o.of} (1 = most allowed).
          </p>
        ) : (
          <p className="muted">No positional split for this position.</p>
        )}
      </div>
      <div>
        <h4>His red-zone and goal-line work</h4>
        {u ? (
          <p>
            {u.tds} TDs in {u.games_with_a_touch_or_target} games. Red zone: {u.rz_tgt} targets ({pc(u.rz_tgt_team_share)} of
            team), {u.rz_car} carries ({pc(u.rz_car_team_share)}). Inside the 10: {u.i10_tgt} targets, {u.i10_car} carries.
            Goal line (inside the 5): {u.gl_tgt} targets, {u.gl_car} carries ({pc(u.gl_car_team_share)} of team carries).
          </p>
        ) : (
          <p className="muted">No 2026 touches found for this team.</p>
        )}
        <p className="muted small">
          Shares the simulation used this week: red-zone targets {pc(sim.rz_target_share)}, red-zone carries{' '}
          {pc(sim.rz_carry_share)}, goal-line carries {pc(sim.gl_carry_share)}; expected TDs {num(p.expected_tds, 2)}.
        </p>
      </div>
      <div>
        <h4>Game script</h4>
        <p>
          {p.team} {s.market_spread_team == null ? 'no line' : s.market_spread_team > 0 ? `+${s.market_spread_team}` : s.market_spread_team}, total{' '}
          {s.market_total ?? '—'}: market implies {num(s.implied_points)} points. The simulation has {num(s.sim_points)} points,{' '}
          {num(s.sim_team_tds, 2)} team TDs, about {num(s.sim_plays, 0)} plays, and a {pc(s.sim_win_prob)} chance to win.
        </p>
      </div>
      <div>
        <h4>Injuries that change his role</h4>
        {role.length ? (
          <ul>
            {role.map((r, i) =>
              r.kind === 'gains' ? (
                <li key={i}>
                  Takes over work from {r.from} ({r.status || 'no status'}, {pc(r.play_prob)} to play): +{pc(r.carry_share, 1)} of
                  carries, +{pc(r.target_share, 1)} of targets.
                </li>
              ) : (
                <li key={i}>
                  His own status: {r.status || 'on the report, no status'}, {pc(r.play_prob)} to play. His share is cut by that
                  much.
                </li>
              ),
            )}
          </ul>
        ) : (
          <p className="muted">None moved his share in the simulation.</p>
        )}
        {mates.length ? (
          <p className="muted small">
            On the report at skill positions: {mates.map((m) => `${m.player} (${m.position}, ${m.status})`).join(', ')}.
          </p>
        ) : null}
      </div>
    </div>
  )
}
