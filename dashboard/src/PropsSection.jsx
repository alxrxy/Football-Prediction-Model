import PropsPage from './PropsPage.jsx'
import TdPropsPage from './TdPropsPage.jsx'

// The props section: two separate lists behind one toggle.
//   #/nfl/props       yardage / reception props (props.json)
//   #/nfl/props/td    anytime TD props (td_props.json), exploratory
// They share nothing but the section: separate data files, rankings and caveats.
//
// WIRED IN 2026-09-20, once the usage fixes it was waiting on had shipped
// (P23/P24 scrambles, P25 k32+fb, P26 offsets, P27 throwaways) and the lines
// were re-pulled against the live engine. The TD list stays labelled
// "exploratory": P18 (goal-line conversion) is still open and the engine runs
// ~8.3% hot on touchdowns with no bias correction fitted for this market.
// See src/td_props.py for the current caveats; they are served in `note`.

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
