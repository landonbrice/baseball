import { useState, useCallback } from 'react';
import FlagBadge from './FlagBadge';
import ExerciseRow from './ExerciseRow';
import { toggleExercise } from '../api';

/**
 * Resolves an exercise_id (slug or numeric) to a full exercise object.
 */
function resolveExercise(exerciseId, exerciseMap, slugMap) {
  if (exerciseMap[exerciseId]) return exerciseMap[exerciseId];
  const resolvedId = slugMap[exerciseId];
  if (resolvedId && exerciseMap[resolvedId]) return exerciseMap[resolvedId];
  return null;
}

/**
 * Today's training card — plan narrative, grouped exercise blocks, throwing plan.
 * Backward-compatible: renders flat exercises_prescribed if exercise_blocks is absent.
 */
export default function DailyCard({ entry, exerciseMap = {}, slugMap = {}, pitcherId, initData }) {
  if (!entry) {
    return (
      <div className="bg-bg-secondary rounded-xl p-4">
        <p className="text-text-muted text-sm">No training data for today</p>
      </div>
    );
  }

  const { pre_training, plan_generated, plan_narrative } = entry;
  const flagLevel = pre_training?.flag_level || 'green';
  const hasBlocks = plan_generated?.exercise_blocks?.length > 0;

  // Optimistic exercise completion state
  const [completed, setCompleted] = useState(entry.completed_exercises || {});

  const handleToggle = useCallback((exerciseId, newState) => {
    setCompleted(prev => ({ ...prev, [exerciseId]: newState }));
    // Fire-and-forget POST; revert on error
    toggleExercise(pitcherId, entry.date, exerciseId, newState, initData)
      .catch(() => {
        setCompleted(prev => ({ ...prev, [exerciseId]: !newState }));
      });
  }, [pitcherId, entry.date, initData]);

  return (
    <div className="bg-bg-secondary rounded-xl p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-text-primary font-semibold">
            Day {entry.rotation_day ?? '—'} — {plan_generated?.template_day?.replace('day_', 'D') || 'Today'}
          </h3>
          <p className="text-text-muted text-xs mt-0.5">
            Arm feel: {pre_training?.arm_feel ?? '—'}/5 · Sleep: {pre_training?.sleep_hours ?? '—'}h
            {plan_generated?.estimated_duration_min && ` · ~${plan_generated.estimated_duration_min} min`}
          </p>
        </div>
        <FlagBadge level={flagLevel} />
      </div>

      {/* Narrative plan (blue left border) */}
      {plan_narrative && <NarrativeBlock text={plan_narrative} />}

      {/* Exercise blocks (new structured format) */}
      {hasBlocks && plan_generated.exercise_blocks.map((block, i) => (
        <ExerciseBlock
          key={block.block_name || i}
          blockName={block.block_name}
          exercises={block.exercises}
          exerciseMap={exerciseMap}
          slugMap={slugMap}
          completedExercises={completed}
          onToggle={handleToggle}
        />
      ))}

      {/* Backward compat: flat exercises_prescribed */}
      {!hasBlocks && plan_generated?.exercises_prescribed && (
        <div className="border-t border-bg-tertiary pt-2">
          {plan_generated.exercises_prescribed.map((ex, i) => {
            const exercise = resolveExercise(ex.exercise_id, exerciseMap, slugMap);
            return (
              <ExerciseRow
                key={i}
                exercise={exercise || { name: ex.exercise_id }}
                prescribed={ex.prescribed}
              />
            );
          })}
        </div>
      )}

      {/* Throwing plan */}
      {plan_generated?.throwing_plan && (
        <ThrowingBlock plan={plan_generated.throwing_plan} />
      )}

      {/* Outing data (if this day had one) */}
      {entry.outing && (
        <div className="bg-bg-tertiary rounded-lg p-3 mt-2">
          <p className="text-xs text-accent-blue font-medium">Outing</p>
          <p className="text-sm text-text-primary">
            {entry.outing.pitch_count} pitches · Post arm feel: {entry.outing.post_arm_feel}/5
          </p>
          {entry.outing.notes && (
            <p className="text-xs text-text-muted mt-1">{entry.outing.notes}</p>
          )}
        </div>
      )}
    </div>
  );
}


function NarrativeBlock({ text }) {
  return (
    <div className="bg-bg-primary rounded-lg p-3 border-l-[3px] border-accent-blue">
      <p className="text-xs text-text-secondary font-medium mb-1">Today's plan</p>
      <p className="text-sm text-text-primary leading-relaxed whitespace-pre-line">{text}</p>
    </div>
  );
}


function ExerciseBlock({ blockName, exercises, exerciseMap, slugMap, completedExercises, onToggle }) {
  return (
    <div className="mb-1">
      <p className="text-[11px] font-medium text-text-secondary uppercase tracking-wider mb-2">
        {blockName}
      </p>
      {exercises.map((ex, i) => {
        const exercise = resolveExercise(ex.exercise_id || ex.slug, exerciseMap, slugMap);
        const isCompleted = completedExercises[ex.exercise_id] === true;
        return (
          <ExerciseRow
            key={i}
            exercise={exercise || { name: ex.exercise_id }}
            prescribed={ex.prescribed}
            completed={isCompleted}
            onToggle={() => onToggle(ex.exercise_id, !isCompleted)}
          />
        );
      })}
    </div>
  );
}


function ThrowingBlock({ plan }) {
  return (
    <div className="mb-1">
      <p className="text-[11px] font-medium text-text-secondary uppercase tracking-wider mb-2">
        Throwing
      </p>
      <div className="bg-bg-primary rounded-lg p-3">
        <p className="text-sm text-text-primary">{plan.type} — {plan.details}</p>
      </div>
    </div>
  );
}
