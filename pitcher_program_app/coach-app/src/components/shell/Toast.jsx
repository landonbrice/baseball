import { createContext, useContext, useState, useCallback, useMemo } from 'react'

const ToastContext = createContext(null)

const TONE = {
  success: 'border-forest bg-bone text-forest',
  warn:    'border-amber  bg-bone text-amber',
  error:   'border-crimson bg-bone text-crimson',
  info:    'border-maroon bg-bone text-maroon',
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const addToast = useCallback((message, tone = 'success', ttl = 3500) => {
    const id = Date.now() + Math.random()
    setToasts(prev => [...prev, { id, message, tone }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), ttl)
  }, [])

  const toastApi = useMemo(() => ({
    success: (msg, ttl) => addToast(msg, 'success', ttl),
    warn:    (msg, ttl) => addToast(msg, 'warn',    ttl),
    error:   (msg, ttl) => addToast(msg, 'error',   ttl),
    info:    (msg, ttl) => addToast(msg, 'info',    ttl),
  }), [addToast])

  return (
    <ToastContext.Provider value={toastApi}>
      {children}
      <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2">
        {toasts.map(t => (
          <div
            key={t.id}
            className={`px-4 py-2 rounded-[3px] shadow-md font-ui text-body-sm font-semibold border ${TONE[t.tone] || TONE.info}`}
            style={{ animation: 'fadeIn 0.2s ease-out' }}
          >
            {t.message}
          </div>
        ))}
      </div>
      <style>{`@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }`}</style>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
