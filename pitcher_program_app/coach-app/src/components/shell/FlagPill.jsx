const STYLES = {
  red:     { className: 'bg-crimson text-bone',                          label: 'Red' },
  yellow:  { className: 'bg-amber text-charcoal',                        label: 'Yellow' },
  green:   { className: 'bg-forest text-bone',                           label: 'Green' },
  pending: { className: 'bg-transparent border border-ghost text-ghost', label: 'Pending' },
}

export default function FlagPill({ level }) {
  const style = STYLES[level] || STYLES.pending
  return (
    <span
      className={`inline-block font-ui font-semibold uppercase rounded-[2px] px-[7px] py-[3px] tracking-[0.12em] text-[9px] leading-none ${style.className}`}
    >
      {style.label}
    </span>
  )
}
