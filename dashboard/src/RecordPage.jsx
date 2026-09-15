import BacktestPanel from './BacktestPanel.jsx'
import GradedSlate from './GradedSlate.jsx'
import ResultsPanel from './ResultsPanel.jsx'
import ScoreStrip from './ScoreStrip.jsx'
import { PageHead } from './ui.jsx'

// How the models are doing: correctness vs the market, the latest graded
// slate game by game, the running record and the backtest behind the gates.

export default function RecordPage({ sport }) {
  return (
    <div className="page">
      <PageHead
        title="Track record"
        sub="Every graded prediction against the betting market. Paper trading only: nothing here has cleared the bar for calling an edge real."
      />
      <ScoreStrip results={sport.results} sportLabel={sport.label} />
      <div className="split">
        <div className="split-main">
          <div className="card">
            <GradedSlate slate={sport.results?.last_slate} />
          </div>
        </div>
        <aside className="split-side stack">
          <ResultsPanel results={sport.results} />
          <BacktestPanel backtest={sport.backtest} calibration={sport.calibration} />
        </aside>
      </div>
    </div>
  )
}
