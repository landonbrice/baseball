import { describe, expect, it } from 'vitest'
import { checkinStatus, hasCheckedIn, historyDotStatus } from '../teamDailyStatus'

describe('teamDailyStatus', () => {
  it('prefers canonical checkin_status over legacy fields', () => {
    const row = { checkin_status: 'checked_in', today_status: 'not_yet', checked_in: false }
    expect(checkinStatus(row)).toBe('checked_in')
    expect(hasCheckedIn(row)).toBe(true)
  })

  it('falls back to legacy coach and staff fields', () => {
    expect(checkinStatus({ today_status: 'checked_in' })).toBe('checked_in')
    expect(checkinStatus({ checked_in: true })).toBe('checked_in')
    expect(checkinStatus({})).toBe('not_yet')
  })

  it('maps history dots from canonical check-in status without losing partial legacy rows', () => {
    expect(historyDotStatus({ checkin_status: 'checked_in', status: 'none' })).toBe('checked_in')
    expect(historyDotStatus({ checkin_status: 'not_yet', status: 'partial' })).toBe('partial')
    expect(historyDotStatus({ checkin_status: 'not_yet', status: 'none' })).toBe('none')
  })
})
