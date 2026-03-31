/**
 * WhoopWeekCard — Season tab WHOOP weekly summary.
 * 4 equal ring gauges + HRV sparkline + insight text.
 */

import { useRef, useEffect } from 'react';
import {
  Chart, LineElement, PointElement, LinearScale, CategoryScale,
  Filler, LineController,
} from 'chart.js';

Chart.register(LineElement, PointElement, LinearScale, CategoryScale, Filler, LineController);

const MAROON = '#5c1020';

function Ring({ size, value, max, color }) {
  const sw = 3.5;
  const r = (size - sw) / 2 - 1;
  const circ = 2 * Math.PI * r;
  const pct = value != null && max > 0 ? Math.min(value / max, 1) : 0;
  const offset = circ * (1 - pct);
  return (
    <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#e5e0db" strokeWidth={sw} />
      {pct > 0 && (
        <circle
          cx={size/2} cy={size/2} r={r} fill="none"
          stroke={color} strokeWidth={sw}
          strokeDasharray={circ} strokeDashoffset={offset}
          transform={`rotate(-90 ${size/2} ${size/2})`}
          strokeLinecap="round"
        />
      )}
    </svg>
  );
}

function RingGauge({ value, label, subtitle, subtitleColor, color, max, format }) {
  const display = value != null ? (format ? format(value) : value) : '—';
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ position: 'relative', width: 56, height: 56, margin: '0 auto 4px' }}>
        <Ring size={56} value={value} max={max} color={color} />
        <div style={{
          position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <span style={{ fontSize: value != null && String(display).length > 3 ? 14 : 15, fontWeight: 800, color }}>
            {display}
          </span>
        </div>
      </div>
      <div style={{ fontSize: 11, fontWeight: 600, color: MAROON, textTransform: 'uppercase', letterSpacing: 0.3 }}>
        {label}
      </div>
      {subtitle && (
        <div style={{ fontSize: 11, color: subtitleColor || '#b0a89e', marginTop: 1, fontWeight: subtitleColor ? 700 : 400 }}>
          {subtitle}
        </div>
      )}
    </div>
  );
}

export default function WhoopWeekCard({ data, onAsk }) {
  const canvasRef = useRef(null);
  const chartRef = useRef(null);

  const today = data?.today || {};
  const sparkline = data?.hrv_sparkline || [];
  const labels = data?.hrv_sparkline_labels || [];

  useEffect(() => {
    if (!canvasRef.current || sparkline.length < 2) return;
    if (chartRef.current) chartRef.current.destroy();

    chartRef.current = new Chart(canvasRef.current, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          data: sparkline,
          borderColor: '#4285f4',
          borderWidth: 2,
          tension: 0.4,
          pointRadius: 3,
          pointBackgroundColor: '#4285f4',
          pointBorderWidth: 0,
          fill: true,
          backgroundColor: 'rgba(66,133,244,0.08)',
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
        scales: {
          y: {
            ticks: { font: { size: 11 }, color: '#b0a89e', maxTicksLimit: 3 },
            grid: { color: 'rgba(0,0,0,0.04)' },
            border: { display: false },
          },
          x: {
            ticks: { font: { size: 11 }, color: '#b0a89e' },
            grid: { display: false },
            border: { display: false },
          },
        },
      },
    });

    return () => { if (chartRef.current) chartRef.current.destroy(); };
  }, [sparkline, labels]);

  if (!data) return null;

  const trendPct = data.hrv_trend_pct;
  const hrvSub = trendPct != null
    ? (trendPct >= 0 ? `+${trendPct}%` : `${trendPct}%`)
    : null;
  const hrvSubColor = trendPct != null
    ? (trendPct >= 0 ? '#1D9E75' : '#dc3545')
    : null;

  return (
    <div style={{
      background: '#fff', borderRadius: '0 12px 12px 0', padding: 14,
      margin: '0 12px 10px', borderLeft: '3px solid #5c1020',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <div style={{
          fontSize: 11, fontWeight: 700, color: MAROON,
          letterSpacing: '0.06em', textTransform: 'uppercase',
        }}>
          This week · WHOOP
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#28a745' }} />
          <span style={{ fontSize: 11, color: '#b0a89e' }}>connected</span>
        </div>
      </div>

      {/* 4 Ring gauges */}
      <div style={{ display: 'flex', justifyContent: 'space-around', marginBottom: 14 }}>
        <RingGauge
          value={today.recovery_score}
          label="Recovery"
          subtitle={data.avg_recovery != null ? `avg ${data.avg_recovery}` : null}
          color="#28a745"
          max={100}
        />
        <RingGauge
          value={today.hrv_rmssd != null ? Math.round(today.hrv_rmssd) : null}
          label="HRV"
          subtitle={hrvSub}
          subtitleColor={hrvSubColor}
          color="#4285f4"
          max={today.hrv_rmssd != null ? Math.max(today.hrv_rmssd * 1.3, 100) : 100}
        />
        <RingGauge
          value={today.sleep_performance}
          label="Sleep"
          subtitle={data.avg_sleep_hours != null ? `${data.avg_sleep_hours}h avg` : null}
          color="#9c27b0"
          max={100}
          format={v => v + '%'}
        />
        <RingGauge
          value={today.yesterday_strain}
          label="Strain"
          subtitle="yesterday"
          color="#f59e0b"
          max={21}
          format={v => v?.toFixed(1)}
        />
      </div>

      {/* HRV sparkline */}
      {sparkline.length >= 2 && (
        <>
          <div style={{
            fontSize: 11, color: '#b0a89e', fontWeight: 600,
            textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 5,
          }}>
            HRV this week
          </div>
          <div style={{ position: 'relative', width: '100%', height: 46 }}>
            <canvas ref={canvasRef} />
          </div>
        </>
      )}

      {/* Insight */}
      {data.insight && (
        <div style={{ marginTop: 9, fontSize: 11, color: '#4a2228', lineHeight: 1.55, fontStyle: 'italic' }}>
          {data.insight}
        </div>
      )}

      {/* Ask coach */}
      {data.ask_prompt && onAsk && (
        <div
          onClick={() => onAsk(data.ask_prompt)}
          style={{ marginTop: 9, display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}
        >
          <span style={{ fontSize: 11, color: MAROON, fontWeight: 700 }}>{data.ask_prompt} ↗</span>
          <span />
        </div>
      )}
    </div>
  );
}
