import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../App';
import { useAppContext } from '../hooks/useChatState';
import { useApi } from '../hooks/useApi';
import { deactivatePlan, activatePlan, applyPlanToToday } from '../api';
import DailyCard from '../components/DailyCard';

export default function PlanDetail() {
  const { planId } = useParams();
  const navigate = useNavigate();
  const { pitcherId, initData } = useAuth();
  const { addMessage } = useAppContext();
  const { data, loading, refetch } = useApi(
    pitcherId ? `/api/pitcher/${pitcherId}/plans` : null,
    initData
  );
  const { data: exerciseData } = useApi('/api/exercises', initData);
  const { data: slugData } = useApi('/api/exercises/slugs', initData);

  const plans = data?.plans || [];
  const plan = plans.find(p => p.id === planId);

  const exerciseMap = {};
  if (exerciseData?.exercises) {
    for (const ex of exerciseData.exercises) {
      exerciseMap[ex.id] = ex;
      if (ex.slug) exerciseMap[ex.slug] = ex;
    }
  }
  const slugMap = slugData || {};

  if (loading) {
    return (
      <div className="p-4 space-y-4 animate-pulse">
        <div className="h-6 bg-bg-secondary rounded w-2/3" />
        <div className="h-48 bg-bg-secondary rounded-xl" />
      </div>
    );
  }

  if (!plan) {
    return (
      <div className="p-4">
        <p style={{ color: 'var(--color-ink-muted)', fontSize: 13 }}>Plan not found.</p>
        <button onClick={() => navigate('/plans')} style={{ color: 'var(--color-maroon)', fontSize: 13, background: 'none', border: 'none', cursor: 'pointer', marginTop: 8 }}>
          Back to plans
        </button>
      </div>
    );
  }

  // Shape plan data as a daily log entry for DailyCard
  const entryData = {
    date: plan.created_date,
    arm_care: plan.arm_care || {},
    lifting: plan.lifting || {},
    throwing: plan.throwing || {},
    notes: plan.notes || [],
    plan_generated: {
      arm_care: plan.arm_care,
      lifting: plan.lifting,
      throwing: plan.throwing,
      notes: plan.notes,
    },
    completed_exercises: {},
  };

  const hasExercises = plan.lifting?.exercises?.length || plan.arm_care?.exercises?.length;

  const handleToggleActive = async () => {
    try {
      if (plan.active) {
        await deactivatePlan(pitcherId, planId, initData);
      } else {
        await activatePlan(pitcherId, planId, initData);
      }
      refetch();
    } catch { /* silent */ }
  };

  const handleAddToToday = async () => {
    try {
      await applyPlanToToday(pitcherId, planId, initData);
      navigate('/');
    } catch (e) {
      console.error('Failed to apply plan:', e);
    }
  };

  const handleAskCoach = () => {
    addMessage({
      role: 'bot', type: 'text',
      content: `You're looking at: "${plan.title}". What do you want to know?`,
    });
    navigate('/coach');
  };

  return (
    <div style={{ paddingBottom: 20 }}>
      {/* Header */}
      <div style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 8 }}>
        <button onClick={() => navigate('/plans')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-ink-muted)', fontSize: 16 }}>
          \u2190
        </button>
        <div style={{ flex: 1 }}>
          <h1 style={{ fontSize: 15, fontWeight: 700, color: 'var(--color-ink-primary)', margin: 0 }}>{plan.title}</h1>
          <p style={{ fontSize: 10, color: 'var(--color-ink-muted)', margin: 0 }}>
            {plan.category?.replace(/_/g, ' ')} \u00B7 {plan.created_date}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {hasExercises && (
            <button onClick={handleAddToToday} style={{
              padding: '4px 10px', fontSize: 10, fontWeight: 600, borderRadius: 8, border: 'none', cursor: 'pointer',
              background: 'rgba(34,197,94,0.1)', color: 'var(--color-flag-green)',
            }}>
              Add to today
            </button>
          )}
          <button onClick={handleToggleActive} style={{
            padding: '4px 10px', fontSize: 10, fontWeight: 600, borderRadius: 8, border: 'none', cursor: 'pointer',
            background: plan.active ? 'rgba(239,68,68,0.1)' : 'rgba(34,197,94,0.1)',
            color: plan.active ? 'var(--color-flag-red)' : 'var(--color-flag-green)',
          }}>
            {plan.active ? 'Deactivate' : 'Activate'}
          </button>
        </div>
      </div>

      {/* Status badges */}
      <div style={{ padding: '0 16px 8px', display: 'flex', gap: 6 }}>
        <span style={{
          fontSize: 9, padding: '2px 8px', borderRadius: 10,
          background: plan.active ? 'rgba(34,197,94,0.1)' : 'var(--color-cream-bg)',
          color: plan.active ? 'var(--color-flag-green)' : 'var(--color-ink-muted)',
          fontWeight: 600,
        }}>
          {plan.active ? 'Active' : 'Inactive'}
        </span>
        {plan.modifies_daily_plan && (
          <span style={{ fontSize: 9, padding: '2px 8px', borderRadius: 10, background: 'rgba(59,130,246,0.1)', color: '#3b82f6', fontWeight: 600 }}>
            Modifies daily plan
          </span>
        )}
      </div>

      {/* Summary */}
      {plan.summary && (
        <div style={{ padding: '0 16px 12px' }}>
          <p style={{ fontSize: 12, color: 'var(--color-ink-secondary)', margin: 0 }}>{plan.summary}</p>
        </div>
      )}

      {/* DailyCard rendering of exercises */}
      {hasExercises ? (
        <div style={{ padding: '0 16px 12px' }}>
          <DailyCard
            entry={entryData}
            exerciseMap={exerciseMap}
            slugMap={slugMap}
            pitcherId={pitcherId}
            initData={initData}
            readOnly
          />
        </div>
      ) : plan.content ? (
        <div style={{ padding: '0 16px 12px' }}>
          <div style={{ background: 'var(--color-white)', borderRadius: 12, padding: 14 }}>
            <p style={{ fontSize: 12, color: 'var(--color-ink-primary)', whiteSpace: 'pre-wrap', margin: 0 }}>{plan.content}</p>
          </div>
        </div>
      ) : null}

      {/* Ask coach about this plan */}
      <div
        onClick={handleAskCoach}
        style={{
          margin: '12px 16px', background: 'var(--color-maroon)', borderRadius: 10,
          padding: '9px 14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          cursor: 'pointer',
        }}
      >
        <span style={{ fontSize: 11, fontWeight: 700, color: '#fff' }}>Ask coach about this plan</span>
        <span style={{ color: '#e8a0aa' }}>\u2192</span>
      </div>
    </div>
  );
}
