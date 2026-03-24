import { useState, useRef, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import { useAuth } from '../App';
import { useApi } from '../hooks/useApi';
import { sendChatWithPlan, deactivatePlan, activatePlan, applyPlanToToday } from '../api';
import DailyCard from '../components/DailyCard';

export default function PlanDetail() {
  const { planId } = useParams();
  const navigate = useNavigate();
  const { pitcherId, initData } = useAuth();
  const { data, loading, refetch } = useApi(
    pitcherId ? `/api/pitcher/${pitcherId}/plans` : null,
    initData
  );
  const { data: exerciseData } = useApi('/api/exercises', initData);
  const { data: slugData } = useApi('/api/exercises/slugs', initData);

  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const scrollRef = useRef(null);

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

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages]);

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

  const handleSend = async () => {
    const text = input.trim();
    if (!text || chatLoading) return;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: text }]);
    setChatLoading(true);
    try {
      const history = messages.slice(-6).map(m => ({
        role: m.role === 'user' ? 'user' : 'assistant',
        content: m.content,
      }));
      const res = await sendChatWithPlan(pitcherId, text, {
        plan_id: planId,
        plan_data: plan,
      }, initData, history);
      for (const m of res.messages || []) {
        if (m.type === 'status' && (m.content === 'plan_updated' || m.content === 'plan_loaded')) {
          refetch();
        } else if (m.type === 'text') {
          setMessages(prev => [...prev, { role: 'bot', content: m.content }]);
        }
      }
    } catch {
      setMessages(prev => [...prev, { role: 'bot', content: 'Something went wrong. Try again.' }]);
    } finally {
      setChatLoading(false);
    }
  };

  return (
    <div style={{ paddingBottom: chatOpen ? '55vh' : 120 }}>
      {/* Header */}
      <div style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 8 }}>
        <button onClick={() => navigate('/plans')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-ink-muted)', fontSize: 16 }}>
          ←
        </button>
        <div style={{ flex: 1 }}>
          <h1 style={{ fontSize: 15, fontWeight: 700, color: 'var(--color-ink-primary)', margin: 0 }}>{plan.title}</h1>
          <p style={{ fontSize: 10, color: 'var(--color-ink-muted)', margin: 0 }}>
            {plan.category?.replace(/_/g, ' ')} · {plan.created_date}
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

      {/* Chat section */}
      <div style={{
        position: 'fixed', bottom: 56, left: 0, right: 0, zIndex: 40,
        background: 'var(--color-white)', borderTop: '0.5px solid var(--color-cream-border)',
        display: 'flex', flexDirection: 'column',
        height: chatOpen ? '50vh' : 'auto',
        paddingBottom: 'env(safe-area-inset-bottom, 0)',
      }}>
        {chatOpen && (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 12px', borderBottom: '0.5px solid var(--color-cream-border)', flexShrink: 0 }}>
              <p style={{ fontSize: 11, fontWeight: 600, color: 'var(--color-ink-primary)', margin: 0 }}>Modify this plan</p>
              <button onClick={() => setChatOpen(false)} style={{ color: 'var(--color-ink-muted)', fontSize: 14, cursor: 'pointer', background: 'none', border: 'none' }}>—</button>
            </div>
            <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', padding: '8px 12px' }}>
              {messages.length === 0 && (
                <p style={{ fontSize: 11, color: 'var(--color-ink-muted)', textAlign: 'center', padding: 16 }}>
                  Ask to swap exercises, adjust sets, or change the focus.
                </p>
              )}
              {messages.map((m, i) => (
                <div key={i} style={{ display: 'flex', justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start', marginBottom: 8 }}>
                  <div style={{
                    maxWidth: '85%', borderRadius: 14, padding: '8px 12px', fontSize: 12,
                    ...(m.role === 'user'
                      ? { background: 'var(--color-maroon)', color: '#fff', borderBottomRightRadius: 4 }
                      : { background: 'var(--color-cream-bg)', color: 'var(--color-ink-primary)', borderBottomLeftRadius: 4 }),
                  }}>
                    {m.role === 'bot' ? (
                      <div className="chat-markdown"><ReactMarkdown>{m.content}</ReactMarkdown></div>
                    ) : (
                      <p style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{m.content}</p>
                    )}
                  </div>
                </div>
              ))}
              {chatLoading && (
                <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 8 }}>
                  <div style={{ background: 'var(--color-cream-bg)', borderRadius: 14, padding: '8px 12px', fontSize: 12, color: 'var(--color-ink-muted)', borderBottomLeftRadius: 4 }}>
                    typing...
                  </div>
                </div>
              )}
            </div>
          </>
        )}
        <div style={{ display: 'flex', gap: 8, padding: '6px 12px 8px', borderTop: chatOpen ? '0.5px solid var(--color-cream-border)' : 'none', flexShrink: 0 }}>
          <input
            type="text"
            placeholder="Swap exercises, adjust sets..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onFocus={() => setChatOpen(true)}
            onKeyDown={e => e.key === 'Enter' && handleSend()}
            style={{
              flex: 1, background: 'var(--color-cream-bg)', color: 'var(--color-ink-primary)',
              fontSize: 13, borderRadius: 20, padding: '8px 16px',
              border: '0.5px solid var(--color-cream-border)', outline: 'none',
            }}
          />
          <button onClick={handleSend} disabled={!input.trim() || chatLoading}
            style={{
              width: 34, height: 34, borderRadius: '50%',
              background: !input.trim() || chatLoading ? 'var(--color-cream-subtle)' : 'var(--color-maroon)',
              color: '#fff', border: 'none', cursor: 'pointer',
              fontSize: 14, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
            ↑
          </button>
        </div>
      </div>
    </div>
  );
}
