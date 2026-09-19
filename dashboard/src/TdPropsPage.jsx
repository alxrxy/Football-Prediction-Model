import { useEffect, useState } from 'react'
import { kickoffLabel } from './format.js'
import { teamColor } from './teams.js'
import { PageHead, TeamLogo, pct } from './ui.jsx'

// Anytime-TD props, from td_props.json:
//   python -m src.ingest_td_props && python -m src.td_props
// Exploratory. Kept apart from the yardage list in every layer: its own file,
// ranking, hold-out and caveats. The simulation's chance comes from the stored
// game simulations' box scores; the market's is an estimate, because books
// post Yes only (see src/td_props.py).

const price = (p) => (p == null ? '—' : p > 0 ? `+${p}` : `${p}`)
const signed = (g) => `${g >= 0 ? '+' : '−'}${Math.abs(g * 100).toFixed(1)}`
const share = (v) => (v == null ? '—' : `${Math.round(v * 100)}%`)

const FILTERS = [
  ['all', 'All'],
  ['yes', 'Sim higher'],
  ['no', 'Sim lower'],
]

export default function TdPropsPage({ tabs = null }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('all')
  useEffect(() => {
    fetch(`./td_props.json?ts=${Date.now()}`, { cache: 'no-store' })
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
  const keep = (r) => filter === 'all' || r.pick === filter
  const partial = data && data.games_covered < 16

  return (
    <div className="page">
      <PageHead
        title="Anytime TD props"
        sub={
          data
            ? `Week ${data.week} · ${data.priced} players priced across ${data.games_covered} game${
                data.games_covered === 1 ? '' : 's'
              } · lines pulled ${pulled}`
            : 'Anytime touchdown chances against the game simulations'
        }
      >
        {tabs}
      </PageHead>
      <div className="split">
        <div className="split-main">
          <ExploratoryBanner />
          {error || !data ? (
            <div className="card empty">
              <strong>{error ? 'No TD props ranked yet' : 'Loading TD props…'}</strong>
              <p className="muted">
                Pull the lines and rank them: <code>python -m src.ingest_td_props</code> then{' '}
                <code>python -m src.td_props</code>.
              </p>
            </div>
          ) : (
            <>
              {partial ? (
                <p className="td-sample">
                  <span className="tag warn">Sample</span> {data.games_covered} of 16 games so far:{' '}
                  {Object.values(data.games || {})
                    .map((g) => g.game)
                    .join(', ')}
                  .
                </p>
              ) : null}
              <BiasLine bias={data.bias} />
              <div className="td-controls">
                <div className="segmented" role="group" aria-label="Filter by direction">
                  {FILTERS.map(([key, label]) => (
                    <button key={key} className={filter === key ? 'active' : ''} onClick={() => setFilter(key)}>
                      {label}
                    </button>
                  ))}
                </div>
                <span className="muted small">
                  Ranked by the size of the gap either way. &ldquo;Sim lower&rdquo; rows have no price to take: books
                  don&rsquo;t sell No.
                </span>
              </div>
              <ol className="prop-list">
                {data.props.filter(keep).map((r) => (
                  <TdCard key={`${r.game_id}-${r.player}`} r={r} />
                ))}
              </ol>
              <MoreTd more={(data.more || []).filter(keep)} held={(data.held_out || []).filter(keep)} maxGap={data.max_gap} />
            </>
          )}
        </div>
        <aside className="split-side">
          <HowPriced data={data} />
        </aside>
      </div>
    </div>
  )
}

function ExploratoryBanner() {
  return (
    <div className="td-banner" role="note">
      <strong>Exploratory — lower confidence than the yardage props. Don&rsquo;t bet this list.</strong>
      <ul>
        <li>A touchdown is a yes/no event with a lot of luck in it, so even a correct 35% loses most weeks.</li>
        <li>
          Who scores is the simulator&rsquo;s least certain output: it hands each simulated TD out by past red-zone and
          goal-line usage, adjusted for injuries and the depth chart, and knows nothing about this week&rsquo;s game
          plan.
        </li>
        <li>
          It runs on the same engine that still has an open drive-length gap (simulated drives are shorter than real
          ones; the fix is built but switched off this week).
        </li>
        <li>
          The market number is an estimate. Books only post Yes, so the vig is removed by scaling each book&rsquo;s
          prices to the touchdowns its game total implies, not by a two-sided price.
        </li>
        <li>No bias correction has been fitted for this market, unlike the yardage list.</li>
      </ul>
    </div>
  )
}

function BiasLine({ bias }) {
  if (!bias) return null
  const lower = bias.mean_p_model < bias.mean_p_market
  return (
    <p className="muted small td-bias">
      Across all {bias.n} priced players the simulation averages <b>{pct(bias.mean_p_model)}</b> against the
      market&rsquo;s <b>{pct(bias.mean_p_market)}</b>, and sits lower on {Math.round(bias.share_model_lower * 100)}% of
      them.
      {lower
        ? ' Like the yardage list, part of what ranks here is that lean, not the player.'
        : ''}
    </p>
  )
}

function TdCard({ r }) {
  const yes = r.pick === 'yes'
  return (
    <li className="prop-card td-card" style={{ '--team': teamColor(r.team) }}>
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
          <span className={`pick ${yes ? 'yes' : 'no'}`}>{yes ? '▲ Sim higher' : '▼ Sim lower'}</span>
          <span>Anytime TD</span>
          <span className="muted">
            Yes {price(r.yes_price)}
            {r.book && yes ? ` · ${r.book}` : ''} · {r.books} book{r.books === 1 ? '' : 's'}
            {yes ? '' : ' · No not offered'}
          </span>
          {r.play_prob != null ? <span className="tag warn">{Math.round(r.play_prob * 100)}% to play</span> : null}
          {r.passes_stage1 ? <span className="tag flag">passes Stage 1</span> : null}
        </div>
        <div className="compare" role="img" aria-label={`Simulation ${pct(r.p_model)}, market ${pct(r.p_market)}`}>
          <CompareRow label="Simulation" value={r.p_model} cls="sim" />
          <CompareRow label="Market" value={r.p_market} cls="mkt" />
          <CompareRow label="Price (w/ vig)" value={r.p_market_raw} cls="raw" />
        </div>
        <p className="pc-range muted">
          {r.expected_tds != null ? (
            <>
              Expected TDs <b>{r.expected_tds.toFixed(2)}</b> ·{' '}
            </>
          ) : null}
          2+ TDs {pct(r.two_plus_td)} · {r.touches} touches/game
          {r.usage ? (
            <>
              {' '}
              · red-zone targets {share(r.usage.rz_target_share)} · red-zone carries {share(r.usage.rz_carry_share)} ·
              goal-line carries {share(r.usage.gl_carry_share)}
            </>
          ) : null}
        </p>
      </div>
      <div className={`pc-gap ${yes ? '' : 'neg'}`}>
        <strong>{signed(r.gap)}</strong>
        <em>point gap</em>
      </div>
    </li>
  )
}

function MoreTd({ more, held, maxGap }) {
  if (!more.length && !held.length) return null
  const row = (r, rank) => (
    <tr key={`${r.game_id}-${r.player}`}>
      <td className="num muted">{rank}</td>
      <td>
        <span className="kp-name">
          <TeamLogo abbr={r.team} size={18} />
          <strong>{r.player}</strong>
        </span>
        <em className="sub">
          {r.team} {r.position} · {r.game}
        </em>
      </td>
      <td>
        <span className={`pick sm ${r.pick}`}>{r.pick === 'yes' ? '▲ Higher' : '▼ Lower'}</span>
      </td>
      <td className="num">{price(r.yes_price)}</td>
      <td className="num">{pct(r.p_model)}</td>
      <td className="num">{pct(r.p_market)}</td>
      <td className={`num gap ${r.gap < 0 ? 'neg' : ''}`}>{signed(r.gap)}</td>
    </tr>
  )
  return (
    <details className="card held">
      <summary>
        More TD props · {more.length} further down the ranking
        {held.length ? ` and ${held.length} held out` : ''}
      </summary>
      <div className="table-wrap">
        <table className="more-props">
          <thead>
            <tr>
              <th className="num">#</th>
              <th>Player</th>
              <th>Sim vs market</th>
              <th className="num">Yes</th>
              <th className="num">Sim</th>
              <th className="num">Market</th>
              <th className="num">Gap</th>
            </tr>
          </thead>
          <tbody>
            {more.map((r) => row(r, r.rank))}
            {held.length ? (
              <tr className="group">
                <td colSpan={7}>
                  Held out · gaps over {Math.round(maxGap * 100)} points, more likely a depth-chart or usage miss than a
                  mispriced line
                </td>
              </tr>
            ) : null}
            {held.map((r) => row(r, '—'))}
          </tbody>
        </table>
      </div>
    </details>
  )
}

function HowPriced({ data }) {
  const games = Object.values(data?.games || {})
  const missing = (data?.unmatched || []).filter((u) => (u.p_market_raw || 0) >= 0.1)
  return (
    <div className="card td-side">
      <h4>How this is priced</h4>
      <p className="small">
        <b>Simulation:</b> the share of 10,000 simulated games in which the player scores a rushing or receiving TD.
        Passing TDs don&rsquo;t count for the quarterback; his runs and scrambles do.
      </p>
      <p className="small">
        <b>Market:</b> each book&rsquo;s Yes prices, read as expected TDs, add up to far more than the game can hold.
        Each book is scaled down until they match the TDs its total implies ({data?.devig?.td_per_point ?? 0.105} per
        point, from 2023–25 games), then averaged across books.
      </p>
      {games.length ? (
        <div className="table-wrap">
          <table className="micro">
            <thead>
              <tr>
                <th>Game</th>
                <th className="num">Total</th>
                <th className="num">TDs implied</th>
                <th className="num">Sim TDs</th>
                <th className="num">Vig kept</th>
              </tr>
            </thead>
            <tbody>
              {games.map((g) => {
                const ks = Object.values(g.book_factors || {})
                const lo = ks.length ? Math.min(...ks) : null
                const hi = ks.length ? Math.max(...ks) : null
                return (
                  <tr key={g.game}>
                    <td>{g.game}</td>
                    <td className="num">{g.market_total ?? '—'}</td>
                    <td className="num">{g.implied_player_tds?.toFixed(1) ?? '—'}</td>
                    <td className="num">{g.sim_player_tds?.toFixed(1) ?? '—'}</td>
                    <td className="num" title="Scale applied to each book's prices">
                      {lo == null ? '—' : `${lo.toFixed(2)}–${hi.toFixed(2)}`}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <p className="muted small">
            &ldquo;Vig kept&rdquo; is the scale applied to each book; 0.75 means its prices implied a third more TDs than
            the total supports.
          </p>
        </div>
      ) : null}
      {missing.length ? (
        <>
          <h4>Priced, but not in the simulation</h4>
          <p className="muted small">
            The market gives these players a real chance; the simulated box score has them under one touch a game,
            which usually means the depth chart missed a role.
          </p>
          <ul className="td-missing">
            {missing.map((u) => (
              <li key={`${u.game_id}-${u.player}`}>
                <span>{u.player}</span>
                <span className="muted">{pct(u.p_market_raw)} price</span>
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </div>
  )
}

const CompareRow = ({ label, value, cls }) => (
  <div className="compare-row">
    <span className="compare-label">{label}</span>
    <span className="compare-track">
      <span className={`compare-fill ${cls}`} style={{ width: `${Math.round((value || 0) * 100)}%` }} />
    </span>
    <span className="compare-value">{pct(value)}</span>
  </div>
)
