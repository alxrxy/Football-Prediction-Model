import GameDetail from './GameDetail.jsx'
import GameQA from './GameQA.jsx'
import SimDetail from './SimDetail.jsx'
import { liveGame, useSimEntry } from './simData.js'
import { spreadLabel } from './format.js'
import { matchupColors, team } from './teams.js'
import { StatusChip, TeamLogo, WinBar, n0, pct } from './ui.jsx'

// One game, full page: the matchup, the simulation, how the baseline got its
// number, and a Claude Q&A that answers from this game's data.

export default function GameView({ sport, gameId, feed, onBack, onPast }) {
  const game = sport.games.find((g) => g.game_id === gameId)
  const { entry, week } = useSimEntry(gameId)
  // A past week's game is no longer in the current slate: its header reads the
  // model numbers archived with it, as they stood before kickoff.
  const heroGame = game || (entry?.predictions ? { ...entry.predictions, kickoff: entry.kickoff } : null)
  const lg = liveGame(feed, gameId)
  const home = game?.home || entry?.home
  const away = game?.away || entry?.away

  if (!home) {
    return (
      <div className="page">
        <button className="back" onClick={onBack}>← All games</button>
        <p className="muted">This game isn&rsquo;t in the current export.</p>
      </div>
    )
  }

  return (
    <div className="page game-view">
      {week && !game ? (
        <button className="back" onClick={onPast}>← Past weeks</button>
      ) : (
        <button className="back" onClick={onBack}>← All games</button>
      )}
      <Hero game={heroGame} entry={entry} lg={lg} home={home} away={away} />
      {week && !game ? (
        <p className="muted small">
          From the week {week.week} archive: model and market numbers are the last ones made before kickoff.
        </p>
      ) : null}
      <div className="split">
        <div className="split-main">
          {game?.known_issue ? <div className="caveat">{game.known_issue}</div> : null}
          <div className="card">
            <SimDetail gameId={gameId} />
          </div>
          {game ? (
            <div className="card">
              <GameDetail game={game} embedded />
            </div>
          ) : null}
        </div>
        <aside className="split-side">
          <GameQA
            gameId={gameId}
            title="Ask about this game"
            suggestions={[
              'What does the simulation expect to happen?',
              'Why does the model differ from the market?',
              'Which player projections are the most uncertain?',
            ]}
            placeholder="Ask about the simulation, the line, the players…"
          />
        </aside>
      </div>
    </div>
  )
}

function Hero({ game, entry, lg, home, away }) {
  const colors = matchupColors(away, home)
  const b = game?.baseline
  const pre = entry?.pregame
  const live = lg?.state === 'in'
  const final = !live && entry?.actual?.home_score != null
  const score = live ? { home: lg.home_score, away: lg.away_score } : final ? entry.actual : null
  const kickoff = game?.kickoff || entry?.kickoff
  const pHome = live && lg.live_sim ? lg.live_sim.home_win_prob : pre?.home_win_prob ?? b?.win_prob_home
  return (
    <section className="hero" style={{ '--away': colors.away, '--home': colors.home }}>
      <div className="hero-teams">
        <HeroTeam abbr={away} side="Away" pts={score ? score.away_score ?? score.away : null} />
        <div className="hero-mid">
          <StatusChip status={live ? 'live' : final ? 'final' : 'scheduled'} detail={live ? lg.detail : null} />
          <strong>
            {new Date(kickoff).toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' })}
          </strong>
          <span>{new Date(kickoff).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}</span>
          {game?.venue ? <span className="muted">{game.venue}</span> : null}
        </div>
        <HeroTeam abbr={home} side="Home" pts={score ? score.home_score ?? score.home : null} />
      </div>
      <div className="hero-stats">
        <Stat label="Market" value={spreadLabel(game?.market?.spread ?? b?.market_spread, home, away)} sub={game?.market?.total != null ? `O/U ${game.market.total}` : ''} />
        <Stat label="Baseline" value={b ? spreadLabel(b.model_spread, home, away) : '—'} sub={b ? `${home} ${pct(b.win_prob_home)}` : ''} />
        <Stat label="ML model" value={game?.ml ? spreadLabel(game.ml.model_spread, home, away) : '—'} sub={game?.ml ? `${home} ${pct(game.ml.win_prob_home)}` : ''} />
        <Stat label="Sim median" value={pre ? `${away} ${n0(pre.median?.away)} – ${n0(pre.median?.home)} ${home}` : '—'} sub={pre?.total?.p50 != null ? `total ${n0(pre.total.p50)}` : ''} />
        <Stat
          label="Stage 1 value test"
          value={b?.market_edge ? (b.is_value ? 'Passes' : 'No edge') : '—'}
          sub={b?.market_edge ? `${pct(b.market_edge.p_side_blend)} vs ${pct(b.market_edge.breakeven)} break-even` : ''}
        />
      </div>
      <WinBar away={away} home={home} pHome={pHome} label={live ? 'Live win chance' : 'Simulated win chance'} />
    </section>
  )
}

function HeroTeam({ abbr, side, pts }) {
  return (
    <div className="hero-team">
      <TeamLogo abbr={abbr} size={76} />
      <div>
        <em>{side}</em>
        <strong>{team(abbr).name || abbr}</strong>
      </div>
      {pts != null ? <span className="hero-score">{pts}</span> : null}
    </div>
  )
}

const Stat = ({ label, value, sub }) => (
  <div className="stat-tile">
    <em>{label}</em>
    <strong>{value}</strong>
    {sub ? <span>{sub}</span> : null}
  </div>
)
