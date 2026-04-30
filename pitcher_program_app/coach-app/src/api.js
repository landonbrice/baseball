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
  return postCoachApi(`/api/pitcher/${pitcherId}/preview-mutations`, body, accessToken)
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
