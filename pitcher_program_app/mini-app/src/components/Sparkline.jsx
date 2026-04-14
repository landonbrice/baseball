export default function Sparkline({ data = [], outingIndices = [], width = 80, height = 24 }) {
  if (!data || data.length < 3) return null;

  const pad = 3;
  const minVal = 1;
  const maxVal = 10;
  const range = maxVal - minVal || 1;

  const points = data.map((v, i) => ({
    x: pad + (i / (data.length - 1)) * (width - pad * 2),
    y: pad + (1 - (v - minVal) / range) * (height - pad * 2),
  }));

  const polyline = points.map(p => `${p.x},${p.y}`).join(' ');
  const outingSet = new Set(outingIndices);

  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      <polyline
        points={polyline}
        fill="none"
        stroke="var(--color-rose-blush)"
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      {points.map((p, i) => (
        <circle
          key={i}
          cx={p.x}
          cy={p.y}
          r={outingSet.has(i) ? 2.5 : 1.5}
          fill="var(--color-rose-blush)"
        />
      ))}
    </svg>
  );
}
