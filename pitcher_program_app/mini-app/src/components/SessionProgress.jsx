export default function SessionProgress({ doneCount, totalCount }) {
  const pct = totalCount > 0 ? Math.round((doneCount / totalCount) * 100) : 0;
  const complete = pct >= 100;

  return (
    <div style={{
      background: 'var(--color-white)', borderRadius: 12,
      padding: '12px 14px', boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
    }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
        marginBottom: 8,
      }}>
        <div>
          <p style={{
            margin: 0, fontSize: 9, fontWeight: 700, letterSpacing: 0.8,
            textTransform: 'uppercase', color: 'var(--color-ink-muted)',
          }}>
            📝 Session Progress
          </p>
          <p style={{ margin: '2px 0 0', fontSize: 12, color: 'var(--color-ink-secondary)' }}>
            {doneCount}/{totalCount} exercises
          </p>
        </div>
        <span style={{
          fontSize: 14, fontWeight: 700,
          color: complete ? 'var(--color-flag-green)' : 'var(--color-ink-primary)',
        }}>
          {pct}%
        </span>
      </div>

      <div style={{
        height: 6, borderRadius: 3,
        background: 'var(--color-cream-bg)',
        overflow: 'hidden',
      }}>
        <div style={{
          width: `${pct}%`, height: '100%', borderRadius: 3,
          background: complete ? 'var(--color-flag-green)' : 'var(--color-maroon)',
          transition: 'width 0.3s ease, background 0.3s ease',
        }} />
      </div>
    </div>
  );
}
