import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../App';
import { useApi } from '../hooks/useApi';
import PlanBuilder from '../components/PlanBuilder';

export default function Plans() {
  const { pitcherId, initData } = useAuth();
  const navigate = useNavigate();
  const { data, loading, refetch } = useApi(
    pitcherId ? `/api/pitcher/${pitcherId}/plans` : null,
    initData
  );

  const [showBuilder, setShowBuilder] = useState(false);
  const [expandedPlan, setExpandedPlan] = useState(null);

  const plans = data?.plans || [];
  const currentProgram = plans.find(p => p.active);
  const pastPrograms = plans.filter(p => !p.active);

  if (loading) {
    return (
      <div style={{ padding: 16 }}>
        <div style={{ height: 24, background: 'var(--color-cream-border)', borderRadius: 6, width: '40%', marginBottom: 16 }} />
        <div style={{ height: 120, background: 'var(--color-cream-border)', borderRadius: 12, marginBottom: 12 }} />
        <div style={{ height: 80, background: 'var(--color-cream-border)', borderRadius: 12 }} />
      </div>
    );
  }

  return (
    <div style={{ paddingBottom: 100 }}>
      {/* Header */}
      <div style={{ background: 'var(--color-maroon)', padding: '14px 16px 12px' }}>
        <div style={{ fontSize: 20, fontWeight: 800, color: '#fff', letterSpacing: '-0.4px' }}>My Program</div>
        <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.45)', marginTop: 2 }}>
          Current training program and history
        </div>
      </div>

      <div style={{ padding: '0 12px' }}>
        {/* Current program */}
        {currentProgram ? (
          <div style={{ marginTop: 12 }}>
            <div style={{
              fontSize: 9, fontWeight: 700, color: 'var(--color-maroon)',
              textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6,
            }}>
              Current Program
            </div>
            <CurrentProgramCard
              plan={currentProgram}
              onTapExercise={(planId) => navigate(`/plans/${planId}`)}
              onTalkToCoach={() => navigate('/coach')}
            />
          </div>
        ) : (
          <div style={{
            background: 'var(--color-white)', borderRadius: 12, padding: 16,
            textAlign: 'center', marginTop: 12,
          }}>
            <p style={{ fontSize: 13, color: 'var(--color-ink-primary)', marginBottom: 4 }}>No active program</p>
            <p style={{ fontSize: 11, color: 'var(--color-ink-muted)' }}>
              Check in with the Coach to generate your first plan, or build one below.
            </p>
          </div>
        )}

        {/* Build new plan button */}
        <button
          onClick={() => setShowBuilder(true)}
          style={{
            width: '100%', padding: 11, borderRadius: 12, marginTop: 12,
            background: 'var(--color-white)', color: 'var(--color-maroon)',
            fontSize: 12, fontWeight: 600, border: '1px solid var(--color-maroon)',
            cursor: 'pointer',
          }}
        >
          + Build new program
        </button>

        {/* Program history */}
        {pastPrograms.length > 0 && (
          <div style={{ marginTop: 20 }}>
            <div style={{
              fontSize: 9, fontWeight: 700, color: 'var(--color-ink-muted)',
              textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8,
            }}>
              Program History
            </div>
            {pastPrograms.map(plan => (
              <PastProgramRow
                key={plan.id}
                plan={plan}
                expanded={expandedPlan === plan.id}
                onToggle={() => setExpandedPlan(prev => prev === plan.id ? null : plan.id)}
                onView={() => navigate(`/plans/${plan.id}`)}
              />
            ))}
          </div>
        )}
      </div>

      {showBuilder && <PlanBuilder onClose={() => { setShowBuilder(false); refetch(); }} />}
    </div>
  );
}

