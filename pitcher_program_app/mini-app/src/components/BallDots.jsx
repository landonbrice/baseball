const BALL_COLORS = {
  pink: '#e88ca0',
  green: '#4caf7a',
  blue: '#4a90d9',
  red: '#c94444',
};

const BALL_WEIGHTS = [
  { color: 'pink', label: '100g', hex: BALL_COLORS.pink },
  { color: 'green', label: '150g', hex: BALL_COLORS.green },
  { color: 'blue', label: '225g', hex: BALL_COLORS.blue },
  { color: 'red', label: '350g', hex: BALL_COLORS.red },
];

function parseBallColors(weight) {
  if (!weight) return [];
  return weight.split('/').map(c => c.trim().toLowerCase());
}

export function BallDots({ weight }) {
  const colors = parseBallColors(weight);
  if (colors.length === 0) return null;
  return (
    <span style={{ display: 'inline-flex', gap: 2, marginLeft: 4, verticalAlign: 'middle' }}>
      {colors.map((c, i) => (
        <span
          key={i}
          style={{
            width: 7,
            height: 7,
            borderRadius: '50%',
            background: BALL_COLORS[c] || 'var(--color-ink-faint)',
            display: 'inline-block',
            boxShadow: '0 0 0 0.5px var(--color-cream-border)',
          }}
        />
      ))}
    </span>
  );
}

export function BallColorLegend() {
  return (
    <div style={{ display: 'flex', gap: 12, padding: '6px 14px', justifyContent: 'center' }}>
      {BALL_WEIGHTS.map(b => (
        <div key={b.color} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: b.hex,
              display: 'inline-block',
            }}
          />
          <span style={{ fontSize: 9, color: 'var(--color-ink-muted)' }}>{b.label}</span>
        </div>
      ))}
    </div>
  );
}
