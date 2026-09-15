import { useState } from 'react'
import { findGame, liveGame, useLive, useSims } from './simData.js'
import './sims.css'

// The game view behind an NFL row: projected score and its distribution,
// TD/FG counts, likely scorers and every player's projected line. Three
// versions of the same thing: the pregame projection (fixed at kickoff), the
// live re-projection while the game is on (refreshed every poll), and, once
// it's over, the pregame projection with the actual result beside it.

const NFL_ID = /^\d{4}_\d{2}_/
const n0 = (v) => (v == null || Number.isNaN(Number(v)) ? '—' : `${Math.round(v)}`)
const sgn = (v) => (v == null ? '—' : `${v > 0 ? '+' : ''}${Math.round(v)}`)
const pct = (v) => (v == null ? '—' : `${Math.round(v * 100)}%`)
// Yards and other large values read as whole numbers; small counts keep a
// half where the median genuinely falls between two.
const num = (v) =>
  v == null ? '—' : Math.abs(v) >= 10 ? `${Math.round(v)}` : Number.isInteger(v) ? `${v}` : v.toFixed(1)
const by = (m, home, away) =>
  m == null ? '—' : Math.abs(m) < 0.05 ? "pick'em" : `${m > 0 ? home : away} by ${Math.abs(m).toFixed(1)}`

const band = (q, v) => (v >= q.p25 && v <= q.p75 ? 'in50' : v >= q.p10 && v <= q.p90 ? 'in80' : 'out')
const BAND_LABEL = { in50: 'inside 50%', in80: 'inside 80%', out: 'outside 80%' }

// Both sources reduced to one shape before rendering.
function fromPregame(p) {
  return {
    kind: 'pregame',
    nSims: p.n_sims,
    winHome: p.home_win_prob,
    winAway: p.away_win_prob,
    tie: p.tie_prob,
    meanMargin: p.mean?.home != null ? p.mean.home - p.mean.away : null,
    margin: p.margin,
    total: p.total,
    homePts: p.home_points,
    awayPts: p.away_points,
    median: p.median,
    modal: p.modal,
    topScores: p.top_scores,
    td: p.td,
    fg: p.fg,
    scorers: p.scorers,
    box: p.box_score,
  }
}

function fromLive(ls) {
  const pair = (arr, modes) =>
    arr ? { home: arr[0], away: arr[1], home_mode: modes?.[0], away_mode: modes?.[1] } : null
  return {
    kind: 'live',
    nSims: ls.n_sims,
    state: ls.start_state,
    minutesLeft: ls.minutes_left,
    winHome: ls.home_win_prob,
    winAway: ls.away_win_prob,
    tie: ls.tie_prob,
    meanMargin: ls.mean_margin_home,
    margin: ls.margin,
    total: ls.total,
    homePts: ls.home_points,
    awayPts: ls.away_points,
    median: { home: ls.median_home_points, away: ls.median_away_points },
    modal: { home: ls.modal_home_points, away: ls.modal_away_points, prob: ls.modal_score_prob, tied: ls.scores_tied_with_mode },
    topScores: ls.top_scores,
    td: pair(ls.td, ls.td_mode),
    fg: pair(ls.fg, ls.fg_mode),
    soFar: { td: ls.td_so_far, fg: ls.fg_so_far },
    scorers: ls.scorers,
    box: ls.box_score,
  }
}

