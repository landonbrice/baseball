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
 * Submit post-throw arm feel rating (1-5).
 */
export async function submitThrowFeel(pitcherId, date, postThrowFeel, initData) {
  return postApi(`/api/pitcher/${pitcherId}/throw-feel`, { date, post_throw_feel: postThrowFeel }, initData);
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
export async function sendChat(pitcherId, message, type = 'text', initData = null, history = []) {
  return postApi(`/api/pitcher/${pitcherId}/chat`, { message, type, history }, initData);
}

/**
 * Fetch week summary (Mon-Sun with per-day status).
 */
export async function fetchWeekSummary(pitcherId, initData = null) {
  return fetchApi(`/api/pitcher/${pitcherId}/week-summary`, initData);
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

/**
 * Activate a saved plan (set active=true).
 */
export async function activatePlan(pitcherId, planId, initData = null) {
  return postApi(`/api/pitcher/${pitcherId}/plans/${planId}/activate`, {}, initData);
}

/**
 * Generate a custom plan from user selections.
 */
export async function generatePlan(pitcherId, options, initData = null) {
  return postApi(`/api/pitcher/${pitcherId}/generate-plan`, options, initData);
}

/**
 * Send a chat message with plan context (for plan detail chat).
 */
export async function sendChatWithPlan(pitcherId, message, planContext, initData = null, history = []) {
  return postApi(`/api/pitcher/${pitcherId}/chat`, { message, type: 'text', history, plan_context: planContext }, initData);
}

/**
 * Apply a saved plan to today's daily log entry.
 */
export async function applyPlanToToday(pitcherId, planId, initData = null) {
  return postApi(`/api/pitcher/${pitcherId}/apply-plan/${planId}`, {}, initData);
}

/**
 * Fetch chat history for cross-platform conversation persistence.
 */
export async function fetchChatHistory(pitcherId, initData = null, limit = 30) {
  return fetchApi(`/api/pitcher/${pitcherId}/chat-history?limit=${limit}`, initData);
}

/**
 * Fetch enhanced morning status (arm feel trend, last interaction, schedule).
 */
export async function fetchMorningStatus(pitcherId, initData = null) {
  return fetchApi(`/api/pitcher/${pitcherId}/morning-status`, initData);
}

/**
 * Fetch staff pulse — team check-in status, roles, rotation info.
 */
export async function fetchStaffPulse(initData = null) {
  return fetchApi('/api/staff/pulse', initData);
}

/**
 * Fetch 4-week arm feel trend data for insight chart.
 */
export async function fetchTrend(pitcherId, initData = null) {
  return fetchApi(`/api/pitcher/${pitcherId}/trend`, initData);
}

/**
 * Fetch alternative exercises for swapping.
 */
export async function fetchAlternatives(pitcherId, exerciseId, date, initData = null) {
  const params = new URLSearchParams({ pitcher_id: pitcherId });
  if (date) params.append('date', date);
  return fetchApi(`/api/exercises/${exerciseId}/alternatives?${params}`, initData);
}

/**
 * Swap an exercise in today's plan.
 */
export async function swapExercise(pitcherId, date, fromExerciseId, toExerciseId, reason, initData = null) {
  return postApi(`/api/pitcher/${pitcherId}/swap-exercise`, {
    date,
    from_exercise_id: fromExerciseId,
    to_exercise_id: toExerciseId,
    reason,
    source: 'inline_swap',
  }, initData);
}

/**
 * Apply coach-suggested mutations to today's plan.
 */
export async function applyMutations(pitcherId, date, mutations, initData = null) {
  return postApi(`/api/pitcher/${pitcherId}/apply-mutations`, {
    date,
    mutations,
    source: 'coach_suggestion',
  }, initData);
}

/**
 * Partial update of pitcher profile fields.
 */
export async function patchProfile(pitcherId, partialData, initData = null) {
  const headers = { 'Content-Type': 'application/json' };
  if (initData) headers['X-Telegram-Init-Data'] = initData;

  const res = await fetch(`${API_BASE}/api/pitcher/${pitcherId}/profile`, {
    method: 'PATCH',
    headers,
    body: JSON.stringify(partialData),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `API ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

/**
 * Fetch 4-week training load + streak for profile chart.
 */
export async function fetchTrainingLoad(pitcherId, initData = null) {
  return fetchApi(`/api/pitcher/${pitcherId}/training-load`, initData);
}
