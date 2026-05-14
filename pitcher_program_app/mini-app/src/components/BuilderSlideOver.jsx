/**
 * BuilderSlideOver — Program Builder funnel (Plan 6 / B3).
 *
 * Three states inside one bottom-sheet:
 *   - INPUTS:   form collects {domain, goal, duration_weeks, effective_phase,
 *               hard_constraints}. Continue → /candidates → SOCRATIC.
 *   - SOCRATIC: Coach-style chat. /turn loop until {kind: "ready", ...}.
 *               "I don't know — you decide" tap on every AI turn.
 *   - PREVIEW:  shows the generated program + research citations + expandable
 *               day timeline. Activate / Save as draft / Tweak buttons.
 *               Tweak → SOCRATIC with regen counter (cap 3, warn at 2).
 *
 * Wires to the existing builder endpoints. Pure UI orchestration — all
 * business logic stays server-side.
 */
import { useState, useEffect, useRef } from 'react';
import { useAuth } from '../App';
import {
  fetchBuilderCandidates,
  sendBuilderTurn,
  finalizeBuilder,
  activateProgram,
  archiveProgram,
  interpretGoal,
} from '../api';

const DOMAINS = [
  { id: 'throwing', label: 'Throwing' },
  { id: 'lifting',  label: 'Lifting'  },
];

// Goal chips map 1:1 to block_library.goal_tags. Selecting a chip sends the
// exact tag string the matcher expects. Pitchers don't see / type tag IDs.
// New tags added to block_library should be added here (and gated by domain).
const GOALS_THROWING = [
  { id: 'in_season_maintenance', label: 'In-season maintenance' },
  { id: 'velocity',              label: 'Velocity'              },
  { id: 'longtoss',              label: 'Long toss'             },
  { id: 'arm_health',            label: 'Arm health / return'   },
  { id: 'offseason_base',        label: 'Off-season base'       },
  { id: '__other__',             label: 'Other / describe…'     },
];
// Plan 7 / A13 seeded two lifting templates:
//   hypertrophy_8wk_v1            → goal_tags: hypertrophy, muscle_growth, size
//   in_season_lifting_starter_v1  → goal_tags: in_season_lifting, strength_maintain,
//                                              minimum_effective_dose
// We surface one user-facing chip per template's primary tag, plus a shared
// strength-maintenance chip and the standard Other escape hatch.
const GOALS_LIFTING = [
  { id: 'hypertrophy',       label: 'Hypertrophy'          },
  { id: 'strength_maintain', label: 'Strength maintenance' },
  { id: 'in_season_lifting', label: 'In-season lifting'    },
  { id: '__other__',         label: 'Other / describe…'    },
];

const DURATIONS = [
  { id: 4,  label: '4 wk'  },
  { id: 6,  label: '6 wk'  },
  { id: 8,  label: '8 wk'  },
  { id: 12, label: '12 wk' },
  { id: 16, label: '16 wk' },
];

const PHASES = [
  { id: 'off_season', label: 'Off-season' },
  { id: 'preseason',  label: 'Preseason'  },
  { id: 'in_season',  label: 'In-season'  },
  { id: 'postseason', label: 'Postseason' },
];

const HARD_CONSTRAINTS = [
  { id: 'no_max_effort', label: 'No max effort' },
  { id: 'no_overhead',   label: 'No overhead'   },
  { id: 'short_session', label: 'Short session' },
  { id: 'rehab',         label: 'Rehab'         },
];

const REGEN_CAP = 3;
const REGEN_WARN = 2;

// Public so tests can drive the state machine directly.
export const BUILDER_STATES = {
  INPUTS:   'inputs',
  SOCRATIC: 'socratic',
  PREVIEW:  'preview',
};

