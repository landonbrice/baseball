import { describe, it, expect } from 'vitest'
import {
  normalizeCategoryScores,
  pickDrivingCategory,
  getDrivingSuffix,
} from '../categoryScores'

describe('normalizeCategoryScores', () => {
  it('returns array of three entries when all three present', () => {
    const scores = normalizeCategoryScores({
      tissue_score: 2.3,
      load_score: 6.1,
      recovery_score: 5.4,
    })
    expect(scores).not.toBeNull()
    expect(scores.length).toBe(3)
    expect(scores.map(s => s.key)).toEqual(['tissue_score', 'load_score', 'recovery_score'])
  })

  it('returns null when input is null/undefined', () => {
    expect(normalizeCategoryScores(null)).toBeNull()
    expect(normalizeCategoryScores(undefined)).toBeNull()
  })

  it('returns null when all values are non-numeric', () => {
    expect(normalizeCategoryScores({ tissue_score: null, load_score: undefined })).toBeNull()
  })

  it('coerces numeric strings', () => {
    const scores = normalizeCategoryScores({
      tissue_score: '2.5',
      load_score: 7,
      recovery_score: '6.0',
    })
    expect(scores).not.toBeNull()
    expect(scores[0].value).toBe(2.5)
    expect(scores[2].value).toBe(6.0)
  })

  it('drops fields with non-finite values but keeps the rest', () => {
    const scores = normalizeCategoryScores({
      tissue_score: 4.2,
      load_score: 'not a number',
      recovery_score: 7.1,
    })
    expect(scores.length).toBe(2)
    expect(scores.map(s => s.key)).toEqual(['tissue_score', 'recovery_score'])
  })
})

describe('pickDrivingCategory', () => {
  it('picks the lowest score', () => {
    const scores = normalizeCategoryScores({
      tissue_score: 7.2,
      load_score: 2.3,
      recovery_score: 5.4,
    })
    const drv = pickDrivingCategory(scores)
    expect(drv.key).toBe('load_score')
    expect(drv.short).toBe('load')
  })

  it('ties break to tissue > load > recovery', () => {
    const scores = normalizeCategoryScores({
      tissue_score: 3.0,
      load_score: 3.0,
      recovery_score: 3.0,
    })
    const drv = pickDrivingCategory(scores)
    expect(drv.short).toBe('tissue')
  })

  it('returns null for empty/null input', () => {
    expect(pickDrivingCategory(null)).toBeNull()
    expect(pickDrivingCategory([])).toBeNull()
  })
})

describe('getDrivingSuffix', () => {
  it('returns short label + one-decimal score', () => {
    const out = getDrivingSuffix({
      tissue_score: 2.3,
      load_score: 6.1,
      recovery_score: 5.4,
    })
    expect(out).toEqual({ short: 'tissue', score: '2.3' })
  })

  it('formats integer score with one decimal', () => {
    const out = getDrivingSuffix({
      tissue_score: 7,
      load_score: 2,
      recovery_score: 5,
    })
    expect(out).toEqual({ short: 'load', score: '2.0' })
  })

  it('returns null when no scores', () => {
    expect(getDrivingSuffix(null)).toBeNull()
    expect(getDrivingSuffix({})).toBeNull()
  })
})
