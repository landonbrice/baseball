import { useApi } from './useApi';

/**
 * Combines profile + log + progression data for a pitcher.
 * @param {string|null} pitcherId
 * @param {string|null} initData
 */
export function usePitcher(pitcherId, initData = null) {
  const profile = useApi(
    pitcherId ? `/api/pitcher/${pitcherId}/profile` : null,
    initData
  );
  const log = useApi(
    pitcherId ? `/api/pitcher/${pitcherId}/log` : null,
    initData
  );
  const progression = useApi(
    pitcherId ? `/api/pitcher/${pitcherId}/progression` : null,
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