const chipStyle = (selected) => ({
  padding: '6px 14px',
  fontSize: 11,
  fontWeight: selected ? 600 : 400,
  background: selected ? 'var(--color-maroon)' : 'transparent',
  color: selected ? '#fff' : 'var(--color-ink-secondary)',
  border: selected ? 'none' : '0.5px solid var(--color-cream-border)',
  borderRadius: 14,
  cursor: 'pointer',
  whiteSpace: 'nowrap',
  flexShrink: 0,
});

const sectionLabelStyle = {
  fontSize: 10,
  fontWeight: 600,
  color: 'var(--color-ink-faint)',
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
  marginBottom: 6,
};

const primaryButtonStyle = (disabled) => ({
  width: '100%',
  padding: '12px 16px',
  fontSize: 13,
  fontWeight: 600,
  background: disabled ? 'var(--color-cream-subtle, #d6d0c8)' : 'var(--color-maroon)',
  color: '#fff',
  border: 'none',
  borderRadius: 10,
  cursor: disabled ? 'not-allowed' : 'pointer',
});

const secondaryButtonStyle = {
  flex: 1,
  padding: '10px 14px',
  fontSize: 12,
  fontWeight: 600,
  background: 'transparent',
  color: 'var(--color-maroon)',
  border: '0.5px solid var(--color-maroon)',
  borderRadius: 8,
  cursor: 'pointer',
};

