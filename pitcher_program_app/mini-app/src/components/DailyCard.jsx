import { useState, useCallback, useEffect, useMemo } from 'react';
import { toggleExercise } from '../api';
import { useToast } from '../hooks/useToast';
import ExerciseWhy from './ExerciseWhy';
import { BallDots, BallColorLegend } from './BallDots';
import WhyCard from './WhyCard';
import PostThrowFeel from './PostThrowFeel';
import MobilityCard from './MobilityCard';
import ExerciseSwap from './ExerciseSwap';
import { submitThrowFeel } from '../api';

function resolveExercise(exerciseId, exerciseMap, slugMap) {
  if (exerciseMap[exerciseId]) return exerciseMap[exerciseId];
  const resolvedId = slugMap[exerciseId];
  if (resolvedId && exerciseMap[resolvedId]) return exerciseMap[resolvedId];
  return null;
}

const BLOCKS = [
  { key: 'warmup', emoji: '\uD83D\uDD25', label: 'Dynamic Warmup' },
  { key: 'arm_care', emoji: '\uD83D\uDCAA', label: 'Arm Care' },
  { key: 'lifting', emoji: '\uD83C\uDFCB\uFE0F', label: 'Lifting' },
  { key: 'throwing', emoji: '\u26BE', label: 'Throwing' },
];

// ---------------------------------------------------------------------------
// Guided day flow — phase model
// ---------------------------------------------------------------------------

// Short label + emoji + human label for each phase. Shared between the
// BLOCKS rendering chain and the guided-flow visual states.
const PHASE_DEFS = {
  warmup:   { id: 'warmup',   label: 'Warmup' },
  arm_care: { id: 'arm_care', label: 'Arm Care' },
  lifting:  { id: 'lifting',  label: 'Lifting' },
  throwing: { id: 'throwing', label: 'Throwing' },
  mobility: { id: 'mobility', label: 'Mobility' },
};

/**
 * Returns an ordered array of phase IDs for this entry.
 * Skips phases with no content. Respects arm_care.timing ("pre_throw" | "pre_lift").
 * 5-phase model: warmup, arm_care, lifting, throwing (includes nested post-throw), mobility.
 */
function computePhaseOrder(entry, mobilityData) {
  if (!entry) return [];

  const warmupData = entry.warmup || entry.plan_generated?.warmup;
  const armCareData = entry.arm_care || entry.plan_generated?.arm_care || {};
  const liftingData = entry.lifting || entry.plan_generated?.lifting;
  const liftingBlocks = entry.plan_generated?.exercise_blocks || [];
  const throwingData = entry.throwing || entry.plan_generated?.throwing;

  const hasWarmup = !!(warmupData && (
    (Array.isArray(warmupData.blocks) && warmupData.blocks.some(b => b.exercises?.length > 0)) ||
    (Array.isArray(warmupData.exercises) && warmupData.exercises.length > 0)
  ));

  const hasArmCare = !!(
    (Array.isArray(armCareData.exercises) && armCareData.exercises.length > 0) ||
    liftingBlocks.some(b => (b.block_name || '').toLowerCase().includes('arm'))
  );
  const armCareTiming = armCareData.timing || 'pre_lift';

  const hasLifting = !!(
    (liftingData?.exercises?.length > 0) ||
    liftingBlocks.some(b => !(b.block_name || '').toLowerCase().includes('arm') && (b.exercises || []).length > 0)
  );

  const throwingType = throwingData?.type;
  const hasThrowing = throwingType && throwingType !== 'none' && throwingType !== 'no_throw';

  const hasMobility = !!(mobilityData && (
    (Array.isArray(mobilityData.videos) && mobilityData.videos.length > 0) ||
    mobilityData.video_id
  ));

  const order = [];
  if (hasWarmup) order.push('warmup');

  // Arm care timing dictates whether it comes before throwing or before lifting
  if (armCareTiming === 'pre_throw' && hasThrowing) {
    if (hasArmCare) order.push('arm_care');
    order.push('throwing');
    if (hasLifting) order.push('lifting');
  } else {
    if (hasArmCare) order.push('arm_care');
    if (hasLifting) order.push('lifting');
    if (hasThrowing) order.push('throwing');
  }

  if (hasMobility) order.push('mobility');
  return order;
}

/**
 * Returns an array of item completion keys for the phase, used to check
 * against entry.completed_exercises. Empty array means "no items to track."
 * Throwing rolls up ALL exercises across ALL phases including nested post-throw recovery.
 */
function getPhaseItems(phaseId, entry) {
  if (!entry) return [];
  const plan = entry.plan_generated || {};

  if (phaseId === 'warmup') {
    const warmup = entry.warmup || plan.warmup;
    const blocks = warmup?.blocks || [];
    return blocks.flatMap(b => (b.exercises || []).map(ex => ex.exercise_id || ex.name)).filter(Boolean);
  }

  if (phaseId === 'arm_care') {
    const armCare = entry.arm_care || plan.arm_care;
    const directExs = armCare?.exercises || [];
    if (directExs.length > 0) {
      return directExs.map(ex => ex.exercise_id || ex.name).filter(Boolean);
    }
    // Fallback: arm care blocks from plan_generated.exercise_blocks
    const armBlocks = (plan.exercise_blocks || [])
      .filter(b => (b.block_name || '').toLowerCase().includes('arm'));
    return armBlocks.flatMap(b => (b.exercises || []).map(ex => ex.exercise_id || ex.name)).filter(Boolean);
  }

  if (phaseId === 'lifting') {
    // Dual source per CLAUDE.md "DailyCard Rendering — Dual Data Sources"
    const lifting = entry.lifting || plan.lifting;
    const directExs = lifting?.exercises || [];
    if (directExs.length > 0) {
      return directExs.map(ex => ex.exercise_id || ex.name).filter(Boolean);
    }
    // Fallback to exercise_blocks, excluding arm care
    const liftBlocks = (plan.exercise_blocks || [])
      .filter(b => !(b.block_name || '').toLowerCase().includes('arm'));
    return liftBlocks.flatMap(b => (b.exercises || []).map(ex => ex.exercise_id || ex.name)).filter(Boolean);
  }

  if (phaseId === 'throwing') {
    const throwing = entry.throwing || plan.throwing || plan.throwing_plan;
    const phases = throwing?.phases || [];
    // Rolls up all throwing phase exercises (includes post-throw recovery)
    return phases.flatMap(p =>
      (p.exercises || []).map(ex => ex.exercise_id || ex.name || ex.drill)
    ).filter(Boolean);
  }

  if (phaseId === 'mobility') return []; // terminal, no items to track

  return [];
}

