/**
 * Phase 1 trajectory-aware triage persists three 0-10 category scores on
 * `daily_entries.pre_training.category_scores`:
 *
 *   { tissue_score, load_score, recovery_score }
 *
 * Pitchers without a baseline silently fall through the legacy flat-trigger
 * path and never get category scores. `null` / missing means "no baseline".
 *
 * The "driving" category is the one with the LOWEST score — that's the
 * category limiting today's readiness. Tie-break order (consistent across
 * surfaces): tissue > load > recovery.
 */

const KEYS = [
  { key: 'tissue_score', label: 'Tissue', short: 'tissue' },
  { key: 'load_score', label: 'Load', short: 'load' },
  { key: 'recovery_score', label: 'Recovery', short: 'recovery' },
]

/**
 * Normalize raw category_scores into an array of {key, label, short, value}
 * entries, or null if no usable scores are present.
 *
 * Accepts numbers, numeric strings, or null/undefined per field. Drops fields
 * whose value isn't a finite number — the row is only "present" if at least
 * one of the three is usable.
 */
export function normalizeCategoryScores(raw) {
  if (!raw || typeof raw !== 'object') return null
  const out = []
  for (const { key, label, short } of KEYS) {
    const v = raw[key]
    const num = typeof v === 'number' ? v : (v == null ? null : Number(v))
    if (num != null && Number.isFinite(num)) {
      out.push({ key, label, short, value: num })
    }
  }
  return out.length > 0 ? out : null
}

/**
 * Given normalized scores, return the driving entry (lowest value).
 * Tie-break order: tissue > load > recovery — matches the KEYS array order.
 */
export function pickDrivingCategory(scores) {
  if (!Array.isArray(scores) || scores.length === 0) return null
  let best = scores[0]
  for (let i = 1; i < scores.length; i++) {
    if (scores[i].value < best.value) {
      best = scores[i]
    }
  }
  return best
}

/**
 * Convenience: from raw category_scores, return the driving category short
 * label + formatted score (one decimal). Returns null if no scores or input
 * unusable.
 *
 *   { short: 'tissue', score: '2.3' }  |  null
 */
export function getDrivingSuffix(raw) {
  const scores = normalizeCategoryScores(raw)
  if (!scores) return null
  const drv = pickDrivingCategory(scores)
  if (!drv) return null
  return { short: drv.short, score: drv.value.toFixed(1) }
}
