import { useState, useCallback } from 'react';
import { toggleExercise } from '../api';
import ExerciseWhy from './ExerciseWhy';

function resolveExercise(exerciseId, exerciseMap, slugMap) {
  if (exerciseMap[exerciseId]) return exerciseMap[exerciseId];
  const resolvedId = slugMap[exerciseId];
  if (resolvedId && exerciseMap[resolvedId]) return exerciseMap[resolvedId];
  return null;
}

const BLOCKS = [
  { key: 'arm_care', emoji: '\uD83D\uDCAA', label: 'Arm Care' },
  { key: 'lifting', emoji: '\uD83C\uDFCB\uFE0F', label: 'Lifting' },
  { key: 'throwing', emoji: '\u26BE', label: 'Throwing' },
];

export default function DailyCard({ entry, exerciseMap = {}, slugMap = {}, pitcherId, initData, readOnly = false }) {
  const rawCE = entry?.completed_exercises;
  const [completed, setCompleted] = useState((rawCE && !Array.isArray(rawCE)) ? rawCE : {});
  const [expandedWhy, setExpandedWhy] = useState({});

  const handleToggle = useCallback((exerciseId, newState) => {
    if (readOnly) return;
    setCompleted(prev => ({ ...prev, [exerciseId]: newState }));
    toggleExercise(pitcherId, entry?.date, exerciseId, newState, initData)
      .catch(() => setCompleted(prev => ({ ...prev, [exerciseId]: !newState })));
  }, [pitcherId, entry?.date, initData, readOnly]);

  const toggleWhy = useCallback((exerciseId) => {
    setExpandedWhy(prev => ({ ...prev, [exerciseId]: !prev[exerciseId] }));
  }, []);

  if (!entry) {
    return (
      <div style={{ background: 'var(--color-white)', borderRadius: 12, padding: 16 }}>
        <p style={{ color: 'var(--color-ink-muted)', fontSize: 13 }}>No training data for today</p>
      </div>
    );
  }

  const { plan_generated } = entry;
  const blockData = {
    arm_care: entry.arm_care || plan_generated?.arm_care,
    lifting: entry.lifting || plan_generated?.lifting,
    throwing: entry.throwing || plan_generated?.throwing,
  };
  const rawNotes = entry.notes || plan_generated?.notes;
  const notes = Array.isArray(rawNotes) ? rawNotes : [];
  const hasStructured = !!(blockData.arm_care?.exercises?.length || blockData.lifting?.exercises?.length);
  const fallbackBlocks = plan_generated?.exercise_blocks || [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {BLOCKS.map(({ key, emoji, label }) => {
        const data = blockData[key];
        if (key === 'throwing') {
          return (
            <ThrowingBlock
              key={key}
              emoji={emoji}
              label={label}
              throwing={data}
              fallbackPlan={plan_generated?.throwing_plan}
            />
          );
        }
        return (
          <ExerciseBlock
            key={key}
            blockKey={key}
            emoji={emoji}
            label={label}
            data={data}
            fallbackBlocks={fallbackBlocks}
            hasStructured={hasStructured}
            exerciseMap={exerciseMap}
            slugMap={slugMap}
            completed={completed}
            onToggle={readOnly ? null : handleToggle}
            expandedWhy={expandedWhy}
            onToggleWhy={toggleWhy}
          />
        );
      })}

      {notes.length > 0 && <NotesBlock notes={notes} />}

      {entry.outing && (
        <div style={{ background: 'var(--color-white)', borderRadius: 12, padding: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
            <span style={{ fontSize: 14 }}>{'\uD83D\uDCCA'}</span>
            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-ink-primary)' }}>Outing</span>
          </div>
          <p style={{ fontSize: 13, color: 'var(--color-ink-primary)', margin: 0 }}>
            {entry.outing.pitch_count} pitches · Post feel: {entry.outing.arm_feel ?? entry.outing.post_arm_feel}/5
          </p>
          {entry.outing.notes && (
            <p style={{ fontSize: 11, color: 'var(--color-ink-muted)', marginTop: 4, margin: '4px 0 0' }}>
              {Array.isArray(entry.outing.notes) ? entry.outing.notes.join('; ') : String(entry.outing.notes)}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Exercise Block (arm_care, lifting) ──

function ExerciseBlock({ blockKey, emoji, label, data, fallbackBlocks, hasStructured, exerciseMap, slugMap, completed, onToggle, expandedWhy, onToggleWhy }) {
  const exercises = data?.exercises || [];
  const hasDirect = hasStructured && exercises.length > 0;

  // Resolve fallback exercises for this block
  let fallbackExercises = [];
  if (!hasDirect) {
    const isArm = blockKey === 'arm_care';
    const filtered = fallbackBlocks.filter(b => {
      const name = b.block_name?.toLowerCase() || '';
      return isArm ? name.includes('arm') : (!name.includes('arm') && !name.includes('plyo'));
    });
    fallbackExercises = filtered.flatMap(b => b.exercises || []);
  }

  const allEx = hasDirect ? exercises : fallbackExercises;
  if (allEx.length === 0) return null;

  const doneCount = allEx.filter(ex => completed[ex.exercise_id] === true).length;
  const subtitle = data?.intent || data?.timing || data?.type || '';
  const duration = data?.estimated_duration_min;
  const reasoning = data?.reasoning;

  return (
    <div style={{ background: 'var(--color-white)', borderRadius: 12, overflow: 'hidden' }}>
      {/* Block header */}
      <div style={{ padding: '10px 14px', borderBottom: '0.5px solid var(--color-cream-border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 14 }}>{emoji}</span>
            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-ink-primary)' }}>{label}</span>
            {subtitle && <span style={{ fontSize: 11, color: 'var(--color-ink-muted)' }}>{'\u2014 '}{subtitle}</span>}
            {duration && <span style={{ fontSize: 10, color: 'var(--color-ink-faint)' }}>{duration} min</span>}
          </div>
          <span style={{ fontSize: 11, color: doneCount === allEx.length && allEx.length > 0 ? 'var(--color-flag-green)' : 'var(--color-ink-muted)', fontWeight: 600 }}>
            {doneCount}/{allEx.length}
          </span>
        </div>
        {reasoning && typeof reasoning === 'string' && (
          <p style={{ fontSize: 11, color: 'var(--color-ink-muted)', fontStyle: 'italic', lineHeight: 1.5, margin: '4px 0 0' }}>
            {reasoning}
          </p>
        )}
      </div>

      {/* Exercise list */}
      <div style={{ padding: '6px 14px 10px' }}>
        <SupersetList
          exercises={allEx}
          exerciseMap={exerciseMap}
          slugMap={slugMap}
          completed={completed}
          onToggle={onToggle}
          expandedWhy={expandedWhy}
          onToggleWhy={onToggleWhy}
        />
      </div>
    </div>
  );
}

// ── Throwing Block ──

function ThrowingBlock({ emoji, label, throwing, fallbackPlan }) {
  const data = throwing || fallbackPlan;
  if (!data) return null;
  const type = data.type || data.details || 'none';
  const detail = data.detail || data.details || '';
  const intent = data.intent;
  const duration = data.estimated_duration_min;
  if (type === 'none' && !detail) return null;

  return (
    <div style={{ background: 'var(--color-white)', borderRadius: 12, overflow: 'hidden' }}>
      <div style={{ padding: '10px 14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 14 }}>{emoji}</span>
            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-ink-primary)' }}>{label}</span>
            {duration && <span style={{ fontSize: 11, color: 'var(--color-ink-muted)' }}>{'\u2014 '}{duration} min</span>}
          </div>
          {intent && <PillBadge>{intent}</PillBadge>}
        </div>
        <p style={{ fontSize: 13, color: 'var(--color-ink-secondary)', marginTop: 6, margin: '6px 0 0', textTransform: 'capitalize' }}>
          {type.replace(/_/g, ' ')}
        </p>
        {detail && detail !== type && (
          <p style={{ fontSize: 12, color: 'var(--color-ink-muted)', margin: '4px 0 0', lineHeight: 1.5 }}>{detail}</p>
        )}
      </div>
    </div>
  );
}

// ── Notes Block ──

function NotesBlock({ notes }) {
  return (
    <div style={{ background: 'var(--color-white)', borderRadius: 12, padding: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
        <span style={{ fontSize: 14 }}>{'\uD83D\uDCDD'}</span>
        <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-ink-primary)' }}>Notes</span>
      </div>
      <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
        {notes.map((note, i) => (
          <li key={i} style={{ display: 'flex', gap: 8, fontSize: 12, color: 'var(--color-ink-secondary)', marginBottom: 6 }}>
            <span style={{ color: 'var(--color-ink-muted)', flexShrink: 0 }}>{'\u00B7'}</span>
            <span>{typeof note === 'string' ? note : JSON.stringify(note)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ── Superset renderer ──

function SupersetList({ exercises, exerciseMap, slugMap, completed, onToggle, expandedWhy, onToggleWhy }) {
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
            const exerciseObj = lib || { name: ex.name || ex.exercise_id, youtube_url: '', muscles_primary: [], pitching_relevance: '' };
            const isCompleted = completed[ex.exercise_id] === true;
            const label = g.letter ? `${g.letter}${ei + 1}` : null;
            const noteStr = typeof ex.note === 'string' ? ex.note : '';
            const isFpm = noteStr.toLowerCase().includes('elevated') || noteStr.toLowerCase().includes('fpm');
            const rawWhy = ex.why || exerciseObj.pitching_relevance || '';
            const why = typeof rawWhy === 'string' ? rawWhy : '';

            return (
              <ExerciseItem
                key={ei}
                exerciseId={ex.exercise_id}
                exercise={exerciseObj}
                rx={ex.rx || ex.prescribed || ''}
                prescription={ex.prescription || ''}
                note={noteStr}
                label={label}
                completed={isCompleted}
                isFpm={isFpm}
                why={why}
                whyExpanded={!!expandedWhy[ex.exercise_id]}
                onToggle={onToggle ? () => onToggle(ex.exercise_id, !isCompleted) : null}
                onToggleWhy={() => onToggleWhy(ex.exercise_id)}
              />
            );
          })}
        </div>
      ))}
    </div>
  );
}

// ── Exercise item ──

function ExerciseItem({ exerciseId, exercise, rx, prescription, note: rawNote, label, completed, isFpm, why, whyExpanded, onToggle, onToggleWhy }) {
  const note = typeof rawNote === 'string' ? rawNote : '';
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

  const fullRx = rx || prescription;

  return (
    <div>
      <div style={rowStyle}>
        {onToggle ? (
          <button onClick={onToggle} style={circleStyle}>
            {completed ? '\u2713' : label || '\u00B7'}
          </button>
        ) : (
          <span style={circleStyle}>{label || '\u00B7'}</span>
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
          <div style={{ fontSize: 11, color: isFpm && !completed ? 'var(--color-maroon)' : 'var(--color-ink-muted)', marginTop: 2 }}>
            {isFpm && !completed && <span>{'priority \u00B7 '}</span>}
            {fullRx}
            {note && !isFpm && <span style={{ color: 'var(--color-maroon)' }}>{' \u00B7 '}{note}</span>}
          </div>
        </div>

        {why && !completed && (
          <button
            onClick={onToggleWhy}
            style={{
              width: 20, height: 20, borderRadius: '50%', flexShrink: 0,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 10, cursor: 'pointer', border: 'none',
              background: whyExpanded ? 'var(--color-rose-blush)' : 'var(--color-cream-bg)',
              color: whyExpanded ? '#fff' : 'var(--color-ink-muted)',
            }}
          >
            i
          </button>
        )}

        {exercise.youtube_url && (
          <a href={exercise.youtube_url} target="_blank" rel="noopener noreferrer"
            style={{ fontSize: 11, color: 'var(--color-maroon)', flexShrink: 0, textDecoration: 'none' }}>{'\u25B6'}</a>
        )}

        {isFpm && !completed && (
          <span style={{
            fontSize: 8, padding: '2px 6px', borderRadius: 8,
            border: '1px solid var(--color-maroon)', color: 'var(--color-maroon)',
            flexShrink: 0, fontWeight: 600, textTransform: 'uppercase',
          }}>FPM</span>
        )}
      </div>

      <ExerciseWhy why={why} expanded={whyExpanded} />
    </div>
  );
}

// ── Small helpers ──

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