/**
 * Returns true if the phase should be considered complete for guided-flow purposes.
 * - Mobility is always "complete" (terminal, optional)
 * - Empty phases (no items) are complete
 * - Manually-marked-done phases (via button) are complete
 * - Otherwise, all items must be in completed_exercises with true
 */
function isPhaseComplete(phaseId, entry, completed, manuallyDone) {
  if (phaseId === 'mobility') return true;
  if (manuallyDone && manuallyDone.has(phaseId)) return true;
  const items = getPhaseItems(phaseId, entry);
  if (items.length === 0) return true;
  const completedMap = completed || {};
  return items.every(itemKey => completedMap[itemKey] === true);
}

function ResearchWhySheet({ researchSources, onClose }) {
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const apiUrl = import.meta.env.VITE_API_URL;

  useEffect(() => {
    if (!researchSources?.length) {
      setLoading(false);
      return;
    }
    fetch(`${apiUrl}/api/research/docs?ids=${researchSources.join(',')}`)
      .then(r => r.json())
      .then(data => { setDocs(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [researchSources, apiUrl]);

  if (loading) return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 50,
      display: 'flex', alignItems: 'flex-end', justifyContent: 'center',
      backgroundColor: 'rgba(0,0,0,0.4)'
    }} onClick={onClose}>
      <div style={{
        width: '100%', maxWidth: 480, borderRadius: '16px 16px 0 0',
        backgroundColor: '#fff', padding: '20px 20px 32px'
      }} onClick={e => e.stopPropagation()}>
        <p style={{ textAlign: 'center', color: '#9ca3af' }}>Loading...</p>
      </div>
    </div>
  );

  if (!docs.length) return null;

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 50,
      display: 'flex', alignItems: 'flex-end', justifyContent: 'center',
      backgroundColor: 'rgba(0,0,0,0.4)'
    }} onClick={onClose}>
      <div style={{
        width: '100%', maxWidth: 480, borderRadius: '16px 16px 0 0',
        backgroundColor: '#fff', padding: '20px 20px 32px'
      }} onClick={e => e.stopPropagation()}>
        <div style={{
          width: 40, height: 4, borderRadius: 2,
          backgroundColor: '#d1d5db', margin: '0 auto 16px'
        }} />
        <h3 style={{ fontSize: 18, fontWeight: 600, color: '#111827', marginBottom: 12 }}>
          Why today looks different
        </h3>
        <p style={{ fontSize: 14, color: '#6b7280', marginBottom: 16 }}>
          Your plan is informed by:
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {docs.map(doc => (
            <div key={doc.id} style={{
              borderRadius: 8, border: '1px solid #e5e7eb', padding: 12
            }}>
              <p style={{ fontWeight: 500, color: '#1f2937' }}>{doc.title}</p>
              <p style={{ fontSize: 14, color: '#6b7280', marginTop: 4 }}>{doc.summary}</p>
            </div>
          ))}
        </div>
        <button
          onClick={onClose}
          style={{
            marginTop: 16, width: '100%', borderRadius: 8,
            backgroundColor: '#800000', color: '#fff',
            padding: '10px 0', fontSize: 14, fontWeight: 500,
            border: 'none', cursor: 'pointer'
          }}
        >
          Got it
        </button>
      </div>
    </div>
  );
}

