import { useCoachApi } from '../hooks/useApi'
import InsightCard from '../components/InsightCard'
import Masthead from '../components/shell/Masthead'
import EditorialState from '../components/shell/EditorialState'

const TODAY = new Date().toLocaleDateString('en-US', {
  weekday: 'short', month: 'short', day: 'numeric', timeZone: 'America/Chicago',
}).replace(',', ' ·')

export default function Insights() {
  const { data, loading, error, refetch } = useCoachApi('/api/coach/insights?status=pending')
  const suggestions = data?.suggestions || []

  const stub = <Masthead kicker="Chicago · Pitching Staff" title="Insights" date={TODAY} />

  return (
    <>
      {stub}
      <div className="p-6">
        <h2 className="text-lg font-bold text-charcoal mb-4">Coaching Insights</h2>

        {loading && <EditorialState type="loading" copy="Gathering insights…" />}
        {error && <EditorialState type="error" copy={error} retry={refetch} />}
        {!loading && suggestions.length === 0 && (
          <EditorialState type="empty" copy="No pending suggestions. Insights are generated after morning check-ins for pitchers with upcoming starts." />
        )}

        <div className="space-y-3">
          {suggestions.map(s => (
            <InsightCard key={s.suggestion_id} suggestion={s} onResolved={refetch} />
          ))}
        </div>
      </div>
    </>
  )
}
