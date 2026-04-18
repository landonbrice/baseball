import { useState, useEffect } from 'react';
import { logUiFallback } from '../api';

/**
 * Renders a plan mutation preview card in the coach chat.
 * Shows what changes the coach is suggesting (add/swap/remove/modify exercises)
 * with Apply/Keep buttons.
 *
 * Props:
 *   mutations - array of mutation objects: { action, exercise_id, from_exercise_id, to_exercise_id, name, rx, note }
 *   onApply() - callback when pitcher accepts changes
 *   onKeep() - callback when pitcher declines changes
 *   applied - boolean, true after changes are applied
 */
export default function MutationPreview({ mutations, onApply, onKeep, applied }) {
  const [applying, setApplying] = useState(false);

  useEffect(() => {
    (mutations || []).forEach(m => {
      if (m.action === 'swap' && !m.name && m.to_exercise_id) {
        logUiFallback({
          exerciseId: m.to_exercise_id,
          surface: 'mini-app',
          component: 'MutationPreview',
        });
      }
    });
  }, [mutations]);

  if (!mutations || mutations.length === 0) return null;

  const handleApply = async () => {
    setApplying(true);
    try {
      await onApply();
    } catch {
      setApplying(false);
    }
  };

  return (
    <div style={{
      margin: '8px 0', padding: '10px 12px', borderRadius: 10,
      background: applied ? '#1D9E7508' : '#f5f1eb',
      border: `1px solid ${applied ? '#1D9E7525' : '#e4dfd8'}`,
    }}>
      <div style={{
        fontSize: 11, fontWeight: 600, color: applied ? '#1D9E75' : '#6b5f58',
        marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5,
      }}>
        {applied ? 'Changes applied' : 'Suggested changes'}
      </div>

      {mutations.map((m, i) => (
        <div key={i} style={{
          display: 'flex', alignItems: 'center', gap: 8, padding: '6px 0',
          borderBottom: i < mutations.length - 1 ? '1px solid #e4dfd840' : 'none',
          opacity: applied ? 0.7 : 1,
        }}>
          <div style={{
            width: 22, height: 22, borderRadius: 11, flexShrink: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 10, fontWeight: 700,
            background: m.action === 'add' ? '#1D9E7515' : m.action === 'remove' ? '#A32D2D15' : '#5c102008',
            color: m.action === 'add' ? '#1D9E75' : m.action === 'remove' ? '#A32D2D' : '#5c1020',
          }}>
            {m.action === 'add' ? '+' : m.action === 'remove' ? '\u2212' : m.action === 'swap' ? '\u21BB' : '\u270E'}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            {m.action === 'swap' ? (
              <div>
                <span style={{ fontSize: 12, color: '#b0a89e', textDecoration: 'line-through' }}>
                  {m.from_name || m.from_exercise_id}
                </span>
                <span style={{ fontSize: 12, color: '#6b5f58' }}> → </span>
                <span style={{ fontSize: 12, fontWeight: 500, color: '#2a1a18' }}>
                  {m.name || m.to_exercise_id}
                </span>
                {m.rx && <span style={{ fontSize: 11, color: '#b0a89e' }}> {m.rx}</span>}
              </div>
            ) : m.action === 'remove' ? (
              <span style={{ fontSize: 12, color: '#A32D2D', textDecoration: 'line-through' }}>
                {m.name || m.exercise_id}
              </span>
            ) : (
              <div>
                <span style={{ fontSize: 12, fontWeight: 500, color: '#2a1a18' }}>
                  {m.action === 'add' ? '+ ' : ''}{m.name || m.exercise_id}
                </span>
                {m.rx && <span style={{ fontSize: 11, color: '#b0a89e' }}> {m.rx}</span>}
                {m.note && <span style={{ fontSize: 11, color: '#6b5f58', fontStyle: 'italic' }}> — {m.note}</span>}
              </div>
            )}
          </div>
        </div>
      ))}

      {!applied && (
        <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
          <button
            onClick={handleApply}
            disabled={applying}
            style={{
              flex: 1, padding: '8px 0', borderRadius: 8, border: 'none',
              background: '#5c1020', color: '#fff', fontSize: 12,
              fontWeight: 600, cursor: applying ? 'wait' : 'pointer',
              opacity: applying ? 0.7 : 1,
            }}
          >
            {applying ? 'Applying...' : 'Apply Changes'}
          </button>
          <button
            onClick={onKeep}
            style={{
              flex: 1, padding: '8px 0', borderRadius: 8,
              border: '1px solid #e4dfd8', background: 'transparent',
              color: '#6b5f58', fontSize: 12, fontWeight: 500, cursor: 'pointer',
            }}
          >
            Keep Current
          </button>
        </div>
      )}
    </div>
  );
}
