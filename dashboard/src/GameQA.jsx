import { useState } from 'react'
import './claude.css'

// Ask Claude about one game. Answers come from the local Q&A server
// (python -m src.api_server), which holds the API key and sends Claude only
// this game's numbers: before kickoff the prediction, market and simulation;
// while it's on, the live state and re-projection. Every question is a
// metered API call, so nothing is asked until the button is pressed.

const MAX_LEN = 500
const OFFLINE = 'The Q&A server isn’t running. Start it with: python -m src.api_server'

// scope 'props' asks about the week's ranked props instead of one game.
export default function GameQA({ gameId, scope = 'game', title = 'Ask about this game', suggestions = [], placeholder }) {
  const [question, setQuestion] = useState('')
  const [turns, setTurns] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const ask = async (q) => {
    const text = (q ?? question).trim()
    if (!text || busy) return
    setBusy(true)
    setError(null)
    try {
      const r = await fetch('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scope,
          game_id: gameId,
          question: text,
          history: turns.slice(-3).map(({ q: tq, a }) => ({ q: tq, a })),
        }),
      })
      const body = await r.json().catch(() => null)
      if (!r.ok) throw new Error(body?.error || OFFLINE)
      setTurns((t) => [...t, { q: text, a: body.answer, cost: body.cost_usd, mode: body.mode }])
      setQuestion('')
    } catch (e) {
      setError(e.message === 'Failed to fetch' ? OFFLINE : e.message)
    } finally {
      setBusy(false)
    }
  }

  // The dropdown sits inside a clickable table row; keep clicks and keys here.
  const stop = (e) => e.stopPropagation()

  return (
    <section className="qa" onClick={stop} onKeyDown={stop}>
      <div className="qa-head">
        <h4>{title}</h4>
        <span className="muted small">Claude API · metered, about 2¢ a question</span>
      </div>
      {turns.map((t, i) => (
        <div className="qa-turn" key={i}>
          <p className="qa-q">{t.q}</p>
          <p className="qa-a">{t.a}</p>
          <p className="qa-meta">
            {t.mode === 'live' ? 'answered from live data · ' : ''}
            {t.cost != null ? `~$${t.cost.toFixed(3)}` : ''}
          </p>
        </div>
      ))}
      {!turns.length && suggestions.length > 0 && (
        <div className="qa-suggest">
          {suggestions.map((s) => (
            <button key={s} type="button" disabled={busy} onClick={() => ask(s)}>
              {s}
            </button>
          ))}
        </div>
      )}
      <form
        className="qa-form"
        onSubmit={(e) => {
          e.preventDefault()
          ask()
        }}
      >
        <input
          value={question}
          maxLength={MAX_LEN}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={placeholder || 'Ask anything about this game’s numbers…'}
          aria-label="Question about this game"
        />
        <button type="submit" disabled={busy || !question.trim()}>
          {busy ? 'Asking…' : 'Ask'}
        </button>
      </form>
      {error && <p className="qa-error">{error}</p>}
    </section>
  )
}
