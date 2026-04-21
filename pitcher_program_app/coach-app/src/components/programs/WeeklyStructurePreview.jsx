export default function WeeklyStructurePreview({ block }) {
  const phases = block?.content?.phases || []
  if (phases.length === 0) {
    return <p className="font-ui text-body-sm text-subtle italic">No weekly structure for this block.</p>
  }
  return (
    <div className="space-y-3 max-h-48 overflow-y-auto">
      {phases.map((phase, i) => (
        <div key={i} className="border-l-2 border-maroon pl-3">
          <h4 className="font-serif font-bold text-body text-charcoal">{phase.name}</h4>
          <p className="font-ui text-meta text-subtle">
            Weeks {phase.weeks?.join(', ')} · {phase.effort_pct}% effort
          </p>
          {phase.distances && (
            <p className="font-ui text-meta text-muted">{phase.distances.join(', ')}</p>
          )}
          {phase.intent_notes && (
            <p className="font-serif italic text-meta text-subtle">{phase.intent_notes}</p>
          )}
        </div>
      ))}
    </div>
  )
}
