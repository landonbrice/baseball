import { useState, useMemo } from 'react'
import FlagPill from './shell/FlagPill'

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'flagged', label: 'Flagged' },
  { key: 'notes', label: 'With notes' },
]

function Sparkline({ series, color = 'var(--color-maroon)', label }) {
  if (!Array.isArray(series) || series.length === 0) return null
  const width = 260
  const height = 40
  const pad = 2
  const values = series.map(v => (typeof v === 'number' ? v : null))
  const clean = values.filter(v => v != null)
  if (clean.length === 0) return null
  const min = Math.min(...clean)
  const max = Math.max(...clean)
  const range = max - min || 1
  const step = series.length > 1 ? (width - pad * 2) / (series.length - 1) : 0
  const points = values
    .map((v, i) => {
      if (v == null) return null
      const x = pad + step * i
      const y = pad + (1 - (v - min) / range) * (height - pad * 2)
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .filter(Boolean)
    .join(' ')
  return (
    <div>
      <div className="font-ui font-semibold uppercase text-[9px] tracking-[0.16em] text-muted mb-1">
        {label} <span className="tabular text-graphite ml-1">({min.toFixed(1)}&ndash;{max.toFixed(1)})</span>
      </div>
      <svg width={width} height={height} className="block">
        <polyline
          points={points}
          fill="none"
          stroke={color}
          strokeWidth="1.5"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      </svg>
    </div>
  )
}

export default function PlayerHistory({ data }) {
  const recent = data?.recent_check_ins || []
  const injuries = data?.injuries || []
  const [filter, setFilter] = useState('all')

  const armFeel = useMemo(
    () => [...recent].reverse().map(e => e.pre_training?.arm_feel ?? null),
    [recent]
  )
  const energy = useMemo(
    () => [...recent].reverse().map(e => e.pre_training?.overall_energy ?? null),
    [recent]
  )

  const filtered = useMemo(() => {
    return recent.filter(e => {
      if (filter === 'flagged') return e.pre_training?.flag_level === 'yellow' || e.pre_training?.flag_level === 'red'
      if (filter === 'notes') return (e.pre_training?.note || '').trim().length > 0
      return true
    })
  }, [recent, filter])

  return (
    <div className="space-y-5">
      <section>
        <h3 className="font-ui font-semibold uppercase text-[10px] tracking-[0.2em] text-maroon mb-2">
          Last 30 days
        </h3>
        <div className="grid grid-cols-2 gap-5">
          <Sparkline series={armFeel} color="#5c1020" label="Arm feel" />
          <Sparkline series={energy} color="#2d5a3d" label="Energy" />
        </div>
      </section>

      <section>
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-ui font-semibold uppercase text-[10px] tracking-[0.2em] text-maroon">
            Check-in log
          </h3>
          <div className="flex gap-1">
            {FILTERS.map(f => (
              <button
                key={f.key}
                type="button"
                onClick={() => setFilter(f.key)}
                className={`font-ui text-[10px] uppercase tracking-[0.1em] px-2 py-1 rounded-[2px] ${
                  filter === f.key
                    ? 'bg-maroon text-bone'
                    : 'bg-parchment text-graphite hover:bg-hover'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
        <div className="divide-y divide-cream-dark">
          {filtered.length === 0 && (
            <p className="font-ui text-meta text-muted py-2">No entries match this filter.</p>
          )}
          {filtered.map(e => (
            <div key={e.date} className="py-2">
              <div className="flex items-center gap-3">
                <span className="font-ui text-meta text-graphite w-20 tabular">{e.date}</span>
                <FlagPill level={e.pre_training?.flag_level || 'green'} />
                <span className="font-serif text-body text-charcoal tabular">
                  AF {e.pre_training?.arm_feel ?? '—'}
                </span>
                {e.pre_training?.arm_assessment?.needs_followup && (
                  <span className="font-ui text-[9px] font-bold uppercase tracking-[0.12em] text-amber bg-amber/10 px-1.5 py-0.5 rounded-[2px]">
                    Follow up
                  </span>
                )}
                {(e.pre_training?.note || '').trim() && (
                  <span className="font-ui text-meta text-muted italic truncate">
                    &ldquo;{e.pre_training.note}&rdquo;
                  </span>
                )}
              </div>
              {e.pre_training?.arm_assessment?.summary && (
                <p className="font-ui text-meta text-muted mt-1 ml-[5.75rem]">
                  {e.pre_training.arm_assessment.summary}
                </p>
              )}
            </div>
          ))}
        </div>
      </section>

      {injuries.length > 0 && (
        <section>
          <h3 className="font-ui font-semibold uppercase text-[10px] tracking-[0.2em] text-maroon mb-2">
            Injury history
          </h3>
          <div className="space-y-1">
            {injuries.map((inj, i) => (
              <div key={i} className="bg-parchment rounded-[3px] px-3 py-2">
                <p className="font-serif font-bold text-body text-charcoal">{inj.area}</p>
                <p className="font-ui text-meta text-muted">
                  {inj.status || ''}{inj.flag_level ? ` · ${inj.flag_level}` : ''}{inj.notes ? ` · ${inj.notes}` : ''}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
