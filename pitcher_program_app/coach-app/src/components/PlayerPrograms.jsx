/**
 * PlayerPrograms — 5th tab inside PlayerSlideOver.
 *
 * Sections (top to bottom):
 *   1. Active programs (read-only)        — GET /api/coach/pitcher/{id}/programs?status=active
 *   2. Drafts (D14 completed-only)        — GET /api/coach/pitcher/{id}/drafts
 *   3. Archived programs                  — GET /api/coach/pitcher/{id}/programs?status=archived
 *   4. Hold event log (last 30 days)      — GET /api/coach/pitcher/{id}/program-holds?days=30
 *   5. Phase override controls            — PATCH /api/coach/pitcher/{id}/phase-override
 *
 * The PATCH writes to pitcher_training_model.coach_{throwing,lifting}_phase_override
 * (migration 023) and inserts an audit row into coach_actions. v1 decision: NO
 * recompute of program schedule on override change — A5's recompute path is the
 * future hook. See `coach_routes.py::coach_patch_phase_override` for rationale.
 *
 * Phase divergence pill (throwing ≠ lifting): rendered above the override editor.
 *
 * `initialOverrides` (optional prop): if PlayerSlideOver already has the current
 * model.coach_*_phase_override values, pass them through so the editor starts
 * pre-filled. Otherwise the editor starts empty (untouched override).
 */
import { useState } from 'react'
import { useCoachApi } from '../hooks/useApi'
import { useCoachAuth } from '../hooks/useCoachAuth'
import { patchPhaseOverride } from '../api'

function SectionHeader({ children }) {
  return (
    <h3 className="font-ui font-semibold uppercase text-[10px] tracking-[0.2em] text-maroon mb-1.5">
      {children}
    </h3>
  )
}

function EmptyState({ children }) {
  return (
    <p className="font-ui text-meta text-muted italic">{children}</p>
  )
}

function ProgramRow({ program }) {
  const day = (program.current_day_index ?? 0) + 1
  const held = program.held_days_count ?? 0
  const domainLabel = program.domain
    ? `${program.domain[0].toUpperCase()}${program.domain.slice(1)}`
    : '—'
  return (
    <div className="border-b border-cream-dark/60 last:border-b-0 py-1.5">
      <div className="flex items-baseline justify-between gap-3">
        <span className="font-serif text-body text-charcoal">
          [{domainLabel}] {program.parent_template_id || '—'}
        </span>
        <span className="font-ui text-meta text-muted tabular">
          Day {day}{held > 0 ? ` · Held ${held}` : ''}
        </span>
      </div>
      {program.archive_reason && (
        <div className="font-ui text-meta text-muted italic mt-0.5">
          {program.archive_reason}
        </div>
      )}
    </div>
  )
}

function ProgramsSection({ title, rows, emptyMsg }) {
  return (
    <section>
      <SectionHeader>{title}</SectionHeader>
      {rows && rows.length > 0
        ? rows.map(p => <ProgramRow key={p.program_id} program={p} />)
        : <EmptyState>{emptyMsg}</EmptyState>}
    </section>
  )
}

function HoldEventLog({ events }) {
  return (
    <section>
      <SectionHeader>Hold Events · Last 30 days</SectionHeader>
      {events && events.length > 0
        ? events.map(e => (
            <div
              key={e.hold_event_id}
              className="border-b border-cream-dark/60 last:border-b-0 py-1.5 flex items-baseline justify-between gap-3"
            >
              <span className="font-serif text-body text-charcoal">
                {e.hold_date}
              </span>
              <span className="font-ui text-meta text-muted tabular">
                {e.reason_code || '—'}
              </span>
            </div>
          ))
        : <EmptyState>No holds in the last 30 days.</EmptyState>}
    </section>
  )
}

function DivergencePill({ throwingPhase, liftingPhase }) {
  if (!throwingPhase || !liftingPhase) return null
  if (throwingPhase === liftingPhase) return null
  return (
    <span
      data-testid="phase-divergence-pill"
      className="inline-block bg-amber/10 text-amber font-ui text-[10px] uppercase tracking-[0.12em] px-2 py-0.5 rounded-[2px] border border-amber/30"
    >
      Phases diverge
    </span>
  )
}

