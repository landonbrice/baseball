import { useEffect } from 'react'
import { useCoachAuth } from './useCoachAuth'

const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '')

/**
 * Resolve an exercise's display name via the coach-app exerciseMap, falling back
 * to any name stamped on the item itself, then to the ID. Fires telemetry on fallback (D9).
 */
export function useExerciseName({ item, component }) {
  const { exerciseMap } = useCoachAuth()
  const ex = item || {}
  const mapHit = exerciseMap[ex.exercise_id] || null
  const name = ex.name || (mapHit && mapHit.name) || null
  // D22: only fire telemetry once the map has loaded — avoids false-positive flood on fresh login
  const mapReady = Object.keys(exerciseMap).length > 0

  useEffect(() => {
    if (!mapReady) return
    if (!name && ex.exercise_id) {
      try {
        fetch(`${API_BASE}/api/telemetry/ui-fallback`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            exercise_id: ex.exercise_id,
            surface: 'coach-app',
            component: component || 'unknown',
          }),
        }).catch(() => {})
      } catch (_e) {}
    }
  }, [mapReady, name, ex.exercise_id, component])

  return name || ex.exercise_id || 'Unknown exercise'
}
