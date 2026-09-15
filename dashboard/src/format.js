// Shared formatting. Sign conventions live here so no component reinvents them.

export const signed = (value, digits = 1) =>
  value === null || value === undefined
    ? '—'
    : `${value > 0 ? '+' : ''}${value.toFixed(digits)}`

export const pct = (value) =>
  value === null || value === undefined ? '—' : `${Math.round(value * 100)}%`

export const kickoffLabel = (iso) => {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
}

export const dateLabel = (iso) => {
  if (!iso) return ''
  const date = new Date(`${iso}T12:00:00Z`)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleDateString([], {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  })
}

// A spread is a home-team line: negative means the home team is favoured.
// Naming the favourite removes the ambiguity a bare signed number carries, so
// the parts are returned separately and stacked in the cell -- that keeps the
// column narrow without falling back to an unlabelled number.
export const spreadParts = (spread, home, away) => {
  if (spread === null || spread === undefined) return null
  if (spread === 0) return { team: 'pick', line: 'PK' }
  return {
    team: spread < 0 ? home : away,
    line: (-Math.abs(spread)).toFixed(1),
  }
}

export const spreadLabel = (spread, home, away) => {
  const parts = spreadParts(spread, home, away)
  return parts ? `${parts.team} ${parts.line}` : '—'
}

// Edge is positive when the model prefers the home side.
export const edgeSide = (edge, home, away) => {
  if (edge === null || edge === undefined) return null
  if (Math.abs(edge) < 0.05) return null
  return edge > 0 ? home : away
}

export const confidenceRank = { high: 3, medium: 2, low: 1 }

// Colour for a correctness score, where 50 is parity with the market.
export const tone = (score) => (score >= 53 ? 'good' : score < 47 ? 'bad' : '')
