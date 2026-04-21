import InsightActions from './InsightActions'

const BORDER_COLOR = {
  pre_start_nudge: 'var(--color-amber)',
  trend_warning: 'var(--color-crimson)',
  suggestion: 'var(--color-maroon)',
  fatigue_flag: 'var(--color-amber)',
  recovery_concern: 'var(--color-maroon)',
}

const STATUS_BORDER = {
  accepted: 'var(--color-forest)',
  dismissed: 'var(--color-ghost)',
}

const TYPE_LABEL = {
  pre_start_nudge: 'Pre-Start',
  fatigue_flag: 'Fatigue Alert',
  recovery_concern: 'Recovery',
  trend_warning: 'Trend Warning',
  suggestion: 'General',
}

export default function InsightCard({ suggestion, variant = 'hero', onAccept, onDismiss, onDefer }) {
  const typeLabel = TYPE_LABEL[suggestion.category] || suggestion.category

  if (variant === 'compact') {
    const ts = suggestion.created_at
      ? new Date(suggestion.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
      : ''
    return (
      <div
        className="flex items-center gap-3 py-1.5 px-3 bg-bone rounded-[3px]"
        style={{ borderLeft: `3px solid ${STATUS_BORDER[suggestion.status] || 'var(--color-ghost)'}` }}
      >
        <span className="font-serif font-semibold text-body-sm text-charcoal truncate flex-1">
          {suggestion.pitcher_name || suggestion.pitcher_id}
        </span>
        <span className="font-ui text-meta text-subtle">{typeLabel}</span>
        <span className="font-ui text-meta text-muted capitalize">{suggestion.status}</span>
        {ts && <span className="font-ui text-micro text-ghost">{ts}</span>}
      </div>
    )
  }

  return (
    <div
      className="bg-bone border border-cream-dark rounded-[3px] p-4"
      style={{ borderLeft: `4px solid ${BORDER_COLOR[suggestion.category] || BORDER_COLOR.suggestion}` }}
    >
      <div className="flex items-center gap-2 mb-2">
        <span className="font-serif font-semibold text-body-sm bg-parchment px-2 py-0.5 rounded-[2px] text-charcoal">
          {suggestion.pitcher_name || suggestion.pitcher_id}
        </span>
        <span className="font-ui text-eyebrow uppercase tracking-[0.16em] text-subtle">
          {typeLabel}
        </span>
      </div>
      <h3 className="font-serif font-bold text-h2 text-charcoal mb-1">{suggestion.title}</h3>
      <p className="font-serif italic text-body text-graphite border-l-2 border-maroon pl-3 mb-3 leading-relaxed">
        {suggestion.reasoning}
      </p>
      {suggestion.proposed_action?.description && (
        <p className="font-ui text-body-sm text-maroon font-semibold mb-3">
          {suggestion.proposed_action.description}
        </p>
      )}
      <InsightActions onAccept={onAccept} onDismiss={onDismiss} onDefer={onDefer} />
    </div>
  )
}
