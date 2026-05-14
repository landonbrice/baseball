import { useState, useEffect, useCallback } from 'react';

/**
 * 3-tier auth resolution:
 * 1. Telegram WebApp initData (production)
 * 2. URL token param (PWA with JWT)
 * 3. VITE_TEST_PITCHER_ID env var (development)
 *
 * Also exposes viewportHeight that updates when Telegram keyboard opens/closes.
 */
export function useTelegram() {
  const [authState, setAuthState] = useState({
    pitcherId: null,
    initData: null,
    loading: true,
  });
  const [viewportHeight, setViewportHeight] = useState(window.innerHeight);

  useEffect(() => {
    const tg = window.Telegram?.WebApp;

    // Tier 1: Telegram WebApp
    if (tg?.initData) {
      tg.ready();
      tg.expand();

      // Track viewport changes (keyboard open/close)
      const onViewportChanged = () => {
        const h = tg.viewportStableHeight || tg.viewportHeight || window.innerHeight;
        setViewportHeight(h);
      };
      tg.onEvent('viewportChanged', onViewportChanged);
      // Set initial stable height
      setViewportHeight(tg.viewportStableHeight || tg.viewportHeight || window.innerHeight);

      setAuthState({ pitcherId: null, initData: tg.initData, loading: false });
      return () => tg.offEvent('viewportChanged', onViewportChanged);
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

  // Also listen to window resize as fallback for non-Telegram contexts
  useEffect(() => {
    const onResize = () => {
      const tg = window.Telegram?.WebApp;
      if (!tg?.initData) setViewportHeight(window.innerHeight);
    };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  return { ...authState, viewportHeight };
}

/**
 * Wire the Telegram hardware BackButton to a handler while a surface is open.
 *
 * Calls WebApp.BackButton.show() + onClick(onPress) on mount, hide() +
 * offClick(onPress) on unmount. Safe outside Telegram (vitest jsdom, browser
 * preview, PWA) — guards `window` and `Telegram.WebApp.BackButton`.
 *
 * Note on dep stability: the effect re-runs whenever `onPress` changes
 * identity. Parents passing a non-memoized handler (the common case for
 * `onClose` props) will re-register on every render. That's a small perf
 * cost, not a correctness issue. Wrap with `useCallback` at the call site
 * if you want to eliminate the churn.
 */
export function useBackButton(onPress) {
  useEffect(() => {
    if (typeof window === 'undefined' || !window.Telegram?.WebApp) return;
    const wa = window.Telegram.WebApp;
    if (!wa.BackButton) return;
    wa.BackButton.show();
    wa.BackButton.onClick(onPress);
    return () => {
      try {
        wa.BackButton.offClick(onPress);
      } catch (_) {
        // Telegram SDK may throw if the handler reference isn't the original
        // (e.g. after hot-reload). Hide still needs to run.
      }
      wa.BackButton.hide();
    };
  }, [onPress]);
}
