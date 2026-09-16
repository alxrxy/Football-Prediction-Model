// The headline record, split the two ways a bet is actually settled: picking
// the winner (moneyline) and covering the number (against the spread). They
// come apart badly -- a model can pick 79% of winners and still go 4-10 ATS,
// because picking favourites wins games and says nothing about the line.

const MODEL_LABELS = {
  'baseline-v1': 'Baseline',
  'ml-v1': 'ML model',
}

// Break-even against standard -110 juice.
const BREAK_EVEN = 0.524

const rate = (wins, n) => (n ? `${((wins / n) * 100).toFixed(1)}%` : '—')

export default function RecordTotals({ results }) {
  const models = Object.entries(results?.models || {})
  const total = results?.total_graded || 0
  if (!total || !models.length) return null

  return (
    <section className="totals">
      <h3>
        Total record
        <span className="muted">
          {total} graded prediction{total === 1 ? '' : 's'}
        </span>
      </h3>
      <div className="total-grid">
        {models.map(([version, m]) => {
          const su = m.su || {}
          const ats = m.ats || {}
          const suN = su.n || 0
          const suRight = su.right || 0
          const decided = ats.decided || 0
          const beat = decided ? ats.win / decided > BREAK_EVEN : null
          return (
            <div className="total-card" key={version}>
              <h4>{MODEL_LABELS[version] || version}</h4>
              <div className="total-pair">
                <div className="total-stat">
                  <em>Moneyline · straight up</em>
                  <strong>
                    {suRight}-{suN - suRight}
                  </strong>
                  <span>
                    {rate(suRight, suN)} of {suN} decided
                  </span>
                </div>
                <div className="total-stat">
                  <em>Against the spread</em>
                  <strong className={beat === null ? '' : beat ? 'good' : 'bad'}>
                    {ats.win || 0}-{ats.loss || 0}
                    {ats.push ? `-${ats.push}` : ''}
                  </strong>
                  <span>
                    {rate(ats.win || 0, decided)} · 52.4% breaks even
                  </span>
                </div>
              </div>
            </div>
          )
        })}
      </div>
      <p className="muted small">
        Moneyline counts only games with a winner; a tie is no result. Against
        the spread is graded on the side the model leaned, against the line
        stored with the prediction rather than one pulled afterwards.
      </p>
    </section>
  )
}
