export default function Scoreboard({ cells }) {
  if (!Array.isArray(cells) || cells.length !== 5) {
    throw new Error('<Scoreboard> requires exactly 5 cells')
  }
  return (
    <div className="bg-parchment border-y border-cream-dark grid grid-cols-5">
      {cells.map((cell, i) => (
        <div
          key={cell.label + i}
          className={`px-4 py-3.5 ${i < 4 ? 'border-r border-cream-dark' : ''}`}
        >
          <div className="font-ui font-semibold uppercase text-eyebrow tracking-[0.16em] text-muted">
            {cell.label}
          </div>
          <div className="scoreboard-value font-serif font-bold text-h1 text-charcoal mt-1">
            {cell.value == null ? <span className="text-muted">—</span> : cell.value}
          </div>
          {cell.sub && (
            <div className="font-ui text-meta text-muted mt-0.5">{cell.sub}</div>
          )}
        </div>
      ))}
    </div>
  )
}
