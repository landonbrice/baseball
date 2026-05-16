import { useState, useEffect } from 'react'
import { useCoachAuth } from '../../hooks/useCoachAuth'
import {
  fetchResearchDocs,
  patchTemplateResearchDocs,
} from '../../api'

/**
 * Plan 8 / C3 — modal that lets a coach attach/detach research docs from
 * a `block_library` template.
 *
 * Two-column UI: Available (left) and Attached (right). Clicking a row in
 * Available adds it to Attached; clicking a row in Attached removes it.
 * Save commits the new `research_doc_ids` array via PATCH.
 *
 * v1 is attach-existing only — coach picks from the canonical on-disk doc
 * set. Authoring + frontmatter validation + storage choice defer to Plan 9
 * (L6).
 *
 * Props:
 *   - template:  {block_template_id, name, research_doc_ids: [...]}
 *   - onClose:   fn() — coach dismissed the modal
 *   - onSaved:   fn(updatedTemplate) — successful save
 */
export default function TemplateResearchEditor({ template, onClose, onSaved }) {
  const { getAccessToken } = useCoachAuth()
  const [allDocs, setAllDocs] = useState([])
  const [attachedIds, setAttachedIds] = useState(
    Array.isArray(template?.research_doc_ids) ? template.research_doc_ids : []
  )
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const { docs } = await fetchResearchDocs(getAccessToken())
        if (!cancelled) setAllDocs(docs || [])
      } catch {
        if (!cancelled) setError("Couldn't load research docs.")
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
    // getAccessToken intentionally not in deps — see useCoachAuth note;
    // capturing once on mount is correct for this one-shot fetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function attach(docId) {
    if (!attachedIds.includes(docId)) {
      setAttachedIds([...attachedIds, docId])
    }
  }
  function detach(docId) {
    setAttachedIds(attachedIds.filter(d => d !== docId))
  }

  async function handleSave() {
    setSaving(true)
    setError(null)
    try {
      const { template: updated } = await patchTemplateResearchDocs(
        template.block_template_id,
        attachedIds,
        getAccessToken(),
      )
      onSaved?.(updated)
      onClose?.()
    } catch {
      setError("Could not save. Try again.")
      setSaving(false)
    }
  }

  const availableDocs = allDocs.filter(d => !attachedIds.includes(d.id))
  const attachedDocs = allDocs.filter(d => attachedIds.includes(d.id))

  return (
    <div
      role="dialog"
      aria-label="Edit research docs"
      className="fixed top-0 right-0 h-full bg-bone shadow-xl z-50 flex flex-col border-l border-cream-dark"
      style={{ width: 560 }}
    >
      <div className="flex items-center justify-between px-6 py-4 border-b border-cream-dark">
        <div>
          <h2 className="font-serif font-bold text-h2 text-charcoal">Research docs</h2>
          <p className="font-ui text-body-sm text-subtle">{template?.name}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="font-ui text-h1 text-muted hover:text-charcoal leading-none"
        >
          ×
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4">
        {loading && (
          <p className="font-ui text-body-sm text-subtle">Loading…</p>
        )}
        {error && (
          <p className="font-ui text-body-sm text-crimson" role="alert">
            {error}
          </p>
        )}
        {!loading && (
          <div className="grid grid-cols-2 gap-4">
            <div>
              <h3 className="font-serif font-semibold text-body mb-2">Available</h3>
              <ul data-testid="available-docs" className="space-y-1">
                {availableDocs.map(d => (
                  <li key={d.id}>
                    <button
                      type="button"
                      onClick={() => attach(d.id)}
                      data-testid={`attach-${d.id}`}
                      className="w-full text-left px-3 py-2 border border-cream-dark rounded hover:border-maroon hover:bg-cream"
                    >
                      <div className="font-serif font-semibold text-body-sm text-charcoal">
                        {d.title}
                      </div>
                      <div className="font-ui text-meta text-subtle">{d.summary}</div>
                    </button>
                  </li>
                ))}
                {availableDocs.length === 0 && (
                  <li className="font-ui text-body-sm text-subtle italic">
                    All docs attached.
                  </li>
                )}
              </ul>
            </div>
            <div>
              <h3 className="font-serif font-semibold text-body mb-2">Attached</h3>
              <ul data-testid="attached-docs" className="space-y-1">
                {attachedDocs.map(d => (
                  <li key={d.id}>
                    <button
                      type="button"
                      onClick={() => detach(d.id)}
                      data-testid={`detach-${d.id}`}
                      className="w-full text-left px-3 py-2 border border-maroon rounded bg-cream hover:border-crimson"
                    >
                      <div className="font-serif font-semibold text-body-sm text-charcoal">
                        {d.title}
                      </div>
                      <div className="font-ui text-meta text-subtle">Click to remove</div>
                    </button>
                  </li>
                ))}
                {attachedDocs.length === 0 && (
                  <li className="font-ui text-body-sm text-subtle italic">
                    No docs attached.
                  </li>
                )}
              </ul>
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-cream-dark">
        <button
          type="button"
          onClick={onClose}
          disabled={saving}
          className="font-ui text-body-sm text-muted hover:text-charcoal disabled:opacity-50"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={handleSave}
          disabled={loading || saving}
          data-testid="research-save"
          className="font-ui text-body-sm bg-maroon text-cream px-4 py-2 rounded hover:bg-maroon-ink disabled:opacity-50"
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
      </div>
    </div>
  )
}
