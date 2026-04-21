export default function GameCard({ game, starterName, onClick }) {
  const date = new Date(game.game_date + 'T12:00:00')
  const weekday = date.toLocaleDateString('en-US', { weekday: 'long', timeZone: 'America/Chicago' })
  const dateStr = date.toLocaleDateString('en-US', { month: 'long', day: 'numeric', timeZone: 'America/Chicago' })

  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full text-left bg-bone border border-cream-dark rounded-[3px] p-4 hover:bg-cream/50 transition-colors"
    >
      <div className="flex items-start justify-between">
        <div>
          <h2 className="font-serif font-bold text-h2 text-charcoal">
            {game.home_away === 'home' ? 'vs' : '@'} {game.opponent}
          </h2>
          <p className="font-ui text-body-sm text-subtle mt-0.5">{weekday} · {dateStr}</p>
          {game.game_time && (
            <p className="font-ui text-meta text-muted mt-0.5">{game.game_time}</p>
          )}
        </div>
        <span
          className="font-ui text-meta font-semibold px-2 py-0.5 rounded-[2px] flex-shrink-0"
          style={{
            background: game.home_away === 'home' ? 'var(--color-parchment)' : 'var(--color-cream-dark)',
            color: 'var(--color-charcoal)',
          }}
        >
          {game.home_away === 'home' ? 'Home' : 'Away'}
        </span>
      </div>
      {starterName && (
        <p className="font-serif font-semibold text-body-sm text-maroon mt-2">SP: {starterName}</p>
      )}
    </button>
  )
}
