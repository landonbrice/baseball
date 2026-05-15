const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '')

export async function fetchCoachApi(path, accessToken) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Authorization': `Bearer ${accessToken}` },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body?.error?.message || body?.detail || `API ${res.status}`)
  }
  return res.json()
}

export async function postCoachApi(path, body, accessToken) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data?.error?.message || data?.detail || `API ${res.status}`)
  }
  return res.json()
}

export async function patchCoachApi(path, body, accessToken) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'PATCH',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data?.error?.message || data?.detail || `API ${res.status}`)
  }
  return res.json()
}

export async function deleteCoachApi(path, accessToken) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'DELETE',
    headers: { 'Authorization': `Bearer ${accessToken}` },
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data?.error?.message || data?.detail || `API ${res.status}`)
  }
  return res.json()
}

// -- F4: rationale preview --

export async function previewMutations(pitcherId, body, accessToken) {
  return postCoachApi(`/api/coach/pitcher/${pitcherId}/preview-mutations`, body, accessToken)
}

// -- Plan 7 / C1: active programs for a pitcher (Team Overview strip) --

export async function fetchPitcherActivePrograms(pitcherId, accessToken) {
  return fetchCoachApi(`/api/coach/pitcher/${pitcherId}/programs?status=active`, accessToken)
}

// -- Plan 7 / C2: program hold-event log + phase override --

export async function fetchProgramHolds(pitcherId, accessToken, { days = 30 } = {}) {
  return fetchCoachApi(`/api/coach/pitcher/${pitcherId}/program-holds?days=${days}`, accessToken)
}

export async function patchPhaseOverride(pitcherId, body, accessToken) {
  return patchCoachApi(`/api/coach/pitcher/${pitcherId}/phase-override`, body, accessToken)
}

// -- Plan 7 / C3: program templates + recent player-built strip --

export async function fetchTemplates(accessToken, { domain, phase } = {}) {
  const params = new URLSearchParams()
  if (domain) params.set('domain', domain)
  if (phase) params.set('phase', phase)
  const qs = params.toString()
  // Coach mirror — see api/coach_routes.py::coach_get_program_templates.
  // The pitcher-facing /api/programs/templates rejects Supabase Bearer JWTs.
  const path = qs
    ? `/api/coach/programs/templates?${qs}`
    : '/api/coach/programs/templates'
  return fetchCoachApi(path, accessToken)
}

export async function fetchRecentPlayerBuiltPrograms(accessToken, { limit = 20 } = {}) {
  return fetchCoachApi(
    `/api/coach/programs/recent-player-built?limit=${limit}`,
    accessToken,
  )
}

// -- Plan 7 / C4: coach Program Builder client fns --
//
// These wrap the coach mirror endpoints of /api/coach/programs/builder/*
// (see api/coach_routes.py Plan 2 + C4 extensions). The shared
// BuilderSlideOver consumes a token-bound `api` adapter object (see
// CreateProgramSlideOver) so the slide-over never touches auth headers.

export async function coachFetchBuilderCandidates(envelope, accessToken) {
  return postCoachApi('/api/coach/programs/builder/candidates', envelope, accessToken)
}

export async function coachSendBuilderTurn(sessionId, userMessage, accessToken) {
  return postCoachApi(
    '/api/coach/programs/builder/turn',
    { session_id: sessionId, user_message: userMessage },
    accessToken,
  )
}

export async function coachFinalizeBuilder(sessionId, chosenTemplateId, tunedSpec, accessToken) {
  return postCoachApi(
    '/api/coach/programs/builder/finalize',
    { session_id: sessionId, chosen_template_id: chosenTemplateId, tuned_spec: tunedSpec },
    accessToken,
  )
}

export async function coachActivateProgram(programId, accessToken) {
  return postCoachApi(`/api/coach/programs/${programId}/activate`, {}, accessToken)
}

export async function coachArchiveProgram(programId, reason, accessToken) {
  return postCoachApi(`/api/coach/programs/${programId}/archive`, { reason }, accessToken)
}

export async function coachInterpretGoal(text, domain, accessToken) {
  return postCoachApi(
    '/api/coach/programs/builder/interpret-goal',
    { text, domain },
    accessToken,
  )
}

// -- Plan 8 / C3: coach-authored research doc attach workflow --
//
// fetchResearchDocs hits the new `/api/coach/research-docs` listing endpoint
// (returns {docs: [{id, title, summary, applies_to, priority}, ...]} read
// from `data/knowledge/research/*.md` on the backend).
//
// patchTemplateResearchDocs sets the picked doc ids on a block_library row:
//   PATCH /api/coach/block-library/{template_id}/research-docs
//   body: { research_doc_ids: [...] }
//   returns: { template: <updated row> }

export async function fetchResearchDocs(accessToken) {
  return fetchCoachApi('/api/coach/research-docs', accessToken)
}

export async function patchTemplateResearchDocs(templateId, docIds, accessToken) {
  return patchCoachApi(
    `/api/coach/block-library/${templateId}/research-docs`,
    { research_doc_ids: docIds },
    accessToken,
  )
}

// -- Plan 8 / C1: insight Archive / Accept CTAs --

export async function actOnInsight(insightId, action, accessToken) {
  return postCoachApi(
    `/api/coach/insights/${insightId}/action`,
    { action },
    accessToken,
  )
}

// Composite helper — the Archive button on a drift insight conceptually
// does one action but issues two backend calls: archive the program, then
// dismiss the insight. Kept as a separate helper so each step is testable
// independently and so a failure between steps is recoverable (next 9am
// digest will dedup-suppress the stale insight).
export async function archiveProgramByInsight(programId, reason, accessToken) {
  return postCoachApi(
    `/api/coach/programs/${programId}/archive`,
    { reason },
    accessToken,
  )
}

// -- Nudge --

export async function nudgePitcher(pitcherId, accessToken) {
  const res = await fetch(`${API_BASE}/api/coach/pitcher/${pitcherId}/nudge`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${accessToken}` },
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data?.detail || `API ${res.status}`)
  }
  return res.json()
}

// -- Stub functions (backend wiring in future sprint) --

export async function createTeamProgram(payload) {
  return Promise.resolve({ status: 'stub', payload })
}

export async function updatePhase(payload) {
  return Promise.resolve({ status: 'stub', payload })
}

export async function createPhase(payload) {
  return Promise.resolve({ status: 'stub', payload })
}

export async function advancePhase() {
  return Promise.resolve({ status: 'stub' })
}
