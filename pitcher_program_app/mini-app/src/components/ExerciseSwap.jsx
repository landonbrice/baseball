import { useState, useCallback } from 'react';
import { fetchAlternatives, swapExercise } from '../api';

const REASONS = [
  { key: 'no_equipment', label: 'No equipment' },
  { key: 'doesnt_feel_right', label: "Doesn't feel right" },
  { key: 'preference', label: 'Just swap it' },
];

/**
 * Inline exercise swap UI (Approach D — Coach Hybrid).
 *
 * Fast path: "Just swap it" -> instant alternatives, no LLM.
 * Learning path: "No equipment" / "Doesn't feel right" -> records reason, shows alternatives.
 */
export default function ExerciseSwap({ exerciseId, exerciseName, pitcherId, date, initData, onSwap, onCancel }) {
  const [step, setStep] = useState('reasons');
  const [alternatives, setAlternatives] = useState([]);
  const [selectedReason, setSelectedReason] = useState(null);
  const [error, setError] = useState(null);

  const handleReason = useCallback(async (reason) => {
    setSelectedReason(reason);
    setStep('loading');
    setError(null);
    try {
      const result = await fetchAlternatives(pitcherId, exerciseId, date, initData);
      setAlternatives(result.alternatives || []);
      setStep('alternatives');
    } catch (err) {
      setError('Failed to load alternatives');
      setStep('reasons');
    }
  }, [pitcherId, exerciseId, date, initData]);

  const handleSwap = useCallback(async (alt) => {
    setStep('swapping');
    // Step 1: call the API. If this fails, show the "swap failed" error.
    try {
      await swapExercise(pitcherId, date, exerciseId, alt.exercise_id, selectedReason, initData);
    } catch (err) {
      setError('Swap failed \u2014 try again');
      setStep('alternatives');
      return;
    }
    // Step 2: backend write succeeded. Notify the parent.
    // If the parent callback throws, log it but DON'T show "swap failed" —
    // the swap is persisted, we just hit a frontend issue updating local state.
    try {
      onSwap({
        exercise_id: alt.exercise_id,
        name: alt.name,
        rx: alt.rx,
        prescribed: alt.rx,
        youtube_url: alt.youtube_url,
        swapped_from: exerciseId,
        swapped_from_name: exerciseName,
      });
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('onSwap callback threw after successful backend swap:', err);
      // Let the component unmount naturally — the swap DID persist
    }
  }, [pitcherId, date, exerciseId, exerciseName, selectedReason, initData, onSwap]);

  return (
    <div style={{ marginTop: 8, marginLeft: 50 }}>
      {step === 'reasons' && (
        <div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {REASONS.map((r) => (
              <button
                key={r.key}
                onClick={() => handleReason(r.key)}
                style={{
                  padding: '6px 11px', borderRadius: 18,
                  border: '1.5px solid #e4dfd8', background: '#ffffff',
                  fontSize: 12, color: '#6b5f58', cursor: 'pointer',
                  fontWeight: 500,
                }}
              >
                {r.label}
              </button>
            ))}
            <button
              onClick={onCancel}
              style={{
                padding: '6px 11px', borderRadius: 18,
                border: '1.5px solid #e4dfd8', background: 'transparent',
                fontSize: 12, color: '#b0a89e', cursor: 'pointer',
              }}
            >
              Cancel
            </button>
          </div>
          {error && <div style={{ fontSize: 11, color: '#A32D2D', marginTop: 6 }}>{error}</div>}
        </div>
      )}

      {step === 'loading' && (
        <div style={{
          padding: 12, borderRadius: 10, background: '#f5f1eb',
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <div style={{
            width: 18, height: 18, borderRadius: 9,
            border: '2px solid #5c1020', borderTopColor: 'transparent',
            animation: 'spin 0.8s linear infinite',
          }} />
          <span style={{ fontSize: 12, color: '#6b5f58' }}>Finding alternatives...</span>
        </div>
      )}

      {step === 'alternatives' && (
        <div style={{
          padding: '10px 12px', borderRadius: 10,
          background: '#f5f1eb', border: '1px solid #e4dfd8',
        }}>
          <div style={{
            fontSize: 11, fontWeight: 600, color: '#b0a89e',
            marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5,
          }}>
            Swap with
          </div>
          {alternatives.length === 0 && (
            <div style={{ fontSize: 12, color: '#6b5f58' }}>No alternatives available</div>
          )}
          {alternatives.map((alt, i) => (
            <div
              key={alt.exercise_id}
              onClick={() => handleSwap(alt)}
              style={{
                display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0',
                borderBottom: i < alternatives.length - 1 ? '1px solid #e4dfd840' : 'none',
                cursor: 'pointer',
              }}
            >
              <div style={{
                width: 28, height: 28, borderRadius: 14,
                background: i === 0 ? '#1D9E7515' : '#5c102008',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 12, color: i === 0 ? '#1D9E75' : '#5c1020', flexShrink: 0,
              }}>
                {i === 0 ? '\u2605' : '\u21BB'}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 13, fontWeight: 500, color: '#2a1a18' }}>{alt.name}</span>
                  {alt.tag && (
                    <span style={{
                      fontSize: 9, padding: '1px 6px', borderRadius: 8,
                      background: '#1D9E7515', color: '#1D9E75', fontWeight: 600,
                    }}>{alt.tag}</span>
                  )}
                </div>
                <div style={{ fontSize: 11, color: '#b0a89e' }}>
                  {alt.rx} &middot; {alt.match_reason}
                </div>
              </div>
            </div>
          ))}
          {error && <div style={{ fontSize: 11, color: '#A32D2D', marginTop: 6 }}>{error}</div>}
          <button
            onClick={onCancel}
            style={{
              marginTop: 8, padding: '4px 10px', borderRadius: 12,
              border: '1px solid #e4dfd8', background: 'transparent',
              fontSize: 11, color: '#b0a89e', cursor: 'pointer',
            }}
          >
            Cancel
          </button>
        </div>
      )}

      {step === 'swapping' && (
        <div style={{
          padding: 12, borderRadius: 10, background: '#f5f1eb',
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <div style={{
            width: 18, height: 18, borderRadius: 9,
            border: '2px solid #5c1020', borderTopColor: 'transparent',
            animation: 'spin 0.8s linear infinite',
          }} />
          <span style={{ fontSize: 12, color: '#6b5f58' }}>Swapping...</span>
        </div>
      )}
    </div>
  );
}
