import { useState } from 'react'
import { parseBrief } from '@shared/parseBrief.js'
import { useExerciseName } from '../hooks/useExerciseName'

export default function PlayerToday({ data, onAdjust, onRestrict }) {
  if (!data) return null

  const today = new Date().toLocaleDateString('en-CA', { timeZone: 'America/Chicago' })
  const week = data.current_week || []
  const todayEntry = week.find(e => e.date === today)
  const model = data.training_model || {}
  const injuries = data.injuries || []

  return (
    <div className="space-y-4">
      {/* Stats row */}
      <div className="grid grid-cols-4 gap-2">
        <StatCard
          label="Flag"
          value={model.flag_level || 'green'}
          color={model.flag_level === 'red' ? '#c0392b' : model.flag_level === 'yellow' ? '#d4a017' : '#2d5a3d'}
        />
        <StatCard label="Days Since Outing" value={model.days_since_outing ?? '-'} />
        <StatCard label="Arm Feel" value={todayEntry?.pre_training?.arm_feel || '-'} />
        <StatCard label="WHOOP" value={data.whoop_today ? `${data.whoop_today.recovery_score}%` : '-'} />
      </div>

      {/* Morning brief */}
      {todayEntry?.morning_brief && (
        <div className="bg-cream rounded-lg p-3">
          <p className="text-xs text-subtle mb-1">Morning Brief</p>
          <p className="text-sm text-charcoal leading-relaxed">
            {parseBrief(todayEntry.morning_brief).coaching_note || (typeof todayEntry.morning_brief === 'string' && !todayEntry.morning_brief.trim().startsWith('{') ? todayEntry.morning_brief : '')}
          </p>
        </div>
      )}

      {/* Active injuries */}
      {injuries.filter(i => i.status === 'active' || i.status === 'monitoring').length > 0 && (
        <div className="bg-crimson/5 border border-crimson/20 rounded-lg p-3">
          <p className="text-xs font-medium text-crimson mb-1">Active Injury Flags</p>
          {injuries
            .filter(i => i.status === 'active' || i.status === 'monitoring')
            .map((inj, i) => (
              <p key={i} className="text-xs text-charcoal">
                {inj.area} — {inj.flag_level} ({inj.status})
              </p>
            ))}
        </div>
      )}

      {/* Team block tag */}
      {data.active_team_block && (
        <div className="bg-maroon/5 border border-maroon/20 rounded-lg p-3">
          <p className="text-xs text-maroon font-medium">
            Team Block: Week {data.active_team_block.week}, Day {data.active_team_block.day}
          </p>
        </div>
      )}

      {/* Plan sections */}
      {todayEntry?.plan_generated ? (
        <div className="space-y-3">
          <PlanSection title="Warmup" data={todayEntry.warmup} />
          <PlanSection title="Arm Care" data={todayEntry.arm_care} />
          <LiftingSection data={todayEntry.lifting || todayEntry.plan_generated} />
          <PlanSection
            title="Throwing"
            data={todayEntry.throwing || todayEntry.plan_generated?.throwing_plan}
          />
        </div>
      ) : (
        <p className="text-subtle text-sm">No plan generated yet today.</p>
      )}

      {/* Override buttons */}
      <div className="flex gap-2 pt-2 border-t border-cream-dark">
        <button
          onClick={onAdjust}
          className="flex-1 py-2 bg-maroon text-white rounded text-xs font-medium hover:bg-maroon-light"
        >
          Adjust Today
        </button>
        <button
          onClick={onRestrict}
          className="flex-1 py-2 border border-maroon text-maroon rounded text-xs font-medium hover:bg-maroon/5"
        >
          Add Restriction
        </button>
      </div>

      {/* Pending suggestions */}
      {(data.pending_suggestions || []).length > 0 && (
        <div className="bg-amber/10 border border-amber/30 rounded-lg p-3">
          <p className="text-xs font-medium text-amber mb-1">Pending Suggestions</p>
          {data.pending_suggestions.map(s => (
            <p key={s.suggestion_id} className="text-sm text-charcoal mt-1">
              {s.title}
            </p>
          ))}
        </div>
      )}
    </div>
  )
}

function StatCard({ label, value, color }) {
  return (
    <div className="bg-cream rounded-lg p-2 text-center">
      <p className="text-[10px] text-subtle">{label}</p>
      <p className="text-sm font-medium" style={{ color: color || '#2c2c2c' }}>
        {value}
      </p>
    </div>
  )
}

function PlanSection({ title, data }) {
  if (!data) return null
  const isObject = typeof data === 'object' && !Array.isArray(data)

  return (
    <div className="bg-cream/50 rounded-lg p-3">
      <p className="text-xs font-medium text-charcoal mb-1">{title}</p>
      {isObject ? (
        <pre className="text-[10px] text-subtle overflow-x-auto whitespace-pre-wrap">
          {JSON.stringify(data, null, 2).slice(0, 500)}
        </pre>
      ) : (
        <p className="text-xs text-subtle">{String(data).slice(0, 200)}</p>
      )}
    </div>
  )
}

function ExerciseNameSpan({ ex }) {
  const name = useExerciseName({ item: ex, component: 'PlayerToday' })
  return <span className="text-charcoal">{name}</span>
}

function LiftingSection({ data }) {
  if (!data) return null
  const exercises = data.exercises || data.exercise_blocks || []
  if (!Array.isArray(exercises) || exercises.length === 0) {
    return <PlanSection title="Lifting" data={data} />
  }

  return (
    <div className="bg-cream/50 rounded-lg p-3">
      <p className="text-xs font-medium text-charcoal mb-2">Lifting</p>
      {exercises.map((block, bi) => {
        const blockExercises = block.exercises || [block]
        return (
          <div key={bi} className="mb-2">
            {block.block_name && (
              <p className="text-[10px] text-subtle font-medium mb-1">{block.block_name}</p>
            )}
            {(Array.isArray(blockExercises) ? blockExercises : []).map((ex, i) => (
              <div key={i} className="flex justify-between text-xs py-0.5">
                <ExerciseNameSpan ex={ex} />
                <span className="text-subtle">{ex.prescribed || ex.rx || ''}</span>
              </div>
            ))}
          </div>
        )
      })}
    </div>
  )
}
