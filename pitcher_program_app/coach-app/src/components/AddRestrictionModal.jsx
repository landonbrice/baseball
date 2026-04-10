import { useState } from 'react'
import { postCoachApi } from '../api'
import { useCoachAuth } from '../hooks/useCoachAuth'

export default function AddRestrictionModal({ pitcherId, onClose, onApplied }) {
  const { getAccessToken } = useCoachAuth()
  const [type, setType] = useState('exercise_blocked')
  const [target, setTarget] = useState('')
  const [reason, setReason] = useState('')
  const [expiresAt, setExpiresAt] = useState('')
  const [saving, setSaving] = useState(false)

  async function handleSave() {
    if (!target) return
    setSaving(true)
    try {
      await postCoachApi(
        `/api/coach/pitcher/${pitcherId}/restriction`,
        {
          restriction_type: type,
          target,
          reason,
          expires_at: expiresAt || undefined,
        },
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
        <h3 className="text-sm font-bold text-charcoal mb-3">Add Restriction</h3>
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-subtle mb-1">Type</label>
            <select
              value={type}
              onChange={e => setType(e.target.value)}
              className="w-full px-3 py-2 border border-cream-dark rounded text-sm"
            >
              <option value="exercise_blocked">Exercise Blocked</option>
              <option value="equipment_unavailable">Equipment Unavailable</option>
              <option value="movement_limited">Movement Limited</option>
            </select>
          </div>

          <div>
            <label className="block text-xs text-subtle mb-1">
              Target (exercise ID, equipment, or movement)
            </label>
            <input
              value={target}
              onChange={e => setTarget(e.target.value)}
              className="w-full px-3 py-2 border border-cream-dark rounded text-sm"
              placeholder="e.g. ex_045 or overhead_press"
            />
          </div>

          <div>
            <label className="block text-xs text-subtle mb-1">Reason</label>
            <input
              value={reason}
              onChange={e => setReason(e.target.value)}
              className="w-full px-3 py-2 border border-cream-dark rounded text-sm"
              placeholder="e.g. Shoulder impingement"
            />
          </div>

          <div>
            <label className="block text-xs text-subtle mb-1">Expires (optional)</label>
            <input
              type="date"
              value={expiresAt}
              onChange={e => setExpiresAt(e.target.value)}
              className="w-full px-3 py-2 border border-cream-dark rounded text-sm"
            />
          </div>
        </div>

        <div className="flex gap-2 mt-4">
          <button
            onClick={onClose}
            className="flex-1 py-2 border border-cream-dark rounded text-sm"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={!target || saving}
            className="flex-1 py-2 bg-maroon text-white rounded text-sm font-medium hover:bg-maroon-light disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Add Restriction'}
          </button>
        </div>
      </div>
    </>
  )
}
