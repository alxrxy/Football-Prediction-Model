import { kickoffLabel, shortDate, spreadParts } from './format.js'
import { TeamLogo } from './ui.jsx'

// Every graded week, newest first, with that week's record and every game
// under it. A weekly record is the unit a season gets read in, and keeping the
// games attached means a bad week stays on screen game by game instead of
// dissolving into the cumulative number.

const MODEL_LABELS = {
  'baseline-v1': 'Baseline',
  'ml-v1': 'ML model',
}

const BREAK_EVEN = 0.524

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

function Moneyline({ value }) {
  if (value === null || value === undefined) return <td className="result muted">tie</td>
  return <td className={`result ${value ? 'W' : 'L'}`}>{value ? '✓' : '✗'}</td>
}

function WeekTag({ version, stats }) {
  const su = stats.su || {}
  const ats = stats.ats || {}
  const suN = su.n || 0
  const suRight = su.right || 0
  const decided = ats.decided || 0
  const beat = decided ? ats.win / decided > BREAK_EVEN : null
  return (
    <span className="week-tag">
      <b>{MODEL_LABELS[version] || version}</b>
      <span>
        ML {suRight}-{suN - suRight}
      </span>
      <span className={beat === null ? '' : beat ? 'good' : 'bad'}>
        ATS {ats.win || 0}-{ats.loss || 0}
        {ats.push ? `-${ats.push}` : ''}
      </span>
    </span>
  )
}

function dateRange(start, end) {
  if (!start) return ''
  return start === end ? shortDate(start) : `${shortDate(start)} – ${shortDate(end)}`
}

export default function WeekBreakdown({ weeks }) {
  if (!weeks?.length) return null

  return (
    <section className="weeks">
      <h3>Week by week</h3>
      {weeks.map((week, i) => (
        <details className="week" key={`${week.season}-${week.week}`} open={i === 0}>
          <summary>
            <span className="week-name">Week {week.week}</span>
            <span className="muted small">
              {dateRange(week.start, week.end)} · {week.n_games} game
              {week.n_games === 1 ? '' : 's'}
            </span>
            <span className="week-tags">
              {Object.entries(week.models || {}).map(([version, stats]) => (
                <WeekTag key={version} version={version} stats={stats} />
              ))}
            </span>
          </summary>

          <div className="table-wrap">
            <table className="slate">
              <thead>
                <tr className="group-head">
                  <th colSpan={4} />
                  <th colSpan={4}>Baseline</th>
                  <th colSpan={3}>ML model</th>
                </tr>
                <tr>
                  <th>Kick</th>
                  <th>Matchup</th>
                  <th className="num">Final</th>
                  <th className="num">Market</th>
                  <th className="num">Spread</th>
                  <th>Leaned</th>
                  <th>ATS</th>
                  <th>Moneyline</th>
                  <th className="num">Spread</th>
                  <th>ATS</th>
                  <th>Moneyline</th>
                </tr>
              </thead>
              <tbody>
                {week.games.map((game) => {
                  const b = game.baseline
                  const ml = game.ml
                  const homeWon = game.home_points > game.away_points
                  return (
                    <tr key={game.game_id}>
                      <td className="muted">{kickoffLabel(game.kickoff, true)}</td>
                      <td className="matchup">
                        <span className="wk-team">
                          <TeamLogo abbr={game.away} size={18} />
                          <strong>{game.away}</strong>
                        </span>
                        <span className="at">@</span>
                        <span className="wk-team">
                          <TeamLogo abbr={game.home} size={18} />
                          <strong>{game.home}</strong>
                        </span>
                        {game.neutral && <span className="tag">neutral</span>}
                      </td>
                      <td className="num final">
                        <span className={homeWon ? '' : 'won'}>{game.away_points}</span>
                        {'–'}
                        <span className={homeWon ? 'won' : ''}>{game.home_points}</span>
                      </td>
                      <SpreadCell spread={game.market_spread} game={game} />
                      <SpreadCell spread={b?.model_spread} game={game} />
                      <td className="lean">
                        {b?.lean ? (b.lean === 'home' ? game.home : game.away) : '—'}
                      </td>
                      <Result value={b?.ats} />
                      <Moneyline value={b?.su} />
                      <SpreadCell spread={ml?.model_spread} game={game} />
                      <Result value={ml?.ats} />
                      <Moneyline value={ml?.su} />
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <p className="muted small week-note">
            Final is away–home, winner in bold. Leaned is the side the baseline
            edge pointed to; ATS grades that side against the stored line. A
            moneyline ✓ means the model&rsquo;s favourite won outright.
          </p>
        </details>
      ))}
    </section>
  )
}
