export default function Masthead({ kicker, title, date, week, actionSlot }) {
  return (
    <header className="bg-parchment border-b-2 border-maroon px-6 pt-5 pb-3.5 mb-3.5">
      <div className="flex items-end justify-between gap-4">
        <div>
          <div className="font-ui font-semibold uppercase text-kicker tracking-[0.2em] text-maroon">
            {kicker}
          </div>
          <h1
            className="font-serif font-bold text-display text-charcoal mt-1"
            style={{ letterSpacing: '-0.015em' }}
          >
            {title}
          </h1>
        </div>
        <div className="flex items-end gap-4">
          <div className="text-right">
            <div className="font-ui text-meta text-muted">{date}</div>
            {week && (
              <div className="font-ui text-body-sm font-semibold text-charcoal mt-0.5">
                {week}
              </div>
            )}
          </div>
          {actionSlot && <div>{actionSlot}</div>}
        </div>
      </div>
    </header>
  )
}
