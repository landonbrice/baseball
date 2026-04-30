import { useState } from 'react'
import { postCoachApi, previewMutations } from '../api'
import { useCoachAuth } from '../hooks/useCoachAuth'
import MutationPreview from './MutationPreview'

export default function AdjustTodayModal({ pitcherId, onClose, onApplied }) {
  const { getAccessToken } = useCoachAuth()
  const [action, setAction] = useState('remove')
  const [exerciseId, setExerciseId] = useState('')
  const [toExerciseId, setToExerciseId] = useState('')
  const [rx, setRx] = useState('')
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [previewing, setPreviewing] = useState(false)
  const [proposed, setProposed] = useState(null)
  const [previewError, setPreviewError] = useState(null)

  function buildMutation() {
    const mutation = { action, exercise_id: exerciseId }
    if (action === 'swap') {
      mutation.from_exercise_id = exerciseId
      mutation.to_exercise_id = toExerciseId
    }
    if (rx) mutation.rx = rx
    if (note) mutation.note = note
    return mutation
  }

  async function handlePreview() {
    if (!exerciseId) return
    setPreviewing(true)
    setPreviewError(null)
    setProposed(null)
    try {
      const today = new Date().toLocaleDateString('en-CA', { timeZone: 'America/Chicago' })
      const out = await previewMutations(
        pitcherId,
        { mutations: [buildMutation()], date: today },
        getAccessToken()
      )
      setProposed(out?.proposed_rationale || null)
    } catch (err) {
      setPreviewError(err.message)
    } finally {
      setPreviewing(false)
    }
  }

  async function handleApply() {
    if (!exerciseId) return
    setSaving(true)

    try {
      const today = new Date().toLocaleDateString('en-CA', { timeZone: 'America/Chicago' })
      await postCoachApi(
        `/api/coach/pitcher/${pitcherId}/adjust-today`,
        { mutations: [buildMutation()], date: today },
        getAccessToken()
      )
      onApplied?.()
      onClose()
    } catch (err) {
      alert(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <div className="fixed inset-0 bg-black/30 z-50" onClick={onClose} />
      <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-lg shadow-xl z-[51] p-6 w-96">
        <h3 className="text-sm font-bold text-charcoal mb-3">Adjust Today's Plan</h3>
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-subtle mb-1">Action</label>
            <select
              value={action}
              onChange={e => setAction(e.target.value)}
              className="w-full px-3 py-2 border border-cream-dark rounded text-sm"
            >
              <option value="remove">Remove Exercise</option>
              <option value="swap">Swap Exercise</option>
              <option value="modify">Modify Prescription</option>
              <option value="add">Add Exercise</option>
            </select>
          </div>

          <div>
            <label className="block text-xs text-subtle mb-1">
              {action === 'swap' ? 'From Exercise ID' : 'Exercise ID'}
            </label>
            <input
              value={exerciseId}
              onChange={e => setExerciseId(e.target.value)}
              className="w-full px-3 py-2 border border-cream-dark rounded text-sm"
              placeholder="ex_001"
            />
          </div>

          {action === 'swap' && (
            <div>
              <label className="block text-xs text-subtle mb-1">To Exercise ID</label>
              <input
                value={toExerciseId}
                onChange={e => setToExerciseId(e.target.value)}
                className="w-full px-3 py-2 border border-cream-dark rounded text-sm"
                placeholder="ex_002"
              />
            </div>
          )}

          {(action === 'modify' || action === 'add' || action === 'swap') && (
            <div>
              <label className="block text-xs text-subtle mb-1">Prescription</label>
              <input
                value={rx}
                onChange={e => setRx(e.target.value)}
                className="w-full px-3 py-2 border border-cream-dark rounded text-sm"
                placeholder="3x8 @ 135"
              />
            </div>
          )}

          <div>
            <label className="block text-xs text-subtle mb-1">Note (optional)</label>
            <input
              value={note}
              onChange={e => setNote(e.target.value)}
              className="w-full px-3 py-2 border border-cream-dark rounded text-sm"
            />
          </div>
        </div>

        {previewError && (
          <p className="mt-3 text-xs text-crimson">{previewError}</p>
        )}
        {proposed && (
          <div className="mt-3">
            <MutationPreview proposed={proposed} />
          </div>
        )}

        <div className="flex gap-2 mt-4">
          <button
            onClick={onClose}
            className="flex-1 py-2 border border-cream-dark rounded text-sm"
          >
            Cancel
          </button>
          <button
            onClick={handlePreview}
            disabled={!exerciseId || previewing || saving}
            className="flex-1 py-2 border border-maroon text-maroon rounded text-sm font-medium hover:bg-hover disabled:opacity-50"
          >
            {previewing ? 'Previewing...' : 'Preview'}
          </button>
          <button
            onClick={handleApply}
            disabled={!exerciseId || saving}
            className="flex-1 py-2 bg-maroon text-white rounded text-sm font-medium hover:bg-maroon-light disabled:opacity-50"
          >
            {saving ? 'Applying...' : 'Apply'}
          </button>
        </div>
      </div>
    </>
  )
}
