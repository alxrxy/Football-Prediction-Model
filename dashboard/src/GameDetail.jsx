import SimDetail from './SimDetail.jsx'
import GameQA from './GameQA.jsx'
import { signed, spreadLabel } from './format.js'

// Line movement (P52). Display only: how the market's number has moved since
// the week reopened and since we first tracked it. Not bet percentages.
const movedOn = (iso) =>
  iso ? new Date(iso).toLocaleDateString([], { weekday: 'short', month: 'numeric', day: 'numeric' }) : ''

function MoveRow({ title, at, block, home, away }) {
  if (!block) return null
  const { spread: sp, total: tot } = block
  return (
    <li>
      <span className="muted">{title}{at ? ` (${movedOn(at)})` : ''}</span>
      <span>
        {sp && (
          <>
            {spreadLabel(sp.from, home, away)} → {spreadLabel(sp.to, home, away)}
            {' · '}
            {sp.toward ? `${Math.abs(sp.move).toFixed(1)} toward ${sp.toward}` : 'no meaningful move'}
            {sp.key_numbers?.length ? ` · through ${[...new Set(sp.key_numbers.map(Math.abs))].join(', ')}` : ''}
          </>
        )}
        {tot && (
          <span className="muted">
            {sp ? ' · ' : ''}O/U {tot.from} → {tot.to}
            {tot.direction ? ` (${tot.direction} ${Math.abs(tot.move).toFixed(1)})` : ''}
          </span>
        )}
      </span>
      <span className="muted">{(sp || tot).books} books</span>
    </li>
  )
}

export function LineMovement({ movement: m, home, away }) {
  if (!m) return null
  return (
    <>
      <h4 className="spaced">Line movement</h4>
      <ul className="books line-move">
        <MoveRow title="Since reopen" at={m.reopen_at} block={m.since_reopen} home={home} away={away} />
        <MoveRow title={m.reopen_is_first ? 'Since reopen (first tracked)' : 'Since first tracked'}
                 at={m.first_at} block={m.since_first} home={home} away={away} />
      </ul>
      <p className="muted small">{m.label} Current as of {movedOn(m.current_at)}, {m.pulls} pulls.</p>
    </>
  )
}

// Plain-language note on why the model leans the way it does. Display only:
// written from the served numbers by src/game_explain.py, it changes none.
export function WhyBox({ explanation: why }) {
  if (!why?.text) return null
  return (
    <section className="why">
      <h4>{why.toss_up ? 'Why the model sees a near toss-up' : `Why the model leans ${why.favoured}`}</h4>
      <p>{why.text}</p>
      <p className="why-note">
        Written by Claude from this game&rsquo;s breakdown. It explains the number; it doesn&rsquo;t change it.
      </p>
    </section>
  )
}

