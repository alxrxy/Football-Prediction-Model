import { Fragment, useState } from 'react'
import GameDetail from './GameDetail.jsx'
import { edgeSide, kickoffLabel, signed, spreadParts, pct } from './format.js'

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

const SORTS = {
  kickoff: (a, b) => (a.kickoff || '').localeCompare(b.kickoff || ''),
  edge: (a, b) => Math.abs(b.baseline?.edge ?? -1) - Math.abs(a.baseline?.edge ?? -1),
  matchup: (a, b) => a.home.localeCompare(b.home),
}

export default function SlateTable({ games }) {
  const [open, setOpen] = useState(null)
  const [sort, setSort] = useState('kickoff')
  const [hideProxy, setHideProxy] = useState(false)

  const shown = games
    .filter((g) => !hideProxy || g.baseline?.baseline_source !== 'sp_plus_fcs_proxy')
    .slice()
    .sort(SORTS[sort])

  return (
    <>
      <div className="controls">
        <div className="segmented">
          {Object.keys(SORTS).map((key) => (
            <button
              key={key}
              className={sort === key ? 'active' : ''}
              onClick={() => setSort(key)}
            >
              {key === 'kickoff' ? 'Kickoff' : key === 'edge' ? 'Edge size' : 'Team'}
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
              <th className="num">Market</th>
              <th className="num">Baseline</th>
              <th className="num">ML</th>
              <th className="num">Edge</th>
              <th>Leans</th>
              <th className="num">Home WP</th>
              <th>Conf</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((game) => {
              const b = game.baseline
              const ml = game.ml
              const side = edgeSide(b?.edge, game.home, game.away)
              const isOpen = open === game.game_id
              const proxy = b?.baseline_source === 'sp_plus_fcs_proxy'
              return (
                // Key belongs on the fragment, not the rows inside it: a row
                // plus its detail row are one list item.
                <Fragment key={game.game_id}>
                  <tr
                    className={`row ${isOpen ? 'open' : ''} ${proxy ? 'proxy' : ''}`}
                    onClick={() => setOpen(isOpen ? null : game.game_id)}
                  >
                    <td className="muted">{kickoffLabel(game.kickoff)}</td>
                    <td className="matchup">
                      <strong>{game.away}</strong> <span className="at">@</span>{' '}
                      <strong>{game.home}</strong>
                      {game.neutral && <span className="tag">neutral</span>}
                      {proxy && <span className="tag warn">proxy rating</span>}
                    </td>
                    <SpreadCell spread={b?.market_spread} game={game} />
                    <SpreadCell spread={b?.model_spread} game={game} />
                    <SpreadCell spread={ml?.model_spread} game={game} />
                    <td className={`num edge ${Math.abs(b?.edge ?? 0) >= 4 ? 'big' : ''}`}>
                      {signed(b?.edge)}
                    </td>
                    <td className="lean">
                      {side ? (
                        <>
                          {side}
                          {b?.is_value && (
                            <span
                              className="tag flag"
                              title="Baseline heuristic only, at a fixed threshold. Not backtested."
                            >
                              unvalidated
                            </span>
                          )}
                        </>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td className="num">{pct(b?.win_prob_home)}</td>
                    <td>
                      <span className={`conf ${b?.confidence}`}>{b?.confidence ?? '—'}</span>
                    </td>
                  </tr>
                  {isOpen && (
                    <tr className="detail-row">
                      <td colSpan={9}>
                        <GameDetail game={game} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="muted small">
        Spreads shown as <em>favourite &minus;points</em>. Edge is positive when
        the model prefers the home side; &ldquo;leans&rdquo; names that side.
        Click any row for the full breakdown.
      </p>
      <p className="muted small">
        <span className="tag flag">unvalidated</span> marks games past the
        baseline&rsquo;s fixed edge threshold. That is a heuristic, not a
        backtested signal &mdash; it is a different thing from the trained
        model&rsquo;s value gate, which is reported separately and is currently
        shut.
      </p>
    </>
  )
}
