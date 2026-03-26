import { useAuth } from '../App';

export default function Home() {
  const { pitcherId } = useAuth();

  return (
    <div style={{ padding: 20 }}>
      <p style={{ fontSize: 16, color: '#5c1020', fontWeight: 700 }}>v2 Debug Home</p>
      <p style={{ fontSize: 12, color: '#6b5f58' }}>Pitcher: {pitcherId || 'none'}</p>
      <p style={{ fontSize: 11, color: '#b0a89e' }}>If you see this, Layout + Router work. Crash is in Home components.</p>
    </div>
  );
}
