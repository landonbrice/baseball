import { useState } from 'react';
import { useAuth } from '../App';
import { submitCheckin, submitOuting, submitAsk } from '../api';

const SLEEP_OPTIONS = [
  { label: '<6h', value: 5.5 },
  { label: '6-7h', value: 6.5 },
  { label: '7-8h', value: 7.5 },
  { label: '8+h', value: 8.5 },
];

export default function ActionBar({ todayEntry, profile, onRefresh, placeholder = 'Ask about today\'s plan...', askOnly = false }) {
  const { pitcherId, initData } = useAuth();
  const [mode, setMode] = useState('default');
  const [armFeel, setArmFeel] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  // Outing state
  const [pitchCount, setPitchCount] = useState('');
  const [outingArmFeel, setOutingArmFeel] = useState(null);
  const [outingNotes, setOutingNotes] = useState('');

  // Q&A state
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState(null);
  const [history, setHistory] = useState([]);
  const [askLoading, setAskLoading] = useState(false);

  const hasCheckedIn = !!todayEntry?.pre_training?.arm_feel;
  const isGameDay = (profile?.active_flags?.days_since_outing ?? 99) >=
    (profile?.rotation_length ?? 7) - 1;

  const reset = () => {
    setMode('default');
    setArmFeel(null);
    setError(null);
    setPitchCount('');
    setOutingArmFeel(null);
    setOutingNotes('');
  };

  const handleArmFeel = (feel) => {
    setArmFeel(feel);
    setMode('sleep');
  };

  const handleSleep = async (hours) => {
    setSubmitting(true);
    setError(null);
    try {
      await submitCheckin(pitcherId, armFeel, hours, initData);
      setMode('done');
      onRefresh?.();
    } catch (e) {
      setError('Check-in failed. Try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleOuting = async () => {
    const count = parseInt(pitchCount);
    if (!count || !outingArmFeel) return;
    setSubmitting(true);
    setError(null);
    try {
      await submitOuting(pitcherId, count, outingArmFeel, outingNotes, initData);
      reset();
      onRefresh?.();
    } catch (e) {
      setError('Outing report failed. Try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleAsk = async () => {
    if (!question.trim() || history.length >= 10) return;
    setAskLoading(true);
    const newHistory = [...history, { role: 'user', content: question }];
    setHistory(newHistory);
    setQuestion('');
    try {
      const res = await submitAsk(pitcherId, question, history, initData);
      setAnswer(res.answer);
      setHistory([...newHistory, { role: 'assistant', content: res.answer }]);
    } catch (e) {
      setAnswer('Something went wrong. Try again.');
    } finally {
      setAskLoading(false);
    }
  };

  // ── Ask-only mode (non-Home pages) ──
  if (askOnly && mode !== 'ask') {
    return (
      <Bar>
        <ActionBtn onClick={() => setMode('ask')}>{placeholder}</ActionBtn>
      </Bar>
    );
  }

  // ── Checked in state ──
  if (hasCheckedIn && mode === 'default') {
    return (
      <Bar>
        <p className="text-xs text-text-secondary">
          Checked in · Arm feel {todayEntry.pre_training.arm_feel}/5
        </p>
        <div className="flex gap-2 mt-2">
          <ActionBtn onClick={() => setMode('ask')}>Ask a question</ActionBtn>
        </div>
      </Bar>
    );
  }

  // ── Done state (just checked in) ──
  if (mode === 'done') {
    return (
      <Bar>
        <p className="text-xs text-text-secondary">Check-in submitted. Your plan is loading.</p>
      </Bar>
    );
  }

  // ── Sleep follow-up ──
  if (mode === 'sleep') {
    return (
      <Bar>
        <p className="text-xs text-text-secondary mb-2">
          Arm feel: {armFeel}/5. How many hours of sleep?
        </p>
        <div className="flex gap-2">
          {SLEEP_OPTIONS.map(opt => (
            <button
              key={opt.value}
              onClick={() => handleSleep(opt.value)}
              disabled={submitting}
              className="flex-1 py-2 text-xs font-medium bg-bg-tertiary text-text-primary rounded-lg hover:bg-accent-blue/20 disabled:opacity-50 transition-colors"
            >
              {opt.label}
            </button>
          ))}
        </div>
        {error && <p className="text-flag-red text-[10px] mt-1">{error}</p>}
      </Bar>
    );
  }

  // ── Outing panel ──
  if (mode === 'outing') {
    return (
      <Bar>
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs font-medium text-text-primary">Log outing</p>
          <button onClick={reset} className="text-[10px] text-text-muted">Cancel</button>
        </div>
        <input
          type="number"
          placeholder="Pitch count"
          value={pitchCount}
          onChange={e => setPitchCount(e.target.value)}
          className="w-full bg-bg-tertiary text-text-primary text-sm rounded-lg px-3 py-2 mb-2 border border-bg-tertiary focus:border-accent-blue focus:outline-none"
        />
        <p className="text-[10px] text-text-muted mb-1">Arm feel post-outing</p>
        <div className="flex gap-1.5 mb-2">
          {[1, 2, 3, 4, 5].map(n => (
            <button
              key={n}
              onClick={() => setOutingArmFeel(n)}
              className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                outingArmFeel === n
                  ? 'bg-accent-blue text-white'
                  : 'bg-bg-tertiary text-text-muted'
              }`}
            >
              {n}
            </button>
          ))}
        </div>
        <input
          type="text"
          placeholder="Notes (optional)"
          value={outingNotes}
          onChange={e => setOutingNotes(e.target.value)}
          className="w-full bg-bg-tertiary text-text-primary text-sm rounded-lg px-3 py-2 mb-2 border border-bg-tertiary focus:border-accent-blue focus:outline-none"
        />
        <button
          onClick={handleOuting}
          disabled={!pitchCount || !outingArmFeel || submitting}
          className="w-full py-2 text-xs font-medium bg-accent-blue text-white rounded-lg disabled:opacity-40 transition-colors"
        >
          {submitting ? 'Submitting...' : 'Submit outing'}
        </button>
        {error && <p className="text-flag-red text-[10px] mt-1">{error}</p>}
      </Bar>
    );
  }

  // ── Q&A overlay ──
  if (mode === 'ask') {
    return (
      <Bar>
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs font-medium text-text-primary">Ask a question</p>
          <button onClick={() => { setMode('default'); setAnswer(null); setHistory([]); }} className="text-[10px] text-text-muted">Close</button>
        </div>
        {answer && (
          <div className="bg-bg-tertiary rounded-lg p-3 mb-2 max-h-40 overflow-y-auto">
            <p className="text-xs text-text-secondary whitespace-pre-wrap">{answer}</p>
          </div>
        )}
        <div className="flex gap-2">
          <input
            type="text"
            placeholder={placeholder}
            value={question}
            onChange={e => setQuestion(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleAsk()}
            className="flex-1 bg-bg-tertiary text-text-primary text-sm rounded-lg px-3 py-2 border border-bg-tertiary focus:border-accent-blue focus:outline-none"
          />
          <button
            onClick={handleAsk}
            disabled={!question.trim() || askLoading}
            className="px-3 py-2 text-xs font-medium bg-accent-blue text-white rounded-lg disabled:opacity-40 transition-colors"
          >
            {askLoading ? '...' : 'Ask'}
          </button>
        </div>
        {history.length >= 10 && (
          <p className="text-[10px] text-text-muted mt-1">Session limit reached. Close and reopen to continue.</p>
        )}
      </Bar>
    );
  }

  // ── Default state: no check-in yet ──
  return (
    <Bar>
      {isGameDay ? (
        <p className="text-xs text-text-secondary mb-2">Game day — good luck</p>
      ) : (
        <>
          <p className="text-xs text-text-muted mb-1">How's the arm?</p>
          <div className="flex gap-1.5 mb-2">
            {[1, 2, 3, 4, 5].map(n => (
              <button
                key={n}
                onClick={() => handleArmFeel(n)}
                className="flex-1 py-2 text-sm font-medium bg-bg-tertiary text-text-primary rounded-lg hover:bg-accent-blue/20 transition-colors"
              >
                {n}
              </button>
            ))}
          </div>
        </>
      )}
      <div className="flex gap-2">
        <ActionBtn onClick={() => setMode('outing')}>
          {isGameDay ? 'Log outing after' : 'I pitched today'}
        </ActionBtn>
        <ActionBtn onClick={() => setMode('ask')}>Ask a question</ActionBtn>
      </div>
      {error && <p className="text-flag-red text-[10px] mt-1">{error}</p>}
    </Bar>
  );
}

function Bar({ children }) {
  return (
    <div className="fixed bottom-14 left-0 right-0 bg-bg-primary border-t border-bg-tertiary p-3 z-40">
      {children}
    </div>
  );
}

function ActionBtn({ onClick, children }) {
  return (
    <button
      onClick={onClick}
      className="flex-1 py-2 text-xs font-medium bg-bg-secondary text-text-primary rounded-lg hover:bg-bg-tertiary transition-colors"
    >
      {children}
    </button>
  );
}
