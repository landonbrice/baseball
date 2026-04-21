const FLAG_COLOR = {
  green: 'var(--color-forest)',
  yellow: 'var(--color-amber)',
  red: 'var(--color-crimson)',
}

const DAY_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

export default function WeekStrip({ roster = [], gameMap = {}, today }) {
  const todayDate = new Date(today + 'T12:00:00')
  const dayOfWeek = todayDate.getDay()
  // Start strip on Monday of current week
  const monday = new Date(todayDate)
  monday.setDate(todayDate.getDate() - (dayOfWeek === 0 ? 6 : dayOfWeek - 1))

  const days = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(monday)
    d.setDate(monday.getDate() + i)
    return d
  })

  return (
    <div className="flex border-y border-cream-dark overflow-x-auto">
      {days.map(d => {
        const dateStr = d.toLocaleDateString('en-CA', { timeZone: 'America/Chicago' })
        const isToday = dateStr === today
        const game = gameMap[dateStr]
        const dayLabel = game
          ? `${game.home_away === 'home' ? 'vs' : '@'} ${game.opponent}`
          : 'Rest'

        return (
          <div
            key={dateStr}
            className={`flex-1 min-w-[90px] px-2 py-2.5 border-r border-cream-dark last:border-r-0 ${isToday ? 'border-b-[2px]' : ''}`}
            style={isToday ? { borderBottomColor: 'var(--color-maroon)' } : {}}
          >
            <p className="font-ui text-eyebrow uppercase tracking-[0.16em] text-subtle">
              {DAY_NAMES[d.getDay()]}
            </p>
            <p className={`font-ui text-body-sm font-semibold mt-0.5 ${isToday ? 'text-maroon' : 'text-charcoal'}`}>
              {d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'America/Chicago' })}
            </p>
            {/* Cap at 12 dots — matches current active roster size. If staff grows beyond 12, add overflow +N badge. */}
            <div className="flex gap-0.5 mt-1.5 flex-wrap">
              {roster.slice(0, 12).map(p => (
                <span
                  key={p.pitcher_id}
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: FLAG_COLOR[p.current_flag_level] || 'var(--color-ghost)' }}
                  title={p.name}
                />
              ))}
            </div>
            <p className="font-ui text-micro text-subtle mt-1 truncate">{dayLabel}</p>
          </div>
        )
      })}
    </div>
  )
}
