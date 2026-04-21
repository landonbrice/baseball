export default function LibraryCard({ block, onAssign }) {
  return (
    <div className="bg-bone border border-cream-dark rounded-[3px] p-3 flex items-center gap-3">
      <div className="flex-1">
        <h4 className="font-serif font-bold text-body text-charcoal">{block.name}</h4>
        <p className="font-ui text-meta text-subtle">
          {block.block_type} · {block.duration_days}d
          {block.content?.throws_per_week ? ` · ${block.content.throws_per_week}x/week` : ''}
        </p>
      </div>
      <button
        type="button"
        onClick={() => onAssign?.(block)}
        className="font-ui text-meta font-semibold text-bone bg-maroon px-2.5 py-1.5 rounded-[3px] hover:bg-maroon-ink flex-shrink-0"
      >
        Assign
      </button>
    </div>
  )
}
