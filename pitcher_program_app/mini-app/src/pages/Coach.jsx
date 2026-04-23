import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import { useAuth } from '../App';
import { useAppContext } from '../hooks/useChatState';
import { usePitcher } from '../hooks/usePitcher';
import { sendChat, sendChatWithPlan, setNextOuting, savePlan, fetchChatHistory, applyMutations } from '../api';
import { useToast } from '../hooks/useToast';
import MutationPreview from '../components/MutationPreview';
import { parseBrief } from '@shared/parseBrief.js';

// D2: defensive — if backend ever leaks a JSON-string envelope as content,
// extract coaching_note before render. Belt-and-suspenders; no-op for plain text.
function sanitizeChatContent(raw) {
  if (typeof raw !== 'string' || !raw.trim().startsWith('{')) return raw;
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return parsed.coaching_note || '';
    }
  } catch (_) {}
  return raw;
}

const ARM_DETAIL_OPTIONS = [
  { label: 'No issues', value: 'no_issues' },
  { label: 'Expected soreness', value: 'expected_soreness' },
  { label: 'Tight/sore', value: 'tight_sore' },
  { label: 'Heavy/dead', value: 'heavy_dead' },
  { label: 'Sharp pain', value: 'sharp_pain' },
  { label: 'Numb/tingling', value: 'numb_tingling' },
  { label: 'Forearm', value: 'forearm' },
  { label: 'Elbow', value: 'elbow' },
  { label: 'Shoulder', value: 'shoulder' },
  { label: 'Different than normal', value: 'different_than_normal' },
  { label: 'Other', value: 'other' },
];

const ARM_AREA_TAGS = new Set(['forearm', 'elbow', 'shoulder']);
const ARM_SENSATION_TAGS = new Set(['tight_sore', 'heavy_dead', 'sharp_pain', 'numb_tingling', 'different_than_normal']);
const ARM_CONCERN_TAGS = new Set(['expected_soreness', 'tight_sore', 'heavy_dead', 'sharp_pain', 'numb_tingling', 'different_than_normal', 'other']);

function armAck(feel) {
  if (feel <= 4) return 'Noted — we’ll keep this conservative.';
  if (feel <= 6) return 'Got it — I’ll factor that in.';
  return 'Arm’s feeling solid.';
}

function validateArmDetails(tags, note) {
  if (!tags.length) return 'Pick at least one detail. “No issues” is fine.';
  const hasArea = tags.some(t => ARM_AREA_TAGS.has(t));
  const hasSensation = tags.some(t => ARM_SENSATION_TAGS.has(t));
  const hasConcern = tags.some(t => ARM_CONCERN_TAGS.has(t));
  if (tags.includes('no_issues') && hasConcern) return 'Choose either no issues or the concern details, not both.';
  if (tags.includes('expected_soreness') && !hasArea) return 'Select where the expected soreness is.';
  if (hasSensation && !hasArea) return 'Select where you’re feeling that.';
  if (hasArea && !hasSensation && !tags.includes('no_issues') && !tags.includes('expected_soreness')) return 'Select what you’re feeling in that area.';
  if (tags.includes('other') && !note.trim()) return 'Add a quick note for Other.';
  return '';
}

