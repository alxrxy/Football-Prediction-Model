import { useEffect, useState } from 'react'
import { spreadLabel } from './format.js'
import { UNVALIDATED_TEXT } from './flagTrust.js'
import { pct } from './ui.jsx'

// P66: the prediction under each realistic starting QB, for a game whose starter
// is unresolved. Comparison only: it reads scenarios.json, which nothing else
// in the pipeline reads, and changes no served number. Shown only for games
// that have scenarios; they retire when the inactive list posts or at kickoff.

let request = null
function loadScenarios() {
  if (!request) {
    request = fetch(`./scenarios.json?ts=${Date.now()}`, { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null)
  }
  return request
}

export default function ScenarioPanel({ gameId }) {
  const [data, setData] = useState(null)
  useEffect(() => {
    let live = true
    loadScenarios().then((d) => live && setData(d))
    return () => {
      live = false
    }
  }, [])
  const g = data?.games?.[gameId]
  if (!g || new Date(g.kickoff) <= new Date()) return null
  const rows = [{ ...g.control, key: 'served', served: true }, ...g.scenarios]
  return (
    <div className="card scenarios">
      <div className="scenarios-head">
        <h3>Starting-QB scenarios</h3>
        <span className="tag unvalidated">comparison only · {UNVALIDATED_TEXT}</span>
      </div>
      <p className="muted small">{g.caveat}</p>
      <div className="table-wrap">
        <table className="micro">
          <thead>
            <tr>
              <th>Scenario</th>
              <th className="num">Baseline</th>
              <th className="num">{g.home} win</th>
              <th className="num">Sim median</th>
              <th>Starting QBs in the sim</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key} className={r.served ? 'total' : ''}>
                <td>
                  {r.served ? 'As served' : r.label}
                  {r.injury_cap_binds ? (
                    <span className="tag" title={`${r.team}'s injury charge is already at the 8-point cap, so this change can't move the margin`}>
                      injury cap
                    </span>
                  ) : null}
                </td>
                <td className="num">{spreadLabel(-r.baseline_margin, g.home, g.away)}</td>
                <td className="num">{pct(r.home_win_prob)}</td>
                <td className="num">
                  {r.margin_p50 > 0 ? `${g.home} +${r.margin_p50}` : r.margin_p50 < 0 ? `${g.away} +${-r.margin_p50}` : 'tie'}
                  {' · '}total {r.total_p50}
                </td>
                <td>
                  {Object.entries(r.sim_qbs || {}).map(([team, q]) => (
                    <div key={team}>
                      {team} {q.player}: {Math.round(q.pass_att)} att, {Math.round(q.pass_yds)} yds
                    </div>
                  ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {g.scenarios.map((s) =>
        s.props?.length ? (
          <details key={s.key} className="scenario-props">
            <summary>
              {s.label}: props that move{s.props.some((p) => p.unreliable) ? ' (includes unreliable QB lines)' : ''}
            </summary>
            <table className="micro">
              <tbody>
                {s.props.map((p) => (
                  <tr key={`${p.odds_name}-${p.market}`} className={p.unreliable ? 'bench' : ''}>
                    <td>{p.player}</td>
                    <td>{p.label} {p.line}</td>
                    <td className="num">sim P(over) {pct(p.p_over)}</td>
                    <td className="num">
                      {p.unreliable ? (
                        <span className="tag warn" title="The simulation gives any starter this team's passing; this line measures that gap, not the player">
                          unreliable
                        </span>
                      ) : p.delta != null ? (
                        `${p.delta > 0 ? '+' : ''}${Math.round(p.delta * 100)} pp vs served`
                      ) : (
                        ''
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        ) : null,
      )}
      <p className="muted small">
        {g.sims.toLocaleString()} simulations per scenario, same seed and inputs as the served run · generated{' '}
        {new Date(data.generated_at).toLocaleString([], { weekday: 'short', hour: 'numeric', minute: '2-digit' })} ·
        retires when the inactive list posts
      </p>
    </div>
  )
}
