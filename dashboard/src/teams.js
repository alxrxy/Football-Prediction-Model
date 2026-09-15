import TEAMS from './nflTeams.json'

// NFL team identity: name, colours and ESPN logo (nflTeams.json, written by
// python -m src.export_team_meta). A team colour always sits beside a logo or
// an abbreviation, so colour is never the only thing identifying a team.

const FALLBACK = { name: '', nick: '', color: '#64748b', color2: '#94a3b8', logo: null }

export const team = (abbr) => TEAMS[abbr] || { ...FALLBACK, name: abbr, nick: abbr }

const rgb = (hex) => {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex || '')
  if (!m) return null
  const n = parseInt(m[1], 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}
const luminance = (c) => {
  const [r, g, b] = c.map((v) => {
    const s = v / 255
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}
const contrast = (a, b) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}
const distance = (a, b) => {
  const p = rgb(a)
  const q = rgb(b)
  return p && q ? Math.hypot(p[0] - q[0], p[1] - q[1], p[2] - q[2]) : 999
}

const isDark = () => {
  const forced = document.documentElement.dataset.theme
  if (forced) return forced === 'dark'
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
}
const SURFACE = { dark: [18, 24, 38], light: [255, 255, 255] }

// The colour to draw a team with on the current surface: its primary, unless
// that nearly vanishes against the background (navy on dark, silver on light).
export function teamColor(abbr) {
  const t = team(abbr)
  const surface = isDark() ? SURFACE.dark : SURFACE.light
  for (const c of [t.color, t.color2]) {
    const v = rgb(c)
    if (v && contrast(v, surface) >= 1.7) return c
  }
  return t.color || FALLBACK.color
}

// Two teams sharing one mark (a win-chance bar, a chart): if their colours are
// too alike to tell apart, the away side switches to its secondary colour.
export function matchupColors(away, home) {
  const h = teamColor(home)
  let a = teamColor(away)
  if (distance(a, h) < 90) {
    const alt = team(away).color2
    if (alt && distance(alt, h) >= 90) a = alt
  }
  return { away: a, home: h }
}
