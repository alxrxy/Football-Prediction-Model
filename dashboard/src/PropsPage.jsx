import { useEffect, useState } from 'react'
import GameQA from './GameQA.jsx'
import { kickoffLabel } from './format.js'
import { teamColor } from './teams.js'
import { PageHead, TeamLogo, pct } from './ui.jsx'

// Best props of the week, from props.json:
//   python -m src.ingest_props && python -m src.props
// Each prop is priced twice: the market's vig-free chance (over/under devigged
// across books) and the simulation's chance for that player; ranked by the gap.
// Claude writes the explanations once per export; the Q&A asks about the list.

const price = (p) => (p == null ? '' : p > 0 ? `+${p}` : `${p}`)
const num = (v) => (v == null ? '—' : Math.abs(v) >= 10 ? Math.round(v) : v)

export default function PropsPage() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => {
    fetch(`./props.json?ts=${Date.now()}`, { cache: 'no-store' })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(setData)
      .catch((e) => setError(e.message))
  }, [])

  const pulled = data?.lines_pulled_at
    ? new Date(data.lines_pulled_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
    : null

  return (
    <div className="page">
      <PageHead
        title="Best props"
        sub={
          data
            ? `Week ${data.week} · ${data.priced} props priced against the simulations · lines pulled ${pulled}`
            : 'Player props ranked against the game simulations'
        }
      />
      <div className="split">
        <div className="split-main">
          {error || !data ? (
            <div className="card empty">
              <strong>{error ? 'No props ranked yet' : 'Loading props…'}</strong>
              <p className="muted">
                Pull the lines and rank them: <code>python -m src.ingest_props</code> then <code>python -m src.props</code>.
              </p>
            </div>
          ) : (
            <>
              <div className="caveat">
                Ranked by how far the simulation&rsquo;s chance sits from the market&rsquo;s. Known bias this week (P17):
                the simulator gives every player league-typical yards per catch and carry, so star receivers tend to project
                under their lines and the gaps run large. Treat these as a check on the simulator, not picks.
              </div>
              <ol className="prop-list">
                {data.props.map((r) => (
                  <PropCard key={`${r.game_id}-${r.player}-${r.market}`} r={r} />
                ))}
              </ol>
              {data.held_out?.length ? (
                <details className="card held">
                  <summary>
                    {data.held_out.length} more held out: gaps over {Math.round(data.max_gap * 100)} points, more likely a
                    usage miss than a mispriced line
                  </summary>
                  <ul>
                    {data.held_out.map((h) => (
                      <li key={`${h.player}-${h.market}`}>
                        <TeamLogo abbr={h.team} size={20} />
                        <strong>{h.player}</strong> {h.label} {h.pick} {h.line}
                        <span className="muted">
                          {' '}
                          · sim {pct(h.p_model)} vs market {pct(h.p_market)} · sim median {num(h.sim?.median)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </details>
              ) : null}
            </>
          )}
        </div>
        <aside className="split-side">
          <GameQA
            scope="props"
            title="Ask about these props"
            suggestions={[
              'Which of these do you trust least, and why?',
              'Why do so many receivers project under their lines?',
              'Explain the top prop in plain English.',
            ]}
            placeholder="Ask about the props list…"
          />
        </aside>
      </div>
    </div>
  )
}

function PropCard({ r }) {
  const over = r.pick === 'over'
  return (
    <li className="prop-card" style={{ '--team': teamColor(r.team) }}>
      <span className="pc-rank">{r.rank}</span>
      <TeamLogo abbr={r.team} size={40} />
      <div className="pc-main">
        <div className="pc-head">
          <strong>{r.player}</strong>
          <span className="muted">
            {r.team} {r.position} · {r.game} · {kickoffLabel(r.kickoff, true)}
          </span>
        </div>
        <div className="pc-pick">
          <span className={`pick ${r.pick}`}>
            {over ? '▲ Over' : '▼ Under'} {r.line}
          </span>
          <span>{r.label}</span>
          <span className="muted">
            {price(r.price)} · {r.book}
            {r.books > 1 ? ` · ${r.books} books` : ' · 1 book'}
          </span>
          {r.passes_stage1 ? <span className="tag flag">passes Stage 1</span> : null}
        </div>
        <div className="compare" role="img" aria-label={`Simulation ${pct(r.p_model)}, market ${pct(r.p_market)}`}>
          <CompareRow label="Simulation" value={r.p_model} cls="sim" />
          <CompareRow label="Market" value={r.p_market} cls="mkt" />
        </div>
        <p className="pc-range muted">
          Simulated {r.label.toLowerCase()}: median <b>{num(r.sim?.median)}</b> · middle 50% {num(r.sim?.p25)}–{num(r.sim?.p75)} ·
          80% {num(r.sim?.p10)}–{num(r.sim?.p90)}
        </p>
        {r.explanation ? <p className="pc-why">{r.explanation}</p> : null}
      </div>
      <div className="pc-gap">
        <strong>+{(r.gap * 100).toFixed(1)}</strong>
        <em>point gap</em>
      </div>
    </li>
  )
}

const CompareRow = ({ label, value, cls }) => (
  <div className="compare-row">
    <span className="compare-label">{label}</span>
    <span className="compare-track">
      <span className={`compare-fill ${cls}`} style={{ width: `${Math.round((value || 0) * 100)}%` }} />
      <span className="compare-mid" />
    </span>
    <span className="compare-value">{pct(value)}</span>
  </div>
)
