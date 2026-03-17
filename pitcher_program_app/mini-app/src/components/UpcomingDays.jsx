const INTENT_LABELS = {
  power_development: 'Power',
  strength_development: 'Strength',
  strength_maintenance: 'Pull',
  recovery_flush: 'Recovery',
  activation_maintenance: 'Mobility',
  none: 'Rest',
};

export default function UpcomingDays({ upcoming = [] }) {
  if (!upcoming.length) return null;

  return (
    <div className="bg-bg-secondary rounded-xl p-4">
      <h3 className="text-sm font-semibold text-text-primary mb-3">Coming up</h3>
      <div className="space-y-0">
        {upcoming.map((day, i) => (
          <div key={i} className={`flex justify-between items-center py-2 ${
            i < upcoming.length - 1 ? 'border-b border-bg-tertiary' : ''
          }`}>
            <div className="min-w-0">
              <p className="text-sm font-medium text-text-primary">
                Day {day.rotation_day} · {INTENT_LABELS[day.training_intent] || day.training_intent}
              </p>
              <p className="text-[11px] text-text-secondary truncate">
                {day.exercise_preview || day.label}
              </p>
            </div>
            {day.duration_min && (
              <span className="text-[11px] text-text-muted flex-shrink-0 ml-2">
                {day.duration_min} min
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
