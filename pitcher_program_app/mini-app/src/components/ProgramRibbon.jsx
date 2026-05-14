/**
 * ProgramRibbon — Plan 6 / B2.
 *
 * Thin ribbon above DailyCard summarizing an active program:
 *   "Throwing · Day 22 of 84 · Held 2 days"
 *
 * Renders nothing when no active program. If both throwing and lifting are
 * active, parent stacks two ribbons.
 *
 * Held affordance: when `heldToday` is true, swaps the right side for a
 * "Program paused today" pill in amber to make the pause obvious without
 * pushing other content down.
 */

function dayCountFromProgram(program) {
  // Prefer generated_schedule_json.days.length when present (drafts/active
  // detail), but the /programs/active summary endpoint trims that column.
  // Fall back to inclusive day count between start_date and nominal_end_date.
  const days = program?.generated_schedule_json?.days;
  if (Array.isArray(days) && days.length > 0) return days.length;
  if (program?.start_date && program?.nominal_end_date) {
    const start = new Date(program.start_date);
    const end = new Date(program.nominal_end_date);
    const ms = end - start;
    if (Number.isFinite(ms) && ms >= 0) {
      // +1 to make inclusive (day_index is 0-based but the ribbon reads naturally as "1 of N")
      return Math.round(ms / (1000 * 60 * 60 * 24)) + 1;
    }
  }
  return null;
}

function domainLabel(domain) {
  if (domain === 'throwing') return 'Throwing';
  if (domain === 'lifting')  return 'Lifting';
  return domain || 'Program';
}

export default function ProgramRibbon({ program, heldToday = false }) {
  if (!program) return null;
  const totalDays = dayCountFromProgram(program);
  const dayIndex = (program.current_day_index ?? 0) + 1; // 1-based for display
  const heldDays = program.held_days_count ?? 0;

  return (
    <div
      role="status"
      data-testid={`program-ribbon-${program.domain || 'unknown'}`}
      style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        gap: 10, padding: '8px 12px',
        background: 'var(--color-maroon)', color: '#fff',
        borderRadius: 10, marginBottom: 8,
      }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        <span style={{
          fontSize: 9, fontWeight: 700, letterSpacing: '0.08em',
          textTransform: 'uppercase', opacity: 0.7,
        }}>{domainLabel(program.domain)}</span>
        <span style={{ fontSize: 12, fontWeight: 600 }}>
          Day {dayIndex}{totalDays ? ` of ${totalDays}` : ''}
          {heldDays > 0 ? ` · Held ${heldDays} day${heldDays === 1 ? '' : 's'}` : ''}
        </span>
      </div>
      {heldToday && (
        <span data-testid="held-today-pill" style={{
          fontSize: 9, fontWeight: 700, letterSpacing: '0.05em',
          textTransform: 'uppercase',
          padding: '3px 8px', borderRadius: 999,
          background: 'var(--color-flag-amber, #b86d00)', color: '#fff',
        }}>Paused today</span>
      )}
    </div>
  );
}
