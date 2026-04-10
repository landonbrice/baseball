import DayBubble from './DayBubble';
import SetNextThrowButton from './SetNextThrowButton';

export default function WeekArc({ arc, onAddThrow }) {
  if (!arc) return null;
  return (
    <div style={{ padding: '18px 14px 14px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0 4px 12px' }}>
        <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--color-maroon)', textTransform: 'uppercase', letterSpacing: 1.2 }}>
          This Week
        </div>
        <SetNextThrowButton onAdd={onAddThrow} />
      </div>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 2, padding: '6px 2px 2px', position: 'relative' }}>
        <div style={{ position: 'absolute', left: 30, right: 30, top: 38, height: 1.5, background: 'var(--color-cream-border)', zIndex: 0 }} />
        {arc.days.map(day => <DayBubble key={day.date} day={day} />)}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, marginTop: 14, fontSize: 9, color: 'var(--color-ink-muted)', textTransform: 'uppercase', letterSpacing: 0.5, fontWeight: 600 }}>
        <span style={{
          width: 12, height: 12, borderRadius: '50%', background: '#fff',
          boxShadow: '0 0 0 1.5px var(--color-cream-border), 0 0 0 3px #1a2942',
          marginRight: 2,
        }} />
        ring = game day
      </div>
    </div>
  );
}
