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
    <div style={{ minHeight: '100vh', background: 'var(--color-cream-bg)' }}>
      <main style={{ paddingBottom: 80 }}>
        <Outlet />
      </main>

      <nav style={{
        position: 'fixed', bottom: 0, left: 0, right: 0,
        background: 'var(--color-white)',
        borderTop: '0.5px solid var(--color-cream-border)',
        paddingBottom: 'env(safe-area-inset-bottom, 0)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-around', alignItems: 'center', height: 56, maxWidth: 480, margin: '0 auto' }}>
          {NAV_ITEMS.map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              style={{ textDecoration: 'none' }}
            >
              {({ isActive }) => (
                <div style={{
                  display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
                  padding: '4px 12px',
                }}>
                  {/* Active dot */}
                  <div style={{
                    width: 4, height: 4, borderRadius: '50%',
                    background: isActive ? 'var(--color-maroon)' : 'transparent',
                    marginBottom: 1,
                  }} />
                  <span style={{
                    fontSize: 16,
                    color: isActive ? 'var(--color-maroon)' : 'var(--color-ink-faint)',
                  }}>{icon}</span>
                  <span style={{
                    fontSize: 10,
                    color: isActive ? 'var(--color-maroon)' : 'var(--color-ink-faint)',
                    fontWeight: isActive ? 600 : 400,
                  }}>{label}</span>
                </div>
              )}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}
