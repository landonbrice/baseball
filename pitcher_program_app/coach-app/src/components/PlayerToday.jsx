import { parseBrief } from '@shared/parseBrief.js'
import { useExerciseName } from '../hooks/useExerciseName'

function SectionHeader({ children }) {
  return (
    <h3 className="font-ui font-semibold uppercase text-[10px] tracking-[0.2em] text-maroon mb-1.5">
      {children}
    </h3>
  )
}

function Section({ title, children }) {
  return (
    <section>
      <SectionHeader>{title}</SectionHeader>
      {children}
    </section>
  )
}

function Item({ name, prescription }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1 border-b border-cream-dark/60 last:border-b-0">
      <span className="font-serif text-body text-charcoal">{name}</span>
      <span className="font-ui text-meta text-muted tabular">{prescription || ''}</span>
    </div>
  )
}

function ExerciseItem({ ex }) {
  const name = useExerciseName({ item: ex, component: 'PlayerToday' })
  return <Item name={name} prescription={ex.prescribed || ex.rx || ''} />
}

function ArmAssessmentBlock({ assessment }) {
  if (!assessment) return null
  const redFlags = assessment.red_flags || []
  const areas = assessment.areas || []
  const sensations = assessment.sensations || []
  const contradictions = assessment.contradictions || []
  return (
    <div className="bg-parchment border border-cream-dark rounded-[3px] p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-ui font-semibold uppercase text-[10px] tracking-[0.16em] text-maroon mb-1">
            Arm Assessment
          </p>
          <p className="font-serif text-body text-charcoal">
            {assessment.summary || `Arm ${assessment.arm_feel || '—'}/10`}
          </p>
          {(areas.length > 0 || sensations.length > 0) && (
            <p className="font-ui text-meta text-muted mt-1">
              {[...areas, ...sensations.map(s => s.replace(/_/g, ' '))].join(' · ')}
            </p>
          )}
        </div>
        {assessment.needs_followup && (
          <span className="font-ui text-[9px] font-bold uppercase tracking-[0.12em] text-amber bg-amber/10 px-2 py-1 rounded-[2px]">
            Follow up
          </span>
        )}
      </div>
      {(redFlags.length > 0 || contradictions.length > 0) && (
        <div className="flex flex-wrap gap-1 mt-2">
          {redFlags.map(flag => (
            <span key={flag} className="font-ui text-[9px] uppercase tracking-[0.1em] text-crimson border border-crimson/30 px-1.5 py-0.5 rounded-[2px]">
              {flag.replace(/_/g, ' ')}
            </span>
          ))}
          {contradictions.map(code => (
            <span key={code} className="font-ui text-[9px] uppercase tracking-[0.1em] text-amber border border-amber/30 px-1.5 py-0.5 rounded-[2px]">
              {code.replace(/_/g, ' ')}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function flattenLifting(lifting) {
  if (!lifting) return []
  const top = Array.isArray(lifting.exercises) ? lifting.exercises : []
  if (top.length > 0) return top
  const blocks = Array.isArray(lifting.exercise_blocks) ? lifting.exercise_blocks : []
  return blocks.flatMap(b => (Array.isArray(b.exercises) ? b.exercises : []))
}

export default function PlayerToday({ data, onAdjust, onRestrict }) {
  if (!data) return null

  const today = new Date().toLocaleDateString('en-CA', { timeZone: 'America/Chicago' })
  const week = data.current_week || []
  const todayEntry = week.find(e => e.date === today)

  const coachingNote = parseBrief(todayEntry?.morning_brief).coaching_note

  const warmup = todayEntry?.warmup
  const armCare = todayEntry?.arm_care
  const lifting = todayEntry?.lifting || todayEntry?.plan_generated?.lifting
  const throwing = todayEntry?.throwing || todayEntry?.plan_generated?.throwing_plan
  const liftingItems = flattenLifting(lifting)
  const armAssessment = todayEntry?.pre_training?.arm_assessment

  return (
    <div className="space-y-5">
      {coachingNote && (
        <div className="bg-parchment border-l-[3px] border-maroon py-2.5 pl-3.5 pr-3 rounded-r-[3px] font-serif italic text-body text-graphite">
          {coachingNote}
        </div>
      )}

      <ArmAssessmentBlock assessment={armAssessment} />

      {!todayEntry?.plan_generated && (
        <p className="font-ui text-meta text-muted">No plan generated yet today.</p>
      )}

      {Array.isArray(warmup) && warmup.length > 0 && (
        <Section title="Warmup">
          {warmup.map((w, i) => (
            <Item
              key={i}
              name={typeof w === 'string' ? w : (w.name || '')}
              prescription={typeof w === 'object' ? (w.prescribed || w.rx || '') : ''}
            />
          ))}
        </Section>
      )}

      {armCare && (
        <Section title="Arm Care">
          {Array.isArray(armCare)
            ? armCare.map((a, i) => (
                <Item
                  key={i}
                  name={typeof a === 'string' ? a : (a.name || '')}
                  prescription={typeof a === 'object' ? (a.prescribed || a.rx || '') : ''}
                />
              ))
            : <p className="font-ui text-meta text-muted">{String(armCare)}</p>}
        </Section>
      )}

      {liftingItems.length > 0 && (
        <Section title="Lift">
          {liftingItems.map((ex, i) => <ExerciseItem key={i} ex={ex} />)}
        </Section>
      )}

      {throwing && (
        <Section title="Throw">
          {typeof throwing === 'string'
            ? <p className="font-ui text-body text-graphite">{throwing}</p>
            : <pre className="font-ui text-meta text-muted whitespace-pre-wrap">{JSON.stringify(throwing, null, 2).slice(0, 400)}</pre>}
        </Section>
      )}

      <div className="flex gap-2 pt-3 border-t border-cream-dark">
        <button
          type="button"
          onClick={onAdjust}
          className="flex-1 py-2 font-ui text-body-sm font-semibold text-bone bg-maroon hover:bg-maroon-ink rounded-[3px]"
        >
          Adjust Today
        </button>
        <button
          type="button"
          onClick={onRestrict}
          className="flex-1 py-2 font-ui text-body-sm font-semibold border border-maroon text-maroon hover:bg-hover rounded-[3px]"
        >
          Add Restriction
        </button>
      </div>

      {(data.pending_suggestions || []).length > 0 && (
        <div className="bg-amber/10 border-l-[3px] border-amber rounded-r-[3px] p-3">
          <p className="font-ui font-semibold uppercase text-[10px] tracking-[0.16em] text-amber mb-1">Pending Suggestions</p>
          {data.pending_suggestions.map(s => (
            <p key={s.suggestion_id} className="font-ui text-body-sm text-charcoal mt-0.5">{s.title}</p>
          ))}
        </div>
      )}
    </div>
  )
}
