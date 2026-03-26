import { useState } from 'react';

export default function PostThrowFeel({ preThrowFeel, existingValue, onCapture }) {
  const [selected, setSelected] = useState(null);
  const [submitted, setSubmitted] = useState(!!existingValue);

  if (submitted || existingValue) {
    const val = existingValue || selected;
    return (
      <div
        style={{
          background: 'rgba(29, 158, 117, 0.07)',
          border: '1px solid rgba(29, 158, 117, 0.19)',
          borderRadius: 10,
          padding: '10px 14px',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}
      >
        <span style={{ fontSize: 14 }}>{'\u2713'}</span>
        <span style={{ fontSize: 12, color: 'var(--color-flag-green)', fontWeight: 600 }}>
          Post-throw feel logged: {val}/5
        </span>
      </div>
    );
  }

  return (
    <div
      style={{
        background: 'var(--color-white)',
        borderRadius: 12,
        padding: '12px 14px',
        textAlign: 'center',
      }}
    >
      <p style={{ fontSize: 13, color: 'var(--color-ink-primary)', fontWeight: 600, margin: '0 0 4px' }}>
        How does your arm feel after throwing?
      </p>
      {preThrowFeel != null && (
        <p style={{ fontSize: 11, color: 'var(--color-ink-muted)', margin: '0 0 10px' }}>
          Pre-throw: {preThrowFeel}/5
        </p>
      )}
      <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginBottom: 10 }}>
        {[1, 2, 3, 4, 5].map(n => (
          <button
            key={n}
            onClick={() => setSelected(n)}
            style={{
              width: 40,
              height: 40,
              borderRadius: 10,
              border: selected === n ? '2px solid var(--color-maroon)' : '1.5px solid var(--color-cream-border)',
              background: selected === n ? 'rgba(232, 160, 170, 0.2)' : 'var(--color-white)',
              color: selected === n ? 'var(--color-maroon)' : 'var(--color-ink-primary)',
              fontSize: 16,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            {n}
          </button>
        ))}
      </div>
      {selected && (
        <button
          onClick={() => {
            setSubmitted(true);
            onCapture?.(selected);
          }}
          style={{
            background: 'var(--color-maroon)',
            color: 'var(--color-white)',
            border: 'none',
            borderRadius: 8,
            padding: '8px 24px',
            fontSize: 12,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          Log it
        </button>
      )}
    </div>
  );
}
