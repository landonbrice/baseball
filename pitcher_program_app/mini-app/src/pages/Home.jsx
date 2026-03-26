import { useMemo, useCallback, useState } from 'react';
import { useAuth } from '../App';
import { useAppContext } from '../hooks/useChatState';
import { usePitcher } from '../hooks/usePitcher';
import { useApi } from '../hooks/useApi';

// Import ALL components — test if just importing crashes
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
  const suffix = globalRefreshKey ? `?_r=${globalRefreshKey}` : '';
  const { profile, log, progression, loading, error } = usePitcher(pitcherId, initData, suffix);
  const weekSummary = useApi(pitcherId ? `/api/pitcher/${pitcherId}/week-summary${suffix}` : null, initData);
  const trendData = useApi(pitcherId ? `/api/pitcher/${pitcherId}/trend${suffix}` : null, initData);
  const staffPulse = useApi('/api/staff/pulse', initData);
  const exercises = useApi('/api/exercises', initData);
  const slugs = useApi('/api/exercises/slugs', initData);
  const upcoming = useApi(pitcherId ? `/api/pitcher/${pitcherId}/upcoming${suffix}` : null, initData);

  if (loading) return <div style={{ padding: 20 }}><p>Loading...</p></div>;

  // Render NOTHING from components yet — just confirm imports work
  return (
    <div style={{ padding: 20 }}>
      <p style={{ fontSize: 16, color: '#5c1020', fontWeight: 700 }}>v4 Import Test</p>
      <p style={{ fontSize: 11 }}>All components imported successfully.</p>
      <p style={{ fontSize: 11 }}>WeekStrip: {String(typeof WeekStrip)}</p>
      <p style={{ fontSize: 11 }}>DailyCard: {String(typeof DailyCard)}</p>
      <p style={{ fontSize: 11 }}>TrendChart: {String(typeof TrendChart)}</p>
      <p style={{ fontSize: 11 }}>Sparkline: {String(typeof Sparkline)}</p>
      <p style={{ fontSize: 11 }}>StreakBadge: {String(typeof StreakBadge)}</p>
      <p style={{ fontSize: 11 }}>SessionProgress: {String(typeof SessionProgress)}</p>
      <p style={{ fontSize: 11 }}>StaffPulse: {String(typeof StaffPulse)}</p>
      <p style={{ fontSize: 11 }}>InsightsCard: {String(typeof InsightsCard)}</p>
      <p style={{ fontSize: 11 }}>UpcomingDays: {String(typeof UpcomingDays)}</p>
      <hr />
      <p style={{ fontSize: 11, fontWeight: 600 }}>Now rendering components one by one:</p>

      <div style={{ marginTop: 8, padding: 8, background: '#f5f1eb', borderRadius: 8 }}>
        <p style={{ fontSize: 9, color: '#999', margin: '0 0 4px' }}>SessionProgress:</p>
        <SessionProgress doneCount={0} totalCount={5} />
      </div>

      <div style={{ marginTop: 8, padding: 8, background: '#f5f1eb', borderRadius: 8 }}>
        <p style={{ fontSize: 9, color: '#999', margin: '0 0 4px' }}>Sparkline:</p>
        <Sparkline data={[3,4,5,4,3]} outingIndices={[]} />
      </div>

      <div style={{ marginTop: 8, padding: 8, background: '#f5f1eb', borderRadius: 8 }}>
        <p style={{ fontSize: 9, color: '#999', margin: '0 0 4px' }}>StreakBadge:</p>
        <StreakBadge streak={3} weekDots={[true,true,true,false,false,false,false]} />
      </div>

      <div style={{ marginTop: 8, padding: 8, background: '#f5f1eb', borderRadius: 8 }}>
        <p style={{ fontSize: 9, color: '#999', margin: '0 0 4px' }}>WeekStrip:</p>
        <WeekStrip week={weekSummary.data?.week || []} selectedDate={null} onDayClick={() => {}} />
      </div>

      <div style={{ marginTop: 8, padding: 8, background: '#f5f1eb', borderRadius: 8 }}>
        <p style={{ fontSize: 9, color: '#999', margin: '0 0 4px' }}>StaffPulse:</p>
        <StaffPulse data={staffPulse.data} />
      </div>

      <div style={{ marginTop: 8, padding: 8, background: '#f5f1eb', borderRadius: 8 }}>
        <p style={{ fontSize: 9, color: '#999', margin: '0 0 4px' }}>InsightsCard:</p>
        <InsightsCard observations={[]} trendWeeks={[]} />
      </div>

      <div style={{ marginTop: 8, padding: 8, background: '#f5f1eb', borderRadius: 8 }}>
        <p style={{ fontSize: 9, color: '#999', margin: '0 0 4px' }}>TrendChart:</p>
        <TrendChart entries={log?.entries || []} />
      </div>

      <div style={{ marginTop: 8, padding: 8, background: '#f5f1eb', borderRadius: 8 }}>
        <p style={{ fontSize: 9, color: '#999', margin: '0 0 4px' }}>DailyCard:</p>
        <DailyCard entry={null} exerciseMap={{}} slugMap={{}} pitcherId={pitcherId} initData={initData} readOnly={true} />
      </div>
    </div>
  );
}
