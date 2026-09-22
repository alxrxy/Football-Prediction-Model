import { useEffect, useState } from 'react'
import SlateTable from './SlateTable.jsx'
import GradedSlate from './GradedSlate.jsx'
import ScoreStrip from './ScoreStrip.jsx'
import BacktestPanel from './BacktestPanel.jsx'
import ResultsPanel from './ResultsPanel.jsx'
import NflHub from './NflHub.jsx'
import { dateLabel, shortDate } from './format.js'

export default function App() {
  const [payload, setPayload] = useState(null)
  const [error, setError] = useState(null)
  const [active, setActive] = useState(null)

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

  // Follow #/nfl/... links (and the back button) to the NFL tab even when the
  // page itself doesn't reload.
  useEffect(() => {
    if (!payload) return undefined
    const onHash = () => {
      const nfl = payload.sports.findIndex((s) => s.sport === 'nfl')
      if (nfl >= 0 && window.location.hash.startsWith('#/nfl')) setActive(nfl)
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [payload])

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

  // The NFL hub keeps its place in the URL hash (#/nfl/...), so a reload or
  // the back button lands on the same section.
  const nflIndex = payload.sports.findIndex((s) => s.sport === 'nfl')
  const index = active ?? (window.location.hash.startsWith('#/nfl') && nflIndex >= 0 ? nflIndex : 0)
  const sport = payload.sports[index]
  const generated = new Date(payload.generated_at)
  const pick = (i) => {
    setActive(i)
    if (payload.sports[i].sport === 'nfl') {
      if (!window.location.hash.startsWith('#/nfl')) window.location.hash = '#/nfl/games'
    } else if (window.location.hash) {
      window.history.replaceState(null, '', window.location.pathname + window.location.search)
    }
  }

  return (
    <div className="shell">
      <header>
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">FP</span>
          <div>
            <h1>Football Predictor</h1>
            <p className="muted">Model lines, game simulations and the evidence for whether any of it beats the market.</p>
          </div>
        </div>
        <div className="meta">
          <span>
            {payload.storage_backend} · {payload.model_version_baseline}
          </span>
          <span className="muted">
            generated{' '}
            {Number.isNaN(generated.getTime())
              ? '—'
              : generated.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}
          </span>
        </div>
      </header>

      <div className="tabs">
        {payload.sports.map((s, i) => (
          <button key={s.sport} className={i === index ? 'active' : ''} onClick={() => pick(i)}>
            {s.label}
            <em>
              {s.games.length} games{s.slate_label ? ` · ${s.slate_label}` : ''}
            </em>
          </button>
        ))}
      </div>

      {sport.sport === 'nfl' ? (
        <NflHub sport={sport} />
      ) : (
        <>
          <ScoreStrip results={sport.results} sportLabel={sport.label} />
          <div className="banner">
            Paper trading only. One slate is not enough signal to trust any edge, and the backtest below has not cleared
            the bar for calling one real.
          </div>
          <div className="layout">
            <main>
              <h2>
                {sport.label}
                <span className="muted">
                  {' · '}
                  {sport.slate_label
                    ? `${sport.slate_label} · ${shortDate(sport.slate_date)} – ${shortDate(sport.slate_end)}`
                    : dateLabel(sport.slate_date)}
                </span>
              </h2>
              {sport.games.length === 0 ? (
                <p className="muted">
                  No games loaded for this slate. Run <code>python run_pipeline.py --sport {sport.sport}</code>.
                </p>
              ) : (
                <SlateTable games={sport.games} results={sport.results} />
              )}
              <GradedSlate slate={sport.results?.last_slate} />
            </main>
            <aside>
              <ResultsPanel results={sport.results} />
              <BacktestPanel backtest={sport.backtest} calibration={sport.calibration} />
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
                  College football mandates no injury report. Coverage is a handful of teams at best, so most games get no
                  injury adjustment, which is not the same as those teams being healthy.
                </p>
              </div>
            </aside>
          </div>
        </>
      )}

      <footer className="muted small">
        Paper trading only. Spreads are home-team lines throughout: negative means the home team is favoured. Free data
        (CFBD, nflverse, ESPN, The Odds API, Open-Meteo); Q&amp;A and prop explanations use the Claude API.
      </footer>
    </div>
  )
}
