export default function ProgramHero({ program }) {
  if (!program) return null;
  const { name, current_phase, phase_progress } = program;
  const totalWeeks = phase_progress?.total || 1;
  const currentWeek = phase_progress?.week || 1;
  const completionPct = Math.min(currentWeek / totalWeeks, 1);
  const dashLength = 125.7;
  const filled = (completionPct * dashLength).toFixed(1);

  return (
    <div style={{
      margin: '14px 14px 0', borderRadius: 16,
      background: 'linear-gradient(165deg, var(--color-maroon) 0%, var(--color-maroon-mid) 100%)',
      padding: '16px 18px 18px',
      color: '#fff',
      boxShadow: '0 4px 20px rgba(92,16,32,0.18)',
      position: 'relative', overflow: 'hidden',
    }}>
      <div style={{ position: 'absolute', top: -30, right: -30, width: 110, height: 110, borderRadius: 55, background: 'rgba(255,255,255,0.04)' }} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', position: 'relative' }}>
        <div>
          <div style={{ fontSize: 9, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1.4, color: 'var(--color-rose-blush)' }}>
            Active Program · Week {currentWeek}
          </div>
          <div style={{ fontSize: 16, fontWeight: 700, marginTop: 4 }}>{name}</div>
          <div style={{ fontSize: 11, color: 'var(--color-rose-blush)', marginTop: 3 }}>
            {current_phase?.name}
          </div>
        </div>
        <div style={{ width: 48, height: 48, position: 'relative', flexShrink: 0 }}>
          <svg width="48" height="48" viewBox="0 0 48 48">
            <circle cx="24" cy="24" r="20" fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth="4" />
            <circle cx="24" cy="24" r="20" fill="none" stroke="#e8a0aa" strokeWidth="4" strokeLinecap="round"
              strokeDasharray={`${filled} ${dashLength}`}
              transform="rotate(-90 24 24)" />
          </svg>
          <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700, color: '#fff' }}>
            {Math.round(completionPct * 100)}%
          </div>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 3, marginTop: 14 }}>
        {Array.from({ length: totalWeeks }).map((_, i) => (
          <div key={i} style={{
            flex: 1, height: 4, borderRadius: 2,
            background: i < currentWeek - 1
              ? 'var(--color-rose-blush)'
              : i === currentWeek - 1
                ? '#fff'
                : 'rgba(255,255,255,0.18)',
            boxShadow: i === currentWeek - 1 ? '0 0 10px rgba(255,255,255,0.5)' : 'none',
          }} />
        ))}
      </div>
    </div>
  );
}
