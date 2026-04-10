import { useNavigate } from 'react-router-dom';

export default function ProgramHistoryTimeline({ programs }) {
  const navigate = useNavigate();
  if (!programs || programs.length === 0) return null;

  return (
    <div style={{ padding: '8px 16px 24px' }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--color-ink-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 12 }}>
        Program History
      </div>
      {programs.map((p, i) => {
        const isActive = !p.deactivated_at;
        return (
          <div key={p.id} style={{ display: 'flex', gap: 12 }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: 20, flexShrink: 0 }}>
              <div style={{
                width: isActive ? 12 : 8, height: isActive ? 12 : 8, borderRadius: '50%',
                background: isActive ? 'var(--color-maroon)' : 'var(--color-cream-border)',
                border: isActive ? '2px solid var(--color-rose-blush)' : 'none',
                flexShrink: 0,
              }} />
              {i < programs.length - 1 && (
                <div style={{ width: 1.5, flex: 1, minHeight: 40, background: 'var(--color-cream-border)' }} />
              )}
            </div>
            <div
              onClick={() => navigate(`/programs/${p.id}`)}
              style={{ flex: 1, cursor: 'pointer', paddingBottom: 16 }}
            >
              <div style={{
                padding: '10px 14px', borderRadius: 10,
                background: isActive ? 'rgba(92,16,32,0.04)' : '#fff',
                border: `1px solid ${isActive ? 'rgba(92,16,32,0.2)' : 'var(--color-cream-border)'}`,
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-ink-primary)' }}>{p.name}</div>
                    <div style={{ fontSize: 11, color: 'var(--color-ink-muted)', marginTop: 2 }}>
                      {p.start_date}{p.end_date ? ` — ${p.end_date}` : (isActive ? ' — Present' : '')}
                    </div>
                  </div>
                  {isActive && (
                    <span style={{ fontSize: 9, fontWeight: 700, padding: '2px 8px', borderRadius: 6, background: 'rgba(29,158,117,0.15)', color: 'var(--color-flag-green)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                      Active
                    </span>
                  )}
                </div>
                {p.deactivation_reason && (
                  <div style={{ fontSize: 11, color: 'var(--color-ink-secondary)', marginTop: 4 }}>
                    {p.deactivation_reason}
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
