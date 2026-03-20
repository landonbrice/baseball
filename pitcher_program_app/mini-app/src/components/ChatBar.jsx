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

    // Build conversation history from existing messages for multi-turn context
    const history = messages
      .filter(m => m.type === 'text')
      .slice(-6)
      .map(m => ({
        role: m.role === 'user' ? 'user' : 'assistant',
        content: m.content,
      }));

    setMessages(prev => [...prev, { role: 'user', type: 'text', content: text }]);
    setLoading(true);
    try {
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
        <div className="flex gap-1.5 px-3 pb-2">
          {[1, 2, 3, 4, 5].map(n => (
            <button key={n} onClick={() => handleArmFeel(n)}
              className="flex-1 py-2 text-sm font-medium bg-bg-tertiary text-text-primary rounded-lg hover:bg-accent-blue/20 transition-colors">
              {n}
            </button>
          ))}
        </div>
      );
    }
    if (checkinFlow?.step === 'sleep') {
      return (
        <div className="flex gap-1.5 px-3 pb-2">
          {[{ l: '<6h', v: 5.5 }, { l: '6-7h', v: 6.5 }, { l: '7-8h', v: 7.5 }, { l: '8+h', v: 8.5 }].map(o => (
            <button key={o.v} onClick={() => handleSleep(o.v, o.l)}
              className="flex-1 py-2 text-xs font-medium bg-bg-tertiary text-text-primary rounded-lg hover:bg-accent-blue/20 transition-colors">
              {o.l}
            </button>
          ))}
        </div>
      );
    }
    if (outingFlow?.step === 'arm_feel') {
      return (
        <div className="flex gap-1.5 px-3 pb-2">
          {[1, 2, 3, 4, 5].map(n => (
            <button key={n} onClick={() => handleOutingArmFeel(n)}
              className="flex-1 py-2 text-sm font-medium bg-bg-tertiary text-text-primary rounded-lg hover:bg-accent-blue/20 transition-colors">
              {n}
            </button>
          ))}
        </div>
      );
    }
    if (nextOutingFlow) {
      return (
        <div className="flex gap-1.5 px-3 pb-2 flex-wrap">
          {[
            { l: 'Tomorrow', d: 1 }, { l: '2 days', d: 2 }, { l: '3 days', d: 3 },
            { l: '4 days', d: 4 }, { l: '5+ days', d: 5 }, { l: 'I just pitched', d: -1 },
          ].map(o => (
            <button key={o.d} onClick={() => {
              if (o.d === -1) { setNextOutingFlow(false); startOuting(); }
              else handleNextOutingSelect(o.d, o.l);
            }}
              className="px-3 py-1.5 text-xs font-medium bg-bg-tertiary text-text-primary rounded-lg hover:bg-accent-blue/20 transition-colors">
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
    : 'Message your bot...';

  // ── Collapsed bar ──
  if (!expanded) {
    return (
      <div className="fixed bottom-16 left-0 right-0 bg-bg-primary border-t border-bg-tertiary z-40"
           style={{ paddingBottom: 'env(safe-area-inset-bottom, 0)' }}>
        {/* Quick actions */}
        {quickActions.length > 0 && (
          <div className="flex gap-1.5 px-3 pt-2 pb-1 overflow-x-auto scrollbar-none">
            {quickActions.map(qa => (
              <button key={qa.label} onClick={qa.action}
                className="px-3 py-1 text-xs font-medium bg-bg-secondary text-text-primary rounded-full whitespace-nowrap hover:bg-bg-tertiary transition-colors">
                {qa.label}
              </button>
            ))}
          </div>
        )}
        {/* Input row */}
        <div className="flex gap-2 px-3 py-2">
          <input
            type="text"
            placeholder="Message your bot..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onFocus={() => setExpanded(true)}
            onKeyDown={e => e.key === 'Enter' && handleSend()}
            className="flex-1 bg-bg-secondary text-text-primary text-sm rounded-full px-4 py-2 border border-bg-tertiary focus:border-accent-blue focus:outline-none"
          />
          <button onClick={handleSend} disabled={!input.trim() || loading}
            className="px-3 py-2 text-xs font-medium bg-accent-blue text-white rounded-full disabled:opacity-40 transition-colors">
            →
          </button>
        </div>
      </div>
    );
  }

  // ── Expanded chat ──
  return (
    <div className="fixed bottom-16 left-0 right-0 bg-bg-primary border-t border-bg-tertiary z-40 flex flex-col"
         style={{ height: '60vh', paddingBottom: 'env(safe-area-inset-bottom, 0)' }}>
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-bg-tertiary flex-shrink-0">
        <p className="text-xs font-medium text-text-primary">Training assistant</p>
        <button onClick={() => setExpanded(false)} className="text-text-muted text-sm px-1">—</button>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-2 space-y-2">
        {messages.length === 0 && (
          <p className="text-xs text-text-muted text-center py-4">
            Ask me anything about your training, or use the quick actions below.
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] rounded-xl px-3 py-2 text-xs ${
              m.role === 'user'
                ? 'bg-accent-blue text-white rounded-br-sm'
                : 'bg-bg-secondary text-text-primary rounded-bl-sm'
            }`}>
              {m.role === 'bot' ? (
                <ReactMarkdown className="chat-markdown">{m.content}</ReactMarkdown>
              ) : (
                <p className="whitespace-pre-wrap">{m.content}</p>
              )}
              {m.type === 'save_plan' && m.plan && (
                <div className="mt-2">
                  {m.saved ? (
                    <span className="text-[10px] text-flag-green">Saved — find it under Plans.</span>
                  ) : (
                    <button
                      onClick={() => handleSavePlan(m.plan, i)}
                      className="px-2 py-1 text-[10px] font-medium bg-accent-blue/20 text-accent-blue rounded-md hover:bg-accent-blue/30 transition-colors"
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
          <div className="flex justify-start">
            <div className="bg-bg-secondary rounded-xl px-3 py-2 text-xs text-text-muted rounded-bl-sm">
              typing...
            </div>
          </div>
        )}
      </div>

      {/* Interactive buttons (arm feel, sleep, etc.) */}
      {renderButtons()}

      {/* Quick actions */}
      {!checkinFlow && !outingFlow && (
        <div className="flex gap-1.5 px-3 py-1 overflow-x-auto scrollbar-none flex-shrink-0">
          {quickActions.map(qa => (
            <button key={qa.label} onClick={qa.action}
              className="px-3 py-1 text-[10px] font-medium bg-bg-secondary text-text-muted rounded-full whitespace-nowrap hover:bg-bg-tertiary transition-colors">
              {qa.label}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="flex gap-2 px-3 py-2 border-t border-bg-tertiary flex-shrink-0">
        <input
          type={outingFlow?.step === 'pitch_count' ? 'number' : 'text'}
          placeholder={inputPlaceholder}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && inputSubmit()}
          disabled={!!checkinFlow || nextOutingFlow}
          className="flex-1 bg-bg-secondary text-text-primary text-sm rounded-full px-4 py-2 border border-bg-tertiary focus:border-accent-blue focus:outline-none disabled:opacity-50"
        />
        <button onClick={inputSubmit} disabled={!input.trim() || loading || !!checkinFlow || nextOutingFlow}
          className="px-3 py-2 text-xs font-medium bg-accent-blue text-white rounded-full disabled:opacity-40 transition-colors">
          →
        </button>
      </div>
    </div>
  );
}
