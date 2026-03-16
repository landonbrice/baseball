import { FLAG_COLORS } from '../constants';

export default function FlagBadge({ level = 'green' }) {
  const colors = FLAG_COLORS[level] || FLAG_COLORS.green;
  return (
    <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium uppercase ${colors.bg} ${colors.text}`}>
      {level}
    </span>
  );
}
