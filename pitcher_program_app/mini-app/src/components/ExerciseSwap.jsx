import { useState, useCallback } from 'react';
import { fetchAlternatives, swapExercise } from '../api';

const REASONS = [
  { key: 'no_equipment', label: 'No equipment' },
  { key: 'doesnt_feel_right', label: "Doesn't feel right" },
  { key: 'preference', label: 'Just swap it' },
];

/**
 * Inline exercise swap panel (Approach D).
 * Shows reason chips first, then filtered alternatives after selection.
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
    try {
      await swapExercise(pitcherId, date, exerciseId, alt.exercise_id, selectedReason, initData);
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
      setError('Swap failed — try again');
      setStep('alternatives');
    }
  }, [pitcherId, date, exerciseId, exerciseName, selectedReason, initData, onSwap]);

  return (
    <div style={{
      marginTop: 8, marginLeft: 50,
      padding: '12px 14px', borderRadius: 10,
      background: '#f5f1eb', border: '1px solid #e4dfd8',
      transition: 'all 0.15s ease',
    }}>
      {/* Reason chips */}
      {step === 'reasons' && (
        <div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: error ? 8 : 0 }}>
            {REASONS.map((r) => (
              <button
                key={r.key}
                onClick={() => handleReason(r.key)}
                style={{
                  padding: '6px 12px', borderRadius: 20,
                  border: '1.5px solid #e4dfd8', background: '#ffffff',
                  fontSize: 12, color: '#6b5f58', cursor: 'pointer',
                  fontWeight: 500, transition: 'all 0.15s ease',
                }}
              >
                {r.label}
              </button>
            ))}
            <button
              onClick={onCancel}
              style={{
                padding: '6px 12px', borderRadius: 20,
                border: 'none', background: 'transparent',
                fontSize: 12, color: '#b0a89e', cursor: 'pointer',
              }}
            >
              Cancel
            </button>
          </div>
          {error && <div style={{ fontSize: 11, color: '#A32D2D', marginTop: 4 }}>{error}</div>}
        </div>
      )}

      {/* Loading */}
      {step === 'loading' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '4px 0' }}>
          <div style={{
            width: 18, height: 18, borderRadius: 9,
            border: '2px solid #5c1020', borderTopColor: 'transparent',
            animation: 'spin 0.8s linear infinite',
          }} />
          <span style={{ fontSize: 12, color: '#6b5f58' }}>Finding alternatives...</span>
        </div>
      )}

      {/* Alternatives */}
      {step === 'alternatives' && (
        <div>
          {alternatives.length === 0 && (
            <div style={{ fontSize: 12, color: '#6b5f58', marginBottom: 8 }}>No alternatives available</div>
          )}
          {alternatives.map((alt, i) => (
            <div
              key={alt.exercise_id}
              onClick={() => handleSwap(alt)}
              style={{
                padding: '8px 12px', borderRadius: 10, marginBottom: 6,
                background: '#ffffff', border: '1px solid #e4dfd8',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                cursor: 'pointer', transition: 'all 0.15s ease',
              }}
            >
              <div>
                <div style={{ fontSize: 13, fontWeight: 500, color: '#2a1a18' }}>{alt.name}</div>
                <div style={{ fontSize: 11, color: '#b0a89e' }}>
                  {alt.rx} &middot; {alt.match_reason}
                </div>
              </div>
              <span style={{ fontSize: 12, fontWeight: 600, color: '#5c1020', flexShrink: 0 }}>
                Use this
              </span>
            </div>
          ))}
          {error && <div style={{ fontSize: 11, color: '#A32D2D', marginTop: 4 }}>{error}</div>}
          <button
            onClick={onCancel}
            style={{
              marginTop: 4, border: 'none', background: 'transparent',
              fontSize: 12, color: '#b0a89e', cursor: 'pointer', padding: '4px 0',
            }}
          >
            Cancel
          </button>
        </div>
      )}

      {/* Swapping */}
      {step === 'swapping' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '4px 0' }}>
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
