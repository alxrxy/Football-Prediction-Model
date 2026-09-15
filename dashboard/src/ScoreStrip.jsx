import { tone } from './format.js'

const MODEL_LABELS = {
  'baseline-v1': 'Baseline',
  'ml-v1': 'ML model',
}

// The headline answer to "how is it doing", on every tab. The breakdown behind
// each number is in the Track record panel.
export default function ScoreStrip({ results, sportLabel }) {
  const models = Object.entries(results?.models || {}).filter(([, m]) => m.score)

  if (!models.length) {
    return (
      <div className="score-strip">
        <span className="strip-title">
          Correctness score
          <em>50 = as good as the betting market</em>
        </span>
        <span className="muted small">
          No {sportLabel} games graded yet. The first score appears once this
          slate finishes and <code>python -m src.grade --refresh</code> runs.
        </span>
      </div>
    )
  }

  return (
    <div className="score-strip">
      <span className="strip-title">
        Correctness score
        <em>50 = as good as the betting market</em>
      </span>
      {models.map(([version, m]) => (
        <div className="strip-model" key={version}>
          <span className={`strip-score ${tone(m.score.score)}`}>
            {Math.round(m.score.score)}
          </span>
          <span>
            <strong>{MODEL_LABELS[version] || version}</strong>
            <em className={tone(m.score.score)}>
              {m.score.verdict} · {m.n} games
            </em>
          </span>
        </div>
      ))}
    </div>
  )
}
