import { useNavigate } from 'react-router-dom';

export default function CoachFAB({ showBadge }) {
  const navigate = useNavigate();

  return (
    <button
      onClick={() => navigate('/coach')}
      style={{
        position: 'fixed', bottom: 68, right: 16,
        width: 48, height: 48, borderRadius: '50%',
        background: 'var(--color-maroon)', border: 'none',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        cursor: 'pointer', zIndex: 50,
        boxShadow: '0 2px 12px rgba(92,16,32,0.3)',
      }}
    >
      <span style={{ fontSize: 22 }}>💬</span>
      {showBadge && (
        <span style={{
          position: 'absolute', top: 2, right: 2,
          width: 10, height: 10, borderRadius: '50%',
          background: '#ef4444', border: '2px solid var(--color-maroon)',
        }} />
      )}
    </button>
  );
}
