import { useState } from 'react'
import { useCoachApi } from '../hooks/useApi'
import { useCoachAuth } from '../hooks/useCoachAuth'
import { postCoachApi } from '../api'
import { useToast } from '../components/shell/Toast'
import Masthead from '../components/shell/Masthead'
import Scoreboard from '../components/shell/Scoreboard'
import EditorialState from '../components/shell/EditorialState'
import BlockCard from '../components/programs/BlockCard'
import LibraryCard from '../components/programs/LibraryCard'
import CreateProgramSlideOver from '../components/programs/CreateProgramSlideOver'
import { TODAY } from '../utils/formatToday'

export default function TeamPrograms() {
  const { getAccessToken } = useCoachAuth()
  const toast = useToast()
  const { data: libData, loading: libLoading } = useCoachApi('/api/coach/team-programs/library')
  const { data: activeData, loading: activeLoading, refetch } = useCoachApi('/api/coach/team-programs/active')
  const [showCreate, setShowCreate] = useState(false)
  const [assigning, setAssigning] = useState(null)
  const [assignDate, setAssignDate] = useState(new Date().toLocaleDateString('en-CA'))

  const library = libData?.blocks || []
  const active = activeData?.blocks || []

  const minEndDate = active.reduce((min, b) => {
    if (!b.start_date || !b.duration_days) return min
    const end = new Date(new Date(b.start_date).getTime() + b.duration_days * 86400000)
    return !min || end < min ? end : min
  }, null)
  const weeksRemaining = minEndDate
    ? Math.max(0, Math.round((minEndDate - Date.now()) / (7 * 86400000)))
    : null

  const scoreboard = !activeData ? null : [
    {
      label: 'Active Blocks',
      value: String(active.length),
      sub: `${active.filter(b => b.block_type === 'throwing').length} throwing`,
    },
    { label: 'Avg Completion', value: '—', sub: 'data pending' },
    {
      label: 'Weeks Remaining',
      value: weeksRemaining != null ? `${weeksRemaining}w` : '—',
      sub: minEndDate
        ? `ends ${minEndDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`
        : '—',
    },
    { label: 'Pitchers Enrolled', value: '—', sub: 'data pending' },
    { label: 'Next Milestone', value: '—', sub: 'data pending' },
  ]

  async function handleEnd(blockId) {
    try {
      await postCoachApi(`/api/coach/team-programs/${blockId}/end`, {}, getAccessToken())
      toast.warn('Block ended')
      refetch()
    } catch (err) {
      toast.error(err.message)
    }
  }

  async function handleAssignConfirm() {
    if (!assigning || !assignDate) return
    try {
      await postCoachApi('/api/coach/team-programs/assign', {
        block_template_id: assigning.block_template_id,
        start_date: assignDate,
      }, getAccessToken())
      toast.success('Block assigned')
      setAssigning(null)
      refetch()
    } catch (err) {
      toast.error(err.message)
    }
  }

  return (
    <>
      <Masthead
        kicker="Chicago · Pitching Staff"
        title="Team Programs"
        date={TODAY}
        actionSlot={
          <button type="button" onClick={() => setShowCreate(true)}
            className="font-ui font-semibold text-body-sm text-bone bg-maroon hover:bg-maroon-ink px-3 py-1.5 rounded-[3px]">
            + New Program
          </button>
        }
      />
      {scoreboard && <Scoreboard cells={scoreboard} />}

      <div className="p-6 space-y-8">
        {(libLoading || activeLoading) && <EditorialState type="loading" copy="Loading programs…" />}

        {!libLoading && !activeLoading && (
          <>
            <section>
              <p className="font-ui text-eyebrow uppercase tracking-[0.2em] text-maroon mb-3">
                Active Programs
              </p>
              {active.length === 0 ? (
                <EditorialState type="empty" copy="No active programs. Assign one from the library below." />
              ) : (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                  {active.map(b => (
                    <BlockCard key={b.block_id} block={b} isActive onEnd={handleEnd} />
                  ))}
                </div>
              )}
            </section>

            <section>
              <p className="font-ui text-eyebrow uppercase tracking-[0.2em] text-subtle mb-3">
                Library
              </p>
              <div className="space-y-2">
                {library.map(b => (
                  <LibraryCard key={b.block_template_id} block={b} onAssign={setAssigning} />
                ))}
              </div>
            </section>
          </>
        )}
      </div>

      {/* Assign date picker modal */}
      {assigning && (
        <>
          <div className="fixed inset-0 bg-black/30 z-40" onClick={() => setAssigning(null)} />
          <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-bone rounded-[3px] shadow-xl z-50 p-6 w-80">
            <h3 className="font-serif font-bold text-h2 text-charcoal mb-3">Assign: {assigning.name}</h3>
            <label className="block font-ui text-body-sm text-subtle mb-1">Start date</label>
            <input type="date" value={assignDate}
              onChange={e => setAssignDate(e.target.value)}
              className="w-full px-3 py-2 border border-cream-dark rounded-[3px] font-ui text-body-sm bg-bone text-charcoal mb-4" />
            <div className="flex gap-2">
              <button type="button" onClick={() => setAssigning(null)}
                className="flex-1 py-2 font-ui text-body-sm text-subtle border border-cream-dark rounded-[3px] hover:bg-cream/50">
                Cancel
              </button>
              <button type="button" onClick={handleAssignConfirm} disabled={!assignDate}
                className="flex-1 py-2 font-ui font-semibold text-body-sm text-bone bg-maroon rounded-[3px] hover:bg-maroon-ink disabled:opacity-50">
                Assign
              </button>
            </div>
          </div>
        </>
      )}

      {showCreate && (
        <>
          <div className="fixed inset-0 bg-black/20 z-40" onClick={() => setShowCreate(false)} />
          <CreateProgramSlideOver library={library} onClose={() => setShowCreate(false)} />
        </>
      )}
    </>
  )
}
