const EMPHASIS_BORDER = {
  hypertrophy: 'var(--color-maroon-ink)',
  strength: 'var(--color-maroon)',
  power: 'var(--color-crimson)',
  maintenance: 'var(--color-forest)',
  gpp: 'var(--color-amber)',
}

/**
 * Plan 7 / C5 — map a `training_phase_blocks` row to one or more
 * `block_library.compatible_phases` strings used by program templates.
 *
 * Live `training_phase_blocks` rows use vocabulary like:
 *   phase_name: "Fall GPP" | "Strength Block" | "Power Block" | "Preseason Ramp" | "In-Season"
 *   emphasis:   "hypertrophy" | "strength" | "power" | "maintenance" | "gpp"
 *
 * `block_library.compatible_phases` uses vocabulary like:
 *   "off_season" | "preseason" | "in_season" | "in_season_active"
 *
 * The phase_name string wins when it matches a known token; otherwise we
 * fall back to emphasis. A phase can map to multiple template phases (e.g.
 * "In-Season" maps to both in_season and in_season_active).
 */
export function phaseToTemplatePhaseIds(phase) {
  if (!phase) return []
  const name = String(phase.phase_name || '').toLowerCase()
  const emphasis = String(phase.emphasis || '').toLowerCase()

  if (/in[-\s]?season/.test(name)) return ['in_season', 'in_season_active']
  if (/preseason/.test(name)) return ['preseason']
  if (/postseason|off[-\s]?season/.test(name)) return ['off_season']

  if (emphasis === 'maintenance') return ['in_season', 'in_season_active']
  if (emphasis === 'power') return ['preseason']
  if (emphasis === 'hypertrophy' || emphasis === 'strength' || emphasis === 'gpp') {
    return ['off_season']
  }
  return []
}

function templatesForPhase(phase, templates) {
  const phaseIds = phaseToTemplatePhaseIds(phase)
  if (phaseIds.length === 0) return []
  return (templates || []).filter(t => {
    const compatible = t.compatible_phases || []
    return compatible.some(p => phaseIds.includes(p))
  })
}

export default function PhaseTimeline({ phases, onSelect, templates = [] }) {
  if (!phases || phases.length === 0) return null

  const today = new Date().toLocaleDateString('en-CA', { timeZone: 'America/Chicago' })

  return (
    <div className="flex gap-1.5 overflow-x-auto pb-3" role="list">
      {phases.map(p => {
        const isCurrent = today >= p.start_date && today <= p.end_date
        const borderColor = EMPHASIS_BORDER[p.emphasis] || 'var(--color-graphite)'
        const days = Math.max(1, Math.round(
          (new Date(p.end_date) - new Date(p.start_date)) / 86400000
        ))
        const width = Math.max(140, days * 2)
        const matched = templatesForPhase(p, templates)

        return (
          <button
            key={p.phase_block_id}
            type="button"
            role="listitem"
            onClick={() => onSelect?.(p)}
            className="group relative flex-shrink-0 bg-cream rounded-[3px] p-3 cursor-pointer hover:bg-cream-dark/50 transition-colors text-left"
            style={{
              width: `${width}px`,
              borderLeft: `3px solid ${borderColor}`,
              borderBottom: isCurrent ? `2px solid var(--color-maroon)` : undefined,
            }}
          >
            <p className={`font-serif font-bold text-body truncate ${isCurrent ? 'text-maroon' : 'text-charcoal'}`}>
              {p.phase_name}
            </p>
            <p className="font-ui text-micro text-subtle whitespace-nowrap">
              {p.start_date} — {p.end_date}
            </p>
            <p className="font-ui text-meta text-subtle capitalize">{p.emphasis}</p>

            {matched.length > 0 && (
              <div
                className="mt-2 pt-2 border-t border-cream-dark"
                aria-label={`Templates available in ${p.phase_name}`}
              >
                <p className="font-ui text-micro uppercase tracking-[0.16em] text-subtle mb-1">
                  Templates
                </p>
                <div className="flex flex-wrap gap-1">
                  {matched.map(t => (
                    <span
                      key={t.block_template_id}
                      className="font-ui text-micro text-charcoal bg-bone border border-cream-dark rounded-[3px] px-1.5 py-0.5 truncate max-w-full"
                      title={t.name}
                    >
                      {t.name}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <span className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity font-ui text-meta text-subtle">
              ✏
            </span>
          </button>
        )
      })}
    </div>
  )
}
