const FLAG_STYLES = {
  green:  'bg-[#064e3b] text-flag-green',
  yellow: 'bg-[#713f12] text-flag-yellow',
  red:    'bg-[#7f1d1d] text-flag-red',
};

export default function FlagBadge({ level = 'green' }) {
  const style = FLAG_STYLES[level] || FLAG_STYLES.green;
  return (
    <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium uppercase ${style}`}>
      {level}
    </span>
  );
}
