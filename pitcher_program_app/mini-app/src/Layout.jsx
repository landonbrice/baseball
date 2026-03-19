import { NavLink, Outlet } from 'react-router-dom';

const NAV_ITEMS = [
  { to: '/', label: 'Home', icon: '⌂' },
  { to: '/exercises', label: 'Exercises', icon: '◎' },
  { to: '/plans', label: 'Plans', icon: '▤' },
  { to: '/log', label: 'History', icon: '▦' },
  { to: '/profile', label: 'Profile', icon: '○' },
];

export default function Layout() {
  return (
    <div className="min-h-screen bg-bg-primary">
      <main className="pb-20">
        <Outlet />
      </main>

      <nav className="fixed bottom-0 left-0 right-0 bg-bg-secondary border-t border-bg-tertiary"
           style={{ paddingBottom: 'env(safe-area-inset-bottom, 0)' }}>
        <div className="flex justify-around items-center h-16 max-w-lg mx-auto">
          {NAV_ITEMS.map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex flex-col items-center gap-0.5 px-3 py-1 text-xs transition-colors ${
                  isActive ? 'text-accent-blue' : 'text-text-muted'
                }`
              }
            >
              <span className="text-lg">{icon}</span>
              <span>{label}</span>
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}
