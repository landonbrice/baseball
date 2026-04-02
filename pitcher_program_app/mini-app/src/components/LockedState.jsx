/**
 * LockedState — reusable empty state with progress rings, blurred previews, and CTAs.
 * Used across the app when a section has no data yet to show progression-oriented messaging.
 */

function ProgressRing({ current, total, size = 40 }) {
  const sw = 3;
  const r = (size - sw) / 2;
  const circ = 2 * Math.PI * r;
  const pct = total > 0 ? Math.min(current / total, 1) : 0;
  const offset = circ * (1 - pct);

  return (
    <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="var(--color-cream-border, #e4dfd8)" strokeWidth={sw} />
      {pct > 0 && (
        <circle
          cx={size/2} cy={size/2} r={r} fill="none"
          stroke="#5c1020" strokeWidth={sw}
          strokeDasharray={circ} strokeDashoffset={offset}
          strokeLinecap="round"
        />
      )}
    </svg>
  );
}

export default function LockedState({
  emoji,
  title,
  description,
  current,
  total,
  unit,
  cta,
  onCtaPress,
  previewContent,
}) {
  const hasProgress = typeof current === 'number' && typeof total === 'number';

  return (
    <div style={{ padding: 16, borderRadius: 12, background: 'var(--color-white, #fff)', textAlign: 'center' }}>
      {previewContent ? (
        <div style={{ position: 'relative', marginBottom: 12 }}>
          <div style={{ filter: 'blur(3px)', opacity: 0.35, pointerEvents: 'none' }}>
            {previewContent}
          </div>
          {hasProgress && (
            <div style={{
              position: 'absolute', top: '50%', left: '50%',
              transform: 'translate(-50%, -50%)',
              display: 'flex', flexDirection: 'column', alignItems: 'center',
            }}>
              <ProgressRing current={current} total={total} />
              <span style={{ fontSize: 10, fontWeight: 600, color: '#5c1020', marginTop: 4 }}>
                {current} of {total}
              </span>
            </div>
          )}
        </div>
      ) : (
        <div style={{
          width: 48, height: 48, borderRadius: '50%',
          background: 'rgba(92,16,32,0.08)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 24, margin: '0 auto 12px',
        }}>
          {emoji}
        </div>
      )}

      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-ink-primary, #2a1a18)', marginBottom: 4 }}>
        {title}
      </div>
      <div style={{ fontSize: 11, color: 'var(--color-ink-secondary, #6b5f58)', lineHeight: 1.5, marginBottom: hasProgress ? 12 : cta ? 12 : 0 }}>
        {description}
      </div>

      {hasProgress && (
        <div style={{ marginBottom: cta ? 12 : 0 }}>
          <div style={{
            width: '100%', height: 4, borderRadius: 2,
            background: 'var(--color-cream-border, #e4dfd8)',
          }}>
            <div style={{
              width: `${Math.min((current / total) * 100, 100)}%`,
              height: '100%', borderRadius: 2, background: '#5c1020',
              transition: 'width 0.3s ease',
            }} />
          </div>
          <div style={{ fontSize: 10, color: 'var(--color-ink-muted, #b0a89e)', marginTop: 4 }}>
            {current} of {total} {unit}
          </div>
        </div>
      )}

      {cta && onCtaPress && (
        <button
          onClick={onCtaPress}
          style={{
            background: '#5c1020', color: '#fff', border: 'none',
            borderRadius: 8, padding: '8px 20px',
            fontSize: 12, fontWeight: 600, cursor: 'pointer',
          }}
        >
          {cta}
        </button>
      )}
    </div>
  );
}

export function FakeBarChart() {
  const heights = [60, 70, 80, 50, 90, 70, 80];
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6, height: 60, justifyContent: 'center' }}>
      {heights.map((h, i) => (
        <div key={i} style={{
          width: 20, height: `${h}%`, borderRadius: 3,
          background: 'rgba(92,16,32,0.5)',
        }} />
      ))}
    </div>
  );
}

export function FakeInsightRows() {
  const dots = ['#1D9E75', '#BA7517', '#5c1020'];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '4px 0' }}>
      {dots.map((color, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ width: 6, height: 6, borderRadius: '50%', background: color, flexShrink: 0 }} />
          <div style={{ height: 12, width: '80%', background: 'var(--color-cream-border, #e4dfd8)', borderRadius: 4 }} />
        </div>
      ))}
    </div>
  );
}
