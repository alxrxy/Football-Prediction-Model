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

// A prop shows two simulation numbers only when the correction actually moved it.
const adjusted = (r) => r.p_model_raw != null && r.p_model_raw !== r.p_model

// Says plainly what the adjustment is and what it is not: a measured shift with
// a small in-sample fit behind it, not a fixed simulator.
function BiasNote({ fit }) {
  const n = fit.n || {}
  const sizes = Object.values(n).sort((a, b) => a - b)
  const rb = fit.position_offsets?.player_rush_yds?.RB
  const rbBias = fit.position_raw_bias_pp?.player_rush_yds?.RB
  const recYds = fit.position_raw_bias_pp?.player_reception_yds
  const recYdsN = fit.position_n?.player_reception_yds || {}
  const dates = fit.measured_at_by_market
  return (
    <div className="caveat">
      <strong>Bias-adjusted.</strong> These are not raw simulation output. The simulator projects skill
      players under their lines, so each category&rsquo;s probability is shifted by a measured offset
      (pass yards {fit.raw_bias_pp?.player_pass_yds > 0 ? '+' : ''}
      {fit.raw_bias_pp?.player_pass_yds}pp, receiving{' '}
      {fit.raw_bias_pp?.player_reception_yds}pp, receptions {fit.raw_bias_pp?.player_receptions}pp).
      It is a statistical correction, not a fix: the underlying cause is still open. The offsets were
      fitted <b>in sample</b>{' '}
      {dates
        ? `(receiving ${dates.player_reception_yds}, receptions ${dates.player_receptions}, pass yards ${dates.player_pass_yds})`
        : `on ${fit.measured_at}`}{' '}
      from{' '}
      {sizes.length ? `${sizes[0]}–${sizes[sizes.length - 1]}` : 'a few dozen'} props per category, so
      they are provisional and unvalidated out of sample.
      {' '}<b>Ranked by the raw simulation&rsquo;s disagreement; the probability shown is
      bias-adjusted.</b>{' '}The offset is one constant per category, so it cannot order players within
      one — it makes the number honest, not the ranking better. Each card shows the raw number alongside.
      {rb != null ? (
        <>
          {' '}<b>Rushing is corrected by position.</b>{' '}Running backs get their own offset
          ({rbBias}pp raw, n = {fit.position_n?.player_rush_yds?.RB}, refitted {fit.position_measured_at}).{' '}
          {fit.position_notes?.player_rush_yds?.RB}{' '}Quarterback rushing props get no offset and are not ranked
          at all: they are held out below as an engine defect.
        </>
      ) : null}
      {recYds ? (
        <>
          {' '}<b>Receiving yards are corrected by position</b>{' '}(raw: WR {recYds.WR}pp, n = {recYdsN.WR};
          TE {recYds.TE}pp, n = {recYdsN.TE}; RB {recYds.RB}pp, n = {recYdsN.RB}), because backs sit about
          half as far under as receivers.{' '}{fit.position_notes?.player_reception_yds?.ALL}
        </>
      ) : null}
    </div>
  )
}

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
            ? `Week ${data.week} · ${data.priced} props priced against the simulations · lines pulled ${pulled}` +
              (data.lines_refreshed_games?.length
                ? ` · ${data.lines_refreshed_games.join(', ')} re-pulled ${new Date(data.lines_refreshed_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}`
                : '')
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
              {data.bias_adjust?.applied ? <BiasNote fit={data.bias_adjust} /> : (
                <div className="caveat">
                  Ranked by how far the simulation&rsquo;s chance sits from the market&rsquo;s. Known bias this week (P17):
                  the simulator gives every player league-typical yards per catch and carry, so star receivers tend to project
                  under their lines and the gaps run large. Treat these as a check on the simulator, not picks.
                </div>
              )}
              <p className="muted small alt-rule">
                Alt line: an easier line on the same side (lower for an over, higher for an under) that the simulation
                gives {Math.round((data.alt_rule?.min_p ?? 0.65) * 100)}%+, priced {data.alt_rule?.min_price ?? -250} or
                longer, with the best expected return. Books post alternates as overs, so unders usually have none. Same
                simulation, same caveat.
              </p>
              <ol className="prop-list">
                {data.props.map((r) => (
                  <PropCard key={`${r.game_id}-${r.player}-${r.market}`} r={r} />
                ))}
              </ol>
              <MoreProps more={data.more || []} held={data.held_out || []} maxGap={data.max_gap}
                structural={data.structural_holdouts || []} />
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
        {r.alt ? (
          <div className="alt-line">
            <span className="alt-tag">Alt line</span>
            <span className={`pick ${r.pick}`}>
              {over ? '▲ Over' : '▼ Under'} {r.alt.line}
            </span>
            <strong className="alt-price">{price(r.alt.price)}</strong>
            <span className="muted">
              {r.alt.book} · simulation {pct(r.alt.p_model)} vs {pct(r.alt.breakeven)} to break even
            </span>
          </div>
        ) : (
          <p className="alt-none muted">
            {r.pick === 'under'
              ? 'No alt line: books post alternates as overs, so there’s no easier under to offer.'
              : 'No alt line clears the bar (an easier over the simulation gives 65%+, at −250 or longer).'}
          </p>
        )}
        <div className="compare" role="img" aria-label={`Simulation ${pct(r.p_model)}, market ${pct(r.p_market)}`}>
          {adjusted(r) ? <CompareRow label="Raw simulation" value={r.p_model_raw} cls="raw" /> : null}
          <CompareRow label={adjusted(r) ? 'Bias-adjusted' : 'Simulation'} value={r.p_model} cls="sim" />
          <CompareRow label="Market" value={r.p_market} cls="mkt" />
        </div>
        <p className="pc-range muted">
          Simulated {r.label.toLowerCase()}: median <b>{num(r.sim?.median)}</b> · middle 50% {num(r.sim?.p25)}–{num(r.sim?.p75)} ·
          80% {num(r.sim?.p10)}–{num(r.sim?.p90)}
        </p>
        {r.defect_note ? <div className="caveat">{r.defect_note}</div> : null}
        {r.explanation ? <p className="pc-why">{r.explanation}</p> : null}
      </div>
      <div className="pc-gap">
        <strong>+{(r.gap * 100).toFixed(1)}</strong>
        <em>{adjusted(r) ? 'raw point gap' : 'point gap'}</em>
        {adjusted(r) && r.gap_adjusted != null ? (
          <em className="muted">{(r.gap_adjusted * 100).toFixed(1)} adjusted</em>
        ) : null}
      </div>
    </li>
  )
}

