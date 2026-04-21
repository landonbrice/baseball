import { useMemo, useState } from 'react'
import { useCoachApi } from '../hooks/useApi'
import Masthead from '../components/shell/Masthead'
import Scoreboard from '../components/shell/Scoreboard'
import EditorialState from '../components/shell/EditorialState'
import WeekStrip from '../components/schedule/WeekStrip'
import GameCard from '../components/schedule/GameCard'
import GamePanel from '../components/GamePanel'
import { TODAY } from '../utils/formatToday'

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

function isoToWeekday(dateStr) {
  return WEEKDAYS[new Date(dateStr + 'T12:00:00').getDay()]
}

export default function Schedule() {
  const [selectedGame, setSelectedGame] = useState(null)
  const today = new Date().toLocaleDateString('en-CA', { timeZone: 'America/Chicago' })

  const rangeStart = new Date(today + 'T12:00:00')
  rangeStart.setDate(rangeStart.getDate() - 14)
  const rangeEnd = new Date(today + 'T12:00:00')
  rangeEnd.setDate(rangeEnd.getDate() + 28)

  const { data, loading, error, refetch } = useCoachApi(
    `/api/coach/schedule?start=${rangeStart.toLocaleDateString('en-CA')}&end=${rangeEnd.toLocaleDateString('en-CA')}`
  )
  const { data: overviewData } = useCoachApi('/api/coach/team/overview')

  const games = data?.games || []
  const roster = overviewData?.roster || []

  const gameMap = useMemo(() => {
    const m = {}
    for (const g of games) m[g.game_date] = g
    return m
  }, [games])

  const futureGames = useMemo(
    () => games.filter(g => g.game_date >= today).sort((a, b) => a.game_date.localeCompare(b.game_date)),
    [games, today]
  )

  const nextGame = futureGames[0] || null
  const nextStart = futureGames.find(g => g.starting_pitcher_id) || null

  const slate14End = new Date(today + 'T12:00:00')
  slate14End.setDate(slate14End.getDate() + 14)
  const slate14 = games.filter(
    g => g.game_date >= today && g.game_date <= slate14End.toLocaleDateString('en-CA')
  )

  const scoreboard = !data ? null : [
    {
      label: 'Next Start',
      value: nextStart ? isoToWeekday(nextStart.game_date) : '—',
      sub: nextStart
        ? `${roster.find(r => r.pitcher_id === nextStart.starting_pitcher_id)?.name || '—'} · ${nextStart.home_away === 'home' ? 'vs' : '@'} ${nextStart.opponent}`
        : 'None assigned',
    },
    {
      label: 'Next Game',
      value: nextGame
        ? new Date(nextGame.game_date + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'America/Chicago' })
        : '—',
      sub: nextGame ? `${nextGame.opponent} · ${nextGame.home_away}` : '—',
    },
    { label: 'Week BPs', value: '—', sub: 'data pending' },
    { label: 'Week Throws', value: '—', sub: 'data pending' },
    {
      label: '14-Day Slate',
      value: `${slate14.length}g`,
      sub: `${slate14.filter(g => g.home_away === 'home').length}h · ${slate14.filter(g => g.home_away === 'away').length}a`,
    },
  ]

  return (
    <>
      <Masthead kicker="Chicago · Pitching Staff" title="Schedule" date={TODAY} />
      {scoreboard && <Scoreboard cells={scoreboard} />}
      <WeekStrip roster={roster} gameMap={gameMap} today={today} />

      <div className="p-6">
        {loading && <EditorialState type="loading" copy="Loading schedule…" />}
        {error && <EditorialState type="error" copy={error} retry={refetch} />}

        {!loading && !error && futureGames.length === 0 && (
          <EditorialState type="empty" copy="No upcoming games scheduled." />
        )}

        {!loading && futureGames.length > 0 && (
          <div className="space-y-2">
            <p className="font-ui text-eyebrow uppercase tracking-[0.2em] text-maroon mb-3">
              Upcoming Games
            </p>
            {futureGames.map(g => (
              <GameCard
                key={g.game_id}
                game={g}
                starterName={g.starting_pitcher_id
                  ? roster.find(r => r.pitcher_id === g.starting_pitcher_id)?.name || null
                  : null}
                onClick={() => setSelectedGame(g)}
              />
            ))}
          </div>
        )}
      </div>

      {selectedGame && (
        <>
          <div className="fixed inset-0 bg-black/20 z-40" onClick={() => setSelectedGame(null)} />
          <GamePanel
            game={selectedGame}
            roster={roster}
            onClose={() => setSelectedGame(null)}
            onUpdated={() => { setSelectedGame(null); refetch() }}
          />
        </>
      )}
    </>
  )
}
