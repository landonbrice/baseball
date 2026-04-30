const LABELS = { 1: 'Sensitive', 2: 'Standard', 3: 'Resilient' }

const TOOLTIP =
  'How much tolerance this pitcher has for training stress before signals ' +
  'should concern us. Sensitive pitchers have narrow tolerance bands; ' +
  'Resilient pitchers have broader bands.'

export default function TierLabel({ tier, baselineState, className = '' }) {
  if (!tier) return null
  const isDefault = tier === 2 && baselineState !== 'provisional'
  if (isDefault) return null
  const base = LABELS[tier] ?? 'Standard'
  const text = baselineState === 'provisional' ? `${base} (provisional)` : base
  return (
    <span
      className={`font-ui uppercase text-[10px] tracking-[0.12em] text-muted ${className}`}
      title={TOOLTIP}
    >
      {text}
    </span>
  )
}
