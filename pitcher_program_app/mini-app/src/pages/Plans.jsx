import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../App';
import { useApi } from '../hooks/useApi';
import { deactivatePlan } from '../api';
import ChatBar from '../components/ChatBar';
import PlanBuilder from '../components/PlanBuilder';

export default function Plans() {
  const { pitcherId, initData } = useAuth();
  const navigate = useNavigate();
  const { data, loading, error, refetch } = useApi(
    pitcherId ? `/api/pitcher/${pitcherId}/plans` : null,
    initData
  );

  const [showBuilder, setShowBuilder] = useState(false);

  const plans = data?.plans || [];
  const activePlans = plans.filter(p => p.active);
  const pastPlans = plans.filter(p => !p.active);

  const handleDeactivate = async (planId, e) => {
    e.stopPropagation();
    try {
      await deactivatePlan(pitcherId, planId, initData);
      refetch();
    } catch {
      // silently fail
    }
  };

  if (loading) {
    return (
      <div className="p-4 space-y-4 animate-pulse">
        <div className="h-6 bg-bg-secondary rounded w-1/3" />
        <div className="h-24 bg-bg-secondary rounded-xl" />
        <div className="h-24 bg-bg-secondary rounded-xl" />
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4 pb-28">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1 className="text-lg font-bold text-text-primary" style={{ margin: 0 }}>Plans</h1>
      </div>

      {/* New plan button */}
      <button
        onClick={() => setShowBuilder(true)}
        style={{
          width: '100%', padding: 12, borderRadius: 12,
          background: 'var(--color-maroon)', color: '#fff',
          fontSize: 13, fontWeight: 500, border: 'none', cursor: 'pointer',
        }}
      >
        + New plan
      </button>

      {plans.length === 0 && (
        <div className="bg-bg-secondary rounded-xl p-4 text-center">
          <p className="text-sm text-text-muted">No saved plans yet.</p>
          <p className="text-xs text-text-muted mt-1">
            Generate one above, or ask the bot for a program — it'll offer to save it here.
          </p>
        </div>
      )}

      {activePlans.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-text-secondary mb-2">Active</h2>
          <div className="space-y-2">
            {activePlans.map(plan => (
              <PlanCard
                key={plan.id}
                plan={plan}
                onClick={() => navigate(`/plans/${plan.id}`)}
                onDeactivate={(e) => handleDeactivate(plan.id, e)}
              />
            ))}
          </div>
        </div>
      )}

      {pastPlans.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-text-muted mb-2">Past</h2>
          <div className="space-y-2">
            {pastPlans.map(plan => (
              <PlanCard
                key={plan.id}
                plan={plan}
                onClick={() => navigate(`/plans/${plan.id}`)}
              />
            ))}
          </div>
        </div>
      )}

      <ChatBar />

      {showBuilder && <PlanBuilder onClose={() => { setShowBuilder(false); refetch(); }} />}
    </div>
  );
}

function PlanCard({ plan, onClick, onDeactivate }) {
  // Exercise preview
  const exercises = plan.lifting?.exercises || [];
  const previewNames = exercises.slice(0, 3).map(ex => ex.name || ex.exercise_id?.replace('ex_', ''));
  const moreCount = Math.max(0, exercises.length - 3);
  const previewText = previewNames.length
    ? previewNames.join(', ') + (moreCount > 0 ? ` + ${moreCount} more` : '')
    : null;

  return (
    <div
      onClick={onClick}
      style={{ cursor: 'pointer' }}
      className="bg-bg-secondary rounded-xl overflow-hidden"
    >
      <div className="w-full text-left px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-text-primary truncate">{plan.title}</p>
            <p className="text-[10px] text-text-muted mt-0.5">
              {plan.category?.replace(/_/g, ' ')} · {plan.created_date}
              {plan.expires_date && ` · expires ${plan.expires_date}`}
            </p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
            {plan.modifies_daily_plan && (
              <span className="text-[9px] bg-accent-blue/10 text-accent-blue px-1.5 py-0.5 rounded-full">
                modifies plan
              </span>
            )}
            <span style={{ color: 'var(--color-ink-faint)', fontSize: 14 }}>›</span>
          </div>
        </div>
        {previewText && (
          <p style={{ fontSize: 11, color: 'var(--color-ink-muted)', marginTop: 4 }}>{previewText}</p>
        )}
        {!previewText && plan.summary && (
          <p className="text-xs text-text-secondary mt-1 line-clamp-2">{plan.summary}</p>
        )}
      </div>
    </div>
  );
}
