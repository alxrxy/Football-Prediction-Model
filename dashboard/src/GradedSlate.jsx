import { useState } from 'react'
import { dateLabel, kickoffLabel, signed, spreadParts } from './format.js'

function SpreadCell({ spread, game }) {
  const parts = spreadParts(spread, game.home, game.away)
  if (!parts) return <td className="num spread muted">—</td>
  return (
    <td className="num spread">
      <span className="fav">{parts.team}</span>
      <span className="line">{parts.line}</span>
    </td>
  )
}

function Result({ value }) {
  if (!value) return <td className="result muted">—</td>
  return <td className={`result ${value}`}>{value}</td>
}

function StraightUp({ value }) {
  if (value === null || value === undefined) return <td className="result muted">tie</td>
  return <td className={`result ${value ? 'W' : 'L'}`}>{value ? '✓' : '✗'}</td>
}

const SORTS = {
  kickoff: (a, b) => (a.kickoff || '').localeCompare(b.kickoff || ''),
  miss: (a, b) => Math.abs(b.baseline?.error ?? 0) - Math.abs(a.baseline?.error ?? 0),
  edge: (a, b) => Math.abs(b.baseline?.edge ?? -1) - Math.abs(a.baseline?.edge ?? -1),
}
const SORT_LABELS = { kickoff: 'Kickoff', miss: 'Biggest miss', edge: 'Edge size' }

function record(games, key) {
  const picks = games.map((g) => g[key]).filter(Boolean)
  const decided = picks.filter((p) => p.su !== null && p.su !== undefined)
  return {
    n: picks.length,
    win: picks.filter((p) => p.ats === 'W').length,
    loss: picks.filter((p) => p.ats === 'L').length,
    suRight: decided.filter((p) => p.su).length,
    suN: decided.length,
  }
}

// Every game of the most recent graded slate, not a summary. A record only
// means something if the misses are on screen next to the hits.
export default function GradedSlate({ slate }) {
  const [sort, setSort] = useState('kickoff')
  const [hideProxy, setHideProxy] = useState(false)
  if (!slate?.games?.length) return null

  const shown = slate.games
    .filter((g) => !hideProxy || g.baseline?.baseline_source !== 'sp_plus_fcs_proxy')
    .slice()
    .sort(SORTS[sort])
  const base = record(shown, 'baseline')
  const ml = record(shown, 'ml')

  return (
    <section className="graded">
      <h2>
        Last graded slate
        <span className="muted"> · {dateLabel(slate.date)}</span>
      </h2>
      <div className="graded-summary">
        <span>
          Baseline <strong>{base.win}-{base.loss}</strong> ATS ·{' '}
          <strong>
            {base.suRight}/{base.suN}
          </strong>{' '}
          straight up
        </span>
        {ml.n > 0 && (
          <span>
            ML <strong>{ml.win}-{ml.loss}</strong> ATS ·{' '}
            <strong>
              {ml.suRight}/{ml.suN}
            </strong>{' '}
            straight up
          </span>
        )}
      </div>

      <div className="controls">
        <div className="segmented">
          {Object.keys(SORTS).map((key) => (
            <button
              key={key}
              className={sort === key ? 'active' : ''}
              onClick={() => setSort(key)}
            >
              {SORT_LABELS[key]}
            </button>
          ))}
        </div>
        <label className="toggle">
          <input
            type="checkbox"
            checked={hideProxy}
            onChange={(e) => setHideProxy(e.target.checked)}
          />
          Hide proxy-rated games
        </label>
        <span className="muted small">{shown.length} games</span>
      </div>

      <div className="table-wrap">
        <table className="slate">
          <thead>
            <tr>
              <th>Kick</th>
              <th>Matchup</th>
              <th className="num">Final</th>
              <th className="num">Market</th>
              <th className="num">Baseline</th>
              <th className="num">Edge</th>
              <th>Leaned</th>
              <th>ATS</th>
              <th>SU</th>
              <th className="num">Model miss</th>
              <th className="num">Line miss</th>
              <th className="num">ML</th>
              <th>ML ATS</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((game) => {
              const b = game.baseline
              const ml = game.ml
              const proxy = b?.baseline_source === 'sp_plus_fcs_proxy'
              const homeWon = game.home_points > game.away_points
              return (
                <tr key={game.game_id} className={proxy ? 'proxy' : ''}>
                  <td className="muted">{kickoffLabel(game.kickoff)}</td>
                  <td className="matchup">
                    <strong>{game.away}</strong> <span className="at">@</span>{' '}
                    <strong>{game.home}</strong>
                    {game.neutral && <span className="tag">neutral</span>}
                    {proxy && <span className="tag warn">proxy rating</span>}
                  </td>
                  <td className="num final">
                    <span className={homeWon ? '' : 'won'}>{game.away_points}</span>
                    {'–'}
                    <span className={homeWon ? 'won' : ''}>{game.home_points}</span>
                  </td>
                  <SpreadCell spread={game.market_spread} game={game} />
                  <SpreadCell spread={b?.model_spread} game={game} />
                  <td className={`num edge ${Math.abs(b?.edge ?? 0) >= 4 ? 'big' : ''}`}>
                    {signed(b?.edge)}
                  </td>
                  <td className="lean">
                    {b?.lean ? (b.lean === 'home' ? game.home : game.away) : '—'}
                  </td>
                  <Result value={b?.ats} />
                  <StraightUp value={b?.su} />
                  <td className="num">{signed(b?.error)}</td>
                  <td className="num muted">{signed(game.market_error)}</td>
                  <SpreadCell spread={ml?.model_spread} game={game} />
                  <Result value={ml?.ats} />
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="muted small">
        Final is away&ndash;home, winner in bold. ATS grades the side the edge
        leaned to against the line stored with the prediction, not a line
        pulled afterwards. Miss is the predicted home margin minus the actual
        one: positive means the home team was overrated. Line miss is the same
        for the market, for comparison.
      </p>
    </section>
  )
}
