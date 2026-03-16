const DAY_LABELS = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];

function armFeelColor(feel) {
  if (feel >= 4) return 'bg-flag-green';
  if (feel === 3) return 'bg-flag-yellow';
  return 'bg-flag-red';
}

function armFeelBg(feel) {
  if (feel >= 4) return 'bg-[#064e3b]';
  if (feel === 3) return 'bg-[#713f12]';
  return 'bg-[#7f1d1d]';
}

/**
 * 7-day color-coded rotation strip showing arm feel by day.
 * @param {Array} entries - Last 7 daily log entries
 * @param {number} todayRotationDay - Current rotation day (0-6)
 */
export default function WeekStrip({ entries = [], todayRotationDay = 0 }) {
  // Build 7-day view from entries
  const days = [];
  const now = new Date();

  for (let i = 6; i >= 0; i--) {
    const date = new Date(now);
    date.setDate(date.getDate() - i);
    const dateStr = date.toISOString().split('T')[0];
    const entry = entries.find(e => e.date === dateStr);
    const dayOfWeek = date.getDay();
    const isToday = i === 0;

    days.push({
      label: DAY_LABELS[dayOfWeek],
      date: date.getDate(),
      armFeel: entry?.pre_training?.arm_feel,
      hasOuting: !!entry?.outing,
      isToday,
      rotationDay: entry?.rotation_day,
    });
  }

  return (
    <div className="flex justify-between gap-1">
      {days.map((day, i) => (
        <div
          key={i}
          className={`flex flex-col items-center flex-1 py-2 rounded-lg ${
            day.isToday ? 'ring-2 ring-accent-blue' : ''
          } ${day.armFeel != null ? armFeelBg(day.armFeel) : 'bg-bg-secondary'}`}
        >
          <span className="text-[10px] text-text-muted">{day.label}</span>
          <span className={`text-sm font-semibold mt-0.5 ${
            day.armFeel != null ? '' : 'text-text-muted'
          }`}>
            {day.armFeel != null ? day.armFeel : '—'}
          </span>
          <span className="text-[10px] text-text-muted mt-0.5">{day.date}</span>
          {day.hasOuting && (
            <div className="w-1.5 h-1.5 rounded-full bg-accent-blue mt-0.5" />
          )}
        </div>
      ))}
    </div>
  );
}
