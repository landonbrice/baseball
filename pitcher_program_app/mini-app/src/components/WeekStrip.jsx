import { FLAG_COLORS, getArmFeelLevel } from '../constants';

const DAY_LABELS = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];

// Rotation day → short training intent label
const INTENT_LABELS = {
  none: 'Rest',
  recovery_flush: 'Recovery',
  power_development: 'Power',
  strength_maintenance: 'Pull',
  strength_development: 'Strength',
  activation_maintenance: 'Mobility',
};

/**
 * 7-day color-coded rotation strip showing arm feel and training intent.
 * @param {Array} entries - Last 7 daily log entries
 * @param {number} todayRotationDay - Current rotation day (0-6)
 */
export default function WeekStrip({ entries = [], todayRotationDay = 0, onDayClick, selectedDate }) {
  const days = [];
  const now = new Date();

  for (let i = 6; i >= 0; i--) {
    const date = new Date(now);
    date.setDate(date.getDate() - i);
    const dateStr = date.toISOString().split('T')[0];
    const entry = entries.find(e => e.date === dateStr);
    const dayOfWeek = date.getDay();
    const isToday = i === 0;

    // Derive rotation day for future days relative to today
    const rotationDay = entry?.rotation_day ?? (isToday ? todayRotationDay : null);

    days.push({
      label: DAY_LABELS[dayOfWeek],
      date: date.getDate(),
      dateStr,
      armFeel: entry?.pre_training?.arm_feel,
      hasOuting: !!entry?.outing,
      hasEntry: !!entry,
      isToday,
      isFuture: !entry && !isToday,
      rotationDay,
      trainingIntent: entry?.plan_generated?.template_day
        ? _intentForDay(rotationDay)
        : (isToday ? _intentForDay(todayRotationDay) : null),
    });
  }

  return (
    <div className="flex justify-between gap-1">
      {days.map((day, i) => {
        const level = day.armFeel != null ? getArmFeelLevel(day.armFeel) : null;
        const bgClass = level ? FLAG_COLORS[level].bg : 'bg-bg-secondary';
        const isSelected = selectedDate && selectedDate === day.dateStr;
        const clickable = day.hasEntry || day.isToday;

        return (
          <button
            key={i}
            disabled={!clickable}
            onClick={() => clickable && onDayClick?.(day.dateStr)}
            className={`flex flex-col items-center flex-1 py-2 rounded-lg transition-colors ${
              isSelected ? 'ring-2 ring-text-primary' : day.isToday ? 'ring-2 ring-accent-blue' : ''
            } ${bgClass} ${day.isFuture ? 'opacity-50' : ''} ${clickable ? 'cursor-pointer' : 'cursor-default'}`}
          >
            <span className="text-[10px] text-text-muted">{day.label}</span>
            <span className={`text-sm font-semibold mt-0.5 ${
              day.armFeel != null ? '' : 'text-text-muted'
            }`}>
              {day.hasOuting ? '🔴' : (day.armFeel != null ? day.armFeel : '—')}
            </span>
            <span className="text-[10px] text-text-muted mt-0.5">{day.date}</span>
            {day.trainingIntent && (
              <span className="text-[8px] text-text-secondary mt-0.5 truncate max-w-full px-0.5">
                {day.trainingIntent}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

// Map rotation day number to intent label
const _DAY_INTENTS = ['none', 'recovery_flush', 'power_development', 'strength_maintenance', 'strength_development', 'activation_maintenance', 'none'];
function _intentForDay(rotationDay) {
  if (rotationDay == null) return null;
  const intent = _DAY_INTENTS[rotationDay % 7];
  return INTENT_LABELS[intent] || null;
}
