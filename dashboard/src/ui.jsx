import { useState } from 'react'
import { matchupColors, team, teamColor } from './teams.js'

// Small shared pieces for the NFL hub.

export function TeamLogo({ abbr, size = 40 }) {
  const [broken, setBroken] = useState(false)
  const t = team(abbr)
  if (!t.logo || broken) {
    return (
      <span className="logo-fallback" style={{ width: size, height: size, background: teamColor(abbr) }} aria-hidden="true">
        {abbr}
      </span>
    )
  }
  return (
    <img
      className="team-logo"
      src={t.logo}
      alt=""
      width={size}
      height={size}
      loading="lazy"
      onError={() => setBroken(true)}
    />
  )
}

// Win chance as one bar split between the two teams, each side labelled with
// its team and percentage so the colours are never the only key.
export function WinBar({ away, home, pHome, label = 'Win chance' }) {
  if (pHome == null) return null
  const { away: ca, home: ch } = matchupColors(away, home)
  const h = Math.round(pHome * 100)
  const a = 100 - h
  return (
    <div className="winbar" role="img" aria-label={`${label}: ${away} ${a}%, ${home} ${h}%`}>
      <div className="winbar-labels">
        <span>
          <i style={{ background: ca }} />
          {away} <b>{a}%</b>
        </span>
        <em>{label}</em>
        <span>
          <b>{h}%</b> {home}
          <i style={{ background: ch }} />
        </span>
      </div>
      <div className="winbar-track">
        <span style={{ flexGrow: Math.max(a, 1), background: ca }} />
        <span style={{ flexGrow: Math.max(h, 1), background: ch }} />
      </div>
    </div>
  )
}

export function PageHead({ title, sub, children }) {
  return (
    <div className="page-head">
      <div>
        <h2>{title}</h2>
        {sub ? <p className="muted">{sub}</p> : null}
      </div>
      {children}
    </div>
  )
}

export function StatusChip({ status, detail }) {
  if (status === 'live') {
    return (
      <span className="chip live">
        <span className="pulse" aria-hidden="true" />
        Live{detail ? ` · ${detail}` : ''}
      </span>
    )
  }
  if (status === 'final') return <span className="chip final">Final</span>
  return <span className="chip">Scheduled</span>
}

// "in 2d 5h", "in 3h 10m", "now"
export function until(iso) {
  const ms = new Date(iso).getTime() - Date.now()
  if (!Number.isFinite(ms)) return ''
  if (ms <= 0) return 'now'
  const m = Math.round(ms / 60000)
  const d = Math.floor(m / 1440)
  const h = Math.floor((m % 1440) / 60)
  return d ? `in ${d}d ${h}h` : h ? `in ${h}h ${m % 60}m` : `in ${m}m`
}

export const pct = (v) => (v == null ? '—' : `${Math.round(v * 100)}%`)
export const n0 = (v) => (v == null || Number.isNaN(Number(v)) ? '—' : `${Math.round(v)}`)
export const byTeam = (m, home, away) =>
  m == null ? '—' : Math.abs(m) < 0.5 ? 'even' : `${m > 0 ? home : away} by ${Math.abs(m).toFixed(1)}`
