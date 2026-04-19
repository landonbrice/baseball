const STATUS_CLASS = {
  checked_in: 'bg-forest',
  partial: 'bg-amber',
  none: 'bg-cream-dark',
}

export default function LastSevenStrip({ days = [] }) {
  return (
    <div className="flex gap-1" aria-label="Last 7 days">
      {days.map((d, i) => (
        <span
          key={d.date || i}
          className={`inline-block w-2 h-2 rounded-full ${STATUS_CLASS[d.status] || STATUS_CLASS.none}`}
          title={`${d.date}: ${d.status}`}
        />
      ))}
    </div>
  )
}
