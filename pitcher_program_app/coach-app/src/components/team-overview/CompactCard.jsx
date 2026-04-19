import LastSevenStrip from './LastSevenStrip'
import { buildTodayObjective } from '../../utils/todayObjective'

function formatDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso + 'T12:00:00')
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'America/Chicago' })
}

export default function CompactCard({ pitcher, onOpen }) {
  const { mark, text } = buildTodayObjective(pitcher.today)
  const af = pitcher.af_7d

  return (
    <button
      type="button"
      aria-label={pitcher.name}
      onClick={() => onOpen && onOpen(pitcher.pitcher_id)}
      className="w-full text-left bg-bone border-l-[3px] border-l-forest rounded-[3px] px-3 py-2.5 hover:bg-hover transition-colors"
    >
      <div className="flex items-baseline justify-between gap-2">
        <div className="font-serif font-bold text-h3 text-charcoal leading-tight">{pitcher.name}</div>
        <div className="font-ui font-bold text-body-sm text-forest tabular">
          {af == null ? <span className="text-muted">—</span> : af.toFixed(1)}
        </div>
      </div>
      <div className="font-ui text-[9px] uppercase tracking-[0.12em] text-muted">{pitcher.role}</div>

      <div className="mt-1.5">
        <span className="font-ui font-semibold uppercase text-[9px] tracking-[0.16em] text-muted mr-1">{mark}</span>
        <span className="font-ui text-body-sm text-graphite">{text}</span>
      </div>

      <div className="mt-1.5 flex items-center justify-between">
        <LastSevenStrip days={pitcher.last_7_days || []} />
        <span className="font-ui text-meta text-muted">Next: {formatDate(pitcher.next_scheduled_start)}</span>
      </div>
    </button>
  )
}
