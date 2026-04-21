import { useState } from 'react'
import { useCoachApi } from '../hooks/useApi'
import { useCoachAuth } from '../hooks/useCoachAuth'
import { deleteCoachApi } from '../api'
import { useToast } from '../components/shell/Toast'
import Masthead from '../components/shell/Masthead'
import Scoreboard from '../components/shell/Scoreboard'
import EditorialState from '../components/shell/EditorialState'
import PhaseTimeline from '../components/phases/PhaseTimeline'
import PhaseEditorSlideOver from '../components/phases/PhaseEditorSlideOver'
import PhaseDetailSection from '../components/phases/PhaseDetailSection'
import { TODAY } from '../utils/formatToday'

export default function Phases() {
  const { getAccessToken } = useCoachAuth()
  const toast = useToast()
  const { data, loading, error, refetch } = useCoachApi('/api/coach/phases')
  const [editing, setEditing] = useState(null) // null | 'new' | phase object

  const phases = data?.phases || []
  // ISO date for comparisons (Chicago TZ). TODAY is the display string reserved for Masthead.
  const today = new Date().toLocaleDateString('en-CA', { timeZone: 'America/Chicago' })

  const currentPhase = phases.find(p => today >= p.start_date && today <= p.end_date) || null
  const nextPhase = phases
    .filter(p => p.start_date > today)
    .sort((a, b) => a.start_date.localeCompare(b.start_date))[0] || null

  const daysToNext = nextPhase
    ? Math.max(0, Math.round(
        (new Date(nextPhase.start_date + 'T12:00:00') - new Date(today + 'T12:00:00')) / 86400000
      ))
    : null

  const currentTotalWeeks = currentPhase
    ? Math.max(1, Math.round(
        (new Date(currentPhase.end_date) - new Date(currentPhase.start_date)) / (7 * 86400000)
      ))
    : null
  const currentElapsedWeeks = currentPhase
    ? Math.max(0, Math.floor((Date.now() - new Date(currentPhase.start_date + 'T12:00:00')) / (7 * 86400000)))
    : null

  const scoreboard = !data ? null : [
    {
      label: 'Current Phase',
      value: currentPhase?.phase_name || '—',
      sub: currentPhase ? `started ${currentPhase.start_date}` : '—',
    },
    {
      label: 'Week',
      value: currentPhase
        ? `${Math.min(currentTotalWeeks, currentElapsedWeeks + 1)} / ${currentTotalWeeks}`
        : '—',
      sub: 'of current phase',
    },
    {
      label: 'Days to Next',
      value: daysToNext != null ? `${daysToNext}d` : '—',
      sub: nextPhase?.phase_name || '—',
    },
    {
      label: 'Target Load',
      value: currentPhase?.target_weekly_load ? String(currentPhase.target_weekly_load) : '—',
      sub: 'throws/week',
    },
    { label: 'Deviation', value: '—', sub: 'vs target' },
  ]

  async function handleDelete(phaseBlockId) {
    try {
      await deleteCoachApi(`/api/coach/phases/${phaseBlockId}`, getAccessToken())
      toast.warn('Phase deleted')
      setEditing(null)
      refetch()
    } catch (err) {
      toast.error(err.message)
    }
  }

  return (
    <>
      <Masthead
        kicker="Chicago · Pitching Staff"
        title="Phases"
        date={TODAY}
        actionSlot={
          <button type="button" onClick={() => setEditing('new')}
            className="font-ui font-semibold text-body-sm text-bone bg-maroon hover:bg-maroon-ink px-3 py-1.5 rounded-[3px]">
            + Add Phase
          </button>
        }
      />
      {scoreboard && <Scoreboard cells={scoreboard} />}

      <div className="p-6 space-y-8">
        {loading && <EditorialState type="loading" copy="Loading phases…" />}
        {error && <EditorialState type="error" copy={error} retry={refetch} />}

        {!loading && !error && (
          <>
            <section>
              <p className="font-ui text-eyebrow uppercase tracking-[0.2em] text-maroon mb-3">
                Phase Timeline
              </p>
              <PhaseTimeline phases={phases} onSelect={p => setEditing(p)} />
              {phases.length === 0 && (
                <EditorialState type="empty" copy="No phases defined. Add one with + Add Phase." />
              )}
            </section>

            {currentPhase && <PhaseDetailSection phase={currentPhase} title="Current Phase" />}
            {nextPhase && <PhaseDetailSection phase={nextPhase} title="Next Up" />}
          </>
        )}
      </div>

      {editing && (
        <>
          <div className="fixed inset-0 bg-black/20 z-40" onClick={() => setEditing(null)} />
          <PhaseEditorSlideOver
            phase={editing === 'new' ? null : editing}
            isNew={editing === 'new'}
            onClose={() => setEditing(null)}
            onSaved={refetch}
            onDelete={editing !== 'new' ? () => handleDelete(editing.phase_block_id) : undefined}
          />
        </>
      )}
    </>
  )
}
