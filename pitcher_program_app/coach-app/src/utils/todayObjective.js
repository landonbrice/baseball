const REST = { mark: 'Rest', text: 'Off day — light mobility optional' }

const MOD_MARK = {
  rest_day: 'Recovery',
  no_throw: 'Recovery',
  light_lifting: 'Light',
  low_volume: 'Light',
  light_day: 'Light',
}

function markForModification(tag) {
  return MOD_MARK[tag] || 'Modified'
}

const DAY_FOCUS_MARK = {
  bullpen: 'Bullpen',
  lift: 'Lift',
  throw: 'Throw',
  plyocare: 'Plyocare',
  recovery: 'Recovery',
}

export function buildTodayObjective(today) {
  if (!today) return REST

  // F4: prefer rationale_short (forward-only — legacy rows get null).
  if (today.rationale_short) {
    const mark = DAY_FOCUS_MARK[today.day_focus] || 'Today'
    return { mark, text: today.rationale_short }
  }

  const mods = Array.isArray(today.modifications) ? today.modifications : []
  if (mods.length > 0) {
    const first = mods[0]
    const mark = markForModification(first.tag)
    const text = first.reason ? `${first.tag}: ${first.reason}` : first.tag
    return { mark, text }
  }

  switch (today.day_focus) {
    case 'bullpen': {
      const bp = today.bullpen || {}
      const parts = []
      if (bp.pitches != null) parts.push(`${bp.pitches}p`)
      if (bp.intent_pct != null) parts.push(`${bp.intent_pct}%`)
      if (bp.mix) parts.push(bp.mix)
      return { mark: 'Bullpen', text: parts.join(' · ') || 'Bullpen day' }
    }
    case 'lift':
      return {
        mark: 'Lift',
        text: today.lifting_summary || 'Programmed lift (details in slide-over)',
      }
    case 'throw': {
      const tt = today.throwing || {}
      return {
        mark: 'Throw',
        text: tt.target_distance != null ? `Long toss · ${tt.target_distance}ft cap` : 'Throwing day',
      }
    }
    case 'plyocare':
      return { mark: 'Plyocare', text: 'Plyocare circuit' }
    case 'recovery':
      return { mark: 'Recovery', text: 'Mobility + post-throw recovery' }
    default:
      return REST
  }
}
