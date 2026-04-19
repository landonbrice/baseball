import { NavLink } from 'react-router-dom'
import { useCoachAuth } from '../../hooks/useCoachAuth'
import TeamBrand from './TeamBrand'

const NAV = [
  { to: '/', label: 'Team Overview' },
  { to: '/schedule', label: 'Schedule' },
  { to: '/programs', label: 'Team Programs' },
  { to: '/phases', label: 'Phases' },
  { to: '/insights', label: 'Insights' },
]

export default function Sidebar() {
  const { logout } = useCoachAuth()
  return (
    <aside className="w-48 bg-bone border-r border-cream-dark flex flex-col h-screen overflow-hidden">
      <TeamBrand />
      <nav className="flex-1 py-2">
        {NAV.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `relative block pl-5 pr-4 py-2 font-ui text-body ${
                isActive
                  ? 'bg-hover text-maroon font-semibold before:content-[""] before:absolute before:left-0 before:top-1 before:bottom-1 before:w-[2px] before:bg-maroon before:rounded-r-[2px]'
                  : 'text-graphite hover:bg-hover/60'
              }`
            }
          >
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="px-4 py-3 border-t border-cream-dark">
        <button
          onClick={logout}
          className="font-ui text-meta text-muted hover:text-charcoal"
        >
          Sign out
        </button>
      </div>
    </aside>
  )
}
