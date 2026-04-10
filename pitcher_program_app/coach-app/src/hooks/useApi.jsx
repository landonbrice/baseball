import { useState, useEffect, useCallback } from 'react'
import { fetchCoachApi } from '../api'
import { useCoachAuth } from './useCoachAuth'

export function useCoachApi(path) {
  const { getAccessToken } = useCoachAuth()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    if (!path) return
    setLoading(true)
    setError(null)
    try {
      const result = await fetchCoachApi(path, getAccessToken())
      setData(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [path, getAccessToken])

  useEffect(() => { load() }, [load])

  return { data, loading, error, refetch: load }
}
