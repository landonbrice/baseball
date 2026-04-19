import { useState } from 'react'
import { useCoachApi } from '../hooks/useApi'
import { useCoachAuth } from '../hooks/useCoachAuth'
import { postCoachApi } from '../api'
import BlockCard from '../components/BlockCard'
import Masthead from '../components/shell/Masthead'

const TODAY = new Date().toLocaleDateString('en-US', {
  weekday: 'short', month: 'short', day: 'numeric', timeZone: 'America/Chicago',
}).replace(',', ' ·')

export default function TeamPrograms() {
  const { getAccessToken } = useCoachAuth()
  const { data: libData, loading: libLoading } = useCoachApi('/api/coach/team-programs/library')
  const { data: activeData, loading: activeLoading, refetch: refetchActive } = useCoachApi('/api/coach/team-programs/active')
  const [assigning, setAssigning] = useState(null) // block being assigned
  const [startDate, setStartDate] = useState('')

  const library = libData?.blocks || []
  const active = activeData?.blocks || []

  async function handleAssign() {
    if (!assigning || !startDate) return
    try {
      await postCoachApi('/api/coach/team-programs/assign', {
        block_template_id: assigning.block_template_id,
        start_date: startDate,
      }, getAccessToken())
      setAssigning(null)
      setStartDate('')
      refetchActive()
    } catch (err) {
      alert(err.message)
    }
  }

  async function handleEnd(blockId) {
    if (!confirm('End this block early?')) return
    try {
      await postCoachApi(`/api/coach/team-programs/${blockId}/end`, {}, getAccessToken())
      refetchActive()
    } catch (err) {
      alert(err.message)
    }
  }

  return (
    <>
      <Masthead kicker="Chicago · Pitching Staff" title="Team Programs" date={TODAY} />
      <div className="p-6">
        <h2 className="text-lg font-bold text-charcoal mb-4">Team Programs</h2>

        {/* Active blocks */}
        <div className="mb-6">
          <h3 className="text-sm font-medium text-subtle mb-2">Active Programs</h3>
          {activeLoading ? <p className="text-subtle text-sm">Loading...</p> : active.length === 0 ? (
            <div className="bg-cream rounded-lg p-4 text-center">
              <p className="text-sm text-subtle">No active programs. Assign one from the library below.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {active.map(b => <BlockCard key={b.block_id} block={b} isActive onEnd={handleEnd} />)}
            </div>
          )}
        </div>

        {/* Block Library */}
        <div>
          <h3 className="text-sm font-medium text-subtle mb-2">Block Library</h3>
          {libLoading ? <p className="text-subtle text-sm">Loading...</p> : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              {library.map(b => <BlockCard key={b.block_template_id} block={b} onAssign={setAssigning} />)}
            </div>
          )}
        </div>

        {/* Assign modal */}
        {assigning && (
          <>
            <div className="fixed inset-0 bg-black/30 z-40" onClick={() => setAssigning(null)} />
            <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-lg shadow-xl z-50 p-6 w-96">
              <h3 className="text-sm font-bold text-charcoal mb-3">Assign: {assigning.name}</h3>
              <label className="block text-xs text-subtle mb-1">Start Date</label>
              <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)}
                className="w-full px-3 py-2 border border-cream-dark rounded text-sm mb-4" />
              <div className="flex gap-2">
                <button onClick={() => setAssigning(null)} className="flex-1 py-2 border border-cream-dark rounded text-sm">Cancel</button>
                <button onClick={handleAssign} disabled={!startDate}
                  className="flex-1 py-2 bg-maroon text-white rounded text-sm font-medium hover:bg-maroon-light disabled:opacity-50">
                  Assign to Team
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </>
  )
}