export default function DailyCard({ entry, exerciseMap = {}, slugMap = {}, pitcherId, initData, readOnly = false }) {
  const { showToast } = useToast();
  const rawCE = entry?.completed_exercises;
  const [completed, setCompleted] = useState((rawCE && !Array.isArray(rawCE)) ? rawCE : {});
  const [expandedWhy, setExpandedWhy] = useState({});
  const [collapsedPhases, setCollapsedPhases] = useState({});
  const [showWhySheet, setShowWhySheet] = useState(false);

  const researchSources = entry?.plan_generated?.research_sources || entry?.research_sources || [];

  const handleToggle = useCallback((exerciseId, newState) => {
    if (readOnly) return;
    setCompleted(prev => ({ ...prev, [exerciseId]: newState }));
    toggleExercise(pitcherId, entry?.date, exerciseId, newState, initData)
      .catch(() => {
        setCompleted(prev => ({ ...prev, [exerciseId]: !newState }));
        showToast('Failed to save exercise', 'error');
      });
  }, [pitcherId, entry?.date, initData, readOnly, showToast]);

  const toggleWhy = useCallback((exerciseId) => {
    setExpandedWhy(prev => ({ ...prev, [exerciseId]: !prev[exerciseId] }));
  }, []);

  // Guided flow state (ephemeral, resets on reload)
  const [manuallyDonePhases, setManuallyDonePhases] = useState(() => new Set());
  const [expandedCompletedPhases, setExpandedCompletedPhases] = useState(() => new Set());

  const handleMarkPhaseDone = useCallback((phaseId) => {
    setManuallyDonePhases(prev => {
      const next = new Set(prev);
      next.add(phaseId);
      return next;
    });
  }, []);

  const handleToggleCompletedPhaseExpand = useCallback((phaseId) => {
    setExpandedCompletedPhases(prev => {
      const next = new Set(prev);
      if (next.has(phaseId)) next.delete(phaseId);
      else next.add(phaseId);
      return next;
    });
  }, []);

  // Swap state (lifting block only)
  const [swappingExerciseId, setSwappingExerciseId] = useState(null);
  const [swappedExercises, setSwappedExercises] = useState({});

  // Local overrides for swapped exercises — maps old exercise_id → new exercise data
  const [swapOverrides, setSwapOverrides] = useState({});

  const handleSwapComplete = useCallback((oldExId, newExercise) => {
    // Store the override so rendering uses the new exercise data
    setSwapOverrides(prev => ({
      ...prev,
      [oldExId]: newExercise,
    }));
    setSwappedExercises(prev => ({
      ...prev,
      [newExercise.exercise_id]: { swapped_from_name: newExercise.swapped_from_name },
    }));
    setSwappingExerciseId(null);
    showToast('Exercise swapped', 'success');
  }, [showToast]);

  if (!entry) {
    return (
      <div style={{ background: 'var(--color-white)', borderRadius: 12, padding: 16 }}>
        <p style={{ color: 'var(--color-ink-muted)', fontSize: 13 }}>No training data for today</p>
      </div>
    );
  }

  const { plan_generated } = entry;
  // Prefer structured throwing_plan (with phases) over flat entry.throwing
  const resolveThrowingData = () => {
    const tp = plan_generated?.throwing_plan;
    if (tp && Array.isArray(tp.phases) && tp.phases.some(p => p.exercises?.length > 0)) return tp;
    const et = entry.throwing;
    if (et && Array.isArray(et.phases) && et.phases.some(p => p.exercises?.length > 0)) return et;
    return et || plan_generated?.throwing;
  };
  const blockData = {
    warmup: entry.warmup || plan_generated?.warmup,
    arm_care: entry.arm_care || plan_generated?.arm_care,
    lifting: entry.lifting || plan_generated?.lifting,
    throwing: resolveThrowingData(),
  };
  const mobilityData = entry.mobility || plan_generated?.mobility;

  const [fetchedMobility, setFetchedMobility] = useState(null);

  useEffect(() => {
    if (!mobilityData && pitcherId) {
      const apiBase = import.meta.env.VITE_API_URL || '';
      fetch(`${apiBase}/api/pitcher/${pitcherId}/mobility-today`)
        .then(r => r.ok ? r.json() : null)
        .then(data => { if (data) setFetchedMobility(data); })
        .catch(() => {});
    }
  }, [mobilityData, pitcherId]);

  const activeMobility = mobilityData || fetchedMobility;

  const rawNotes = entry.notes || plan_generated?.notes;
  const notes = Array.isArray(rawNotes) ? rawNotes : [];
  const hasStructured = !!(blockData.arm_care?.exercises?.length || blockData.lifting?.exercises?.length);
  const fallbackBlocks = plan_generated?.exercise_blocks || [];

  // Guided flow: compute phase order + active phase from entry state
  const phaseOrder = useMemo(
    () => computePhaseOrder(entry, activeMobility),
    [entry, activeMobility]
  );
  const activePhaseId = useMemo(() => {
    for (const pid of phaseOrder) {
      if (!isPhaseComplete(pid, entry, completed, manuallyDonePhases)) return pid;
    }
    // All phases complete — return the last one so no "active" state is shown
    return null;
  }, [phaseOrder, entry, completed, manuallyDonePhases]);

  const phaseStateFor = (phaseId) => {
    if (isPhaseComplete(phaseId, entry, completed, manuallyDonePhases)) return 'complete';
    if (phaseId === activePhaseId) return 'active';
    return 'locked';
  };

  const prevPhaseLabelFor = (phaseId) => {
    const idx = phaseOrder.indexOf(phaseId);
    if (idx <= 0) return null;
    const prevId = phaseOrder[idx - 1];
    return PHASE_DEFS[prevId]?.label || null;
  };

  const phaseItemCounts = (phaseId) => {
    const items = getPhaseItems(phaseId, entry);
    const total = items.length;
    const done = items.filter(k => completed[k] === true).length;
    return { done, total };
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {BLOCKS.map(({ key, emoji, label }) => {
        const data = blockData[key];

        // Guided flow: is this phase in the computed order at all?
        const inFlow = phaseOrder.includes(key);
        const state = inFlow ? phaseStateFor(key) : null;

        // Completed + not re-expanded: render collapsed summary instead of the block
        if (state === 'complete' && !expandedCompletedPhases.has(key) && !readOnly) {
          const { done, total } = phaseItemCounts(key);
          return (
            <CompletedPhaseSummary
              key={key}
              phaseLabel={PHASE_DEFS[key]?.label || label}
              doneCount={done}
              totalCount={total}
              markedDone={manuallyDonePhases.has(key)}
              onClick={() => handleToggleCompletedPhaseExpand(key)}
            />
          );
        }

        // Active: container adds box-shadow stripe + bg tint + relative positioning for NOW pill
        const isActive = state === 'active';
        const wrapperStyle = isActive
          ? {
              boxShadow: 'inset 3px 0 0 #5c1020, 0 1px 3px rgba(92,16,32,0.08)',
              background: 'rgba(92,16,32,0.018)',
              transition: 'box-shadow 0.2s ease',
            }
          : undefined;

        const blockElement = key === 'throwing' ? (
          <ThrowingBlock
            key={key}
            emoji={emoji}
            label={label}
            throwing={data}
            fallbackPlan={plan_generated?.throwing_plan}
            exerciseMap={exerciseMap}
            slugMap={slugMap}
            completed={completed}
            onToggle={readOnly ? null : handleToggle}
            expandedWhy={expandedWhy}
            onToggleWhy={toggleWhy}
            collapsedPhases={collapsedPhases}
            onTogglePhase={(phaseKey) => setCollapsedPhases(prev => ({ ...prev, [phaseKey]: !prev[phaseKey] }))}
            entry={entry}
            pitcherId={pitcherId}
            initData={initData}
            readOnly={readOnly}
            wrapperStyle={wrapperStyle}
          />
        ) : (
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
            swappingExerciseId={key === 'lifting' ? swappingExerciseId : null}
            swappedExercises={key === 'lifting' ? swappedExercises : {}}
            swapOverrides={key === 'lifting' ? swapOverrides : {}}
            onStartSwap={key === 'lifting' && !readOnly ? setSwappingExerciseId : null}
            onSwapComplete={key === 'lifting' && !readOnly ? handleSwapComplete : null}
            onCancelSwap={key === 'lifting' ? () => setSwappingExerciseId(null) : null}
            pitcherId={pitcherId}
            date={entry?.date}
            initData={initData}
            readOnly={readOnly}
            wrapperStyle={wrapperStyle}
            researchSources={key === 'lifting' ? researchSources : []}
            onShowWhySheet={key === 'lifting' && !readOnly ? () => setShowWhySheet(true) : null}
          />
        );

        // Not in guided flow (e.g. readOnly mode) — render plain block
        if (!inFlow || readOnly) return blockElement;

        // Re-expanded completed phase: show collapse affordance
        const isReExpandedComplete = state === 'complete' && expandedCompletedPhases.has(key);

        // Wrap in position:relative container for NOW pill overlay + Mark Done button
        return (
          <div key={key} style={{ position: 'relative' }}>
            {isActive && <NowPill />}
            {blockElement}
            {isActive && (
              <MarkPhaseDoneButton
                phaseLabel={PHASE_DEFS[key]?.label || label}
                onClick={() => handleMarkPhaseDone(key)}
              />
            )}
            {isReExpandedComplete && (
              <CollapsePhaseButton
                phaseLabel={PHASE_DEFS[key]?.label || label}
                onClick={() => handleToggleCompletedPhaseExpand(key)}
              />
            )}
          </div>
        );
      })}

      {notes.length > 0 && <NotesBlock notes={notes} />}

      <MobilityCard mobility={activeMobility} />

      {entry.outing && (
        <div style={{ background: 'var(--color-white)', borderRadius: 12, padding: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
            <span style={{ fontSize: 14 }}>{'\uD83D\uDCCA'}</span>
            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-ink-primary)' }}>Outing</span>
          </div>
          <p style={{ fontSize: 13, color: 'var(--color-ink-primary)', margin: 0 }}>
            {entry.outing.pitch_count} pitches · Post feel: {entry.outing.arm_feel ?? entry.outing.post_arm_feel}/10
          </p>
          {entry.outing.notes && (
            <p style={{ fontSize: 11, color: 'var(--color-ink-muted)', marginTop: 4, margin: '4px 0 0' }}>
              {Array.isArray(entry.outing.notes) ? entry.outing.notes.join('; ') : String(entry.outing.notes)}
            </p>
          )}
        </div>
      )}

      {showWhySheet && (
        <ResearchWhySheet
          researchSources={researchSources}
          onClose={() => setShowWhySheet(false)}
        />
      )}
    </div>
  );
}

// ── Guided Flow — visual helpers ──

/**
 * Collapsed one-line summary for a completed phase.
 * Renders: [green check badge] Phase Name [count pill] [chevron]
 * Tap to re-expand.
 */
function CompletedPhaseSummary({ phaseLabel, doneCount, totalCount, markedDone, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{
        background: 'var(--color-white)',
        borderRadius: 12,
        padding: '12px 16px',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        cursor: 'pointer',
        minHeight: 44,
        transition: 'background 0.15s ease',
      }}
      onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(42,26,24,0.02)'; }}
      onMouseLeave={(e) => { e.currentTarget.style.background = 'var(--color-white)'; }}
    >
      {/* Green check badge */}
      <div style={{
        width: 22,
        height: 22,
        borderRadius: '50%',
        background: 'var(--color-flag-green)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}>
        <span style={{ color: '#ffffff', fontSize: 13, fontWeight: 700, lineHeight: 1 }}>✓</span>
      </div>

      {/* Label */}
      <span style={{
        flex: 1,
        fontSize: 13,
        fontWeight: 500,
        color: 'var(--color-ink-secondary, #6b5f58)',
      }}>
        {phaseLabel}
      </span>

      {/* Count pill (or em-dash if no items) */}
      {totalCount > 0 ? (
        <span style={{
          fontSize: 11,
          fontWeight: 600,
          padding: '3px 9px',
          borderRadius: 8,
          background: 'rgba(29,158,117,0.09)',
          color: 'var(--color-flag-green)',
          fontVariantNumeric: 'tabular-nums',
          letterSpacing: '0.2px',
        }}>
          {doneCount}/{totalCount}
        </span>
      ) : markedDone ? (
        <span style={{ fontSize: 13, color: 'var(--color-ink-muted)', fontWeight: 400 }}>—</span>
      ) : null}

      {/* Chevron — indicates re-expandable */}
      <span style={{
        fontSize: 15,
        color: 'var(--color-ink-muted)',
        fontWeight: 400,
        lineHeight: 1,
        marginLeft: 2,
      }}>
        ›
      </span>
    </div>
  );
}

/**
 * Active phase "NOW" pill — absolutely positioned on the phase container.
 * Appears top-right, slightly peeking above the card edge like a tab tag.
 */
function NowPill() {
  return (
    <div style={{
      position: 'absolute',
      top: -6,
      right: 14,
      fontSize: 9,
      fontWeight: 700,
      letterSpacing: '0.9px',
      background: 'linear-gradient(165deg, #5c1020 0%, #7a1a2e 100%)',
      color: '#ffffff',
      padding: '3px 10px',
      borderRadius: 10,
      boxShadow: '0 2px 8px rgba(92,16,32,0.28)',
      zIndex: 2,
      pointerEvents: 'none',
      textTransform: 'none', // letter-spacing alone does the job
    }}>
      NOW
    </div>
  );
}

/**
 * Subtle "Collapse [phase] ↑" button, rendered beneath a re-expanded
 * completed phase to let the user hide it again. Outline-maroon styling
 * (quieter than MarkPhaseDoneButton) — this is an optional affordance,
 * not the primary action.
 */
function CollapsePhaseButton({ phaseLabel, onClick }) {
  const [hover, setHover] = useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        marginTop: 6,
        width: '100%',
        padding: '9px 20px',
        borderRadius: 10,
        border: '1px solid rgba(92,16,32,0.18)',
        background: hover ? 'rgba(92,16,32,0.04)' : 'transparent',
        color: '#5c1020',
        fontSize: 11,
        fontWeight: 600,
        letterSpacing: '0.3px',
        cursor: 'pointer',
        transition: 'background 0.15s ease, border-color 0.15s ease',
        fontFamily: 'inherit',
      }}
    >
      Collapse {phaseLabel.toLowerCase()} ↑
    </button>
  );
}

