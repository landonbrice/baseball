import { useCoachApi } from '../hooks/useApi'
import InsightCard from '../components/InsightCard'

export default function Insights() {
  const { data, loading, error, refetch } = useCoachApi('/api/coach/insights?status=pending')

  const suggestions = data?.suggestions || []

  return (
    <div className="p-6">
      <h2 className="text-lg font-bold text-charcoal mb-4">Coaching Insights</h2>

      {loading && <p className="text-subtle">Loading insights...</p>}
      {error && <p className="text-crimson text-sm">{error}</p>}

      {!loading && suggestions.length === 0 && (
        <div className="bg-cream rounded-lg p-8 text-center">
          <p className="text-sm text-subtle">No pending suggestions.</p>
          <p className="text-xs text-subtle mt-1">Insights are generated after morning check-ins for pitchers with upcoming starts.</p>
        </div>
      )}

      <div className="space-y-3">
        {suggestions.map(s => (
          <InsightCard key={s.suggestion_id} suggestion={s} onResolved={refetch} />
        ))}
      </div>
    </div>
  )
}
