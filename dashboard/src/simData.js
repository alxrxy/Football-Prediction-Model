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

// A feed older than this means the tracker isn't running. Its last snapshot
// stays on disk and can still say "in progress" for a game that ended days ago.
export const LIVE_FRESH_MS = 10 * 60 * 1000
export const feedFresh = (feed) =>
  Boolean(feed?.generated_at) && Date.now() - new Date(feed.generated_at).getTime() < LIVE_FRESH_MS
export const liveGamesOf = (feed) => (feedFresh(feed) ? (feed.games || []).filter((g) => g.state === 'in') : [])
export const liveGame = (feed, gameId) => (feedFresh(feed) ? feed.games?.find((g) => g.game_id === gameId) : null)

export const findGame = (sims, gameId) =>
  sims?.slates?.flatMap((s) => s.games).find((g) => g.game_id === gameId) || null

// sims_archive/: finished weeks, one file each, plus index.json, written by
// export_sims. The index is read once per page load; a week file only when a
// game in it is opened.
let archiveIndex = null
const archiveWeeks = {}

export function loadArchiveIndex() {
  if (!archiveIndex) {
    archiveIndex = fetch(`./sims_archive/index.json?ts=${Date.now()}`, { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : { weeks: [] }))
      .catch(() => ({ weeks: [] }))
  }
  return archiveIndex
}

function loadArchiveWeek(file) {
  if (!archiveWeeks[file]) {
    archiveWeeks[file] = fetch(`./sims_archive/${file}`, { cache: 'no-store' }).then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      return r.json()
    })
    archiveWeeks[file].catch(() => {
      delete archiveWeeks[file]
    })
  }
  return archiveWeeks[file]
}

// One game's simulation entry: this week's sims.json first, then the archive
// of past weeks. `week` is set only for an archived game.
export function useSimEntry(gameId) {
  const { data, error } = useSims()
  const current = findGame(data, gameId)
  const [archived, setArchived] = useState(undefined)   // undefined: not looked yet
  const needArchive = Boolean(data) && !current
  useEffect(() => {
    if (!needArchive) return undefined
    let alive = true
    loadArchiveIndex()
      .then((idx) => {
        const week = (idx.weeks || []).find((w) => w.games.some((g) => g.game_id === gameId))
        if (!week) return alive && setArchived(null)
        return loadArchiveWeek(week.file).then((d) => alive && setArchived({ entry: findGame(d, gameId), week }))
      })
      .catch(() => alive && setArchived(null))
    return () => {
      alive = false
    }
  }, [needArchive, gameId])
  if (current) return { entry: current, week: null, loading: false, error: null }
  if (!data) return { entry: null, week: null, loading: !error, error }
  return { entry: archived?.entry || null, week: archived?.week || null, loading: archived === undefined, error: null }
}
