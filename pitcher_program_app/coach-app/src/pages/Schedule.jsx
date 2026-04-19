import { useState, useMemo } from 'react'
import { useCoachApi } from '../hooks/useApi'
import GamePanel from '../components/GamePanel'
import Masthead from '../components/shell/Masthead'
import { TODAY } from '../utils/formatToday'

function getMonthDays(year, month) {
  const firstDay = new Date(year, month, 1).getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const days = []
  for (let i = 0; i < firstDay; i++) days.push(null)
  for (let d = 1; d <= daysInMonth; d++) days.push(d)
  return days
}

function formatDate(year, month, day) {
  return `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

export default function Schedule() {
  const [year, setYear] = useState(2026)
  const [month, setMonth] = useState(3) // April = index 3
  const [selectedGame, setSelectedGame] = useState(null)

  const start = formatDate(year, month, 1)
  const end = formatDate(year, month, new Date(year, month + 1, 0).getDate())
  const { data, loading, refetch } = useCoachApi(`/api/coach/schedule?start=${start}&end=${end}`)
  const { data: overviewData } = useCoachApi('/api/coach/team/overview')

  const games = data?.games || []
  const roster = overviewData?.roster || []

  const gameMap = useMemo(() => {
    const m = {}
    for (const g of games) m[g.game_date] = g
    return m
  }, [games])

  const days = getMonthDays(year, month)

  function prevMonth() {
    if (month === 0) { setYear(y => y - 1); setMonth(11) }
    else setMonth(m => m - 1)
  }
  function nextMonth() {
    if (month === 11) { setYear(y => y + 1); setMonth(0) }
    else setMonth(m => m + 1)
  }

  return (
    <>
      <Masthead kicker="Chicago · Pitching Staff" title="Schedule" date={TODAY} />
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-bold text-charcoal">Schedule</h2>
          <div className="flex items-center gap-3">
            <button onClick={prevMonth} className="text-subtle hover:text-charcoal">&larr;</button>
            <span className="text-sm font-medium text-charcoal">{MONTHS[month]} {year}</span>
            <button onClick={nextMonth} className="text-subtle hover:text-charcoal">&rarr;</button>
          </div>
        </div>

        {loading ? <p className="text-subtle">Loading schedule...</p> : (
          <div className="bg-white rounded-lg border border-cream-dark overflow-hidden">
            <div className="grid grid-cols-7 text-center text-xs text-subtle font-medium bg-cream">
              {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(d => (
                <div key={d} className="py-2">{d}</div>
              ))}
            </div>
            <div className="grid grid-cols-7">
              {days.map((day, i) => {
                if (!day) return <div key={i} className="h-20 border-t border-cream-dark bg-cream/30" />
                const dateStr = formatDate(year, month, day)
                const game = gameMap[dateStr]
                const isToday = dateStr === new Date().toLocaleDateString('en-CA', { timeZone: 'America/Chicago' })

                return (
                  <div key={i}
                    onClick={() => game && setSelectedGame(game)}
                    className={`h-20 border-t border-cream-dark p-1.5 ${game ? 'cursor-pointer hover:bg-cream/50' : ''} ${isToday ? 'bg-maroon/5' : ''}`}>
                    <span className={`text-xs ${isToday ? 'font-bold text-maroon' : 'text-subtle'}`}>{day}</span>
                    {game && (
                      <div className="mt-1">
                        <p className="text-xs font-medium text-charcoal truncate">
                          {game.home_away === 'home' ? 'vs' : '@'} {game.opponent}
                        </p>
                        {game.starting_pitcher_id && (
                          <p className="text-[10px] text-maroon truncate">
                            {roster.find(r => r.pitcher_id === game.starting_pitcher_id)?.name || ''}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Upcoming starts strip */}
        {games.filter(g => g.starting_pitcher_id).length > 0 && (
          <div className="mt-4 bg-white rounded-lg border border-cream-dark p-4">
            <p className="text-xs text-subtle mb-2">Assigned Starters This Month</p>
            <div className="flex gap-3 flex-wrap">
              {games.filter(g => g.starting_pitcher_id).map(g => (
                <span key={g.game_id} className="text-xs bg-cream rounded px-2 py-1">
                  {g.game_date.slice(5)} — {roster.find(r => r.pitcher_id === g.starting_pitcher_id)?.name || 'TBD'}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Game panel */}
        {selectedGame && (
          <>
            <div className="fixed inset-0 bg-black/20 z-40" onClick={() => setSelectedGame(null)} />
            <GamePanel game={selectedGame} roster={roster} onClose={() => setSelectedGame(null)} onUpdated={() => { setSelectedGame(null); refetch() }} />
          </>
        )}
      </div>
    </>
  )
}
