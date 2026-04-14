/**
 * Week strip — Mon-Sun with arm-feel-colored status dots, outing markers, and legend.
 * Receives pre-computed `week` array from /week-summary endpoint.
 */
export default function WeekStrip({ week = [], selectedDate, onDayClick }) {
  if (!week.length) return null;

  return (
    <div style={{
      background: 'var(--color-white)',
      borderRadius: 10,
      overflow: 'hidden',
    }}>
      {/* Day chips */}
      <div style={{
        padding: '8px 10px',
        display: 'flex',
        gap: 2,
      }}>
        {week.map(day => (
          <DayChip
            key={day.date}
            day={day}
            isSelected={selectedDate === day.date}
            onClick={day.is_past || day.is_today ? onDayClick : () => {}}
          />
        ))}
      </div>

      {/* Legend */}
      <div style={{
        borderTop: '0.5px solid var(--color-cream-border)',
        padding: '5px 12px',
        display: 'flex',
        gap: 12,
        justifyContent: 'center',
      }}>
        <LegendItem color="var(--color-flag-green)" label="Complete" />
        <LegendItem color="var(--color-flag-yellow)" label="Partial" />
        <LegendItem color="var(--color-cream-subtle)" label="Upcoming" />
        <LegendItem color="var(--color-maroon-mid)" label="Outing" shape="diamond" />
      </div>
    </div>
  );
}

function LegendItem({ color, label, shape = 'circle' }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
      {shape === 'diamond' ? (
        <div style={{ width: 5, height: 5, background: color, transform: 'rotate(45deg)' }} />
      ) : (
        <div style={{ width: 5, height: 5, borderRadius: '50%', background: color }} />
      )}
      <span style={{ fontSize: 8, color: 'var(--color-ink-muted)' }}>{label}</span>
    </div>
  );
}

function DayChip({ day, isSelected, onClick }) {
  const { day_label, day_number, is_today, is_past, flag_level, had_outing, is_upcoming_outing, arm_feel } = day;

  // Arm feel color for the status dot
  const armFeelColor = arm_feel >= 7 ? 'var(--color-flag-green)'
                     : arm_feel >= 5 && arm_feel <= 6 ? 'var(--color-flag-yellow)'
                     : arm_feel >= 1 && arm_feel <= 4 ? 'var(--color-flag-red)'
                     : null;

  // Use arm feel color if available, fall back to flag_level color
  const dotColor = armFeelColor
                || (flag_level === 'green'  ? 'var(--color-flag-green)'
                  : flag_level === 'yellow' ? 'var(--color-flag-yellow)'
                  : flag_level === 'red'    ? 'var(--color-flag-red)'
                  : null);

  const active = is_today || isSelected;

  return (
    <div
      onClick={() => onClick(day.date)}
      style={{
        flex: 1,
        textAlign: 'center',
        padding: '5px 2px',
        borderRadius: 7,
        cursor: is_past || is_today ? 'pointer' : 'default',
        background: active ? 'var(--color-maroon)' : 'transparent',
      }}
    >
      <div style={{
        fontSize: 8,
        color: active ? 'rgba(255,255,255,0.55)'
             : is_past && flag_level ? 'var(--color-ink-muted)'
             : 'var(--color-ink-faint)',
      }}>
        {day_label}
      </div>

      <div style={{
        fontSize: active ? 11 : 10,
        fontWeight: active ? 700 : 400,
        color: active ? '#fff'
             : is_past && flag_level ? 'var(--color-ink-secondary)'
             : 'var(--color-ink-faint)',
        marginTop: 2,
      }}>
        {day_number}
      </div>

      <div style={{ height: 6, display: 'flex', alignItems: 'center', justifyContent: 'center', marginTop: 2 }}>
        {had_outing ? (
          <div style={{
            width: 4, height: 4,
            background: active ? 'var(--color-rose-blush)' : 'var(--color-maroon-mid)',
            transform: 'rotate(45deg)',
          }} />
        ) : is_upcoming_outing ? (
          <div style={{
            width: 4, height: 4,
            border: '1px solid var(--color-rose-blush)',
            borderRadius: '50%',
          }} />
        ) : dotColor ? (
          <div style={{
            width: 4, height: 4, borderRadius: '50%',
            background: active ? '#fff' : dotColor,
          }} />
        ) : null}
      </div>
    </div>
  );
}
