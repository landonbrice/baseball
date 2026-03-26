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
  const firstName = String((profile?.name || 'Dashboard').split(' ')[0]);
  const role = String(profile?.role || 'starter');
  const roleLabel = role === 'starter' ? 'Starter' : 'Reliever';
  const flagLevel = String(flags.current_flag_level || 'green');
  const armFeel = typeof flags.current_arm_feel === 'number' ? flags.current_arm_feel : null;
  const isNewPitcher = !entries.length && !flags.last_outing_date;
  const hasCheckedIn = !!((todayEntry?.pre_training || {}).arm_feel);
  const isViewingPast = selectedDate && selectedDate !== todayStr;

  const rawBrief = todayEntry?.morning_brief || (todayEntry?.plan_generated || {}).morning_brief;
  const morningBrief = typeof rawBrief === 'string' ? rawBrief : null;
  const sleepHours = typeof (todayEntry?.pre_training || {}).sleep_hours === 'number' ? todayEntry.pre_training.sleep_hours : null;
  const rawDur = (todayEntry?.lifting || {}).estimated_duration_min || (todayEntry?.plan_generated || {}).estimated_duration_min;
  const estDuration = typeof rawDur === 'number' ? rawDur : null;
  const flagDot = flagLevel === 'green' ? '#1D9E75' : flagLevel === 'yellow' ? '#BA7517' : '#A32D2D';

  const rawCE = todayEntry?.completed_exercises;
  const completed = (rawCE && typeof rawCE === 'object' && !Array.isArray(rawCE)) ? rawCE : {};
  const allEx = [
    ...((todayEntry?.arm_care || {}).exercises || (todayEntry?.plan_generated?.arm_care || {}).exercises || []),
    ...((todayEntry?.lifting || {}).exercises || (todayEntry?.plan_generated?.lifting || {}).exercises || []),
  ];
  const totalEx = allEx.length;
  const doneEx = allEx.filter(ex => completed[ex.exercise_id] === true).length;
  const sparkline = Array.isArray(trendData.data?.sparkline) ? trendData.data.sparkline : [];
  const outingIdx = Array.isArray(trendData.data?.outing_day_indices) ? trendData.data.outing_day_indices : [];
  const streak = typeof trendData.data?.current_streak === 'number' ? trendData.data.current_streak : 0;
  const weekDots = Array.isArray(weekSummary.data?.week) ? weekSummary.data.week.map(d => !!d.flag_level) : [];
  const daysUntil = typeof flags.next_outing_days === 'number' ? flags.next_outing_days : null;
  const nextLabel = daysUntil == null ? null : daysUntil === 0 ? 'Today' : daysUntil === 1 ? 'Tomorrow' : new Date(Date.now() + daysUntil * 86400000).toLocaleDateString('en-US', { weekday: 'long' });

  return (
    <div style={{ paddingBottom: 20 }}>
      {/* Header */}
      <div style={{ background: '#5c1020', padding: '14px 16px 0' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
          <div>
            <div style={{ fontSize: 9, color: '#e8a0aa', letterSpacing: '0.06em' }}>{'UChicago Baseball'}</div>
            <div style={{ fontSize: 20, fontWeight: 800, color: '#fff', letterSpacing: '-0.5px' }}>
              {firstName}{' '}<span style={{ fontSize: 13, fontWeight: 600 }}>{roleLabel}</span>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Sparkline data={sparkline} outingIndices={outingIdx} />
            <div style={{ background: 'rgba(255,255,255,0.12)', borderRadius: 10, padding: '5px 10px', textAlign: 'center' }}>
              <div style={{ fontSize: 16, fontWeight: 800, color: '#fff', lineHeight: 1.1 }}>{armFeel != null ? String(armFeel) : '\u2013'}</div>
              <div style={{ fontSize: 8, color: 'rgba(255,255,255,0.45)', marginTop: 1 }}>{'arm'}</div>
            </div>
          </div>
        </div>
        {/* Footer row */}
        <div style={{ borderTop: '0.5px solid rgba(255,255,255,0.12)', padding: '8px 0 12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', gap: 16 }}>
            {nextLabel != null && <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)' }}>{'Next: '}<strong style={{ color: '#fff' }}>{String(nextLabel)}</strong></span>}
            {totalEx > 0 && <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)' }}>{String(totalEx) + ' exercises'}</span>}
          </div>
          <StreakBadge streak={streak} weekDots={weekDots} />
        </div>
      </div>

      {/* SessionProgress */}
      {totalEx > 0 && hasCheckedIn && (
        <div style={{ padding: '8px 12px 0' }}><SessionProgress doneCount={doneEx} totalCount={totalEx} /></div>
      )}

      {/* Check-in banner (same as v7) */}
      {!isNewPitcher && !hasCheckedIn && (
        <div onClick={() => navigate('/coach')} style={{ margin: '8px 12px 0', border: '1.5px solid #e8a0aa', background: 'rgba(92,16,32,0.05)', borderRadius: 12, padding: '10px 14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}>
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#2a1a18' }}>{'Morning check-in'}</div>
            <div style={{ fontSize: 10, color: '#b0a89e', marginTop: 2 }}>{"Check in to get today's personalized plan"}</div>
          </div>
          <div style={{ background: '#5c1020', borderRadius: 8, padding: '6px 14px', fontSize: 11, fontWeight: 700, color: '#fff' }}>{'Check In'}</div>
        </div>
      )}

      {/* Brief card (same as v7) */}
      {(morningBrief || !todayEntry) && (
        <div style={{ margin: '8px 12px 0', background: '#fdf8f8', borderLeft: '3px solid #5c1020', borderRadius: '0 10px 10px 0', padding: '10px 14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: flagDot }} />
            <span style={{ fontSize: 9, color: '#b0a89e', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>
              {String(flagLevel) + ' \u00B7 ' + (todayEntry ? 'full session' : 'check in to start')}
            </span>
          </div>
          {morningBrief != null && <p style={{ fontSize: 11, color: '#6b5f58', lineHeight: 1.6, fontStyle: 'italic', margin: 0 }}>{String(morningBrief)}</p>}
          {todayEntry && (
            <div style={{ display: 'flex', marginTop: 8, borderTop: '0.5px solid #e4dfd8', paddingTop: 8 }}>
              <StatCol label="arm" value={armFeel != null ? armFeel + '/5' : '\u2013'} />
              <div style={{ width: 0.5, background: '#e4dfd8' }} />
              <StatCol label="sleep" value={sleepHours != null ? sleepHours + 'h' : '\u2013'} />
              <div style={{ width: 0.5, background: '#e4dfd8' }} />
              <StatCol label="est." value={estDuration != null ? estDuration + 'm' : '\u2013'} />
            </div>
          )}
        </div>
      )}

      {/* NEW vs v7: WeekStrip with isNewPitcher guard */}
      {!isNewPitcher && (
        <div style={{ padding: '8px 12px 0' }}>
          <WeekStrip week={weekSummary.data?.week || []} selectedDate={selectedDate} onDayClick={(d) => setSelectedDate(prev => prev === d ? null : d)} />
        </div>
      )}

      <div style={{ padding: '0 12px' }}>
        {/* NEW vs v7: isNewPitcher conditional */}
        {isNewPitcher ? (
          <div style={{ background: '#fff', borderRadius: 12, padding: 16, textAlign: 'center', marginTop: 12 }}>
            <p style={{ fontSize: 14, color: '#2a1a18', marginBottom: 4 }}>{"You're set up."}</p>
            <p style={{ fontSize: 12, color: '#b0a89e' }}>{'Head to Coach to check in.'}</p>
          </div>
        ) : (
          <div>
            {isViewingPast && (
              <div style={{ textAlign: 'center', marginTop: 8 }}>
                <button onClick={() => setSelectedDate(null)} style={{ padding: '4px 14px', fontSize: 11, fontWeight: 600, background: '#5c1020', color: '#fff', border: 'none', borderRadius: 14, cursor: 'pointer' }}>{'Back to today'}</button>
              </div>
            )}
            <div style={{ marginTop: 12 }}>
              <DailyCard entry={displayEntry || todayEntry} exerciseMap={exerciseMap} slugMap={slugMap} pitcherId={pitcherId} initData={initData} readOnly={!!isViewingPast} />
            </div>
          </div>
        )}

        <UpcomingDays upcoming={upcoming.data?.upcoming} exerciseMap={exerciseMap} />
        {/* NEW vs v7: entries.length guard */}
        {entries.length > 0 && <TrendChart entries={entries} />}
        <InsightsCard observations={progression?.observations} trendWeeks={Array.isArray(trendData.data?.weeks) ? trendData.data.weeks : []} />
        {staffPulse.data && <div style={{ marginTop: 12 }}><StaffPulse data={staffPulse.data} /></div>}
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
