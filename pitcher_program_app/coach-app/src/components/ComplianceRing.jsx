export default function ComplianceRing({ checkedIn, total, size = 120 }) {
  const pct = total > 0 ? checkedIn / total : 0
  const r = (size - 12) / 2
  const circ = 2 * Math.PI * r
  const offset = circ * (1 - pct)

  return (
    <div className="flex flex-col items-center">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#e4dfd8" strokeWidth="10" />
          <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#5c1020" strokeWidth="10"
            strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
            style={{ transition: 'stroke-dashoffset 0.6s ease' }} />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-bold text-charcoal">{checkedIn}</span>
          <span className="text-xs text-subtle">of {total}</span>
        </div>
      </div>
    </div>
  )
}
