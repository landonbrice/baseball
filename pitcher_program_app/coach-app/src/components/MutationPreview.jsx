export default function MutationPreview({ proposed }) {
  if (!proposed) return null
  const {
    exercise_rationale_diff = [],
    day_summary_before,
    day_summary_after,
  } = proposed

  const hasDay = Boolean(day_summary_before || day_summary_after)
  const hasDiff = exercise_rationale_diff.length > 0
  if (!hasDay && !hasDiff) return null

  return (
    <div className="border border-cream-dark rounded-[3px] p-3 bg-parchment font-ui text-meta text-charcoal space-y-2">
      <div className="font-semibold uppercase tracking-[0.16em] text-[10px] text-muted">
        Preview
      </div>
      {hasDay && (
        <div className="space-y-0.5">
          {day_summary_before && (
            <div className="text-muted line-through">{day_summary_before}</div>
          )}
          {day_summary_after && (
            <div className="text-charcoal">{day_summary_after}</div>
          )}
        </div>
      )}
      {hasDiff && (
        <ul className="space-y-1">
          {exercise_rationale_diff.map((d) => (
            <li key={d.exercise_id} className="leading-snug">
              <span className="text-muted">{d.exercise_id}: </span>
              <span className="text-muted line-through">{d.before || '—'}</span>
              <span className="mx-1">→</span>
              <span className="text-charcoal">{d.after || '—'}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
