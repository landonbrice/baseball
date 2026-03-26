import { useAuth } from '../App';
import { useAppContext } from '../hooks/useChatState';
import { usePitcher } from '../hooks/usePitcher';
import { useApi } from '../hooks/useApi';

export default function Home() {
  const { pitcherId, initData } = useAuth();
  const { globalRefreshKey } = useAppContext();
  const suffix = globalRefreshKey ? `?_r=${globalRefreshKey}` : '';

  // Add hooks one at a time to find the crash
  const { profile, log, progression, loading, error } = usePitcher(pitcherId, initData, suffix);
  const weekSummary = useApi(pitcherId ? `/api/pitcher/${pitcherId}/week-summary${suffix}` : null, initData);
  const trendData = useApi(pitcherId ? `/api/pitcher/${pitcherId}/trend${suffix}` : null, initData);
  const staffPulse = useApi('/api/staff/pulse', initData);
  const exercises = useApi('/api/exercises', initData);

  if (loading) return <div style={{ padding: 20 }}><p>Loading...</p></div>;

  const flags = profile?.active_flags || {};
  const entries = log?.entries || [];

  return (
    <div style={{ padding: 20 }}>
      <p style={{ fontSize: 16, color: '#5c1020', fontWeight: 700 }}>v3 Hook Debug</p>
      <p style={{ fontSize: 11 }}>Pitcher: {String(pitcherId || 'none')}</p>
      <p style={{ fontSize: 11 }}>Profile: {String(profile?.name || 'no profile')}</p>
      <p style={{ fontSize: 11 }}>Role: {String(profile?.role || '?')}</p>
      <p style={{ fontSize: 11 }}>Entries: {String(entries.length)}</p>
      <p style={{ fontSize: 11 }}>Arm feel: {String(flags.current_arm_feel ?? 'null')}</p>
      <p style={{ fontSize: 11 }}>Flag: {String(flags.current_flag_level || '?')}</p>
      <p style={{ fontSize: 11 }}>WeekSummary: {String(weekSummary.loading ? 'loading' : weekSummary.error ? 'error' : 'ok')}</p>
      <p style={{ fontSize: 11 }}>Trend: {String(trendData.loading ? 'loading' : trendData.error ? 'error' : 'ok')}</p>
      <p style={{ fontSize: 11 }}>Staff: {String(staffPulse.loading ? 'loading' : staffPulse.error ? 'error' : 'ok')}</p>
      <p style={{ fontSize: 11 }}>Exercises: {String(exercises.loading ? 'loading' : exercises.error ? 'error' : 'ok')}</p>
      <p style={{ fontSize: 11 }}>Progression obs: {String(Array.isArray(progression?.observations) ? progression.observations.length + ' items' : typeof progression?.observations)}</p>
      <hr />
      <p style={{ fontSize: 9, color: '#999' }}>If you see this, all hooks work. Crash is in component rendering.</p>
    </div>
  );
}
