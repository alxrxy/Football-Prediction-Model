import { useLive } from './simData.js'
import GameQA from './GameQA.jsx'
import './claude.css'

// Games in progress: the live-resume simulation's current read (re-projected
// from the real score, clock and field position every poll), with a Q&A box
// that answers from that live state. Reads live.json, which the live tracker
// rewrites every poll: python -m src.live_tracker

const pct = (v) => (v == null ? '—' : `${Math.round(v * 100)}%`)
const n0 = (v) => (v == null ? '—' : Math.round(v))
const by = (m, home, away) =>
  m == null ? '—' : Math.abs(m) < 0.5 ? 'even' : `${m > 0 ? home : away} by ${Math.abs(m).toFixed(1)}`
const STALE_MS = 15 * 60 * 1000

export default function LiveGames() {
  const feed = useLive(true)
  const live = (feed?.games || []).filter((g) => g.state === 'in')
  const updated = feed?.generated_at ? new Date(feed.generated_at) : null
  const stale = updated && Date.now() - updated.getTime() > STALE_MS

  return (
    <section className="live-games">
      <h2>
        Live games
        {live.length ? <span className="muted"> · {live.length} in progress</span> : null}
      </h2>
      {!feed ? (
        <p className="muted">
          No live feed. On game day, start the tracker with <code>python -m src.live_tracker</code>; games in progress
          appear here with the live model and a Q&amp;A box.
        </p>
      ) : !live.length ? (
        <p className="muted">
          No games in progress. The live tracker last updated{' '}
          {updated ? updated.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '—'}
          {stale ? ', so it may not be running' : ''}.
        </p>
      ) : (
        live.map((g) => <LiveCard key={g.game_id} g={g} stale={stale} />)
      )}
    </section>
  )
}

function LiveCard({ g, stale }) {
  const s = g.live_sim
  const pre = g.pregame || {}
  return (
    <div className="live-card">
      <div className="live-score">
        <strong>
          {g.away} {g.away_score} – {g.home_score} {g.home}
        </strong>
        <span className="sim-status live">Live · {g.detail}</span>
        {g.down_distance ? <span className="muted small">{g.down_distance}</span> : null}
        {stale ? <span className="qa-error">feed stale</span> : null}
      </div>
      {s ? (
        <div className="sim-tiles">
          <Tile label={`${g.home} win chance now`} value={pct(s.home_win_prob)} sub={`pregame ${pct(s.pregame_win_prob_home)}`} />
          <Tile label="Projected final (median)" value={`${g.away} ${n0(s.median_away_points)} – ${n0(s.median_home_points)} ${g.home}`} />
          <Tile
            label="Projected margin"
            value={by(s.mean_margin_home, g.home, g.away)}
            sub={`80%: ${g.home} ${n0(s.margin_80_low)} to ${n0(s.margin_80_high)} · pregame ${by(s.pregame_margin_home, g.home, g.away)}`}
          />
          <Tile label="Projected total" value={n0(s.total_median)} sub={`80%: ${n0(s.total_80_low)}–${n0(s.total_80_high)}`} />
        </div>
      ) : (
        <p className="muted small">
          No live re-projection yet for this game{pre.home_win_prob != null ? `; pregame ${g.home} ${pct(pre.home_win_prob)}` : ''}.
        </p>
      )}
      <GameQA
        gameId={g.game_id}
        title="Ask how this game is playing out"
        suggestions={['Why has the win chance moved since kickoff?', 'Who is running ahead of their projection?']}
      />
    </div>
  )
}

const Tile = ({ label, value, sub }) => (
  <div className="sim-tile">
    <em>{label}</em>
    <strong>{value}</strong>
    {sub ? <span>{sub}</span> : null}
  </div>
)