export default function SimDetail({ gameId }) {
  const { data, error } = useSims()
  const entry = findGame(data, gameId)
  const feed = useLive(Boolean(entry) && entry.status !== 'final')
  const [choice, setChoice] = useState(null)

  if (!NFL_ID.test(gameId || '')) return null
  if (error) {
    return (
      <Shell>
        <p className="muted">
          Couldn&rsquo;t load <code>sims.json</code> ({error}). Generate it with{' '}
          <code>python -m src.export_sims</code>.
        </p>
      </Shell>
    )
  }
  if (!data) return <Shell><p className="muted">Loading simulations…</p></Shell>
  if (!entry) {
    return (
      <Shell>
        <p className="muted">
          This game isn&rsquo;t in <code>sims.json</code> yet. Simulate its slate with{' '}
          <code>python -m src.simulate_nfl --date …</code>, then run{' '}
          <code>python -m src.export_sims</code>.
        </p>
      </Shell>
    )
  }

  const lg = liveGame(feed, gameId)
  const status = lg?.state === 'in' ? 'live' : lg?.state === 'post' ? 'final' : entry.status
  const live = lg?.state === 'in' && lg.live_sim ? fromLive(lg.live_sim) : null
  const pre = entry.pregame ? fromPregame(entry.pregame) : null
  const actual = status === 'final' ? entry.actual : null
  const options = []
  if (live) options.push(['live', 'Live model now'])
  if (pre) options.push(['pregame', actual ? 'Pregame vs actual' : 'Pregame projection'])
  const view = options.some(([k]) => k === choice) ? choice : options[0]?.[0]
  const proj = view === 'live' ? live : pre
  const { home, away } = entry

  return (
    <Shell status={status} detail={lg?.detail || entry.detail} options={options} view={view} setView={setChoice}>
      <p className="muted small">{subtitle(view, entry, lg, live)}</p>
      {!proj ? (
        <p className="muted">
          No projection stored for this game. Run <code>python -m src.simulate_nfl --game {gameId}</code>.
        </p>
      ) : (
        <>
          <Tiles proj={proj} home={home} away={away} actual={actual} now={view === 'live' ? lg : null} />
          <Distribution proj={proj} home={home} away={away} actual={actual} />
          <Counts proj={proj} home={home} away={away} actual={actual} />
          <Scorers proj={proj} home={home} away={away} actual={actual} />
          <Props proj={proj} home={home} away={away} actual={actual} />
        </>
      )}
    </Shell>
  )
}

