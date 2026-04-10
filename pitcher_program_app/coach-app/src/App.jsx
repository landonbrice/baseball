import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useCoachAuth } from './hooks/useCoachAuth'
import { ToastProvider } from './components/Toast'
import Shell from './components/Shell'
import Login from './pages/Login'
import TeamOverview from './pages/TeamOverview'
import Schedule from './pages/Schedule'
import TeamPrograms from './pages/TeamPrograms'
import Phases from './pages/Phases'
import Insights from './pages/Insights'

function ProtectedRoutes() {
  const { coach, loading } = useCoachAuth()

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-cream">
        <p className="text-subtle">Loading...</p>
      </div>
    )
  }

  if (!coach) return <Navigate to="/login" replace />

  return (
    <Shell>
      <Routes>
        <Route path="/" element={<TeamOverview />} />
        <Route path="/schedule" element={<Schedule />} />
        <Route path="/programs" element={<TeamPrograms />} />
        <Route path="/phases" element={<Phases />} />
        <Route path="/insights" element={<Insights />} />
      </Routes>
    </Shell>
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
