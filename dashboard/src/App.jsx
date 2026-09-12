import { useEffect, useState } from 'react'
import SlateTable from './SlateTable.jsx'
import BacktestPanel from './BacktestPanel.jsx'
import ResultsPanel from './ResultsPanel.jsx'
import { dateLabel } from './format.js'

export default function App() {
  const [payload, setPayload] = useState(null)
  const [error, setError] = useState(null)
  const [active, setActive] = useState(0)

  useEffect(() => {
    // A single-file export inlines the snapshot on window rather than shipping
    // a second file to fetch, so prefer it when present.
    if (window.__DASHBOARD_DATA__) {
      setPayload(window.__DASHBOARD_DATA__)
      return
    }
    // Otherwise read the sibling file. Relative path so a built bundle works
    // from any static host or subdirectory.
    fetch('./data.json')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(setPayload)
      .catch((e) => setError(e.message))
  }, [])

  if (error) {
    return (
      <div className="shell">
        <div className="panel">
          <h3>No data loaded</h3>
          <p className="muted">
            Could not read <code>data.json</code> ({error}). Generate it with:
          </p>
          <pre>python -m src.export_dashboard</pre>
        </div>
      </div>
    )
  }

  if (!payload) return <div className="shell loading">Loading slate…</div>

  const sport = payload.sports[active]
  const generated = new Date(payload.generated_at)

  return (
    <div className="shell">
      <header>
        <div>
          <h1>Football Predictor</h1>
          <p className="muted">
            Model line vs market line, with the evidence for whether the gap
            means anything.
          </p>
        </div>
        <div className="meta">
          <span>
            {payload.storage_backend} · {payload.model_version_baseline}
          </span>
          <span className="muted">
            generated{' '}
            {Number.isNaN(generated.getTime())
              ? '—'
              : generated.toLocaleString([], {
                  dateStyle: 'medium',
                  timeStyle: 'short',
                })}
          </span>
        </div>
      </header>

      <div className="tabs">
        {payload.sports.map((s, i) => (
          <button
            key={s.sport}
            className={i === active ? 'active' : ''}
            onClick={() => setActive(i)}
          >
            {s.label}
            <em>{s.games.length} games</em>
          </button>
        ))}
      </div>

      <div className="banner">
        Paper trading only. One slate is not enough signal to trust any edge, and
        the backtest below has not cleared the bar for calling one real.
      </div>

      <div className="layout">
        <main>
          <h2>
            {sport.label}
            <span className="muted"> · {dateLabel(sport.slate_date)}</span>
          </h2>
          {sport.games.length === 0 ? (
            <p className="muted">
              No games loaded for this slate. Run{' '}
              <code>python run_pipeline.py --sport {sport.sport}</code>.
            </p>
          ) : (
            <SlateTable games={sport.games} />
          )}
        </main>

        <aside>
          <ResultsPanel results={sport.results} />
          <BacktestPanel
            backtest={sport.backtest}
            calibration={sport.calibration}
          />
          <div className="panel">
            <h3>Injury coverage</h3>
            <div className="stat-row">
              <div>
                <span className="stat">{sport.injury_coverage.teams_with_data}</span>
                <em>teams with data</em>
              </div>
              <div>
                <span className="stat">{sport.injury_coverage.total_rows}</span>
                <em>players listed</em>
              </div>
            </div>
            <p className="muted small">
              {sport.sport === 'nfl'
                ? 'The NFL mandates a weekly report, so coverage is effectively complete and the injury adjustment is meaningful.'
                : 'College football mandates no injury report. Coverage is a handful of teams at best, so most games get no injury adjustment — which is not the same as those teams being healthy.'}
            </p>
          </div>
        </aside>
      </div>

      <footer className="muted small">
        Spreads are home-team lines throughout: negative means the home team is
        favoured. Free data only — CFBD, nflverse, ESPN, The Odds API,
        Open-Meteo.
      </footer>
    </div>
  )
}