export default function BuilderSlideOver({ onClose, onProgramActivated, onDraftSaved, initialDomain = 'throwing' }) {
  const { pitcherId, initData } = useAuth();
  const [state, setState] = useState(BUILDER_STATES.INPUTS);
  const [error, setError] = useState(null);

  // INPUTS state
  const [domain, setDomain]                       = useState(
    initialDomain === 'lifting' || initialDomain === 'throwing' ? initialDomain : 'throwing'
  );
  const [goal, setGoal]                           = useState(null);  // chip id or null
  const [goalText, setGoalText]                   = useState('');    // free-text when goal === '__other__'
  const [durationWeeks, setDurationWeeks]         = useState(12);
  const [effectivePhase, setEffectivePhase]       = useState('in_season');
  const [hardConstraints, setHardConstraints]     = useState([]);
  const [submittingInputs, setSubmittingInputs]   = useState(false);

  // SOCRATIC state
  const [sessionId, setSessionId]                 = useState(null);
  const [messages, setMessages]                   = useState([]); // [{role: 'user'|'bot', content}]
  const [chatInput, setChatInput]                 = useState('');
  const [chatLoading, setChatLoading]             = useState(false);
  const [readyPayload, setReadyPayload]           = useState(null); // {chosen_template_id, tuned_spec}
  const chatScrollRef = useRef(null);

  // PREVIEW state
  const [program, setProgram]                     = useState(null);
  const [citations, setCitations]                 = useState([]);
  const [timelineOpen, setTimelineOpen]           = useState(false);
  const [regenCount, setRegenCount]               = useState(0);
  const [finalizing, setFinalizing]               = useState(false);

  // Auto-scroll chat to bottom when messages change
  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [messages]);

  const toggleConstraint = (id) => {
    setHardConstraints(prev =>
      prev.includes(id) ? prev.filter(c => c !== id) : [...prev, id]
    );
  };

  // ---- State A → State B ----
  const handleContinue = async () => {
    setError(null);
    if (!goal) {
      setError('Pick a goal to continue.');
      return;
    }
    // "Other / describe…" → resolve via LLM interpreter before /candidates.
    // Empty text short-circuits without an API call.
    if (goal === '__other__' && !goalText.trim()) {
      setError('Describe your goal to continue.');
      return;
    }
    setSubmittingInputs(true);
    try {
      let resolvedGoal = goal;
      if (goal === '__other__') {
        try {
          const res = await interpretGoal(goalText.trim(), domain, initData);
          if (!res || res.confidence === 'unknown') {
            setError("I couldn't match that goal. Try a chip above or rephrase.");
            return;
          }
          resolvedGoal = res.tag;
        } catch (e) {
          setError(e?.detail || 'Could not reach the goal interpreter. Try again.');
          return;
        }
      }
      const res = await fetchBuilderCandidates({
        domain,
        goal: resolvedGoal,  // chip id (or interpreter-resolved tag) — already matches a real goal_tag
        duration_weeks: durationWeeks,
        effective_phase: effectivePhase,
        hard_constraints: hardConstraints,
      }, initData);
      if (!res.candidates || res.candidates.length === 0) {
        setError('No templates match those inputs. Try a different goal, duration, or phase.');
        return;
      }
      setSessionId(res.session_id);
      setState(BUILDER_STATES.SOCRATIC);
      // Kick off Socratic with an empty user_message so the LLM opens.
      await sendTurn(res.session_id, '');
    } catch (e) {
      setError(e?.detail || 'Could not fetch candidates. Try again.');
    } finally {
      setSubmittingInputs(false);
    }
  };

  // ---- Socratic turn helper ----
  const sendTurn = async (sid, userMessage) => {
    setChatLoading(true);
    try {
      if (userMessage) {
        setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
      }
      const res = await sendBuilderTurn(sid, userMessage, initData);
      if (res.kind === 'question') {
        setMessages(prev => [...prev, { role: 'bot', content: res.text }]);
      } else if (res.kind === 'ready') {
        setReadyPayload({
          chosen_template_id: res.chosen_template_id,
          tuned_spec: res.tuned_spec,
        });
        setMessages(prev => [...prev,
          { role: 'bot', content: 'Got it — let me draft a program for you.' }]);
      }
    } catch (e) {
      setError(e?.detail || 'Chat error. Try again.');
    } finally {
      setChatLoading(false);
    }
  };

  const handleSendChat = async () => {
    if (!chatInput.trim() || chatLoading) return;
    const msg = chatInput.trim();
    setChatInput('');
    await sendTurn(sessionId, msg);
  };

  const handleIDontKnow = async () => {
    if (chatLoading) return;
    await sendTurn(sessionId, "I don't know — you decide.");
  };

  // ---- State B → State C ----
  const handleFinalize = async () => {
    if (!readyPayload) return;
    setFinalizing(true);
    setError(null);
    try {
      const res = await finalizeBuilder(
        sessionId,
        readyPayload.chosen_template_id,
        readyPayload.tuned_spec,
        initData,
      );
      setProgram(res.program || null);
      setCitations(res.citations || []);
      setState(BUILDER_STATES.PREVIEW);
    } catch (e) {
      setError(e?.detail || 'Could not generate program. Try again.');
    } finally {
      setFinalizing(false);
    }
  };

  // ---- Preview actions ----
  const handleActivate = async () => {
    if (!program?.program_id) return;
    setFinalizing(true);
    try {
      const activated = await activateProgram(program.program_id, initData);
      onProgramActivated?.(activated);
      onClose?.();
    } catch (e) {
      setError(e?.detail || 'Activation failed. Try again.');
    } finally {
      setFinalizing(false);
    }
  };

  const handleSaveDraft = () => {
    // Program already exists as status='draft' after /finalize. Just close.
    onDraftSaved?.(program);
    onClose?.();
  };

  const handleTweak = async () => {
    if (regenCount >= REGEN_CAP) return;
    // Archive the current draft so it doesn't pile up; start a fresh Socratic
    // loop in the SAME session with the previous tuned_spec carried forward.
    if (program?.program_id) {
      try {
        await archiveProgram(program.program_id, 'rebuilt_in_builder', initData);
      } catch (_e) { /* best-effort */ }
    }
    setRegenCount(r => r + 1);
    setProgram(null);
    setCitations([]);
    setReadyPayload(null);
    setTimelineOpen(false);
    setState(BUILDER_STATES.SOCRATIC);
    // Give the LLM context that the user wants a different shape
    await sendTurn(sessionId, "Let me tweak this — adjust based on what we just discussed.");
  };

  // ---- Render ----
  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 100,
      display: 'flex', flexDirection: 'column', justifyContent: 'flex-end',
    }}>
      {/* Backdrop */}
      <div onClick={onClose} style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.3)' }} />

      {/* Sheet */}
      <div style={{
        position: 'relative', background: 'var(--color-white, #fff)',
        borderRadius: '16px 16px 0 0', padding: '16px 16px 24px',
        maxHeight: '88vh', overflowY: 'auto',
      }} data-testid="builder-sheet">
        {/* Handle */}
        <div style={{
          width: 36, height: 4, borderRadius: 2,
          background: 'var(--color-cream-subtle, #d6d0c8)', margin: '0 auto 12px',
        }} />

        <h2 style={{
          fontSize: 15, fontWeight: 700,
          color: 'var(--color-ink-primary)', margin: '0 0 12px',
        }}>
          {state === BUILDER_STATES.INPUTS   && 'Build a program'}
          {state === BUILDER_STATES.SOCRATIC && 'Tell me about it'}
          {state === BUILDER_STATES.PREVIEW  && 'Your program'}
        </h2>

        {error && (
          <div role="alert" style={{
            fontSize: 11, color: 'var(--color-flag-red, #b3261e)',
            background: 'rgba(179,38,30,0.08)', padding: '8px 10px',
            borderRadius: 6, marginBottom: 12,
          }}>{error}</div>
        )}

        {state === BUILDER_STATES.INPUTS && (
          <InputsForm
            domain={domain} setDomain={setDomain}
            goal={goal} setGoal={setGoal}
            goalText={goalText} setGoalText={setGoalText}
            durationWeeks={durationWeeks} setDurationWeeks={setDurationWeeks}
            effectivePhase={effectivePhase} setEffectivePhase={setEffectivePhase}
            hardConstraints={hardConstraints} toggleConstraint={toggleConstraint}
            onContinue={handleContinue} submitting={submittingInputs}
          />
        )}

        {state === BUILDER_STATES.SOCRATIC && (
          <SocraticChat
            messages={messages}
            input={chatInput} setInput={setChatInput}
            loading={chatLoading}
            ready={!!readyPayload}
            onSend={handleSendChat}
            onIDontKnow={handleIDontKnow}
            onFinalize={handleFinalize}
            finalizing={finalizing}
            scrollRef={chatScrollRef}
          />
        )}

        {state === BUILDER_STATES.PREVIEW && program && (
          <PreviewPane
            program={program} citations={citations}
            timelineOpen={timelineOpen} setTimelineOpen={setTimelineOpen}
            regenCount={regenCount} regenCap={REGEN_CAP} regenWarn={REGEN_WARN}
            onActivate={handleActivate}
            onSaveDraft={handleSaveDraft}
            onTweak={handleTweak}
            busy={finalizing}
          />
        )}
      </div>
    </div>
  );
}

