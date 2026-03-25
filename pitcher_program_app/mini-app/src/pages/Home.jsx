import { useMemo, useCallback, useState } from 'react';
import { useAuth } from '../App';
import { useAppContext } from '../hooks/useChatState';
import { usePitcher } from '../hooks/usePitcher';
import { useApi } from '../hooks/useApi';
import WeekStrip from '../components/WeekStrip';
import DailyCard from '../components/DailyCard';
import TrendChart from '../components/TrendChart';
import UpcomingDays from '../components/UpcomingDays';
import InsightsCard from '../components/InsightsCard';

export default function Home() {
  const { pitcherId, initData } = useAuth();
  const { globalRefreshKey } = useAppContext();

  const suffix = globalRefreshKey ? `?_r=${globalRefreshKey}` : '';
  const { profile, log, progression, loading, error } = usePitcher(pitcherId, initData, suffix);
  const exercises = useApi('/api/exercises', initData);
  const slugs = useApi('/api/exercises/slugs', initData);
  const upcoming = useApi(pitcherId ? `/api/pitcher/${pitcherId}/upcoming${suffix}` : null, initData);
  const weekSummary = useApi(pitcherId ? `/api/pitcher/${pitcherId}/week-summary${suffix}` : null, initData);

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
  const rotationPct = Math.min(100, (dayssinceOuting / rotationLength) * 100);
  const firstName = (profile?.name || 'Dashboard').split(' ')[0];
  const flagLevel = flags.current_flag_level || 'green';
  const isNewPitcher = !entries.length && !flags.last_outing_date;

  // Brief + stats from today's entry
  const morningBrief = todayEntry?.morning_brief || todayEntry?.plan_generated?.morning_brief;
  const sleepHours = todayEntry?.pre_training?.sleep_hours;
  const estDuration = todayEntry?.lifting?.estimated_duration_min || todayEntry?.plan_generated?.estimated_duration_min;

  // Session progress
  const completed = todayEntry?.completed_exercises || {};
  const allExercises = [
    ...(todayEntry?.arm_care?.exercises || todayEntry?.plan_generated?.arm_care?.exercises || []),
    ...(todayEntry?.lifting?.exercises || todayEntry?.plan_generated?.lifting?.exercises || []),
  ];
  const totalEx = allExercises.length;
  const doneEx = allExercises.filter(ex => completed[ex.exercise_id] === true).length;
  const donePct = totalEx > 0 ? Math.round((doneEx / totalEx) * 100) : 0;

  const flagDot = flagLevel === 'green' ? 'var(--color-flag-green)'
               : flagLevel === 'yellow' ? 'var(--color-flag-yellow)'
               : 'var(--color-flag-red)';

  return (
    <div style={{ paddingBottom: 20 }}>
      {/* ── Maroon header band ── */}
      <div style={{ background: 'var(--color-maroon)', padding: '14px 16px 12px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
          <div>
            <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.45)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 3 }}>
              Day {dayssinceOuting} · {profile?.role || 'starter'} · {rotationLength}-day
            </div>
            <div style={{ fontSize: 20, fontWeight: 800, color: '#fff', letterSpacing: '-0.5px' }}>
              {firstName}
            </div>
          </div>
          {/* Arm feel ring */}
          <div style={{ background: 'rgba(255,255,255,0.12)', borderRadius: 10, padding: '5px 10px', textAlign: 'center' }}>
            <div style={{ fontSize: 16, fontWeight: 800, color: '#fff', lineHeight: 1.1 }}>{armFeel ?? '–'}</div>
            <div style={{ fontSize: 8, color: 'rgba(255,255,255,0.45)', marginTop: 1 }}>arm</div>
          </div>
        </div>
        {/* Rotation progress bar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <div style={{ flex: 1, height: 3, background: 'rgba(255,255,255,0.12)', borderRadius: 2, overflow: 'hidden' }}>
            <div style={{ width: `${rotationPct}%`, height: '100%', background: 'var(--color-rose-blush)', borderRadius: 2 }} />
          </div>
          {daysUntilOuting != null && (
            <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.4)' }}>outing in {daysUntilOuting}d</span>
          )}
        </div>
      </div>

      {/* ── Week strip ── */}
      {!isNewPitcher && (
        <WeekStrip
          week={weekSummary.data?.week || []}
          selectedDate={selectedDate}
          onDayClick={handleDayClick}
        />
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
                {/* Flag + label */}
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
                {/* Stat row */}
                {todayEntry && (
                  <div style={{ display: 'flex', marginTop: 8, borderTop: '0.5px solid var(--color-cream-border)', paddingTop: 8 }}>
                    <StatCol label="arm" value={armFeel != null ? `${armFeel}/5` : '–'} />
                    <div style={{ width: 0.5, background: 'var(--color-cream-border)' }} />
                    <StatCol label="sleep" value={sleepHours != null ? `${sleepHours}h` : '–'} />
                    <div style={{ width: 0.5, background: 'var(--color-cream-border)' }} />
                    <StatCol label="est. duration" value={estDuration ? `${estDuration}m` : '–'} />
                  </div>
                )}
              </div>
            )}

            {/* ── Daily plan card ── */}
            <div style={{ marginTop: 12 }}>
              <DailyCard
                entry={displayEntry}
                exerciseMap={exerciseMap}
                slugMap={slugMap}
                pitcherId={pitcherId}
                initData={initData}
                readOnly={!!isViewingPast}
              />
            </div>

            {/* ── Session progress bar ── */}
            {totalEx > 0 && !isViewingPast && (
              <div style={{ marginTop: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={{ fontSize: 10, color: 'var(--color-ink-secondary)' }}>{doneEx} / {totalEx} done</span>
                  <span style={{ fontSize: 10, color: 'var(--color-maroon)', fontWeight: 600 }}>{donePct}%</span>
                </div>
                <div style={{ height: 2, background: 'var(--color-cream-border)', borderRadius: 1, overflow: 'hidden' }}>
                  <div style={{ width: `${donePct}%`, height: '100%', background: 'var(--color-maroon)', borderRadius: 1, transition: 'width 0.3s' }} />
                </div>
              </div>
            )}
          </>
        )}

        {/* Coming up */}
        <UpcomingDays upcoming={upcoming.data?.upcoming} exerciseMap={exerciseMap} />

        {/* Arm feel trend */}
        {entries.length > 0 && <TrendChart entries={entries} />}

        {/* Insights */}
        <InsightsCard observations={progression?.observations} />
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
