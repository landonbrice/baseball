export default function StreakBadge({ streak = 0, weekDots = [] }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ display: 'flex', gap: 4 }}>
        {Array.from({ length: 7 }).map((_, i) => (
          <div
            key={i}
            style={{
              width: 6, height: 6, borderRadius: '50%',
              background: weekDots[i] ? 'var(--color-flag-green)' : '#ddd8d0',
            }}
          />
        ))}
      </div>
      <span style={{
        fontSize: 10, color: 'rgba(255,255,255,0.5)', whiteSpace: 'nowrap',
      }}>
        🔥 {streak} day streak
      </span>
    </div>
  );
}