/**
 * "Done with [phase] →" button, rendered beneath the active phase card.
 * Maroon gradient (matches Profile identity header), tactile hover/tap.
 */
function MarkPhaseDoneButton({ phaseLabel, onClick }) {
  const [hover, setHover] = useState(false);
  const [pressed, setPressed] = useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => { setHover(false); setPressed(false); }}
      onMouseDown={() => setPressed(true)}
      onMouseUp={() => setPressed(false)}
      style={{
        marginTop: 8,
        width: '100%',
        padding: '11px 20px',
        borderRadius: 10,
        border: 'none',
        background: 'linear-gradient(165deg, #5c1020 0%, #7a1a2e 100%)',
        color: '#ffffff',
        fontSize: 12,
        fontWeight: 600,
        letterSpacing: '0.3px',
        cursor: 'pointer',
        transform: pressed ? 'scale(0.98)' : (hover ? 'translateY(-1px)' : 'none'),
        boxShadow: hover && !pressed
          ? '0 4px 12px rgba(92,16,32,0.22)'
          : '0 1px 3px rgba(92,16,32,0.15)',
        transition: 'transform 0.15s ease, box-shadow 0.15s ease',
        fontFamily: 'inherit',
      }}
    >
      Done with {phaseLabel.toLowerCase()} →
    </button>
  );
}

