import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import { useAuth } from '../App';
import { useAppContext } from '../hooks/useChatState';
import { usePitcher } from '../hooks/usePitcher';
import { sendChat, setNextOuting, savePlan } from '../api';

export default function Coach() {
  const { pitcherId, initData } = useAuth();
  const navigate = useNavigate();
  const {
    messages, setMessages, addMessage,
    triggerRefresh, clearCoachBadge, setCheckinInProgress,
  } = useAppContext();

  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [checkinFlow, setCheckinFlow] = useState(null);
  const [outingFlow, setOutingFlow] = useState(null);
  const [nextOutingFlow, setNextOutingFlow] = useState(false);
  const scrollRef = useRef(null);

  const { profile, log } = usePitcher(pitcherId, initData);

  const todayStr = new Date().toISOString().split('T')[0];
  const entries = log?.entries || [];
  const todayEntry = entries.find(e => e.date === todayStr);
  const hasCheckedIn = !!todayEntry?.pre_training?.arm_feel;
  const morningBrief = todayEntry?.morning_brief || todayEntry?.plan_generated?.morning_brief;
  const isNewPitcher = profile && !profile.active_flags?.last_outing_date && !todayEntry;
  const [welcomeSent, setWelcomeSent] = useState(false);

  // Clear badge when Coach tab is opened
  useEffect(() => {
    clearCoachBadge();
  }, [clearCoachBadge]);

  // Auto-open with welcome for new pitchers
  useEffect(() => {
    if (isNewPitcher && !welcomeSent && messages.length === 0) {
      setMessages([{
        role: 'bot', type: 'text',
        content: `Hey ${profile?.name?.split(' ')[0] || 'there'}, I'm set up with your profile. Before I can build your first plan, I need to know \u2014 when do you next expect to pitch?`,
      }]);
      setWelcomeSent(true);
      setNextOutingFlow(true);
    }
  }, [isNewPitcher, welcomeSent, messages.length, profile?.name]);

  // Auto-scroll
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages]);

  // Handle status messages from API
  const processResponse = (res) => {
    const newMsgs = [];
    for (const m of res.messages || []) {
      if (m.type === 'status') {
        triggerRefresh();
        if (m.content === 'plan_loaded') {
          setCheckinInProgress(false);
          newMsgs.push({
            role: 'bot',
            type: 'plan_ready',
            content: res.morning_brief || 'Your plan is ready.',
            flagLevel: res.flag_level || 'green',
          });
        }
      } else {
        newMsgs.push({ role: 'bot', ...m });
      }
    }
    return newMsgs;
  };

  // Save plan from a save_plan message
  const handleSavePlan = async (plan, msgIndex) => {
    try {
      await savePlan(pitcherId, plan, initData);
      setMessages(prev => prev.map((m, i) =>
        i === msgIndex ? { ...m, saved: true } : m
      ));
    } catch {
      // Show error inline
    }
  };

  // ── Send free-text message ──
  const handleSend = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', type: 'text', content: text }]);
    setLoading(true);
    try {
      const history = messages
        .filter(m => m.type === 'text')
        .slice(-6)
        .map(m => ({ role: m.role === 'user' ? 'user' : 'assistant', content: m.content }));
      const res = await sendChat(pitcherId, text, 'text', initData, history);
      setMessages(prev => [...prev, ...processResponse(res)]);
    } catch {
      setMessages(prev => [...prev, { role: 'bot', type: 'text', content: 'Something went wrong. Try again.' }]);
    } finally {
      setLoading(false);
    }
  };

  // ── Check-in flow ──
  const startCheckin = () => {
    setCheckinInProgress(true);
    setCheckinFlow({ step: 'arm_report' });
    const firstName = profile?.name?.split(' ')[0] || 'there';
    setMessages(prev => [...prev, { role: 'bot', type: 'text', content: `Morning ${firstName}. How's the arm feeling?` }]);
  };

  const handleArmReport = (text) => {
    setMessages(prev => [...prev, { role: 'user', type: 'text', content: text }]);
    setCheckinFlow({ step: 'lift_pref', arm_report: text });
    setMessages(prev => [...prev, { role: 'bot', type: 'text', content: 'What are you thinking for a lift today?' }]);
  };

  const handleLiftPref = (pref, label) => {
    setMessages(prev => [...prev, { role: 'user', type: 'text', content: label }]);
    setCheckinFlow(prev => ({ ...prev, step: 'throw_intent', lift_preference: pref }));
    setMessages(prev => [...prev, { role: 'bot', type: 'text', content: 'Throwing today?' }]);
  };

  const handleThrowIntent = (intent, label) => {
    setMessages(prev => [...prev, { role: 'user', type: 'text', content: label }]);
    setCheckinFlow(prev => ({ ...prev, step: 'schedule', throw_intent: intent }));
    setMessages(prev => [...prev, { role: 'bot', type: 'text', content: 'When do you pitch next?' }]);
  };

  const handleSchedule = async (days, label) => {
    setMessages(prev => [...prev, { role: 'user', type: 'text', content: label }]);
    const flowData = { ...checkinFlow };
    setCheckinFlow(null);
    setLoading(true);
    setMessages(prev => [...prev, { role: 'bot', type: 'text', content: 'Building your plan...' }]);
    try {
      const res = await sendChat(pitcherId, {
        arm_report: flowData.arm_report,
        arm_feel: null,
        lift_preference: flowData.lift_preference,
        throw_intent: flowData.throw_intent,
        next_pitch_days: days,
      }, 'checkin', initData);
      setMessages(prev => {
        const without = prev.slice(0, -1); // remove "Building your plan..."
        return [...without, ...processResponse(res)];
      });
    } catch {
      setMessages(prev => [...prev, { role: 'bot', type: 'text', content: 'Check-in failed. Try again.' }]);
      setCheckinInProgress(false);
    } finally {
      setLoading(false);
    }
  };

  // ── Outing flow ──
  const startOuting = () => {
    setOutingFlow({ step: 'pitch_count' });
    setMessages(prev => [...prev, { role: 'bot', type: 'text', content: 'How many pitches did you throw?' }]);
  };

  const handlePitchCount = () => {
    const count = parseInt(input);
    if (!count || count < 0 || count > 200) return;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', type: 'text', content: `${count}` }]);
    setOutingFlow({ step: 'arm_feel', pitch_count: count });
    setMessages(prev => [...prev, { role: 'bot', type: 'text', content: `${count} pitches. Arm feel post-outing?` }]);
  };

  const handleOutingArmFeel = async (feel) => {
    setMessages(prev => [...prev, { role: 'user', type: 'text', content: `${feel}` }]);
    const flowData = { ...outingFlow };
    setOutingFlow(null);
    setLoading(true);
    setMessages(prev => [...prev, { role: 'bot', type: 'text', content: 'Processing your outing...' }]);
    try {
      const res = await sendChat(pitcherId, {
        pitch_count: flowData.pitch_count,
        post_arm_feel: feel,
        notes: '',
      }, 'outing', initData);
      setMessages(prev => {
        const without = prev.slice(0, -1);
        return [...without, ...processResponse(res)];
      });
    } catch {
      setMessages(prev => [...prev, { role: 'bot', type: 'text', content: 'Outing report failed. Try again.' }]);
    } finally {
      setLoading(false);
    }
  };

  // ── Next outing flow ──
  const startNextOuting = () => {
    setNextOutingFlow(true);
    setMessages(prev => [...prev, { role: 'bot', type: 'text', content: 'When do you next expect to pitch?' }]);
  };

  const handleNextOutingSelect = async (days, label) => {
    setMessages(prev => [...prev, { role: 'user', type: 'text', content: label }]);
    setNextOutingFlow(false);
    setLoading(true);
    try {
      await setNextOuting(pitcherId, days, initData);
      setMessages(prev => [...prev, { role: 'bot', type: 'text', content: `Got it \u2014 outing in ${days === 0 ? 'today' : days === 1 ? 'tomorrow' : `${days} days`}. Your plan has been updated.` }]);
      triggerRefresh();
    } catch {
      setMessages(prev => [...prev, { role: 'bot', type: 'text', content: 'Failed to update. Try again.' }]);
    } finally {
      setLoading(false);
    }
  };

  // ── Quick action pills ──
  const quickActions = [];
  if (!hasCheckedIn && !checkinFlow) {
    quickActions.push({ label: 'Check in', action: startCheckin });
  }
  if (!outingFlow) {
    quickActions.push({ label: 'Log outing', action: startOuting });
  }
  if (!nextOutingFlow) {
    quickActions.push({ label: 'Next outing', action: startNextOuting });
  }
  if (hasCheckedIn) {
    quickActions.push({ label: "Today's plan", action: () => {
      setInput("What's my plan for today?");
    }});
  }

  // ── Determine what interactive buttons to show ──
  const renderButtons = () => {
    if (checkinFlow?.step === 'lift_pref') {
      return (
        <div style={{ display: 'flex', gap: 6, padding: '0 12px 8px', flexWrap: 'wrap' }}>
          {[
            { l: 'Upper', v: 'upper' }, { l: 'Lower', v: 'lower' }, { l: 'Full body', v: 'full' },
            { l: 'Rest day', v: 'rest' }, { l: 'Your call', v: 'auto' },
          ].map(o => (
            <button key={o.v} onClick={() => handleLiftPref(o.v, o.l)}
              style={{ padding: '6px 12px', fontSize: 11, fontWeight: 500, background: 'var(--color-cream-bg)', color: 'var(--color-ink-primary)', borderRadius: 8, border: '0.5px solid var(--color-cream-border)', cursor: 'pointer' }}>
              {o.l}
            </button>
          ))}
        </div>
      );
    }
    if (checkinFlow?.step === 'throw_intent') {
      return (
        <div style={{ display: 'flex', gap: 6, padding: '0 12px 8px', flexWrap: 'wrap' }}>
          {[
            { l: 'Flat ground', v: 'flat_ground' }, { l: 'Bullpen', v: 'bullpen' },
            { l: 'Long toss', v: 'long_toss' }, { l: 'Light catch', v: 'light_catch' }, { l: 'No', v: 'none' },
          ].map(o => (
            <button key={o.v} onClick={() => handleThrowIntent(o.v, o.l)}
              style={{ padding: '6px 12px', fontSize: 11, fontWeight: 500, background: 'var(--color-cream-bg)', color: 'var(--color-ink-primary)', borderRadius: 8, border: '0.5px solid var(--color-cream-border)', cursor: 'pointer' }}>
              {o.l}
            </button>
          ))}
        </div>
      );
    }
    if (checkinFlow?.step === 'schedule') {
      return (
        <div style={{ display: 'flex', gap: 6, padding: '0 12px 8px', flexWrap: 'wrap' }}>
          {[
            { l: 'Tomorrow', d: 1 }, { l: '2 days', d: 2 }, { l: '3+ days', d: 3 }, { l: 'Not sure', d: 0 },
          ].map(o => (
            <button key={o.d} onClick={() => handleSchedule(o.d, o.l)}
              style={{ padding: '6px 12px', fontSize: 11, fontWeight: 500, background: 'var(--color-cream-bg)', color: 'var(--color-ink-primary)', borderRadius: 8, border: '0.5px solid var(--color-cream-border)', cursor: 'pointer' }}>
              {o.l}
            </button>
          ))}
        </div>
      );
    }
    if (outingFlow?.step === 'arm_feel') {
      return (
        <div style={{ display: 'flex', gap: 6, padding: '0 12px 8px' }}>
          {[1, 2, 3, 4, 5].map(n => (
            <button key={n} onClick={() => handleOutingArmFeel(n)}
              style={{ flex: 1, padding: '8px 0', fontSize: 13, fontWeight: 600, background: 'var(--color-cream-bg)', color: 'var(--color-ink-primary)', borderRadius: 8, border: '0.5px solid var(--color-cream-border)', cursor: 'pointer' }}>
              {n}
            </button>
          ))}
        </div>
      );
    }
    if (nextOutingFlow) {
      return (
        <div style={{ display: 'flex', gap: 6, padding: '0 12px 8px', flexWrap: 'wrap' }}>
          {[
            { l: 'Tomorrow', d: 1 }, { l: '2 days', d: 2 }, { l: '3 days', d: 3 },
            { l: '4 days', d: 4 }, { l: '5+ days', d: 5 }, { l: 'I just pitched', d: -1 },
          ].map(o => (
            <button key={o.d} onClick={() => {
              if (o.d === -1) { setNextOutingFlow(false); startOuting(); }
              else handleNextOutingSelect(o.d, o.l);
            }}
              style={{ padding: '6px 12px', fontSize: 11, fontWeight: 500, background: 'var(--color-cream-bg)', color: 'var(--color-ink-primary)', borderRadius: 8, border: '0.5px solid var(--color-cream-border)', cursor: 'pointer' }}>
              {o.l}
            </button>
          ))}
        </div>
      );
    }
    return null;
  };

  // Route text input to the right handler
  const inputSubmit = checkinFlow?.step === 'arm_report'
    ? () => { if (input.trim()) { handleArmReport(input.trim()); setInput(''); } }
    : outingFlow?.step === 'pitch_count' ? handlePitchCount : handleSend;
  const inputPlaceholder = checkinFlow?.step === 'arm_report'
    ? "e.g. forearm's a little tight..."
    : outingFlow?.step === 'pitch_count'
    ? 'Pitch count...'
    : hasCheckedIn ? "Ask about today's plan..." : 'Ask your coach...';
  const inputDisabled = (!!checkinFlow && checkinFlow.step !== 'arm_report') || nextOutingFlow;

  const flags = profile?.active_flags || {};

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 80px)', background: 'var(--color-cream-bg)' }}>

      {/* Maroon header */}
      <div style={{ background: 'var(--color-maroon)', padding: '14px 16px 12px', flexShrink: 0 }}>
        <div style={{ fontSize: 20, fontWeight: 800, color: '#fff', letterSpacing: '-0.4px' }}>Coach</div>
        <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.45)', marginTop: 2 }}>
          {profile ? `Day ${flags.days_since_outing ?? 0} \u00B7 ${profile.role || 'pitcher'}` : ''}
        </div>
      </div>

      {/* Morning briefing card — only shows if not yet checked in today */}
      {!hasCheckedIn && morningBrief && (
        <div style={{
          margin: '10px 12px 0', background: '#fff', borderRadius: '0 10px 10px 0',
          borderLeft: '3px solid var(--color-maroon)', padding: '10px 12px', flexShrink: 0,
        }}>
          <div style={{
            fontSize: 8, fontWeight: 700, color: 'var(--color-maroon)',
            letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 4,
          }}>
            Morning briefing
          </div>
          <div style={{ fontSize: 10, color: '#4a2228', lineHeight: 1.6, fontStyle: 'italic' }}>
            {morningBrief}
          </div>
        </div>
      )}

      {/* Check-in CTA — before check-in only */}
      {!hasCheckedIn && !checkinFlow && !isNewPitcher && (
        <div
          onClick={startCheckin}
          style={{
            margin: '8px 12px 0', background: 'var(--color-maroon)', borderRadius: 10,
            padding: '9px 14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            cursor: 'pointer', flexShrink: 0,
          }}
        >
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#fff' }}>Check in to confirm your plan</div>
            <div style={{ fontSize: 8, color: 'rgba(255,255,255,0.5)' }}>30 sec \u00B7 arm feel + what you're doing today</div>
          </div>
          <span style={{ color: '#e8a0aa', fontSize: 16 }}>\u2192</span>
        </div>
      )}

      {/* Message thread */}
      <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        {messages.length === 0 && hasCheckedIn && (
          <div style={{ textAlign: 'center', fontSize: 10, color: '#b0a89e', paddingTop: 20 }}>
            Plan's loaded. Ask anything about today.
          </div>
        )}
        {messages.length === 0 && !hasCheckedIn && !isNewPitcher && (
          <div style={{ textAlign: 'center', fontSize: 10, color: '#b0a89e', paddingTop: 20 }}>
            Check in above, or ask anything.
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} style={{ display: 'flex', flexDirection: 'column',
            alignItems: m.role === 'user' ? 'flex-end' : 'flex-start' }}>
            {/* Plan CTA — special message type after check-in */}
            {m.type === 'plan_ready' ? (
              <div style={{
                background: '#fff', borderRadius: '0 10px 10px 3px',
                borderLeft: '2px solid #1D9E75', padding: '8px 10px', maxWidth: '92%',
                border: '0.5px solid #e4dfd8',
              }}>
                <div style={{
                  fontSize: 8, fontWeight: 700, color: '#1D9E75',
                  letterSpacing: '0.05em', textTransform: 'uppercase', marginBottom: 3,
                }}>
                  {(m.flagLevel || 'green').toUpperCase()} \u00B7 plan ready
                </div>
                <div style={{ fontSize: 10, color: '#2a1a18', lineHeight: 1.5, marginBottom: 7 }}>
                  {m.content}
                </div>
                <div
                  onClick={() => navigate('/')}
                  style={{
                    background: 'var(--color-maroon)', borderRadius: 7, padding: '5px 9px',
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer',
                  }}
                >
                  <span style={{ fontSize: 9, fontWeight: 700, color: '#fff' }}>Open today's plan</span>
                  <span style={{ color: '#e8a0aa', fontSize: 11 }}>\u2192</span>
                </div>
              </div>
            ) : (
              <div style={{
                maxWidth: '88%', borderRadius: m.role === 'user' ? '14px 14px 3px 14px' : '14px 14px 14px 3px',
                padding: '7px 10px', fontSize: 10, lineHeight: 1.55,
                background: m.role === 'user' ? 'var(--color-maroon)' : '#fff',
                color: m.role === 'user' ? '#fff' : '#1a0a0d',
                border: m.role === 'user' ? 'none' : '0.5px solid #e4dfd8',
              }}>
                {m.role === 'bot' ? (
                  <div className="chat-markdown"><ReactMarkdown>{m.content}</ReactMarkdown></div>
                ) : (
                  <p style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{m.content}</p>
                )}
                {/* Save plan button */}
                {m.type === 'save_plan' && m.plan && (
                  <div style={{ marginTop: 8 }}>
                    {m.saved ? (
                      <span style={{ fontSize: 10, color: 'var(--color-flag-green)' }}>Saved \u2014 find it under Plans.</span>
                    ) : (
                      <button onClick={() => handleSavePlan(m.plan, i)}
                        style={{
                          padding: '4px 10px', fontSize: 10, fontWeight: 600,
                          background: 'rgba(92,16,32,0.1)', color: 'var(--color-maroon)',
                          border: '0.5px solid var(--color-maroon)', borderRadius: 6, cursor: 'pointer',
                        }}>
                        Save this plan
                      </button>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div style={{
            alignSelf: 'flex-start', background: '#fff', borderRadius: '14px 14px 14px 3px',
            padding: '7px 10px', fontSize: 10, color: '#b0a89e', border: '0.5px solid #e4dfd8',
          }}>
            ...
          </div>
        )}
      </div>

      {/* Interactive buttons */}
      {renderButtons()}

      {/* Quick actions — show when not in a flow */}
      {!checkinFlow && !outingFlow && !nextOutingFlow && quickActions.length > 0 && (
        <div style={{ display: 'flex', gap: 6, padding: '4px 12px', overflowX: 'auto', flexShrink: 0 }}>
          {quickActions.map(qa => (
            <button key={qa.label} onClick={qa.action}
              style={{
                padding: '3px 10px', fontSize: 10, fontWeight: 500,
                background: 'var(--color-cream-bg)', color: 'var(--color-ink-muted)',
                border: '0.5px solid var(--color-cream-border)', borderRadius: 12,
                cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0,
              }}>
              {qa.label}
            </button>
          ))}
        </div>
      )}

      {/* Input — always visible */}
      <div style={{
        padding: '7px 12px', background: '#fff', borderTop: '0.5px solid #e4dfd8',
        paddingBottom: 'calc(7px + env(safe-area-inset-bottom, 0))', flexShrink: 0,
      }}>
        <div style={{
          background: '#f5f1eb', borderRadius: 20, padding: '7px 12px',
          display: 'flex', alignItems: 'center', gap: 8, border: '0.5px solid #e4dfd8',
        }}>
          <input
            type={outingFlow?.step === 'pitch_count' ? 'number' : 'text'}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && inputSubmit()}
            placeholder={inputPlaceholder}
            disabled={inputDisabled}
            style={{
              flex: 1, background: 'transparent', border: 'none', outline: 'none',
              fontSize: 11, color: 'var(--color-ink-primary)',
              opacity: inputDisabled ? 0.5 : 1,
            }}
          />
          <div
            onClick={() => !inputDisabled && inputSubmit()}
            style={{
              width: 20, height: 20, borderRadius: '50%', background: 'var(--color-maroon)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
              flexShrink: 0, opacity: input.trim() && !inputDisabled ? 1 : 0.4,
            }}
          >
            <span style={{ color: '#fff', fontSize: 9 }}>\u2191</span>
          </div>
        </div>
      </div>
    </div>
  );
}
