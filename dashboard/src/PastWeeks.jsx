import { useEffect, useState } from 'react'
import { loadArchiveIndex } from './simData.js'
import { spreadLabel } from './format.js'
import { PageHead, TeamLogo, n0, pct } from './ui.jsx'

// Finished weeks, from sims_archive/index.json (python -m src.export_sims):
// for every game, the pregame simulation and model numbers next to the final.
// Each matchup links to the full game view, which shows the pregame-vs-actual
// breakdown player by player.

const margin = (m, home, away) => {
  if (m == null) return '—'
  const r = Math.round(m * 10) / 10
  return r > 0 ? `${home} by ${r}` : r < 0 ? `${away} by ${-r}` : 'even'
}

// Graded only on simulations made before kickoff, the same rule as the record.
function summary(games) {
  const graded = games.filter((g) => g.simulated && !g.after_kickoff && g.home_score != null)
  const late = games.filter((g) => g.simulated && g.after_kickoff).length
  const called = graded.filter((g) => g.sim_home_win != null && g.home_score !== g.away_score)
  const right = called.filter((g) => (g.sim_home_win > 0.5) === (g.home_score > g.away_score)).length
  const misses = graded
    .filter((g) => g.sim_margin_home != null)
    .map((g) => Math.abs(g.home_score - g.away_score - g.sim_margin_home))
  const avg = misses.length ? misses.reduce((a, b) => a + b, 0) / misses.length : null
  return { graded: graded.length, called: called.length, right, avg, late }
}

export default function PastWeeks() {
  const [index, setIndex] = useState(null)
  useEffect(() => {
    let alive = true
    loadArchiveIndex().then((d) => alive && setIndex(d))
    return () => {
      alive = false
    }
  }, [])
  const weeks = index?.weeks || []

  return (
    <div className="page">
      <PageHead
        title="Past weeks"
        sub="Every finished week: what the simulation and the models expected, next to what happened. Open a game for the player-by-player projections beside each player's actual stats."
      />
      {!index ? (
        <p className="muted">Loading…</p>
      ) : !weeks.length ? (
        <div className="card empty">
          <strong>No finished weeks archived yet</strong>
          <p className="muted">
            A week is archived by <code>python -m src.export_sims</code> once its last game is over.
          </p>
        </div>
      ) : (
        <section className="weeks">
          {weeks.map((w, i) => (
            <Week key={w.file} w={w} open={i === 0} />
          ))}
        </section>
      )}
    </div>
  )
}

function Week({ w, open }) {
  const s = summary(w.games)
  return (
    <details className="week" open={open}>
      <summary>
        <span className="week-name">Week {w.week}</span>
        <span className="muted small">
          {w.season} · {w.games.length} games
          {s.graded
            ? ` · simulation picked ${s.right}/${s.called} winners · average margin miss ${s.avg == null ? '—' : s.avg.toFixed(1)} pts`
            : ' · no simulations made before kickoff to grade'}
          {s.late ? ` · ${s.late} simulation${s.late === 1 ? '' : 's'} run after kickoff, marked and not graded` : ''}
        </span>
      </summary>
      <div className="table-wrap">
        <table className="slate">
          <thead>
            <tr className="group-head">
              <th colSpan={3} />
              <th colSpan={3}>Simulation (median)</th>
              <th colSpan={3}>Spreads before kickoff</th>
            </tr>
            <tr>
              <th>Kick</th>
              <th>Matchup</th>
              <th className="num">Final</th>
              <th className="num">Score</th>
              <th>Margin → actual</th>
              <th className="num">Home win</th>
              <th className="num">Baseline</th>
              <th className="num">ML</th>
              <th className="num">Market</th>
            </tr>
          </thead>
          <tbody>
            {w.games.map((g) => (
              <Row key={g.game_id} g={g} />
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}

function Row({ g }) {
  const { home, away } = g
  const final = g.home_score != null
  const actual = final ? g.home_score - g.away_score : null
  const miss = final && g.sim_margin_home != null ? actual - g.sim_margin_home : null
  const hit =
    final && g.sim_home_win != null && actual !== 0 ? (g.sim_home_win > 0.5) === actual > 0 : null
  return (
    <tr>
      <td className="muted">
        {g.kickoff ? new Date(g.kickoff).toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' }) : ''}
      </td>
      <td>
        <a href={`#/nfl/game/${encodeURIComponent(g.game_id)}`} className="kp-name">
          <TeamLogo abbr={away} size={18} /> {away} @ <TeamLogo abbr={home} size={18} /> {home}
        </a>
        {g.after_kickoff ? <em className="sub"> · simulation run after kickoff, not graded</em> : null}
      </td>
      <td className="num">{final ? `${g.away_score}–${g.home_score}` : '—'}</td>
      <td className="num">{g.simulated ? `${n0(g.sim_away)}–${n0(g.sim_home)}` : '—'}</td>
      <td>
        {g.simulated ? (
          <>
            {margin(g.sim_margin_home, home, away)} → {final ? margin(actual, home, away) : '—'}
            {miss != null ? <span className="muted"> ({miss > 0 ? '+' : ''}{Math.round(miss)})</span> : null}
          </>
        ) : (
          <span className="muted">not simulated</span>
        )}
      </td>
      <td className="num">
        {g.sim_home_win != null ? pct(g.sim_home_win) : '—'}
        {hit == null ? null : hit ? ' ✓' : ' ✗'}
      </td>
      <td className="num">{g.baseline_spread != null ? spreadLabel(g.baseline_spread, home, away) : '—'}</td>
      <td className="num">{g.ml_spread != null ? spreadLabel(g.ml_spread, home, away) : '—'}</td>
      <td className="num">{g.market_spread != null ? spreadLabel(g.market_spread, home, away) : '—'}</td>
    </tr>
  )
}
