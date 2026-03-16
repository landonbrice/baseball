/**
 * Single exercise row in a daily plan card.
 * @param {object} exercise - Exercise from library (resolved)
 * @param {string} prescribed - Prescription string (e.g. "3x5 @ 275")
 * @param {string} mode - Prescription mode
 */
export default function ExerciseRow({ exercise, prescribed, mode }) {
  if (!exercise) return null;

  return (
    <div className="flex items-center justify-between py-1.5">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm text-text-primary truncate">{exercise.name}</span>
          {exercise.youtube_url && (
            <a
              href={exercise.youtube_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent-blue text-xs shrink-0"
            >
              video
            </a>
          )}
        </div>
        {prescribed && (
          <span className="text-xs text-text-muted">{prescribed}</span>
        )}
      </div>
      {mode && (
        <span className="text-[10px] text-text-muted bg-bg-tertiary px-1.5 py-0.5 rounded ml-2 shrink-0">
          {mode}
        </span>
      )}
    </div>
  );
}
