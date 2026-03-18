import { useState, useCallback } from 'react';
import FlagBadge from './FlagBadge';
import { toggleExercise } from '../api';

const TABS = ['Arm care', 'Lifting', 'Throwing', 'Notes'];

function resolveExercise(exerciseId, exerciseMap, slugMap) {
  if (exerciseMap[exerciseId]) return exerciseMap[exerciseId];
  const resolvedId = slugMap[exerciseId];
  if (resolvedId && exerciseMap[resolvedId]) return exerciseMap[resolvedId];
  return null;
}

export default function DailyCard({ entry, exerciseMap = {}, slugMap = {}, pitcherId, initData }) {
  const [tab, setTab] = useState(0);
  const [completed, setCompleted] = useState(entry?.completed_exercises || {});

  const handleToggle = useCallback((exerciseId, newState) => {
    setCompleted(prev => ({ ...prev, [exerciseId]: newState }));
    toggleExercise(pitcherId, entry?.date, exerciseId, newState, initData)
      .catch(() => setCompleted(prev => ({ ...prev, [exerciseId]: !newState })));
  }, [pitcherId, entry?.date, initData]);

  if (!entry) {
    return (
      <div className="bg-bg-secondary rounded-xl p-4">
        <p className="text-text-muted text-sm">No training data for today</p>
      </div>
    );
  }

  const { pre_training, plan_generated } = entry;
  const flagLevel = pre_training?.flag_level || 'green';

  // New structured fields (from structured JSON plan generator)
  const morningBrief = entry.morning_brief || plan_generated?.morning_brief;
  const armCare = entry.arm_care || plan_generated?.arm_care;
  const lifting = entry.lifting || plan_generated?.lifting;
  const throwing = entry.throwing || plan_generated?.throwing;
  const notes = entry.notes || plan_generated?.notes || [];

  // Fallback: old exercise_blocks format
  const hasStructured = !!(armCare?.exercises?.length || lifting?.exercises?.length);
  const fallbackBlocks = plan_generated?.exercise_blocks || [];
  const fallbackNarrative = !hasStructured ? (entry.plan_narrative || plan_generated?.narrative) : null;

  // Determine which tabs have content
  const tabContent = [
    armCare?.exercises?.length > 0 || (!hasStructured && fallbackBlocks.some(b => b.block_name?.toLowerCase().includes('arm'))),
    lifting?.exercises?.length > 0 || (!hasStructured && fallbackBlocks.some(b => !b.block_name?.toLowerCase().includes('arm') && !b.block_name?.toLowerCase().includes('plyo'))),
    !!(throwing?.detail || throwing?.details || plan_generated?.throwing_plan),
    notes.length > 0,
  ];

  return (
    <div className="bg-bg-secondary rounded-xl overflow-hidden">
      {/* Morning brief */}
      {morningBrief && (
        <div className="px-4 pt-4 pb-2">
          <p className="text-sm text-text-primary leading-relaxed">{morningBrief}</p>
        </div>
      )}

      {/* Status pills */}
      <div className="px-4 pb-2 flex items-center gap-2 flex-wrap">
        <FlagBadge level={flagLevel} />
        {pre_training?.arm_feel != null && (
          <Pill>Arm {pre_training.arm_feel}/5</Pill>
        )}
        {pre_training?.sleep_hours != null && (
          <Pill>Sleep {pre_training.sleep_hours}h</Pill>
        )}
        {lifting?.estimated_duration_min && (
          <Pill>~{lifting.estimated_duration_min} min</Pill>
        )}
      </div>

      {/* Fallback narrative (old format only) */}
      {fallbackNarrative && !morningBrief && (
        <div className="px-4 pb-2">
          <div className="bg-bg-primary rounded-lg p-3 border-l-[3px] border-accent-blue">
            <p className="text-sm text-text-primary leading-relaxed whitespace-pre-line">{fallbackNarrative}</p>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-bg-tertiary">
        {TABS.map((t, i) => (
          <button
            key={t}
            onClick={() => setTab(i)}
            className={`flex-1 py-2 text-xs font-medium transition-colors ${
              tab === i
                ? 'text-accent-blue border-b-2 border-accent-blue'
                : tabContent[i]
                  ? 'text-text-secondary'
                  : 'text-text-muted/40'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="p-4">
        {tab === 0 && (
          <TabArmCare
            armCare={armCare}
            fallbackBlocks={fallbackBlocks}
            hasStructured={hasStructured}
            exerciseMap={exerciseMap}
            slugMap={slugMap}
            completed={completed}
            onToggle={handleToggle}
          />
        )}
        {tab === 1 && (
          <TabLifting
            lifting={lifting}
            fallbackBlocks={fallbackBlocks}
            hasStructured={hasStructured}
            exerciseMap={exerciseMap}
            slugMap={slugMap}
            completed={completed}
            onToggle={handleToggle}
          />
        )}
        {tab === 2 && (
          <TabThrowing
            throwing={throwing}
            fallbackPlan={plan_generated?.throwing_plan}
          />
        )}
        {tab === 3 && <TabNotes notes={notes} />}
      </div>

      {/* Outing data */}
      {entry.outing && (
        <div className="px-4 pb-4">
          <div className="bg-bg-tertiary rounded-lg p-3">
            <p className="text-xs text-accent-blue font-medium">Outing</p>
            <p className="text-sm text-text-primary">
              {entry.outing.pitch_count} pitches · Post feel: {entry.outing.arm_feel ?? entry.outing.post_arm_feel}/5
            </p>
            {entry.outing.notes && <p className="text-xs text-text-muted mt-1">{entry.outing.notes}</p>}
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
        {armCare.timing && (
          <p className="text-[10px] text-text-muted uppercase mb-2">{armCare.timing}</p>
        )}
        <SupersetList exercises={armCare.exercises} exerciseMap={exerciseMap} slugMap={slugMap} completed={completed} onToggle={onToggle} />
      </div>
    );
  }
  // Fallback: arm care blocks from old format
  const armBlocks = fallbackBlocks.filter(b => b.block_name?.toLowerCase().includes('arm'));
  if (armBlocks.length) {
    return armBlocks.map((block, i) => (
      <FallbackBlock key={i} block={block} exerciseMap={exerciseMap} slugMap={slugMap} completed={completed} onToggle={onToggle} />
    ));
  }
  return <p className="text-xs text-text-muted">No arm care prescribed today</p>;
}

function TabLifting({ lifting, fallbackBlocks, hasStructured, exerciseMap, slugMap, completed, onToggle }) {
  if (hasStructured && lifting?.exercises?.length) {
    return (
      <div>
        {lifting.intent && (
          <p className="text-[10px] text-text-muted uppercase mb-2">{lifting.intent}</p>
        )}
        <SupersetList exercises={lifting.exercises} exerciseMap={exerciseMap} slugMap={slugMap} completed={completed} onToggle={onToggle} />
      </div>
    );
  }
  // Fallback: non-arm-care blocks
  const liftBlocks = fallbackBlocks.filter(b => !b.block_name?.toLowerCase().includes('arm') && !b.block_name?.toLowerCase().includes('plyo'));
  if (liftBlocks.length) {
    return liftBlocks.map((block, i) => (
      <FallbackBlock key={i} block={block} exerciseMap={exerciseMap} slugMap={slugMap} completed={completed} onToggle={onToggle} />
    ));
  }
  return <p className="text-xs text-text-muted">No lifting prescribed today</p>;
}

function TabThrowing({ throwing, fallbackPlan }) {
  const data = throwing || fallbackPlan;
  if (!data) return <p className="text-xs text-text-muted">No throwing today</p>;

  const type = data.type || data.details || 'none';
  const detail = data.detail || data.details || '';
  const intent = data.intent;

  if (type === 'none' && !detail) {
    return <p className="text-xs text-text-muted">No throwing today — rest/recovery</p>;
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium text-text-primary capitalize">{type.replace(/_/g, ' ')}</span>
        {intent && <Pill>{intent}</Pill>}
      </div>
      {detail && <p className="text-sm text-text-secondary">{detail}</p>}
    </div>
  );
}

function TabNotes({ notes }) {
  if (!notes?.length) return <p className="text-xs text-text-muted">No notes for today</p>;
  return (
    <ul className="space-y-2">
      {notes.map((note, i) => (
        <li key={i} className="flex gap-2 text-sm text-text-secondary">
          <span className="text-text-muted flex-shrink-0">·</span>
          <span>{note}</span>
        </li>
      ))}
    </ul>
  );
}

// ── Superset renderer ──

function SupersetList({ exercises, exerciseMap, slugMap, completed, onToggle }) {
  // Group by superset_group
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
    <div className="space-y-1">
      {groups.map((g, gi) => (
        <div key={gi} className={g.letter ? 'border-l-2 border-accent-blue/30 pl-2 mb-2' : 'mb-1'}>
          {g.exercises.map((ex, ei) => {
            const lib = resolveExercise(ex.exercise_id, exerciseMap, slugMap);
            const exerciseObj = lib || { name: ex.name || ex.exercise_id, youtube_url: '', muscles_primary: [] };
            const isCompleted = completed[ex.exercise_id] === true;
            const label = g.letter ? `${g.letter}${ei + 1}` : null;

            return (
              <div key={ei} className="flex items-center gap-2 py-1">
                {/* Superset label or checkbox */}
                {onToggle ? (
                  <button onClick={() => onToggle(ex.exercise_id, !isCompleted)}
                    className={`w-6 h-5 rounded-md border-[1.5px] flex-shrink-0 flex items-center justify-center text-[9px] font-medium transition-colors ${
                      isCompleted
                        ? 'border-accent-blue bg-accent-blue/10 text-accent-blue'
                        : 'border-bg-tertiary text-text-muted'
                    }`}>
                    {isCompleted ? '✓' : label || '·'}
                  </button>
                ) : (
                  <span className="text-[10px] text-text-muted w-6 text-center flex-shrink-0">{label}</span>
                )}

                {/* Exercise info */}
                <div className="flex-1 min-w-0">
                  <p className={`text-sm truncate ${isCompleted ? 'text-text-muted line-through' : 'text-text-primary'}`}>
                    {exerciseObj.name}
                  </p>
                  <p className="text-[11px] text-text-muted truncate">
                    {ex.rx || ex.prescribed || ''}
                    {ex.note && <span className="text-accent-blue"> · {ex.note}</span>}
                  </p>
                </div>

                {/* Video */}
                {exerciseObj.youtube_url && (
                  <a href={exerciseObj.youtube_url} target="_blank" rel="noopener noreferrer"
                    className="text-[11px] text-accent-blue flex-shrink-0">▶</a>
                )}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

// ── Fallback block renderer (old format) ──

function FallbackBlock({ block, exerciseMap, slugMap, completed, onToggle }) {
  return (
    <div className="mb-2">
      <p className="text-[10px] font-medium text-text-secondary uppercase tracking-wider mb-1">{block.block_name}</p>
      {block.exercises?.map((ex, i) => {
        const exercise = resolveExercise(ex.exercise_id, exerciseMap, slugMap);
        const isCompleted = completed[ex.exercise_id] === true;
        return (
          <div key={i} className="flex items-center gap-3 py-1">
            {onToggle && (
              <button onClick={() => onToggle(ex.exercise_id, !isCompleted)}
                className={`w-5 h-5 rounded-md border-[1.5px] flex-shrink-0 flex items-center justify-center transition-colors ${
                  isCompleted ? 'border-accent-blue bg-accent-blue/10 text-accent-blue' : 'border-bg-tertiary'
                }`}>
                {isCompleted && <span className="text-[10px]">✓</span>}
              </button>
            )}
            <div className="flex-1 min-w-0">
              <p className={`text-sm truncate ${isCompleted ? 'text-text-muted line-through' : 'text-text-primary'}`}>
                {exercise?.name || ex.exercise_id}
              </p>
              <p className="text-[11px] text-text-muted">{ex.prescribed}</p>
            </div>
            {exercise?.youtube_url && (
              <a href={exercise.youtube_url} target="_blank" rel="noopener noreferrer"
                className="text-[11px] text-accent-blue flex-shrink-0">▶</a>
            )}
          </div>
        );
      })}
    </div>
  );
}

function Pill({ children }) {
  return (
    <span className="text-[10px] bg-bg-tertiary text-text-muted px-2 py-0.5 rounded-full">
      {children}
    </span>
  );
}
