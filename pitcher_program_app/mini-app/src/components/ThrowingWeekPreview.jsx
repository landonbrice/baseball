const INTENT_COLORS = {
  recovery: 'var(--color-flag-green)',
  build: 'var(--color-flag-yellow)',
  compete: 'var(--color-flag-red)',
};

export default function ThrowingWeekPreview({ days }) {
  if (!days || days.length === 0) return null;

  // Filter to days that have throwing data
  const throwingDays = days.map(day => {
    const t = day.throwing;
    if (!t || typeof t === 'string') {
      // Legacy format or no throwing
      const label = typeof t === 'string' ? t.replace(/_/g, ' ') : 'No throw';
      return { ...day, throwLabel: label, throwsEstimate: 0, intensity: null, intent: 'recovery' };
    }
    return {
      ...day,
      throwLabel: t.day_type_label || t.type?.replace(/_/g, ' ') || 'Unknown',
      throwsEstimate: (t.volume_summary || {}).total_throws_estimate || 0,
      intensity: t.intensity_range || null,
      intent: t.intent || 'recovery',
    };
  });

  return (
    <div style={{ background: 'var(--color-white)', borderRadius: 12, overflow: 'hidden' }}>
      <div style={{ padding: '10px 14px', borderBottom: '0.5px solid var(--color-cream-border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 14 }}>🗓️</span>
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-ink-primary)' }}>Throwing Week</span>
        </div>
      </div>
      <div style={{ padding: '6px 0' }}>
        {throwingDays.map((day, i) => (
          <div
            key={i}
            style={{
              padding: '8px 14px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              borderBottom: i < throwingDays.length - 1 ? '0.5px solid var(--color-cream-border)' : 'none',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-ink-primary)', minWidth: 50 }}>
                Day {day.rotation_day}
              </span>
              <span style={{ fontSize: 12, color: 'var(--color-ink-secondary)' }}>
                {day.throwLabel}
              </span>
              {day.throwsEstimate > 0 && (
                <span style={{ fontSize: 10, color: 'var(--color-ink-faint)' }}>
                  ~{day.throwsEstimate} throws
                </span>
              )}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              {day.intensity && (
                <span style={{
                  fontSize: 9, background: 'var(--color-cream-bg)', color: 'var(--color-ink-muted)',
                  padding: '2px 8px', borderRadius: 10,
                }}>
                  {typeof day.intensity === 'number' ? `${day.intensity}%` : day.intensity}
                </span>
              )}
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  background: INTENT_COLORS[day.intent] || 'var(--color-ink-faint)',
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
