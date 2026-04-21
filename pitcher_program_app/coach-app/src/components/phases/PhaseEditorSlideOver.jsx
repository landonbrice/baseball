import { useState, useEffect } from 'react'
import { useToast } from '../shell/Toast'
import { updatePhase, createPhase, advancePhase } from '../../api'

const EMPHASIS_TAGS = ['strength', 'power', 'velocity', 'longtoss', 'recovery', 'hypertrophy', 'gpp', 'maintenance']

export default function PhaseEditorSlideOver({ phase, isNew = false, onClose, onSaved, onDelete }) {
  const toast = useToast()
  const [form, setForm] = useState({
    phase_name: phase?.phase_name || '',
    start_date: phase?.start_date || '',
    end_date: phase?.end_date || '',
    target_weekly_load: phase?.target_weekly_load || '',
    emphasis: phase?.emphasis || '',
    notes: phase?.notes || '',
  })
  const [showAdvanceConfirm, setShowAdvanceConfirm] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    function onKey(e) { if (e.key === 'Escape') onClose?.() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  async function handleSave(e) {
    e.preventDefault()
    setSubmitting(true)
    try {
      const payload = {
        ...form,
        target_weekly_load: form.target_weekly_load ? parseInt(form.target_weekly_load, 10) : null,
      }
      if (isNew) {
        await createPhase(payload)
      } else {
        await updatePhase({ phaseId: phase.phase_block_id, ...payload })
      }
      toast.success(`Phase ${isNew ? 'created' : 'updated'} (preview mode — backend pending)`)
      onSaved?.()
      onClose?.()
    } catch (err) {
      toast.error(err?.message || 'Failed to save phase')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleAdvance() {
    setShowAdvanceConfirm(false)
    try {
      await advancePhase()
      toast.success('Phases updated (preview mode)')
      onSaved?.()
      onClose?.()
    } catch (err) {
      toast.error(err?.message || 'Failed to advance phase')
    }
  }

  return (
    <div className="fixed top-0 right-0 h-full w-[560px] bg-bone shadow-xl z-50 flex flex-col border-l border-cream-dark">
      <div className="flex items-center justify-between px-6 py-4 border-b border-cream-dark">
        <h2 className="font-serif font-bold text-h1 text-charcoal">
          {isNew ? 'New Phase' : `Edit Phase — ${phase?.phase_name || ''}`}
        </h2>
        <button type="button" onClick={onClose} aria-label="Close"
          className="font-ui text-h1 text-muted hover:text-charcoal leading-none">×</button>
      </div>

      <form onSubmit={handleSave} className="flex flex-col flex-1 overflow-hidden">
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          <div>
            <label className="block font-ui text-body-sm text-subtle mb-1">Phase name</label>
            <input type="text" autoFocus value={form.phase_name}
              onChange={e => setForm(f => ({ ...f, phase_name: e.target.value }))}
              className="w-full px-3 py-2 border border-cream-dark rounded-[3px] font-ui text-body-sm bg-bone text-charcoal" />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-ui text-body-sm text-subtle mb-1">Start date</label>
              <input type="date" value={form.start_date}
                onChange={e => setForm(f => ({ ...f, start_date: e.target.value }))}
                className="w-full px-3 py-2 border border-cream-dark rounded-[3px] font-ui text-body-sm bg-bone text-charcoal" />
            </div>
            <div>
              <label className="block font-ui text-body-sm text-subtle mb-1">End date</label>
              <input type="date" value={form.end_date}
                onChange={e => setForm(f => ({ ...f, end_date: e.target.value }))}
                className="w-full px-3 py-2 border border-cream-dark rounded-[3px] font-ui text-body-sm bg-bone text-charcoal" />
            </div>
          </div>

          <div>
            <label className="block font-ui text-body-sm text-subtle mb-1">Target weekly load (throws/week)</label>
            <input type="number" min="0" value={form.target_weekly_load}
              onChange={e => setForm(f => ({ ...f, target_weekly_load: e.target.value }))}
              className="w-full px-3 py-2 border border-cream-dark rounded-[3px] font-ui text-body-sm bg-bone text-charcoal" />
          </div>

          <div>
            <label className="block font-ui text-body-sm text-subtle mb-2">Training emphasis</label>
            <div className="flex flex-wrap gap-2">
              {EMPHASIS_TAGS.map(tag => (
                <button key={tag} type="button"
                  onClick={() => setForm(f => ({ ...f, emphasis: f.emphasis === tag ? '' : tag }))}
                  className={`font-ui text-meta px-2.5 py-1 rounded-[3px] capitalize transition-colors ${
                    form.emphasis === tag ? 'bg-maroon text-bone' : 'bg-cream text-charcoal hover:bg-cream-dark'
                  }`}>
                  {tag}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block font-ui text-body-sm text-subtle mb-1">Notes</label>
            <textarea rows={2} value={form.notes || ''}
              onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
              className="w-full px-3 py-2 border border-cream-dark rounded-[3px] font-ui text-body-sm bg-bone text-charcoal" />
          </div>

          {!isNew && (
            <div className="pt-2 border-t border-cream-dark">
              {showAdvanceConfirm ? (
                <div className="bg-amber/10 border border-amber rounded-[3px] p-3">
                  <p className="font-ui text-body-sm text-charcoal mb-2">
                    End this phase and start the next? This shifts all phase blocks forward.
                  </p>
                  <div className="flex gap-2">
                    <button type="button" onClick={handleAdvance}
                      className="font-ui font-semibold text-meta text-bone bg-maroon px-3 py-1.5 rounded-[3px]">
                      Confirm
                    </button>
                    <button type="button" onClick={() => setShowAdvanceConfirm(false)}
                      className="font-ui text-meta text-subtle hover:text-charcoal">
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <button type="button" onClick={() => setShowAdvanceConfirm(true)}
                  className="font-ui text-body-sm text-maroon hover:underline">
                  Advance to Next Phase →
                </button>
              )}
            </div>
          )}
        </div>

        <div className="bg-bone border-t border-cream-dark px-6 py-3 flex gap-3 justify-end">
          {!isNew && onDelete && (
            <button type="button" onClick={onDelete}
              className="font-ui text-meta text-crimson hover:underline mr-auto">
              Delete
            </button>
          )}
          <button type="button" onClick={onClose}
            className="font-ui text-body-sm text-subtle hover:text-charcoal px-3 py-2">
            Cancel
          </button>
          <button type="submit" disabled={submitting}
            className="font-ui font-semibold text-body-sm text-bone bg-maroon px-4 py-2 rounded-[3px] hover:bg-maroon-ink disabled:opacity-50">
            {submitting ? 'Saving…' : 'Save Phase'}
          </button>
        </div>
      </form>
    </div>
  )
}
