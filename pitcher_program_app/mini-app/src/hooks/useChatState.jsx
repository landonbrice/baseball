import { createContext, useContext, useState, useCallback } from 'react';

const AppContext = createContext(null);

export function AppProvider({ children }) {
  // Coach conversation — persists across tab navigation
  const [messages, setMessages] = useState([]);

  // Global refresh counter — any component can trigger a Home re-fetch
  const [globalRefreshKey, setGlobalRefreshKey] = useState(0);
  const triggerRefresh = useCallback(() => {
    setGlobalRefreshKey(k => k + 1);
  }, []);

  // Coach notification badge — true when there's an unread morning briefing
  const [coachBadge, setCoachBadge] = useState(false);
  const clearCoachBadge = useCallback(() => setCoachBadge(false), []);

  // Coach in-progress indicator — true while check-in is mid-flow
  const [checkinInProgress, setCheckinInProgress] = useState(false);

  const addMessage = useCallback((msg) => setMessages(prev => [...prev, msg]), []);
  const addMessages = useCallback((msgs) => setMessages(prev => [...prev, ...msgs]), []);
  const clearMessages = useCallback(() => setMessages([]), []);
  const replaceLastAndAdd = useCallback((msgs) => {
    setMessages(prev => [...prev.slice(0, -1), ...msgs]);
  }, []);

  return (
    <AppContext.Provider value={{
      messages, setMessages, addMessage, addMessages, clearMessages, replaceLastAndAdd,
      globalRefreshKey, triggerRefresh,
      coachBadge, setCoachBadge, clearCoachBadge,
      checkinInProgress, setCheckinInProgress,
    }}>
      {children}
    </AppContext.Provider>
  );
}

export function useAppContext() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useAppContext must be used within AppProvider');
  return ctx;
}

// Backwards-compatible alias
export function useChat() {
  return useAppContext();
}
