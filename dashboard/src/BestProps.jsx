import { useEffect, useState } from 'react'
import { kickoffLabel } from './format.js'
import './claude.css'

// Best props of the week, from props.json:
//   python -m src.ingest_props && python -m src.props
// Each prop is priced twice: the market's vig-free chance (devigged over/under,
// averaged across books) and the simulation's chance for that player. Ranked by
// the gap on the side the simulation prefers. The explanations are written by
// Claude once per export, not per page view.

const pct = (v) => (v == null ? '—' : `${Math.round(v * 100)}%`)
const price = (p) => (p == null ? '' : p > 0 ? `+${p}` : `${p}`)
const num = (v) => (v == null ? '—' : Math.abs(v) >= 10 ? Math.round(v) : v)

export default function BestProps() {
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

  return (
    <section className="best-props">
      <h2>
        Best props of the week
        {data?.week ? <span className="muted"> · Week {data.week}</span> : null}
      </h2>
      {error || !data ? (
        <p className="muted">
          {error ? 'No props ranked yet. ' : 'Loading props… '}
          Pull the lines and rank them with <code>python -m src.ingest_props</code> then{' '}
          <code>python -m src.props</code>.
        </p>
      ) : !data.props?.length ? (
        <p className="muted">No props could be priced against the simulations this week.</p>
      ) : (
        <>
          <p className="caveat">
            Ranked by how far the simulation&rsquo;s chance sits from the market&rsquo;s vig-free chance. Player
            projections are the simulator&rsquo;s lowest-confidence output, so a big gap is as likely to be a usage miss
            as a mispriced line. None of these are validated picks.
          </p>
          <p className="caveat">
            Known bias, week 2: the simulator gives every player league-typical yards per catch and carry, and splits
            targets by depth-chart share, so star receivers tend to project under their lines and the gaps run large.
            Treat this list as a check on the simulator until player-level efficiency is modelled (calibration log,
            P17).
          </p>
          <div className="table-wrap">
            <table className="props-rank">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Player</th>
                  <th>Prop</th>
                  <th className="num">Sim</th>
                  <th className="num">Market</th>
                  <th className="num">Gap</th>
                  <th>Sim range</th>
                </tr>
              </thead>
              <tbody>
                {data.props.map((r) => (
                  <PropRow key={`${r.game_id}-${r.player}-${r.market}`} r={r} />
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted small">
            Sim and Market are each side&rsquo;s chance of the pick hitting. Sim range: the median, then the middle 50%
            of simulations. Best price across {data.props[0]?.books ? 'the books quoting the consensus line' : 'books'};
            the tag marks a prop that would also pass the Stage 1 test (blended with the market at model weight{' '}
            {data.model_weight}, {Math.round(data.edge_buffer * 100)} pp past break-even).{' '}
            {data.held_out?.length
              ? `${data.held_out.length} prop(s) with gaps over ${Math.round(data.max_gap * 100)} pp are held out as likely usage misses. `
              : ''}
            Lines pulled{' '}
            {data.lines_pulled_at ? new Date(data.lines_pulled_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '—'}
            .
          </p>
        </>
      )}
    </section>
  )
}

function PropRow({ r }) {
  return (
    <>
      <tr>
        <td className="num rank">{r.rank}</td>
        <td>
          <strong>{r.player}</strong>
          <em className="sub">
            {r.team} {r.position} · {r.game} · {kickoffLabel(r.kickoff, true)}
          </em>
        </td>
        <td>
          {r.label} <strong>{r.pick === 'over' ? 'Over' : 'Under'} {r.line}</strong>
          <em className="sub">
            {price(r.price)} {r.book}
            {r.passes_stage1 ? <span className="tag flag">passes Stage 1</span> : null}
          </em>
        </td>
        <td className="num">{pct(r.p_model)}</td>
        <td className="num">{pct(r.p_market)}</td>
        <td className="num gap">+{(r.gap * 100).toFixed(1)}</td>
        <td className="muted">
          {num(r.sim?.median)} <em className="sub">50%: {num(r.sim?.p25)}–{num(r.sim?.p75)}</em>
        </td>
      </tr>
      {r.explanation ? (
        <tr className="why">
          <td />
          <td colSpan={6}>{r.explanation}</td>
        </tr>
      ) : null}
    </>
  )
}
