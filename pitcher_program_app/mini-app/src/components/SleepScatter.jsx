/**
 * Sleep vs arm feel scatter plot — Chart.js scatter chart.
 * Points colored by sleep threshold (< 7h = yellow, >= 7h = maroon).
 */

import { useRef, useEffect } from 'react';
import {
  Chart, PointElement, LinearScale, Tooltip, ScatterController,
} from 'chart.js';

Chart.register(PointElement, LinearScale, Tooltip, ScatterController);

const MAROON = '#5c1020';
const YELLOW = '#BA7517';

export default function SleepScatter({ points = [] }) {
  const canvasRef = useRef(null);
  const chartRef = useRef(null);

  useEffect(() => {
    if (!canvasRef.current || points.length < 3) return;

    if (chartRef.current) chartRef.current.destroy();

    chartRef.current = new Chart(canvasRef.current, {
      type: 'scatter',
      data: {
        datasets: [{
          data: points.map(p => ({ x: p.sleep, y: p.arm_feel })),
          backgroundColor: points.map(p => p.sleep < 7 ? 'rgba(186,117,23,0.6)' : 'rgba(92,16,32,0.5)'),
          pointRadius: 6,
          pointBorderWidth: 0,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: { label: ctx => `Sleep ${ctx.parsed.x}h → Arm ${ctx.parsed.y}/10` },
          },
        },
        scales: {
          x: {
            min: 4.5, max: 9.5,
            title: { display: true, text: 'sleep (h)', font: { size: 11 }, color: '#b0a89e' },
            ticks: { font: { size: 11 }, color: '#b0a89e' },
            grid: { color: 'rgba(0,0,0,0.04)' },
            border: { display: false },
          },
          y: {
            min: 0.5, max: 10.5,
            title: { display: true, text: 'arm feel', font: { size: 11 }, color: '#b0a89e' },
            ticks: { stepSize: 1, font: { size: 11 }, color: '#b0a89e' },
            grid: { color: 'rgba(0,0,0,0.04)' },
            border: { display: false },
          },
        },
      },
    });

    return () => { if (chartRef.current) chartRef.current.destroy(); };
  }, [points]);

  if (points.length < 3) return null;

  return (
    <div style={{ position: 'relative', width: '100%', height: 120 }}>
      <canvas ref={canvasRef} />
    </div>
  );
}
