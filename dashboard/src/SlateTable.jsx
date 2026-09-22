import { Fragment, useState } from 'react'
import GameDetail from './GameDetail.jsx'
import { edgeSide, kickoffLabel, signed, spreadParts, pct } from './format.js'
import { UNVALIDATED_TEXT, flagTrust, labelled, trustTitle } from './flagTrust.js'

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

export default function SlateTable({ games, results }) {
  const trust = flagTrust(results)
  const [open, setOpen] = useState(null)
  const [sort, setSort] = useState('kickoff')
  // An NFL week runs Thursday to Monday; show the day when the slate spans several.
  const multiDay = new Set(games.map((g) => new Date(g.kickoff).toDateString())).size > 1
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
                    <td className="muted">{kickoffLabel(game.kickoff, multiDay)}</td>
                    <td className="matchup">
                      <strong>{game.away}</strong> <span className="at">@</span>{' '}
                      <strong>{game.home}</strong>
                      {game.neutral && <span className="tag">neutral</span>}
                      {proxy && <span className="tag warn">proxy rating</span>}
                      {!b && !ml && (
                        <span className="tag" title="No prediction has been run for this slate yet">
                          not predicted
                        </span>
                      )}
                    </td>
                    {/* The prediction's line is the one it was made and graded
                        against; before there is one, show the current market. */}
                    <SpreadCell spread={b?.market_spread ?? game.market?.spread} game={game} />
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
                              className={labelled(trust) ? 'tag unvalidated' : 'tag flag'}
                              title={
                                labelled(trust)
                                  ? trustTitle(trust)
                                  : b?.market_edge
                                  ? `Blended with the devigged market (model weight ${b.market_edge.weight}): ` +
                                    `${(b.market_edge.p_side_blend * 100).toFixed(1)}% to cover vs ` +
                                    `${(b.market_edge.breakeven * 100).toFixed(1)}% break-even. ` +
                                    'Not yet validated by closing line value.'
                                  : 'Baseline heuristic only, at a fixed threshold. Not backtested.'
                              }
                            >
                              {labelled(trust) ? `flag · ${UNVALIDATED_TEXT}` : 'unvalidated'}
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
        <span className="tag flag">unvalidated</span> marks games where the
        baseline, blended with the devigged market at a small model weight,
        still clears the price&rsquo;s break-even by 3+ points of probability.
        Almost nothing does, by design: the model hasn&rsquo;t shown it knows
        something the line doesn&rsquo;t, and it stays unvalidated until closing
        line value backs it. The trained model&rsquo;s value gate is separate,
        reported in the backtest panel, and currently shut.
      </p>
    </>
  )
}
