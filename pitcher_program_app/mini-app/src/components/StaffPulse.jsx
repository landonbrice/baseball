import { useState } from 'react';

export default function StaffPulse({ data }) {
  const [expanded, setExpanded] = useState(false);

  if (!data) return null;

  const { checked_in_count = 0, total_pitchers = 0, pitchers = [] } = data;

  return (
    <div style={{
      background: 'var(--color-white)', borderRadius: 12,
      boxShadow: '0 1px 3px rgba(0,0,0,0.04)', overflow: 'hidden',
    }}>
      {/* Header */}
      <button
        onClick={() => setExpanded(prev => !prev)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 8,
          padding: '12px 14px', border: 'none', background: 'transparent',
          cursor: 'pointer', textAlign: 'left',
        }}
      >
        <span style={{ fontSize: 14 }}>{'\u26BE'}</span>
        <span style={{
          fontSize: 9, fontWeight: 700, letterSpacing: 0.8,
          textTransform: 'uppercase', color: 'var(--color-ink-muted)',
          flex: 1,
        }}>
          Pitching Staff
        </span>
        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-ink-primary)' }}>
          {checked_in_count}/{total_pitchers}
        </span>
        <span style={{
          fontSize: 10, color: 'var(--color-ink-muted)',
          transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
          transition: 'transform 0.2s ease',
          display: 'inline-block',
        }}>
          {'\u25BC'}
        </span>
      </button>

      {/* Expanded list */}
      {expanded && pitchers.length > 0 && (
        <div style={{ padding: '0 14px 10px' }}>
          {pitchers.map((p, i) => {
            const checkedIn = !!p.checked_in;
            return (
              <div
                key={p.id || i}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: '7px 0',
                  borderTop: i > 0 ? '0.5px solid var(--color-cream-border)' : 'none',
                }}
              >
                <div style={{
                  width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
                  background: checkedIn ? 'var(--color-flag-green)' : '#ddd8d0',
                }} />
                <span style={{
                  flex: 1, fontSize: 12, minWidth: 0,
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  color: checkedIn ? 'var(--color-ink-primary)' : 'var(--color-ink-muted)',
                }}>
                  {p.first_name || p.name}
                </span>
                {(p.role) && (
                  <span style={{
                    fontSize: 9, fontWeight: 600, textTransform: 'uppercase',
                    padding: '1px 6px', borderRadius: 6,
                    background: 'var(--color-cream-bg)', color: 'var(--color-ink-secondary)',
                    flexShrink: 0,
                  }}>
                    {p.role}
                  </span>
                )}
                {(p.rotation_info || p.rotation) && (
                  <span style={{
                    fontSize: 10, color: 'var(--color-ink-muted)', flexShrink: 0,
                  }}>
                    {String(p.rotation_info || p.rotation)}
                  </span>
                )}
                {p.days_since_outing != null && p.days_since_outing < 99 && (
                  <span style={{
                    fontSize: 9, color: 'var(--color-ink-faint)', flexShrink: 0,
                  }}>
                    {p.days_since_outing}d ago
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
