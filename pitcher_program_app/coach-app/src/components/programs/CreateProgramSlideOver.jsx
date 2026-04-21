import { useState, useEffect } from 'react'
import { useToast } from '../shell/Toast'
import { createTeamProgram } from '../../api'
import WeeklyStructurePreview from './WeeklyStructurePreview'

export default function CreateProgramSlideOver({ library = [], onClose }) {
  const toast = useToast()
  const [form, setForm] = useState({
    name: '',
    baseBlockId: '',
    startDate: new Date().toLocaleDateString('en-CA'),
    durationWeeks: '',
    notes: '',
  })
  const [submitting, setSubmitting] = useState(false)

  const selectedBlock = library.find(b => b.block_template_id === form.baseBlockId) || null

  useEffect(() => {
    if (selectedBlock?.duration_days) {
      setForm(f => ({ ...f, durationWeeks: String(Math.round(selectedBlock.duration_days / 7)) }))
    }
  }, [form.baseBlockId])

  useEffect(() => {
    function onKey(e) { if (e.key === 'Escape') onClose?.() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.name.trim()) { toast.error('Program name is required'); return }
    setSubmitting(true)
    try {
      await createTeamProgram({
        name: form.name,
        baseBlockId: form.baseBlockId,
        startDate: form.startDate,
        durationWeeks: form.durationWeeks ? parseInt(form.durationWeeks, 10) : null,
        notes: form.notes,
      })
      console.log('CreateProgram:', form)
      toast.success('Program created (preview mode — backend pending)')
      onClose?.()
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed top-0 right-0 h-full w-[560px] bg-bone shadow-xl z-50 flex flex-col border-l border-cream-dark">
      <div className="flex items-center justify-between px-6 py-4 border-b border-cream-dark">
        <h2 className="font-serif font-bold text-h1 text-charcoal">New Program</h2>
        <button type="button" onClick={onClose} aria-label="Close"
          className="font-ui text-h1 text-muted hover:text-charcoal leading-none">×</button>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col flex-1 overflow-hidden">
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          <div>
            <label className="block font-ui text-body-sm text-subtle mb-1">Program name *</label>
            <input type="text" required value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              className="w-full px-3 py-2 border border-cream-dark rounded-[3px] font-ui text-body-sm bg-bone text-charcoal"
              placeholder="e.g., Spring Velocity Block" />
          </div>
          <div>
            <label className="block font-ui text-body-sm text-subtle mb-1">Base block</label>
            <select value={form.baseBlockId}
              onChange={e => setForm(f => ({ ...f, baseBlockId: e.target.value }))}
              className="w-full px-3 py-2 border border-cream-dark rounded-[3px] font-ui text-body-sm bg-bone text-charcoal">
              <option value="">— Select a block —</option>
              {library.map(b => (
                <option key={b.block_template_id} value={b.block_template_id}>
                  {b.name} · {Math.round((b.duration_days || 0) / 7)}w · {b.block_type}
                </option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-ui text-body-sm text-subtle mb-1">Start date</label>
              <input type="date" value={form.startDate}
                onChange={e => setForm(f => ({ ...f, startDate: e.target.value }))}
                className="w-full px-3 py-2 border border-cream-dark rounded-[3px] font-ui text-body-sm bg-bone text-charcoal" />
            </div>
            <div>
              <label className="block font-ui text-body-sm text-subtle mb-1">Duration (weeks)</label>
              <input type="number" min="1" value={form.durationWeeks}
                onChange={e => setForm(f => ({ ...f, durationWeeks: e.target.value }))}
                className="w-full px-3 py-2 border border-cream-dark rounded-[3px] font-ui text-body-sm bg-bone text-charcoal" />
            </div>
          </div>
          <div>
            <label className="block font-ui text-body-sm text-subtle mb-1">Notes</label>
            <textarea rows={2} value={form.notes}
              onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
              className="w-full px-3 py-2 border border-cream-dark rounded-[3px] font-ui text-body-sm bg-bone text-charcoal"
              placeholder="Optional…" />
          </div>
          {selectedBlock && (
            <div>
              <p className="font-ui text-eyebrow uppercase tracking-[0.16em] text-subtle mb-2">Weekly Structure</p>
              <WeeklyStructurePreview block={selectedBlock} />
            </div>
          )}
        </div>

        <div className="bg-bone border-t border-cream-dark px-6 py-3 flex gap-3 justify-end">
          <button type="button" onClick={onClose}
            className="font-ui text-body-sm text-subtle hover:text-charcoal px-3 py-2">
            Cancel
          </button>
          <button type="submit" disabled={submitting}
            className="font-ui font-semibold text-body-sm text-bone bg-maroon px-4 py-2 rounded-[3px] hover:bg-maroon-ink disabled:opacity-50">
            {submitting ? 'Creating…' : 'Create Program'}
          </button>
        </div>
      </form>
    </div>
  )
}