export default function Coach() {
  const { pitcherId, initData } = useAuth();
  const navigate = useNavigate();
  const {
    messages, setMessages, addMessage,
    globalRefreshKey, triggerRefresh, clearCoachBadge, setCheckinInProgress, setCheckinCompleted,
    consumePlanContext,
  } = useAppContext();

  const { showToast } = useToast();
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [checkinFlow, setCheckinFlow] = useState(null);
  const [outingFlow, setOutingFlow] = useState(null);
  const [nextOutingFlow, setNextOutingFlow] = useState(false);
  const scrollRef = useRef(null);

  const suffix = globalRefreshKey ? `?_r=${globalRefreshKey}` : '';
  const { profile, log } = usePitcher(pitcherId, initData, suffix);

  const todayStr = new Date().toLocaleDateString('en-CA', { timeZone: 'America/Chicago' });
  const entries = log?.entries || [];
  const todayEntry = entries.find(e => e.date === todayStr);
  const hasCheckedIn = !!(todayEntry?.pre_training?.arm_feel &&
    (todayEntry?.plan_narrative || todayEntry?.plan_generated?.exercise_blocks?.length));
  const checkedInNoPlan = !!(todayEntry?.pre_training?.arm_feel && !hasCheckedIn);
  // Degraded: plan exists but LLM review failed → let pitcher retry for coach brief
  const planDegraded = todayEntry?.plan_generated?.source === 'python_fallback';
  const rawBrief = todayEntry?.morning_brief || todayEntry?.plan_generated?.morning_brief;
  const parsedBrief = parseBrief(rawBrief);
  const morningBrief = parsedBrief.coaching_note || (typeof rawBrief === 'string' && !rawBrief.trim().startsWith('{') ? rawBrief : null);
  const isNewPitcher = profile && !profile.active_flags?.last_outing_date && !todayEntry;
  const [welcomeSent, setWelcomeSent] = useState(false);

  // Clear badge when Coach tab is opened
  useEffect(() => {
    clearCoachBadge();
  }, [clearCoachBadge]);

  // Load conversation history from Supabase on first open (cross-platform persistence)
  const [historyLoaded, setHistoryLoaded] = useState(false);
  useEffect(() => {
    if (!pitcherId || historyLoaded || messages.length > 0) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetchChatHistory(pitcherId, initData, 20);
        if (cancelled || !res.messages?.length) return;
        const restored = res.messages
          .filter(m => m.role === 'user' || m.role === 'assistant')
          .map(m => ({
            role: m.role === 'user' ? 'user' : 'bot',
            type: 'text',
            content: m.role === 'assistant' ? sanitizeChatContent(m.content) : m.content,
          }));
        if (restored.length > 0) {
          setMessages(restored);
        }
      } catch (e) {
        // Non-critical — just start with empty chat
      } finally {
        if (!cancelled) setHistoryLoaded(true);
      }
    })();
    return () => { cancelled = true; };
  }, [pitcherId, initData, historyLoaded]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-open with personalized welcome for new pitchers
  useEffect(() => {
    if (isNewPitcher && !welcomeSent && messages.length === 0) {
      const firstName = profile?.name?.split(' ')[0] || 'there';
      const role = profile?.role === 'starter' ? 'starter' : 'reliever';
      const rotLen = profile?.rotation_length || 7;
      const arsenal = (profile?.pitching_profile || {}).pitch_arsenal || [];
      const pitchCount = (profile?.pitching_profile || {}).typical_pitch_count || 0;
      const injuries = profile?.injury_history || [];
      const goalPrimary = (profile?.goals || {}).primary;

      // Paragraph 1 — what we know about their pitching
      let p1 = `Hey ${firstName} — I've got your intake loaded. I see you're a **${role} on a ${rotLen}-day rotation**`;
      if (arsenal.length > 0) p1 += ` with a **${arsenal.length}-pitch mix**`;
      if (pitchCount > 0) p1 += `. Typical outing around **${pitchCount} pitches**`;
      p1 += '.';

      // Paragraph 2 — injury awareness (conditional)
      let p2 = '';
      if (injuries.length > 0) {
        const areas = injuries.map(inj => {
          const area = (inj.area || '').replace(/_/g, ' ');
          return inj.description ? `**${area}** — ${inj.description.split('.')[0].toLowerCase()}` : `**${area}**`;
        });
        p2 = `\n\nI'm tracking ${areas.join(', ')}. Your plans will have modified loads and I'll flag any concerning patterns early.`;
      }

      // Paragraph 3 — goal connection
      let p3 = '\n\nReady to build your first plan?';
      if (goalPrimary) p3 = `\n\nYour goal — *${goalPrimary}* — lines up perfectly with how I program. Ready to build your first plan?`;

      setMessages([{ role: 'bot', type: 'text', content: p1 + p2 + p3 }]);
      setWelcomeSent(true);
      setNextOutingFlow(true);
    }
  }, [isNewPitcher, welcomeSent, messages.length, profile]); // eslint-disable-line react-hooks/exhaustive-deps

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
          setCheckinCompleted(true);
          showToast('Plan generated', 'success');
          newMsgs.push({
            role: 'bot',
            type: 'plan_ready',
            content: parseBrief(res.morning_brief).coaching_note || 'Your plan is ready.',
            flagLevel: res.flag_level || 'green',
          });
        } else if (m.content === 'plan_failed') {
          setCheckinInProgress(false);
          setCheckinCompleted(false);
          showToast('Plan generation failed — tap "Retry plan"', 'error');
        } else if (m.content === 'plan_degraded') {
          // Plan is complete but coaching commentary is missing (LLM review failed).
          // Mark checkin complete so the user sees their plan, but surface a retry option.
          setCheckinInProgress(false);
          setCheckinCompleted(true);
          showToast('Baseline plan ready — coach brief unavailable. Retry for full plan.', 'warning');
          newMsgs.push({
            role: 'bot',
            type: 'plan_ready',
            content: parseBrief(res.morning_brief).coaching_note || 'Baseline plan ready.',
            flagLevel: res.flag_level || 'green',
            degraded: true,
          });
        } else if (m.content === 'plan_updated') {
          showToast('Plan updated', 'success');
          newMsgs.push({
            role: 'bot', type: 'text',
            content: 'Plan updated — your changes are live on Home.',
          });
        } else if (m.content === 'rotation_reset') {
          showToast('Outing logged', 'success');
          newMsgs.push({
            role: 'bot', type: 'text',
            content: 'Outing logged. Rotation reset — recovery plan is on Home.',
          });
        }
      } else {
        newMsgs.push({
          role: 'bot',
          ...m,
          content: m.content ? sanitizeChatContent(m.content) : m.content,
        });
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
      const planCtx = consumePlanContext();
      const res = planCtx
        ? await sendChatWithPlan(pitcherId, text, planCtx, initData, history)
        : await sendChat(pitcherId, text, 'text', initData, history);
      setMessages(prev => [...prev, ...processResponse(res)]);
    } catch (err) {
      console.error('Chat send failed:', err);
      setMessages(prev => [...prev, { role: 'bot', type: 'text', content: `Something went wrong: ${err.message || 'unknown error'}. Try again.` }]);
    } finally {
      setLoading(false);
    }
  };

  const flags = profile?.active_flags || {};

  // ── Smart defaults ──
  const daysSince = flags.days_since_outing ?? 99;
  const isRecoveryDay = daysSince <= 1;
  const scheduleKnown = flags.next_outing_days != null && flags.next_outing_days > 0;

  // ── Finalize check-in — send to API ──
  const finalizeCheckin = async (flowData) => {
    setCheckinFlow(null);
    setLoading(true);
    setMessages(prev => [...prev, { role: 'bot', type: 'text', content: 'Building your plan...' }]);
    try {
      const res = await sendChat(pitcherId, {
        arm_report: flowData.arm_report || '',
        arm_feel: flowData.arm_feel || null,
        arm_detail_tags: flowData.arm_detail_tags || [],
        energy: flowData.energy ?? null,
        lift_preference: flowData.lift_preference || 'auto',
        throw_intent: flowData.throw_intent || 'none',
        next_pitch_days: flowData.next_pitch_days ?? (scheduleKnown ? flags.next_outing_days : null),
        arm_clarification: flowData.arm_clarification || '',
      }, 'checkin', initData);
      setMessages(prev => {
        const without = prev.slice(0, -1);
        return [...without, ...processResponse(res)];
      });
    } catch (err) {
      console.error('Check-in failed:', err);
      setMessages(prev => [...prev, { role: 'bot', type: 'text', content: `Check-in failed: ${err.message || 'unknown error'}. Try again.` }]);
      setCheckinInProgress(false);
    } finally {
      setLoading(false);
    }
  };

  // ── Check-in flow ──
  const startCheckin = () => {
    setCheckinInProgress(true);
    setCheckinFlow({ step: 'arm_feel', arm_detail_tags: [], arm_report: '' });
    const firstName = profile?.name?.split(' ')[0] || 'there';
    const flags = profile?.active_flags || {};
    const daysSince = flags.days_since_outing ?? 0;
    const rotationLen = profile?.rotation_length ?? 7;
    const nextOuting = flags.next_outing_days;

    const newMsgs = [];

    // Extended time off acknowledgment
    if (daysSince > rotationLen) {
      if (nextOuting && nextOuting > 0) {
        newMsgs.push({ role: 'bot', type: 'text', content:
          `Day ${daysSince} since your last outing \u2014 next one in ~${nextOuting} days. Training based on that timeline.` });
      } else {
        newMsgs.push({ role: 'bot', type: 'text', content:
          `You're ${daysSince} days out from your last outing with no upcoming date set. I'll build today's plan from your lift preference. Set a date in the schedule step when you know it.` });
      }
    }

    const greeting = isRecoveryDay
      ? `Morning ${firstName}. Day after \u2014 pick your arm feel today, 1-10.`
      : `Morning ${firstName}. Pick your arm feel today, 1-10.`;
    newMsgs.push({ role: 'bot', type: 'text', content: greeting });
    setMessages(prev => [...prev, ...newMsgs]);
  };

  const handleArmFeel = (feel) => {
    setMessages(prev => [...prev, { role: 'user', type: 'text', content: `${feel}` }]);
    setCheckinFlow({ ...checkinFlow, step: 'arm_detail', arm_feel: feel, arm_detail_tags: [] });
    setMessages(prev => [...prev, { role: 'bot', type: 'text', content: `${armAck(feel)} Anything specific I should factor in?` }]);
  };

  const toggleArmDetail = (tag) => {
    const current = checkinFlow?.arm_detail_tags || [];
    const next = current.includes(tag)
      ? current.filter(t => t !== tag)
      : [...current, tag];
    setCheckinFlow({ ...checkinFlow, arm_detail_tags: next });
  };

  const handleArmDetailContinue = () => {
    const tags = checkinFlow?.arm_detail_tags || [];
    const note = input.trim();
    const error = validateArmDetails(tags, note);
    if (error) {
      showToast(error, 'warning');
      return;
    }

    const labelMap = Object.fromEntries(ARM_DETAIL_OPTIONS.map(o => [o.value, o.label]));
    const label = tags.map(t => labelMap[t] || t).join(', ');
    setMessages(prev => [...prev, { role: 'user', type: 'text', content: note ? `${label}: ${note}` : label }]);
    setInput('');

    const feel = checkinFlow.arm_feel;
    const flowData = { ...checkinFlow, arm_report: note, arm_detail_tags: tags };

    // Refinement 1: Recovery day — recommend + give choice
    if (isRecoveryDay) {
      const feelComment = feel != null
        ? (feel >= 7 ? `arm's at a ${feel} \u2014 solid recovery` : feel >= 5 ? `arm's at a ${feel} \u2014 pretty typical day-after` : `arm's at a ${feel} \u2014 let's be careful`)
        : 'day after';
      setCheckinFlow({ ...flowData, step: 'recovery_confirm' });
      setMessages(prev => [...prev, { role: 'bot', type: 'text',
        content: `Day after, ${feelComment}. I'd keep it to recovery flush and blood flow. Want me to build that, or are you thinking something different?`
      }]);
      return;
    }

    // Refinement 2: Arm feel 1-4 — probe before assuming protective
    if (feel != null && feel <= 4) {
      setCheckinFlow({ ...flowData, step: 'low_arm_clarify' });
      setMessages(prev => [...prev, { role: 'bot', type: 'text',
        content: `${armAck(feel)} That's on the lower end \u2014 is this soreness you'd expect given where you are in rotation, or does something feel different?`
      }]);
      return;
    }

    // Normal flow: ack + energy capture (then → lift_pref via handleEnergy)
    // Recovery/low-arm branches intentionally skip energy capture to keep those
    // fast paths short; backend treats a missing `energy` as null and defaults.
    setCheckinFlow({ ...flowData, step: 'energy' });
    setMessages(prev => [...prev, { role: 'bot', type: 'text', content: armAck(feel) + ' Energy today, 1-10?' }]);
  };

  const handleEnergy = (energy) => {
    setMessages(prev => [...prev, { role: 'user', type: 'text', content: `${energy}` }]);
    setCheckinFlow({ ...checkinFlow, step: 'lift_pref', energy });
    setMessages(prev => [...prev, { role: 'bot', type: 'text', content: 'Got it. What are you thinking for a lift?' }]);
  };

  // Refinement 1: Recovery day choice handler
  const handleRecoveryConfirm = (choice) => {
    if (choice === 'yes') {
      setMessages(prev => [...prev, { role: 'user', type: 'text', content: 'Recovery day' }]);
      const flowData = { ...checkinFlow, lift_preference: 'rest', throw_intent: 'none' };
      if (scheduleKnown) {
        setMessages(prev => [...prev, { role: 'bot', type: 'text', content: 'Recovery day it is. Building your plan...' }]);
        finalizeCheckin(flowData);
      } else {
        setCheckinFlow({ ...flowData, step: 'schedule' });
        setMessages(prev => [...prev, { role: 'bot', type: 'text', content: 'Recovery day it is. When do you pitch next?' }]);
      }
    } else {
      setMessages(prev => [...prev, { role: 'user', type: 'text', content: 'Something different' }]);
      setCheckinFlow({ ...checkinFlow, step: 'lift_pref' });
      setMessages(prev => [...prev, { role: 'bot', type: 'text', content: "Got it \u2014 your call. What are you thinking for a lift?" }]);
    }
  };

  // Refinement 2: Low arm feel clarification handler
  const handleLowArmClarify = (choice) => {
    if (choice === 'expected') {
      setMessages(prev => [...prev, { role: 'user', type: 'text', content: 'Expected soreness' }]);
      setCheckinFlow({ ...checkinFlow, step: 'lift_pref', arm_clarification: 'expected_soreness' });
      setMessages(prev => [...prev, { role: 'bot', type: 'text', content: "Expected soreness \u2014 got it. We'll keep intensity down. Want to do a light lift or take a rest day?" }]);
    } else {
      setMessages(prev => [...prev, { role: 'user', type: 'text', content: 'Something feels off' }]);
      const flowData = { ...checkinFlow, arm_clarification: 'concerned', lift_preference: 'rest', throw_intent: 'none' };
      if (scheduleKnown) {
        setMessages(prev => [...prev, { role: 'bot', type: 'text', content: "Something feels off \u2014 flagging this. Building a protective plan..." }]);
        finalizeCheckin(flowData);
      } else {
        setCheckinFlow({ ...flowData, step: 'schedule' });
        setMessages(prev => [...prev, { role: 'bot', type: 'text', content: "Something feels off \u2014 flagging this. We'll go protective today. When do you pitch next?" }]);
      }
    }
  };

  const handleLiftPref = (pref, label) => {
    setMessages(prev => [...prev, { role: 'user', type: 'text', content: label }]);
    const updated = { ...checkinFlow, lift_preference: pref };

    // Smart default: rest day → skip throw intent
    if (pref === 'rest') {
      updated.throw_intent = 'none';
      if (scheduleKnown) {
        setMessages(prev => [...prev, { role: 'bot', type: 'text', content: 'Rest day \u2014 building your plan.' }]);
        finalizeCheckin(updated);
        return;
      }
      setCheckinFlow({ ...updated, step: 'schedule' });
      setMessages(prev => [...prev, { role: 'bot', type: 'text', content: 'When do you pitch next?' }]);
      return;
    }

    setCheckinFlow({ ...updated, step: 'throw_intent' });
    setMessages(prev => [...prev, { role: 'bot', type: 'text', content: 'Throwing today?' }]);
  };

  const handleThrowIntent = (intent, label) => {
    setMessages(prev => [...prev, { role: 'user', type: 'text', content: label }]);
    const updated = { ...checkinFlow, throw_intent: intent };

    // Smart default: skip schedule if already known
    if (scheduleKnown) {
      setMessages(prev => [...prev, { role: 'bot', type: 'text', content: 'Got it.' }]);
      finalizeCheckin(updated);
      return;
    }

    setCheckinFlow({ ...updated, step: 'schedule' });
    setMessages(prev => [...prev, { role: 'bot', type: 'text', content: 'When do you pitch next?' }]);
  };

  const handleSchedule = async (days, label) => {
    setMessages(prev => [...prev, { role: 'user', type: 'text', content: label }]);
    const flowData = { ...checkinFlow, next_pitch_days: days > 0 ? days : null };
    await finalizeCheckin(flowData);
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

  // ── Retry plan (re-triggers triage + plan gen with saved check-in data) ──
  const retryPlan = async () => {
    setLoading(true);
    addMessage({ role: 'user', type: 'text', content: 'Retry plan generation' });
    try {
      const res = await sendChat(pitcherId, {
        arm_feel: todayEntry.pre_training?.arm_feel ?? null,
        arm_detail_tags: todayEntry.pre_training?.arm_detail_tags ?? [],
        arm_report: todayEntry.pre_training?.arm_report ?? '',
        sleep_hours: todayEntry.pre_training?.sleep_hours ?? null,
        energy: todayEntry.pre_training?.overall_energy ?? null,
      }, 'checkin', initData);
      processResponse(res);
      for (const m of res.messages || []) {
        if (m.type === 'text') addMessage({ role: 'bot', type: 'text', content: sanitizeChatContent(m.content) });
      }
    } catch {
      addMessage({ role: 'bot', type: 'text', content: 'Plan retry failed. Try again or check in from Telegram.' });
    } finally {
      setLoading(false);
    }
  };

  // ── Quick action pills ──
  const quickActions = [];
  if (!hasCheckedIn && !checkinFlow && !checkedInNoPlan) {
    quickActions.push({ label: '✅ Check in', action: startCheckin });
  }
  if (checkedInNoPlan || planDegraded) {
    quickActions.push({
      label: planDegraded ? '🔄 Retry for coach brief' : '🔄 Retry plan',
      action: retryPlan,
    });
  }
  if (!outingFlow) {
    quickActions.push({ label: '📊 Log outing', action: startOuting });
  }
  if (!nextOutingFlow) {
    quickActions.push({ label: '📅 Next outing', action: startNextOuting });
  }
  if (hasCheckedIn) {
    quickActions.push({ label: "📝 Today's plan", action: () => {
      setInput("What's my plan for today?");
    }});
    quickActions.push({ label: '🔄 Re-check-in', action: () => {
      setCheckinCompleted(false);
      startCheckin();
    }});
  }

  // ── Determine what interactive buttons to show ──
  const renderButtons = () => {
    const btnStyle = { padding: '6px 12px', fontSize: 11, fontWeight: 500, background: 'var(--color-cream-bg)', color: 'var(--color-ink-primary)', borderRadius: 8, border: '0.5px solid var(--color-cream-border)', cursor: 'pointer' };

    if (checkinFlow?.step === 'arm_feel') {
      return (
        <div style={{ padding: '0 12px 8px' }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, justifyContent: 'center' }}>
            {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(n => (
              <button key={n} onClick={() => handleArmFeel(n)}
                style={{ width: 32, height: 36, fontSize: 13, fontWeight: 700, background: 'var(--color-cream-bg)', color: 'var(--color-ink-primary)', borderRadius: 8, border: '0.5px solid var(--color-cream-border)', cursor: 'pointer' }}>
                {n}
              </button>
            ))}
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 4px 0', fontSize: 8, color: '#9f9188' }}>
            <span>rough</span><span>normal</span><span>great</span>
          </div>
        </div>
      );
    }
    if (checkinFlow?.step === 'arm_detail') {
      const selected = checkinFlow.arm_detail_tags || [];
      const note = input.trim();
      const error = validateArmDetails(selected, note);
      return (
        <div style={{ padding: '0 12px 8px' }}>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {ARM_DETAIL_OPTIONS.map(o => {
              const active = selected.includes(o.value);
              return (
                <button key={o.value} onClick={() => toggleArmDetail(o.value)}
                  style={{
                    padding: '6px 10px', fontSize: 10, fontWeight: 600,
                    background: active ? 'var(--color-maroon)' : 'var(--color-cream-bg)',
                    color: active ? '#fff' : 'var(--color-ink-primary)',
                    borderRadius: 999, border: '0.5px solid var(--color-cream-border)', cursor: 'pointer',
                  }}>
                  {o.label}
                </button>
              );
            })}
          </div>
          {error && selected.length > 0 && (
            <div style={{ marginTop: 6, fontSize: 9, color: 'var(--color-maroon)' }}>{error}</div>
          )}
          <button onClick={handleArmDetailContinue}
            style={{
              marginTop: 8, width: '100%', padding: '8px 12px', fontSize: 11, fontWeight: 700,
              background: error ? '#d9d0c4' : 'var(--color-maroon)', color: '#fff',
              border: 'none', borderRadius: 8, cursor: error ? 'not-allowed' : 'pointer',
            }}>
            Continue
          </button>
        </div>
      );
    }
    if (checkinFlow?.step === 'recovery_confirm') {
      return (
        <div style={{ display: 'flex', gap: 6, padding: '0 12px 8px', flexWrap: 'wrap' }}>
          <button onClick={() => handleRecoveryConfirm('yes')} style={btnStyle}>Recovery day</button>
          <button onClick={() => handleRecoveryConfirm('no')} style={btnStyle}>Something different</button>
        </div>
      );
    }
    if (checkinFlow?.step === 'low_arm_clarify') {
      return (
        <div style={{ display: 'flex', gap: 6, padding: '0 12px 8px', flexWrap: 'wrap' }}>
          <button onClick={() => handleLowArmClarify('expected')} style={btnStyle}>Expected soreness</button>
          <button onClick={() => handleLowArmClarify('concerned')} style={btnStyle}>Something feels off</button>
        </div>
      );
    }
    if (checkinFlow?.step === 'energy') {
      return (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, padding: '0 12px 8px', justifyContent: 'center' }}>
          {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(n => (
            <button key={n} onClick={() => handleEnergy(n)}
              style={{ width: 32, height: 36, fontSize: 13, fontWeight: 600, background: 'var(--color-cream-bg)', color: 'var(--color-ink-primary)', borderRadius: 8, border: '0.5px solid var(--color-cream-border)', cursor: 'pointer' }}>
              {n}
            </button>
          ))}
        </div>
      );
    }
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
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, padding: '0 12px 8px', justifyContent: 'center' }}>
          {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(n => (
            <button key={n} onClick={() => handleOutingArmFeel(n)}
              style={{ width: 32, height: 36, fontSize: 13, fontWeight: 600, background: 'var(--color-cream-bg)', color: 'var(--color-ink-primary)', borderRadius: 8, border: '0.5px solid var(--color-cream-border)', cursor: 'pointer' }}>
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
  const inputSubmit = checkinFlow?.step === 'arm_detail'
    ? handleArmDetailContinue
    : outingFlow?.step === 'pitch_count' ? handlePitchCount : handleSend;
  const inputPlaceholder = checkinFlow?.step === 'arm_detail'
    ? 'Optional note, required for Other...'
    : outingFlow?.step === 'pitch_count'
    ? 'Pitch count...'
    : hasCheckedIn ? "Ask about today's plan..." : 'Ask your coach...';
  const inputDisabled = (!!checkinFlow && checkinFlow.step !== 'arm_detail') || nextOutingFlow;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100dvh - 80px)', background: 'var(--color-cream-bg)' }}>

      {/* Maroon header */}
      <div style={{ background: 'var(--color-maroon)', padding: '14px 16px 12px', flexShrink: 0 }}>
        <div style={{ fontSize: 20, fontWeight: 800, color: '#fff', letterSpacing: '-0.4px' }}>💬 Coach</div>
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
                  <div className="chat-markdown"><ReactMarkdown>{typeof m.content === 'string' ? m.content : ''}</ReactMarkdown></div>
                ) : (
                  <p style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{typeof m.content === 'string' ? m.content : String(m.content ?? '')}</p>
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
                {/* Plan mutation preview */}
                {m.type === 'plan_mutation' && m.mutations && (
                  <MutationPreview
                    mutations={m.mutations}
                    applied={!!m.mutationsApplied}
                    onApply={async () => {
                      const today = new Date().toLocaleDateString('en-CA', { timeZone: 'America/Chicago' });
                      await applyMutations(pitcherId, today, m.mutations, initData);
                      setMessages(prev => prev.map((msg, idx) =>
                        idx === i ? { ...msg, mutationsApplied: true } : msg
                      ));
                      showToast('Plan updated', 'success');
                      triggerRefresh();
                    }}
                    onKeep={() => {
                      setMessages(prev => prev.map((msg, idx) =>
                        idx === i ? { ...msg, mutationsApplied: 'declined' } : msg
                      ));
                    }}
                  />
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
            <span style={{ color: '#fff', fontSize: 9 }}>{'\u2191'}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