// ── Exercise Block (arm_care, lifting) ──

function ExerciseBlock({ blockKey, emoji, label, data, fallbackBlocks, hasStructured, exerciseMap, slugMap, completed, onToggle, expandedWhy, onToggleWhy, swappingExerciseId, swappedExercises, swapOverrides, onStartSwap, onSwapComplete, onCancelSwap, pitcherId, date, initData, readOnly, wrapperStyle, researchSources = [], onShowWhySheet }) {
  const [warmupExpanded, setWarmupExpanded] = useState(false);
  const exercises = data?.exercises || [];
  const hasDirect = hasStructured && exercises.length > 0;

  // Resolve fallback exercises for this block
  let fallbackExercises = [];
  let fallbackBlockGroups = []; // Preserve block_name structure for lifting
  if (!hasDirect) {
    const isArm = blockKey === 'arm_care';
    const filtered = fallbackBlocks.filter(b => {
      const name = b.block_name?.toLowerCase() || '';
      return isArm ? name.includes('arm') : (!name.includes('arm') && !name.includes('plyo'));
    });
    fallbackExercises = filtered.flatMap(b => b.exercises || []);
    // For lifting, keep the block groups for stratification
    if (blockKey === 'lifting') {
      fallbackBlockGroups = filtered.map(b => ({
        label: b.block_name || null,
        exercises: b.exercises || [],
      })).filter(g => g.exercises.length > 0);
    }
  }

  const allEx = hasDirect ? exercises : fallbackExercises;
  if (allEx.length === 0) return null;

  const doneCount = allEx.filter(ex => completed[ex.exercise_id] === true).length;
  const subtitle = data?.intent || data?.timing || data?.type || '';
  const duration = data?.estimated_duration_min;
  const reasoning = data?.reasoning;

  // Warmup block: group exercises by their block name, collapsed by default
  if (blockKey === 'warmup' && allEx.length > 0) {
    const groups = [];
    let currentBlock = null;
    for (const ex of allEx) {
      if (ex.block !== currentBlock) {
        currentBlock = ex.block;
        groups.push({ label: currentBlock, exercises: [ex] });
      } else {
        groups[groups.length - 1].exercises.push(ex);
      }
    }

    return (
      <div style={{ background: 'var(--color-white)', borderRadius: 12, overflow: 'hidden', ...wrapperStyle }}>
        <div
          onClick={() => setWarmupExpanded(prev => !prev)}
          style={{ padding: '10px 14px', borderBottom: warmupExpanded ? '0.5px solid var(--color-cream-border)' : 'none', cursor: 'pointer' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 14 }}>{emoji}</span>
              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-ink-primary)' }}>{label}</span>
              {duration && <span style={{ fontSize: 10, color: 'var(--color-ink-faint)' }}>{duration} min</span>}
              <span style={{ fontSize: 10, color: 'var(--color-ink-muted)' }}>{warmupExpanded ? '\u25BC' : '\u25B6'}</span>
            </div>
            <span style={{ fontSize: 11, color: doneCount === allEx.length && allEx.length > 0 ? 'var(--color-flag-green)' : 'var(--color-ink-muted)', fontWeight: 600 }}>
              {doneCount}/{allEx.length}
            </span>
          </div>
        </div>
        {warmupExpanded && (
          <div style={{ padding: '4px 14px 10px' }}>
            {groups.map((g, gi) => (
              <div key={gi}>
                <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--color-ink-muted)', textTransform: 'uppercase', letterSpacing: 0.5, padding: '6px 0 2px' }}>
                  {g.label}
                </div>
                <SupersetList
                  exercises={g.exercises}
                  exerciseMap={exerciseMap}
                  slugMap={slugMap}
                  completed={completed}
                  onToggle={onToggle}
                  expandedWhy={expandedWhy}
                  onToggleWhy={onToggleWhy}
                />
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div style={{
      background: 'var(--color-white)', borderRadius: blockKey === 'lifting' ? 14 : 12, overflow: 'hidden',
      boxShadow: blockKey === 'lifting' ? '0 1px 3px rgba(42,26,24,0.06)' : 'none',
      ...wrapperStyle,
    }}>
      {/* Block header */}
      <div style={{ padding: '10px 14px', borderBottom: '0.5px solid var(--color-cream-border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 14 }}>{emoji}</span>
            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-ink-primary)' }}>{label}</span>
            {subtitle && <span style={{ fontSize: 11, color: 'var(--color-ink-muted)' }}>{'\u2014 '}{subtitle}</span>}
            {duration && <span style={{ fontSize: 10, color: 'var(--color-ink-faint)' }}>{duration} min</span>}
            {blockKey === 'lifting' && researchSources.length > 0 && !readOnly && (
              <button
                onClick={onShowWhySheet}
                style={{
                  marginLeft: 4, display: 'inline-flex', alignItems: 'center',
                  borderRadius: 9999, backgroundColor: '#f3f4f6',
                  padding: '2px 8px', fontSize: 12, color: '#6b7280',
                  border: 'none', cursor: 'pointer'
                }}
                title="Why today looks different"
              >
                &#9432; why
              </button>
            )}
          </div>
          <span style={{ fontSize: 12, color: doneCount === allEx.length && allEx.length > 0 ? 'var(--color-flag-green)' : 'var(--color-ink-muted)', fontWeight: 600 }}>
            {doneCount}/{allEx.length}
          </span>
        </div>
        {reasoning && typeof reasoning === 'string' && (
          <p style={{ fontSize: 11, color: 'var(--color-ink-muted)', fontStyle: 'italic', lineHeight: 1.5, margin: '4px 0 0' }}>
            {reasoning}
          </p>
        )}
      </div>

      {/* Exercise list — with sub-block grouping for lifting */}
      <div style={{ padding: '6px 14px 10px' }}>
        {blockKey === 'lifting' && (() => {
          // Build block groups from exercise_blocks (which always has block_name structure)
          // Filter to lifting-related blocks (skip arm care blocks)
          const liftingBlocks = fallbackBlocks
            .filter(b => {
              const name = (b.block_name || '').toLowerCase();
              return !name.includes('arm') && (b.exercises || []).length > 0;
            })
            .map(b => ({ label: b.block_name || null, exercises: b.exercises || [] }));

          // If exercise_blocks don't have structure, try individual exercise block fields
          let blockGroups = liftingBlocks.length > 0 ? liftingBlocks : [];

          if (blockGroups.length === 0 && allEx.length > 0) {
            let curBlock = null;
            for (const ex of allEx) {
              const bk = ex.block_name || ex.block;
              if (bk && bk !== curBlock) {
                curBlock = bk;
                blockGroups.push({ label: bk, exercises: [ex] });
              } else if (bk && blockGroups.length > 0) {
                blockGroups[blockGroups.length - 1].exercises.push(ex);
              } else {
                if (blockGroups.length === 0) blockGroups.push({ label: null, exercises: [] });
                blockGroups[blockGroups.length - 1].exercises.push(ex);
              }
            }
          }

          // If only one group with no label, render flat
          const hasMultipleBlocks = blockGroups.length > 1 || (blockGroups.length === 1 && blockGroups[0].label);
          if (!hasMultipleBlocks) {
            return (
              <SupersetList
                exercises={allEx} exerciseMap={exerciseMap} slugMap={slugMap}
                completed={completed} onToggle={onToggle}
                expandedWhy={expandedWhy} onToggleWhy={onToggleWhy}
                swappingExerciseId={swappingExerciseId} swappedExercises={swappedExercises}
                swapOverrides={swapOverrides} onStartSwap={onStartSwap} onSwapComplete={onSwapComplete} onCancelSwap={onCancelSwap}
                pitcherId={pitcherId} date={date} initData={initData} readOnly={readOnly}
              />
            );
          }
          return blockGroups.map((bg, bgi) => (
            <div key={bgi}>
              {bg.label && (
                <div style={{
                  padding: '8px 0 4px',
                  background: bgi === 0 ? 'rgba(92,16,32,0.024)' : 'transparent',
                  borderTop: bgi > 0 ? '1px solid var(--color-cream-border)' : 'none',
                  margin: bgi > 0 ? '4px 0 0' : '0',
                }}>
                  <span style={{
                    fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1,
                    color: bgi === 0 ? 'var(--color-maroon)' : 'var(--color-ink-muted)',
                  }}>
                    {bg.label}
                  </span>
                </div>
              )}
              <SupersetList
                exercises={bg.exercises} exerciseMap={exerciseMap} slugMap={slugMap}
                completed={completed} onToggle={onToggle}
                expandedWhy={expandedWhy} onToggleWhy={onToggleWhy}
                swappingExerciseId={swappingExerciseId} swappedExercises={swappedExercises}
                swapOverrides={swapOverrides} onStartSwap={onStartSwap} onSwapComplete={onSwapComplete} onCancelSwap={onCancelSwap}
                pitcherId={pitcherId} date={date} initData={initData} readOnly={readOnly}
              />
            </div>
          ));
        })()}
        {blockKey !== 'lifting' && (
          <SupersetList
            exercises={allEx} exerciseMap={exerciseMap} slugMap={slugMap}
            completed={completed} onToggle={onToggle}
            expandedWhy={expandedWhy} onToggleWhy={onToggleWhy}
          />
        )}
      </div>
    </div>
  );
}

// ── Throwing Block ──

function ThrowingBlock({ emoji, label, throwing, fallbackPlan, exerciseMap, slugMap, completed, onToggle, expandedWhy, onToggleWhy, collapsedPhases, onTogglePhase, entry, pitcherId, initData, readOnly, wrapperStyle }) {
  const data = throwing || fallbackPlan;
  if (!data) return null;

  const phases = Array.isArray(data.phases) ? data.phases : [];
  const hasPhases = phases.some(p => p.exercises?.length > 0);

  // If we have structured phases, render the rich view
  if (hasPhases) {
    const allExercises = phases.flatMap(p => p.exercises || []);
    const doneCount = allExercises.filter(ex => completed[ex.exercise_id] === true).length;
    const totalCount = allExercises.length;
    const dayLabel = data.day_type_label || data.type?.replace(/_/g, ' ') || '';
    const intensity = data.intensity_range;
    const duration = data.estimated_duration_min;
    const reasoning = data.reasoning;
    const vol = data.volume_summary;

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {data.triage_modified && (
          <WhyCard
            reasoning={reasoning}
            originalDayType={data.original_day_type}
            currentDayType={dayLabel}
          />
        )}
        <div style={{ background: 'var(--color-white)', borderRadius: 12, overflow: 'hidden', ...wrapperStyle }}>
        {/* Header */}
        <div style={{ padding: '10px 14px', borderBottom: '0.5px solid var(--color-cream-border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 14 }}>{emoji}</span>
              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-ink-primary)' }}>{label}</span>
              {dayLabel && <span style={{ fontSize: 11, color: 'var(--color-ink-muted)' }}>{'\u2014 '}{dayLabel}</span>}
            </div>
            <span style={{ fontSize: 11, color: doneCount === totalCount && totalCount > 0 ? 'var(--color-flag-green)' : 'var(--color-ink-muted)', fontWeight: 600 }}>
              {doneCount}/{totalCount}
            </span>
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 4, flexWrap: 'wrap' }}>
            {intensity && <PillBadge>{intensity}</PillBadge>}
            {duration && <PillBadge>{duration} min</PillBadge>}
            {vol?.total_throws_estimate > 0 && <PillBadge>~{vol.total_throws_estimate} throws</PillBadge>}
            {data.team_block_tag && (
              <span style={{ display: 'inline-flex', alignItems: 'center', padding: '2px 8px', borderRadius: 9999, fontSize: 11, fontWeight: 500, backgroundColor: 'rgba(92, 16, 32, 0.1)', color: '#5c1020' }}>
                {data.team_block_tag}
              </span>
            )}
          </div>
          {reasoning && typeof reasoning === 'string' && !data.triage_modified && (
            <p style={{ fontSize: 11, color: 'var(--color-ink-muted)', fontStyle: 'italic', lineHeight: 1.5, margin: '4px 0 0' }}>
              {reasoning}
            </p>
          )}
        </div>

        {/* Phases */}
        <div style={{ padding: '4px 0' }}>
          {phases.map((phase, pi) => {
            const phaseExercises = phase.exercises || [];
            if (phaseExercises.length === 0) return null;
            const phaseKey = `throwing_phase_${pi}`;
            const isCollapsed = !!collapsedPhases[phaseKey];
            const phaseDone = phaseExercises.filter(ex => completed[ex.exercise_id] === true).length;

            const isPostThrow = (phase.phase_name || '').toLowerCase().includes('post-throw');
            return (
              <div key={pi} style={{ borderBottom: pi < phases.length - 1 ? '0.5px solid var(--color-cream-border)' : 'none' }}>
                {/* Phase header */}
                <div
                  onClick={() => onTogglePhase(phaseKey)}
                  style={{
                    padding: '6px 14px', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    background: isPostThrow ? 'rgba(29, 158, 117, 0.06)' : 'var(--color-cream-bg)',
                  }}
                >
                  <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--color-ink-secondary)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                    {isCollapsed ? '\u25B6 ' : '\u25BC '}{phase.phase_name || `Phase ${pi + 1}`}
                  </span>
                  <span style={{ fontSize: 10, color: phaseDone === phaseExercises.length && phaseExercises.length > 0 ? 'var(--color-flag-green)' : 'var(--color-ink-faint)' }}>
                    {phaseDone}/{phaseExercises.length}
                  </span>
                </div>
                {/* Phase exercises */}
                {!isCollapsed && (
                  <div style={{ padding: '4px 14px 8px' }}>
                    <SupersetList
                      exercises={phaseExercises}
                      exerciseMap={exerciseMap}
                      slugMap={slugMap}
                      completed={completed}
                      onToggle={onToggle}
                      expandedWhy={expandedWhy}
                      onToggleWhy={onToggleWhy}
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Ball color legend — show when any exercise has ball_weight */}
        {allExercises.some(ex => ex.ball_weight) && (
          <div style={{ borderTop: '0.5px solid var(--color-cream-border)' }}>
            <BallColorLegend />
          </div>
        )}
      </div>

      {/* Post-throw feel capture — appears when all throwing exercises are done */}
      {!readOnly && totalCount > 0 && doneCount === totalCount && (
        <PostThrowFeel
          preThrowFeel={(entry?.pre_training || {}).arm_feel}
          existingValue={data.post_throw_feel}
          onCapture={(feel) => submitThrowFeel(pitcherId, entry?.date, feel, initData)}
        />
      )}
      </div>
    );
  }

  // Legacy fallback: simple text display
  const type = data.type || data.details || 'none';
  const detail = data.detail || data.details || '';
  const intent = data.intent;
  const duration = data.estimated_duration_min;
  if (type === 'none' && !detail) return null;

  return (
    <div style={{ background: 'var(--color-white)', borderRadius: 12, overflow: 'hidden', ...wrapperStyle }}>
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

function SupersetList({ exercises, exerciseMap, slugMap, completed, onToggle, expandedWhy, onToggleWhy, swappingExerciseId, swappedExercises, swapOverrides, onStartSwap, onSwapComplete, onCancelSwap, pitcherId, date, initData, readOnly }) {
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
            // Apply swap override if this exercise was swapped
            const override = swapOverrides?.[ex.exercise_id];
            const displayEx = override ? { ...ex, exercise_id: override.exercise_id, name: override.name, rx: override.rx, prescribed: override.prescribed || override.rx } : ex;

            const exId = displayEx.exercise_id || `flow_${(displayEx.name || '').replace(/\s+/g, '_').toLowerCase()}`;
            const lib = resolveExercise(exId, exerciseMap, slugMap);
            const exerciseObj = lib || { name: displayEx.name || exId, youtube_url: override?.youtube_url || '', muscles_primary: [], pitching_relevance: '' };
            const isCompleted = completed[exId] === true;
            const label = g.letter ? `${g.letter}${ei + 1}` : null;
            const noteStr = typeof displayEx.note === 'string' ? displayEx.note : '';
            const isFpm = noteStr.toLowerCase().includes('elevated') || noteStr.toLowerCase().includes('fpm');
            const rawWhy = displayEx.why || exerciseObj.pitching_relevance || '';
            const why = typeof rawWhy === 'string' ? rawWhy : '';

            return (
              <ExerciseItem
                key={ei}
                exerciseId={exId}
                exercise={exerciseObj}
                rx={displayEx.rx || displayEx.prescribed || ''}
                prescription={displayEx.prescription || ''}
                note={noteStr}
                label={label}
                completed={isCompleted}
                isFpm={isFpm}
                why={why}
                whyExpanded={!!expandedWhy[exId]}
                onToggle={onToggle ? () => onToggle(exId, !isCompleted) : null}
                onToggleWhy={() => onToggleWhy(exId)}
                ballWeight={displayEx.ball_weight}
                swappingExerciseId={swappingExerciseId}
                swappedFrom={swappedExercises?.[exId]}
                onStartSwap={onStartSwap}
                onSwapComplete={onSwapComplete}
                onCancelSwap={onCancelSwap}
                pitcherId={pitcherId}
                date={date}
                initData={initData}
                readOnly={readOnly}
              />
            );
          })}
        </div>
      ))}
    </div>
  );
}

// ── Exercise item ──

function ExerciseItem({ exerciseId, exercise, rx, prescription, note: rawNote, label, completed, isFpm, why, whyExpanded, onToggle, onToggleWhy, ballWeight, swappingExerciseId, swappedFrom, onStartSwap, onSwapComplete, onCancelSwap, pitcherId, date, initData, readOnly }) {
  const note = typeof rawNote === 'string' ? rawNote : '';
  const isSwapping = swappingExerciseId === exerciseId;

  const rowStyle = {
    display: 'flex', alignItems: 'center', gap: 10, padding: '10px 4px',
    borderRadius: 8,
    background: completed ? 'rgba(29,158,117,0.024)'
      : isFpm ? 'rgba(245,224,228,0.25)'
      : 'transparent',
    opacity: isSwapping ? 0.5 : 1,
    transition: 'all 0.15s ease',
  };

  const circleStyle = {
    width: 24, height: 24, borderRadius: 12, flexShrink: 0,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: 11, fontWeight: 700, cursor: onToggle ? 'pointer' : 'default',
    border: 'none',
    transition: 'all 0.15s ease',
    ...(completed
      ? { background: 'var(--color-flag-green)', color: '#fff' }
      : isFpm
        ? { background: 'rgba(92,16,32,0.08)', color: 'var(--color-maroon)' }
        : { background: 'var(--color-cream-border)', color: 'var(--color-ink-muted)' }
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
            fontSize: 14, margin: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
            letterSpacing: -0.2,
            color: completed ? 'var(--color-ink-muted)' : 'var(--color-ink-primary)',
            textDecoration: completed ? 'line-through' : 'none',
            fontWeight: isFpm && !completed ? 600 : 500,
          }}>
            {exercise.name || 'Unknown exercise'}
            <BallDots weight={ballWeight} />
          </p>
          <div style={{ fontSize: 12, marginTop: 2, color: isFpm && !completed ? 'var(--color-maroon)' : 'var(--color-ink-muted)', fontWeight: isFpm && !completed ? 500 : 400 }}>
            {isFpm && !completed && (
              <span style={{
                fontSize: 9, padding: '1px 5px', borderRadius: 4,
                background: 'var(--color-maroon)', color: '#fff',
                fontWeight: 700, marginRight: 6, letterSpacing: 0.5,
                verticalAlign: 'middle',
              }}>FPM</span>
            )}
            {fullRx}
            {note && !isFpm && <span style={{ color: 'var(--color-maroon)' }}>{' \u00B7 '}{note}</span>}
          </div>
        </div>

        {/* Action cluster — hidden when completed */}
        {!completed && (
          <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0 }}>
            {why && (
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
                style={{
                  width: 28, height: 28, borderRadius: 8, flexShrink: 0,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 12, textDecoration: 'none',
                  background: 'var(--color-cream-bg)', color: 'var(--color-maroon)',
                }}>{'\u25B6'}</a>
            )}

            {onStartSwap && !readOnly && !isSwapping && (
              <button
                onClick={(e) => { e.stopPropagation(); onStartSwap(exerciseId); }}
                style={{
                  height: 28, borderRadius: 8, border: 'none',
                  padding: '0 10px',
                  background: isSwapping ? 'var(--color-maroon)' : 'rgba(92,16,32,0.07)',
                  color: isSwapping ? '#fff' : 'var(--color-maroon)',
                  fontSize: 11, fontWeight: 600, cursor: 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  transition: 'all 0.15s ease',
                  flexShrink: 0,
                }}
              >
                Swap
              </button>
            )}
          </div>
        )}

        {/* Done badge — shown when completed */}
        {completed && (
          <span style={{
            fontSize: 10, color: 'var(--color-flag-green)', fontWeight: 600,
            padding: '2px 8px', borderRadius: 6,
            background: 'rgba(29,158,117,0.06)',
            flexShrink: 0,
          }}>Done</span>
        )}
      </div>

      {/* Inline swap UI */}
      {isSwapping && (
        <ExerciseSwap
          exerciseId={exerciseId}
          exerciseName={exercise.name}
          pitcherId={pitcherId}
          date={date}
          initData={initData}
          onSwap={(newEx) => onSwapComplete(exerciseId, newEx)}
          onCancel={onCancelSwap}
        />
      )}

      {/* Swapped indicator */}
      {swappedFrom && (
        <div style={{
          marginLeft: 50, marginTop: 2, marginBottom: 6, fontSize: 11,
          color: 'var(--color-ink-muted)', fontStyle: 'italic',
          display: 'flex', alignItems: 'center', gap: 4,
        }}>
          <span style={{ color: 'var(--color-flag-green)' }}>{'\u21BB'}</span>
          swapped from {swappedFrom.swapped_from_name}
        </div>
      )}

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
