/**
 * BuildEntrypointSelector — Plan 7 / C4.
 *
 * Three-option modal sheet rendered when a coach taps "+ Build Program":
 *   1. "Build a team program"        → interview_mode='team_personalize'
 *   2. "Build for a specific pitcher" → flips to PitcherPicker, then
 *                                       interview_mode='personalize' + pitcherIdForCoach
 *   3. "Author a new template"        → interview_mode='authoring'
 *
 * Pure UI — the caller (CreateProgramSlideOver) drives the state machine
 * and forwards the chosen mode into the shared BuilderSlideOver.
 *
 * `onPick({ mode })` — mode is the SELECTOR ID, not the final interview_mode
 * forwarded to the slide-over. CreateProgramSlideOver maps
 *   'team_personalize'        → BuilderSlideOver interview_mode='team_personalize'
 *   'personalize_for_pitcher' → PitcherPicker, then interview_mode='personalize'
 *   'authoring'               → BuilderSlideOver interview_mode='authoring'
 */
import { useEffect } from 'react'

const SHEET_WIDTH = 480

const OPTIONS = [
  {
    id: 'team_personalize',
    title: 'Build a team program',
    description:
      'A program for the whole pitching staff. The interview tunes it for team-level defaults.',
  },
  {
    id: 'personalize_for_pitcher',
    title: 'Build for a specific pitcher',
    description:
      "Pulls in that pitcher's profile, injury history, and current state before tuning.",
  },
  {
    id: 'authoring',
    title: 'Author a new template',
    description:
      'No pitcher attached. The output becomes a reusable template for the team library.',
  },
]

export default function BuildEntrypointSelector({ onPick, onClose }) {
  // ESC closes the entire flow (consistent with the rest of the slide-overs).
  useEffect(() => {
    function onKey(e) {
      if (e.key === 'Escape') onClose?.()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      role="dialog"
      aria-label="Build a program"
      className="fixed top-0 right-0 h-full bg-bone shadow-xl z-50 flex flex-col border-l border-cream-dark"
      style={{ width: SHEET_WIDTH }}
    >
      <div className="flex items-center justify-between px-6 py-4 border-b border-cream-dark">
        <h2 className="font-serif font-bold text-h1 text-charcoal">Build a Program</h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="font-ui text-h1 text-muted hover:text-charcoal leading-none"
        >
          ×
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-3">
        <p className="font-ui text-body-sm text-subtle mb-2">
          Pick a starting point. You can change the goal and details during the interview.
        </p>
        {OPTIONS.map((opt) => (
          <button
            key={opt.id}
            type="button"
            onClick={() => onPick({ mode: opt.id })}
            className="w-full text-left px-4 py-4 border border-cream-dark rounded-[6px] bg-bone hover:border-maroon hover:bg-cream focus:outline-none focus:ring-2 focus:ring-maroon"
            data-testid={`entrypoint-${opt.id}`}
          >
            <div className="font-serif font-semibold text-h3 text-charcoal mb-1">{opt.title}</div>
            <div className="font-ui text-body-sm text-subtle leading-snug">{opt.description}</div>
          </button>
        ))}
      </div>
    </div>
  )
}