// Everything below the top list: the rest of the ranking, then the props held
// out for gaps too big to believe.
function MoreProps({ more, held, maxGap, structural }) {
  if (!more.length && !held.length) return null
  const gapHeld = held.filter((r) => r.held_reason !== 'structural')
  const defectHeld = held.filter((r) => r.held_reason === 'structural')
  const row = (r, rank) => (
    <tr key={`${r.game_id}-${r.player}-${r.market}`}>
      <td className="num muted">{rank}</td>
      <td>
        <span className="kp-name">
          <TeamLogo abbr={r.team} size={18} />
          <strong>{r.player}</strong>
        </span>
        <em className="sub">{r.game}</em>
        {r.defect_note ? <em className="sub">Known issue (P28): starter mismatch, treat with caution</em> : null}
      </td>
      <td>{r.label}</td>
      <td>
        <span className={`pick sm ${r.pick}`}>
          {r.pick === 'over' ? '▲ O' : '▼ U'} {r.line}
        </span>
      </td>
      <td className="num">{price(r.price)}</td>
      <td className="num">{pct(r.p_model)}</td>
      <td className="num">{pct(r.p_market)}</td>
      <td className="num gap">+{(r.gap * 100).toFixed(1)}</td>
    </tr>
  )
  return (
    <details className="card held">
      <summary>
        More props · {more.length} further down the ranking
        {held.length ? ` and ${held.length} held out` : ''}
      </summary>
      <div className="table-wrap">
        <table className="more-props">
          <thead>
            <tr>
              <th className="num">#</th>
              <th>Player</th>
              <th>Prop</th>
              <th>Pick</th>
              <th className="num">Price</th>
              <th className="num">Sim</th>
              <th className="num">Market</th>
              <th className="num">Gap</th>
            </tr>
          </thead>
          <tbody>
            {more.map((r) => row(r, r.rank))}
            {gapHeld.length ? (
              <tr className="group">
                <td colSpan={8}>
                  Held out · gaps over {Math.round(maxGap * 100)} points, more likely a usage miss than a mispriced line
                </td>
              </tr>
            ) : null}
            {gapHeld.map((r) => row(r, '—'))}
            {defectHeld.length ? (
              <tr className="group">
                <td colSpan={8}>
                  Held out · engine defect, not player signal
                  {structural.map((s) => <em key={s.market + s.position} className="sub">{s.note}</em>)}
                </td>
              </tr>
            ) : null}
            {defectHeld.map((r) => row(r, '—'))}
          </tbody>
        </table>
      </div>
    </details>
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
