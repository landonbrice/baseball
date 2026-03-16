import { useState, useEffect, createContext, useContext } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { useTelegram } from './hooks/useTelegram';
import { resolveAuth } from './api';
import Layout from './Layout';
import Home from './pages/Home';
import ExerciseLibrary from './pages/ExerciseLibrary';
import LogHistory from './pages/LogHistory';
import Profile from './pages/Profile';

const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

export default function App() {
  const { pitcherId: devPitcherId, initData, loading: telegramLoading } = useTelegram();
  const [pitcherId, setPitcherId] = useState(devPitcherId);
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState(null);

  useEffect(() => {
    if (devPitcherId) {
      setPitcherId(devPitcherId);
      return;
    }
    if (initData && !pitcherId) {
      setAuthLoading(true);
      resolveAuth(initData)
        .then(setPitcherId)
        .catch((err) => {
          setAuthError(err.message);
          setPitcherId(null);
        })
        .finally(() => setAuthLoading(false));
    }
  }, [devPitcherId, initData]);

  if (telegramLoading || authLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-text-secondary">Loading...</div>
      </div>
    );
  }

  if (!pitcherId) {
    return (
      <div className="flex items-center justify-center min-h-screen px-6">
        <div className="text-center">
          <p className="text-text-secondary text-lg mb-2">No pitcher profile found</p>
          <p className="text-text-muted text-sm">Open this app through the Telegram bot to get started.</p>
          {authError && (
            <p className="text-red-400 text-xs mt-4 font-mono">Debug: {authError}</p>
          )}
          <p className="text-text-muted text-xs mt-2 font-mono">
            initData: {initData ? 'present' : 'missing'}
          </p>
        </div>
      </div>
    );
  }

  return (
    <AuthContext.Provider value={{ pitcherId, initData }}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Home />} />
            <Route path="exercises" element={<ExerciseLibrary />} />
            <Route path="log" element={<LogHistory />} />
            <Route path="profile" element={<Profile />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthContext.Provider>
  );
}
