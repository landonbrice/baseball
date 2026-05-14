/**
 * Programs — Plan 6 / B1, extended Plan 7 / B13.
 *
 * Single editorial scrolling page (spec D10). Sections top-to-bottom:
 *   1. Masthead — kicker, first-name title, today's date
 *   2. Today    — date + day_focus + plan source tag
 *   3. Active Programs — up to 2 cards (throwing + lifting)
 *   4. Build a Program CTA → opens BuilderSlideOver
 *   5. Drafts
 *   6. Favorites — block snapshots with inline expansion (D13 render-only)
 *   7. Program History — archived chronologically
 *   8. Browse Templates — collapsed by default; tap to expand → list of
 *      block_library templates with "Build with this template" entry into
 *      the BuilderSlideOver (Plan 7 / B13).
 */
import { useState, useMemo, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../App';
import { useApi } from '../hooks/useApi';
import { usePitcher } from '../hooks/usePitcher';
import BuilderSlideOver from '../components/BuilderSlideOver';

const TODAY_STR = () => new Date().toLocaleDateString('en-CA', { timeZone: 'America/Chicago' });

const DOMAIN_LABEL = { throwing: 'Throwing', lifting: 'Lifting' };
const SOURCE_LABEL = {
  llm_enriched:       { label: 'LLM enriched',       tone: 'forest' },
  python_fallback:    { label: 'Python fallback',    tone: 'amber' },
  program_prescribed: { label: 'Program prescribed', tone: 'maroon' },
};

const BLOCK_TYPE_FILTERS = [
  { id: null,        label: 'All'       },
  { id: 'lifting',   label: 'Lifting'   },
  { id: 'arm_care',  label: 'Arm care'  },
  { id: 'throwing',  label: 'Throwing'  },
  { id: 'warmup',    label: 'Warmup'    },
];

// ---------- Section primitives ----------

const sectionLabelStyle = {
  fontSize: 10, fontWeight: 700,
  color: 'var(--color-ink-faint)',
  textTransform: 'uppercase', letterSpacing: '0.08em',
  padding: '16px 16px 8px',
};

const cardStyle = {
  background: 'var(--color-white, #fff)',
  borderRadius: 12,
  padding: '12px 14px',
  marginBottom: 8,
  border: '0.5px solid var(--color-cream-border)',
};

const emptyHintStyle = {
  fontSize: 11, color: 'var(--color-ink-muted)',
  fontStyle: 'italic', padding: '0 16px 8px',
};

const chipStyle = (selected) => ({
  padding: '4px 12px',
  fontSize: 10, fontWeight: selected ? 600 : 400,
  background: selected ? 'var(--color-maroon)' : 'transparent',
  color: selected ? '#fff' : 'var(--color-ink-secondary)',
  border: selected ? 'none' : '0.5px solid var(--color-cream-border)',
  borderRadius: 12, cursor: 'pointer', whiteSpace: 'nowrap',
});

// ---------- Page ----------

export default function Programs() {
  const { pitcherId, initData } = useAuth();
  const navigate = useNavigate();
  const { profile, log } = usePitcher(pitcherId, initData);

  // Combined builder state — Browse Templates threads through `initialGoal`
  // alongside the existing `initialDomain` from Build CTA / Replace.
  const [builderState, setBuilderState] = useState({
    open: false, domain: 'throwing', goal: null,
  });
  const [refreshKey, setRefreshKey]     = useState(0);
  const bust = refreshKey ? `?_r=${refreshKey}` : '';

  const active     = useApi(pitcherId ? `/api/programs/active${bust}` : null, initData);
  const drafts     = useApi(pitcherId ? `/api/programs/drafts${bust}` : null, initData);
  const history    = useApi(pitcherId ? `/api/programs/history${bust}` : null, initData);
  const holdsToday = useApi(pitcherId ? `/api/programs/holds-today${bust}` : null, initData);
  const favorites  = useApi(pitcherId ? `/api/favorites${bust}` : null, initData);
  // B14: scheduled-throw anchors for the throwing Active card.
  const throws     = useApi(
    pitcherId ? `/api/pitcher/${pitcherId}/scheduled-throws${bust}` : null,
    initData,
  );

  const todayStr = TODAY_STR();

  // B14: pick next future throw (date >= today, Chicago tz). API already sorts ASC.
  const nextThrow = useMemo(() => {
    const list = throws.data?.scheduled_throws || [];
    return list.find(t => (t?.date || '') >= todayStr) || null;
  }, [throws.data, todayStr]);
  const entries = log?.entries || [];
  const todayEntry = entries.find(e => e.date === todayStr);

  const refetchAll = () => setRefreshKey(k => k + 1);
  const closeBuilder = () => setBuilderState({ open: false, domain: 'throwing', goal: null });

  const openBuilder = (domain) => {
    setBuilderState({ open: true, domain: domain || 'throwing', goal: null });
  };

  // B13: Browse Templates "Build with this template" entry point.
  const handleBuildWithTemplate = ({ domain, goal }) => {
    setBuilderState({
      open: true,
      domain: domain || 'throwing',
      goal: goal || null,
    });
  };

  return (
    <div style={{ paddingBottom: 100 }}>
      <Masthead profile={profile} todayStr={todayStr} />

      <TodaySection todayEntry={todayEntry} />

      <ActiveSection
        active={active.data}
        loading={active.loading}
        holdsToday={holdsToday.data}
        nextThrow={nextThrow}
        onReplace={openBuilder}
        onView={(programId) => navigate(`/programs/${programId}`)}
      />

      <BuildCTA onClick={() => openBuilder('throwing')} />

      <DraftsSection
        drafts={drafts.data?.drafts || []}
        loading={drafts.loading}
        onActivate={(programId) => navigate(`/programs/${programId}`)}
      />

      <FavoritesSection
        favorites={favorites.data?.favorites || []}
        loading={favorites.loading}
      />

      <HistorySection
        history={history.data?.history || []}
        loading={history.loading}
      />

      <BrowseTemplatesSection
        initData={initData}
        onBuildWith={handleBuildWithTemplate}
      />

      {builderState.open && (
        <BuilderSlideOver
          initialDomain={builderState.domain}
          initialGoal={builderState.goal}
          onClose={closeBuilder}
          onProgramActivated={() => { closeBuilder(); refetchAll(); }}
          onDraftSaved={() => { closeBuilder(); refetchAll(); }}
        />
      )}
    </div>
  );
}

// ---------- 1. Masthead ----------

function Masthead({ profile, todayStr }) {
  const firstName = (profile?.name || '').split(' ')[0] || 'Pitcher';
  // Human date: "Tue, May 13"
  const display = useMemo(() => {
    try {
      const d = new Date(todayStr + 'T12:00:00');
      return d.toLocaleDateString('en-US', {
        weekday: 'short', month: 'short', day: 'numeric',
        timeZone: 'America/Chicago',
      });
    } catch (_e) { return todayStr; }
  }, [todayStr]);
  return (
    <div data-testid="masthead" style={{ padding: '16px 16px 8px' }}>
      <div style={{
        fontSize: 9, fontWeight: 700, letterSpacing: '0.1em',
        color: 'var(--color-maroon)', textTransform: 'uppercase',
        marginBottom: 4,
      }}>My Programs</div>
      <h1 style={{
        fontSize: 22, fontWeight: 700, color: 'var(--color-ink-primary)',
        margin: 0, lineHeight: 1.2, letterSpacing: '-0.01em',
      }}>{firstName}</h1>
      <div style={{
        fontSize: 11, color: 'var(--color-ink-muted)', marginTop: 2,
      }}>{display}</div>
    </div>
  );
}

// ---------- 2. Today section ----------

function TodaySection({ todayEntry }) {
  if (!todayEntry) return null;
  const planGen = todayEntry.plan_generated || {};
  const dayFocus = planGen.day_focus;
  const source = planGen.source;
  const sourceInfo = source ? SOURCE_LABEL[source] : null;

  if (!dayFocus && !sourceInfo) return null;

  return (
    <div style={{ padding: '0 16px 8px' }} data-testid="today-section">
      <div style={{
        ...cardStyle, marginBottom: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        gap: 8,
      }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
          <span style={{
            fontSize: 9, fontWeight: 700, letterSpacing: '0.08em',
            color: 'var(--color-ink-faint)', textTransform: 'uppercase',
          }}>Today</span>
          <span style={{
            fontSize: 13, fontWeight: 600,
            color: 'var(--color-ink-primary)',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>{dayFocus || '—'}</span>
        </div>
        {sourceInfo && <SourceTag info={sourceInfo} />}
      </div>
    </div>
  );
}

function SourceTag({ info }) {
  const colorMap = {
    forest: 'var(--color-flag-green, #1D9E75)',
    amber:  'var(--color-flag-amber, #b86d00)',
    maroon: 'var(--color-maroon)',
  };
  const color = colorMap[info.tone] || 'var(--color-ink-muted)';
  return (
    <span data-testid="today-source-tag" style={{
      fontSize: 8, fontWeight: 700, letterSpacing: '0.05em',
      textTransform: 'uppercase', color,
      padding: '3px 8px', borderRadius: 999,
      border: `0.5px solid ${color}`, flexShrink: 0,
    }}>{info.label}</span>
  );
}

// ---------- 3. Active Programs ----------

function ActiveSection({ active, loading, holdsToday, nextThrow, onReplace, onView }) {
  if (loading) {
    return (
      <>
        <div style={sectionLabelStyle}>Active Programs</div>
        <div style={emptyHintStyle}>Loading…</div>
      </>
    );
  }
  const throwing = active?.throwing;
  const lifting  = active?.lifting;
  if (!throwing && !lifting) {
    return (
      <>
        <div style={sectionLabelStyle}>Active Programs</div>
        <div style={emptyHintStyle} data-testid="active-empty">
          No active program yet. Build one below.
        </div>
      </>
    );
  }
  return (
    <>
      <div style={sectionLabelStyle}>Active Programs</div>
      <div style={{ padding: '0 16px' }}>
        {throwing && (
          <ProgramCard
            program={throwing} heldToday={!!holdsToday?.throwing}
            nextThrow={nextThrow}
            onView={() => onView(throwing.program_id)}
            onReplace={() => onReplace('throwing')}
          />
        )}
        {lifting && (
          <ProgramCard
            program={lifting} heldToday={!!holdsToday?.lifting}
            onView={() => onView(lifting.program_id)}
            onReplace={() => onReplace('lifting')}
          />
        )}
      </div>
    </>
  );
}

function ProgramCard({ program, heldToday, nextThrow, onView, onReplace }) {
  const dayIndex = (program.current_day_index ?? 0) + 1;
  const totalDays = computeTotalDays(program);
  const heldDays = program.held_days_count ?? 0;
  const domainLabel = DOMAIN_LABEL[program.domain] || program.domain;
  // B14: only the throwing card gets the scheduled-throw anchor banner.
  const showNextThrow = program.domain === 'throwing' && !!nextThrow;
  const throwKind = nextThrow?.kind || nextThrow?.type;

  return (
    <div style={cardStyle} data-testid={`active-card-${program.domain}`}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        marginBottom: 6,
      }}>
        <div>
          <div style={{
            fontSize: 9, fontWeight: 700, letterSpacing: '0.08em',
            color: 'var(--color-ink-faint)', textTransform: 'uppercase',
            marginBottom: 1,
          }}>{domainLabel}</div>
          <div style={{
            fontSize: 14, fontWeight: 700, color: 'var(--color-ink-primary)',
          }}>
            Day {dayIndex}{totalDays ? ` of ${totalDays}` : ''}
          </div>
        </div>
        {heldToday && (
          <span style={{
            fontSize: 8, fontWeight: 700, letterSpacing: '0.05em',
            textTransform: 'uppercase',
            padding: '3px 7px', borderRadius: 999,
            background: 'var(--color-flag-amber, #b86d00)', color: '#fff',
          }}>Paused today</span>
        )}
      </div>
      <div style={{ fontSize: 11, color: 'var(--color-ink-muted)', marginBottom: 10 }}>
        {heldDays > 0 ? `Held ${heldDays} day${heldDays === 1 ? '' : 's'} total` : '—'}
        {program.start_date && (
          <> · Started <span style={{ color: 'var(--color-ink-secondary)' }}>{program.start_date}</span></>
        )}
      </div>
      {showNextThrow && (
        <div
          data-testid={`active-card-${program.domain}-next-throw`}
          style={{
            fontSize: 11, color: 'var(--color-ink-muted)',
            marginTop: -4, marginBottom: 10,
          }}
        >
          Next{throwKind ? ` ${throwKind}` : ''}:{' '}
          <strong style={{ color: 'var(--color-ink-secondary)' }}>{nextThrow.date}</strong>
        </div>
      )}
      <div style={{ display: 'flex', gap: 8 }}>
        <button
          type="button" onClick={onView}
          style={smallActionStyle('primary')}
        >View</button>
        <button
          type="button" onClick={onReplace}
          style={smallActionStyle('secondary')}
        >Replace</button>
      </div>
    </div>
  );
}

function smallActionStyle(variant) {
  if (variant === 'primary') {
    return {
      flex: 1, padding: '8px 12px', fontSize: 11, fontWeight: 600,
      background: 'var(--color-maroon)', color: '#fff',
      border: 'none', borderRadius: 8, cursor: 'pointer',
    };
  }
  return {
    flex: 1, padding: '8px 12px', fontSize: 11, fontWeight: 600,
    background: 'transparent', color: 'var(--color-maroon)',
    border: '0.5px solid var(--color-maroon)', borderRadius: 8, cursor: 'pointer',
  };
}

function computeTotalDays(program) {
  const days = program?.generated_schedule_json?.days;
  if (Array.isArray(days) && days.length > 0) return days.length;
  if (program?.start_date && program?.nominal_end_date) {
    const start = new Date(program.start_date);
    const end = new Date(program.nominal_end_date);
    const ms = end - start;
    if (Number.isFinite(ms) && ms >= 0) {
      return Math.round(ms / (1000 * 60 * 60 * 24)) + 1;
    }
  }
  return null;
}

// ---------- 4. Build CTA ----------

function BuildCTA({ onClick }) {
  return (
    <div style={{ padding: '12px 16px 16px' }}>
      <button
        type="button" onClick={onClick}
        data-testid="build-cta"
        style={{
          width: '100%', padding: '14px 16px',
          fontSize: 13, fontWeight: 700,
          background: 'var(--color-maroon)', color: '#fff',
          border: 'none', borderRadius: 12,
          cursor: 'pointer', letterSpacing: '0.02em',
        }}
      >Build a Program</button>
    </div>
  );
}

// ---------- 5. Drafts ----------

function DraftsSection({ drafts, loading, onActivate }) {
  if (loading) return null;
  if (!drafts || drafts.length === 0) return null;
  return (
    <>
      <div style={sectionLabelStyle}>Drafts</div>
      <div style={{ padding: '0 16px' }}>
        {drafts.map(d => (
          <div key={d.program_id} style={{ ...cardStyle, cursor: 'pointer' }}
            onClick={() => onActivate(d.program_id)}
            data-testid={`draft-${d.program_id}`}
          >
            <div style={{
              fontSize: 9, fontWeight: 700, letterSpacing: '0.08em',
              color: 'var(--color-ink-faint)', textTransform: 'uppercase',
              marginBottom: 2,
            }}>{DOMAIN_LABEL[d.domain] || d.domain} draft</div>
            <div style={{
              fontSize: 12, fontWeight: 600, color: 'var(--color-ink-primary)',
            }}>
              {d.start_date ? `Starts ${d.start_date}` : 'No start date'}
            </div>
            <div style={{ fontSize: 10, color: 'var(--color-ink-muted)', marginTop: 2 }}>
              Tap to review or activate
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

// ---------- 6. Favorites ----------

function FavoritesSection({ favorites, loading }) {
  const [filterType, setFilterType] = useState(null);
  const [expanded, setExpanded] = useState(null); // favorite_id

  const filtered = useMemo(() => {
    if (!filterType) return favorites;
    return favorites.filter(f => f.block_type === filterType);
  }, [favorites, filterType]);

  if (loading) {
    return (
      <>
        <div style={sectionLabelStyle}>Favorites</div>
        <div style={emptyHintStyle}>Loading…</div>
      </>
    );
  }
  if (!favorites || favorites.length === 0) {
    return (
      <>
        <div style={sectionLabelStyle}>Favorites</div>
        <div style={emptyHintStyle} data-testid="favorites-empty">
          No favorites yet. Tap the heart on any block to save it.
        </div>
      </>
    );
  }

  return (
    <>
      <div style={sectionLabelStyle}>Favorites</div>
      {/* Type chip filter */}
      <div style={{ display: 'flex', gap: 6, padding: '0 16px 8px', overflowX: 'auto' }}
        data-testid="favorites-filter">
        {BLOCK_TYPE_FILTERS.map(f => (
          <button
            key={String(f.id)} type="button"
            onClick={() => setFilterType(f.id)}
            style={chipStyle(filterType === f.id)}
            aria-pressed={filterType === f.id}
          >{f.label}</button>
        ))}
      </div>
      <div style={{ padding: '0 16px' }}>
        {filtered.length === 0 ? (
          <div style={emptyHintStyle}>No favorites of this type.</div>
        ) : (
          filtered.map(f => (
            <FavoriteRow
              key={f.favorite_id} favorite={f}
              expanded={expanded === f.favorite_id}
              onToggle={() => setExpanded(prev =>
                prev === f.favorite_id ? null : f.favorite_id)}
            />
          ))
        )}
      </div>
    </>
  );
}

function FavoriteRow({ favorite, expanded, onToggle }) {
  const blockLabel = BLOCK_TYPE_FILTERS.find(f => f.id === favorite.block_type)?.label
    || favorite.block_type;
  const snapshot = favorite.block_snapshot_json || {};
  const exercises = Array.isArray(snapshot.exercises) ? snapshot.exercises : [];

  return (
    <div style={cardStyle} data-testid={`favorite-${favorite.favorite_id}`}>
      <button
        type="button" onClick={onToggle}
        aria-expanded={expanded}
        style={{
          width: '100%', display: 'flex', alignItems: 'center',
          justifyContent: 'space-between', background: 'transparent',
          border: 'none', padding: 0, cursor: 'pointer', textAlign: 'left',
        }}
      >
        <div>
          <div style={{
            fontSize: 9, fontWeight: 700, letterSpacing: '0.08em',
            color: 'var(--color-ink-faint)', textTransform: 'uppercase',
          }}>{blockLabel}</div>
          <div style={{
            fontSize: 12, fontWeight: 600,
            color: 'var(--color-ink-primary)', marginTop: 2,
          }}>
            From {favorite.source_entry_date}
            {exercises.length > 0 && ` · ${exercises.length} exercises`}
          </div>
        </div>
        <span style={{ fontSize: 10, color: 'var(--color-ink-muted)' }}>
          {expanded ? '▾' : '▸'}
        </span>
      </button>
      {expanded && (
        <div style={{
          marginTop: 10, paddingTop: 10,
          borderTop: '0.5px solid var(--color-cream-border)',
        }} data-testid={`favorite-expanded-${favorite.favorite_id}`}>
          {exercises.length === 0 ? (
            <div style={{ fontSize: 11, color: 'var(--color-ink-muted)' }}>
              Snapshot has no exercises.
            </div>
          ) : (
            exercises.map((ex, i) => (
              <div key={i} style={{
                display: 'flex', justifyContent: 'space-between',
                padding: '4px 0', fontSize: 11,
                color: 'var(--color-ink-secondary)',
                borderBottom: i < exercises.length - 1
                  ? '0.5px solid var(--color-cream-border)' : 'none',
              }}>
                <span style={{
                  color: 'var(--color-ink-primary)', fontWeight: 500,
                }}>{ex.name || ex.exercise_id || 'Exercise'}</span>
                <span style={{ color: 'var(--color-ink-muted)' }}>
                  {[ex.sets, ex.reps].filter(v => v != null).join(' × ')}
                </span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

// ---------- 8. Browse Templates ----------

// Parse a Postgres int4range string into a "low–high weeks" label.
// Server returns shapes like "[8,12]", "[6,10)", "[4,)". Inclusive vs
// exclusive bounds matter — we render the *inclusive* range so the user
// sees the actually-allowed durations, not the raw bracket form.
function formatDurationRange(raw) {
  if (raw == null) return null;
  if (typeof raw !== 'string') return String(raw);
  const m = raw.match(/^([\[\(])\s*(\d+)?\s*,\s*(\d+)?\s*([\]\)])$/);
  if (!m) return raw; // unknown shape — fall back to raw string
  const [, lb, lowStr, highStr, ub] = m;
  if (lowStr == null && highStr == null) return null;
  let low = lowStr != null ? parseInt(lowStr, 10) : null;
  let high = highStr != null ? parseInt(highStr, 10) : null;
  // Postgres int4range with exclusive bracket: shift to inclusive.
  if (low != null && lb === '(') low += 1;
  if (high != null && ub === ')') high -= 1;
  if (low != null && high != null) {
    return low === high ? `${low} wk` : `${low}–${high} wk`;
  }
  if (low != null) return `${low}+ wk`;
  if (high != null) return `up to ${high} wk`;
  return null;
}

function BrowseTemplatesSection({ initData, onBuildWith }) {
  const [open, setOpen] = useState(false);
  // useApi skips fetching when path is null — gate by `open` so we don't
  // hit the network until the user expands the section.
  const { data, loading, error } = useApi(
    open ? '/api/programs/templates' : null,
    initData,
  );
  const templates = data?.templates || [];

  return (
    <>
      <button
        type="button"
        data-testid="browse-templates-toggle"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
        style={{
          ...sectionLabelStyle,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          width: '100%',
          background: 'transparent', border: 'none', cursor: 'pointer',
          textAlign: 'left',
        }}
      >
        <span>Browse Templates</span>
        <span style={{ fontSize: 10, color: 'var(--color-ink-muted)' }}>
          {open ? '▾' : '▸'}
        </span>
      </button>
      {open && (
        <div style={{ padding: '0 16px' }} data-testid="browse-templates-body">
          {loading && (
            <div style={emptyHintStyle}>Loading templates…</div>
          )}
          {error && (
            <div role="alert" style={emptyHintStyle}>
              Could not load templates.
            </div>
          )}
          {!loading && !error && templates.length === 0 && (
            <div style={emptyHintStyle}>No templates available.</div>
          )}
          {!loading && !error && templates.map(t => (
            <TemplateRow
              key={t.block_template_id}
              template={t}
              onBuildWith={() => onBuildWith?.({
                domain: t.domain,
                goal: Array.isArray(t.goal_tags) ? t.goal_tags[0] : null,
              })}
            />
          ))}
        </div>
      )}
    </>
  );
}

function TemplateRow({ template, onBuildWith }) {
  const durationLabel = formatDurationRange(template.duration_range_weeks);
  const domainLabel = DOMAIN_LABEL[template.domain] || template.domain;
  return (
    <div
      style={cardStyle}
      data-testid={`template-row-${template.block_template_id}`}
    >
      <div style={{
        display: 'flex', alignItems: 'baseline', justifyContent: 'space-between',
        marginBottom: 6, gap: 8,
      }}>
        <div style={{ minWidth: 0 }}>
          <div style={{
            fontSize: 9, fontWeight: 700, letterSpacing: '0.08em',
            color: 'var(--color-ink-faint)', textTransform: 'uppercase',
            marginBottom: 2,
          }}>{domainLabel}{durationLabel ? ` · ${durationLabel}` : ''}</div>
          <div style={{
            fontSize: 13, fontWeight: 700, color: 'var(--color-ink-primary)',
          }}>{template.name}</div>
        </div>
      </div>
      {template.description && (
        <div style={{
          fontSize: 11, color: 'var(--color-ink-muted)', marginBottom: 10,
          lineHeight: 1.4,
        }}>{template.description}</div>
      )}
      <button
        type="button"
        onClick={onBuildWith}
        data-testid={`template-build-${template.block_template_id}`}
        style={smallActionStyle('primary')}
      >Build with this template</button>
    </div>
  );
}

// ---------- 7. Program History ----------

function HistorySection({ history, loading }) {
  if (loading) return null;
  if (!history || history.length === 0) return null;
  return (
    <>
      <div style={sectionLabelStyle}>Program History</div>
      <div style={{ padding: '0 16px' }}>
        {history.map(p => (
          <div key={p.program_id} style={cardStyle}
            data-testid={`history-${p.program_id}`}>
            <div style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
            }}>
              <div style={{
                fontSize: 12, fontWeight: 600, color: 'var(--color-ink-primary)',
              }}>{DOMAIN_LABEL[p.domain] || p.domain}</div>
              <div style={{ fontSize: 10, color: 'var(--color-ink-faint)' }}>
                {p.archived_at ? p.archived_at.slice(0, 10) : ''}
              </div>
            </div>
            <div style={{ fontSize: 10, color: 'var(--color-ink-muted)', marginTop: 2 }}>
              {p.start_date} → {p.archived_at ? p.archived_at.slice(0, 10) : '—'}
              {p.archive_reason && (
                <> · <span style={{ fontStyle: 'italic' }}>{p.archive_reason}</span></>
              )}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
