import { useState } from 'react'
import { postCoachApi } from '../api'
import { useCoachAuth } from '../hooks/useCoachAuth'

const CATEGORY_LABELS = {
  pre_start_nudge: 'Pre-Start',
  fatigue_flag: 'Fatigue Alert',
  recovery_concern: 'Recovery',
  progression_opportunity: 'Progression',
}

export default function InsightCard({ suggestion, onResolved }) {
  const { getAccessToken } = useCoachAuth()
  const [acting, setActing] = useState(false)

  async function handleAccept() {
    setActing(true)
    try {
      await postCoachApi(`/api/coach/insights/${suggestion.suggestion_id}/accept`, {}, getAccessToken())
      onResolved?.()
    } catch (err) {
      alert(err.message)
    } finally {
      setActing(false)
    }
  }

  async function handleDismiss() {
    setActing(true)
    try {
      await postCoachApi(`/api/coach/insights/${suggestion.suggestion_id}/dismiss`, {}, getAccessToken())
      onResolved?.()
    } catch (err) {
      alert(err.message)
    } finally {
      setActing(false)
    }
  }

  const categoryLabel = CATEGORY_LABELS[suggestion.category] || suggestion.category

  return (
    <div className="bg-white rounded-lg border border-cream-dark p-4">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber/20 text-amber font-medium">
              {categoryLabel}
            </span>
          </div>
          <h3 className="text-sm font-medium text-charcoal">{suggestion.title}</h3>
          <p className="text-xs text-subtle mt-1 leading-relaxed">{suggestion.reasoning}</p>
          {suggestion.proposed_action && (
            <p className="text-xs text-maroon mt-2 font-medium">{suggestion.proposed_action.description}</p>
          )}
        </div>
      </div>
      <div className="flex gap-2 mt-3">
        <button onClick={handleAccept} disabled={acting}
          className="px-3 py-1.5 bg-forest text-white rounded text-xs font-medium hover:opacity-90 disabled:opacity-50">
          Accept
        </button>
        <button onClick={handleDismiss} disabled={acting}
          className="px-3 py-1.5 border border-cream-dark text-subtle rounded text-xs hover:text-charcoal disabled:opacity-50">
          Dismiss
        </button>
      </div>
    </div>
  )
}