// ---------------- Sub-components ----------------

// Per-domain default duration. Throwing keeps 12 wk (covers velocity / longtoss /
// in-season maintenance). Lifting defaults to 8 wk so it sits inside both seeded
// templates' ranges: hypertrophy_8wk_v1 [6,10] AND in_season_lifting_starter_v1
// [10,16] both accept 8 in practice (the latter clamps at /candidates with a
// near-edge match) — and 8 is the most-requested off-season hypertrophy length.
const DEFAULT_DURATION_BY_DOMAIN = {
  throwing: 12,
  lifting:  8,
};

function InputsForm({
  domain, setDomain, goal, setGoal,
  goalText, setGoalText,
  durationWeeks, setDurationWeeks,
  effectivePhase, setEffectivePhase,
  hardConstraints, toggleConstraint,
  onContinue, submitting,
}) {
  const goalOptions = domain === 'lifting' ? GOALS_LIFTING : GOALS_THROWING;
  // When domain switches, the prior goal selection may not exist in the new
  // domain's goal list → clear so the user picks again. Also clear any
  // pending "Other" text so it doesn't leak across domains, and bump the
  // duration to the per-domain default so the chip pre-selection makes sense.
  const handleDomainChange = (id) => {
    if (id === domain) return;
    setDomain(id);
    setGoal(null);
    setGoalText('');
    const nextDefault = DEFAULT_DURATION_BY_DOMAIN[id];
    if (nextDefault !== undefined) setDurationWeeks(nextDefault);
  };

  const handleGoalChange = (id) => {
    setGoal(id);
    // Clear the free-text when leaving the Other branch so a stale draft
    // doesn't survive after picking a real chip.
    if (id !== '__other__') setGoalText('');
  };

  return (
    <div data-testid="inputs-form">
      <p style={sectionLabelStyle}>Domain</p>
      <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
        {DOMAINS.map(d => (
          <button key={d.id} onClick={() => handleDomainChange(d.id)}
            style={chipStyle(domain === d.id)} aria-pressed={domain === d.id}>
            {d.label}
          </button>
        ))}
      </div>

      <p style={sectionLabelStyle}>Goal</p>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 14 }}
        data-testid="goal-chips">
        {goalOptions.map(g => (
          <button key={g.id} onClick={() => handleGoalChange(g.id)}
            style={chipStyle(goal === g.id)} aria-pressed={goal === g.id}>
            {g.label}
          </button>
        ))}
      </div>

      {goal === '__other__' && (
        <input
          type="text"
          value={goalText}
          onChange={e => setGoalText(e.target.value)}
          placeholder="Describe your goal — e.g. add velocity post-surgery"
          aria-label="Goal description"
          data-testid="goal-other-input"
          style={{
            width: '100%',
            padding: '8px 10px',
            fontSize: 12,
            border: '0.5px solid var(--color-cream-border)',
            borderRadius: 6,
            background: 'var(--color-white, #fff)',
            color: 'var(--color-ink-primary)',
            marginBottom: 14,
            boxSizing: 'border-box',
          }}
        />
      )}

      <p style={sectionLabelStyle}>Duration</p>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 14 }}>
        {DURATIONS.map(d => (
          <button key={d.id} onClick={() => setDurationWeeks(d.id)}
            style={chipStyle(durationWeeks === d.id)} aria-pressed={durationWeeks === d.id}>
            {d.label}
          </button>
        ))}
      </div>

      <p style={sectionLabelStyle}>Phase</p>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 14 }}>
        {PHASES.map(p => (
          <button key={p.id} onClick={() => setEffectivePhase(p.id)}
            style={chipStyle(effectivePhase === p.id)} aria-pressed={effectivePhase === p.id}>
            {p.label}
          </button>
        ))}
      </div>

      <p style={sectionLabelStyle}>Hard constraints (optional)</p>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 18 }}>
        {HARD_CONSTRAINTS.map(c => (
          <button key={c.id} onClick={() => toggleConstraint(c.id)}
            style={chipStyle(hardConstraints.includes(c.id))}
            aria-pressed={hardConstraints.includes(c.id)}>
            {c.label}
          </button>
        ))}
      </div>

      <button onClick={onContinue} disabled={submitting}
        style={primaryButtonStyle(submitting)}>
        {submitting ? 'Finding templates…' : 'Continue'}
      </button>
    </div>
  );
}

