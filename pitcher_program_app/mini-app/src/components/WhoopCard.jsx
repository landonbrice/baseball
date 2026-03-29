/**
 * WhoopCard — Biometrics card showing WHOOP recovery, HRV, sleep, strain.
 *
 * Large recovery ring on left, 3 satellite metric rings stacked on right.
 * Only renders when data is available (conditional in Home.jsx).
 */

function Ring({ size, value, max, color, bgColor = '#e8e4de', strokeWidth }) {
  const sw = strokeWidth || (size > 50 ? 7 : 4);
  const r = (size - sw) / 2;
  const circ = 2 * Math.PI * r;
  const pct = value != null && max > 0 ? Math.min(value / max, 1) : 0;
  const offset = circ * (1 - pct);

  return (
    <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={bgColor} strokeWidth={sw} />
      {pct > 0 && (
        <circle
          cx={size/2} cy={size/2} r={r} fill="none"
          stroke={color} strokeWidth={sw}
          strokeDasharray={circ} strokeDashoffset={offset}
          strokeLinecap="round"
        />
      )}
    </svg>
  );
}

function recoveryColor(score) {
  if (score == null) return '#999';
  if (score >= 67) return '#28a745';
  if (score >= 34) return '#e8a317';
  return '#dc3545';
}

export default function WhoopCard({ data, averages }) {
  if (!data) return null;

  const recovery = data.recovery_score;
  const hrv = data.hrv_rmssd;
  const hrv7d = data.hrv_7day_avg || (averages && averages.avg_hrv) || null;
  const sleepPerf = data.sleep_performance;
  const sleepHrs = data.sleep_hours;
  const strain = data.yesterday_strain;
  const avgRecovery = averages?.avg_recovery;
  const avgStrain = averages?.avg_strain;
  const avgSleepHrs = averages?.avg_sleep_hours;

  // HRV delta
  let hrvDelta = null;
  if (hrv != null && hrv7d != null && hrv7d > 0) {
    hrvDelta = Math.round((hrv - hrv7d) / hrv7d * 100);
  }

  return (
    <div style={{
      background: '#fff',
      borderRadius: 12,
      padding: '14px 16px',
      boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
      borderLeft: '4px solid #5c1020',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 14 }}>
        <div style={{ width: 7, height: 7, borderRadius: '50%', background: '#28a745' }} />
        <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: 1.2, color: '#666', textTransform: 'uppercase' }}>
          Biometrics · Today
        </span>
      </div>

      {/* Body */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
        {/* Recovery hero ring */}
        <div style={{ textAlign: 'center', flexShrink: 0 }}>
          <div style={{ position: 'relative', width: 80, height: 80 }}>
            <Ring size={80} value={recovery} max={100} color={recoveryColor(recovery)} />
            <div style={{
              position: 'absolute', top: 0, left: 0, width: 80, height: 80,
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            }}>
              <span style={{ fontSize: 22, fontWeight: 800, color: '#2a1a18', lineHeight: 1 }}>
                {recovery != null ? recovery : '–'}
              </span>
              <span style={{ fontSize: 7, fontWeight: 700, letterSpacing: 1, color: '#888', textTransform: 'uppercase', marginTop: 2 }}>
                Recovery
              </span>
            </div>
          </div>
          {avgRecovery != null && (
            <div style={{ fontSize: 10, color: '#999', marginTop: 4 }}>avg {avgRecovery}</div>
          )}
        </div>

        {/* Satellite metrics */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, flex: 1 }}>
          {/* HRV */}
          <MetricRow
            label="HRV"
            value={hrv != null ? Math.round(hrv) : null}
            ringColor="#4285f4"
            ringValue={hrv} ringMax={hrv7d ? hrv7d * 1.5 : 100}
            sub={hrv7d != null ? (
              <>
                <span>7d avg {Math.round(hrv7d)}ms</span>
                {hrvDelta != null && (
                  <span style={{ color: hrvDelta >= 0 ? '#28a745' : '#dc3545', fontWeight: 600, marginLeft: 4 }}>
                    {hrvDelta >= 0 ? '+' : ''}{hrvDelta}%
                  </span>
                )}
              </>
            ) : null}
          />

          {/* Sleep */}
          <MetricRow
            label="Sleep"
            value={sleepPerf}
            ringColor="#9c27b0"
            ringValue={sleepPerf} ringMax={100}
            sub={
              <>
                {sleepHrs != null && <span>{sleepHrs}h actual</span>}
                {sleepHrs != null && avgSleepHrs != null && <span style={{ marginLeft: 4 }}>· avg {avgSleepHrs}h</span>}
              </>
            }
          />

          {/* Strain */}
          <MetricRow
            label="Strain"
            value={strain != null ? strain.toFixed(1) : null}
            ringColor="#e8a317"
            ringValue={strain} ringMax={21}
            sub={
              <>
                <span>yesterday</span>
                {avgStrain != null && <span style={{ marginLeft: 4 }}>· avg {avgStrain}</span>}
              </>
            }
          />
        </div>
      </div>
    </div>
  );
}

function MetricRow({ label, value, ringColor, ringValue, ringMax, sub }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ position: 'relative', width: 36, height: 36, flexShrink: 0 }}>
        <Ring size={36} value={ringValue} max={ringMax} color={ringColor} />
        <div style={{
          position: 'absolute', top: 0, left: 0, width: 36, height: 36,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: '#2a1a18' }}>
            {value != null ? value : '–'}
          </span>
        </div>
      </div>
      <div>
        <div style={{ fontSize: 12, fontWeight: 700, color: '#2a1a18' }}>{label}</div>
        {sub && <div style={{ fontSize: 10, color: '#999' }}>{sub}</div>}
      </div>
    </div>
  );
}
