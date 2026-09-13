const MODEL_LABELS = {
  'baseline-v1': 'Baseline',
  'ml-v1': 'ML model',
}

const PART_LABELS = {
  winners: 'Picking winners',
  margin: 'Margin accuracy',
  spread: 'Against the spread',
}

// Break-even against standard -110 juice.
const BREAK_EVEN = 0.524

// One-sided test against break-even, matching src/grade.py.
function pValue(wins, n) {
  if (!n) return 1
  const se = Math.sqrt((BREAK_EVEN * (1 - BREAK_EVEN)) / n)
  const z = (wins / n - BREAK_EVEN) / se
  return 0.5 * (1 - erf(z / Math.SQRT2))
}

function erf(x) {
  // Abramowitz & Stegun 7.1.26.
  const sign = x < 0 ? -1 : 1
  x = Math.abs(x)
  const t = 1 / (1 + 0.3275911 * x)
  const y =
    1 -
    ((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t +
      0.254829592) *
      t *
      Math.exp(-x * x)
  return sign * y
}

function tone(value) {
  if (value >= 53) return 'good'
  if (value < 47) return 'bad'
  return ''
}

// One number for "how is it doing", benchmarked against the market rather
// than against zero. A raw hit rate flatters any model: picking every betting
// favourite wins most games, so 80% straight up can still be worse than doing
// nothing. The score is built in src/grade.correctness_score; 50 is parity.
function ScoreCard({ score }) {
  if (!score) return null
  return (
    <div className="score-card">
      <div className="score-head">
        <span className={`score ${tone(score.score)}`}>{Math.round(score.score)}</span>
        <span className="muted">/100</span>
        <span className={`score-verdict ${tone(score.score)}`}>{score.verdict}</span>
      </div>
      <div className="bars">
        {Object.entries(score.parts).map(([key, part]) => (
          <div className="bar-row score-row" key={key}>
            <span className="bar-label">{PART_LABELS[key] || key}</span>
            <div className="bar-track score-track">
              <div
                className={`bar-fill current ${part.value >= 50 ? 'is-good' : 'is-bad'}`}
                style={{ width: `${Math.max(Math.min(part.value, 100), 1)}%` }}
              />
            </div>
            <span className="bar-value">{Math.round(part.value)}</span>
            <span className="bar-note">{part.detail}</span>
          </div>
        ))}
      </div>
      <p className="muted small">
        Correctness score: 50 = exactly as good as the betting market, higher is
        better. The tick on each bar marks 50.
      </p>
    </div>
  )
}

function SlateHistory({ slates }) {
  if (!slates?.length) return null
  return (
    <table className="micro">
      <thead>
        <tr>
          <th>Slate</th>
          <th className="num">Games</th>
          <th className="num">Score</th>
          <th className="num">SU</th>
          <th className="num">ATS</th>
        </tr>
      </thead>
      <tbody>
        {slates.map((s) => (
          <tr key={s.date}>
            <td>{s.date}</td>
            <td className="num">{s.n}</td>
            <td className={`num ${s.score != null ? tone(s.score) : ''}`}>
              {s.score != null ? Math.round(s.score) : '—'}
            </td>
            <td className="num">
              {s.su.n ? `${Math.round((s.su.right / s.su.n) * 100)}%` : '—'}
            </td>
            <td className="num">
              {s.ats.win}-{s.ats.loss}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

// The accumulated record. Separate from the backtest above it: that is how the
// model did on history it never trained on, this is how it has done since.
export default function ResultsPanel({ results }) {
  const models = Object.entries(results?.models || {})
  const total = results?.total_graded || 0

  if (!total) {
    return (
      <div className="panel">
        <h3>Track record</h3>
        <p className="muted small">
          Nothing graded yet. Once a slate finishes, run{' '}
          <code>python -m src.grade --refresh</code> and this fills in with the
          real record: a correctness score against the market, straight up,
          against the spread, and margin error against the closing line.
        </p>
        <p className="muted small">
          This is the panel that matters. Everything above it is a forecast;
          this is the only part that can ever say whether the forecasts were any
          good.
        </p>
      </div>
    )
  }

  return (
    <div className="panel">
      <h3>
        Track record <span className="muted">{total} graded</span>
      </h3>

      {total < 200 && (
        <div className="verdict off">
          {total} graded result{total === 1 ? '' : 's'} is far too few to
          conclude anything. Telling a real 55% edge from a coin flip takes
          several hundred games — a good run and a lucky run look identical
          here.
        </div>
      )}

      {models.map(([version, s]) => {
        const decided = s.ats?.decided || 0
        const wins = s.ats?.win || 0
        const p = decided ? pValue(wins, decided) : 1
        const beatLine =
          s.mae != null && s.market_mae != null ? s.mae - s.market_mae : null
        return (
          <div key={version} className="record">
            <h4>{MODEL_LABELS[version] || version}</h4>
            <ScoreCard score={s.score} />
            <div className="stat-row">
              {s.su?.n > 0 && (
                <div>
                  <span className="stat">
                    {((s.su.right / s.su.n) * 100).toFixed(1)}%
                  </span>
                  <em>
                    straight up · {s.su.right}/{s.su.n}
                  </em>
                </div>
              )}
              {decided > 0 && (
                <div>
                  <span className={`stat ${wins / decided > BREAK_EVEN ? 'good' : ''}`}>
                    {((wins / decided) * 100).toFixed(1)}%
                  </span>
                  <em>
                    ATS · {wins}-{s.ats.loss}
                    {s.ats.push ? `-${s.ats.push}` : ''}
                  </em>
                </div>
              )}
              {s.brier != null && (
                <div>
                  <span className="stat">{s.brier.toFixed(3)}</span>
                  <em>Brier · 0.25 = coin flip</em>
                </div>
              )}
            </div>

            {beatLine != null && (
              <p className="small">
                Margin error {s.mae.toFixed(2)} pts vs the closing line&rsquo;s{' '}
                {s.market_mae.toFixed(2)} —{' '}
                <span className={beatLine < 0 ? 'good' : 'bad'}>
                  {beatLine > 0 ? '+' : ''}
                  {beatLine.toFixed(2)}
                </span>
                , {beatLine < 0 ? 'better than the line' : 'worse than the line'}.
              </p>
            )}

            {decided > 0 && (
              <p className="muted small">
                p = {p.toFixed(3)} against break-even.{' '}
                {p < 0.05
                  ? 'Distinguishable from chance on this sample.'
                  : 'Not distinguishable from chance.'}
              </p>
            )}

            <SlateHistory slates={s.by_slate} />

            {Object.entries(s.by_conf || {}).length > 0 && (
              <table className="micro">
                <thead>
                  <tr>
                    <th>Confidence</th>
                    <th className="num">ATS</th>
                    <th className="num">Win%</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(s.by_conf).map(([tier, [w, n]]) => (
                    <tr key={tier}>
                      <td>
                        <span className={`conf ${tier}`}>{tier}</span>
                      </td>
                      <td className="num">
                        {w}/{n}
                      </td>
                      <td className="num">{((w / n) * 100).toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )
      })}
    </div>
  )
}
