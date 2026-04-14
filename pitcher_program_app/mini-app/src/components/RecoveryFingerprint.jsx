/**
 * RecoveryFingerprint — multi-line Chart.js chart overlaying all starts.
 * Each start is a line from Outing → D+1 → D+2 → D+3 → D+4.
 */

import { useRef, useEffect } from 'react';
import {
  Chart, LineElement, PointElement, LinearScale, CategoryScale,
  Tooltip, LineController,
} from 'chart.js';

Chart.register(LineElement, PointElement, LinearScale, CategoryScale, Tooltip, LineController);

const LINE_STYLES = [
  { borderColor: '#5c1020', borderWidth: 2.5, pointRadius: 5, pointBackgroundColor: '#5c1020', borderDash: [] },
  { borderColor: '#e8a0aa', borderWidth: 2, pointRadius: 4, pointBackgroundColor: '#e8a0aa', borderDash: [] },
  { borderColor: '#b0a89e', borderWidth: 2, pointRadius: 4, pointBackgroundColor: '#b0a89e', borderDash: [4, 3] },
  { borderColor: '#4285f4', borderWidth: 2, pointRadius: 4, pointBackgroundColor: '#4285f4', borderDash: [2, 2] },
  { borderColor: '#BA7517', borderWidth: 2, pointRadius: 4, pointBackgroundColor: '#BA7517', borderDash: [6, 3] },
];

const LABELS = ['Outing', 'D+1', 'D+2', 'D+3', 'D+4'];

export default function RecoveryFingerprint({ outings = [] }) {
  const canvasRef = useRef(null);
  const chartRef = useRef(null);

  // Only outings with at least 1 recovery point
  const validOutings = outings.filter(o => o.recovery && o.recovery.length > 0);

  useEffect(() => {
    if (!canvasRef.current || validOutings.length === 0) return;
    if (chartRef.current) chartRef.current.destroy();

    const datasets = validOutings.map((o, idx) => {
      const style = LINE_STYLES[idx % LINE_STYLES.length];
      // Build data: post_arm_feel as point 0, then D+1 through D+4
      const data = [o.post_arm_feel ?? null];
      for (let d = 0; d < 4; d++) {
        const r = o.recovery[d];
        data.push(r ? r.arm_feel : null);
      }

      const pcLabel = o.pitch_count ? ` (${o.pitch_count}p)` : '';
      return {
        label: `Start ${idx + 1}${pcLabel}`,
        data,
        ...style,
        pointBorderWidth: 0,
        tension: 0.3,
        fill: false,
        spanGaps: true,
      };
    });

    chartRef.current = new Chart(canvasRef.current, {
      type: 'line',
      data: { labels: LABELS, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: ctx => ctx.dataset.label + ': ' + ctx.parsed.y + '/10',
            },
          },
        },
        scales: {
          y: {
            min: 1, max: 10,
            ticks: { stepSize: 2, font: { size: 11 }, color: '#b0a89e', callback: v => v + '/10' },
            grid: { color: 'rgba(0,0,0,0.04)' },
            border: { display: false },
          },
          x: {
            ticks: { font: { size: 11 }, color: '#5c1020', autoSkip: false },
            grid: { display: false },
            border: { display: false },
          },
        },
      },
    });

    return () => { if (chartRef.current) chartRef.current.destroy(); };
  }, [validOutings]);

  if (validOutings.length === 0) return null;

  return (
    <div>
      <div style={{ position: 'relative', width: '100%', height: 155 }}>
        <canvas ref={canvasRef} />
      </div>
      <div style={{ display: 'flex', gap: 12, marginTop: 8, flexWrap: 'wrap' }}>
        {validOutings.map((o, idx) => {
          const style = LINE_STYLES[idx % LINE_STYLES.length];
          const pcLabel = o.pitch_count ? ` (${o.pitch_count} pitches)` : '';
          return (
            <span key={idx} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: '#6b5f58' }}>
              <span style={{
                width: 12, height: 2.5, background: style.borderColor,
                display: 'inline-block', borderRadius: 2,
              }} />
              Start {idx + 1}{pcLabel}
            </span>
          );
        })}
      </div>
    </div>
  );
}
