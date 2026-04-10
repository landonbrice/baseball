import { useState } from 'react'

export default function BlockCard({ block, onAssign, onEnd, isActive }) {
  const [expanded, setExpanded] = useState(false)
  const phases = block.content?.phases || []

  return (
    <div className="bg-white rounded-lg border border-cream-dark p-4">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-sm font-bold text-charcoal">{block.name}</h3>
          <p className="text-xs text-subtle mt-0.5">{block.description}</p>
          <div className="flex gap-2 mt-2">
            <span className="text-xs bg-cream rounded px-2 py-0.5">{block.block_type}</span>
            <span className="text-xs bg-cream rounded px-2 py-0.5">{block.duration_days} days</span>
            {block.content?.throws_per_week && (
              <span className="text-xs bg-cream rounded px-2 py-0.5">{block.content.throws_per_week}x/week</span>
            )}
          </div>
        </div>
        {isActive ? (
          <button onClick={() => onEnd?.(block.block_id)}
            className="text-xs px-3 py-1 border border-crimson text-crimson rounded hover:bg-crimson/10">
            End Block
          </button>
        ) : (
          <button onClick={() => onAssign?.(block)}
            className="text-xs px-3 py-1 bg-maroon text-white rounded hover:bg-maroon-light">
            Assign
          </button>
        )}
      </div>

      {/* Preview toggle */}
      <button onClick={() => setExpanded(!expanded)} className="text-xs text-maroon mt-2 hover:underline">
        {expanded ? 'Hide preview' : 'Preview phases'}
      </button>

      {expanded && phases.length > 0 && (
        <div className="mt-3 space-y-2 border-t border-cream-dark pt-2">
          {phases.map((p, i) => (
            <div key={i} className="bg-cream rounded p-2">
              <p className="text-xs font-medium text-charcoal">{p.name}</p>
              <p className="text-[10px] text-subtle">
                Weeks {p.weeks?.join(', ')} · {p.effort_pct}% effort · {p.distances?.join(', ')}
              </p>
              {p.intent_notes && <p className="text-[10px] text-subtle italic mt-0.5">{p.intent_notes}</p>}
            </div>
          ))}
        </div>
      )}

      {isActive && (
        <div className="mt-2 text-xs text-subtle">
          Started: {block.start_date} · Status: {block.status}
        </div>
      )}
    </div>
  )
}
