/**
 * Plan 7 / C3 — Recent player-built programs strip.
 *
 * Renders a flat roster list of the most-recent N programs across the team.
 * Each row: {pitcher_name} · {domain} · {template_id} · {status} · created {date}.
 *
 * This is a roster overview, not an insights feed — no CTAs.
 */

function fmtDate(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  } catch {
    return '—'
  }
}

function StatusPill({ status }) {
  const tone =
    status === 'active' ? 'bg-forest/15 text-forest border-forest/30'
    : status === 'draft' ? 'bg-amber/15 text-amber border-amber/30'
    : status === 'archived' ? 'bg-charcoal/10 text-subtle border-charcoal/20'
    : status === 'error' ? 'bg-crimson/15 text-crimson border-crimson/30'
    : 'bg-cream text-subtle border-cream-dark'
  return (
    <span
      className={`font-ui text-meta uppercase tracking-wider px-1.5 py-0.5 rounded-[2px] border ${tone}`}
    >
      {status || 'unknown'}
    </span>
  )
}

export default function PlayerBuiltProgramsStrip({ programs = [] }) {
  if (!programs || programs.length === 0) {
    return (
      <p className="font-ui text-body-sm text-subtle italic">
        No player-built programs yet.
      </p>
    )
  }

  return (
    <ul className="divide-y divide-cream-dark border border-cream-dark rounded-[3px] bg-bone">
      {programs.map(p => (
        <li
          key={p.program_id}
          className="px-3 py-2 flex items-center gap-3 text-body-sm font-ui"
        >
          <div className="flex-1 min-w-0">
            <p className="text-charcoal truncate">
              <span className="font-semibold">{p.pitcher_name || p.pitcher_id}</span>
              <span className="text-subtle"> · </span>
              <span className="capitalize">{p.domain || '—'}</span>
              <span className="text-subtle"> · </span>
              <span className="text-subtle">{p.parent_template_id || '—'}</span>
            </p>
            <p className="text-meta text-subtle truncate">
              created {fmtDate(p.created_at)}
              {p.created_by_role ? ` · by ${p.created_by_role}` : ''}
            </p>
          </div>
          <StatusPill status={p.status} />
        </li>
      ))}
    </ul>
  )
}
