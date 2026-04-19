export default function PendingStrip({ pending, nudgeEnabled = false }) {
  if (!Array.isArray(pending) || pending.length === 0) return null

  return (
    <div className="border border-dashed border-cream-dark bg-black/[0.03] rounded-[3px] px-3.5 py-2.5 flex items-center gap-3 flex-wrap">
      <span className="font-ui font-semibold uppercase text-[9px] tracking-[0.16em] text-amber">
        Awaiting check-in
      </span>
      {pending.map(p => (
        <span key={p.pitcher_id} className="flex items-center gap-1.5">
          <span className="font-ui text-body-sm text-charcoal">{p.name}</span>
          <span className="font-ui text-meta text-muted">
            {typeof p.hours_since_last === 'number' ? `${p.hours_since_last}h ago` : ''}
          </span>
          <button
            type="button"
            disabled={!nudgeEnabled}
            title={nudgeEnabled ? 'Send a reminder' : 'Backend pending (Spec 3)'}
            className="font-ui text-meta font-semibold text-maroon hover:text-maroon-ink disabled:text-muted disabled:cursor-not-allowed"
          >
            Nudge →
          </button>
        </span>
      ))}
    </div>
  )
}
