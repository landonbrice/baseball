import { useState, useEffect } from 'react';

/**
 * 3-tier auth resolution:
 * 1. Telegram WebApp initData (production)
 * 2. URL token param (PWA with JWT)
 * 3. VITE_TEST_PITCHER_ID env var (development)
 */
export function useTelegram() {
  const [authState, setAuthState] = useState({
    pitcherId: null,
    initData: null,
    loading: true,
  });

  useEffect(() => {
    // Tier 1: Telegram WebApp
    const tg = window.Telegram?.WebApp;
    if (tg?.initData) {
      tg.ready();
      tg.expand();
      setAuthState({ pitcherId: null, initData: tg.initData, loading: false });
      return;
    }

    // Tier 2: URL token
    const params = new URLSearchParams(window.location.search);
    const token = params.get('token');
    if (token) {
      setAuthState({ pitcherId: null, initData: token, loading: false });
      return;
    }

    // Tier 3: Dev fallback
    const testId = import.meta.env.VITE_TEST_PITCHER_ID;
    if (testId) {
      setAuthState({ pitcherId: testId, initData: null, loading: false });
      return;
    }

    setAuthState({ pitcherId: null, initData: null, loading: false });
  }, []);

  return authState;
}
