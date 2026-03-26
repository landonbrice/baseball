import { useMemo, useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../App';
import { useAppContext } from '../hooks/useChatState';
import { usePitcher } from '../hooks/usePitcher';
import { useApi } from '../hooks/useApi';
import WeekStrip from '../components/WeekStrip';
import DailyCard from '../components/DailyCard';
import TrendChart from '../components/TrendChart';
import UpcomingDays from '../components/UpcomingDays';
import InsightsCard from '../components/InsightsCard';
import SessionProgress from '../components/SessionProgress';
import Sparkline from '../components/Sparkline';
import StreakBadge from '../components/StreakBadge';
import StaffPulse from '../components/StaffPulse';

export default function Home() {
  const { pitcherId, initData } = useAuth();
  const { globalRefreshKey } = useAppContext();
  const navigate = useNavigate();
  const suffix = globalRefreshKey ? `?_r=${globalRefreshKey}` : '';
  const { profile, log, progression, loading, error } = usePitcher(pitcherId, initData, suffix);
  const exercises = useApi('/api/exercises', initData);
  const slugs = useApi('/api/exercises/slugs', initData);
  const upcoming = useApi(pitcherId ? `/api/pitcher/${pitcherId}/upcoming${suffix}` : null, initData);
  const weekSummary = useApi(pitcherId ? `/api/pitcher/${pitcherId}/week-summary${suffix}` : null, initData);
  const trendData = useApi(pitcherId ? `/api/pitcher/${pitcherId}/trend${suffix}` : null, initData);
  const staffPulse = useApi('/api/staff/pulse', initData);

  const exerciseMap = useMemo(() => {
    if (!exercises.data?.exercises) return {};
    const map = {};
    for (const ex of exercises.data.exercises) map[ex.id] = ex;
    return map;
  }, [exercises.data]);
  const slugMap = useMemo(() => slugs.data || {}, [slugs.data]);
  const [selectedDate, setSelectedDate] = useState(null);

  const entries = log?.entries || [];
  const todayStr = new Date().toISOString().split('T')[0];
  const todayEntry = entries.find(e => e.date === todayStr) || entries[entries.length - 1];
  const displayEntry = useMemo(() => {
    if (!selectedDate) return todayEntry;
    return entries.find(e => e.date === selectedDate) || null;
  }, [selectedDate, entries, todayEntry]);

  if (loading) return <div style={{ padding: 20 }}><p>Loading...</p></div>;

  const flags = profile?.active_flags || {};

  // SECTION A: just test the header
  const firstName = String((profile?.name || 'Dashboard').split(' ')[0]);
  const role = String(profile?.role || 'starter');

  return (
    <div style={{ paddingBottom: 20 }}>
      <p style={{ padding: '8px 12px', fontSize: 9, color: '#999' }}>v6 bisect</p>

      {/* SECTION A: Header */}
      <div style={{ background: '#5c1020', padding: '14px 16px 12px' }}>
        <div style={{ fontSize: 9, color: '#e8a0aa' }}>{'UChicago Baseball'}</div>
        <div style={{ fontSize: 20, fontWeight: 800, color: '#fff' }}>
          {firstName}
        </div>
        <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)' }}>{role}</div>
      </div>

      {/* SECTION B: Components with real data (proven working in v5) */}
      <div style={{ padding: '0 12px' }}>
        <WeekStrip week={weekSummary.data?.week || []} selectedDate={selectedDate} onDayClick={(d) => setSelectedDate(prev => prev === d ? null : d)} />
        <div style={{ marginTop: 8 }}><DailyCard entry={displayEntry || todayEntry} exerciseMap={exerciseMap} slugMap={slugMap} pitcherId={pitcherId} initData={initData} readOnly={true} /></div>
        <UpcomingDays upcoming={upcoming.data?.upcoming} exerciseMap={exerciseMap} />
        <TrendChart entries={entries} />
        <InsightsCard observations={progression?.observations} trendWeeks={Array.isArray(trendData.data?.weeks) ? trendData.data.weeks : []} />
        {staffPulse.data && <div style={{ marginTop: 12 }}><StaffPulse data={staffPulse.data} /></div>}
      </div>
    </div>
  );
}
