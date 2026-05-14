/**
 * ProgramStrip — small 2-row caption showing a pitcher's active programs.
 *
 * Rendered inside HeroCard and CompactCard on the Team Overview page.
 * Pulled from GET /api/coach/pitcher/{id}/programs?status=active (Plan 7 / A3-coach).
 *
 * Shape per program row (subset of _PROGRAM_SUMMARY_COLUMNS in bot/services/db.py):
 *   {
 *     program_id: string,
 *     domain: 'throwing' | 'lifting',
 *     parent_template_id: string,
 *     current_day_index: number | null,   // 0-indexed; render as Day N+1
 *     held_days_count: number | null,
 *   }
 *
 * Returns null when there are no programs so the caller does not have to gate.
 */
export default function ProgramStrip({ programs }) {
  if (!programs || programs.length === 0) return null
  return (
    <div
      data-testid="program-strip"
      className="mt-2 flex flex-col gap-0.5"
    >
      {programs.map((p) => {
        const domainLabel = p.domain
          ? `${p.domain[0].toUpperCase()}${p.domain.slice(1)}`
          : '—'
        const day = (p.current_day_index ?? 0) + 1
        const held = p.held_days_count ?? 0
        return (
          <div
            key={p.program_id}
            className="font-ui text-[10px] text-muted leading-snug"
          >
            [{domainLabel}] {p.parent_template_id} · Day {day}
            {held > 0 && ` · Held ${held}`}
          </div>
        )
      })}
    </div>
  )
}
