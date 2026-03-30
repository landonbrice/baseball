/**
 * Season arm feel timeline — Chart.js line chart.
 * Shows arm feel (1-5) over the full season with outing markers and flag coloring.
 */

import { useRef, useEffect } from 'react';
import {
  Chart, LineElement, PointElement, LinearScale, CategoryScale,
  Filler, Tooltip, LineController,
} from 'chart.js';

Chart.register(LineElement, PointElement, LinearScale, CategoryScale, Filler, Tooltip, LineController);

const MAROON = '#5c1020';
const YELLOW = '#BA7517';
const GREEN = '#1D9E75';

function formatDate(dateStr) {
  const d = new Date(dateStr + 'T12:00:00');
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export default function SeasonTimeline({ timeline = [] }) {
  const canvasRef = useRef(null);
  const chartRef = useRef(null);

  useEffect(() => {
    if (!canvasRef.current || timeline.length < 2) return;

    if (chartRef.current) chartRef.current.destroy();

    const labels = timeline.map(t => formatDate(t.date));
    const data = timeline.map(t => t.arm_feel);

    chartRef.current = new Chart(canvasRef.current, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          data,
          borderColor: MAROON,
          borderWidth: 2,
          pointBackgroundColor: timeline.map(t => {
            if (t.is_outing) return 'rgba(92,16,32,0.3)';
            if (t.flag_level === 'yellow') return YELLOW;
            if (t.arm_feel >= 4) return GREEN;
            return MAROON;
          }),
          pointRadius: timeline.map(t => t.is_outing ? 6 : 3),
          pointBorderWidth: timeline.map(t => t.is_outing ? 2 : 0),
          pointBorderColor: MAROON,
          tension: 0.35,
          fill: true,
          backgroundColor: (ctx) => {
            const g = ctx.chart.ctx.createLinearGradient(0, 0, 0, 130);
            g.addColorStop(0, 'rgba(92,16,32,0.12)');
            g.addColorStop(1, 'rgba(92,16,32,0.01)');
            return g;
          },
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: { label: ctx => 'Arm feel: ' + ctx.parsed.y + '/5' },
          },
        },
        scales: {
          y: {
            min: 1, max: 5,
            ticks: { stepSize: 1, font: { size: 9 }, color: '#b0a89e' },
            grid: { color: 'rgba(0,0,0,0.04)' },
            border: { display: false },
          },
          x: {
            ticks: { font: { size: 8 }, color: '#b0a89e', maxRotation: 0, autoSkip: true, maxTicksLimit: 6 },
            grid: { display: false },
            border: { display: false },
          },
        },
      },
    });

    return () => { if (chartRef.current) chartRef.current.destroy(); };
  }, [timeline]);

  if (timeline.length < 2) return null;

  return (
    <div>
      <div style={{ position: 'relative', width: '100%', height: 180 }}>
        <canvas ref={canvasRef} />
      </div>
      <div style={{ display: 'flex', gap: 12, marginTop: 8, flexWrap: 'wrap' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 9, color: '#6b5f58' }}>
          <span style={{ width: 20, height: 2, background: MAROON, display: 'inline-block', borderRadius: 1 }} />
          Arm feel
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 9, color: '#6b5f58' }}>
          <span style={{ width: 7, height: 7, background: MAROON, borderRadius: '50%', display: 'inline-block', opacity: 0.3 }} />
          Outing
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 9, color: '#6b5f58' }}>
          <span style={{ width: 7, height: 7, background: YELLOW, borderRadius: 2, display: 'inline-block' }} />
          Yellow flag
        </span>
      </div>
    </div>
  );
}
