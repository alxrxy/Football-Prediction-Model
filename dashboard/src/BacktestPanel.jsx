// The backtest is shown as prominently as the picks, on purpose. A dashboard
// that displays edges without the evidence about whether those edges have ever
// worked is the thing this project is trying not to build.
export default function BacktestPanel({ backtest, calibration }) {
  if (!backtest) {
    return (
      <div className="panel">
        <h3>Backtest</h3>
        <p className="muted">
          No trained model for this sport yet. Run{' '}
          <code>python -m src.train_model</code>.
        </p>
      </div>
    )
  }

  const marketMae = backtest.market_mae
  const rows = Object.entries(backtest.models)
  const atsSets = Object.entries(backtest.ats || {}).filter(([, b]) => b.length)
  const anySignificant = atsSets.some(([, buckets]) =>
    buckets.some((b) => b.significant),
  )

  return (
    <div className="panel">
      <h3>
        Backtest <span className="muted">holdout {backtest.holdout_season}</span>
      </h3>

      <div className={`verdict ${anySignificant ? 'ok' : 'off'}`}>
        {anySignificant
          ? 'Some edge threshold beat the closing line significantly, so the trained model is permitted to flag value.'
          : 'No edge threshold beat the closing line by more than noise, so the trained model flags nothing as value. The baseline heuristic still marks games past its fixed threshold; those are labelled unvalidated and carry no evidence behind them.'}
      </div>

      <h4>Margin error vs the closing line</h4>
      <table className="micro">
        <thead>
          <tr>
            <th>Model</th>
            <th className="num">MAE</th>
            <th className="num">vs line</th>
          </tr>
        </thead>
        <tbody>
          <tr className="bench">
            <td>Closing line</td>
            <td className="num">{marketMae?.toFixed(3)}</td>
            <td className="num muted">benchmark</td>
          </tr>
          {rows.map(([name, r]) => {
            const delta = r.mae - marketMae
            return (
              <tr key={name}>
                <td>{name.replace('_', ' ')}</td>
                <td className="num">{r.mae?.toFixed(3)}</td>
                <td className={`num ${delta < 0 ? 'good' : 'bad'}`}>
                  {delta > 0 ? '+' : ''}
                  {delta.toFixed(3)}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <p className="muted small">
        Lower is better. Beating the line is the only meaningful bar — a model
        can predict margins to within 10 points and still be useless if the line
        manages 9.8 on the same games.
      </p>

      {atsSets.map(([name, buckets]) => (
        <div key={name}>
          <h4 className="spaced">Against the spread — {name.replace('_', ' ')}</h4>
          <table className="micro">
            <thead>
              <tr>
                <th>Edge</th>
                <th className="num">Record</th>
                <th className="num">Win%</th>
                <th className="num">p (corrected)</th>
              </tr>
            </thead>
            <tbody>
              {buckets.map((b) => (
                <tr key={b.threshold}>
                  <td>&ge; {b.threshold.toFixed(1)}</td>
                  <td className="num">
                    {b.wins}/{b.n}
                  </td>
                  <td className={`num ${b.win_pct > 0.524 ? 'good' : ''}`}>
                    {(b.win_pct * 100).toFixed(1)}%
                  </td>
                  <td className="num">
                    {b.p_value?.toFixed(3)}
                    {b.significant ? ' ✓' : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
      <p className="muted small">
        Break-even at standard &minus;110 juice is 52.4%. p-values are
        Bonferroni-corrected for testing ten model/threshold combinations —
        without that correction roughly one bucket clears 0.05 by luck each run.
      </p>

      {calibration?.n > 0 && (
        <>
          <h4 className="spaced">This slate vs the market</h4>
          <div className="stat-row">
            <div>
              <span className="stat">{calibration.mean_abs.toFixed(2)}</span>
              <em>mean |model &minus; market|, pts</em>
            </div>
            <div>
              <span className="stat">
                {calibration.mean_signed > 0 ? '+' : ''}
                {calibration.mean_signed.toFixed(2)}
              </span>
              <em>mean signed edge</em>
            </div>
            <div>
              <span className="stat">{calibration.n}</span>
              <em>fully-rated games</em>
            </div>
          </div>
          <h5>How many games each threshold would flag</h5>
          <div className="bars">
            {Object.entries(calibration.threshold_counts).map(([t, count]) => {
              const share = count / calibration.n
              const current = Number(t) === calibration.current_threshold
              return (
                <div className="bar-row" key={t}>
                  <span className="bar-label">&ge; {t}</span>
                  <div className="bar-track">
                    <div
                      className={`bar-fill ${current ? 'current' : ''}`}
                      style={{ width: `${Math.max(share * 100, 1)}%` }}
                    />
                  </div>
                  <span className="bar-value">
                    {count} ({Math.round(share * 100)}%)
                    {current ? ' ← current' : ''}
                  </span>
                </div>
              )
            })}
          </div>
          {calibration.threshold_counts[
            calibration.current_threshold.toFixed(1)
          ] /
            calibration.n >
            0.4 && (
            <p className="caveat">
              The current threshold flags most of the slate. A signal that fires
              on the majority of games carries no information.
            </p>
          )}
        </>
      )}
    </div>
  )
}
