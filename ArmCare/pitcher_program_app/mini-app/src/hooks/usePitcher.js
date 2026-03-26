import { useApi } from './useApi';

/**
 * Combines profile + log + progression data for a pitcher.
 * @param {string|null} pitcherId
 * @param {string|null} initData
 * @param {string} suffix - Optional query string suffix for cache-busting
 */
export function usePitcher(pitcherId, initData = null, suffix = '') {
  const profile = useApi(
    pitcherId ? `/api/pitcher/${pitcherId}/profile${suffix}` : null,
    initData
  );
  const log = useApi(
    pitcherId ? `/api/pitcher/${pitcherId}/log${suffix}` : null,
    initData
  );
  const progression = useApi(
    pitcherId ? `/api/pitcher/${pitcherId}/progression${suffix}` : null,
    initData
  );

  const loading = profile.loading || log.loading || progression.loading;
  const error = profile.error || log.error || progression.error;

  return {
    profile: profile.data,
    log: log.data,
    progression: progression.data,
    loading,
    error,
  };
}
