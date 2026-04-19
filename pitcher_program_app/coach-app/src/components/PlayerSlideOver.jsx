import { useEffect, useState } from 'react'
import { useCoachApi } from '../hooks/useApi'
import PlayerToday from './PlayerToday'
import PlayerWeek from './PlayerWeek'
import PlayerHistory from './PlayerHistory'
import AdjustTodayModal from './AdjustTodayModal'
import AddRestrictionModal from './AddRestrictionModal'
import FlagPill from './shell/FlagPill'

const TABS = [
  { key: 'today', label: 'Today' },
  { key: 'week', label: 'Week' },
  { key: 'history', label: 'History' },
]

function formatShortDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso + 'T12:00:00')
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'America/Chicago' })
}

function computeStreak(week) {
  if (!Array.isArray(week)) return 0
  const sorted = [...week].sort((a, b) => (a.date || '').localeCompare(b.date || ''))
  let streak = 0
  for (let i = sorted.length - 1; i >= 0; i--) {
    const e = sorted[i]
    const done = e.completed_exercises && Object.keys(e.completed_exercises).length > 0
    if (done) streak += 1
    else break
  }
  return streak
}

function computeAf7d(recentCheckins) {
  if (!Array.isArray(recentCheckins)) return null
  const last7 = recentCheckins.slice(0, 7)
  const vals = last7
    .map(e => e.pre_training?.arm_feel)
    .filter(v => typeof v === 'number')
  if (vals.length === 0) return null
  return Math.round((vals.reduce((a, b) => a + b, 0) / vals.length) * 10) / 10
}

export default function PlayerSlideOver({ pitcherId, onClose }) {
  const { data, loading, error, refetch } = useCoachApi(pitcherId ? `/api/coach/pitcher/${pitcherId}` : null)
  const [activeTab, setActiveTab] = useState('today')
  const [showAdjust, setShowAdjust] = useState(false)
  const [showRestrict, setShowRestrict] = useState(false)

  useEffect(() => {
    if (!pitcherId) return
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [pitcherId, onClose])

  if (!pitcherId) return null

  const model = data?.training_model || {}
  const af7d = computeAf7d(data?.recent_check_ins)
  const streak = computeStreak(data?.current_week)
  const nextStart = data?.next_start?.game_date

  const injuryLine = (() => {
    const injs = (data?.injuries || []).filter(i => i.flag_level === 'yellow' || i.flag_level === 'red')
    if (injs.length === 0) return null
    return injs.map(i => `${i.area} (${i.flag_level})`).join(' · ')
  })()

  return (
    <>
      <div className="fixed inset-0 bg-black/20 z-40" onClick={onClose} />
      <div
        className="fixed top-0 right-0 h-full w-[480px] max-w-full bg-bone shadow-xl z-50 flex flex-col"
        style={{ animation: 'slideIn 0.2s ease-out' }}
      >
        <style>{`@keyframes slideIn { from { transform: translateX(100%); } to { transform: translateX(0); } }`}</style>

        <div className="px-5 pt-5 pb-4 border-b border-cream-dark">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="font-serif font-bold text-h1 text-charcoal leading-tight">
                {data?.profile?.name || pitcherId}
              </h2>
              <p className="font-ui text-meta text-muted mt-0.5 uppercase tracking-[0.1em]">
                {data?.profile?.role || ''}
              </p>
            </div>
            <div className="flex items-start gap-2">
              <FlagPill level={model.current_flag_level || 'green'} />
              <button
                type="button"
                onClick={onClose}
                aria-label="Close"
                className="font-ui text-h2 text-muted hover:text-charcoal leading-none"
              >
                ×
              </button>
            </div>
          </div>

          {injuryLine && (
            <div className="mt-2 inline-block bg-parchment text-maroon font-ui text-[10px] px-2 py-0.5 rounded-[2px]">
              {injuryLine}
            </div>
          )}

          <div className="mt-4 grid grid-cols-3 border border-cream-dark rounded-[3px] bg-parchment">
            <MiniCell label="AF 7d" value={af7d != null ? af7d.toFixed(1) : '—'} />
            <MiniCell label="Streak" value={`${streak}d`} divider />
            <MiniCell label="Next Start" value={formatShortDate(nextStart)} divider />
          </div>
        </div>

        <div className="flex border-b border-cream-dark px-5">
          {TABS.map(t => (
            <button
              key={t.key}
              type="button"
              onClick={() => setActiveTab(t.key)}
              className={`px-3 py-2 font-ui uppercase tracking-[0.12em] text-[11px] border-b-2 ${
                activeTab === t.key
                  ? 'border-maroon text-maroon font-semibold'
                  : 'border-transparent text-muted hover:text-charcoal'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-auto p-5">
          {loading && !data && <p className="font-ui text-meta text-muted">Loading player data…</p>}
          {error && <p className="font-ui text-body text-crimson">{error}</p>}
          {data && (
            <>
              {activeTab === 'today' && (
                <PlayerToday
                  data={data}
                  onAdjust={() => setShowAdjust(true)}
                  onRestrict={() => setShowRestrict(true)}
                />
              )}
              {activeTab === 'week' && <PlayerWeek data={data} />}
              {activeTab === 'history' && <PlayerHistory data={data} />}
            </>
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

function MiniCell({ label, value, divider }) {
  return (
    <div className={`px-3 py-2 ${divider ? 'border-l border-cream-dark' : ''}`}>
      <div className="font-ui font-semibold uppercase text-[9px] tracking-[0.16em] text-muted">{label}</div>
      <div className="font-serif font-bold text-h2 text-charcoal tabular">{value}</div>
    </div>
  )
}
