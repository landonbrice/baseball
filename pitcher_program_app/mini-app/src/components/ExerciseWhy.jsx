export default function ExerciseWhy({ why, expanded, onToggle }) {
  if (!expanded || !why) return null;

  return (
    <div style={{
      background: 'var(--color-cream-bg)',
      borderLeft: '2px solid var(--color-rose-blush)',
      padding: 6,
      fontSize: 11,
      lineHeight: 1.6,
      color: 'var(--color-ink-secondary)',
      borderRadius: '0 4px 4px 0',
      marginTop: 4,
    }}>
      {why}
    </div>
  );
}
