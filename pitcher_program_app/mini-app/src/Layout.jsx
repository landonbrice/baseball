import { NavLink, Outlet } from 'react-router-dom';
import { Component } from 'react';
import { useAppContext } from './hooks/useChatState';
import CoachFAB from './components/CoachFAB';

class SafeWrap extends Component {
  constructor(props) { super(props); this.state = { error: null }; }
  static getDerivedStateFromError(error) { return { error }; }
  render() { return this.state.error ? null : this.props.children; }
}

const NAV_ITEMS = [
  { to: '/',        label: 'Home',    icon: '🏠' },
  { to: '/plans',   label: 'Program', icon: '📋' },
  { to: '/log',     label: 'Season',  icon: '📊' },
  { to: '/profile', label: 'Profile', icon: '👤' },
];

export default function Layout() {
  const { coachBadge, checkinInProgress } = useAppContext();

  return (
    <div style={{ minHeight: '100vh', background: 'var(--color-cream-bg)' }}>
      <main style={{ paddingBottom: 80 }}>
        <Outlet />
      </main>

      {/* Coach floating action button */}
      <SafeWrap><CoachFAB showBadge={coachBadge || checkinInProgress} /></SafeWrap>

      <nav style={{
        position: 'fixed', bottom: 0, left: 0, right: 0,
        background: 'var(--color-white)',
        borderTop: '0.5px solid var(--color-cream-border)',
        paddingBottom: 'env(safe-area-inset-bottom, 0)',
        zIndex: 10,
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
                  padding: '4px 12px', position: 'relative',
                }}>
                  {/* Active dot */}
                  <div style={{
                    width: 4, height: 4, borderRadius: '50%',
                    background: isActive ? 'var(--color-maroon)' : 'transparent',
                    marginBottom: 1,
                  }} />
                  <span style={{
                    fontSize: 20,
                    filter: isActive ? 'none' : 'grayscale(80%)',
                    opacity: isActive ? 1 : 0.5,
                  }}>
                    {icon}
                  </span>
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
