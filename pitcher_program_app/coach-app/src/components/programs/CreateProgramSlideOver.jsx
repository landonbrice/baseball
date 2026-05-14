/**
 * CreateProgramSlideOver — Plan 7 / C4 rebuild.
 *
 * The coach "+ Build Program" chrome. Drives a three-step state machine:
 *
 *   1. <BuildEntrypointSelector>           → pick a build mode
 *   2. <PitcherPicker> (conditional)        → pick the target pitcher
 *   3. <BuilderSlideOver>                   → shared builder flow
 *
 * Locked decisions:
 *   - L2: coach build UX reuses the shared BuilderSlideOver with `interview_mode`.
 *   - L9: BuilderSlideOver mounts inside this slide-over chrome (no separate page).
 *
 * The shared BuilderSlideOver takes its API surface as a prop so it can run
 * inside both mini-app (pitcher) and coach-app. We wrap the six coach client
 * fns in a memoized adapter that closes over the current access token.
 *
 * The legacy `library` prop is accepted (and ignored) so the existing
 * TeamPrograms callsite keeps compiling during the C4 cutover.
 */
import { useState, useMemo } from 'react'
import { useCoachAuth } from '../../hooks/useCoachAuth'
import BuilderSlideOver from '@shared/builder/BuilderSlideOver.jsx'
import BuildEntrypointSelector from '../BuildEntrypointSelector'
import PitcherPicker from '../PitcherPicker'
import {
  coachFetchBuilderCandidates,
  coachSendBuilderTurn,
  coachFinalizeBuilder,
  coachActivateProgram,
  coachArchiveProgram,
  coachInterpretGoal,
} from '../../api'

// Selector ids → interview_mode forwarded to BuilderSlideOver.
const SELECTOR_TO_MODE = {
  team_personalize: 'team_personalize',
  personalize_for_pitcher: 'personalize',
  authoring: 'authoring',
}

export default function CreateProgramSlideOver({
  onClose,
  onProgramActivated,
  onDraftSaved,
  // eslint-disable-next-line no-unused-vars -- legacy prop preserved for back-compat with TeamPrograms callsite
  library,
}) {
  const { getAccessToken } = useCoachAuth()

  // null → selector; otherwise an id from SELECTOR_TO_MODE
  const [pickedSelector, setPickedSelector] = useState(null)
  // null → picker (when pickedSelector === 'personalize_for_pitcher'); else {pitcher_id, name}
  const [pickedPitcher, setPickedPitcher] = useState(null)

  // Token-bound API adapter consumed by the shared BuilderSlideOver.
  // getAccessToken is sync (`session?.access_token || ''`) — we call it on
  // every request so a Supabase refresh during a long Socratic loop swaps
  // the bearer in without remounting. Same pattern as the mini-app's
  // MiniAppBuilderSlideOver adapter.
  const api = useMemo(
    () => ({
      fetchCandidates: (envelope)            => coachFetchBuilderCandidates(envelope, getAccessToken()),
      sendTurn:        (sid, msg)            => coachSendBuilderTurn(sid, msg, getAccessToken()),
      finalize:        (sid, tplId, spec)    => coachFinalizeBuilder(sid, tplId, spec, getAccessToken()),
      activateProgram: (programId)           => coachActivateProgram(programId, getAccessToken()),
      archiveProgram:  (programId, reason)   => coachArchiveProgram(programId, reason, getAccessToken()),
      interpretGoal:   (text, domain)        => coachInterpretGoal(text, domain, getAccessToken()),
    }),
    [getAccessToken],
  )

  // ---- Step 1: entry-point selector ----
  if (pickedSelector === null) {
    return (
      <BuildEntrypointSelector
        onPick={({ mode }) => setPickedSelector(mode)}
        onClose={onClose}
      />
    )
  }

  // ---- Step 2 (conditional): pitcher picker ----
  if (pickedSelector === 'personalize_for_pitcher' && !pickedPitcher) {
    return (
      <PitcherPicker
        onPick={setPickedPitcher}
        onClose={onClose}
        onBack={() => setPickedSelector(null)}
      />
    )
  }

  // ---- Step 3: BuilderSlideOver ----
  const interviewMode = SELECTOR_TO_MODE[pickedSelector] || 'team_personalize'
  return (
    <BuilderSlideOver
      api={api}
      interview_mode={interviewMode}
      pitcherIdForCoach={pickedPitcher?.pitcher_id || null}
      onClose={onClose}
      onProgramActivated={onProgramActivated}
      onDraftSaved={onDraftSaved}
    />
  )
}
