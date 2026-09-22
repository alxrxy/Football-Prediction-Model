import BacktestPanel from './BacktestPanel.jsx'
import EdgeRecord from './EdgeRecord.jsx'
import RecordTotals from './RecordTotals.jsx'
import ResultsPanel from './ResultsPanel.jsx'
import ScoreStrip from './ScoreStrip.jsx'
import WeekBreakdown from './WeekBreakdown.jsx'
import { PageHead } from './ui.jsx'

// How the models are doing: the total record split into moneyline and spread,
// the flagged picks and ATS by edge size, then the same split week by week with every game under it, the running
// record and the backtest behind the gates.

export default function RecordPage({ sport }) {
  const results = sport.results
  const graded = results?.total_graded || 0

  return (
    <div className="page">
      <PageHead
        title="Track record"
        sub="Every graded prediction against the betting market. Paper trading only: nothing here has cleared the bar for calling an edge real."
      />
      <ScoreStrip results={results} sportLabel={sport.label} />
      <div className="split">
        <div className="split-main">
          {graded ? (
            <div className="card">
              <RecordTotals results={results} />
              <EdgeRecord results={results} />
              <WeekBreakdown weeks={results?.weeks} />
            </div>
          ) : (
            <div className="card empty">
              <strong>Nothing graded yet</strong>
              <p className="muted">
                Once a week finishes, run <code>python -m src.grade --refresh</code>{' '}
                and the record fills in here: moneyline and spread totals, then
                each week with every game.
              </p>
            </div>
          )}
        </div>
        <aside className="split-side stack">
          <ResultsPanel results={results} />
          <BacktestPanel backtest={sport.backtest} calibration={sport.calibration} />
        </aside>
      </div>
    </div>
  )
}
