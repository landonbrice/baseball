export function checkinStatus(row = {}) {
  if (row.checkin_status) return row.checkin_status
  if (row.today_status) return row.today_status
  if (row.checked_in === true) return 'checked_in'
  return 'not_yet'
}

export function hasCheckedIn(row = {}) {
  return checkinStatus(row) === 'checked_in'
}

export function historyDotStatus(day = {}) {
  const status = checkinStatus(day)
  if (status === 'checked_in') return 'checked_in'
  if (day.status === 'partial') return 'partial'
  return 'none'
}
