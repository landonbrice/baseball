import { useState } from 'react'
import { useCoachApi } from '../hooks/useApi'

export default function PlayerSlideOver({ pitcherId, onClose }) {
  const { data, loading, error } = useCoachApi(pitcherId ? `/api/coach/pitcher/${pitcherId}` : null)
  const [activeTab, setActiveTab] = useState('today')

  if (!pitcherId) return null

  const TABS = [
    { key: 'today', label: 'Today' },
    { key: 'week', label: 'This Week' },
    { key: 'history', label: 'History' },
  ]

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/20 z-40" onClick={onClose} />
      {/* Panel */}
      <div className="fixed top-0 right-0 h-full w-[60%] max-w-3xl bg-white shadow-xl z-50 flex flex-col"
        style={{ animation: 'slideIn 0.2s ease-out' }}>
        <style>{`@keyframes slideIn { from { transform: translateX(100%); } to { transform: translateX(0); } }`}</style>

        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-cream-dark">
          <div>
            {loading ? <span className="text-subtle">Loading...</span> : (
              <>
                <h2 className="text-lg font-bold text-charcoal">{data?.profile?.name || pitcherId}</h2>
                <p className="text-xs text-subtle mt-0.5">
                  {data?.profile?.role} {data?.next_start ? `· Next start: ${data.next_start.game_date}` : ''}
                </p>
              </>
            )}
          </div>
          <button onClick={onClose} className="text-subtle hover:text-charcoal text-lg">&times;</button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-cream-dark">
          {TABS.map(t => (
            <button key={t.key} onClick={() => setActiveTab(t.key)}
              className={`px-4 py-2 text-sm font-medium border-b-2 ${activeTab === t.key ? 'border-maroon text-maroon' : 'border-transparent text-subtle hover:text-charcoal'}`}>
              {t.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-4">
          {error && <p className="text-crimson text-sm">{error}</p>}
          {loading ? <p className="text-subtle">Loading player data...</p> : (
            <div>
              {activeTab === 'today' && <PlayerTodayPlaceholder data={data} />}
              {activeTab === 'week' && <PlayerWeekPlaceholder data={data} />}
              {activeTab === 'history' && <PlayerHistoryPlaceholder data={data} />}
            </div>
          )}
        </div>
      </div>
    </>
  )
}

function PlayerTodayPlaceholder({ data }) {
  if (!data) return null
  const week = data.current_week || []
  const today = week.find(e => e.date === new Date().toLocaleDateString('en-CA', { timeZone: 'America/Chicago' }))
  const model = data.training_model || {}

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-cream rounded-lg p-3 text-center">
          <p className="text-xs text-subtle">Flag</p>
          <p className="text-sm font-medium" style={{ color: model.flag_level === 'red' ? '#c0392b' : model.flag_level === 'yellow' ? '#d4a017' : '#2d5a3d' }}>
            {model.flag_level || 'green'}
          </p>
        </div>
        <div className="bg-cream rounded-lg p-3 text-center">
          <p className="text-xs text-subtle">Days Since Outing</p>
          <p className="text-sm font-medium text-charcoal">{model.days_since_outing ?? '-'}</p>
        </div>
        <div className="bg-cream rounded-lg p-3 text-center">
          <p className="text-xs text-subtle">WHOOP</p>
          <p className="text-sm font-medium text-charcoal">{data.whoop_today ? `${data.whoop_today.recovery_score}%` : '-'}</p>
        </div>
      </div>
      {today?.morning_brief && (
        <div className="bg-cream rounded-lg p-3">
          <p className="text-xs text-subtle mb-1">Morning Brief</p>
          <p className="text-sm text-charcoal">{typeof today.morning_brief === 'string' ? today.morning_brief : today.morning_brief?.coaching_note || ''}</p>
        </div>
      )}
      {today?.plan_generated ? (
        <div className="bg-cream rounded-lg p-3">
          <p className="text-xs text-subtle mb-1">Today's Plan</p>
          <p className="text-sm text-charcoal">Plan generated. Full detail view coming in next update.</p>
        </div>
      ) : (
        <p className="text-subtle text-sm">No plan generated yet today.</p>
      )}
      {(data.pending_suggestions || []).length > 0 && (
        <div className="bg-amber/10 border border-amber/30 rounded-lg p-3">
          <p className="text-xs font-medium text-amber">Pending Suggestions</p>
          {data.pending_suggestions.map(s => (
            <p key={s.suggestion_id} className="text-sm text-charcoal mt-1">{s.title}</p>
          ))}
        </div>
      )}
    </div>
  )
}

function PlayerWeekPlaceholder({ data }) {
  const week = data?.current_week || []
  return (
    <div className="space-y-2">
      {week.length === 0 && <p className="text-subtle text-sm">No entries this week.</p>}
      {week.map(e => (
        <div key={e.date} className="flex items-center gap-3 p-2 rounded bg-cream">
          <span className="text-xs font-medium text-charcoal w-20">{e.date}</span>
          <span className="text-xs text-subtle">{e.plan_generated ? 'Plan generated' : 'No plan'}</span>
          <span className="text-xs text-subtle">{e.completed_exercises ? `${Object.keys(e.completed_exercises).length} completed` : ''}</span>
        </div>
      ))}
    </div>
  )
}

function PlayerHistoryPlaceholder({ data }) {
  const recent = data?.recent_check_ins || []
  return (
    <div className="space-y-2">
      <p className="text-xs text-subtle">Last 10 check-ins</p>
      {recent.map(e => (
        <div key={e.date} className="flex items-center gap-3 p-2 rounded bg-cream">
          <span className="text-xs font-medium text-charcoal w-20">{e.date}</span>
          <span className="text-xs text-subtle">Arm feel: {e.pre_training?.arm_feel || '-'}</span>
        </div>
      ))}
    </div>
  )
}
