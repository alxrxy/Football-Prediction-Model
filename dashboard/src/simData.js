import { useEffect, useState } from 'react'

// sims.json: pregame projections and final results, written by
//   python -m src.export_sims
// live.json: the live tracker's latest poll, rewritten every ~2.5 minutes by
//   python -m src.live_tracker
// Both are relative to the page, like data.json.

const LIVE_REFRESH_MS = 20000
// sims.json changes when the live tracker re-exports it after a game goes
// final, so an open page re-reads it; one shared request serves every view.
const SIMS_REFRESH_MS = 120000
let simsRequest = null
let simsRequestedAt = 0

function loadSims() {
  if (!simsRequest || Date.now() - simsRequestedAt > SIMS_REFRESH_MS / 2) {
    simsRequestedAt = Date.now()
    simsRequest = fetch(`./sims.json?ts=${simsRequestedAt}`, { cache: 'no-store' }).then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      return r.json()
    })
    simsRequest.catch(() => {
      simsRequest = null
    })
  }
  return simsRequest
}

export function useSims() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => {
    let alive = true
    const load = () =>
      loadSims()
        .then((d) => {
          if (!alive) return
          setData(d)
          setError(null)
        })
        .catch((e) => alive && setError(e.message))
    load()
    const id = setInterval(load, SIMS_REFRESH_MS)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [])
  // A failed refresh keeps the copy already on screen; the error only shows
  // when there is nothing to show instead.
  return { data, error: data ? null : error }
}

// Polls live.json while `enabled`. A failed read keeps the previous copy.
export function useLive(enabled) {
  const [data, setData] = useState(null)
  useEffect(() => {
    if (!enabled) return undefined
    let alive = true
    const load = () =>
      fetch(`./live.json?ts=${Date.now()}`, { cache: 'no-store' })
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => {
          if (alive && d) setData(d)
        })
        .catch(() => {})
    load()
    const id = setInterval(load, LIVE_REFRESH_MS)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [enabled])
  return data
}

export const findGame = (sims, gameId) =>
  sims?.slates?.flatMap((s) => s.games).find((g) => g.game_id === gameId) || null
