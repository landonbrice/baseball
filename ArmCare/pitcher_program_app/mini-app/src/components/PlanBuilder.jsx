import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../App';
import { generatePlan } from '../api';

const PLAN_TYPES = [
  { id: 'lower_power', label: 'Lower — power' },
  { id: 'lower_strength', label: 'Lower — strength' },
  { id: 'upper_pull', label: 'Upper — pull' },
  { id: 'upper_push', label: 'Upper — push' },
  { id: 'full_body', label: 'Full body' },
  { id: 'recovery', label: 'Recovery' },
  { id: 'arm_care', label: 'Arm care' },
];

const DURATIONS = [
  { id: 25, label: '25 min' },
  { id: 45, label: '45 min' },
  { id: 60, label: '60 min' },
  { id: null, label: 'No limit' },
];

const EMPHASES = [
  { id: 'heavy_compounds', label: 'Heavy compounds' },
  { id: 'hypertrophy', label: 'Hypertrophy' },
  { id: 'explosive', label: 'Explosive / power' },
  { id: 'fpm', label: 'FPM / arm health' },
  { id: 'pre_game', label: 'Pre-game light' },
];

export default function PlanBuilder({ onClose }) {
  const { pitcherId, initData } = useAuth();
  const navigate = useNavigate();
  const [planType, setPlanType] = useState('full_body');
  const [duration, setDuration] = useState(45);
  const [emphasis, setEmphasis] = useState([]);
  const [notes, setNotes] = useState('');
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);

  const toggleEmphasis = (id) => {
    setEmphasis(prev => prev.includes(id) ? prev.filter(e => e !== id) : [...prev, id]);
  };

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const res = await generatePlan(pitcherId, {
        plan_type: planType,
        duration_min: duration,
        emphasis,
        notes,
      }, initData);
      if (res.plan?.id) {
        navigate(`/plans/${res.plan.id}`);
      }
      onClose?.();
    } catch (e) {
      setError('Failed to generate plan. Try again.');
    } finally {
      setGenerating(false);
    }
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

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 100,
      display: 'flex', flexDirection: 'column', justifyContent: 'flex-end',
    }}>
      {/* Backdrop */}
      <div onClick={onClose} style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.3)' }} />

      {/* Sheet */}
      <div style={{
        position: 'relative', background: 'var(--color-white)',
        borderRadius: '16px 16px 0 0', padding: '16px 16px 24px',
        maxHeight: '80vh', overflowY: 'auto',
      }}>
        {/* Handle */}
        <div style={{ width: 36, height: 4, borderRadius: 2, background: 'var(--color-cream-subtle)', margin: '0 auto 12px' }} />

        <h2 style={{ fontSize: 15, fontWeight: 700, color: 'var(--color-ink-primary)', margin: '0 0 16px' }}>New plan</h2>

        {/* Plan type */}
        <p style={{ fontSize: 10, fontWeight: 600, color: 'var(--color-ink-faint)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>Type</p>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 16 }}>
          {PLAN_TYPES.map(t => (
            <button key={t.id} onClick={() => setPlanType(t.id)} style={chipStyle(planType === t.id)}>{t.label}</button>
          ))}
        </div>

        {/* Duration */}
        <p style={{ fontSize: 10, fontWeight: 600, color: 'var(--color-ink-faint)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>Duration</p>
        <div style={{ display: 'flex', gap: 6, marginBottom: 16 }}>
          {DURATIONS.map(d => (
            <button key={String(d.id)} onClick={() => setDuration(d.id)} style={chipStyle(duration === d.id)}>{d.label}</button>
          ))}
        </div>

        {/* Emphasis */}
        <p style={{ fontSize: 10, fontWeight: 600, color: 'var(--color-ink-faint)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>Emphasis (optional)</p>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 16 }}>
          {EMPHASES.map(e => (
            <button key={e.id} onClick={() => toggleEmphasis(e.id)} style={chipStyle(emphasis.includes(e.id))}>{e.label}</button>
          ))}
        </div>

        {/* Notes */}
        <p style={{ fontSize: 10, fontWeight: 600, color: 'var(--color-ink-faint)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>Notes (optional)</p>
        <input
          type="text"
          placeholder="e.g. skip overhead pressing, add hip work..."
          value={notes}
          onChange={e => setNotes(e.target.value)}
          style={{
            width: '100%', fontSize: 12, padding: '8px 12px', borderRadius: 10,
            border: '0.5px solid var(--color-cream-border)', background: 'var(--color-cream-bg)',
            color: 'var(--color-ink-primary)', outline: 'none', boxSizing: 'border-box',
            marginBottom: 16,
          }}
        />

        {error && <p style={{ fontSize: 11, color: 'var(--color-flag-red)', marginBottom: 8 }}>{error}</p>}

        {/* Generate button */}
        <button
          onClick={handleGenerate}
          disabled={generating}
          style={{
            width: '100%', padding: 12, borderRadius: 12,
            background: generating ? 'var(--color-cream-subtle)' : 'var(--color-maroon)',
            color: '#fff', fontSize: 13, fontWeight: 600,
            border: 'none', cursor: generating ? 'default' : 'pointer',
          }}
        >
          {generating ? 'Building your plan...' : 'Generate'}
        </button>
      </div>
    </div>
  );
}