function subtitle(view, entry, lg, live) {
  if (view === 'live') {
    const s = live.state || {}
    return `Live model: re-simulated ${live.nSims?.toLocaleString()} times from ${s.description || 'the current state'} (${lg.detail}${live.minutesLeft != null ? `, ${Math.round(live.minutesLeft)} min left` : ''}), same engine and team strengths as the pregame projection. Updates every poll; the pregame view never changes after kickoff.`
  }
  const p = entry.pregame
  if (!p) return ''
  const when = p.generated_at
    ? new Date(p.generated_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
    : '?'
  return `Pregame projection: ${p.n_sims?.toLocaleString()} simulations centred on the baseline margin (${by(p.anchor_margin_home, entry.home, entry.away)}), run ${when}${p.after_kickoff ? ', after kickoff but from inputs published before it' : ''}.`
}

function Shell({ status, detail, options = [], view, setView, children }) {
  return (
    <section className="sim">
      <div className="sim-head">
        <h4>Game simulation</h4>
        {status && (
          <span className={`sim-status ${status}`}>
            {status === 'live' ? `Live · ${detail || ''}` : status === 'final' ? 'Final' : 'Scheduled'}
          </span>
        )}
        {options.length > 1 && (
          <div className="segmented">
            {options.map(([k, label]) => (
              <button
                key={k}
                className={k === view ? 'active' : ''}
                onClick={(e) => {
                  e.stopPropagation()
                  setView(k)
                }}
              >
                {label}
              </button>
            ))}
          </div>
        )}
      </div>
      {children}
    </section>
  )
}

const Tile = ({ label, value, sub, cls = '' }) => (
  <div className={`sim-tile ${cls}`}>
    <em>{label}</em>
    <strong>{value}</strong>
    {sub ? <span>{sub}</span> : null}
  </div>
)

function Tiles({ proj, home, away, actual, now }) {
  const m = proj.margin
  const final = actual && actual.home_score != null
  return (
    <div className="sim-tiles">
      {final && (
        <Tile
          cls="actual"
          label="Final score"
          value={`${away} ${actual.away_score} – ${actual.home_score} ${home}`}
          sub={m ? `margin ${BAND_LABEL[band(m, actual.home_score - actual.away_score)]} of the projection` : ''}
        />
      )}
      {now && <Tile cls="actual" label="Score now" value={`${away} ${now.away_score} – ${now.home_score} ${home}`} sub={now.detail} />}
      <Tile label="Projected final (median)" value={`${away} ${n0(proj.median?.away)} – ${n0(proj.median?.home)} ${home}`} />
      {proj.modal?.prob != null && (
        <Tile
          label="Most likely exact final"
          value={`${away} ${proj.modal.away} – ${proj.modal.home} ${home}`}
          sub={`${(proj.modal.prob * 100).toFixed(1)}% of simulations${proj.modal.tied ? `; within noise of ${proj.modal.tied} others` : ''}`}
        />
      )}
      <Tile label={`${home} win probability`} value={pct(proj.winHome)} sub={`${away} ${pct(proj.winAway)} · tie ${pct(proj.tie)}`} />
      <Tile
        label="Projected margin"
        value={by(proj.meanMargin, home, away)}
        sub={m ? `50%: ${home} ${sgn(m.p25)} to ${sgn(m.p75)} · 80%: ${sgn(m.p10)} to ${sgn(m.p90)}` : ''}
      />
      <Tile
        label="Total points"
        value={n0(proj.total?.p50)}
        sub={proj.total ? `50%: ${n0(proj.total.p25)}–${n0(proj.total.p75)} · 80%: ${n0(proj.total.p10)}–${n0(proj.total.p90)}` : ''}
      />
    </div>
  )
}

// Fixed domains, so bars read the same from game to game.
const DOMAINS = { points: [0, 50], margin: [-35, 35], total: [15, 80] }

function Distribution({ proj, home, away, actual }) {
  const rows = [
    [`${away} points`, proj.awayPts, DOMAINS.points, actual?.away_score, n0],
    [`${home} points`, proj.homePts, DOMAINS.points, actual?.home_score, n0],
    [`Margin (${home})`, proj.margin, DOMAINS.margin, actual ? actual.home_score - actual.away_score : null, sgn],
    ['Total', proj.total, DOMAINS.total, actual ? actual.home_score + actual.away_score : null, n0],
  ].filter((r) => r[1])
  if (!rows.length) return null
  const hasActual = rows.some((r) => r[3] != null)
  return (
    <div className="sim-block">
      <h4>Score distribution</h4>
      {rows.map(([label, q, domain, act, fmt]) => (
        <RangeRow key={label} label={label} q={q} domain={domain} actual={act ?? null} fmt={fmt} />
      ))}
      <div className="range-legend">
        <span><i className="k80" />middle 80% of simulations</span>
        <span><i className="k50" />middle 50%</span>
        <span><i className="kmed" />median</span>
        {hasActual && <span><i className="kact" />actual</span>}
      </div>
      {proj.topScores?.length ? (
        <p className="muted small">
          Most common exact finals:{' '}
          {proj.topScores
            .slice(0, 5)
            .map((t) => `${away} ${t.away}–${t.home} ${home} (${(t.prob * 100).toFixed(1)}%)`)
            .join(' · ')}
        </p>
      ) : null}
    </div>
  )
}

function RangeRow({ label, q, domain, actual, fmt }) {
  const [lo, hi] = domain
  const x = (v) => Math.max(0, Math.min(100, ((v - lo) / (hi - lo)) * 100))
  const describe = `${label}: median ${fmt(q.p50)}, middle 50% ${fmt(q.p25)} to ${fmt(q.p75)}, middle 80% ${fmt(q.p10)} to ${fmt(q.p90)}${actual != null ? `, actual ${fmt(actual)}` : ''}`
  return (
    <div className="range-row">
      <span className="range-label">{label}</span>
      <div className="range-track" role="img" aria-label={describe}>
        {lo < 0 && <span className="zero" style={{ left: `${x(0)}%` }} />}
        <span className="band80" style={{ left: `${x(q.p10)}%`, width: `${x(q.p90) - x(q.p10)}%` }} />
        <span className="band50" style={{ left: `${x(q.p25)}%`, width: `${x(q.p75) - x(q.p25)}%` }} />
        <span className="median" style={{ left: `${x(q.p50)}%` }} />
        {actual != null && <span className="actual-mark" style={{ left: `${x(actual)}%` }} />}
      </div>
      <span className="range-text">
        {fmt(q.p50)}
        <em>50% {fmt(q.p25)} to {fmt(q.p75)} · 80% {fmt(q.p10)} to {fmt(q.p90)}</em>
        {actual != null && <b> · actual {fmt(actual)} ({BAND_LABEL[band(q, actual)]})</b>}
      </span>
    </div>
  )
}

function Counts({ proj, home, away, actual }) {
  const t = proj.td
  const f = proj.fg
  if (!t?.home && !f?.home) return null
  return (
    <div className="sim-block">
      <h4>Touchdowns and field goals</h4>
      <p className="muted small">
        Chance of each final count{proj.kind === 'live' ? ', including what has already been scored' : ''}. The most
        likely count is outlined{actual ? '; the actual count is marked' : ''}.
      </p>
      <CountRow label={`${away} TDs`} dist={t?.away} mode={t?.away_mode} actual={actual?.td?.away} soFar={proj.soFar?.td?.[1]} />
      <CountRow label={`${home} TDs`} dist={t?.home} mode={t?.home_mode} actual={actual?.td?.home} soFar={proj.soFar?.td?.[0]} />
      <CountRow label={`${away} FGs`} dist={f?.away} mode={f?.away_mode} actual={actual?.fg?.away} soFar={proj.soFar?.fg?.[1]} />
      <CountRow label={`${home} FGs`} dist={f?.home} mode={f?.home_mode} actual={actual?.fg?.home} soFar={proj.soFar?.fg?.[0]} />
    </div>
  )
}

function CountRow({ label, dist, mode, actual, soFar }) {
  if (!dist) return null
  const cells = [0, 1, 2, 3, 4].map((k) => [String(k), dist[String(k)] ?? 0])
  cells.push(['5+', Object.entries(dist).reduce((s, [k, p]) => (parseInt(k, 10) >= 5 ? s + p : s), 0)])
  const max = Math.max(0.01, ...cells.map((c) => c[1]))
  const hit = (k, v) => v != null && (k === '5+' ? v >= 5 : Number(k) === v)
  return (
    <div className="count-row">
      <span className="count-label">{label}</span>
      {cells.map(([k, p]) => (
        <span
          key={k}
          className={`count-cell${hit(k, mode) ? ' mode' : ''}${hit(k, actual) ? ' actual' : ''}`}
          title={`${k}: ${pct(p)} of simulations`}
        >
          <span className="count-bar" style={{ height: `${Math.round((p / max) * 100)}%` }} />
          {hit(k, actual) && <i>actual</i>}
          <b>{k}</b>
          <em>{pct(p)}</em>
        </span>
      ))}
      <span className="count-note">
        most likely {mode ?? '—'}
        {soFar != null ? ` · ${soFar} so far` : ''}
        {actual != null ? ` · actual ${actual}` : ''}
      </span>
    </div>
  )
}

function Scorers({ proj, home, away, actual }) {
  const sc = proj.scorers
  if (!sc) return null
  const live = proj.kind === 'live'
  const list = (side, team) => (
    <div>
      <h5>{team}</h5>
      <ul className="sim-scorers">
        {(sc[side] || []).slice(0, 8).map((p) => (
          <li key={p.player}>
            <span className="who">
              {p.player}
              <em>{p.position || ''}{p.depth_rank || ''}</em>
            </span>
            <span className="num">{pct(live ? p.td_from_here : p.anytime_td)}</span>
            {live && p.tds_so_far ? <span className="tagline hit">{p.tds_so_far} TD so far</span> : null}
            {actual && p.actual_tds != null ? (
              <span className={`tagline${p.actual_tds ? ' hit' : ''}`}>
                {p.actual_tds ? `scored ${p.actual_tds}` : 'did not score'}
              </span>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  )
  return (
    <div className="sim-block">
      <h4>
        Most likely touchdown scorers <span className="lowconf">low confidence</span>
      </h4>
      <p className="muted small">
        {live ? 'Chance to score a touchdown from here on.' : 'Chance to score at least one touchdown.'} Based on usage
        share, like the player projections below.
      </p>
      <div className="sim-cols">
        {list('away', away)}
        {list('home', home)}
      </div>
      {actual?.scorers && (
        <p className="muted small">
          Actual touchdown scorers: {away} {actual.scorers.away?.join(', ') || 'none'} · {home}{' '}
          {actual.scorers.home?.join(', ') || 'none'}
        </p>
      )}
    </div>
  )
}

const SO_FAR_KEY = {
  passing: { att: 'pass_att', cmp: 'pass_cmp', yds: 'pass_yds', td: 'pass_td', int: 'pass_int' },
  rushing: { att: 'rush_att', yds: 'rush_yds', td: 'rush_td' },
  receiving: { tgt: 'tgt', rec: 'rec', yds: 'rec_yds', td: 'rec_td' },
}
const PROP_TABLES = [
  ['passing', 'Passing', [['cmp', 'Cmp'], ['att', 'Att'], ['yds', 'Yds'], ['td', 'TD'], ['int', 'INT']], 'att'],
  ['rushing', 'Rushing', [['att', 'Car'], ['yds', 'Yds'], ['td', 'TD']], 'att'],
  ['receiving', 'Receiving', [['tgt', 'Tgt'], ['rec', 'Rec'], ['yds', 'Yds'], ['td', 'TD']], 'tgt'],
]

function Props({ proj, home, away, actual }) {
  const box = proj.box
  return (
    <div className="sim-block">
      <h4>
        Player projections <span className="lowconf">lower confidence</span>
      </h4>
      {!box ? (
        <p className="muted">
          No player projections in this simulation. Re-run <code>python -m src.simulate_nfl</code> for this game.
        </p>
      ) : (
        <>
          <p className="caveat">{box.note} Treat these as rougher than the score and win projections above.</p>
          <p className="prop-key">
            Each cell: the median, then the middle 50% and middle 80% of simulations.
            {proj.kind === 'live' ? ' Live lines are projected finals: stats so far plus the simulated rest of the game.' : ''}
            {actual ? ' Last line: the actual result and where it fell.' : ''}
          </p>
          {[['away', away], ['home', home]].map(([side, team]) => (
            <TeamProps
              key={side}
              team={team}
              data={box[side]}
              live={proj.kind === 'live'}
              actual={Boolean(actual)}
              extra={actual?.unprojected?.[side]}
            />
          ))}
        </>
      )}
    </div>
  )
}

function TeamProps({ team, data, live, actual, extra }) {
  if (!data) return null
  const t = data.team || {}
  return (
    <div className="team-props">
      <h5>
        {team}
        <span className="muted">
          team medians: {n0(t.pass_yds?.median)} passing yds, {n0(t.rush_yds?.median)} rushing yds
        </span>
      </h5>
      {PROP_TABLES.map(([group, title, cols, sortKey]) => {
        // A table lists a player only with at least one attempt / target on
        // average; below that every cell is a zero and the row is noise.
        const rows = (data.players || [])
          .filter((p) => p[group] && (p[group][sortKey].mean >= 1 || p.actual?.[group]))
          .sort((a, b) => b[group][sortKey].mean - a[group][sortKey].mean)
        if (!rows.length) return null
        return (
          <div className="table-wrap" key={group}>
            <table className="micro props">
              <thead>
                <tr>
                  <th>{title}</th>
                  {cols.map(([k, label]) => (
                    <th key={k} className="num">{label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((p) => (
                  <tr key={p.player}>
                    <td className="who">
                      {p.player}
                      <em>{p.position || ''}{p.depth_rank || ''}</em>
                    </td>
                    {cols.map(([k]) => (
                      <StatCell
                        key={k}
                        q={p[group][k]}
                        actual={actual ? (p.actual ? p.actual[group]?.[k] ?? 0 : null) : null}
                        soFar={live ? p.so_far?.[SO_FAR_KEY[group][k]] ?? 0 : null}
                      />
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      })}
      {extra?.length ? (
        <p className="muted small">
          Recorded stats without a projection: {extra.map((e) => e.name).join(', ')}
        </p>
      ) : null}
    </div>
  )
}

function StatCell({ q, actual, soFar }) {
  if (!q) return <td className="num muted">—</td>
  return (
    <td className="num stat">
      <strong>{num(q.median)}</strong>
      <span className="r50">{num(q.p25)}–{num(q.p75)}</span>
      <span className="r80">{num(q.p10)}–{num(q.p90)}</span>
      {soFar != null && <span className="so-far">{soFar} so far</span>}
      {actual != null && (
        <span className="act">
          {actual} <i>{BAND_LABEL[band(q, actual)]}</i>
        </span>
      )}
    </td>
  )
}
