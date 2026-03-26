/**
 * Single exercise row with interactive checkbox, prescription, and optional video link.
 */
export default function ExerciseRow({ exercise, prescribed, completed, onToggle }) {
  if (!exercise) return null;

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10, padding: '6px 4px',
      opacity: completed ? 0.45 : 1,
    }}>
      {onToggle ? (
        <button
          onClick={onToggle}
          style={{
            width: 20, height: 20, borderRadius: '50%', flexShrink: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 9, fontWeight: 600, cursor: 'pointer', border: 'none',
            ...(completed
              ? { background: 'var(--color-flag-green)', color: '#fff' }
              : { background: 'transparent', border: '1.5px solid var(--color-cream-subtle)', color: 'var(--color-ink-muted)' }
            ),
          }}
        >
          {completed ? '✓' : '·'}
        </button>
      ) : (
        <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--color-ink-muted)', flexShrink: 0, marginLeft: 6, marginRight: 2 }} />
      )}

      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{
          fontSize: 13, margin: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          color: completed ? '#888' : 'var(--color-ink-primary)',
          textDecoration: completed ? 'line-through' : 'none',
        }}>
          {exercise.name || 'Unknown exercise'}
        </p>
        <p style={{ fontSize: 11, color: 'var(--color-ink-muted)', margin: 0 }}>
          {prescribed}
          {exercise.muscles_primary?.[0] && ` · ${exercise.muscles_primary[0]}`}
        </p>
      </div>

      {exercise.youtube_url && (
        <a href={exercise.youtube_url} target="_blank" rel="noopener noreferrer"
          style={{ fontSize: 11, color: 'var(--color-maroon)', flexShrink: 0, textDecoration: 'none' }}>
          ▶
        </a>
      )}
    </div>
  );
}
