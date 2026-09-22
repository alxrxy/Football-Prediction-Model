// Does disagreeing with the line pay? The flagged picks' record, then ATS by
// the size of the edge, season-wide beside each week. The weeks sit side by
// side because the question is whether a pattern repeats: in weeks 1 and 2 of
// 2026 the baseline did worse the more it disagreed with the market, and one
// week of that is noise while five in a row is not.

const MODEL_LABELS = {
  'baseline-v1': 'Baseline',
  'ml-v1': 'ML model',
}

const BREAK_EVEN = 0.524

function record(r) {
  if (!r) return '—'
  const n = r.win + r.loss + r.push
  if (!n) return '—'
  return `${r.win}-${r.loss}${r.push ? `-${r.push}` : ''}`
}

function rateOf(r) {
  const decided = r ? r.win + r.loss : 0
  return decided ? r.win / decided : null
}

function tone(r) {
  const rate = rateOf(r)
  return rate === null ? 'muted' : rate > BREAK_EVEN ? 'good' : 'bad'
}

function pct(r) {
  const rate = rateOf(r)
  return rate === null ? '' : `${(rate * 100).toFixed(0)}%`
}

function Stat({ label, r, note }) {
  return (
    <div className="total-stat">
      <em>{label}</em>
      <strong className={tone(r) === 'muted' ? '' : tone(r)}>{record(r)}</strong>
      <span>{note ?? (rateOf(r) === null ? 'none yet' : `${pct(r)} · 52.4% breaks even`)}</span>
    </div>
  )
}

const FLAGS_SHOWN = 6

function FlagList({ games }) {
  return (
    <ul className="flag-list">
      {games.map((g) => (
        <li key={g.game_id}>
          <span className="muted">Wk {g.week}</span>
          <span>
            {g.away} @ {g.home}
          </span>
          <span className="muted">
            took {g.lean} · edge {Math.abs(g.edge).toFixed(1)}
          </span>
          <b className={`result ${g.ats}`}>{g.ats}</b>
        </li>
      ))}
    </ul>
  )
}

function ModelEdges({ version, season, weeks }) {
  // Newest first; the season's older flags fold away once there are many.
  const flaggedGames = [...(season.flagged_games || [])].reverse()
  const recent = flaggedGames.slice(0, FLAGS_SHOWN)
  const older = flaggedGames.slice(FLAGS_SHOWN)
  return (
    <div className="total-card edge-card">
      <h4>{MODEL_LABELS[version] || version}</h4>
      <div className="total-pair">
        <Stat label="Flagged picks" r={season.flagged}
              note={flaggedGames.length ? undefined : 'no pick flagged yet'} />
        <Stat label="Not flagged" r={season.unflagged} />
      </div>

      <div className="table-wrap">
        <table className="micro edge-table">
          <thead>
            <tr>
              <th>|Edge|</th>
              <th className="num">Season</th>
              {weeks.map((w) => (
                <th className="num" key={w.week}>Wk {w.week}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {season.by_edge.map((row, i) => (
              <tr key={row.min}>
                <td>{row.min === 0 ? 'all picks' : `≥ ${row.min} pts`}</td>
                <td className={`num ${tone(row)}`}>
                  {record(row)} <small>{pct(row)}</small>
                </td>
                {weeks.map((w) => {
                  const cell = w.models?.[version]?.edges?.by_edge?.[i]
                  return (
                    <td className={`num ${tone(cell)}`} key={w.week}>{record(cell)}</td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {recent.length > 0 && (
        <>
          <FlagList games={recent} />
          {older.length > 0 && (
            <details className="flag-more">
              <summary className="muted small">
                {older.length} earlier flagged pick{older.length === 1 ? '' : 's'}
              </summary>
              <FlagList games={older} />
            </details>
          )}
        </>
      )}
    </div>
  )
}

export default function EdgeRecord({ results }) {
  const models = Object.entries(results?.models || {}).filter(([, m]) => m.edges)
  if (!models.length) return null
  const weeks = results?.weeks || []

  return (
    <section className="totals edge-record">
      <h3>
        Flagged edges &amp; ATS by edge size
        <span className="muted">season, then week by week</span>
      </h3>
      <div className="total-grid">
        {models.map(([version, m]) => (
          <ModelEdges key={version} version={version} season={m.edges} weeks={weeks} />
        ))}
      </div>
      <p className="muted small">
        Edge is the model&rsquo;s spread minus the stored line, in points; each
        row counts every pick at least that far from the line, pushes included.
        If disagreeing with the market pays, the lower rows should beat the top
        one. A few dozen games cannot show that either way, so read the week
        columns for whether a pattern repeats, not the size of any one record.
      </p>
    </section>
  )
}
