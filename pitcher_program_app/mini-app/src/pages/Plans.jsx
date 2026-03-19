import { useState } from 'react';
import { useAuth } from '../App';
import { useApi } from '../hooks/useApi';
import { deactivatePlan } from '../api';
import ChatBar from '../components/ChatBar';

export default function Plans() {
  const { pitcherId, initData } = useAuth();
  const { data, loading, error, refetch } = useApi(
    pitcherId ? `/api/pitcher/${pitcherId}/plans` : null,
    initData
  );

  const [expandedId, setExpandedId] = useState(null);

  const plans = data?.plans || [];
  const activePlans = plans.filter(p => p.active);
  const pastPlans = plans.filter(p => !p.active);

  const handleDeactivate = async (planId) => {
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
      <h1 className="text-lg font-bold text-text-primary">Saved Plans</h1>

      {plans.length === 0 && (
        <div className="bg-bg-secondary rounded-xl p-4 text-center">
          <p className="text-sm text-text-muted">No saved plans yet.</p>
          <p className="text-xs text-text-muted mt-1">
            Ask your bot for a program or progression — it'll offer to save it here.
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
                expanded={expandedId === plan.id}
                onToggle={() => setExpandedId(prev => prev === plan.id ? null : plan.id)}
                onDeactivate={() => handleDeactivate(plan.id)}
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
                expanded={expandedId === plan.id}
                onToggle={() => setExpandedId(prev => prev === plan.id ? null : plan.id)}
              />
            ))}
          </div>
        </div>
      )}

      <ChatBar />
    </div>
  );
}

function PlanCard({ plan, expanded, onToggle, onDeactivate }) {
  return (
    <div className="bg-bg-secondary rounded-xl overflow-hidden">
      <button onClick={onToggle} className="w-full text-left px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-text-primary truncate">{plan.title}</p>
            <p className="text-[10px] text-text-muted mt-0.5">
              {plan.category?.replace(/_/g, ' ')} · {plan.created_date}
              {plan.expires_date && ` · expires ${plan.expires_date}`}
            </p>
          </div>
          {plan.modifies_daily_plan && (
            <span className="text-[9px] bg-accent-blue/10 text-accent-blue px-1.5 py-0.5 rounded-full ml-2 flex-shrink-0">
              modifies plan
            </span>
          )}
        </div>
        {!expanded && plan.summary && (
          <p className="text-xs text-text-secondary mt-1 line-clamp-2">{plan.summary}</p>
        )}
      </button>

      {expanded && (
        <div className="px-4 pb-3 border-t border-bg-tertiary pt-2">
          {plan.summary && (
            <p className="text-xs text-text-secondary mb-2">{plan.summary}</p>
          )}
          <p className="text-xs text-text-primary whitespace-pre-wrap">{plan.content}</p>
          {onDeactivate && plan.active && (
            <button
              onClick={(e) => { e.stopPropagation(); onDeactivate(); }}
              className="mt-3 px-3 py-1 text-[10px] font-medium text-flag-red bg-flag-red/10 rounded-md"
            >
              Deactivate
            </button>
          )}
        </div>
      )}
    </div>
  );
}
