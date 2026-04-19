import { describe, it, expect } from 'vitest'
import { buildTeamLede } from '../teamLede'

const p = (name, flag_level, af_7d = null, active_injury_flags = []) => ({
  pitcher_id: name.toLowerCase(),
  name,
  flag_level,
  af_7d,
  active_injury_flags,
})

describe('buildTeamLede', () => {
  it('RED branch: highlights the red-flagged pitcher with injury context', () => {
    const roster = [
      p('Heron', 'red', 5.2, ['ulnar nerve (red)']),
      p('Alpha', 'green', 7.2),
    ]
    const compliance = { checked_in_today: 2, total: 2, flags: { red: 1, yellow: 0, green: 1 } }
    const out = buildTeamLede(roster, compliance)
    expect(out.priority).toBe('red')
    expect(out.text).toMatch(/Heron/)
    expect(out.text).toMatch(/close attention/i)
  })

  it('YELLOW branch: names all yellow-flagged pitchers', () => {
    const roster = [
      p('Wilson', 'yellow', 6.1, ['ulnar nerve']),
      p('Sosna', 'yellow', 6.3, ['oblique']),
      p('Alpha', 'green', 7.5),
    ]
    const compliance = { checked_in_today: 3, total: 3, flags: { red: 0, yellow: 2, green: 1 } }
    const out = buildTeamLede(roster, compliance)
    expect(out.priority).toBe('yellow')
    expect(out.text).toMatch(/Wilson/)
    expect(out.text).toMatch(/Sosna/)
  })

  it('ALL-GREEN high-compliance branch: clean morning', () => {
    const roster = [p('Alpha', 'green', 7.4), p('Beta', 'green', 7.8)]
    const compliance = { checked_in_today: 2, total: 2, flags: { red: 0, yellow: 0, green: 2 } }
    const out = buildTeamLede(roster, compliance)
    expect(out.priority).toBe('clean')
    expect(out.text).toMatch(/2\/2/)
    expect(out.text).toMatch(/7\.6/)
  })

  it('ALL-GREEN low-compliance branch (<75%): quiet-morning nudge', () => {
    const roster = [
      p('Alpha', 'green'), p('Beta', 'green'), p('Gamma', 'green'), p('Delta', 'green'),
    ]
    const compliance = { checked_in_today: 1, total: 4, flags: { red: 0, yellow: 0, green: 4 } }
    const out = buildTeamLede(roster, compliance)
    expect(out.priority).toBe('quiet')
    expect(out.text).toMatch(/1\/4/)
    expect(out.text).toMatch(/nudge/i)
  })

  it('MIXED: red takes priority even if yellows present', () => {
    const roster = [
      p('Heron', 'red', 5.0),
      p('Wilson', 'yellow', 6.0),
    ]
    const compliance = { checked_in_today: 2, total: 2, flags: { red: 1, yellow: 1, green: 0 } }
    const out = buildTeamLede(roster, compliance)
    expect(out.priority).toBe('red')
    expect(out.text).toMatch(/Heron/)
  })

  it('SINGLE pitcher edge case still renders cleanly', () => {
    const roster = [p('Solo', 'green', 7.0)]
    const compliance = { checked_in_today: 1, total: 1, flags: { red: 0, yellow: 0, green: 1 } }
    const out = buildTeamLede(roster, compliance)
    expect(out.priority).toBe('clean')
    expect(out.text).toMatch(/1\/1/)
  })
})
