import { useState, useEffect, useCallback } from 'react';
import { fetchApi } from '../api';

/**
 * Generic fetch hook: { data, loading, error, refetch }
 * @param {string|null} path - API path. Pass null to skip.
 * @param {string|null} initData - Auth token
 */
export function useApi(path, initData = null) {
  const [state, setState] = useState({ data: null, loading: !!path, error: null });
  const [refreshKey, setRefreshKey] = useState(0);

  const refetch = useCallback(() => setRefreshKey(k => k + 1), []);

  useEffect(() => {
    if (!path) return;

    let cancelled = false;
    setState(prev => ({ ...prev, loading: true, error: null }));

    fetchApi(path, initData)
      .then(data => { if (!cancelled) setState({ data, loading: false, error: null }); })
      .catch(error => { if (!cancelled) setState({ data: null, loading: false, error }); });

    return () => { cancelled = true; };
  }, [path, initData, refreshKey]);

  return { ...state, refetch };
}
