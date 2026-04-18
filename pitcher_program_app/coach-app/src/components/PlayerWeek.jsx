import { parseBrief } from '@shared/parseBrief.js'

export default function PlayerWeek({ data }) {
  const week = data?.current_week || []
  const today = new Date().toLocaleDateString('en-CA', { timeZone: 'America/Chicago' })

  if (week.length === 0) return <p className="text-subtle text-sm">No entries this week.</p>

  return (
    <div className="space-y-2">
      {week.map(e => {
        const isToday = e.date === today
        const hasPlan = !!e.plan_generated
        const completedCount = e.completed_exercises ? Object.keys(e.completed_exercises).length : 0

        return (
          <div
            key={e.date}
            className={`rounded-lg p-3 ${isToday ? 'bg-maroon/5 border border-maroon/20' : 'bg-cream'}`}
          >
            <div className="flex items-center justify-between">
              <div>
                <span className={`text-xs font-medium ${isToday ? 'text-maroon' : 'text-charcoal'}`}>
                  {e.date} {isToday ? '(Today)' : ''}
                </span>
                {e.rotation_day != null && (
                  <span className="text-[10px] text-subtle ml-2">Day {e.rotation_day}</span>
                )}
              </div>
              <div className="flex gap-2">
                {hasPlan && (
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-forest/10 text-forest">
                    Plan
                  </span>
                )}
                {completedCount > 0 && (
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-maroon/10 text-maroon">
                    {completedCount} done
                  </span>
                )}
              </div>
            </div>
            {(() => {
              const coachingNote = parseBrief(e.morning_brief).coaching_note;
              if (!coachingNote) return null;
              return <p className="text-[10px] text-subtle mt-1 truncate">{coachingNote}</p>;
            })()}
            {e.active_team_block_id && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-maroon/10 text-maroon mt-1 inline-block">
                Team Block
              </span>
            )}
          </div>
        )
      })}
    </div>
  )
}
