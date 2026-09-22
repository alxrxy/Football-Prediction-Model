// Standing rule, adopted 2026-09-22 (calibration-log.md): baseline value flags
// are shown for tracking but are not an actionable signal until the flagged
// picks themselves beat the -110 break-even. P37 found the baseline edge covers
// ~50% at every size over ten replayed seasons, so a flag has to earn trust on
// its own record. Display only: nothing here changes an edge or a flag.
//
// Cleared when, counting every graded baseline flag (pushes excluded):
//   at least MIN_FLAGS decided, and
//   one-sided binomial P(wins >= observed | 52.4%) < ALPHA.

export const TRUST_MODEL = 'baseline-v1'
export const BREAK_EVEN = 0.524
export const MIN_FLAGS = 50
export const ALPHA = 0.05

// P(X >= k) for X ~ Binomial(n, p), summed in log space so n in the hundreds is fine.
function tailAtLeast(k, n, p) {
  if (k <= 0) return 1
  if (k > n) return 0
  let logC = 0 // log C(n, 0)
  let total = 0
  for (let i = 0; i <= n; i++) {
    if (i > 0) logC += Math.log(n - i + 1) - Math.log(i)
    if (i >= k) total += Math.exp(logC + i * Math.log(p) + (n - i) * Math.log(1 - p))
  }
  return Math.min(1, total)
}

// Fewest wins out of n that would clear the test.
function winsNeeded(n) {
  for (let k = 0; k <= n; k++) if (tailAtLeast(k, n, BREAK_EVEN) < ALPHA) return k
  return null
}

export function flagTrust(results) {
  const r = results?.models?.[TRUST_MODEL]?.edges?.flagged || { win: 0, loss: 0, push: 0 }
  const decided = r.win + r.loss
  const p = decided ? tailAtLeast(r.win, decided, BREAK_EVEN) : 1
  const validated = decided >= MIN_FLAGS && p < ALPHA
  const target = Math.max(decided, MIN_FLAGS)
  return { ...r, decided, p, validated, target, winsNeeded: winsNeeded(target) }
}

// Is this pick's flag one the rule covers? Only the baseline's flags are.
export const labelled = (trust, version = TRUST_MODEL) => version === TRUST_MODEL && !trust.validated

export const UNVALIDATED_TEXT = 'not yet statistically validated'

export function trustTitle(t) {
  return (
    `Tracked, not actionable. Baseline flags are ${t.win}-${t.loss}${t.push ? `-${t.push}` : ''} ` +
    `(${t.decided} of ${MIN_FLAGS} graded). The label comes off only when graded flags beat ` +
    `${(BREAK_EVEN * 100).toFixed(1)}% break-even at p < ${ALPHA} over at least ${MIN_FLAGS} ` +
    `(e.g. ${t.winsNeeded}-${t.target - t.winsNeeded} at ${t.target}).`
  )
}
