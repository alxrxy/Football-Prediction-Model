import GameQA from './GameQA.jsx'
import WinProbChart from './WinProbChart.jsx'
import { feedFresh, liveGamesOf } from './simData.js'
import { kickoffLabel } from './format.js'
import { matchupColors, team } from './teams.js'
import { PageHead, StatusChip, TeamLogo, byTeam, n0, pct, until } from './ui.jsx'

// Games in progress: the flow of each game (score, clock, field position, the
// live model's win chance over time, scoring) with a Claude Q&A that answers
// from the live state. Needs the live tracker running: python -m src.live_tracker
// A stopped tracker's old snapshot is ignored (simData.feedFresh), so a game
// that ended days ago never shows here as live.

export default function LivePage({ feed, sport, onOpen }) {
  const live = liveGamesOf(feed)
  const running = feedFresh(feed)
  const next = (sport.games || [])
    .filter((g) => new Date(g.kickoff).getTime() > Date.now())
    .sort((a, b) => a.kickoff.localeCompare(b.kickoff))
    .slice(0, 4)

  return (
    <div className="page">
      <PageHead
        title="Live games"
        sub={
          live.length
            ? `${live.length} in progress · updates every poll`
            : running
              ? 'The live tracker is running; no game is in progress right now'
              : 'The live tracker isn’t running'
        }
      />
      {live.length ? (
        live.map((g) => <LiveGame key={g.game_id} g={g} onOpen={onOpen} />)
      ) : (
        <div className="card empty live-empty">
          <span className="empty-icon" aria-hidden="true">◌</span>
          <strong>No games in progress</strong>
          <p className="muted">
            {running
              ? 'Games appear here the moment they kick off, with the live model and a Q&A box.'
              : 'On game day, start the tracker with python -m src.live_tracker (and python -m src.api_server for Q&A). Games in progress then appear here.'}
          </p>
          {next.length ? (
            <div className="next-up">
              <h4>Next kickoffs</h4>
              {next.map((g) => (
                <button key={g.game_id} className="next-row" onClick={() => onOpen(g.game_id)}>
                  <TeamLogo abbr={g.away} size={24} />
                  <span>{g.away}</span>
                  <span className="at">@</span>
                  <TeamLogo abbr={g.home} size={24} />
                  <span>{g.home}</span>
                  <span className="muted">
                    {new Date(g.kickoff).toLocaleDateString([], { weekday: 'short' })} {kickoffLabel(g.kickoff)}
                  </span>
                  <span className="countdown">{until(g.kickoff)}</span>
                </button>
              ))}
            </div>
          ) : null}
        </div>
      )}
    </div>
  )
}

function LiveGame({ g, onOpen }) {
  const { home, away } = g
  const colors = matchupColors(away, home)
  const s = g.live_sim || {}
  const scoring = (g.recent_scoring || []).slice().reverse()
  return (
    <section className="live-game">
      <div className="scoreboard" style={{ '--away': colors.away, '--home': colors.home }}>
        <SbTeam abbr={away} pts={g.away_score} ball={g.possession === away} />
        <div className="sb-mid">
          <StatusChip status="live" detail={g.detail} />
          {g.down_distance ? <strong>{g.down_distance}</strong> : null}
          {g.red_zone ? <span className="chip rz">Red zone</span> : null}
          <button className="linkish" onClick={() => onOpen(g.game_id)}>Full game page →</button>
        </div>
        <SbTeam abbr={home} pts={g.home_score} ball={g.possession === home} right />
      </div>
      <div className="split">
        <div className="split-main">
          <div className="card">
            <WinProbChart history={g.live_history} home={home} away={away} colors={colors} scoring={g.score_path} />
          </div>
          <div className="tiles">
            <Tile label={`${home} win chance`} value={pct(s.home_win_prob)} sub={`pregame ${pct(s.pregame_win_prob_home)}`} />
            <Tile label="Projected final" value={`${away} ${n0(s.median_away_points)} – ${n0(s.median_home_points)} ${home}`} sub="median of the re-simulations" />
            <Tile label="Projected margin" value={byTeam(s.mean_margin_home, home, away)} sub={`80%: ${home} ${n0(s.margin_80_low)} to ${n0(s.margin_80_high)}`} />
            <Tile label="Projected total" value={n0(s.total_median)} sub={`80%: ${n0(s.total_80_low)}–${n0(s.total_80_high)}`} />
          </div>
          <div className="card">
            <h4>Scoring</h4>
            {scoring.length ? (
              <ul className="scoring">
                {scoring.map((e, i) => (
                  <li key={i}>
                    <TeamLogo abbr={e.team} size={22} />
                    <span className="sc-when">Q{e.period} {e.clock}</span>
                    <span className="sc-what">
                      <b>{e.type}</b> {e.text}
                    </span>
                    <span className="sc-score">
                      {e.away_score}–{e.home_score}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted small">No scoring yet.</p>
            )}
          </div>
          <KeyPlayers box={s.box_score} home={home} away={away} />
        </div>
        <aside className="split-side">
          <GameQA
            gameId={g.game_id}
            title="Ask how this game is playing out"
            suggestions={[
              'How is this playing out against the pregame projection?',
              'What does the live model expect from here?',
              'Who is running ahead of their projection?',
            ]}
            placeholder="Ask about the game so far or how it should finish…"
          />
        </aside>
      </div>
    </section>
  )
}

function SbTeam({ abbr, pts, ball, right }) {
  return (
    <div className={`sb-team${right ? ' right' : ''}`}>
      <TeamLogo abbr={abbr} size={64} />
      <div className="sb-name">
        <strong>{team(abbr).nick || abbr}</strong>
        <em>{ball ? '● ball' : abbr}</em>
      </div>
      <span className="sb-score">{pts ?? '–'}</span>
    </div>
  )
}

function KeyPlayers({ box, home, away }) {
  if (!box) return null
  const rows = []
  for (const [side, abbr] of [['away', away], ['home', home]]) {
    for (const p of (box[side]?.players || []).slice(0, 4)) {
      const main = p.passing ? ['pass yds', p.passing.yds] : p.rushing && (!p.receiving || p.rushing.att?.mean >= p.receiving.tgt?.mean) ? ['rush yds', p.rushing.yds] : p.receiving ? ['rec yds', p.receiving.yds] : null
      if (!main) continue
      const sf = p.so_far || {}
      const now = main[0] === 'pass yds' ? sf.pass_yds : main[0] === 'rush yds' ? sf.rush_yds : sf.rec_yds
      rows.push({ abbr, name: p.player, stat: main[0], now: now ?? 0, q: main[1] })
    }
  }
  if (!rows.length) return null
  return (
    <div className="card">
      <h4>Key players · so far and projected final</h4>
      <table className="micro">
        <thead>
          <tr>
            <th>Player</th>
            <th>Stat</th>
            <th className="num">So far</th>
            <th className="num">Projected final</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={`${r.abbr}-${r.name}`}>
              <td>
                <span className="kp-name">
                  <TeamLogo abbr={r.abbr} size={18} />
                  {r.name}
                </span>
              </td>
              <td className="muted">{r.stat}</td>
              <td className="num">{r.now}</td>
              <td className="num">
                {n0(r.q?.median)} <span className="muted">({n0(r.q?.p25)}–{n0(r.q?.p75)})</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const Tile = ({ label, value, sub }) => (
  <div className="stat-tile">
    <em>{label}</em>
    <strong>{value}</strong>
    {sub ? <span>{sub}</span> : null}
  </div>
)
