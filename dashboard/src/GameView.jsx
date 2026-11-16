import GameDetail, { WhyBox } from './GameDetail.jsx'
import GameQA from './GameQA.jsx'
import ScenarioPanel from './ScenarioPanel.jsx'
import SimDetail from './SimDetail.jsx'
import { liveGame, useSimEntry } from './simData.js'
import { spreadLabel } from './format.js'
import { matchupColors, team } from './teams.js'
import { StatusChip, TeamLogo, WinBar, n0, pct } from './ui.jsx'
import { UNVALIDATED_TEXT, flagTrust, labelled, trustTitle } from './flagTrust.js'

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
  const trust = flagTrust(sport.results)

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
      <Hero game={heroGame} entry={entry} lg={lg} home={home} away={away} trust={trust} />
      {week && !game ? (
        <p className="muted small">
          From the week {week.week} archive: model and market numbers are the last ones made before kickoff.
        </p>
      ) : null}
      <div className="split">
        <div className="split-main">
          {game?.preliminary ? <div className="caveat preliminary-notice">{game.preliminary}</div> : null}
          {game?.known_issue ? <div className="caveat">{game.known_issue}</div> : null}
          {game?.board?.tier ? <BoardPanel board={game.board} /> : null}
          {game ? <ScenarioPanel gameId={gameId} /> : null}
          {game ? <WhyBox explanation={game.explanation} /> : null}
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

function Hero({ game, entry, lg, home, away, trust }) {
  const colors = matchupColors(away, home)
  const b = game?.baseline
  const pre = entry?.pregame
  const live = lg?.state === 'in'
  const final = !live && entry?.actual?.home_score != null
  const score = live ? { home: lg.home_score, away: lg.away_score } : final ? entry.actual : null
  const kickoff = game?.kickoff || entry?.kickoff
  const pHome = live && lg.live_sim ? lg.live_sim.home_win_prob : pre?.home_win_prob ?? b?.win_prob_home
  const unvalidated = b?.is_value && labelled(trust)
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
          value={b?.market_edge ? (b.is_value ? (unvalidated ? 'Flagged · unvalidated' : 'Passes') : 'No edge') : b ? 'Not run' : '—'}
          // Predictions made before the test existed (2026-09-15) have no
          // market_edge; say so instead of looking like missing data.
          sub={
            b?.market_edge
              ? `${pct(b.market_edge.p_side_blend)} vs ${pct(b.market_edge.breakeven)} break-even`
              : b
                ? `predates the test${b.is_value ? ' · flagged by the earlier edge rule' : ''}`
                : ''
          }
        />
      </div>
      <WinBar away={away} home={home} pHome={pHome} label={live ? 'Live win chance' : 'Simulated win chance'} />
      {unvalidated && (
        <p className="trust-note">
          <b>Flag {UNVALIDATED_TEXT}.</b> {trustTitle(trust)}
        </p>
      )}
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


// Week-10 final board (display only; calibration/board_wk10.py). Tier rules and P82 are in calibration-log.md.
function BoardPanel({ board }) {
  const sh = board.shadow
  const f = (x) => (x == null ? '—' : `${x > 0 ? '+' : ''}${Number(x).toFixed(1)}`)
  return (
    <div className="card board-panel">
      <h3>
        Final board · <span className={`tag tier tier-${board.tier.toLowerCase()}`}>{board.tier} confidence</span>{' '}
        <span className="muted small">{board.label}</span>
      </h3>
      <p className="small">
        Baseline (headline) {f(board.baseline_margin_home)} · ML {f(board.ml_margin_home)} · sim home win{' '}
        {board.sim_home_wp != null ? `${Math.round(board.sim_home_wp * 100)}%` : '—'} · market {board.market_spread_home} / O/U{' '}
        {board.market_total ?? '—'} · model − market {f(board.model_vs_market)} (home margins)
      </p>
      <p className="small">
        Injury charge totals:{' '}
        {Object.entries(board.injury_total || {}).map(([t, v]) => `${t} −${Number(v).toFixed(2)}`).join(' · ')}
      </p>
      <p className="small"><strong>Tier:</strong> {(board.tier_reasons || []).join('; ')}</p>
      {sh ? (
        <div className="caveat">
          <strong>P82 shadow, UNVALIDATED (not the headline):</strong> headline {f(sh.headline_margin_home)} → shadow{' '}
          {f(sh.shadow_margin_home)} ({f(sh.difference)}).
          <ul>
            {sh.teams.map((t) => (
              <li key={t.team}>
                {t.team} {t.expected_starter.name}: {t.expected_starter.dropbacks_2025_26} dropbacks 2025-26 (
                {t.expected_starter.career_dropbacks_2015_26} career){t.low_confidence ? ' · LOW CONFIDENCE (<200 career dropbacks)' : ''};
                shrunk EPA/db {t.expected_starter.epa_db_shrunk}; vs usual {f(t.pts_vs_usual)} pts, vs replacement{' '}
                {f(t.pts_vs_replacement)} pts; flat charge in headline {Number(t.flat_qb_charge_in_headline).toFixed(2)}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {board.notes ? (
        <ul className="small">
          {Object.entries(board.notes).map(([k, v]) => (
            <li key={k}><strong>{k}:</strong> {v}</li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
