import { useMemo, useCallback, useState, Component } from 'react';
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

class Safe extends Component {
  constructor(props) { super(props); this.state = { error: null }; }
  static getDerivedStateFromError(error) { return { error }; }
  render() {
    if (this.state.error) {
      return <div style={{ padding: 8, margin: '4px 12px', background: '#fff0f0', borderRadius: 8, border: '1px solid #f5c6cb' }}>
        <p style={{ fontSize: 11, color: '#A32D2D', margin: 0, fontWeight: 600 }}>[{this.props.name}] {String(this.state.error)}</p>
      </div>;
    }
    return this.props.children;
  }
}

export default function Home() {
  const { pitcherId, initData } = useAuth();
  const { globalRefreshKey } = useAppContext();
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

  const entries = log?.entries || [];
  const todayStr = new Date().toISOString().split('T')[0];
  const todayEntry = entries.find(e => e.date === todayStr) || entries[entries.length - 1];
  const flags = profile?.active_flags || {};

  if (loading) return <div style={{ padding: 20 }}><p>Loading...</p></div>;

  return (
    <div style={{ padding: 12, paddingBottom: 20 }}>
      <p style={{ fontSize: 14, color: '#5c1020', fontWeight: 700, margin: '0 0 8px' }}>v5 Real Data Test</p>

      <Safe name="WeekStrip-real">
        <WeekStrip week={weekSummary.data?.week || []} selectedDate={null} onDayClick={() => {}} />
      </Safe>

      <Safe name="StaffPulse-real">
        <StaffPulse data={staffPulse.data} />
      </Safe>

      <Safe name="SessionProgress-real">
        <SessionProgress doneCount={0} totalCount={0} />
      </Safe>

      <Safe name="InsightsCard-real">
        <InsightsCard observations={progression?.observations} trendWeeks={Array.isArray(trendData.data?.weeks) ? trendData.data.weeks : []} />
      </Safe>

      <Safe name="Sparkline-real">
        <Sparkline data={Array.isArray(trendData.data?.sparkline) ? trendData.data.sparkline : []} outingIndices={[]} />
      </Safe>

      <Safe name="StreakBadge-real">
        <StreakBadge streak={trendData.data?.current_streak || 0} weekDots={(weekSummary.data?.week || []).map(d => !!d.flag_level)} />
      </Safe>

      <Safe name="TrendChart-real">
        <TrendChart entries={entries} />
      </Safe>

      <Safe name="UpcomingDays-real">
        <UpcomingDays upcoming={upcoming.data?.upcoming} exerciseMap={exerciseMap} />
      </Safe>

      <Safe name="DailyCard-real">
        <DailyCard entry={todayEntry} exerciseMap={exerciseMap} slugMap={slugMap} pitcherId={pitcherId} initData={initData} readOnly={true} />
      </Safe>
    </div>
  );
}
