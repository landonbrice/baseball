const EMPHASIS_COLORS = {
  hypertrophy: '#7a1a2e',
  strength: '#5c1020',
  power: '#c0392b',
  maintenance: '#2d5a3d',
  gpp: '#d4a017',
}

export default function PhaseTimeline({ phases, onSelect }) {
  if (!phases || phases.length === 0) {
    return <p className="text-sm text-subtle">No phases defined.</p>
  }

  const today = new Date().toLocaleDateString('en-CA', { timeZone: 'America/Chicago' })

  return (
    <div className="flex gap-1 overflow-x-auto pb-2">
      {phases.map(p => {
        const isCurrent = today >= p.start_date && today <= p.end_date
        const color = EMPHASIS_COLORS[p.emphasis] || '#7a7a7a'
        const start = new Date(p.start_date)
        const end = new Date(p.end_date)
        const days = Math.max(1, Math.round((end - start) / 86400000))
        const width = Math.max(80, days * 2.5)

        return (
          <div
            key={p.phase_block_id}
            onClick={() => onSelect?.(p)}
            className={`rounded-lg p-2 cursor-pointer flex-shrink-0 ${isCurrent ? 'ring-2 ring-offset-1' : ''}`}
            style={{
              backgroundColor: color + '15',
              borderLeft: `3px solid ${color}`,
              width: `${width}px`,
              ringColor: color,
            }}
          >
            <p className="text-xs font-medium truncate" style={{ color }}>
              {p.phase_name}
            </p>
            <p className="text-[10px] text-subtle whitespace-nowrap">
              {p.start_date} — {p.end_date}
            </p>
            <p className="text-[10px] text-subtle capitalize">{p.emphasis}</p>
          </div>
        )
      })}
    </div>
  )
}
