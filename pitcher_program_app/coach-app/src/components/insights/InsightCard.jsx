import { useNavigate } from 'react-router-dom'
import InsightActions from './InsightActions'

const BORDER_COLOR = {
  pre_start_nudge: 'var(--color-amber)',
  trend_warning: 'var(--color-crimson)',
  suggestion: 'var(--color-maroon)',
  fatigue_flag: 'var(--color-amber)',
  recovery_concern: 'var(--color-maroon)',
  // A4 — Plan 7 program-builder insight types
  program_drift: 'var(--color-amber)',
  program_flag_mismatch: 'var(--color-crimson)',
  team_program_lagging: 'var(--color-amber)',
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
  // A4 — Plan 7 program-builder insight types
  program_drift: 'Program Drift',
  program_flag_mismatch: 'Program Mismatch',
  team_program_lagging: 'Team Lag',
}

// Categories that show standard Accept/Dismiss/Defer actions. Program-builder
// insight types (A4) instead surface navigation CTAs — Accept/Dismiss wiring
// for those is Plan 8 work.
const STANDARD_ACTION_CATEGORIES = new Set([
  'pre_start_nudge',
  'fatigue_flag',
  'recovery_concern',
  'trend_warning',
  'suggestion',
])

function ProgramInsightActions({ category, suggestion }) {
  const navigate = useNavigate()
  const ctx = suggestion.proposed_action || {}

  if (category === 'program_drift') {
    // v1: no-op buttons so the visual lands; archive/accept wiring lives in Plan 8.
    return (
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => {
            // TODO(plan-8): wire archive-program action for drift insight
          }}
          className="px-3 py-1.5 bg-maroon text-bone font-ui font-semibold text-body-sm rounded-[3px] hover:opacity-90"
        >
          Archive program
        </button>
        <button
          type="button"
          onClick={() => {
            // TODO(plan-8): wire accept-new-pace action for drift insight
          }}
          className="font-ui text-body-sm text-subtle hover:text-charcoal"
        >
          Accept new pace
        </button>
      </div>
    )
  }

  if (category === 'program_flag_mismatch') {
    return (
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() =>
            navigate('/', { state: { openPitcherId: suggestion.pitcher_id || ctx.pitcher_id } })
          }
          className="px-3 py-1.5 bg-maroon text-bone font-ui font-semibold text-body-sm rounded-[3px] hover:opacity-90"
        >
          Open Programs
        </button>
      </div>
    )
  }

  if (category === 'team_program_lagging') {
    return (
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => navigate('/programs')}
          className="px-3 py-1.5 bg-maroon text-bone font-ui font-semibold text-body-sm rounded-[3px] hover:opacity-90"
        >
          Open Team Programs
        </button>
      </div>
    )
  }

  return null
}

export default function InsightCard({ suggestion, variant = 'hero', onAccept, onDismiss, onDefer }) {
  const typeLabel = TYPE_LABEL[suggestion.category] || suggestion.category
  const isProgramInsight = !STANDARD_ACTION_CATEGORIES.has(suggestion.category)

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
      {isProgramInsight ? (
        <ProgramInsightActions category={suggestion.category} suggestion={suggestion} />
      ) : (
        <InsightActions onAccept={onAccept} onDismiss={onDismiss} onDefer={onDefer} />
      )}
    </div>
  )
}
