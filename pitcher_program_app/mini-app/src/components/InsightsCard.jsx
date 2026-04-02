import TrendInsightChart from './TrendInsightChart';
import LockedState, { FakeInsightRows } from './LockedState';

function categorizeInsight(text) {
  const lower = text.toLowerCase();
  if (lower.includes('declining') || lower.includes('concern') || lower.includes('dip') || lower.includes('below')) return 'concern';
  if (lower.includes('sleep')) return 'sleep';
  if (lower.includes('trending up') || lower.includes('strong') || lower.includes('excellent') || lower.includes('stable') || lower.includes('good range') || lower.includes('compounding')) return 'positive';
  if (lower.includes('trend') || lower.includes('average') || lower.includes('averaging')) return 'trend';
  if (lower.includes('check-in') || lower.includes('logged')) return 'progress';
  return 'default';
}

const CATEGORY_STYLES = {
  concern: { dot: '#ef4444', bg: 'rgba(239,68,68,0.06)' },
  sleep: { dot: 'var(--color-ink-muted)', bg: 'transparent' },
  positive: { dot: '#16a34a', bg: 'rgba(22,163,74,0.06)' },
  trend: { dot: 'var(--color-maroon)', bg: 'transparent' },
  progress: { dot: 'var(--color-maroon)', bg: 'rgba(92,16,32,0.04)' },
  default: { dot: 'var(--color-ink-muted)', bg: 'transparent' },
};

export default function InsightsCard({ observations = [], trendWeeks = [], narrative, narrativeHeadline, narrativeWeek }) {
  const safeObs = Array.isArray(observations) ? observations.filter(o => typeof o === 'string') : [];
  const safeWeeks = Array.isArray(trendWeeks) ? trendWeeks : [];
  const hasChart = safeWeeks.length >= 2;
  const hasObs = safeObs.length > 0;
  const hasNarrative = narrative && typeof narrative === 'string';

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
        display: 'flex', alignItems: 'center', gap: 6,
      }}>
        <span>🧠 Weekly Insight</span>
        {hasChart && (
          <span style={{
            fontSize: 8, fontWeight: 600, color: 'var(--color-ink-muted)',
            textTransform: 'none', letterSpacing: 0,
          }}>
            {safeWeeks.length} week{safeWeeks.length !== 1 ? 's' : ''} of data
          </span>
        )}
      </div>

      {/* LLM Coaching Narrative */}
      {hasNarrative && (
        <div style={{
          background: 'rgba(92,16,32,0.04)',
          borderLeft: '3px solid var(--color-maroon)',
          borderRadius: '0 8px 8px 0',
          padding: '12px 14px',
          marginBottom: 12,
        }}>
          {narrativeHeadline && (
            <div style={{
              fontSize: 12, fontWeight: 700, color: 'var(--color-ink-primary)',
              marginBottom: 4,
            }}>
              {narrativeHeadline}
            </div>
          )}
          <p style={{
            fontSize: 12, color: 'var(--color-ink-secondary)',
            lineHeight: 1.65, margin: 0,
          }}>
            {narrative}
          </p>
          {narrativeWeek && (
            <div style={{
              fontSize: 9, color: 'var(--color-ink-muted)',
              marginTop: 8, textTransform: 'uppercase', letterSpacing: '0.04em',
            }}>
              Week of {narrativeWeek}
            </div>
          )}
        </div>
      )}

      {/* 4-week trend chart */}
      {hasChart && (
        <div style={{ marginBottom: 12 }}>
          <TrendInsightChart weeks={safeWeeks} />
        </div>
      )}

      {/* Text insights */}
      {hasObs ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {safeObs.map((obs, i) => {
            const category = categorizeInsight(obs);
            const styles = CATEGORY_STYLES[category];
            return (
              <div key={i} style={{
                display: 'flex', gap: 8, alignItems: 'flex-start',
                background: styles.bg, borderRadius: 8,
                padding: styles.bg !== 'transparent' ? '8px 10px' : '2px 0',
              }}>
                <div style={{
                  width: 6, height: 6, borderRadius: '50%',
                  background: styles.dot, flexShrink: 0, marginTop: 5,
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
      ) : !hasNarrative && (
        <LockedState
          emoji={'\uD83E\uDDE0'}
          title="Insights unlock after your first week"
          description={"I'll surface arm feel trends, sleep patterns, and coaching observations"}
          current={0}
          total={7}
          unit="days tracked"
          previewContent={<FakeInsightRows />}
        />
      )}
    </div>
  );
}