// The per-game breakdown (architecture section 6): where the number came from,
// layer by layer, plus the injury report that fed it.
export default function GameDetail({ game, embedded = false }) {
  const baseline = game.baseline
  const layers = baseline?.layers
  const layer1 = baseline?.layer1

  return (
    <div className="detail">
      {/* On the NFL game page, GameView shows this at the top instead. */}
      {!embedded && <WhyBox explanation={game.explanation} />}
      <div className="detail-grid">
        <section>
          <h4>How the baseline got there</h4>
          {layer1 ? (
            <table className="micro">
              <tbody>
                <tr>
                  <td>Power rating difference</td>
                  <td className="num">{signed(layer1.baseline_margin)}</td>
                  <td className="muted">{layer1.source}</td>
                </tr>
                {layers && (
                  <>
                    <tr>
                      <td>Home field</td>
                      <td className="num">{signed(layers.home_field)}</td>
                      <td className="muted">{game.neutral ? 'neutral site' : ''}</td>
                    </tr>
                    <tr>
                      <td>Rest</td>
                      <td className="num">{signed(layers.rest)}</td>
                      <td className="muted">
                        {layers.home_rest_days != null
                          ? `${Math.round(layers.home_rest_days)}d vs ${Math.round(
                              layers.away_rest_days ?? 0,
                            )}d`
                          : 'no prior game loaded'}
                      </td>
                    </tr>
                    <tr>
                      <td>Travel</td>
                      <td className="num">{signed(layers.travel)}</td>
                      <td className="muted">
                        {layers.away_travel_miles != null
                          ? `${Math.round(layers.away_travel_miles)} mi away`
                          : '—'}
                      </td>
                    </tr>
                    <tr>
                      <td>Injuries</td>
                      <td className="num">{signed(layers.injury)}</td>
                      <td className="muted">
                        {layers.injury_data_available
                          ? `${layers.injury_coverage} reported`
                          : 'no data'}
                      </td>
                    </tr>
                    <tr>
                      <td>Weather</td>
                      <td className="num">
                        {layers.wind_factor != null && layers.wind_factor !== 1
                          ? `x${layers.wind_factor.toFixed(3)}`
                          : 'none'}
                      </td>
                      <td className="muted">
                        {layers.is_dome
                          ? 'indoors'
                          : layers.wind_mph != null
                            ? `${Math.round(layers.wind_mph)} mph wind, ${Math.round(
                                layers.temp_f ?? 0,
                              )}°F`
                            : '—'}
                      </td>
                    </tr>
                  </>
                )}
                <tr className="total">
                  <td>Predicted margin</td>
                  <td className="num">{signed(baseline.margin_home)}</td>
                  <td className="muted">home team</td>
                </tr>
              </tbody>
            </table>
          ) : (
            <p className="muted">No baseline breakdown stored for this game.</p>
          )}

          {baseline?.baseline_source === 'sp_plus_fcs_proxy' && (
            <p className="caveat">
              One side has no power rating and was filled with a flat
              replacement-level proxy. This game is never value-flagged, because
              the disagreement with the market would mostly be the proxy&rsquo;s
              own error.
            </p>
          )}
        </section>

        <section>
          <h4>Injury report</h4>
          {game.injuries.home.length === 0 && game.injuries.away.length === 0 ? (
            <p className="muted">
              Nothing reported for either side. That is not the same as both
              teams being healthy — college injury reporting is not mandated and
              is mostly absent.
            </p>
          ) : (
            <div className="injury-cols">
              {['away', 'home'].map((side) => (
                <div key={side}>
                  <h5>{side === 'home' ? game.home : game.away}</h5>
                  {game.injuries[side].length === 0 ? (
                    <p className="muted">none reported</p>
                  ) : (
                    <ul className="injuries">
                      {game.injuries[side].map((item, i) => (
                        <li key={i}>
                          <span className="pts">{item.points?.toFixed(2)}</span>
                          <span className="who">
                            {item.player}
                            <em>
                              {item.position}
                              {item.status ? ` · ${item.status}` : ''}
                              {item.practice ? ` · ${item.practice}` : ''}
                            </em>
                          </span>
                          <span className="snap">
                            {item.snap_share != null
                              ? `${Math.round(item.snap_share * 100)}% snaps`
                              : ''}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          )}

          <h4 className="spaced">Market</h4>
          {game.books.length === 0 ? (
            <p className="muted">No individual book prices stored.</p>
          ) : (
            <ul className="books">
              {game.books.map((b) => (
                <li key={b.book}>
                  <span className="muted">{b.book.replace(/^(oddsapi|cfbd):/, '')}</span>
                  <span>{spreadLabel(b.spread, game.home, game.away)}</span>
                  <span className="muted">{b.total != null ? `O/U ${b.total}` : ''}</span>
                </li>
              ))}
            </ul>
          )}
          <LineMovement movement={game.line_movement} home={game.home} away={game.away} />
        </section>
      </div>
      {/* The NFL game page shows the simulation and Q&A itself; embedded, only
          the breakdown is wanted. In the college table's dropdown, all of it. */}
      {!embedded && (
        <>
          <SimDetail gameId={game.game_id} />
          <GameQA
            gameId={game.game_id}
            suggestions={['Why does the model differ from the market here?', 'What would have to go right for the underdog?']}
          />
        </>
      )}
    </div>
  )
}
