import TrendInsightChart from './TrendInsightChart';

function categorizeInsight(text) {
  const lower = text.toLowerCase();
  if (lower.includes('sleep')) return 'sleep';
  if (lower.includes('trend') || lower.includes('average') || lower.includes('averaging')) return 'trend';
  if (lower.includes('concern') || lower.includes('dip') || lower.includes('below')) return 'concern';
  if (lower.includes('positive') || lower.includes('stable') || lower.includes('good')) return 'positive';
  return 'default';
}

const CATEGORY_COLORS = {
  trend: 'var(--color-maroon)',
  sleep: 'var(--color-ink-muted)',
  concern: 'var(--color-flag-yellow)',
  positive: 'var(--color-flag-green)',
  default: 'var(--color-ink-muted)',
};

export default function InsightsCard({ observations = [], trendWeeks = [] }) {
  // Guard: ensure observations is an array of strings
  const safeObs = Array.isArray(observations) ? observations.filter(o => typeof o === 'string') : [];
  const safeWeeks = Array.isArray(trendWeeks) ? trendWeeks : [];
  if (!safeObs.length && safeWeeks.length < 2) return null;

  return (
    <div style={{
      background: 'var(--color-white)',
      borderRadius: 12,
      padding: 14,
      marginTop: 12,
    }}>
      {/* Section header */}
      <div style={{
        fontSize: 9, fontWeight: 700, color: 'var(--color-maroon)',
        textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10,
      }}>
        Weekly Insight
      </div>

      {/* 4-week trend chart */}
      {safeWeeks.length >= 2 && (
        <div style={{ marginBottom: 12 }}>
          <TrendInsightChart weeks={safeWeeks} />
        </div>
      )}

      {/* Text insights */}
      {safeObs.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {safeObs.map((obs, i) => {
            const category = categorizeInsight(obs);
            const dotColor = CATEGORY_COLORS[category];
            return (
              <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                <div style={{
                  width: 5, height: 5, borderRadius: '50%',
                  background: dotColor, flexShrink: 0, marginTop: 5,
                }} />
                <p style={{
                  fontSize: 11, color: 'var(--color-ink-secondary)',
                  lineHeight: 1.6, margin: 0,
                }}>
                  {obs}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
