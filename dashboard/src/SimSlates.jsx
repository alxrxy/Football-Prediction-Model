import { Fragment, useState } from 'react'
import SimDetail from './SimDetail.jsx'
import { useLive, useSims } from './simData.js'
import { dateLabel, kickoffLabel } from './format.js'
import './sims.css'

// Every NFL game on today's slate and the next few, finished, live or
// upcoming, each row opening the game view.

const pct = (v) => (v == null ? '—' : `${Math.round(v * 100)}%`)
const n0 = (v) => (v == null ? '—' : `${Math.round(v)}`)
const shortDate = (iso) => {
  const d = new Date(`${iso}T12:00:00Z`)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' })
}

export default function SimSlates() {
  const { data, error } = useSims()
  const [date, setDate] = useState(null)
  const [open, setOpen] = useState(null)
  const slates = data?.slates || []
  const slate = slates.find((s) => s.date === date) || slates[0]
  const watch = Boolean(slate?.games.some((g) => g.status !== 'final'))
  const live = useLive(watch)
  const liveById = new Map((live?.games || []).map((g) => [g.game_id, g]))

  if (error) {
    return (
      <section className="sim-slates">
        <h2>Game simulations</h2>
        <p className="muted">
          Couldn&rsquo;t load <code>sims.json</code> ({error}). Generate it with <code>python -m src.export_sims</code>.
        </p>
      </section>
    )
  }
  if (!data) return null
  if (!slate) {
    return (
      <section className="sim-slates">
        <h2>Game simulations</h2>
        <p className="muted">No simulated games yet.</p>
      </section>
    )
  }

  return (
    <section className="sim-slates">
      <h2>
        Game simulations <span className="muted">· {dateLabel(slate.date)}</span>
      </h2>
      <p className="muted small">
        Every NFL game: the pregame projection, the live re-projection while it&rsquo;s on, and the actual result once
        it&rsquo;s over. Click a game for the score distribution, TD/FG counts, likely scorers and player projections.
      </p>
      <div className="controls">
        <div className="segmented">
          {slates.map((s) => (
            <button
              key={s.date}
              className={s.date === slate.date ? 'active' : ''}
              onClick={() => {
                setDate(s.date)
                setOpen(null)
              }}
            >
              {shortDate(s.date)} · {s.games.length}
            </button>
          ))}
        </div>
        <span className="muted small">exported {kickoffLabel(data.generated_at)}</span>
      </div>
      <div className="table-wrap">
        <table className="slate">
          <thead>
            <tr>
              <th>Kick</th>
              <th>Matchup</th>
              <th>Status</th>
              <th>Pregame projection</th>
              <th className="num">Home win, pregame</th>
              <th className="num">Home win, live</th>
            </tr>
          </thead>
          <tbody>
            {slate.games.map((g) => {
              const lg = liveById.get(g.game_id)
              const inPlay = lg?.state === 'in'
              const status = inPlay ? 'live' : lg?.state === 'post' ? 'final' : g.status
              const score = lg && lg.state !== 'pre'
                ? { home: lg.home_score, away: lg.away_score }
                : g.actual
                  ? { home: g.actual.home_score, away: g.actual.away_score }
                  : g.score
              const p = g.pregame
              const isOpen = open === g.game_id
              const line = score ? `${g.away} ${score.away}–${score.home} ${g.home}` : ''
              return (
                <Fragment key={g.game_id}>
                  <tr className={`row ${isOpen ? 'open' : ''}`} onClick={() => setOpen(isOpen ? null : g.game_id)}>
                    <td className="muted">{kickoffLabel(g.kickoff)}</td>
                    <td className="matchup">
                      <strong>{g.away}</strong> <span className="at">@</span> <strong>{g.home}</strong>
                    </td>
                    <td className={`status-cell ${status}`}>
                      {status === 'final' ? `Final · ${line}` : status === 'live' ? `${lg?.detail || 'Live'} · ${line}` : 'Scheduled'}
                    </td>
                    <td>
                      {p ? `${g.away} ${n0(p.median?.away)}–${n0(p.median?.home)} ${g.home}` : <span className="muted">not simulated</span>}
                    </td>
                    <td className="num">{pct(p?.home_win_prob)}</td>
                    <td className="num">{inPlay && lg.live_sim ? pct(lg.live_sim.home_win_prob) : '—'}</td>
                  </tr>
                  {isOpen && (
                    <tr className="detail-row">
                      <td colSpan={6}>
                        <div className="detail">
                          <SimDetail gameId={g.game_id} />
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}
