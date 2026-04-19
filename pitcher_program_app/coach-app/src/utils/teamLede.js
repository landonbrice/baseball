const LOW_COMPLIANCE = 0.75

function lastName(fullName) {
  if (!fullName) return ''
  const parts = fullName.trim().split(/\s+/)
  return parts[parts.length - 1]
}

function injuryBlurb(pitcher) {
  const first = (pitcher.active_injury_flags || [])[0]
  return first ? ` (${first})` : ''
}

function avgAf(roster) {
  const vals = roster.map(p => p.af_7d).filter(v => typeof v === 'number' && !Number.isNaN(v))
  if (vals.length === 0) return null
  return Math.round((vals.reduce((a, b) => a + b, 0) / vals.length) * 10) / 10
}

export function buildTeamLede(roster, compliance) {
  const reds = roster.filter(p => p.flag_level === 'red')
  const yellows = roster.filter(p => p.flag_level === 'yellow')
  const { checked_in_today: checked, total } = compliance || {}
  const pct = total > 0 ? checked / total : 1

  if (reds.length > 0) {
    const names = reds.map(p => `${lastName(p.name)}${injuryBlurb(p)}`).join(' and ')
    const headline = reds.length === 1 ? 'One arm needs close attention today' : `${reds.length} arms need close attention today`
    return {
      priority: 'red',
      text: `${headline}: ${names}.`,
    }
  }

  if (yellows.length > 0) {
    if (yellows.length === 1) {
      return {
        priority: 'yellow',
        text: `${lastName(yellows[0].name)} is flagged yellow today${injuryBlurb(yellows[0])} — worth a check-in.`,
      }
    }
    const names = yellows.map(p => lastName(p.name))
    const joined = names.length === 2
      ? `${names[0]} and ${names[1]}`
      : `${names.slice(0, -1).join(', ')}, and ${names[names.length - 1]}`
    return {
      priority: 'yellow',
      text: `${joined} are all carrying yellow flags — keep an eye on them.`,
    }
  }

  if (pct < LOW_COMPLIANCE) {
    return {
      priority: 'quiet',
      text: `Quiet morning so far — only ${checked}/${total} checked in. Consider a nudge.`,
    }
  }

  const af = avgAf(roster)
  const afLine = af != null ? `, staff averaging ${af.toFixed(1)} arm feel` : ''
  return {
    priority: 'clean',
    text: `A clean morning — ${checked}/${total} in before practice${afLine}. Programming continues as scheduled.`,
  }
}
