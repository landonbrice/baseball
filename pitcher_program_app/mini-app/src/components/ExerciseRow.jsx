/**
 * Single exercise row with interactive checkbox, prescription, and optional video link.
 * @param {object} exercise - Exercise from library (resolved)
 * @param {string} prescribed - Prescription string (e.g. "3x5 @ 275")
 * @param {boolean} completed - Whether this exercise is marked complete
 * @param {function} onToggle - Called when checkbox is tapped (optional)
 */
export default function ExerciseRow({ exercise, prescribed, completed, onToggle }) {
  if (!exercise) return null;

  return (
    <div className="flex items-center gap-3 py-1.5">
      {/* Clickable checkbox (only if onToggle provided) */}
      {onToggle ? (
        <button
          onClick={onToggle}
          className={`w-5 h-5 rounded-md border-[1.5px] flex-shrink-0 flex items-center justify-center transition-colors
            ${completed
              ? 'border-accent-blue bg-accent-blue/10 text-accent-blue'
              : 'border-bg-tertiary'}`}
        >
          {completed && <span className="text-[10px]">✓</span>}
        </button>
      ) : (
        <div className="w-1.5 h-1.5 rounded-full bg-text-muted flex-shrink-0 ml-1.5 mr-1" />
      )}

      {/* Exercise info */}
      <div className="flex-1 min-w-0">
        <p className={`text-sm truncate ${completed ? 'text-text-muted line-through' : 'text-text-primary'}`}>
          {exercise.name || 'Unknown exercise'}
        </p>
        <p className="text-[11px] text-text-muted">
          {prescribed}
          {exercise.muscles_primary?.[0] && ` · ${exercise.muscles_primary[0]}`}
        </p>
      </div>

      {/* Video link */}
      {exercise.youtube_url && (
        <a href={exercise.youtube_url} target="_blank" rel="noopener noreferrer"
           className="text-[11px] text-accent-blue flex-shrink-0">
          ▶
        </a>
      )}
    </div>
  );
}
