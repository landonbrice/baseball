const INSIGHT_ICONS = {
  trend: '📈',
  sleep: '💤',
  concern: '⚠️',
  positive: '💪',
  default: '📋',
};

function categorizeInsight(text) {
  const lower = text.toLowerCase();
  if (lower.includes('sleep')) return 'sleep';
  if (lower.includes('trend') || lower.includes('average') || lower.includes('averaging')) return 'trend';
  if (lower.includes('concern') || lower.includes('dip') || lower.includes('below')) return 'concern';
  if (lower.includes('positive') || lower.includes('stable') || lower.includes('good')) return 'positive';
  return 'default';
}

export default function InsightsCard({ observations = [] }) {
  if (!observations.length) return null;

  return (
    <div className="bg-bg-secondary rounded-xl p-4">
      <h3 className="text-sm font-semibold text-text-primary mb-3">Insights</h3>
      <div className="space-y-2">
        {observations.map((obs, i) => {
          const category = categorizeInsight(obs);
          const icon = INSIGHT_ICONS[category];
          return (
            <div key={i} className="flex gap-2 items-start">
              <span className="text-xs mt-0.5">{icon}</span>
              <p className="text-xs text-text-secondary leading-relaxed">{obs}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
