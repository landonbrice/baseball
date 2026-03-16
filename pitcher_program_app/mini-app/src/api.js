const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

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
