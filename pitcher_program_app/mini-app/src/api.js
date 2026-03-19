const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '');

/**
 * Fetch from the data API with optional auth header.
 * @param {string} path - API path (e.g. "/api/exercises")
 * @param {string|null} initData - Telegram initData for auth
 */
export async function fetchApi(path, initData = null) {
  const headers = {};
  if (initData) {
    headers['X-Telegram-Init-Data'] = initData;
  }

  const res = await fetch(`${API_BASE}${path}`, { headers });

  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`);
  }

  return res.json();
}

/**
 * Resolve auth: if we have initData, call /api/auth/resolve to get pitcher_id.
 * If we already have pitcherId (dev mode), skip.
 */
export async function resolveAuth(initData) {
  const data = await fetchApi(`/api/auth/resolve?initData=${encodeURIComponent(initData)}`);
  return data.pitcher_id;
}

/**
 * Fetch upcoming rotation days preview.
 */
export async function fetchUpcoming(pitcherId, initData) {
  return fetchApi(`/api/pitcher/${pitcherId}/upcoming`, initData);
}

/**
 * Toggle exercise completion (optimistic UI — call after local state update).
 */
export async function toggleExercise(pitcherId, date, exerciseId, completed, initData) {
  return postApi(`/api/pitcher/${pitcherId}/complete-exercise`, { date, exercise_id: exerciseId, completed }, initData);
}

/**
 * POST to the data API with optional auth header.
 */
export async function postApi(path, body, initData = null) {
  const headers = { 'Content-Type': 'application/json' };
  if (initData) headers['X-Telegram-Init-Data'] = initData;

  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

/**
 * Submit a daily check-in.
 */
export async function submitCheckin(pitcherId, armFeel, sleepHours, initData) {
  return postApi(`/api/pitcher/${pitcherId}/checkin`, { arm_feel: armFeel, sleep_hours: sleepHours }, initData);
}

/**
 * Submit a post-outing report.
 */
export async function submitOuting(pitcherId, pitchCount, postArmFeel, notes, initData) {
  return postApi(`/api/pitcher/${pitcherId}/outing`, { pitch_count: pitchCount, post_arm_feel: postArmFeel, notes }, initData);
}

/**
 * Ask a free-text question.
 */
export async function submitAsk(pitcherId, question, history, initData) {
  return postApi(`/api/pitcher/${pitcherId}/ask`, { question, history }, initData);
}

/**
 * Send a chat message (unified endpoint for check-in, outing, text).
 * Returns { messages: [{ type, content, buttons? }] }
 */
export async function sendChat(pitcherId, message, type = 'text', initData = null) {
  return postApi(`/api/pitcher/${pitcherId}/chat`, { message, type }, initData);
}

/**
 * Set when the pitcher expects to pitch next.
 * days_until_outing: 0 = today, 1 = tomorrow, etc.
 */
export async function setNextOuting(pitcherId, daysUntil, initData = null) {
  return postApi(`/api/pitcher/${pitcherId}/set-next-outing`, { days_until_outing: daysUntil }, initData);
}

/**
 * Fetch saved plans for a pitcher.
 */
export async function fetchPlans(pitcherId, initData = null) {
  return fetchApi(`/api/pitcher/${pitcherId}/plans`, initData);
}

/**
 * Save a new plan.
 */
export async function savePlan(pitcherId, plan, initData = null) {
  return postApi(`/api/pitcher/${pitcherId}/plans`, plan, initData);
}

/**
 * Deactivate a saved plan.
 */
export async function deactivatePlan(pitcherId, planId, initData = null) {
  return postApi(`/api/pitcher/${pitcherId}/plans/${planId}/deactivate`, {}, initData);
}
