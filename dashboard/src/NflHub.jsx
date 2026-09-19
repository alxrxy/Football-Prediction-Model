import { useEffect, useState } from 'react'
import GamesPage from './GamesPage.jsx'
import GameView from './GameView.jsx'
import PropsPage from './PropsPage.jsx'
import LivePage from './LivePage.jsx'
import PastWeeks from './PastWeeks.jsx'
import RecordPage from './RecordPage.jsx'
import { liveGamesOf, useLive } from './simData.js'
import './hub.css'

// The NFL tab: three full-page sections, plus the track record.
//   #/nfl/games          every game of the week; #/nfl/game/<id> opens one
//   #/nfl/props          best props of the week
//   #/nfl/live           games in progress
//   #/nfl/record         track record and backtest
//   #/nfl/past           finished weeks, projected vs actual
// Routes live in the URL hash so the browser's back button works.

const SECTIONS = [
  ['games', 'Games', 'Every game of the week, simulated'],
  ['props', 'Props', 'Best player props, explained'],
  ['live', 'Live', 'Games in progress'],
]

const parse = () => {
  const parts = window.location.hash.replace(/^#\/?/, '').split('/')
  if (parts[1] === 'game' && parts[2]) return { section: 'games', gameId: decodeURIComponent(parts[2]) }
  return { section: parts[1] || 'games', gameId: null }
}

export default function NflHub({ sport }) {
  const [route, setRoute] = useState(parse)
  useEffect(() => {
    const onHash = () => {
      setRoute(parse())
      window.scrollTo({ top: 0 })
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  const go = (path) => {
    window.location.hash = `#/nfl/${path}`
  }
  const feed = useLive(true)
  const live = liveGamesOf(feed)

  return (
    <div className="hub">
      <nav className="hub-nav" aria-label="NFL sections">
        {SECTIONS.map(([key, label, hint]) => (
          <button
            key={key}
            className={route.section === key ? 'active' : ''}
            aria-current={route.section === key ? 'page' : undefined}
            onClick={() => go(key)}
          >
            <span className="hub-label">
              {label}
              {key === 'live' && live.length ? (
                <span className="live-count">
                  <span className="pulse" aria-hidden="true" />
                  {live.length}
                </span>
              ) : null}
            </span>
            <em>{hint}</em>
          </button>
        ))}
        <button
          className={`record ${route.section === 'record' ? 'active' : ''}`}
          aria-current={route.section === 'record' ? 'page' : undefined}
          onClick={() => go('record')}
        >
          <span className="hub-label">Record</span>
          <em>How the models are doing</em>
        </button>
        <button
          className={`record ${route.section === 'past' ? 'active' : ''}`}
          aria-current={route.section === 'past' ? 'page' : undefined}
          onClick={() => go('past')}
        >
          <span className="hub-label">Past weeks</span>
          <em>Projected vs actual</em>
        </button>
      </nav>

      {route.gameId ? (
        <GameView sport={sport} gameId={route.gameId} feed={feed} onBack={() => go('games')} onPast={() => go('past')} />
      ) : route.section === 'props' ? (
        <PropsPage />
      ) : route.section === 'live' ? (
        <LivePage feed={feed} sport={sport} onOpen={(id) => go(`game/${encodeURIComponent(id)}`)} />
      ) : route.section === 'record' ? (
        <RecordPage sport={sport} />
      ) : route.section === 'past' ? (
        <PastWeeks />
      ) : (
        <GamesPage sport={sport} feed={feed} onOpen={(id) => go(`game/${encodeURIComponent(id)}`)} />
      )}
    </div>
  )
}
