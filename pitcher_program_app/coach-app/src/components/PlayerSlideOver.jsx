import { useState } from 'react'
import { useCoachApi } from '../hooks/useApi'
import PlayerToday from './PlayerToday'
import PlayerWeek from './PlayerWeek'
import PlayerHistory from './PlayerHistory'
import AdjustTodayModal from './AdjustTodayModal'
import AddRestrictionModal from './AddRestrictionModal'

export default function PlayerSlideOver({ pitcherId, onClose }) {
  const { data, loading, error, refetch } = useCoachApi(pitcherId ? `/api/coach/pitcher/${pitcherId}` : null)
  const [activeTab, setActiveTab] = useState('today')
  const [showAdjust, setShowAdjust] = useState(false)
  const [showRestrict, setShowRestrict] = useState(false)

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
              {activeTab === 'today' && (
                <PlayerToday
                  data={data}
                  onAdjust={() => setShowAdjust(true)}
                  onRestrict={() => setShowRestrict(true)}
                />
              )}
              {activeTab === 'week' && <PlayerWeek data={data} />}
              {activeTab === 'history' && <PlayerHistory data={data} />}
            </div>
          )}
        </div>
      </div>

      {showAdjust && (
        <AdjustTodayModal
          pitcherId={pitcherId}
          onClose={() => setShowAdjust(false)}
          onApplied={refetch}
        />
      )}
      {showRestrict && (
        <AddRestrictionModal
          pitcherId={pitcherId}
          onClose={() => setShowRestrict(false)}
          onApplied={refetch}
        />
      )}
    </>
  )
}

