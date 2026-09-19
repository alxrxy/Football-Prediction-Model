import PropsPage from './PropsPage.jsx'
import TdPropsPage from './TdPropsPage.jsx'

// The props section: two separate lists behind one toggle.
//   #/nfl/props       yardage / reception props (props.json)
//   #/nfl/props/td    anytime TD props (td_props.json), exploratory
// They share nothing but the section: separate data files, rankings and caveats.
//
// HELD, NOT WIRED IN (2026-09-18): the TD list waits on the usage fixes (P23-P26).
// Nothing imports this file, so #/nfl/props/td falls through to PropsPage. To
// turn it on, in NflHub.jsx: import PropsSection instead of PropsPage, add
// `sub: parts[2] || null` to what parse() returns, and render
// <PropsSection sub={route.sub} /> for the props section.

const TABS = [
  ['', 'Yardage / Reception Props', 'Over/under lines'],
  ['td', 'Anytime TD Props', 'Exploratory · lower confidence'],
]

export default function PropsSection({ sub }) {
  const tab = sub === 'td' ? 'td' : ''
  const tabs = (
    <div className="props-tabs" role="tablist" aria-label="Props lists">
      {TABS.map(([key, label, hint]) => (
        <button
          key={key || 'yards'}
          role="tab"
          aria-selected={tab === key}
          className={tab === key ? 'active' : ''}
          onClick={() => {
            window.location.hash = key ? `#/nfl/props/${key}` : '#/nfl/props'
          }}
        >
          <span>{label}</span>
          <em className={key === 'td' ? 'exp' : ''}>{hint}</em>
        </button>
      ))}
    </div>
  )
  return tab === 'td' ? <TdPropsPage tabs={tabs} /> : <PropsPage tabs={tabs} />
}
