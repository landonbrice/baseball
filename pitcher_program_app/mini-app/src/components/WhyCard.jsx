export default function WhyCard({ reasoning, originalDayType, currentDayType }) {
  if (!reasoning) return null;
  return (
    <div
      style={{
        background: 'rgba(232, 160, 170, 0.13)',
        border: '1px solid rgba(232, 160, 170, 0.33)',
        borderRadius: 10,
        padding: '10px 12px',
        display: 'flex',
        gap: 8,
        alignItems: 'flex-start',
      }}
    >
      <span style={{ fontSize: 15, flexShrink: 0 }}>{'\u26A0\uFE0F'}</span>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--color-maroon)', marginBottom: 3, display: 'flex', alignItems: 'center', gap: 6 }}>
          Plan adjusted
          {originalDayType && originalDayType !== currentDayType && (
            <span style={{ fontSize: 9, color: 'var(--color-ink-muted)', fontWeight: 400 }}>
              {originalDayType} {'\u2192'} {currentDayType}
            </span>
          )}
        </div>
        <p style={{ fontSize: 12, color: 'var(--color-ink-secondary)', margin: 0, lineHeight: 1.5 }}>
          {reasoning}
        </p>
      </div>
    </div>
  );
}