function PhaseOverrideControls({ pitcherId, initialOverrides, onSaved }) {
  const { getAccessToken } = useCoachAuth()
  const [throwing, setThrowing] = useState(initialOverrides?.throwing_phase || '')
  const [lifting, setLifting] = useState(initialOverrides?.lifting_phase || '')
  const [saving, setSaving] = useState(false)
  const [savedAt, setSavedAt] = useState(null)
  const [error, setError] = useState(null)
  const [current, setCurrent] = useState(initialOverrides || { throwing_phase: null, lifting_phase: null })

  async function handleSave() {
    setError(null)
    setSaving(true)
    const body = {}
    if (throwing !== (current.throwing_phase || '')) body.throwing_phase = throwing
    if (lifting !== (current.lifting_phase || '')) body.lifting_phase = lifting
    if (Object.keys(body).length === 0) {
      setSaving(false)
      setError('No changes')
      return
    }
    try {
      const result = await patchPhaseOverride(pitcherId, body, getAccessToken())
      const next = result.coach_phase_overrides || { throwing_phase: null, lifting_phase: null }
      setCurrent(next)
      setThrowing(next.throwing_phase || '')
      setLifting(next.lifting_phase || '')
      setSavedAt(Date.now())
      if (onSaved) onSaved(next)
    } catch (err) {
      setError(err.message || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section>
      <SectionHeader>Coach Phase Override</SectionHeader>
      <div className="mb-2">
        <DivergencePill
          throwingPhase={current.throwing_phase}
          liftingPhase={current.lifting_phase}
        />
      </div>
      <p className="font-ui text-meta text-muted mb-2">
        Leave blank to clear the override and fall back to the team phase.
      </p>
      <div className="space-y-2">
        <label className="block">
          <span className="block font-ui text-meta text-charcoal mb-0.5">Throwing phase</span>
          <input
            type="text"
            value={throwing}
            onChange={e => setThrowing(e.target.value)}
            maxLength={60}
            placeholder="off_season / preseason / in_season …"
            className="w-full border border-cream-dark rounded-[3px] px-2 py-1 font-ui text-body-sm text-charcoal"
          />
        </label>
        <label className="block">
          <span className="block font-ui text-meta text-charcoal mb-0.5">Lifting phase</span>
          <input
            type="text"
            value={lifting}
            onChange={e => setLifting(e.target.value)}
            maxLength={60}
            placeholder="strength / power / hypertrophy …"
            className="w-full border border-cream-dark rounded-[3px] px-2 py-1 font-ui text-body-sm text-charcoal"
          />
        </label>
        <div className="flex items-center gap-3 pt-1">
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="py-1.5 px-3 font-ui text-body-sm font-semibold text-bone bg-maroon hover:bg-maroon-ink rounded-[3px] disabled:opacity-50"
          >
            {saving ? 'Saving…' : 'Save override'}
          </button>
          {savedAt && !error && (
            <span className="font-ui text-meta text-forest">Saved.</span>
          )}
          {error && (
            <span className="font-ui text-meta text-crimson">{error}</span>
          )}
        </div>
      </div>
    </section>
  )
}

export default function PlayerPrograms({ pitcherId, initialOverrides }) {
  // Plan 7 / A3-coach endpoints. We split active vs archived into two calls
  // rather than fetching all + filtering — the backend's status filter is
  // idiomatic and trims the payload server-side.
  const active = useCoachApi(pitcherId ? `/api/coach/pitcher/${pitcherId}/programs?status=active` : null)
  const drafts = useCoachApi(pitcherId ? `/api/coach/pitcher/${pitcherId}/drafts` : null)
  const archived = useCoachApi(pitcherId ? `/api/coach/pitcher/${pitcherId}/programs?status=archived` : null)
  const holds = useCoachApi(pitcherId ? `/api/coach/pitcher/${pitcherId}/program-holds?days=30` : null)

  return (
    <div className="space-y-5">
      <ProgramsSection
        title="Active Programs"
        rows={active.data?.programs || []}
        emptyMsg="No active programs."
      />
      <ProgramsSection
        title="Drafts"
        rows={drafts.data?.drafts || []}
        emptyMsg="No saved drafts."
      />
      <ProgramsSection
        title="Archived"
        rows={archived.data?.programs || []}
        emptyMsg="No archived programs."
      />
      <HoldEventLog events={holds.data?.events || []} />
      <PhaseOverrideControls
        pitcherId={pitcherId}
        initialOverrides={initialOverrides}
      />
    </div>
  )
}

// Exported for tests so we don't have to mount the whole tab tree.
export { PhaseOverrideControls, DivergencePill, ProgramsSection, HoldEventLog }
