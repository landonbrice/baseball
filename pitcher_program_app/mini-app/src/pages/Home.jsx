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

  if (error) {
    return (
      <div style={{ padding: 16 }}>
        <p style={{ color: 'var(--color-flag-red)', fontSize: 14 }}>Failed to load data. Check your connection.</p>
      </div>
    );
  }

  const flags = profile?.active_flags || {};
  const armFeel = flags.current_arm_feel;
  const dayssinceOuting = flags.days_since_outing ?? 0;
  const rotationLength = profile?.rotation_length || 7;
  const daysUntilOuting = flags.next_outing_days;
  const firstName = (profile?.name || 'Dashboard').split(' ')[0];
  const flagLevel = flags.current_flag_level || 'green';
  const isNewPitcher = !entries.length && !flags.last_outing_date;
  const role = profile?.role || 'starter';
  const roleLabel = role === 'starter' ? 'Starter' : 'Reliever';
  const hasCheckedInToday = !!(todayEntry?.pre_training?.arm_feel);

  // Brief + stats from today's entry
  const morningBrief = todayEntry?.morning_brief || todayEntry?.plan_generated?.morning_brief;
  const sleepHours = todayEntry?.pre_training?.sleep_hours;
  const estDuration = todayEntry?.lifting?.estimated_duration_min || todayEntry?.plan_generated?.estimated_duration_min;

  // Session progress — guard: completed_exercises can be [] or {} from Supabase
  const rawCompleted = todayEntry?.completed_exercises;
  const completed = (rawCompleted && !Array.isArray(rawCompleted)) ? rawCompleted : {};
  const allExercises = [
    ...(todayEntry?.arm_care?.exercises || todayEntry?.plan_generated?.arm_care?.exercises || []),
    ...(todayEntry?.lifting?.exercises || todayEntry?.plan_generated?.lifting?.exercises || []),
  ];
  const totalEx = allExercises.length;
  const doneEx = allExercises.filter(ex => completed[ex.exercise_id] === true).length;

  const flagDot = flagLevel === 'green' ? 'var(--color-flag-green)'
               : flagLevel === 'yellow' ? 'var(--color-flag-yellow)'
               : 'var(--color-flag-red)';

  // Trend data
  const sparkline = trendData.data?.sparkline || [];
  const outingDayIndices = trendData.data?.outing_day_indices || [];
  const currentStreak = trendData.data?.current_streak || 0;
  const trendWeeks = trendData.data?.weeks || [];

  // Week dots for streak badge (from weekSummary)
  const weekDots = (weekSummary.data?.week || []).map(d => !!d.flag_level);

  // Next outing day name
  const nextOutingLabel = useMemo(() => {
    if (daysUntilOuting == null) return null;
    if (daysUntilOuting === 0) return 'Today';
    if (daysUntilOuting === 1) return 'Tomorrow';
    const d = new Date();
    d.setDate(d.getDate() + daysUntilOuting);
    return d.toLocaleDateString('en-US', { weekday: 'long' });
  }, [daysUntilOuting]);

  return (
    <div style={{ paddingBottom: 20 }}>
      {/* ── 1. Enhanced header band ── */}
      <div style={{ background: 'var(--color-maroon)', padding: '14px 16px 0' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
          <div>
            <div style={{ fontSize: 9, color: 'var(--color-rose-blush)', letterSpacing: '0.06em' }}>
              UChicago Baseball
            </div>
            <div style={{ fontSize: 20, fontWeight: 800, color: '#fff', letterSpacing: '-0.5px' }}>
              {firstName}
              <span style={{ fontSize: 13, fontWeight: 600, marginLeft: 6 }}>{roleLabel}</span>
            </div>
          </div>
          {/* Arm feel + sparkline */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Sparkline data={sparkline} outingIndices={outingDayIndices} />
            <div style={{ background: 'rgba(255,255,255,0.12)', borderRadius: 10, padding: '5px 10px', textAlign: 'center' }}>
              <div style={{ fontSize: 16, fontWeight: 800, color: '#fff', lineHeight: 1.1 }}>{armFeel ?? '\u2013'}</div>
              <div style={{ fontSize: 8, color: 'rgba(255,255,255,0.45)', marginTop: 1 }}>arm</div>
            </div>
          </div>
        </div>

        {/* Footer row: next outing, session info, streak */}
        <div style={{
          borderTop: '0.5px solid rgba(255,255,255,0.12)',
          padding: '8px 0 12px',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <div style={{ display: 'flex', gap: 16 }}>
            {nextOutingLabel && (
              <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)' }}>
                Next: <strong style={{ color: '#fff' }}>{nextOutingLabel}</strong>
              </span>
            )}
            {totalEx > 0 && (
              <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)' }}>
                {totalEx} exercises{estDuration ? ` \u00B7 ~${estDuration}m` : ''}
              </span>
            )}
          </div>
          <StreakBadge streak={currentStreak} weekDots={weekDots} />
        </div>
      </div>

      {/* ── 2. Check-in banner (if not checked in) ── */}
      {!isNewPitcher && !hasCheckedInToday && (
        <div
          onClick={() => navigate('/coach')}
          style={{
            margin: '8px 12px 0',
            border: '1.5px solid var(--color-rose-blush)',
            background: 'rgba(92,16,32,0.05)',
            borderRadius: 12, padding: '10px 14px',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            cursor: 'pointer',
          }}
        >
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--color-ink-primary)' }}>
              Morning check-in
            </div>
            <div style={{ fontSize: 10, color: 'var(--color-ink-muted)', marginTop: 2 }}>
              Check in to get today's personalized plan
            </div>
          </div>
          <div style={{
            background: 'var(--color-maroon)', borderRadius: 8,
            padding: '6px 14px', fontSize: 11, fontWeight: 700, color: '#fff',
          }}>
            Check In
          </div>
        </div>
      )}

      {/* ── 3. Session progress ── */}
      {totalEx > 0 && !isViewingPast && hasCheckedInToday && (
        <div style={{ padding: '8px 12px 0' }}>
          <SessionProgress doneCount={doneEx} totalCount={totalEx} />
        </div>
      )}

      {/* ── 4. Week strip ── */}
      {!isNewPitcher && (
        <div style={{ padding: '8px 12px 0' }}>
          <WeekStrip
            week={weekSummary.data?.week || []}
            selectedDate={selectedDate}
            onDayClick={handleDayClick}
          />
        </div>
      )}

      <div style={{ padding: '0 12px' }}>
        {/* Welcome state */}
        {isNewPitcher ? (
          <div style={{ background: 'var(--color-white)', borderRadius: 12, padding: 16, textAlign: 'center', marginTop: 12 }}>
            <p style={{ fontSize: 14, color: 'var(--color-ink-primary)', marginBottom: 4 }}>You're set up.</p>
            <p style={{ fontSize: 12, color: 'var(--color-ink-muted)' }}>
              Head to the Coach tab to check in or log an outing to get your first plan.
            </p>
          </div>
        ) : (
          <>
            {/* Back to today */}
            {isViewingPast && (
              <div style={{ textAlign: 'center', marginTop: 8 }}>
                <button
                  onClick={() => setSelectedDate(null)}
                  style={{
                    padding: '4px 14px', fontSize: 11, fontWeight: 600,
                    background: 'var(--color-maroon)', color: '#fff',
                    border: 'none', borderRadius: 14, cursor: 'pointer',
                  }}
                >
                  Back to today
                </button>
              </div>
            )}

            {/* ── Brief card ── */}
            {(morningBrief || !todayEntry) && (
              <div style={{
                background: '#fdf8f8',
                borderLeft: '3px solid var(--color-maroon)',
                borderRadius: '0 10px 10px 0',
                padding: '10px 14px',
                marginTop: 12,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                  <div style={{ width: 6, height: 6, borderRadius: '50%', background: flagDot }} />
                  <span style={{ fontSize: 9, color: 'var(--color-ink-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>
                    {flagLevel} · {todayEntry ? 'full session' : 'check in to start'}
                  </span>
                </div>
                {morningBrief && (
                  <p style={{ fontSize: 11, color: 'var(--color-ink-secondary)', lineHeight: 1.6, fontStyle: 'italic', margin: 0 }}>
                    {morningBrief}
                  </p>
                )}
                {todayEntry && (
                  <div style={{ display: 'flex', marginTop: 8, borderTop: '0.5px solid var(--color-cream-border)', paddingTop: 8 }}>
                    <StatCol label="arm" value={armFeel != null ? `${armFeel}/5` : '\u2013'} />
                    <div style={{ width: 0.5, background: 'var(--color-cream-border)' }} />
                    <StatCol label="sleep" value={sleepHours != null ? `${sleepHours}h` : '\u2013'} />
                    <div style={{ width: 0.5, background: 'var(--color-cream-border)' }} />
                    <StatCol label="est. duration" value={estDuration ? `${estDuration}m` : '\u2013'} />
                  </div>
                )}
              </div>
            )}

            {/* ── 5. Today's plan card ── */}
            <div style={{ marginTop: 12 }}>
              {!hasCheckedInToday && todayEntry && (
                <p style={{ fontSize: 9, color: 'var(--color-ink-faint)', textAlign: 'right', marginBottom: 4 }}>
                  tap info for why
                </p>
              )}
              <DailyCard
                entry={displayEntry}
                exerciseMap={exerciseMap}
                slugMap={slugMap}
                pitcherId={pitcherId}
                initData={initData}
                readOnly={!!isViewingPast}
              />
            </div>
          </>
        )}

        {/* Coming up */}
        <UpcomingDays upcoming={upcoming.data?.upcoming} exerciseMap={exerciseMap} />

        {/* Arm feel trend */}
        {entries.length > 0 && <TrendChart entries={entries} />}

        {/* ── 6. Weekly insight + trend chart ── */}
        <InsightsCard observations={progression?.observations} trendWeeks={trendWeeks} />

        {/* ── 7. Staff pulse ── */}
        {staffPulse.data && (
          <div style={{ marginTop: 12 }}>
            <StaffPulse data={staffPulse.data} />
          </div>
        )}
      </div>
    </div>
  );
}

function StatCol({ label, value }) {
  return (
    <div style={{ flex: 1, textAlign: 'center' }}>
      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-ink-primary)' }}>{value}</div>
      <div style={{ fontSize: 8, color: 'var(--color-ink-muted)', marginTop: 1, textTransform: 'uppercase' }}>{label}</div>
    </div>
  );
}

function PageSkeleton() {
  return (
    <div style={{ padding: 16 }}>
      <div style={{ height: 80, background: 'var(--color-cream-border)', borderRadius: 10, marginBottom: 12 }} />
      <div style={{ display: 'flex', gap: 4 }}>
        {[...Array(7)].map((_, i) => (
          <div key={i} style={{ flex: 1, height: 50, background: 'var(--color-cream-border)', borderRadius: 7 }} />
        ))}
      </div>
      <div style={{ height: 120, background: 'var(--color-cream-border)', borderRadius: 12, marginTop: 12 }} />
    </div>
  );
}
