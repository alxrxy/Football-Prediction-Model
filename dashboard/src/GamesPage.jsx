import { findGame, liveGame, useSims } from './simData.js'
import { kickoffLabel, shortDate, spreadLabel } from './format.js'
import { matchupColors, team } from './teams.js'
import { PageHead, StatusChip, TeamLogo, WinBar, n0 } from './ui.jsx'

// Every game of the week as a card, grouped by day. A card opens the game's
// full page: prediction, simulation and the Claude Q&A.

export default function GamesPage({ sport, feed, onOpen }) {
  const { data: sims } = useSims()
  const games = [...(sport.games || [])].sort((a, b) => (a.kickoff || '').localeCompare(b.kickoff || ''))
  const days = []
  for (const g of games) {
    const day = new Date(g.kickoff).toDateString()
    const last = days[days.length - 1]
    if (last && last.day === day) last.games.push(g)
    else days.push({ day, kickoff: g.kickoff, games: [g] })
  }
  const flagged = games.filter((g) => g.baseline?.is_value).length

  return (
    <div className="page">
      <PageHead
        title={sport.slate_label ? `${sport.slate_label}` : 'This week'}
        sub={`${sport.slate_end ? `${shortDate(sport.slate_date)} – ${shortDate(sport.slate_end)} · ` : ''}${games.length} games · ${flagged ? `${flagged} flagged by the Stage 1 test` : 'none pass the Stage 1 value test'} · click a game for its simulation and Q&A`}
      />
      {!games.length && <p className="muted">No games loaded. Run the pipeline, then python -m src.export_dashboard.</p>}
      {days.map((d) => (
        <section key={d.day} className="day">
          <h3 className="day-head">
            {new Date(d.kickoff).toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' })}
            <span className="muted"> · {d.games.length} {d.games.length === 1 ? 'game' : 'games'}</span>
          </h3>
          <div className="game-grid">
            {d.games.map((g) => (
              <GameCard
                key={g.game_id}
                game={g}
                sim={findGame(sims, g.game_id)}
                lg={liveGame(feed, g.game_id)}
                onOpen={onOpen}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}

function GameCard({ game, sim, lg, onOpen }) {
  const { home, away } = game
  const b = game.baseline
  const pre = sim?.pregame
  const live = lg?.state === 'in'
  const final = !live && (sim?.status === 'final' || sim?.actual?.home_score != null)
  const score = live
    ? { home: lg.home_score, away: lg.away_score }
    : final && sim?.actual
      ? { home: sim.actual.home_score, away: sim.actual.away_score }
      : null
  const colors = matchupColors(away, home)
  const spread = game.market?.spread ?? b?.market_spread
  const pHome = live && lg.live_sim ? lg.live_sim.home_win_prob : pre?.home_win_prob ?? b?.win_prob_home
  const open = () => onOpen(game.game_id)

  return (
    <article
      className={`game-card${live ? ' is-live' : ''}${final ? ' is-final' : ''}`}
      style={{ '--away': colors.away, '--home': colors.home }}
      role="button"
      tabIndex={0}
      onClick={open}
      onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), open())}
      aria-label={`${team(away).name} at ${team(home).name}`}
    >
      <div className="gc-top">
        <span className="gc-time">{kickoffLabel(game.kickoff)}</span>
        <StatusChip status={live ? 'live' : final ? 'final' : 'scheduled'} detail={live ? lg.detail : null} />
      </div>
      <div className="gc-teams">
        {[
          [away, score?.away, 'away'],
          [home, score?.home, 'home'],
        ].map(([abbr, pts, side]) => (
          <div className="gc-team" key={side}>
            <TeamLogo abbr={abbr} size={34} />
            <span className="gc-name">
              <strong>{team(abbr).nick || abbr}</strong>
              <em>{side === 'home' ? `${abbr} · home` : abbr}</em>
            </span>
            {pts != null ? <span className="gc-score">{pts}</span> : null}
          </div>
        ))}
      </div>
      <div className="gc-lines">
        <div>
          <em>Market</em>
          <strong>{spreadLabel(spread, home, away)}</strong>
          <span>{game.market?.total != null ? `O/U ${game.market.total}` : '—'}</span>
        </div>
        <div>
          <em>Model</em>
          <strong>{b ? spreadLabel(b.model_spread, home, away) : '—'}</strong>
          <span>{game.ml ? `ML ${spreadLabel(game.ml.model_spread, home, away)}` : ''}</span>
        </div>
        <div>
          <em>Sim final</em>
          <strong>{pre ? `${n0(pre.median?.away)}–${n0(pre.median?.home)}` : '—'}</strong>
          <span>{pre?.total?.p50 != null ? `total ${n0(pre.total.p50)}` : 'not simulated'}</span>
        </div>
      </div>
      <WinBar away={away} home={home} pHome={pHome} label={live ? 'Live win chance' : 'Win chance'} />
      {b?.is_value ? <span className="tag flag">passes Stage 1 · unvalidated</span> : null}
      {game.known_issue ? <span className="tag flag">known issue · treat with caution</span> : null}
    </article>
  )
}
