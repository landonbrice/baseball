export default function TrendInsightChart({ weeks = [] }) {
  if (weeks.length < 2) return null;

  const svgW = 280;
  const svgH = 140;
  const pad = { top: 16, right: 12, bottom: 28, left: 26 };
  const plotW = svgW - pad.left - pad.right;
  const plotH = svgH - pad.top - pad.bottom;

  const minY = 1;
  const maxY = 10;
  const rangeY = maxY - minY;

  const toX = (i) => pad.left + (i / (weeks.length - 1)) * plotW;
  const toY = (v) => pad.top + (1 - (v - minY) / rangeY) * plotH;

  const avgPoints = weeks.map((w, i) => ({ x: toX(i), y: toY(w.avg) }));
  const avgLine = avgPoints.map(p => `${p.x},${p.y}`).join(' ');

  // High-low band path
  const bandTop = weeks.map((w, i) => `${toX(i)},${toY(w.high)}`).join(' ');
  const bandBot = [...weeks].reverse().map((w, i) => `${toX(weeks.length - 1 - i)},${toY(w.low)}`).join(' ');
  const bandPath = `${bandTop} ${bandBot}`;

  const gridLines = [2, 4, 6, 8, 10];

  return (
    <div style={{
      background: 'var(--color-cream-bg)', borderRadius: 10, padding: 8,
    }}>
      <svg width="100%" viewBox={`0 0 ${svgW} ${svgH}`} style={{ display: 'block' }}>
        {/* Y-axis gridlines and labels */}
        {gridLines.map(v => (
          <g key={v}>
            <line
              x1={pad.left} y1={toY(v)} x2={svgW - pad.right} y2={toY(v)}
              stroke="var(--color-cream-border)" strokeWidth={0.5}
            />
            <text
              x={pad.left - 6} y={toY(v) + 3}
              textAnchor="end" fontSize={8} fill="var(--color-ink-muted)"
            >
              {v}
            </text>
          </g>
        ))}

        {/* High-low range band */}
        <polygon
          points={bandPath}
          fill="var(--color-rose-blush)" opacity={0.25}
        />

        {/* Avg line */}
        <polyline
          points={avgLine}
          fill="none" stroke="var(--color-maroon)" strokeWidth={2}
          strokeLinejoin="round" strokeLinecap="round"
        />

        {/* Data points and value labels */}
        {avgPoints.map((p, i) => (
          <g key={i}>
            <circle cx={p.x} cy={p.y} r={3} fill="var(--color-maroon)" />
            <text
              x={p.x} y={p.y - 7}
              textAnchor="middle" fontSize={8} fontWeight={600}
              fill="var(--color-ink-primary)"
            >
              {weeks[i].avg.toFixed(1)}
            </text>
          </g>
        ))}

        {/* X-axis week labels */}
        {weeks.map((w, i) => (
          <text
            key={i}
            x={toX(i)} y={svgH - 6}
            textAnchor="middle" fontSize={8}
            fill="var(--color-ink-muted)"
          >
            {w.week_label}
          </text>
        ))}
      </svg>
    </div>
  );
}
