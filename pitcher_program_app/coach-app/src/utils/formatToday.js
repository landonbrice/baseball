/** Returns today's date formatted as "Sat · Apr 18" in Chicago timezone. */
export function formatToday(now = new Date()) {
  return now
    .toLocaleDateString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      timeZone: 'America/Chicago',
    })
    .replace(',', ' ·')
}

/** Stable constant for the current render; callers that want live updates should call formatToday() themselves. */
export const TODAY = formatToday()
