import { useState, useCallback } from 'react';
import { toggleExercise } from '../api';

const TABS = [
  { id: 'arm_care', label: 'Arm care' },
  { id: 'lifting', label: 'Lifting' },
  { id: 'throwing', label: 'Throwing' },
  { id: 'notes', label: 'Notes' },
];

function resolveExercise(exerciseId, exerciseMap, slugMap) {
  if (exerciseMap[exerciseId]) return exerciseMap[exerciseId];
  const resolvedId = slugMap[exerciseId];
  if (resolvedId && exerciseMap[resolvedId]) return exerciseMap[resolvedId];
  return null;
}

export default function DailyCard({ entry, exerciseMap = {}, slugMap = {}, pitcherId, initData, readOnly = false }) {
  const [activeTab, setActiveTab] = useState('arm_care');
  const [completed, setCompleted] = useState(entry?.completed_exercises || {});

  const handleToggle = useCallback((exerciseId, newState) => {
    if (readOnly) return;
    setCompleted(prev => ({ ...prev, [exerciseId]: newState }));
    toggleExercise(pitcherId, entry?.date, exerciseId, newState, initData)
      .catch(() => setCompleted(prev => ({ ...prev, [exerciseId]: !newState })));
  }, [pitcherId, entry?.date, initData, readOnly]);

  if (!entry) {
    return (
      <div style={{ background: 'var(--color-white)', borderRadius: 12, padding: 16 }}>
        <p style={{ color: 'var(--color-ink-muted)', fontSize: 13 }}>No training data for today</p>
      </div>
    );
  }

  const { plan_generated } = entry;
  const armCare = entry.arm_care || plan_generated?.arm_care;
  const lifting = entry.lifting || plan_generated?.lifting;
  const throwing = entry.throwing || plan_generated?.throwing;
  const notes = entry.notes || plan_generated?.notes || [];
  const hasStructured = !!(armCare?.exercises?.length || lifting?.exercises?.length);
  const fallbackBlocks = plan_generated?.exercise_blocks || [];

  // Tab content availability
  const tabHasContent = {
    arm_care: armCare?.exercises?.length > 0 || (!hasStructured && fallbackBlocks.some(b => b.block_name?.toLowerCase().includes('arm'))),
    lifting: lifting?.exercises?.length > 0 || (!hasStructured && fallbackBlocks.some(b => !b.block_name?.toLowerCase().includes('arm') && !b.block_name?.toLowerCase().includes('plyo'))),
    throwing: !!(throwing?.detail || throwing?.details || plan_generated?.throwing_plan),
    notes: notes.length > 0,
  };

  return (
    <div style={{ background: 'var(--color-white)', borderRadius: 12, overflow: 'hidden' }}>
      {/* ── Pill nav ── */}
      <div style={{
        padding: '8px 12px',
        display: 'flex',
        gap: 6,
        overflowX: 'auto',
        borderBottom: '0.5px solid var(--color-cream-border)',
        background: 'var(--color-cream-bg)',
      }}>
        {TABS.map(s => (
          <div
            key={s.id}
            onClick={() => setActiveTab(s.id)}
            style={{
              padding: '4px 12px',
              borderRadius: 14,
              fontSize: 10,
              fontWeight: activeTab === s.id ? 700 : 400,
              background: activeTab === s.id ? 'var(--color-maroon)' : 'transparent',
              color: activeTab === s.id ? '#fff' : tabHasContent[s.id] ? 'var(--color-ink-secondary)' : 'var(--color-ink-faint)',
              border: activeTab === s.id ? 'none' : '0.5px solid var(--color-cream-border)',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              flexShrink: 0,
            }}
          >
            {s.label}
          </div>
        ))}
      </div>

      {/* ── Tab content ── */}
      <div style={{ padding: 14 }}>
        {activeTab === 'arm_care' && (
          <TabArmCare armCare={armCare} fallbackBlocks={fallbackBlocks} hasStructured={hasStructured}
            exerciseMap={exerciseMap} slugMap={slugMap} completed={completed} onToggle={readOnly ? null : handleToggle} />
        )}
        {activeTab === 'lifting' && (
          <TabLifting lifting={lifting} fallbackBlocks={fallbackBlocks} hasStructured={hasStructured}
            exerciseMap={exerciseMap} slugMap={slugMap} completed={completed} onToggle={readOnly ? null : handleToggle} />
        )}
        {activeTab === 'throwing' && (
          <TabThrowing throwing={throwing} fallbackPlan={plan_generated?.throwing_plan} />
        )}
        {activeTab === 'notes' && <TabNotes notes={notes} />}
      </div>

      {/* Outing data */}
      {entry.outing && (
        <div style={{ padding: '0 14px 14px' }}>
          <div style={{ background: 'var(--color-cream-bg)', borderRadius: 10, padding: 12 }}>
            <p style={{ fontSize: 10, color: 'var(--color-maroon)', fontWeight: 600, marginBottom: 4 }}>Outing</p>
            <p style={{ fontSize: 13, color: 'var(--color-ink-primary)' }}>
              {entry.outing.pitch_count} pitches · Post feel: {entry.outing.arm_feel ?? entry.outing.post_arm_feel}/5
            </p>
            {entry.outing.notes && <p style={{ fontSize: 11, color: 'var(--color-ink-muted)', marginTop: 4 }}>{entry.outing.notes}</p>}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Tabs ──

function TabArmCare({ armCare, fallbackBlocks, hasStructured, exerciseMap, slugMap, completed, onToggle }) {
  if (hasStructured && armCare?.exercises?.length) {
    return (
      <div>
        {armCare.timing && <SectionLabel>{armCare.timing}</SectionLabel>}
        <SupersetList exercises={armCare.exercises} exerciseMap={exerciseMap} slugMap={slugMap} completed={completed} onToggle={onToggle} />
      </div>
    );
  }
  const armBlocks = fallbackBlocks.filter(b => b.block_name?.toLowerCase().includes('arm'));
  if (armBlocks.length) {
    return armBlocks.map((block, i) => (
      <FallbackBlock key={i} block={block} exerciseMap={exerciseMap} slugMap={slugMap} completed={completed} onToggle={onToggle} />
    ));
  }
  return <EmptyTab>No arm care prescribed today</EmptyTab>;
}

function TabLifting({ lifting, fallbackBlocks, hasStructured, exerciseMap, slugMap, completed, onToggle }) {
  if (hasStructured && lifting?.exercises?.length) {
    return (
      <div>
        {lifting.intent && <SectionLabel>{lifting.intent}</SectionLabel>}
        <SupersetList exercises={lifting.exercises} exerciseMap={exerciseMap} slugMap={slugMap} completed={completed} onToggle={onToggle} />
      </div>
    );
  }
  const liftBlocks = fallbackBlocks.filter(b => !b.block_name?.toLowerCase().includes('arm') && !b.block_name?.toLowerCase().includes('plyo'));
  if (liftBlocks.length) {
    return liftBlocks.map((block, i) => (
      <FallbackBlock key={i} block={block} exerciseMap={exerciseMap} slugMap={slugMap} completed={completed} onToggle={onToggle} />
    ));
  }
  return <EmptyTab>No lifting prescribed today</EmptyTab>;
}

function TabThrowing({ throwing, fallbackPlan }) {
  const data = throwing || fallbackPlan;
  if (!data) return <EmptyTab>No throwing today</EmptyTab>;
  const type = data.type || data.details || 'none';
  const detail = data.detail || data.details || '';
  const intent = data.intent;
  if (type === 'none' && !detail) return <EmptyTab>No throwing today — rest/recovery</EmptyTab>;
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-ink-primary)', textTransform: 'capitalize' }}>{type.replace(/_/g, ' ')}</span>
        {intent && <PillBadge>{intent}</PillBadge>}
      </div>
      {detail && <p style={{ fontSize: 13, color: 'var(--color-ink-secondary)', marginTop: 6 }}>{detail}</p>}
    </div>
  );
}

function TabNotes({ notes }) {
  if (!notes?.length) return <EmptyTab>No notes for today</EmptyTab>;
  return (
    <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
      {notes.map((note, i) => (
        <li key={i} style={{ display: 'flex', gap: 8, fontSize: 13, color: 'var(--color-ink-secondary)', marginBottom: 8 }}>
          <span style={{ color: 'var(--color-ink-muted)', flexShrink: 0 }}>·</span>
          <span>{note}</span>
        </li>
      ))}
    </ul>
  );
}

// ── Superset renderer ──

function SupersetList({ exercises, exerciseMap, slugMap, completed, onToggle }) {
  const groups = [];
  let currentGroup = null;
  let letterIndex = 0;

  for (const ex of exercises) {
    const group = ex.superset_group;
    if (group && group === currentGroup?.key) {
      currentGroup.exercises.push(ex);
    } else if (group) {
      currentGroup = { key: group, letter: String.fromCharCode(65 + letterIndex), exercises: [ex] };
      groups.push(currentGroup);
      letterIndex++;
    } else {
      groups.push({ key: null, letter: null, exercises: [ex] });
      currentGroup = null;
    }
  }

  return (
    <div>
      {groups.map((g, gi) => (
        <div key={gi} style={g.letter ? { borderLeft: '2px solid var(--color-rose-blush)', paddingLeft: 8, marginBottom: 8 } : { marginBottom: 4 }}>
          {g.exercises.map((ex, ei) => {
            const lib = resolveExercise(ex.exercise_id, exerciseMap, slugMap);
            const exerciseObj = lib || { name: ex.name || ex.exercise_id, youtube_url: '', muscles_primary: [] };
            const isCompleted = completed[ex.exercise_id] === true;
            const label = g.letter ? `${g.letter}${ei + 1}` : null;
            const isFpm = (ex.note || '').toLowerCase().includes('elevated') || (ex.note || '').toLowerCase().includes('fpm');

            return (
              <ExerciseItem
                key={ei}
                exercise={exerciseObj}
                rx={ex.rx || ex.prescribed || ''}
                note={ex.note}
                label={label}
                completed={isCompleted}
                isFpm={isFpm}
                onToggle={onToggle ? () => onToggle(ex.exercise_id, !isCompleted) : null}
              />
            );
          })}
        </div>
      ))}
    </div>
  );
}

// ── Exercise item with three visual states ──

function ExerciseItem({ exercise, rx, note, label, completed, isFpm, onToggle }) {
  const rowStyle = {
    display: 'flex', alignItems: 'center', gap: 10, padding: '6px 4px',
    borderRadius: 8,
    opacity: completed ? 0.45 : 1,
    background: isFpm && !completed ? '#fdf8f8' : 'transparent',
  };

  const circleStyle = {
    width: 20, height: 20, borderRadius: '50%', flexShrink: 0,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: 9, fontWeight: 600, cursor: onToggle ? 'pointer' : 'default',
    border: 'none',
    ...(completed
      ? { background: 'var(--color-flag-green)', color: '#fff' }
      : isFpm
        ? { background: 'transparent', border: '1.5px solid var(--color-maroon)', color: 'var(--color-maroon)' }
        : { background: 'transparent', border: '1.5px solid var(--color-cream-subtle)', color: 'var(--color-ink-muted)' }
    ),
  };

  return (
    <div style={rowStyle}>
      {onToggle ? (
        <button onClick={onToggle} style={circleStyle}>
          {completed ? '✓' : label || '·'}
        </button>
      ) : (
        <span style={circleStyle}>{label || '·'}</span>
      )}

      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{
          fontSize: 13, margin: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          color: completed ? '#888' : 'var(--color-ink-primary)',
          textDecoration: completed ? 'line-through' : 'none',
          fontWeight: isFpm && !completed ? 600 : 400,
        }}>
          {exercise.name || 'Unknown exercise'}
        </p>
        <p style={{ fontSize: 11, color: isFpm && !completed ? 'var(--color-maroon)' : 'var(--color-ink-muted)', margin: 0 }}>
          {isFpm && !completed && <span>priority · </span>}
          {rx}
          {note && !isFpm && <span style={{ color: 'var(--color-maroon)' }}> · {note}</span>}
        </p>
      </div>

      {exercise.youtube_url && (
        <a href={exercise.youtube_url} target="_blank" rel="noopener noreferrer"
          style={{ fontSize: 11, color: 'var(--color-maroon)', flexShrink: 0, textDecoration: 'none' }}>▶</a>
      )}

      {isFpm && !completed && (
        <span style={{
          fontSize: 8, padding: '2px 6px', borderRadius: 8,
          border: '1px solid var(--color-maroon)', color: 'var(--color-maroon)',
          flexShrink: 0, fontWeight: 600, textTransform: 'uppercase',
        }}>FPM</span>
      )}
    </div>
  );
}

// ── Fallback block renderer (old format) ──

function FallbackBlock({ block, exerciseMap, slugMap, completed, onToggle }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <SectionLabel>{block.block_name}</SectionLabel>
      {block.exercises?.map((ex, i) => {
        const exercise = resolveExercise(ex.exercise_id, exerciseMap, slugMap);
        const isCompleted = completed[ex.exercise_id] === true;
        return (
          <ExerciseItem
            key={i}
            exercise={exercise || { name: ex.exercise_id, youtube_url: '', muscles_primary: [] }}
            rx={ex.prescribed}
            note={null}
            label={null}
            completed={isCompleted}
            isFpm={false}
            onToggle={onToggle ? () => onToggle(ex.exercise_id, !isCompleted) : null}
          />
        );
      })}
    </div>
  );
}

// ── Small helpers ──

function SectionLabel({ children }) {
  return (
    <p style={{
      fontSize: 8, color: 'var(--color-ink-faint)', textTransform: 'uppercase',
      letterSpacing: '0.08em', marginBottom: 6, fontWeight: 600,
    }}>
      {children}
    </p>
  );
}

function EmptyTab({ children }) {
  return <p style={{ fontSize: 12, color: 'var(--color-ink-muted)' }}>{children}</p>;
}

function PillBadge({ children }) {
  return (
    <span style={{
      fontSize: 9, background: 'var(--color-cream-bg)', color: 'var(--color-ink-muted)',
      padding: '2px 8px', borderRadius: 10,
    }}>
      {children}
    </span>
  );
}
