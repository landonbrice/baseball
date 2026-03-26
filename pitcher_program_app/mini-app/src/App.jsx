import { useState, useEffect, createContext, useContext, Component } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { useTelegram } from './hooks/useTelegram';
import { resolveAuth, fetchApi } from './api';
import { AppProvider, useAppContext } from './hooks/useChatState.jsx';
import Layout from './Layout';
import Home from './pages/Home';
import Coach from './pages/Coach';
import ExerciseLibrary from './pages/ExerciseLibrary';
import LogHistory from './pages/LogHistory';
import Profile from './pages/Profile';
import Plans from './pages/Plans';
import PlanDetail from './pages/PlanDetail';

class ErrorBoundary extends Component {
  constructor(props) { super(props); this.state = { error: null }; }
  static getDerivedStateFromError(error) { return { error }; }
  componentDidCatch(error, info) { console.error('App crash:', error, info); }
  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 24, textAlign: 'center' }}>
          <p style={{ fontSize: 14, color: '#A32D2D', marginBottom: 8 }}>Something went wrong</p>
          <p style={{ fontSize: 11, color: '#6b5f58', marginBottom: 12 }}>{this.state.error?.message}</p>
          <button onClick={() => { this.setState({ error: null }); window.location.reload(); }}
            style={{ padding: '8px 16px', background: '#5c1020', color: '#fff', border: 'none', borderRadius: 8, fontSize: 12 }}>
            Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

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
            <p className="text-red-400 text-xs mt-4 font-mono">{authError}</p>
          )}
        </div>
      </div>
    );
  }

  return (
    <ErrorBoundary>
      <AuthContext.Provider value={{ pitcherId, initData }}>
        <AppProvider>
          <MorningBadgeCheck pitcherId={pitcherId} initData={initData} />
          <BrowserRouter>
            <Routes>
              <Route element={<Layout />}>
                <Route index element={<Home />} />
                <Route path="coach" element={<Coach />} />
                <Route path="plans" element={<Plans />} />
                <Route path="plans/:planId" element={<PlanDetail />} />
                <Route path="log" element={<LogHistory />} />
                <Route path="exercises" element={<ExerciseLibrary />} />
                <Route path="profile" element={<Profile />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </AppProvider>
      </AuthContext.Provider>
    </ErrorBoundary>
  );
}

function MorningBadgeCheck({ pitcherId, initData }) {
  const { setCoachBadge } = useAppContext();

  useEffect(() => {
    if (!pitcherId) return;
    fetchApi(`/api/pitcher/${pitcherId}/morning-status`, initData)
      .then(d => {
        if (d.has_briefing && !d.checked_in_today) {
          setCoachBadge(true);
        }
      })
      .catch(() => {});
  }, [pitcherId, initData, setCoachBadge]);

  return null;
}
