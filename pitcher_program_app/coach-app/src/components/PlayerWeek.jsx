import Lede from './shell/Lede'
import { parseBrief } from '@shared/parseBrief.js'

const FLAG_DOT = {
  red: 'bg-crimson',
  yellow: 'bg-amber',
  green: 'bg-forest',
}

function dayAbbrev(iso) {
  if (!iso) return ''
  const d = new Date(iso + 'T12:00:00')
  return d.toLocaleDateString('en-US', { weekday: 'short', timeZone: 'America/Chicago' })
}

function completionRatio(entry) {
  const done = entry?.completed_exercises ? Object.keys(entry.completed_exercises).length : 0
  const planLift = entry?.lifting?.exercises?.length || entry?.plan_generated?.lifting?.exercises?.length || 0
  if (planLift === 0) return done > 0 ? 1 : 0
  return Math.min(1, done / planLift)
}

export default function PlayerWeek({ data }) {
  const week = data?.current_week || []
  const today = new Date().toLocaleDateString('en-CA', { timeZone: 'America/Chicago' })
  const model = data?.training_model || {}
  const weeklySummary = model?.current_week_state?.summary
    || data?.weekly_summary?.narrative
    || parseBrief(week.find(e => e.date === today)?.morning_brief).coaching_note
    || null

  if (week.length === 0) {
    return <p className="font-ui text-meta text-muted">No entries this week.</p>
  }

  return (
    <div className="space-y-5">
      <section>
        <h3 className="font-ui font-semibold uppercase text-[10px] tracking-[0.2em] text-maroon mb-2">
          This Week
        </h3>
        <div className="grid grid-cols-7 gap-1.5">
          {week.slice(0, 7).map(e => {
            const isToday = e.date === today
            const ratio = completionRatio(e)
            const flag = e.pre_training?.flag_level || (ratio > 0 ? 'green' : null)
            return (
              <div
                key={e.date}
                className={`h-20 w-full rounded-[3px] border px-1.5 py-1.5 flex flex-col justify-between ${
                  isToday ? 'border-maroon bg-hover' : 'border-cream-dark bg-bone'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-ui uppercase text-[9px] tracking-[0.1em] text-muted">
                    {dayAbbrev(e.date)}
                  </span>
                  {flag && <span className={`w-1.5 h-1.5 rounded-full ${FLAG_DOT[flag] || 'bg-cream-dark'}`} />}
                </div>
                <div className="font-ui text-meta text-graphite leading-tight">
                  {e.plan_generated?.day_focus || '—'}
                </div>
                <div
                  className="h-1 rounded-full bg-cream-dark overflow-hidden"
                  aria-label={`Completion ${Math.round(ratio * 100)}%`}
                >
                  <div
                    className="h-full bg-forest"
                    style={{ width: `${Math.round(ratio * 100)}%` }}
                  />
                </div>
              </div>
            )
          })}
        </div>
      </section>

      {weeklySummary && (
        <section>
          <h3 className="font-ui font-semibold uppercase text-[10px] tracking-[0.2em] text-maroon mb-2">
            Weekly Arc
          </h3>
          <Lede>{weeklySummary}</Lede>
        </section>
      )}
    </div>
  )
}
