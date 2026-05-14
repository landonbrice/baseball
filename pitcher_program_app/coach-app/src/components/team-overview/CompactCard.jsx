import LastSevenStrip from './LastSevenStrip'
import ProgramStrip from './ProgramStrip'
import { buildTodayObjective } from '../../utils/todayObjective'
import { getDrivingSuffix, normalizeCategoryScores, pickDrivingCategory } from '../../utils/categoryScores'

function formatDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso + 'T12:00:00')
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'America/Chicago' })
}

export default function CompactCard({ pitcher, onOpen, activePrograms }) {
  const { mark, text } = buildTodayObjective(pitcher.today)
  const af = pitcher.af_7d
  const flag = pitcher.flag_level || 'green'
  // C7: CompactCard mostly hosts green pitchers (Team Overview partitions
  // red/yellow → HeroCard). Mirror HeroCard's contract — surface a driving-
  // category suffix when flagged. Additionally, when green AND a category
  // score is below 4 (low side of green), surface as a soft warning so
  // coaches see drift before the flag flips.
  let drivingSuffix = null
  if (flag !== 'green') {
    drivingSuffix = getDrivingSuffix(pitcher.category_scores)
  } else {
    const scores = normalizeCategoryScores(pitcher.category_scores)
    const drv = pickDrivingCategory(scores)
    if (drv && drv.value < 4) {
      drivingSuffix = { short: drv.short, score: drv.value.toFixed(1) }
    }
  }

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
      <div className="flex items-center gap-1.5">
        <div className="font-ui text-[9px] uppercase tracking-[0.12em] text-muted">{pitcher.role}</div>
        {drivingSuffix && (
          <span
            data-testid="flag-driving-suffix"
            className="font-ui text-[9px] uppercase tracking-[0.12em] text-muted tabular"
          >
            · {drivingSuffix.short} {drivingSuffix.score}
          </span>
        )}
      </div>

      <div className="mt-1.5">
        <span className="font-ui font-semibold uppercase text-[9px] tracking-[0.16em] text-muted mr-1">{mark}</span>
        <span className="font-ui text-body-sm text-graphite">{text}</span>
      </div>

      <div className="mt-1.5 flex items-center justify-between">
        <LastSevenStrip days={pitcher.last_7_days || []} />
        <span className="font-ui text-meta text-muted">Next: {formatDate(pitcher.next_scheduled_start)}</span>
      </div>

      <ProgramStrip programs={activePrograms} />
    </button>
  )
}
