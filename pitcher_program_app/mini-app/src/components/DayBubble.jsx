export default function DayBubble({ day }) {
  const { day_label, state, emoji, label, logged, has_game } = day;
  const isToday = state === 'today';
  const isOuting = state === 'outing';
  const isDone = state === 'done';
  const isPast = state === 'done' || state === 'outing';

  const dlabelColor = isToday || isOuting
    ? 'var(--color-maroon)'
    : (has_game ? '#1a2942' : 'var(--color-ink-muted)');

  let bubbleStyle = {
    width: 30, height: 30, borderRadius: '50%',
    background: '#fff', border: '1.5px solid var(--color-cream-border)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: 14, position: 'relative', zIndex: 1,
  };
  if (isDone) Object.assign(bubbleStyle, { background: 'var(--color-flag-green)', borderColor: 'var(--color-flag-green)', color: '#fff', fontSize: 13, fontWeight: 700 });
  if (isOuting) Object.assign(bubbleStyle, { background: '#f5e0e4', borderColor: 'var(--color-rose-blush)', color: 'var(--color-maroon)' });
  if (isToday) Object.assign(bubbleStyle, {
    width: 44, height: 44, background: 'var(--color-maroon)',
    border: '2px solid var(--color-rose-blush)', color: '#fff', fontSize: 18,
    boxShadow: '0 5px 16px rgba(92,16,32,0.35)', marginTop: -7,
  });

  if (has_game) {
    const baseShadow = isToday ? ', 0 5px 16px rgba(92,16,32,0.35)' : '';
    bubbleStyle.boxShadow = `0 0 0 2.5px var(--color-cream-bg), 0 0 0 4px #1a2942${baseShadow}`;
  }

  return (
    <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', position: 'relative', padding: '4px 0' }}>
      <div style={{ fontSize: 9, fontWeight: 700, color: dlabelColor, textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 6 }}>
        {day_label}
      </div>
      <div style={bubbleStyle}>
        {isDone ? '✓' : emoji}
      </div>
      <div style={{
        fontSize: 10, fontWeight: isToday ? 700 : 500,
        color: isToday ? 'var(--color-ink-primary)' : 'var(--color-ink-muted)',
        marginTop: 12, textAlign: 'center', lineHeight: 1.25,
        opacity: isPast ? 0.5 : 1,
      }}>
        {label}
        {logged && (
          <span style={{
            display: 'inline-block', width: 5, height: 5, borderRadius: '50%',
            background: 'var(--color-flag-yellow)', marginLeft: 3,
            verticalAlign: 'middle',
            boxShadow: '0 0 0 2px rgba(186,117,23,0.15)',
          }} />
        )}
      </div>
    </div>
  );
}
