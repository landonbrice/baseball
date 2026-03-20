import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { useAuth } from '../App';
import { useChat } from '../hooks/useChatState.jsx';
import { sendChat, setNextOuting, savePlan } from '../api';

/**
 * ChatBar — persistent chat interface at bottom of every page.
 *
 * Props:
 *   onRefresh  — called when a status message signals data change
 *   todayEntry — today's log entry (to detect if already checked in)
 *   profile    — pitcher profile (for context-aware quick actions)
 */
export default function ChatBar({ onRefresh, todayEntry, profile }) {
  const { pitcherId, initData } = useAuth();
  const { messages, setMessages, addMessage, addMessages, replaceLastAndAdd } = useChat();
  const [expanded, setExpanded] = useState(false);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [checkinFlow, setCheckinFlow] = useState(null); // { step, arm_feel?, sleep_hours? }
  const [outingFlow, setOutingFlow] = useState(null); // { step, pitch_count?, post_arm_feel? }
  const [nextOutingFlow, setNextOutingFlow] = useState(false);
  const scrollRef = useRef(null);

  const hasCheckedIn = !!todayEntry?.pre_training?.arm_feel;
  const isNewPitcher = profile && !profile.active_flags?.last_outing_date && !todayEntry;
  const [welcomeSent, setWelcomeSent] = useState(false);

  // Auto-open with welcome for new pitchers
  useEffect(() => {
    if (isNewPitcher && !welcomeSent && messages.length === 0) {
      setExpanded(true);
      setMessages([{
        role: 'bot', type: 'text',
        content: `Hey ${profile?.name?.split(' ')[0] || 'there'}, I'm set up with your profile. Before I can build your first plan, I need to know — when do you next expect to pitch?`,
      }]);
      setWelcomeSent(true);
    }
  }, [isNewPitcher, welcomeSent, messages.length, profile?.name]);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  // Handle status messages from API
  const processResponse = (res) => {
    const newMsgs = [];
    for (const m of res.messages || []) {
      if (m.type === 'status') {
        onRefresh?.();
      } else {
        newMsgs.push({ role: 'bot', ...m });
      }
    }
    return newMsgs;
  };

  // Handle saving a plan from a save_plan message
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
    setExpanded(true);
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
    setExpanded(true);
    setCheckinFlow({ step: 'arm_feel' });
    setMessages(prev => [...prev, { role: 'bot', type: 'text', content: "How's the arm?" }]);
  };

  const handleArmFeel = (feel) => {
    setMessages(prev => [...prev, { role: 'user', type: 'text', content: `${feel}` }]);
    setCheckinFlow({ step: 'sleep', arm_feel: feel });
    setMessages(prev => [...prev, { role: 'bot', type: 'text', content: 'Sleep?' }]);
  };

  const handleSleep = async (hours, label) => {
    setMessages(prev => [...prev, { role: 'user', type: 'text', content: label }]);
    setCheckinFlow(null);
    setLoading(true);
    setMessages(prev => [...prev, { role: 'bot', type: 'text', content: 'Running triage and building your plan...' }]);
    try {
      const res = await sendChat(pitcherId, {
        arm_feel: checkinFlow.arm_feel,
        sleep_hours: hours,
      }, 'checkin', initData);
      setMessages(prev => {
        // Remove the "building plan" message
        const without = prev.slice(0, -1);
        return [...without, ...processResponse(res)];
      });
    } catch {
      setMessages(prev => [...prev, { role: 'bot', type: 'text', content: 'Check-in failed. Try again.' }]);
    } finally {
      setLoading(false);
    }
  };

  // ── Outing flow ──
  const startOuting = () => {
    setExpanded(true);
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
    setOutingFlow(null);
    setLoading(true);
    setMessages(prev => [...prev, { role: 'bot', type: 'text', content: 'Processing your outing...' }]);
    try {
      const res = await sendChat(pitcherId, {
        pitch_count: outingFlow.pitch_count,
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
    setExpanded(true);
    setNextOutingFlow(true);
    setMessages(prev => [...prev, { role: 'bot', type: 'text', content: 'When do you next expect to pitch?' }]);
  };

  const handleNextOutingSelect = async (days, label) => {
    setMessages(prev => [...prev, { role: 'user', type: 'text', content: label }]);
    setNextOutingFlow(false);
    setLoading(true);
    try {
      await setNextOuting(pitcherId, days, initData);
      setMessages(prev => [...prev, { role: 'bot', type: 'text', content: `Got it — outing in ${days === 0 ? 'today' : days === 1 ? 'tomorrow' : `${days} days`}. Your plan has been updated.` }]);
      onRefresh?.();
    } catch {
      setMessages(prev => [...prev, { role: 'bot', type: 'text', content: 'Failed to update. Try again.' }]);
    } finally {
      setLoading(false);
    }
  };

  // ── Quick action pills (contextual) ──
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
      setExpanded(true);
      setInput("What's my plan for today?");
    }});
  }

  // ── Determine what interactive buttons to show ──
  const renderButtons = () => {
    if (checkinFlow?.step === 'arm_feel') {
      return (
        <div style={{ display: 'flex', gap: 6, padding: '0 12px 8px' }}>
          {[1, 2, 3, 4, 5].map(n => (
            <button key={n} onClick={() => handleArmFeel(n)}
              style={{ flex: 1, padding: '8px 0', fontSize: 13, fontWeight: 600, background: 'var(--color-cream-bg)', color: 'var(--color-ink-primary)', borderRadius: 8, border: '0.5px solid var(--color-cream-border)', cursor: 'pointer' }}>
              {n}
            </button>
          ))}
        </div>
      );
    }
    if (checkinFlow?.step === 'sleep') {
      return (
        <div style={{ display: 'flex', gap: 6, padding: '0 12px 8px' }}>
          {[{ l: '<6h', v: 5.5 }, { l: '6-7h', v: 6.5 }, { l: '7-8h', v: 7.5 }, { l: '8+h', v: 8.5 }].map(o => (
            <button key={o.v} onClick={() => handleSleep(o.v, o.l)}
              style={{ flex: 1, padding: '8px 0', fontSize: 11, fontWeight: 500, background: 'var(--color-cream-bg)', color: 'var(--color-ink-primary)', borderRadius: 8, border: '0.5px solid var(--color-cream-border)', cursor: 'pointer' }}>
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

  // Whether the text input should submit to the outing pitch count handler
  const inputSubmit = outingFlow?.step === 'pitch_count' ? handlePitchCount : handleSend;
  const inputPlaceholder = outingFlow?.step === 'pitch_count'
    ? 'Pitch count...'
    : 'Ask about today\'s plan...';

  // ── Collapsed bar ──
  if (!expanded) {
    return (
      <div style={{
        position: 'fixed', bottom: 56, left: 0, right: 0, zIndex: 40,
        background: 'var(--color-white)', borderTop: '0.5px solid var(--color-cream-border)',
        paddingBottom: 'env(safe-area-inset-bottom, 0)',
      }}>
        {/* Quick actions */}
        {quickActions.length > 0 && (
          <div style={{ display: 'flex', gap: 6, padding: '8px 12px 4px', overflowX: 'auto' }}>
            {quickActions.map(qa => (
              <button key={qa.label} onClick={qa.action}
                style={{
                  padding: '4px 12px', fontSize: 11, fontWeight: 500,
                  background: 'var(--color-cream-bg)', color: 'var(--color-ink-secondary)',
                  border: '0.5px solid var(--color-cream-border)', borderRadius: 14,
                  cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0,
                }}>
                {qa.label}
              </button>
            ))}
          </div>
        )}
        {/* Input row */}
        <div style={{ display: 'flex', gap: 8, padding: '6px 12px 8px' }}>
          <input
            type="text"
            placeholder="Ask about today's plan..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onFocus={() => setExpanded(true)}
            onKeyDown={e => e.key === 'Enter' && handleSend()}
            style={{
              flex: 1, background: 'var(--color-cream-bg)', color: 'var(--color-ink-primary)',
              fontSize: 13, borderRadius: 20, padding: '8px 16px',
              border: '0.5px solid var(--color-cream-border)', outline: 'none',
            }}
          />
          <button onClick={handleSend} disabled={!input.trim() || loading}
            style={{
              width: 34, height: 34, borderRadius: '50%',
              background: !input.trim() || loading ? 'var(--color-cream-subtle)' : 'var(--color-maroon)',
              color: '#fff', border: 'none', cursor: 'pointer',
              fontSize: 14, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
            ↑
          </button>
        </div>
      </div>
    );
  }

  // ── Expanded chat ──
  return (
    <div style={{
      position: 'fixed', bottom: 56, left: 0, right: 0, zIndex: 40,
      background: 'var(--color-white)', borderTop: '0.5px solid var(--color-cream-border)',
      display: 'flex', flexDirection: 'column', height: '60vh',
      paddingBottom: 'env(safe-area-inset-bottom, 0)',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '8px 12px', borderBottom: '0.5px solid var(--color-cream-border)', flexShrink: 0,
      }}>
        <p style={{ fontSize: 11, fontWeight: 600, color: 'var(--color-ink-primary)', margin: 0 }}>Training assistant</p>
        <button onClick={() => setExpanded(false)}
          style={{ color: 'var(--color-ink-muted)', fontSize: 14, cursor: 'pointer', background: 'none', border: 'none', padding: '0 4px' }}>—</button>
      </div>

      {/* Messages */}
      <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', padding: '8px 12px' }}>
        {messages.length === 0 && (
          <p style={{ fontSize: 11, color: 'var(--color-ink-muted)', textAlign: 'center', padding: '16px 0' }}>
            Ask me anything about your training, or use the quick actions below.
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} style={{ display: 'flex', justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start', marginBottom: 8 }}>
            <div style={{
              maxWidth: '85%', borderRadius: 14, padding: '8px 12px', fontSize: 12,
              ...(m.role === 'user'
                ? { background: 'var(--color-maroon)', color: '#fff', borderBottomRightRadius: 4 }
                : { background: 'var(--color-cream-bg)', color: 'var(--color-ink-primary)', borderBottomLeftRadius: 4 }
              ),
            }}>
              {m.role === 'bot' ? (
                <div className="chat-markdown">
                  <ReactMarkdown>{m.content}</ReactMarkdown>
                </div>
              ) : (
                <p style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{m.content}</p>
              )}
              {m.type === 'save_plan' && m.plan && (
                <div style={{ marginTop: 8 }}>
                  {m.saved ? (
                    <span style={{ fontSize: 10, color: 'var(--color-flag-green)' }}>Saved — find it under Plans.</span>
                  ) : (
                    <button
                      onClick={() => handleSavePlan(m.plan, i)}
                      style={{
                        padding: '4px 10px', fontSize: 10, fontWeight: 600,
                        background: 'rgba(255,255,255,0.2)', color: '#fff',
                        border: 'none', borderRadius: 8, cursor: 'pointer',
                      }}
                    >
                      Save this plan
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 8 }}>
            <div style={{
              background: 'var(--color-cream-bg)', borderRadius: 14, padding: '8px 12px',
              fontSize: 12, color: 'var(--color-ink-muted)', borderBottomLeftRadius: 4,
            }}>
              typing...
            </div>
          </div>
        )}
      </div>

      {/* Interactive buttons */}
      {renderButtons()}

      {/* Quick actions */}
      {!checkinFlow && !outingFlow && (
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

      {/* Input */}
      <div style={{
        display: 'flex', gap: 8, padding: '6px 12px 8px',
        borderTop: '0.5px solid var(--color-cream-border)', flexShrink: 0,
      }}>
        <input
          type={outingFlow?.step === 'pitch_count' ? 'number' : 'text'}
          placeholder={inputPlaceholder}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && inputSubmit()}
          disabled={!!checkinFlow || nextOutingFlow}
          style={{
            flex: 1, background: 'var(--color-cream-bg)', color: 'var(--color-ink-primary)',
            fontSize: 13, borderRadius: 20, padding: '8px 16px',
            border: '0.5px solid var(--color-cream-border)', outline: 'none',
            opacity: (!!checkinFlow || nextOutingFlow) ? 0.5 : 1,
          }}
        />
        <button onClick={inputSubmit}
          disabled={!input.trim() || loading || !!checkinFlow || nextOutingFlow}
          style={{
            width: 34, height: 34, borderRadius: '50%',
            background: (!input.trim() || loading || !!checkinFlow || nextOutingFlow) ? 'var(--color-cream-subtle)' : 'var(--color-maroon)',
            color: '#fff', border: 'none', cursor: 'pointer',
            fontSize: 14, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
          ↑
        </button>
      </div>
    </div>
  );
}
