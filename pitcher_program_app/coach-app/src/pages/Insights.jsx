import { useCoachApi } from '../hooks/useApi'
import { useCoachAuth } from '../hooks/useCoachAuth'
import { postCoachApi } from '../api'
import { useToast } from '../components/shell/Toast'
import Masthead from '../components/shell/Masthead'
import Scoreboard from '../components/shell/Scoreboard'
import EditorialState from '../components/shell/EditorialState'
import InsightCard from '../components/insights/InsightCard'
import { TODAY } from '../utils/formatToday'

export default function Insights() {
  const { data, loading, error, refetch } = useCoachApi('/api/coach/insights')
  const { getAccessToken } = useCoachAuth()
  const toast = useToast()

  const pending = data?.pending || []
  const recent = data?.recent || []
  const stats = data?.stats || {}

  const scoreboard = !data ? null : [
    {
      label: 'Pending',
      value: String(stats.pending_count ?? '—'),
      sub: stats.oldest_pending_days != null ? `${stats.oldest_pending_days}d oldest` : '—',
    },
    {
      label: 'Accepted 7d',
      value: String(stats.accepted_7d ?? '—'),
      sub: stats.total_7d ? `${stats.acceptance_rate_7d}% acceptance` : '—',
    },
    {
      label: 'Dismissed 7d',
      value: String(stats.dismissed_7d ?? '—'),
      sub: stats.total_7d ? `${100 - stats.acceptance_rate_7d}% dismissed` : '—',
    },
    {
      label: 'Acceptance Rate',
      value: stats.acceptance_rate_30d != null ? `${stats.acceptance_rate_30d}%` : '—',
      sub: 'rolling 30d',
    },
    {
      label: 'Oldest Pending',
      value: stats.oldest_pending_days != null ? `${stats.oldest_pending_days}d` : '—',
      sub: stats.oldest_pending_type || '—',
    },
  ]

  async function handleAccept(suggestionId) {
    try {
      await postCoachApi(`/api/coach/insights/${suggestionId}/accept`, {}, getAccessToken())
      toast.success('Insight accepted')
      refetch()
    } catch (err) {
      toast.error(err.message)
    }
  }

  async function handleDismiss(suggestionId) {
    try {
      await postCoachApi(`/api/coach/insights/${suggestionId}/dismiss`, {}, getAccessToken())
      toast.warn('Dismissed')
      refetch()
    } catch (err) {
      toast.error(err.message)
    }
  }

  function handleDefer() {
    toast.info('Deferred (backend pending)')
  }

  return (
    <>
      <Masthead kicker="Chicago · Pitching Staff" title="Insights" date={TODAY} />
      {scoreboard && <Scoreboard cells={scoreboard} />}

      <div className="p-6 space-y-8">
        {loading && <EditorialState type="loading" copy="Gathering insights…" />}
        {error && <EditorialState type="error" copy={error} retry={refetch} />}

        {!loading && !error && (
          <>
            {pending.length === 0 && (
              <EditorialState
                type="empty"
                copy="No pending insights. Insights are generated after morning check-ins for pitchers with upcoming starts."
              />
            )}

            {pending.length > 0 && (
              <section>
                <p className="font-ui text-eyebrow uppercase tracking-[0.2em] text-maroon mb-3">
                  Pending · {pending.length}
                </p>
                <div className="space-y-3">
                  {pending.map(s => (
                    <InsightCard
                      key={s.suggestion_id}
                      suggestion={s}
                      variant="hero"
                      onAccept={() => handleAccept(s.suggestion_id)}
                      onDismiss={() => handleDismiss(s.suggestion_id)}
                      onDefer={handleDefer}
                    />
                  ))}
                </div>
              </section>
            )}

            {recent.length > 0 && (
              <section>
                <p className="font-ui text-eyebrow uppercase tracking-[0.2em] text-subtle mb-3">
                  Recent · last 7 days
                </p>
                <div className="space-y-1.5">
                  {recent.map(s => (
                    <InsightCard key={s.suggestion_id} suggestion={s} variant="compact" />
                  ))}
                </div>
              </section>
            )}
          </>
        )}
      </div>
    </>
  )
}
