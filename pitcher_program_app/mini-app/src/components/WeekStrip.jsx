/**
 * Week strip — Mon-Sun with status dots and outing markers.
 * Receives pre-computed `week` array from /week-summary endpoint.
 */
export default function WeekStrip({ week = [], selectedDate, onDayClick }) {
  if (!week.length) return null;

  return (
    <div style={{
      background: 'var(--color-white)',
      padding: '8px 10px',
      borderBottom: '0.5px solid var(--color-cream-border)',
      display: 'flex',
      gap: 2,
      borderRadius: 10,
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
  );
}

function DayChip({ day, isSelected, onClick }) {
  const { day_label, day_number, is_today, is_past, flag_level, had_outing, is_upcoming_outing } = day;

  const dotColor = flag_level === 'green'  ? 'var(--color-flag-green)'
                 : flag_level === 'yellow' ? 'var(--color-flag-yellow)'
                 : flag_level === 'red'    ? 'var(--color-flag-red)'
                 : null;

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
      {/* Day letter */}
      <div style={{
        fontSize: 8,
        color: active ? 'rgba(255,255,255,0.55)'
             : is_past && flag_level ? 'var(--color-ink-muted)'
             : 'var(--color-ink-faint)',
      }}>
        {day_label}
      </div>

      {/* Day number */}
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

      {/* Marker row */}
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
          <div style={{ width: 4, height: 4, borderRadius: '50%', background: dotColor }} />
        ) : null}
      </div>
    </div>
  );
}
