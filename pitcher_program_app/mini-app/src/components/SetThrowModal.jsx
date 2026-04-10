import { useState } from 'react';

const TYPES = [
  { value: 'catch', label: 'Catch' },
  { value: 'long_toss', label: 'Long toss' },
  { value: 'bullpen', label: 'Bullpen' },
  { value: 'side', label: 'Side' },
];

function next4Days() {
  const out = [];
  const today = new Date();
  for (let i = 1; i <= 4; i++) {
    const d = new Date(today);
    d.setDate(today.getDate() + i);
    out.push({
      iso: d.toISOString().slice(0, 10),
      label: d.toLocaleDateString('en-US', { weekday: 'short' }).toUpperCase(),
      n: d.getDate(),
    });
  }
  return out;
}

export default function SetThrowModal({ onClose, onSave }) {
  const [type, setType] = useState('bullpen');
  const [date, setDate] = useState(next4Days()[0].iso);
  const dates = next4Days();

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
        display: 'flex', alignItems: 'flex-end', zIndex: 100,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '100%', background: 'var(--color-cream-bg)',
          borderRadius: '18px 18px 0 0', padding: '20px 18px 24px',
        }}
      >
        <div style={{ fontSize: 9, fontWeight: 700, color: 'var(--color-maroon)', textTransform: 'uppercase', letterSpacing: 1.2 }}>
          Log a throwing session
        </div>
        <div style={{ marginTop: 14 }}>
          <div style={{ fontSize: 9, fontWeight: 700, color: 'var(--color-ink-muted)', textTransform: 'uppercase', letterSpacing: 0.6, marginBottom: 6 }}>
            Type
          </div>
          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
            {TYPES.map((t) => (
              <button
                key={t.value}
                onClick={() => setType(t.value)}
                style={{
                  fontSize: 11, fontWeight: 600,
                  padding: '6px 11px', borderRadius: 14,
                  border: '1px solid var(--color-cream-border)',
                  background: type === t.value ? 'var(--color-maroon)' : '#fff',
                  color: type === t.value ? '#fff' : 'var(--color-ink-secondary)',
                  cursor: 'pointer',
                }}
              >{t.label}</button>
            ))}
          </div>
        </div>
        <div style={{ marginTop: 14 }}>
          <div style={{ fontSize: 9, fontWeight: 700, color: 'var(--color-ink-muted)', textTransform: 'uppercase', letterSpacing: 0.6, marginBottom: 6 }}>
            When
          </div>
          <div style={{ display: 'flex', gap: 5 }}>
            {dates.map((d) => (
              <button
                key={d.iso}
                onClick={() => setDate(d.iso)}
                style={{
                  flex: 1, padding: '8px 4px', borderRadius: 10,
                  border: '1px solid var(--color-cream-border)',
                  background: date === d.iso ? 'var(--color-maroon)' : '#fff',
                  cursor: 'pointer',
                }}
              >
                <span style={{ display: 'block', fontSize: 9, color: date === d.iso ? '#fff' : 'var(--color-ink-muted)' }}>{d.label}</span>
                <span style={{ display: 'block', fontSize: 13, fontWeight: 700, color: date === d.iso ? '#fff' : 'var(--color-ink-primary)', marginTop: 1 }}>{d.n}</span>
              </button>
            ))}
          </div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 18 }}>
          <button onClick={onClose} style={{ fontSize: 12, fontWeight: 600, padding: '8px 16px', borderRadius: 10, border: 'none', background: 'transparent', color: 'var(--color-ink-muted)', cursor: 'pointer' }}>Cancel</button>
          <button onClick={() => onSave({ date, type })} style={{ fontSize: 12, fontWeight: 600, padding: '8px 16px', borderRadius: 10, border: 'none', background: 'var(--color-maroon)', color: '#fff', cursor: 'pointer' }}>Save</button>
        </div>
      </div>
    </div>
  );
}
