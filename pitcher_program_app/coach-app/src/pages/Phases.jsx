import { useState } from 'react'
import { useCoachApi } from '../hooks/useApi'
import { useCoachAuth } from '../hooks/useCoachAuth'
import { postCoachApi, patchCoachApi, deleteCoachApi } from '../api'
import PhaseTimeline from '../components/PhaseTimeline'

const EMPTY = { phase_name: '', start_date: '', end_date: '', emphasis: '', notes: '' }

export default function Phases() {
  const { getAccessToken } = useCoachAuth()
  const { data, loading, refetch } = useCoachApi('/api/coach/phases')
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(EMPTY)

  const phases = data?.phases || []

  function openNew() {
    setForm(EMPTY)
    setEditing('new')
  }

  function openEdit(p) {
    setForm({ ...p })
    setEditing(p.phase_block_id)
  }

  async function handleSave() {
    try {
      if (editing === 'new') {
        await postCoachApi('/api/coach/phases', form, getAccessToken())
      } else {
        await patchCoachApi(`/api/coach/phases/${editing}`, form, getAccessToken())
      }
      setEditing(null)
      refetch()
    } catch (err) {
      alert(err.message)
    }
  }

  async function handleDelete() {
    if (!confirm('Delete this phase?')) return
    try {
      await deleteCoachApi(`/api/coach/phases/${editing}`, getAccessToken())
      setEditing(null)
      refetch()
    } catch (err) {
      alert(err.message)
    }
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold text-charcoal">Training Phases</h2>
        <button
          onClick={openNew}
          className="text-xs px-3 py-1.5 bg-maroon text-white rounded hover:bg-maroon-light"
        >
          Add Phase
        </button>
      </div>

      {loading ? (
        <p className="text-subtle">Loading...</p>
      ) : (
        <PhaseTimeline phases={phases} onSelect={openEdit} />
      )}

      {/* Phase list */}
      <div className="mt-6 space-y-2">
        {phases.map(p => (
          <div
            key={p.phase_block_id}
            onClick={() => openEdit(p)}
            className="bg-white rounded-lg border border-cream-dark p-3 cursor-pointer hover:bg-cream/50 flex justify-between items-center"
          >
            <div>
              <p className="text-sm font-medium text-charcoal">{p.phase_name}</p>
              <p className="text-xs text-subtle">
                {p.start_date} — {p.end_date} · {p.emphasis}
              </p>
            </div>
          </div>
        ))}
      </div>

      {/* Edit/Create modal */}
      {editing && (
        <>
          <div className="fixed inset-0 bg-black/30 z-40" onClick={() => setEditing(null)} />
          <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-lg shadow-xl z-50 p-6 w-96 max-h-[90vh] overflow-y-auto">
            <h3 className="text-sm font-bold text-charcoal mb-3">
              {editing === 'new' ? 'New Phase' : 'Edit Phase'}
            </h3>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-subtle mb-1">Name</label>
                <input
                  type="text"
                  value={form.phase_name}
                  onChange={e => setForm({ ...form, phase_name: e.target.value })}
                  className="w-full px-3 py-2 border border-cream-dark rounded text-sm"
                  placeholder="e.g., Hypertrophy Block"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs text-subtle mb-1">Start</label>
                  <input
                    type="date"
                    value={form.start_date}
                    onChange={e => setForm({ ...form, start_date: e.target.value })}
                    className="w-full px-3 py-2 border border-cream-dark rounded text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs text-subtle mb-1">End</label>
                  <input
                    type="date"
                    value={form.end_date}
                    onChange={e => setForm({ ...form, end_date: e.target.value })}
                    className="w-full px-3 py-2 border border-cream-dark rounded text-sm"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs text-subtle mb-1">Emphasis</label>
                <select
                  value={form.emphasis}
                  onChange={e => setForm({ ...form, emphasis: e.target.value })}
                  className="w-full px-3 py-2 border border-cream-dark rounded text-sm"
                >
                  <option value="">Select...</option>
                  <option value="hypertrophy">Hypertrophy</option>
                  <option value="strength">Strength</option>
                  <option value="power">Power</option>
                  <option value="maintenance">Maintenance</option>
                  <option value="gpp">GPP</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-subtle mb-1">Notes</label>
                <textarea
                  value={form.notes || ''}
                  onChange={e => setForm({ ...form, notes: e.target.value })}
                  className="w-full px-3 py-2 border border-cream-dark rounded text-sm"
                  placeholder="Optional notes..."
                  rows={2}
                />
              </div>
            </div>
            <div className="flex gap-2 mt-4">
              {editing !== 'new' && (
                <button
                  onClick={handleDelete}
                  className="text-xs text-crimson hover:underline mr-auto"
                >
                  Delete
                </button>
              )}
              <button
                onClick={() => setEditing(null)}
                className="flex-1 py-2 border border-cream-dark rounded text-sm hover:bg-cream/50"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                className="flex-1 py-2 bg-maroon text-white rounded text-sm font-medium hover:bg-maroon-light"
              >
                Save
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
