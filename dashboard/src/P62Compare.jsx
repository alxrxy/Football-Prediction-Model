import { useEffect, useState } from 'react'
import { UNVALIDATED_TEXT } from './flagTrust.js'

// P62 Phase 1 (S8c): the Sportradar shadow pull measured against the Odds API
// pull it sits beside, from p62_compare.json:
//   python -m src.p62_compare --export      (also run after every props ranking)
// Built from saved shadow files only; nothing here feeds the list above. When
// the file is missing or unreadable the section is simply not shown.

const MARKET = {
  player_pass_yds: 'Pass yds',
  player_rush_yds: 'Rush yds',
  player_reception_yds: 'Rec yds',
  player_receptions: 'Receptions',
}
const BOOK = { draftkings: 'DraftKings', fanduel: 'FanDuel', betmgm: 'BetMGM', betrivers: 'BetRivers', williamhill_us: 'Caesars' }

const statusClass = (s) => (s.startsWith('PASS') ? 'pass' : s.startsWith('STOP') || s.startsWith('FAIL') ? 'stop' : 'open')
const statusWord = (s) => s.split(' ')[0]
const when = (iso) => new Date(iso).toLocaleString([], { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
const price = (p) => (p == null ? '—' : p > 0 ? `+${p}` : `${p}`)

// Where a prop sits in one source's ranking. A prop off the ranked list was
// either held out (its line and side still shown) or never priced at all.
const STATE = {
  'held: gap': ['held out', 'gap over the hold-out limit: more likely a usage miss'],
  'held: structural': ['held out', 'engine defect, not player signal'],
  started: ['started', 'game kicked off; pregame line no longer bettable'],
  'not priced': ['not priced', 'no line from this source for this prop'],
}

function Slot({ state, rank, side, line, topN }) {
  const pill = side ? (
    <span className={`pick sm ${side}`}>{side === 'over' ? '▲ O' : '▼ U'} {line ?? '—'}</span>
  ) : null
  if (!state || state === 'ranked') {
    return (
      <span className={rank <= topN ? '' : 'muted'}>
        #{rank} {pill}
      </span>
    )
  }
  const [word, why] = STATE[state] || [state, '']
  return (
    <span className="p62-slot">
      <span className="p62-cause warn" title={why}>{word}</span> {pill}
      {why ? <em className="sub">{why}</em> : null}
    </span>
  )
}

export default function P62Compare() {
  const [d, setD] = useState(null)
  useEffect(() => {
    fetch(`./p62_compare.json?ts=${Date.now()}`, { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => setD(j && Array.isArray(j.criteria) ? j : null))
      .catch(() => setD(null))
  }, [])
  if (!d) return null

  const pullAt = Object.fromEntries((d.pulls || []).map((p) => [p.stamp, p.at]))
  const multiPull = (d.pulls || []).length > 1
  const changes = d.changes || []
  const diffs = d.line_diffs || []

  return (
    <details className="card held p62">
      <summary>
        <span>Odds source check · Sportradar vs The Odds API</span>
        <span className="p62-pills" aria-label="Criteria status">
          {d.criteria.map((c) => (
            <span key={c.id} className={`p62-pill ${statusClass(c.status)}`} title={`${c.id} ${c.name}: ${c.status}`}>
              {c.id} {statusWord(c.status).toLowerCase()}
            </span>
          ))}
        </span>
      </summary>

      <div className="p62-body">
        <p className="p62-intro">
          <span className="tag unvalidated">shadow comparison · {UNVALIDATED_TEXT}</span>{' '}
          Every props pull is shadowed by a Sportradar pull of the same games; this checks whether swapping the
          source would change anything. Nothing here feeds the list above.{' '}
          <span className="muted">
            Window {when(d.window.start)} – {when(d.window.end)} · {d.pulls.length} pull{d.pulls.length === 1 ? '' : 's'},{' '}
            {d.paired} game pairs{d.excluded ? `, ${d.excluded} excluded` : ''} · updated {when(d.generated_at)}
          </span>
        </p>

        <ul className="p62-criteria">
          {d.criteria.map((c) => (
            <li key={c.id}>
              <span className={`p62-status ${statusClass(c.status)}`}>{statusWord(c.status)}</span>
              <div>
                <strong>
                  {c.id} {c.name}
                </strong>
                {c.status.includes('(') ? <em className="muted"> {c.status.slice(c.status.indexOf('('))}</em> : null}
                <span className="p62-detail">{c.detail.join(' · ')}</span>
                {c.items?.length ? (
                  <ul className="p62-items">
                    {c.items.map((x) => (
                      <li key={x}>{x}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
            </li>
          ))}
        </ul>

        <h4 className="p62-h">
          Ranking changes <span className="muted">· top {d.top_n} entries, exits and side flips, with their cause</span>
        </h4>
        {changes.length ? (
          <div className="table-wrap">
            <table className="more-props p62-table">
              <thead>
                <tr>
                  <th>Player</th>
                  <th>Prop</th>
                  <th>Odds API</th>
                  <th>Sportradar</th>
                  <th>Change</th>
                  <th>Cause</th>
                </tr>
              </thead>
              <tbody>
                {changes.map((c) => (
                  <tr key={`${c.pull}-${c.game_id}-${c.player}-${c.market}`}>
                    <td>
                      <strong>{c.player}</strong>
                      <em className="sub">
                        {c.team} · {c.game}
                        {multiPull ? ` · ${when(pullAt[c.pull])}` : ''}
                      </em>
                    </td>
                    <td>{c.label || MARKET[c.market] || c.market}</td>
                    <td>
                      <Slot state={c.odds_state} rank={c.odds_rank} side={c.odds_side ?? c.odds_pick} line={c.odds_line} topN={d.top_n} />
                    </td>
                    <td>
                      <Slot state={c.sr_state} rank={c.sr_rank} side={c.sr_side ?? c.sr_pick} line={c.sr_line} topN={d.top_n} />
                    </td>
                    <td>{c.kinds.join(' + ')}</td>
                    <td>
                      <span className={`p62-cause ${c.cause === 'unexplained' ? 'stop' : ''}`}>{c.cause}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted small">No prop enters or leaves the top {d.top_n}, and none flips side.</p>
        )}
        <p className="muted small p62-legend">
          <b>Book mix</b>: the change disappears when both sources are cut to the books they share. <b>Line</b>: a
          shared book posts a different line or price. <b>Coverage</b>: Sportradar has no line for that prop.{' '}
          <b>Unexplained</b> is a stop.
        </p>

        <details className="p62-diffs">
          <summary>
            Line-by-line differences · {d.line_diff_count} on shared books
            {d.line_diff_count > diffs.length ? ` (first ${diffs.length} shown)` : ''}
          </summary>
          {diffs.length ? (
            <div className="table-wrap">
              <table className="more-props">
                <thead>
                  <tr>
                    <th>Player</th>
                    <th>Prop</th>
                    <th>Book</th>
                    <th className="num">Odds API</th>
                    <th className="num">Sportradar</th>
                    <th>Tag</th>
                  </tr>
                </thead>
                <tbody>
                  {diffs.map((x) => (
                    <tr key={`${x.pull}-${x.game}-${x.player}-${x.market}-${x.book}`}>
                      <td>
                        <strong>{x.player}</strong>
                        <em className="sub">
                          {x.game.replace(/^\d{4}_\d{2}_/, '').replace('_', ' @ ')} · {x.minutes} min apart
                          {multiPull ? ` · ${when(pullAt[x.pull])}` : ''}
                        </em>
                      </td>
                      <td>
                        {MARKET[x.market] || x.market}
                        <em className="sub">{x.kind === 'total' ? 'different line' : 'price only'}</em>
                      </td>
                      <td>{BOOK[x.book] || x.book}</td>
                      <td className="num">
                        {x.odds.point} <span className="muted">{price(x.odds.over)}/{price(x.odds.under)}</span>
                      </td>
                      <td className="num">
                        {x.sr.point} <span className="muted">{price(x.sr.over)}/{price(x.sr.under)}</span>
                      </td>
                      <td>
                        <span className={`p62-cause ${x.tag === 'unexplained' ? 'warn' : ''}`}>{x.tag}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="muted small">Every shared book posts the same line and price in both sources.</p>
          )}
          <p className="muted small p62-legend">
            <b>Lag</b>: one side still shows the other&rsquo;s previous line. <b>Gap</b>: the two pulls were more than 5
            minutes apart. <b>Unexplained</b>: neither; counted against the 95% bars above, not a stop on its own.
          </p>
        </details>
      </div>
    </details>
  )
}