function SocraticChat({
  messages, input, setInput, loading, ready,
  onSend, onIDontKnow, onFinalize, finalizing, scrollRef,
}) {
  return (
    <div data-testid="socratic-chat">
      <div ref={scrollRef} style={{
        maxHeight: '50vh', overflowY: 'auto', marginBottom: 10,
        display: 'flex', flexDirection: 'column', gap: 8,
        padding: '4px 2px',
      }}>
        {messages.length === 0 && (
          <div style={{ fontSize: 11, color: 'var(--color-ink-muted)', fontStyle: 'italic' }}>
            Starting up…
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} style={{
            display: 'flex',
            justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start',
          }}>
            <div style={{
              maxWidth: '88%',
              borderRadius: m.role === 'user' ? '14px 14px 3px 14px' : '14px 14px 14px 3px',
              padding: '7px 10px', fontSize: 11, lineHeight: 1.55,
              background: m.role === 'user' ? 'var(--color-maroon)' : '#fff',
              color: m.role === 'user' ? '#fff' : 'var(--color-ink-primary)',
              border: m.role === 'user' ? 'none' : '0.5px solid var(--color-cream-border)',
              whiteSpace: 'pre-wrap',
            }}>{m.content}</div>
          </div>
        ))}
        {loading && (
          <div style={{ fontSize: 10, color: 'var(--color-ink-muted)' }}>…thinking</div>
        )}
      </div>

      {!ready ? (
        <>
          <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
            <input
              type="text" value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') onSend(); }}
              placeholder="Type your answer…" disabled={loading}
              style={{
                flex: 1, padding: '8px 10px', fontSize: 12,
                border: '0.5px solid var(--color-cream-border)', borderRadius: 6,
                background: 'var(--color-white, #fff)',
                color: 'var(--color-ink-primary)',
              }}
              aria-label="Chat input"
            />
            <button onClick={onSend} disabled={loading || !input.trim()}
              style={{
                padding: '8px 14px', fontSize: 12, fontWeight: 600,
                background: 'var(--color-maroon)', color: '#fff',
                border: 'none', borderRadius: 6,
                cursor: (loading || !input.trim()) ? 'not-allowed' : 'pointer',
                opacity: (loading || !input.trim()) ? 0.5 : 1,
              }}>Send</button>
          </div>
          <button onClick={onIDontKnow} disabled={loading}
            style={{
              width: '100%', padding: '8px 12px', fontSize: 11,
              background: 'transparent',
              color: 'var(--color-ink-secondary)',
              border: '0.5px dashed var(--color-cream-border)',
              borderRadius: 6, cursor: loading ? 'not-allowed' : 'pointer',
            }}>I don't know — you decide</button>
        </>
      ) : (
        <button onClick={onFinalize} disabled={finalizing}
          style={primaryButtonStyle(finalizing)}>
          {finalizing ? 'Drafting program…' : 'See the program'}
        </button>
      )}
    </div>
  );
}

