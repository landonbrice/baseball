/**
 * PitcherPicker — Plan 7 / C4.
 *
 * Step 2 of the "Build for a specific pitcher" flow. Lists the team roster
 * (from `/api/coach/team/overview`), lets the coach pick one. On pick,
 * forwards `{ pitcher_id, name }` to the parent which then mounts the shared
 * BuilderSlideOver with interview_mode='personalize' + pitcherIdForCoach.
 *
 * v1 is deliberately a flat list with no search/filter — UChicago Baseball
 * has 12 pitchers and the picker rarely opens. If the roster grows, drop in
 * a top-of-list filter input.
 */
import { useCoachApi } from '../hooks/useApi'

const SHEET_WIDTH = 480

export default function PitcherPicker({ onPick, onClose, onBack }) {
  const { data, loading, error } = useCoachApi('/api/coach/team/overview')
  const roster = Array.isArray(data?.roster) ? data.roster : []

  return (
    <div
      role="dialog"
      aria-label="Pick a pitcher"
      className="fixed top-0 right-0 h-full bg-bone shadow-xl z-50 flex flex-col border-l border-cream-dark"
      style={{ width: SHEET_WIDTH }}
    >
      <div className="flex items-center justify-between px-6 py-4 border-b border-cream-dark">
        <div className="flex items-center gap-3">
          {onBack && (
            <button
              type="button"
              onClick={onBack}
              aria-label="Back"
              className="font-ui text-body-sm text-muted hover:text-charcoal"
            >
              ← Back
            </button>
          )}
          <h2 className="font-serif font-bold text-h1 text-charcoal">Pick a Pitcher</h2>
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
          <p className="font-ui text-body-sm text-subtle">Loading roster…</p>
        )}
        {error && (
          <p className="font-ui text-body-sm text-crimson" role="alert">
            Couldn't load roster: {error}
          </p>
        )}
        {!loading && !error && roster.length === 0 && (
          <p className="font-ui text-body-sm text-subtle">
            No pitchers on this team yet.
          </p>
        )}
        {!loading && !error && roster.length > 0 && (
          <ul className="space-y-2" data-testid="pitcher-picker-list">
            {roster.map((p) => (
              <li key={p.pitcher_id}>
                <button
                  type="button"
                  onClick={() => onPick({ pitcher_id: p.pitcher_id, name: p.name })}
                  className="w-full text-left px-4 py-3 border border-cream-dark rounded-[6px] bg-bone hover:border-maroon hover:bg-cream focus:outline-none focus:ring-2 focus:ring-maroon flex items-center justify-between"
                  data-testid={`pick-pitcher-${p.pitcher_id}`}
                >
                  <div>
                    <div className="font-serif font-semibold text-h3 text-charcoal leading-tight">
                      {p.name || p.pitcher_id}
                    </div>
                    {p.role && (
                      <div className="font-ui text-body-sm text-subtle leading-tight">
                        {p.role}
                      </div>
                    )}
                  </div>
                  <span className="font-ui text-body-sm text-muted">→</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
