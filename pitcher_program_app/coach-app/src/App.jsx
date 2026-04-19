import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useCoachAuth } from './hooks/useCoachAuth'
import { ToastProvider } from './components/shell/Toast'
import Sidebar from './components/shell/Sidebar'
import Login from './pages/Login'
import TeamOverview from './pages/TeamOverview'
import Schedule from './pages/Schedule'
import TeamPrograms from './pages/TeamPrograms'
import Phases from './pages/Phases'
import Insights from './pages/Insights'
import DesignSandbox from './pages/DesignSandbox'

function ProtectedRoutes() {
  const { coach, loading } = useCoachAuth()

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-cream">
        <p className="font-ui text-meta text-muted">Loading…</p>
      </div>
    )
  }

  if (!coach) return <Navigate to="/login" replace />

  return (
    <div className="flex h-screen bg-cream">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<TeamOverview />} />
          <Route path="/schedule" element={<Schedule />} />
          <Route path="/programs" element={<TeamPrograms />} />
          <Route path="/phases" element={<Phases />} />
          <Route path="/insights" element={<Insights />} />
          {import.meta.env.DEV && (
            <Route path="/__design" element={<DesignSandbox />} />
          )}
        </Routes>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/*" element={<ProtectedRoutes />} />
          </Routes>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
