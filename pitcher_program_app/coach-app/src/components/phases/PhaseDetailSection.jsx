export default function PhaseDetailSection({ phase, title = 'Current Phase' }) {
  if (!phase) return null

  const start = new Date(phase.start_date + 'T12:00:00')
  const end = new Date(phase.end_date + 'T12:00:00')
  const totalWeeks = Math.max(1, Math.round((end - start) / (7 * 86400000)))
  const elapsedWeeks = Math.max(0, Math.floor((Date.now() - start) / (7 * 86400000)))
  const currentWeek = Math.min(totalWeeks, elapsedWeeks + 1)

  return (
    <div className="border-t border-cream-dark pt-6">
      <p className="font-ui text-eyebrow uppercase tracking-[0.2em] text-maroon mb-2">{title}</p>
      <h2 className="font-serif font-bold text-h1 text-charcoal mb-1">{phase.phase_name}</h2>
      {phase.notes && (
        <p className="font-serif italic text-body text-graphite border-l-2 border-maroon pl-3 mb-4">
          {phase.notes}
        </p>
      )}
      <div className="flex gap-6 flex-wrap">
        <div>
          <p className="font-ui text-eyebrow uppercase tracking-[0.16em] text-subtle">Duration</p>
          <p className="font-ui font-semibold text-body text-charcoal mt-0.5">{totalWeeks}w</p>
        </div>
        <div>
          <p className="font-ui text-eyebrow uppercase tracking-[0.16em] text-subtle">Emphasis</p>
          <p className="font-ui font-semibold text-body text-charcoal mt-0.5 capitalize">{phase.emphasis || '—'}</p>
        </div>
        <div>
          <p className="font-ui text-eyebrow uppercase tracking-[0.16em] text-subtle">Week</p>
          <p className="font-ui font-semibold text-body text-charcoal mt-0.5">{currentWeek} / {totalWeeks}</p>
        </div>
        {phase.target_weekly_load && (
          <div>
            <p className="font-ui text-eyebrow uppercase tracking-[0.16em] text-subtle">Target Load</p>
            <p className="font-ui font-semibold text-body text-charcoal mt-0.5">{phase.target_weekly_load} throws/wk</p>
          </div>
        )}
      </div>
    </div>
  )
}
