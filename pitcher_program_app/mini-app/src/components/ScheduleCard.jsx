function GameItem({ game, isFeatured }) {
  const yourStart = game.is_your_start;
  const isPast = new Date(game.date) < new Date(new Date().toISOString().slice(0, 10));
  const dateLabel = new Date(game.date + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }).toUpperCase();

  let style = {
    flex: 1, minWidth: 0,
    background: 'rgba(255,255,255,0.06)',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: 10, padding: '9px 9px 10px',
    borderTop: '2px solid rgba(255,255,255,0.25)',
  };
  if (isPast) Object.assign(style, { opacity: 0.5, borderTopColor: 'rgba(255,255,255,0.15)' });
  if (isFeatured) Object.assign(style, { background: 'rgba(255,255,255,0.13)', borderColor: 'rgba(255,255,255,0.2)', borderTop: '2px solid #fff' });
  if (yourStart) Object.assign(style, { borderTop: '2px solid var(--color-rose-blush)', background: 'rgba(232,160,170,0.12)', borderColor: 'rgba(232,160,170,0.25)' });

  return (
    <div style={style}>
      <div style={{ fontSize: 9, fontWeight: 700, color: yourStart ? 'var(--color-rose-blush)' : 'rgba(255,255,255,0.55)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
        {dateLabel}
      </div>
      <div style={{ fontSize: 12, fontWeight: 700, color: '#fff', marginTop: 4, lineHeight: 1.2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {!game.home && <span style={{ fontSize: 10, opacity: 0.6 }}>@ </span>}
        {game.opponent}
      </div>
      <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.6)', marginTop: 4, fontWeight: 500 }}>
        {yourStart && <span style={{ fontWeight: 700, color: 'var(--color-rose-blush)', textTransform: 'uppercase', letterSpacing: 0.4, fontSize: 8, background: 'rgba(232,160,170,0.18)', padding: '1px 5px', borderRadius: 4 }}>YOUR START</span>}
        {!yourStart && (game.time || '') + (game.result ? ` · ${game.result}` : '')}
      </div>
    </div>
  );
}

export default function ScheduleCard({ schedule }) {
  if (!schedule || schedule.length === 0) return null;
  const today = new Date().toISOString().slice(0, 10);
  const featuredIdx = schedule.findIndex(g => g.date >= today);
  return (
    <div style={{
      margin: '16px 14px 0', background: '#1a2942',
      borderRadius: 14, padding: '14px 16px 16px',
      boxShadow: '0 4px 16px rgba(26,41,66,0.18)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={{ fontSize: 9, fontWeight: 700, color: 'rgba(255,255,255,0.7)', textTransform: 'uppercase', letterSpacing: 1.3 }}>
          ⚾ Maroons · This Week
        </div>
      </div>
      <div style={{ display: 'flex', gap: 6 }}>
        {schedule.map((g, i) => <GameItem key={g.date} game={g} isFeatured={i === featuredIdx} />)}
      </div>
    </div>
  );
}
