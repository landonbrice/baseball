export default function BlockCard({ block, isActive, onEnd, onAssign, onViewDetails }) {
  const weeksElapsed = isActive && block.start_date
    ? Math.floor((Date.now() - new Date(block.start_date).getTime()) / (7 * 86400000))
    : 0
  const totalWeeks = block.duration_days ? Math.round(block.duration_days / 7) : null
  const weeksRemaining = totalWeeks ? Math.max(0, totalWeeks - weeksElapsed) : null
  const progressPct = totalWeeks ? Math.min(100, Math.round((weeksElapsed / totalWeeks) * 100)) : 0

  return (
    <div className="bg-bone border border-cream-dark rounded-[3px] p-3.5">
      <div className="flex items-start justify-between mb-2">
        <h3 className="font-serif font-bold text-h2 text-charcoal leading-tight flex-1 pr-2">
          {block.name}
        </h3>
        <span className="font-ui text-eyebrow uppercase tracking-[0.16em] text-maroon flex-shrink-0">
          {block.block_type}
        </span>
      </div>

      {isActive && totalWeeks && (
        <>
          <div className="w-full h-[3px] bg-cream-dark rounded-full mb-1.5">
            <div
              className="h-full rounded-full"
              style={{ width: `${progressPct}%`, backgroundColor: 'var(--color-maroon)' }}
            />
          </div>
          <p className="font-ui text-meta text-subtle mb-2">
            {weeksElapsed}w elapsed · {weeksRemaining}w remaining
          </p>
        </>
      )}

      {block.description && (
        <p className="font-ui text-body-sm text-subtle mb-2">{block.description}</p>
      )}

      <div className="flex items-center gap-2 mt-2">
        {isActive ? (
          <button
            type="button"
            onClick={() => onEnd?.(block.block_id)}
            className="font-ui text-meta font-semibold text-crimson border border-crimson px-2 py-1 rounded-[3px] hover:bg-crimson/10"
          >
            End Block
          </button>
        ) : (
          <button
            type="button"
            onClick={() => onAssign?.(block)}
            className="font-ui text-meta font-semibold text-bone bg-maroon px-2 py-1 rounded-[3px] hover:bg-maroon-ink"
          >
            Assign
          </button>
        )}
        {onViewDetails && (
          <button
            type="button"
            onClick={() => onViewDetails(block)}
            className="font-ui text-meta text-maroon hover:underline"
          >
            View details
          </button>
        )}
      </div>
    </div>
  )
}
