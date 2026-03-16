import FlagBadge from './FlagBadge';
import ExerciseRow from './ExerciseRow';

/**
 * Resolves an exercise_id (slug or numeric) to a full exercise object.
 */
function resolveExercise(exerciseId, exerciseMap, slugMap) {
  // Direct lookup by numeric ID
  if (exerciseMap[exerciseId]) return exerciseMap[exerciseId];
  // Slug lookup
  const resolvedId = slugMap[exerciseId];
  if (resolvedId && exerciseMap[resolvedId]) return exerciseMap[resolvedId];
  return null;
}

/**
 * Today's training card showing plan + exercises.
 * @param {object} entry - Today's daily log entry
 * @param {object} exerciseMap - Map of exercise ID → exercise object
 * @param {object} slugMap - Map of slug → numeric ID
 */
export default function DailyCard({ entry, exerciseMap = {}, slugMap = {} }) {
  if (!entry) {
    return (
      <div className="bg-bg-secondary rounded-xl p-4">
        <p className="text-text-muted text-sm">No training data for today</p>
      </div>
    );
  }

  const { pre_training, plan_generated } = entry;
  const flagLevel = pre_training?.flag_level || 'green';

  return (
    <div className="bg-bg-secondary rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-text-primary font-semibold">
            Day {entry.rotation_day} — {plan_generated?.template_day?.replace('day_', 'D') || `R${entry.rotation_day}`}
          </h3>
          <p className="text-text-muted text-xs mt-0.5">
            Arm feel: {pre_training?.arm_feel}/5 · Sleep: {pre_training?.sleep_hours}h
          </p>
        </div>
        <FlagBadge level={flagLevel} />
      </div>

      {plan_generated?.exercises_prescribed && (
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
