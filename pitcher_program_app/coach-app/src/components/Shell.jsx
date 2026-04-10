import { NavLink, Outlet } from 'react-router-dom'
import { useCoachAuth } from '../hooks/useCoachAuth'

const NAV = [
  { to: '/', label: 'Team Overview' },
  { to: '/schedule', label: 'Schedule' },
  { to: '/programs', label: 'Team Programs' },
  { to: '/phases', label: 'Phases' },
  { to: '/insights', label: 'Insights' },
]

export default function Shell() {
  const { coach, logout } = useCoachAuth()

  return (
    <div className="flex h-screen bg-cream">
      {/* Sidebar */}
      <aside className="w-52 bg-white border-r border-cream-dark flex flex-col">
        <div className="p-4 border-b border-cream-dark">
          <h1 className="text-sm font-bold text-maroon">{coach?.team_name || 'Dashboard'}</h1>
          <p className="text-xs text-subtle mt-0.5">{coach?.coach_name}</p>
        </div>
        <nav className="flex-1 py-2">
          {NAV.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `block px-4 py-2 text-sm ${isActive ? 'bg-cream text-maroon font-medium' : 'text-charcoal hover:bg-cream/50'}`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-cream-dark">
          <button onClick={logout} className="text-xs text-subtle hover:text-charcoal">
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
