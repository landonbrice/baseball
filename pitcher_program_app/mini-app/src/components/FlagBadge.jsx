const COLORS = {
  green:  { bg: 'rgba(29,158,117,0.12)', color: 'var(--color-flag-green)' },
  yellow: { bg: 'rgba(186,117,23,0.12)', color: 'var(--color-flag-yellow)' },
  red:    { bg: 'rgba(163,45,45,0.12)',   color: 'var(--color-flag-red)' },
};

export default function FlagBadge({ level = 'green' }) {
  const c = COLORS[level] || COLORS.green;
  return (
    <span style={{
      display: 'inline-block', padding: '2px 10px', borderRadius: 10,
      fontSize: 10, fontWeight: 600, textTransform: 'uppercase',
      background: c.bg, color: c.color,
    }}>
      {level}
    </span>
  );
}
