import { describe, it, expect } from 'vitest'
import { buildTodayObjective } from '../todayObjective'

describe('buildTodayObjective', () => {
  it('returns Rest fallback for null/undefined today', () => {
    expect(buildTodayObjective(null)).toEqual({ mark: 'Rest', text: 'Off day — light mobility optional' })
    expect(buildTodayObjective(undefined)).toEqual({ mark: 'Rest', text: 'Off day — light mobility optional' })
  })

  it('returns Rest fallback when today.day_focus is null and no modifications', () => {
    expect(buildTodayObjective({ day_focus: null, modifications: [] }))
      .toEqual({ mark: 'Rest', text: 'Off day — light mobility optional' })
  })

  it('Modifications override day_focus (severity-sensitive)', () => {
    expect(
      buildTodayObjective({
        day_focus: 'lift',
        modifications: [{ tag: 'rest_day', reason: 'red flag' }],
      })
    ).toEqual({ mark: 'Recovery', text: 'rest_day: red flag' })

    expect(
      buildTodayObjective({
        day_focus: 'lift',
        modifications: [{ tag: 'light_lifting', reason: 'forearm tight' }],
      })
    ).toEqual({ mark: 'Light', text: 'light_lifting: forearm tight' })

    expect(
      buildTodayObjective({
        day_focus: 'lift',
        modifications: [{ tag: 'swap_exercise', reason: 'knee discomfort' }],
      })
    ).toEqual({ mark: 'Modified', text: 'swap_exercise: knee discomfort' })
  })

  it('Bullpen — formats pitches · intent · mix', () => {
    expect(
      buildTodayObjective({
        day_focus: 'bullpen',
        bullpen: { pitches: 35, intent_pct: 80, mix: 'FB/CH/SL' },
      })
    ).toEqual({ mark: 'Bullpen', text: '35p · 80% · FB/CH/SL' })
  })

  it('Bullpen — falls back gracefully when mix absent', () => {
    expect(
      buildTodayObjective({
        day_focus: 'bullpen',
        bullpen: { pitches: 30, intent_pct: 75 },
      })
    ).toEqual({ mark: 'Bullpen', text: '30p · 75%' })
  })

  it('Lift — uses lifting_summary', () => {
    expect(
      buildTodayObjective({
        day_focus: 'lift',
        lifting_summary: 'Upper push — bench, DB row, rotary med-ball',
      })
    ).toEqual({ mark: 'Lift', text: 'Upper push — bench, DB row, rotary med-ball' })
  })

  it('Lift — fallback when lifting_summary empty', () => {
    expect(buildTodayObjective({ day_focus: 'lift', lifting_summary: null }))
      .toEqual({ mark: 'Lift', text: 'Programmed lift (details in slide-over)' })
  })

  it('Throw — long-toss cap string', () => {
    expect(
      buildTodayObjective({
        day_focus: 'throw',
        throwing: { target_distance: 180 },
      })
    ).toEqual({ mark: 'Throw', text: 'Long toss · 180ft cap' })
  })

  it('Plyocare — "Plyocare" mark', () => {
    expect(buildTodayObjective({ day_focus: 'plyocare' }))
      .toEqual({ mark: 'Plyocare', text: 'Plyocare circuit' })
  })

  it('Recovery — "Recovery" mark', () => {
    expect(buildTodayObjective({ day_focus: 'recovery' }))
      .toEqual({ mark: 'Recovery', text: 'Mobility + post-throw recovery' })
  })
})

describe('buildTodayObjective F4 behavior', () => {
  it('prefers rationale_short when present', () => {
    expect(
      buildTodayObjective({
        rationale_short: 'Yellow — arm feel 5.',
        modifications: [{ tag: 'old_tag', reason: 'should not show' }],
        day_focus: 'lift',
      })
    ).toEqual({ mark: 'Lift', text: 'Yellow — arm feel 5.' })
  })

  it('rationale_short pairs mark with day_focus', () => {
    expect(
      buildTodayObjective({
        rationale_short: 'Bullpen — keep tempo light.',
        modifications: [],
        day_focus: 'bullpen',
      })
    ).toEqual({ mark: 'Bullpen', text: 'Bullpen — keep tempo light.' })
  })

  it('rationale_short with unknown day_focus falls back to "Today" mark', () => {
    expect(
      buildTodayObjective({
        rationale_short: 'Off-day check; mobility only.',
        modifications: [],
        day_focus: null,
      })
    ).toEqual({ mark: 'Today', text: 'Off-day check; mobility only.' })
  })

  it('falls back to legacy modifications when rationale_short null', () => {
    const out = buildTodayObjective({
      rationale_short: null,
      modifications: [
        { tag: 'maintain_compounds_reduced', reason: 'tissue' },
        { tag: 'no_high_intent_throw', reason: null },
      ],
      day_focus: 'lift',
    })
    expect(out.text).toMatch(/maintain_compounds_reduced/i)
  })

  it('falls back to day_focus when rationale_short null and no modifications', () => {
    expect(
      buildTodayObjective({
        rationale_short: null,
        modifications: [],
        day_focus: 'lift',
        lifting_summary: 'Upper push',
      })
    ).toEqual({ mark: 'Lift', text: 'Upper push' })
  })

  it('Rest fallback when everything is empty', () => {
    expect(
      buildTodayObjective({ rationale_short: null, modifications: [], day_focus: null })
    ).toEqual(REST_FIXTURE)
  })
})

const REST_FIXTURE = { mark: 'Rest', text: 'Off day — light mobility optional' }