function PreviewPane({
  program, citations,
  timelineOpen, setTimelineOpen,
  regenCount, regenCap, regenWarn,
  onActivate, onSaveDraft, onTweak, busy,
}) {
  const days = (program?.generated_schedule_json?.days) || [];
  const totalDays = days.length;
  const totalWeeks = Math.ceil(totalDays / 7);

  const tweakDisabled = regenCount >= regenCap;
  const showRegenWarn = regenCount >= regenWarn && !tweakDisabled;

  // Group days by week for the timeline
  const weeks = [];
  for (let i = 0; i < days.length; i += 7) {
    weeks.push(days.slice(i, i + 7));
  }

  return (
    <div data-testid="preview-pane">
      {/* Header stats */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8,
        marginBottom: 14,
      }}>
        <StatCell label="Domain" value={program.domain || '—'} />
        <StatCell label="Length" value={`${totalWeeks} wk`} />
        <StatCell label="Days"   value={String(totalDays)}    />
      </div>

      <div style={{
        fontSize: 11, color: 'var(--color-ink-secondary)',
        marginBottom: 14, padding: '8px 10px',
        background: 'var(--color-cream-soft, #f5efe6)', borderRadius: 6,
      }}>
        Start: <strong style={{ color: 'var(--color-ink-primary)' }}>{program.start_date || '—'}</strong>
        {' · '}Ends: <strong style={{ color: 'var(--color-ink-primary)' }}>{program.nominal_end_date || '—'}</strong>
      </div>

      {/* Expandable day timeline */}
      <button onClick={() => setTimelineOpen(!timelineOpen)}
        style={{
          width: '100%', padding: '8px 10px', fontSize: 11, fontWeight: 600,
          background: 'transparent', color: 'var(--color-maroon)',
          border: '0.5px solid var(--color-cream-border)', borderRadius: 6,
          cursor: 'pointer', marginBottom: 10, textAlign: 'left',
        }}
        aria-expanded={timelineOpen}>
        {timelineOpen ? '▾' : '▸'} Day-by-day timeline ({totalDays} days)
      </button>
      {timelineOpen && (
        <div data-testid="timeline" style={{
          maxHeight: '30vh', overflowY: 'auto', marginBottom: 14,
          fontSize: 10, color: 'var(--color-ink-secondary)',
          background: 'var(--color-cream-soft, #f5efe6)', borderRadius: 6, padding: 8,
        }}>
          {weeks.map((week, wi) => (
            <div key={wi} style={{ marginBottom: 8 }}>
              <div style={{
                fontWeight: 700, color: 'var(--color-ink-primary)', marginBottom: 4,
              }}>Week {wi + 1}</div>
              {week.map((day) => (
                <div key={day.day_index} style={{
                  display: 'flex', justifyContent: 'space-between',
                  padding: '2px 0',
                }}>
                  <span>{day.template_key}</span>
                  <span style={{ color: 'var(--color-ink-muted)' }}>{day.date}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}

      {/* Research citations */}
      {citations.length > 0 && (
        <div data-testid="citations" style={{ marginBottom: 14 }}>
          <p style={sectionLabelStyle}>Why this program</p>
          {citations.map(c => (
            <div key={c.id} style={{
              padding: '8px 10px', marginBottom: 6,
              background: 'var(--color-cream-soft, #f5efe6)', borderRadius: 6,
            }}>
              <div style={{
                fontSize: 11, fontWeight: 600,
                color: 'var(--color-ink-primary)', marginBottom: 2,
              }}>{c.title}</div>
              {c.summary && (
                <div style={{ fontSize: 10, color: 'var(--color-ink-secondary)' }}>
                  {c.summary}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Regen warning */}
      {showRegenWarn && (
        <div style={{
          fontSize: 10, color: 'var(--color-flag-amber, #b86d00)',
          marginBottom: 10, padding: '6px 10px',
          background: 'rgba(184,109,0,0.08)', borderRadius: 6,
        }}>
          One more tweak left before lock — make this one count.
        </div>
      )}

      {/* Action row */}
      <button onClick={onActivate} disabled={busy}
        style={{ ...primaryButtonStyle(busy), marginBottom: 8 }}>
        {busy ? 'Activating…' : 'Activate'}
      </button>
      <div style={{ display: 'flex', gap: 8 }}>
        <button onClick={onSaveDraft} disabled={busy}
          style={secondaryButtonStyle}>Save as draft</button>
        <button onClick={onTweak} disabled={busy || tweakDisabled}
          style={{
            ...secondaryButtonStyle,
            opacity: tweakDisabled ? 0.4 : 1,
            cursor: tweakDisabled ? 'not-allowed' : 'pointer',
          }}
          title={tweakDisabled ? 'Tweak limit reached' : ''}>
          Tweak{regenCap > 0 ? ` (${regenCount}/${regenCap})` : ''}
        </button>
      </div>
    </div>
  );
}

function StatCell({ label, value }) {
  return (
    <div style={{
      padding: '8px 10px', textAlign: 'center',
      background: 'var(--color-cream-soft, #f5efe6)', borderRadius: 6,
    }}>
      <div style={{
        fontSize: 8, fontWeight: 700,
        color: 'var(--color-ink-faint)',
        textTransform: 'uppercase', letterSpacing: '0.08em',
        marginBottom: 2,
      }}>{label}</div>
      <div style={{
        fontSize: 14, fontWeight: 700,
        color: 'var(--color-ink-primary)',
      }}>{value}</div>
    </div>
  );
}
