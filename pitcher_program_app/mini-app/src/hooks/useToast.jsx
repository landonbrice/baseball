import { createContext, useContext, useState, useCallback, useRef } from 'react';

const ToastContext = createContext(null);

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be inside ToastProvider');
  return ctx;
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const idRef = useRef(0);

  const showToast = useCallback((message, type = 'error') => {
    const id = ++idRef.current;
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 3500);
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      {toasts.length > 0 && (
        <div style={{
          position: 'fixed', bottom: 60, left: 12, right: 12,
          zIndex: 9999, display: 'flex', flexDirection: 'column', gap: 6,
          pointerEvents: 'none',
        }}>
          {toasts.map(t => (
            <div key={t.id} style={{
              padding: '10px 14px',
              borderRadius: 10,
              fontSize: 12,
              fontWeight: 600,
              color: '#fff',
              background: t.type === 'error' ? '#dc2626'
                : t.type === 'success' ? '#16a34a'
                : '#5c1020',
              boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
              animation: 'toast-in 0.2s ease-out',
              pointerEvents: 'auto',
            }}>
              {t.message}
            </div>
          ))}
        </div>
      )}
      <style>{`
        @keyframes toast-in {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </ToastContext.Provider>
  );
}
