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
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 20h9" />
        <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
      </svg>
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
