export default function TodayDetailCard({ today }) {
  if (!today) return null;
  return (
    <div style={{
      margin: '16px 14px 14px', background: '#fff',
      borderRadius: 14, border: '1.5px solid var(--color-maroon)',
      padding: '14px 16px 14px',
      boxShadow: '0 4px 16px rgba(92,16,32,0.08)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <div style={{ fontSize: 9, fontWeight: 700, color: 'var(--color-maroon)', textTransform: 'uppercase', letterSpacing: 1.2 }}>
          {today.label}
        </div>
      </div>
      <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--color-ink-primary)', marginTop: 5, letterSpacing: -0.2 }}>
        {today.title}
      </div>
      {today.subtitle && (
        <div style={{ fontSize: 11, color: 'var(--color-ink-secondary)', marginTop: 6, lineHeight: 1.5 }}>
          {today.subtitle}
        </div>
      )}
    </div>
  );
}
