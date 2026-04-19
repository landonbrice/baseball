import FlagPill from '../shell/FlagPill'
import LastSevenStrip from './LastSevenStrip'
import { buildTodayObjective } from '../../utils/todayObjective'

const BORDER = {
  red: 'border-l-crimson',
  yellow: 'border-l-amber',
  green: 'border-l-forest',
}

function formatDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso + 'T12:00:00')
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'America/Chicago' })
}

export default function HeroCard({ pitcher, onOpen }) {
  const flag = pitcher.flag_level || 'green'
  const border = BORDER[flag] || BORDER.green
  const { mark, text } = buildTodayObjective(pitcher.today)
  const af = pitcher.af_7d

  return (
    <button
      type="button"
      onClick={() => onOpen && onOpen(pitcher.pitcher_id)}
      aria-label={pitcher.name}
      className={`w-full text-left bg-bone border-l-[4px] ${border} rounded-[3px] p-3 hover:bg-hover transition-colors shadow-[0_1px_0_rgba(0,0,0,0.03)] hover:shadow-[0_2px_6px_rgba(0,0,0,0.06)]`}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="font-serif font-bold text-h2 text-charcoal leading-tight">{pitcher.name}</div>
          <div className="font-ui text-[10px] text-muted uppercase tracking-[0.1em] mt-0.5">
            {pitcher.role}
          </div>
        </div>
        <FlagPill level={flag} />
      </div>

      {pitcher.active_injury_flags && pitcher.active_injury_flags.length > 0 && (
        <div className="mt-2 inline-block bg-parchment text-maroon font-ui text-[10px] px-2 py-0.5 rounded-[2px]">
          {pitcher.active_injury_flags.join(' · ')}
        </div>
      )}

      <div className="mt-3 pb-2.5 border-b border-dashed border-cream-dark">
        <div className="font-ui font-semibold uppercase text-[9px] tracking-[0.16em] text-muted">
          Today · {mark}
        </div>
        <div className="font-ui text-body text-charcoal mt-0.5">{text}</div>
      </div>

      <div className="mt-2 grid grid-cols-3 gap-2">
        <div>
          <div className="font-ui font-semibold uppercase text-[9px] tracking-[0.16em] text-muted">AF 7d</div>
          <div className="font-serif font-bold text-h2 text-charcoal tabular">
            {af == null ? <span className="text-muted">—</span> : af.toFixed(1)}
          </div>
        </div>
        <div>
          <div className="font-ui font-semibold uppercase text-[9px] tracking-[0.16em] text-muted">Last 7</div>
          <div className="mt-1"><LastSevenStrip days={pitcher.last_7_days || []} /></div>
        </div>
        <div>
          <div className="font-ui font-semibold uppercase text-[9px] tracking-[0.16em] text-muted">Next Start</div>
          <div className="font-serif font-bold text-h3 text-charcoal tabular">
            {formatDate(pitcher.next_scheduled_start)}
          </div>
        </div>
      </div>
    </button>
  )
}