function CurrentProgramCard({ plan, onTapExercise, onTalkToCoach }) {
  const exercises = plan.lifting?.exercises || [];
  const armCareExercises = plan.arm_care?.exercises || [];

  return (
    <div style={{ background: 'var(--color-white)', borderRadius: 12, overflow: 'hidden' }}>
      {/* Title */}
      <div style={{ padding: '12px 14px', borderBottom: '0.5px solid var(--color-cream-border)' }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--color-ink-primary)' }}>
          {plan.title || 'Active Program'}
        </div>
        <div style={{ fontSize: 10, color: 'var(--color-ink-muted)', marginTop: 2 }}>
          {plan.category?.replace(/_/g, ' ')} · since {plan.created_date}
        </div>
        {plan.summary && (
          <p style={{ fontSize: 11, color: 'var(--color-ink-secondary)', marginTop: 6, lineHeight: 1.5 }}>
            {plan.summary}
          </p>
        )}
      </div>

      {/* Exercise list */}
      {(armCareExercises.length > 0 || exercises.length > 0) && (
        <div style={{ padding: '10px 14px' }}>
          {armCareExercises.length > 0 && (
            <div style={{ marginBottom: 8 }}>
              <p style={{
                fontSize: 8, fontWeight: 700, color: 'var(--color-ink-faint)',
                textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4,
              }}>
                Arm Care
              </p>
              {armCareExercises.map((ex, i) => (
                <ProgramExerciseRow key={i} exercise={ex} />
              ))}
            </div>
          )}
          {exercises.length > 0 && (
            <div>
              <p style={{
                fontSize: 8, fontWeight: 700, color: 'var(--color-ink-faint)',
                textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4,
              }}>
                Lifting
              </p>
              {exercises.map((ex, i) => (
                <ProgramExerciseRow key={i} exercise={ex} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Action: talk to coach */}
      <div style={{ padding: '0 14px 12px' }}>
        <button
          onClick={onTalkToCoach}
          style={{
            width: '100%', padding: 9, borderRadius: 8,
            background: 'var(--color-cream-bg)', color: 'var(--color-maroon)',
            fontSize: 11, fontWeight: 600, border: 'none', cursor: 'pointer',
          }}
        >
          Talk to Coach about changes
        </button>
      </div>
    </div>
  );
}

function ProgramExerciseRow({ exercise }) {
  const name = exercise.name || exercise.exercise_id?.replace('ex_', '').replace(/_/g, ' ');
  const rx = exercise.rx || exercise.prescribed || exercise.prescription || '';

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0',
      borderBottom: '0.5px solid var(--color-cream-bg)',
    }}>
      <div style={{
        width: 5, height: 5, borderRadius: '50%',
        background: 'var(--color-ink-faint)', flexShrink: 0,
      }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{
          fontSize: 12, margin: 0, color: 'var(--color-ink-primary)',
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          textTransform: 'capitalize',
        }}>
          {name}
        </p>
      </div>
      {rx && (
        <span style={{ fontSize: 10, color: 'var(--color-ink-muted)', flexShrink: 0 }}>
          {rx}
        </span>
      )}
    </div>
  );
}

function PastProgramRow({ plan, expanded, onToggle, onView }) {
  const exercises = plan.lifting?.exercises || [];
  const changeReason = plan.summary || plan.category?.replace(/_/g, ' ') || '';

  return (
    <div style={{
      background: 'var(--color-white)', borderRadius: 10,
      marginBottom: 6, overflow: 'hidden',
    }}>
      {/* Header row */}
      <div
        onClick={onToggle}
        style={{
          padding: '10px 14px', cursor: 'pointer',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}
      >
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{
            fontSize: 12, fontWeight: 500, color: 'var(--color-ink-primary)',
            margin: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          }}>
            {plan.title || 'Untitled program'}
          </p>
          <p style={{ fontSize: 10, color: 'var(--color-ink-muted)', margin: '2px 0 0' }}>
            {plan.created_date}
            {changeReason && ` · ${changeReason}`}
          </p>
        </div>
        <span style={{ fontSize: 12, color: 'var(--color-ink-faint)', flexShrink: 0 }}>
          {expanded ? '\u25BE' : '\u25B8'}
        </span>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div style={{ padding: '0 14px 10px' }}>
          {exercises.length > 0 && (
            <div style={{ marginBottom: 8 }}>
              {exercises.slice(0, 6).map((ex, i) => (
                <ProgramExerciseRow key={i} exercise={ex} />
              ))}
              {exercises.length > 6 && (
                <p style={{ fontSize: 10, color: 'var(--color-ink-muted)', marginTop: 4 }}>
                  + {exercises.length - 6} more
                </p>
              )}
            </div>
          )}
          <button
            onClick={onView}
            style={{
              padding: '6px 12px', fontSize: 10, fontWeight: 600,
              background: 'var(--color-cream-bg)', color: 'var(--color-maroon)',
              border: 'none', borderRadius: 6, cursor: 'pointer',
            }}
          >
            View full program
          </button>
        </div>
      )}
    </div>
  );
}
