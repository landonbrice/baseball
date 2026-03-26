import { useMemo, useCallback, useState, Component } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../App';
import { useAppContext } from '../hooks/useChatState';
import { usePitcher } from '../hooks/usePitcher';
import { useApi } from '../hooks/useApi';

// Phase 4 components — each wrapped in Safe below
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
      return (
        <div style={{ padding: 8, margin: '4px 12px', background: '#fff0f0', borderRadius: 8, border: '1px solid #f5c6cb' }}>
          <p style={{ fontSize: 11, color: '#A32D2D', margin: 0, fontWeight: 600 }}>
            [{this.props.name}] crashed
          </p>
          <p style={{ fontSize: 9, color: '#6b5f58', margin: '4px 0 0' }}>
            {String(this.state.error)}
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}

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
  const handleDayClick = useCallback((dateStr) => {
    setSelectedDate(prev => prev === dateStr ? null : dateStr);
  }, []);

  const entries = log?.entries || [];
  const todayStr = new Date().toISOString().split('T')[0];
  const todayEntry = entries.find(e => e.date === todayStr) || entries[entries.length - 1];

  const displayEntry = useMemo(() => {
    if (!selectedDate) return todayEntry;
    return entries.find(e => e.date === selectedDate) || null;
  }, [selectedDate, entries, todayEntry]);

  const isViewingPast = selectedDate && selectedDate !== todayStr;

  if (loading) return <PageSkeleton />;
  if (error) return <div style={{ padding: 16 }}><p style={{ color: '#A32D2D', fontSize: 14 }}>Failed to load data.</p></div>;

  const flags = profile?.active_flags || {};
  const armFeel = flags.current_arm_feel;
  const dso = flags.days_since_outing ?? 0;
  const rotLen = profile?.rotation_length || 7;
  const daysUntil = flags.next_outing_days;
  const firstName = String((profile?.name || 'Dashboard').split(' ')[0]);
  const flagLevel = String(flags.current_flag_level || 'green');
  const isNewPitcher = !entries.length && !flags.last_outing_date;
  const role = String(profile?.role || 'starter');
  const roleLabel = role === 'starter' ? 'Starter' : 'Reliever';
  const hasCheckedIn = !!(todayEntry?.pre_training?.arm_feel);

  // Guard all rendered values as primitives
  const rawBrief = todayEntry?.morning_brief || todayEntry?.plan_generated?.morning_brief;
  const morningBrief = typeof rawBrief === 'string' ? rawBrief : null;
  const sleepHours = typeof todayEntry?.pre_training?.sleep_hours === 'number' ? todayEntry.pre_training.sleep_hours : null;
  const estDuration = todayEntry?.lifting?.estimated_duration_min || todayEntry?.plan_generated?.estimated_duration_min || null;

  const rawCE = todayEntry?.completed_exercises;
  const completed = (rawCE && typeof rawCE === 'object' && !Array.isArray(rawCE)) ? rawCE : {};
  const allExercises = [
    ...(todayEntry?.arm_care?.exercises || todayEntry?.plan_generated?.arm_care?.exercises || []),
    ...(todayEntry?.lifting?.exercises || todayEntry?.plan_generated?.lifting?.exercises || []),
  ];
  const totalEx = allExercises.length;
  const doneEx = allExercises.filter(ex => completed[ex.exercise_id] === true).length;

  const flagDot = flagLevel === 'green' ? '#1D9E75' : flagLevel === 'yellow' ? '#BA7517' : '#A32D2D';

  const sparkline = Array.isArray(trendData.data?.sparkline) ? trendData.data.sparkline : [];
  const outingIdx = Array.isArray(trendData.data?.outing_day_indices) ? trendData.data.outing_day_indices : [];
  const streak = typeof trendData.data?.current_streak === 'number' ? trendData.data.current_streak : 0;
  const trendWeeks = Array.isArray(trendData.data?.weeks) ? trendData.data.weeks : [];
  const weekDots = Array.isArray(weekSummary.data?.week) ? weekSummary.data.week.map(d => !!d.flag_level) : [];

  const nextLabel = useMemo(() => {
    if (daysUntil == null) return null;
    if (daysUntil === 0) return 'Today';
    if (daysUntil === 1) return 'Tomorrow';
    const d = new Date(); d.setDate(d.getDate() + daysUntil);
    return d.toLocaleDateString('en-US', { weekday: 'long' });
  }, [daysUntil]);

  return (
    <div style={{ paddingBottom: 20 }}>
      {/* 1. Header */}
      <Safe name="Header">
        <div style={{ background: '#5c1020', padding: '14px 16px 0' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
            <div>
              <div style={{ fontSize: 9, color: '#e8a0aa', letterSpacing: '0.06em' }}>UChicago Baseball</div>
              <div style={{ fontSize: 20, fontWeight: 800, color: '#fff', letterSpacing: '-0.5px' }}>
                {firstName} <span style={{ fontSize: 13, fontWeight: 600 }}>{roleLabel}</span>
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Safe name="Sparkline"><Sparkline data={sparkline} outingIndices={outingIdx} /></Safe>
              <div style={{ background: 'rgba(255,255,255,0.12)', borderRadius: 10, padding: '5px 10px', textAlign: 'center' }}>
                <div style={{ fontSize: 16, fontWeight: 800, color: '#fff', lineHeight: 1.1 }}>{armFeel ?? '\u2013'}</div>
                <div style={{ fontSize: 8, color: 'rgba(255,255,255,0.45)', marginTop: 1 }}>arm</div>
              </div>
            </div>
          </div>
          <div style={{ borderTop: '0.5px solid rgba(255,255,255,0.12)', padding: '8px 0 12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', gap: 16 }}>
              {nextLabel && <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)' }}>Next: <strong style={{ color: '#fff' }}>{nextLabel}</strong></span>}
              {totalEx > 0 && <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)' }}>{totalEx} exercises</span>}
            </div>
            <Safe name="StreakBadge"><StreakBadge streak={streak} weekDots={weekDots} /></Safe>
          </div>
        </div>
      </Safe>

      {/* 2. Check-in banner */}
      <Safe name="CheckinBanner">
        {!isNewPitcher && !hasCheckedIn && (
          <div onClick={() => navigate('/coach')} style={{ margin: '8px 12px 0', border: '1.5px solid #e8a0aa', background: 'rgba(92,16,32,0.05)', borderRadius: 12, padding: '10px 14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}>
            <div>
              <div style={{ fontSize: 12, fontWeight: 700, color: '#2a1a18' }}>Morning check-in</div>
              <div style={{ fontSize: 10, color: '#b0a89e', marginTop: 2 }}>Check in to get today's personalized plan</div>
            </div>
            <div style={{ background: '#5c1020', borderRadius: 8, padding: '6px 14px', fontSize: 11, fontWeight: 700, color: '#fff' }}>Check In</div>
          </div>
        )}
      </Safe>

      {/* 3. Session progress */}
      <Safe name="SessionProgress">
        {totalEx > 0 && !isViewingPast && hasCheckedIn && (
          <div style={{ padding: '8px 12px 0' }}><SessionProgress doneCount={doneEx} totalCount={totalEx} /></div>
        )}
      </Safe>

      {/* 4. Week strip */}
      <Safe name="WeekStrip">
        {!isNewPitcher && (
          <div style={{ padding: '8px 12px 0' }}>
            <WeekStrip week={weekSummary.data?.week || []} selectedDate={selectedDate} onDayClick={handleDayClick} />
          </div>
        )}
      </Safe>

      <div style={{ padding: '0 12px' }}>
        {isNewPitcher ? (
          <div style={{ background: '#fff', borderRadius: 12, padding: 16, textAlign: 'center', marginTop: 12 }}>
            <p style={{ fontSize: 14, color: '#2a1a18', marginBottom: 4 }}>You're set up.</p>
            <p style={{ fontSize: 12, color: '#b0a89e' }}>Head to the Coach tab to check in or log an outing to get your first plan.</p>
          </div>
        ) : (
          <>
            {isViewingPast && (
              <div style={{ textAlign: 'center', marginTop: 8 }}>
                <button onClick={() => setSelectedDate(null)} style={{ padding: '4px 14px', fontSize: 11, fontWeight: 600, background: '#5c1020', color: '#fff', border: 'none', borderRadius: 14, cursor: 'pointer' }}>Back to today</button>
              </div>
            )}

            {/* Brief card */}
            <Safe name="BriefCard">
              {(morningBrief || !todayEntry) && (
                <div style={{ background: '#fdf8f8', borderLeft: '3px solid #5c1020', borderRadius: '0 10px 10px 0', padding: '10px 14px', marginTop: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                    <div style={{ width: 6, height: 6, borderRadius: '50%', background: flagDot }} />
                    <span style={{ fontSize: 9, color: '#b0a89e', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>
                      {flagLevel} {'\u00B7'} {todayEntry ? 'full session' : 'check in to start'}
                    </span>
                  </div>
                  {morningBrief && <p style={{ fontSize: 11, color: '#6b5f58', lineHeight: 1.6, fontStyle: 'italic', margin: 0 }}>{morningBrief}</p>}
                  {todayEntry && (
                    <div style={{ display: 'flex', marginTop: 8, borderTop: '0.5px solid #e4dfd8', paddingTop: 8 }}>
                      <StatCol label="arm" value={armFeel != null ? `${armFeel}/5` : '\u2013'} />
                      <div style={{ width: 0.5, background: '#e4dfd8' }} />
                      <StatCol label="sleep" value={sleepHours != null ? `${sleepHours}h` : '\u2013'} />
                      <div style={{ width: 0.5, background: '#e4dfd8' }} />
                      <StatCol label="est." value={estDuration ? `${estDuration}m` : '\u2013'} />
                    </div>
                  )}
                </div>
              )}
            </Safe>

            {/* Daily plan */}
            <Safe name="DailyCard">
              <div style={{ marginTop: 12 }}>
                <DailyCard entry={displayEntry} exerciseMap={exerciseMap} slugMap={slugMap} pitcherId={pitcherId} initData={initData} readOnly={!!isViewingPast} />
              </div>
            </Safe>
          </>
        )}

        <Safe name="UpcomingDays"><UpcomingDays upcoming={upcoming.data?.upcoming} exerciseMap={exerciseMap} /></Safe>
        <Safe name="TrendChart">{entries.length > 0 && <TrendChart entries={entries} />}</Safe>
        <Safe name="InsightsCard"><InsightsCard observations={progression?.observations} trendWeeks={trendWeeks} /></Safe>
        <Safe name="StaffPulse">{staffPulse.data && <div style={{ marginTop: 12 }}><StaffPulse data={staffPulse.data} /></div>}</Safe>
      </div>
    </div>
  );
}

function StatCol({ label, value }) {
  return (
    <div style={{ flex: 1, textAlign: 'center' }}>
      <div style={{ fontSize: 13, fontWeight: 600, color: '#2a1a18' }}>{String(value)}</div>
      <div style={{ fontSize: 8, color: '#b0a89e', marginTop: 1, textTransform: 'uppercase' }}>{String(label)}</div>
    </div>
  );
}

function PageSkeleton() {
  return (
    <div style={{ padding: 16 }}>
      <div style={{ height: 80, background: '#e4dfd8', borderRadius: 10, marginBottom: 12 }} />
      <div style={{ display: 'flex', gap: 4 }}>
        {[...Array(7)].map((_, i) => <div key={i} style={{ flex: 1, height: 50, background: '#e4dfd8', borderRadius: 7 }} />)}
      </div>
      <div style={{ height: 120, background: '#e4dfd8', borderRadius: 12, marginTop: 12 }} />
    </div>
  );
}
