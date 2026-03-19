import { createContext, useContext, useState, useCallback } from 'react';

const ChatContext = createContext(null);

export function ChatProvider({ children }) {
  const [messages, setMessages] = useState([]);

  const addMessage = useCallback((msg) => {
    setMessages(prev => [...prev, msg]);
  }, []);

  const addMessages = useCallback((msgs) => {
    setMessages(prev => [...prev, ...msgs]);
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  const replaceLastAndAdd = useCallback((msgs) => {
    setMessages(prev => [...prev.slice(0, -1), ...msgs]);
  }, []);

  return (
    <ChatContext.Provider value={{ messages, setMessages, addMessage, addMessages, clearMessages, replaceLastAndAdd }}>
      {children}
    </ChatContext.Provider>
  );
}

export function useChat() {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error('useChat must be used within ChatProvider');
  return ctx;
}
