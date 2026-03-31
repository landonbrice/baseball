/**
 * Season arm feel + recovery timeline — Chart.js dual-axis line chart.
 *
 * Left Y-axis: arm feel (1-5, maroon line with gradient fill)
 * Right Y-axis: recovery % (0-100, green/red dots)
 * Outing markers: vertical dashed lines with S1/S2 labels
 * Rotation day labels: second row below x-axis dates
 */

import { useRef, useEffect } from 'react';
import {
  Chart, LineElement, PointElement, LinearScale, CategoryScale,
  Filler, Tooltip, LineController,
} from 'chart.js';

Chart.register(LineElement, PointElement, LinearScale, CategoryScale, Filler, Tooltip, LineController);

const MAROON = '#5c1020';
const YELLOW = '#BA7517';
const GREEN = '#28a745';
const RED = '#dc3545';

function formatDate(dateStr) {
  const d = new Date(dateStr + 'T12:00:00');
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// Plugin: vertical dashed lines at outing indices with S1/S2 labels
const outingLinesPlugin = {
  id: 'outingLines',
  afterDraw(chart) {
    const meta = chart.getDatasetMeta(0);
    const ctx = chart.ctx;
    const area = chart.chartArea;
    let outingNum = 0;

    chart.data._outingIndices?.forEach(idx => {
      const pt = meta.data[idx];
      if (!pt) return;
      outingNum++;
      ctx.save();
      ctx.setLineDash([3, 3]);
      ctx.strokeStyle = MAROON;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(pt.x, area.top);
      ctx.lineTo(pt.x, area.bottom);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = MAROON;
      ctx.font = '700 11px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('S' + outingNum, pt.x, area.top - 3);
      ctx.restore();
    });
  },
};

// Plugin: rotation day labels below x-axis
const rotationLabelsPlugin = {
  id: 'rotationLabels',
  afterDraw(chart) {
    const rotDays = chart.data._rotationDays;
    if (!rotDays) return;
    const xScale = chart.scales.x;
    const area = chart.chartArea;
    const ctx = chart.ctx;
    ctx.save();
    ctx.font = '600 11px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillStyle = '#b0a89e';
    for (let i = 0; i < rotDays.length; i++) {
      const x = xScale.getPixelForTick(i);
      if (x !== undefined && rotDays[i] != null) {
        ctx.fillText('D' + rotDays[i], x, area.bottom + 32);
      }
    }
    ctx.restore();
  },
};

export default function SeasonTimeline({ timeline = [], hasWhoop = false }) {
  const canvasRef = useRef(null);
  const chartRef = useRef(null);

  useEffect(() => {
    if (!canvasRef.current || timeline.length < 2) return;
    if (chartRef.current) chartRef.current.destroy();

    const labels = timeline.map(t => formatDate(t.date));
    const armFeelData = timeline.map(t => t.arm_feel);
    const outingIndices = [];
    timeline.forEach((t, i) => { if (t.is_outing) outingIndices.push(i); });
    const rotationDays = timeline.map(t => t.rotation_day);

    const hasRecovery = hasWhoop && timeline.some(t => t.recovery_score != null);
    const recoveryData = hasRecovery
      ? timeline.map(t => t.recovery_score ?? null)
      : [];

    const datasets = [
      // Arm feel — left axis
      {
        label: 'Arm feel',
        data: armFeelData,
        borderColor: MAROON,
        borderWidth: 2.5,
        tension: 0.4,
        pointBackgroundColor: armFeelData.map(v => v <= 3 ? YELLOW : '#1D9E75'),
        pointRadius: armFeelData.map(v => v <= 3 ? 6 : 3.5),
        pointBorderWidth: 0,
        fill: true,
        backgroundColor: (ctx) => {
          const g = ctx.chart.ctx.createLinearGradient(0, 0, 0, 150);
          g.addColorStop(0, 'rgba(92,16,32,0.11)');
          g.addColorStop(1, 'rgba(92,16,32,0.01)');
          return g;
        },
        yAxisID: 'yA',
        order: 1,
        z: 2,
      },
    ];

    if (hasRecovery) {
      datasets.push({
        label: 'Recovery',
        data: recoveryData,
        borderColor: 'rgba(40,167,69,0.75)',
        borderWidth: 1.5,
        tension: 0.4,
        pointBackgroundColor: recoveryData.map(r =>
          r == null ? 'transparent' : r < 67 ? 'rgba(220,53,69,0.8)' : 'rgba(40,167,69,0.8)'
        ),
        pointRadius: recoveryData.map(r => r == null ? 0 : 4),
        pointBorderWidth: recoveryData.map(r => r == null ? 0 : 1),
        pointBorderColor: recoveryData.map(r =>
          r == null ? 'transparent' : r < 67 ? RED : GREEN
        ),
        fill: false,
        yAxisID: 'yR',
        order: 2,
        z: 1,
        spanGaps: true,
      });
    }

    const data = { labels, datasets, _outingIndices: outingIndices, _rotationDays: rotationDays };

    chartRef.current = new Chart(canvasRef.current, {
      type: 'line',
      data,
      plugins: [outingLinesPlugin, rotationLabelsPlugin],
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 18, bottom: 28 } },
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: ctx => {
                if (ctx.dataset.label === 'Arm feel') return 'Arm: ' + ctx.parsed.y + '/5';
                if (ctx.dataset.label === 'Recovery') return 'Recovery: ' + ctx.parsed.y + '%';
                return '';
              },
            },
          },
        },
        scales: {
          yA: {
            min: 1, max: 5, position: 'left',
            ticks: { stepSize: 1, font: { size: 11 }, color: MAROON, callback: v => v + '/5' },
            grid: { color: 'rgba(0,0,0,0.05)' },
            border: { display: false },
          },
          ...(hasRecovery ? {
            yR: {
              min: 0, max: 100, position: 'right',
              ticks: { stepSize: 25, font: { size: 11 }, color: 'rgba(40,167,69,0.6)', callback: v => v + '%' },
              grid: { display: false },
              border: { display: false },
            },
          } : {}),
          x: {
            ticks: { font: { size: 11 }, color: '#b0a89e', maxTicksLimit: 6, maxRotation: 0 },
            grid: { display: false },
            border: { display: false },
          },
        },
      },
    });

    return () => { if (chartRef.current) chartRef.current.destroy(); };
  }, [timeline, hasWhoop]);

  if (timeline.length < 2) return null;

  const hasRecovery = hasWhoop && timeline.some(t => t.recovery_score != null);

  return (
    <div>
      <div style={{ position: 'relative', width: '100%', height: 175 }}>
        <canvas ref={canvasRef} />
      </div>
      <div style={{ display: 'flex', gap: 11, marginTop: 10, flexWrap: 'wrap' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: '#6b5f58' }}>
          <span style={{ width: 18, height: 2.5, background: MAROON, display: 'inline-block', borderRadius: 2 }} />
          Arm feel
        </span>
        {hasRecovery && (
          <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: '#6b5f58' }}>
            <span style={{ display: 'inline-flex', gap: 1 }}>
              <span style={{ width: 5, height: 5, background: GREEN, borderRadius: '50%' }} />
              <span style={{ width: 5, height: 5, background: GREEN, borderRadius: '50%' }} />
            </span>
            Recovery
          </span>
        )}
        {timeline.some(t => t.is_outing) && (
          <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: '#6b5f58' }}>
            <span style={{ width: 1, height: 12, borderLeft: '1.5px dashed #5c1020', display: 'inline-block' }} />
            Outing
          </span>
        )}
      </div>
    </div>
  );
}
