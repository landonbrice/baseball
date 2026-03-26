/**
 * Hand-rolled SVG line chart for arm feel trend (28-day).
 * No charting library — keeps bundle small for Telegram Mini App.
 */

import { FLAG_COLORS, getArmFeelLevel } from '../constants';

const CHART_W = 320;
const CHART_H = 120;
const PAD_X = 30;
const PAD_Y = 15;
const PLOT_W = CHART_W - PAD_X * 2;
const PLOT_H = CHART_H - PAD_Y * 2;

export default function TrendChart({ entries = [], days = 28 }) {
  // Filter entries with arm feel data, take last N days
  const withFeel = entries
    .filter(e => e.pre_training?.arm_feel != null)
    .slice(-days);

  if (withFeel.length < 2) {
    return (
      <div className="bg-bg-secondary rounded-xl p-4 h-[160px] flex items-center justify-center">
        <p className="text-text-muted text-sm">Not enough data for trend chart</p>
      </div>
    );
  }

  const feels = withFeel.map(e => e.pre_training?.arm_feel ?? 3);
  const minFeel = 1;
  const maxFeel = 5;
  const range = maxFeel - minFeel;
  const avg = feels.reduce((a, b) => a + b, 0) / feels.length;

  // Build points
  const points = feels.map((feel, i) => {
    const x = PAD_X + (i / (feels.length - 1)) * PLOT_W;
    const y = PAD_Y + PLOT_H - ((feel - minFeel) / range) * PLOT_H;
    return { x, y, feel, date: withFeel[i].date };
  });

  const pathD = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
  const strokeColor = FLAG_COLORS[getArmFeelLevel(Math.round(avg))].stroke;

  // Outing markers
  const outingPoints = points.filter((_, i) => withFeel[i].outing);

  return (
    <div className="bg-bg-secondary rounded-xl p-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-text-primary text-sm font-semibold">Arm Feel Trend</h3>
        <span className="text-text-muted text-xs">
          avg {avg.toFixed(1)}/5 · {withFeel.length}d
        </span>
      </div>

      <svg viewBox={`0 0 ${CHART_W} ${CHART_H}`} className="w-full" preserveAspectRatio="xMidYMid meet">
        {/* Y-axis labels */}
        {[1, 2, 3, 4, 5].map(v => {
          const y = PAD_Y + PLOT_H - ((v - minFeel) / range) * PLOT_H;
          return (
            <g key={v}>
              <line x1={PAD_X} y1={y} x2={PAD_X + PLOT_W} y2={y} stroke="#0f3460" strokeWidth="0.5" />
              <text x={PAD_X - 6} y={y + 3} fill="#6c6c7e" fontSize="9" textAnchor="end">{v}</text>
            </g>
          );
        })}

        {/* Trend line */}
        <path d={pathD} fill="none" stroke={strokeColor} strokeWidth="2" strokeLinejoin="round" />

        {/* Data points */}
        {points.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r="3" fill={strokeColor} />
        ))}

        {/* Outing markers */}
        {outingPoints.map((p, i) => (
          <circle key={`o-${i}`} cx={p.x} cy={CHART_H - 6} r="3" fill="#378ADD" />
        ))}
      </svg>

      {outingPoints.length > 0 && (
        <div className="flex items-center gap-1 mt-1">
          <div className="w-2 h-2 rounded-full bg-accent-blue" />
          <span className="text-[10px] text-text-muted">Outing</span>
        </div>
      )}
    </div>
  );
}
