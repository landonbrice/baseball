import { useState } from 'react'
import { useCoachApi } from '../hooks/useApi'
import { useCoachAuth } from '../hooks/useCoachAuth'
import { postCoachApi } from '../api'
import { useToast } from '../components/shell/Toast'
import Masthead from '../components/shell/Masthead'
import Scoreboard from '../components/shell/Scoreboard'
import EditorialState from '../components/shell/EditorialState'
import BlockCard from '../components/programs/BlockCard'
import CreateProgramSlideOver from '../components/programs/CreateProgramSlideOver'
import PlayerBuiltProgramsStrip from '../components/team-programs/PlayerBuiltProgramsStrip'
import { TODAY } from '../utils/formatToday'

/**
 * Plan 7 / C3 — Team Programs page rebuild.
 *
 * Five sections in order:
 *   1. Masthead (+ "Build Program" actionSlot opens the legacy slide-over;
 *      C4 will replace its body with the BuilderSlideOver selector)
 *   2. Scoreboard (5 cells, derived from active blocks)
 *   3. Active Team Programs grid — legacy /team-programs/active rows
 *   4. Library — canonical block_library templates from A12
 *   5. Recent Player-Built Programs — strip from C3 endpoint
 */
export default function TeamPrograms() {
  const { getAccessToken } = useCoachAuth()
  const toast = useToast()
  const { data: activeData, loading: activeLoading, error: activeError, refetch: refetchActive } =
    useCoachApi('/api/coach/team-programs/active')
  const { data: templatesData, loading: templatesLoading, error: templatesError } =
    useCoachApi('/api/programs/templates')
  const { data: recentData, loading: recentLoading, error: recentError } =
    useCoachApi('/api/coach/programs/recent-player-built?limit=20')

  const [showCreate, setShowCreate] = useState(false)

  const active = activeData?.blocks || []
  const templates = templatesData?.templates || []
  const recent = recentData?.programs || []

  // Library list still drives the existing CreateProgramSlideOver chrome. Until
  // C4 replaces the body with BuilderSlideOver, the legacy slide-over needs
  // `block_template_id` + `duration_days`-shaped entries. We pass the canonical
  // templates as a thin compat list — the slide-over only reads the id + name
  // for the picker.
  const slideOverLibrary = templates.map(t => ({
    block_template_id: t.block_template_id,
    name: t.name,
    block_type: t.domain,
    duration_days: (t.duration_range_weeks?.[0] || 0) * 7,
  }))

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
    {
      label: 'Templates',
      value: String(templates.length),
      sub: templates.length === 0 ? 'library empty' : 'canonical',
    },
    {
      label: 'Weeks Remaining',
      value: weeksRemaining != null ? `${weeksRemaining}w` : '—',
      sub: minEndDate
        ? `ends ${minEndDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`
        : '—',
    },
    {
      label: 'Recent Builds',
      value: String(recent.length),
      sub: recent.length ? 'last 20' : 'none yet',
    },
    { label: 'Next Milestone', value: '—', sub: 'data pending' },
  ]

  async function handleEnd(blockId) {
    try {
      await postCoachApi(`/api/coach/team-programs/${blockId}/end`, {}, getAccessToken())
      toast.warn('Block ended')
      refetchActive()
    } catch (err) {
      toast.error(err.message)
    }
  }

  const anyLoading = activeLoading || templatesLoading || recentLoading
  const fatalError = activeError  // active is the only required section to render

  return (
    <>
      <Masthead
        kicker="Chicago · Pitching Staff"
        title="Team Programs"
        date={TODAY}
        actionSlot={
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            className="font-ui font-semibold text-body-sm text-bone bg-maroon hover:bg-maroon-ink px-3 py-1.5 rounded-[3px]"
          >
            + Build Program
          </button>
        }
      />
      {scoreboard && <Scoreboard cells={scoreboard} />}

      <div className="p-6 space-y-8">
        {anyLoading && !activeData && !templatesData && !recentData && (
          <EditorialState type="loading" copy="Loading programs…" />
        )}
        {fatalError && (
          <EditorialState type="error" copy={fatalError} retry={refetchActive} />
        )}

        {!fatalError && (
          <>
            {/* Section 3: Active Team Programs grid */}
            <section>
              <p className="font-ui text-eyebrow uppercase tracking-[0.2em] text-maroon mb-3">
                Active Programs
              </p>
              {activeLoading && !activeData ? (
                <EditorialState type="loading" copy="Loading active programs…" />
              ) : active.length === 0 ? (
                <EditorialState
                  type="empty"
                  copy="No active programs. Build one from the templates below."
                />
              ) : (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                  {active.map(b => (
                    <BlockCard key={b.block_id} block={b} isActive onEnd={handleEnd} />
                  ))}
                </div>
              )}
            </section>

            {/* Section 4: Library of canonical templates (A12) */}
            <section>
              <p className="font-ui text-eyebrow uppercase tracking-[0.2em] text-subtle mb-3">
                Library
              </p>
              {templatesLoading && !templatesData ? (
                <EditorialState type="loading" copy="Loading templates…" />
              ) : templatesError ? (
                <p className="font-ui text-body-sm text-crimson">{templatesError}</p>
              ) : templates.length === 0 ? (
                <EditorialState
                  type="empty"
                  copy="No canonical templates seeded yet."
                />
              ) : (
                <ul className="divide-y divide-cream-dark border border-cream-dark rounded-[3px] bg-bone">
                  {templates.map(t => {
                    const weeks = t.duration_range_weeks
                    const weeksStr = Array.isArray(weeks) && weeks.length === 2
                      ? `${weeks[0]}–${weeks[1]}wk`
                      : '—'
                    return (
                      <li
                        key={t.block_template_id}
                        className="px-3 py-2 flex items-center gap-3"
                      >
                        <div className="flex-1 min-w-0">
                          <h4 className="font-serif font-bold text-body text-charcoal truncate">
                            {t.name}
                          </h4>
                          <p className="font-ui text-meta text-subtle truncate">
                            <span className="capitalize">{t.domain || '—'}</span>
                            <span> · </span>
                            {weeksStr}
                            {t.implied_phase ? ` · ${t.implied_phase}` : ''}
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={() => setShowCreate(true)}
                          className="font-ui text-meta font-semibold text-bone bg-maroon px-2.5 py-1.5 rounded-[3px] hover:bg-maroon-ink flex-shrink-0"
                        >
                          Build
                        </button>
                      </li>
                    )
                  })}
                </ul>
              )}
            </section>

            {/* Section 5: Recent Player-Built Programs roster strip */}
            <section>
              <p className="font-ui text-eyebrow uppercase tracking-[0.2em] text-subtle mb-3">
                Recent Player-Built Programs
              </p>
              {recentLoading && !recentData ? (
                <EditorialState type="loading" copy="Loading recent builds…" />
              ) : recentError ? (
                <p className="font-ui text-body-sm text-crimson">{recentError}</p>
              ) : (
                <PlayerBuiltProgramsStrip programs={recent} />
              )}
            </section>
          </>
        )}
      </div>

      {showCreate && (
        <>
          <div className="fixed inset-0 bg-black/20 z-40" onClick={() => setShowCreate(false)} />
          <CreateProgramSlideOver
            library={slideOverLibrary}
            onClose={() => setShowCreate(false)}
          />
        </>
      )}
    </>
  )
}
