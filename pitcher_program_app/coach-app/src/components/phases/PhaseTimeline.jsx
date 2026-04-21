const EMPHASIS_BORDER = {
  hypertrophy: 'var(--color-maroon-ink)',
  strength: 'var(--color-maroon)',
  power: 'var(--color-crimson)',
  maintenance: 'var(--color-forest)',
  gpp: 'var(--color-amber)',
}

export default function PhaseTimeline({ phases, onSelect }) {
  if (!phases || phases.length === 0) return null

  const today = new Date().toLocaleDateString('en-CA', { timeZone: 'America/Chicago' })

  return (
    <div className="flex gap-1.5 overflow-x-auto pb-3" role="list">
      {phases.map(p => {
        const isCurrent = today >= p.start_date && today <= p.end_date
        const borderColor = EMPHASIS_BORDER[p.emphasis] || 'var(--color-graphite)'
        const days = Math.max(1, Math.round(
          (new Date(p.end_date) - new Date(p.start_date)) / 86400000
        ))
        const width = Math.max(100, days * 2)

        return (
          <button
            key={p.phase_block_id}
            type="button"
            role="listitem"
            onClick={() => onSelect?.(p)}
            className="group relative flex-shrink-0 bg-cream rounded-[3px] p-3 cursor-pointer hover:bg-cream-dark/50 transition-colors text-left"
            style={{
              width: `${width}px`,
              borderLeft: `3px solid ${borderColor}`,
              borderBottom: isCurrent ? `2px solid var(--color-maroon)` : undefined,
            }}
          >
            <p className={`font-serif font-bold text-body truncate ${isCurrent ? 'text-maroon' : 'text-charcoal'}`}>
              {p.phase_name}
            </p>
            <p className="font-ui text-micro text-subtle whitespace-nowrap">
              {p.start_date} — {p.end_date}
            </p>
            <p className="font-ui text-meta text-subtle capitalize">{p.emphasis}</p>
            <span className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity font-ui text-meta text-subtle">
              ✏
            </span>
          </button>
        )
      })}
    </div>
  )
}
