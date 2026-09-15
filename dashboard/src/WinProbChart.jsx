import { useRef, useState } from 'react'

// Live win chance over the game, from the live tracker's history. One series
// (the home side's chance, from the live model), so the title names it and no
// legend box is needed. The area above 50% is washed in the home colour and
// below in the away colour, and both sides are labelled with their team, so
// colour never carries identity alone. Hover or arrow keys move a crosshair.

const W = 640
const H = 230
const PAD = { l: 44, r: 58, t: 14, b: 28 }

export default function WinProbChart({ history, home, away, colors, scoring = [] }) {
  const [idx, setIdx] = useState(null)
  const ref = useRef(null)
  const pts = (history || []).filter((p) => p.t != null && p.wp_home != null).sort((a, b) => a.t - b.t)
  if (pts.length < 2) {
    return <p className="muted small">The win-chance chart fills in after a few live polls.</p>
  }
  const maxT = Math.max(60, Math.ceil(pts[pts.length - 1].t / 15) * 15)
  const x = (t) => PAD.l + (t / maxT) * (W - PAD.l - PAD.r)
  const y = (p) => PAD.t + (1 - p) * (H - PAD.t - PAD.b)
  const line = pts.map((p, i) => `${i ? 'L' : 'M'}${x(p.t).toFixed(1)},${y(p.wp_home).toFixed(1)}`).join('')
  const area = `${line}L${x(pts[pts.length - 1].t).toFixed(1)},${y(0.5)}L${x(pts[0].t).toFixed(1)},${y(0.5)}Z`
  const last = pts[pts.length - 1]
  const cur = idx == null ? null : pts[idx]

  const nearest = (clientX) => {
    const box = ref.current.getBoundingClientRect()
    const t = (((clientX - box.left) / box.width) * W - PAD.l) / (W - PAD.l - PAD.r) * maxT
    let best = 0
    pts.forEach((p, i) => {
      if (Math.abs(p.t - t) < Math.abs(pts[best].t - t)) best = i
    })
    return best
  }
  const quarter = (t) => (t >= 60 ? 'OT' : `Q${Math.floor(t / 15) + 1}`)

  return (
    <figure className="wpchart">
      <figcaption>
        <strong>{home} win chance through the game</strong>
        <span className="muted"> · live model, re-simulated every poll</span>
      </figcaption>
      <div className="wpchart-wrap">
        <svg
          ref={ref}
          viewBox={`0 0 ${W} ${H}`}
          role="img"
          aria-label={`${home} win chance went from ${Math.round(pts[0].wp_home * 100)}% to ${Math.round(last.wp_home * 100)}%`}
          tabIndex={0}
          onPointerMove={(e) => setIdx(nearest(e.clientX))}
          onPointerLeave={() => setIdx(null)}
          onKeyDown={(e) => {
            if (e.key === 'ArrowLeft') setIdx((i) => Math.max(0, (i ?? pts.length - 1) - 1))
            if (e.key === 'ArrowRight') setIdx((i) => Math.min(pts.length - 1, (i ?? pts.length - 1) + 1))
          }}
          onBlur={() => setIdx(null)}
        >
          <defs>
            <clipPath id="wp-above">
              <rect x="0" y="0" width={W} height={y(0.5)} />
            </clipPath>
            <clipPath id="wp-below">
              <rect x="0" y={y(0.5)} width={W} height={H} />
            </clipPath>
          </defs>
          {[0, 0.25, 0.5, 0.75, 1].map((p) => (
            <g key={p}>
              <line className={p === 0.5 ? 'grid mid' : 'grid'} x1={PAD.l} x2={W - PAD.r} y1={y(p)} y2={y(p)} />
              <text className="tick" x={PAD.l - 8} y={y(p) + 4} textAnchor="end">
                {Math.round(p * 100)}%
              </text>
            </g>
          ))}
          {[15, 30, 45, 60].filter((t) => t <= maxT).map((t) => (
            <line key={t} className="grid" x1={x(t)} x2={x(t)} y1={PAD.t} y2={H - PAD.b} />
          ))}
          {[0, 15, 30, 45].map((t) => (
            <text key={t} className="tick" x={x(t + 7.5)} y={H - 9} textAnchor="middle">
              Q{t / 15 + 1}
            </text>
          ))}
          {maxT > 60 ? (
            <text className="tick" x={x(60 + (maxT - 60) / 2)} y={H - 9} textAnchor="middle">OT</text>
          ) : null}
          <path d={area} clipPath="url(#wp-above)" style={{ fill: colors.home }} className="wash" />
          <path d={area} clipPath="url(#wp-below)" style={{ fill: colors.away }} className="wash" />
          {scoring.map((s, i) =>
            s.t != null ? <circle key={i} className="score-tick" cx={x(s.t)} cy={H - PAD.b} r="4" /> : null,
          )}
          <path d={line} className="wpline" />
          <circle className="enddot" cx={x(last.t)} cy={y(last.wp_home)} r="4.5" />
          <text className="endlabel" x={x(last.t) + 9} y={y(last.wp_home) + 4}>
            {Math.round(last.wp_home * 100)}%
          </text>
          <text className="side-label" x={W - PAD.r + 8} y={PAD.t + 12}>{home} ↑</text>
          <text className="side-label" x={W - PAD.r + 8} y={H - PAD.b - 4}>{away} ↓</text>
          {cur ? (
            <g>
              <line className="crosshair" x1={x(cur.t)} x2={x(cur.t)} y1={PAD.t} y2={H - PAD.b} />
              <circle className="enddot" cx={x(cur.t)} cy={y(cur.wp_home)} r="4.5" />
            </g>
          ) : null}
        </svg>
        {cur ? (
          <div className="wp-tip" style={{ left: `${(x(cur.t) / W) * 100}%` }}>
            <strong>{home} {Math.round(cur.wp_home * 100)}%</strong>
            <span>{quarter(cur.t)} · minute {Math.round(cur.t)}</span>
            {cur.margin_proj != null ? (
              <span>
                projected margin {cur.margin_proj > 0 ? home : away} {Math.abs(cur.margin_proj).toFixed(1)}
              </span>
            ) : null}
            {cur.espn_wp != null ? <span>ESPN: {home} {Math.round(cur.espn_wp * 100)}%</span> : null}
          </div>
        ) : null}
      </div>
    </figure>
  )
}
