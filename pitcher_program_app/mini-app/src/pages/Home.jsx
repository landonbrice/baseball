import { useMemo, useCallback, useState } from 'react';
import { useAuth } from '../App';
import { usePitcher } from '../hooks/usePitcher';
import { useApi } from '../hooks/useApi';
import FlagBadge from '../components/FlagBadge';
import WeekStrip from '../components/WeekStrip';
import DailyCard from '../components/DailyCard';
import TrendChart from '../components/TrendChart';
import UpcomingDays from '../components/UpcomingDays';
import InsightsCard from '../components/InsightsCard';
import ChatBar from '../components/ChatBar';
import NextOutingPicker from '../components/NextOutingPicker';

function getRotationLabel(profile) {
  const days = profile?.active_flags?.days_since_outing;
  const rotation = profile?.rotation_length || 7;

  if (days == null || days >= 99) return 'No recent outing logged';
  if (days > rotation) return `Day ${days} (extended rest)`;
  return `Day ${days}`;
}

export default function Home() {
  const { pitcherId, initData } = useAuth();
  // Refresh counter to force re-fetches after actions
  const [refreshKey, setRefreshKey] = useState(0);
  const handleRefresh = useCallback(() => setRefreshKey(k => k + 1), []);

  // Append refreshKey as cache-bust param to dynamic data paths
  const suffix = refreshKey ? `?_r=${refreshKey}` : '';
  const { profile, log, progression, loading, error } = usePitcher(pitcherId, initData, suffix);
  const exercises = useApi('/api/exercises', initData);
  const slugs = useApi('/api/exercises/slugs', initData);
  const upcoming = useApi(pitcherId ? `/api/pitcher/${pitcherId}/upcoming${suffix}` : null, initData);

  // Build exercise lookup maps
  const exerciseMap = useMemo(() => {
    if (!exercises.data?.exercises) return {};
    const map = {};
    for (const ex of exercises.data.exercises) {
      map[ex.id] = ex;
    }
    return map;
  }, [exercises.data]);

  const slugMap = useMemo(() => slugs.data || {}, [slugs.data]);

  if (loading) {
    return <PageSkeleton />;
  }

  if (error) {
    return (
      <div className="p-4">
        <p className="text-flag-red text-sm">Failed to load data. Check your connection.</p>
      </div>
    );
  }

  const entries = log?.entries || [];
  const todayStr = new Date().toISOString().split('T')[0];
  const todayEntry = entries.find(e => e.date === todayStr) || entries[entries.length - 1];
  const flagLevel = profile?.active_flags?.current_flag_level || 'green';
  const isNewPitcher = !entries.length && !profile?.active_flags?.last_outing_date;

  return (
    <div className="p-4 space-y-3 pb-36">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-text-primary">
            {profile?.name || 'Dashboard'}
          </h1>
          <p className="text-text-muted text-xs">
            {getRotationLabel(profile)} ·{' '}
            {profile?.role} · {profile?.rotation_length}-day rotation
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <FlagBadge level={flagLevel} />
          <NextOutingPicker profile={profile} onRefresh={handleRefresh} />
        </div>
      </div>

      {/* Welcome state for new pitchers */}
      {isNewPitcher ? (
        <div className="bg-bg-secondary rounded-xl p-4 text-center">
          <p className="text-sm text-text-primary mb-1">You're set up.</p>
          <p className="text-xs text-text-muted">
            To get your first personalized plan, use the action bar below
            to log an outing or do a check-in.
          </p>
        </div>
      ) : (
        <>
          {/* Week strip with training intents */}
          <WeekStrip
            entries={entries}
            todayRotationDay={todayEntry?.rotation_day || profile?.active_flags?.days_since_outing || 0}
          />

          {/* Today's plan — the big card */}
          <DailyCard
            entry={todayEntry}
            exerciseMap={exerciseMap}
            slugMap={slugMap}
            pitcherId={pitcherId}
            initData={initData}
          />
        </>
      )}

      {/* Coming up — next 3 days */}
      <UpcomingDays upcoming={upcoming.data?.upcoming} exerciseMap={exerciseMap} />

      {/* Arm feel trend */}
      {entries.length > 0 && <TrendChart entries={entries} />}

      {/* Insights */}
      <InsightsCard observations={progression?.observations} />

      {/* Action bar */}
      <ChatBar
        todayEntry={todayEntry?.date === todayStr ? todayEntry : null}
        profile={profile}
        onRefresh={handleRefresh}
      />
    </div>
  );
}

function PageSkeleton() {
  return (
    <div className="p-4 space-y-4 animate-pulse">
      <div className="h-6 bg-bg-secondary rounded w-1/3" />
      <div className="flex gap-1">
        {[...Array(7)].map((_, i) => (
          <div key={i} className="flex-1 h-16 bg-bg-secondary rounded-lg" />
        ))}
      </div>
      <div className="h-40 bg-bg-secondary rounded-xl" />
      <div className="h-24 bg-bg-secondary rounded-xl" />
      <div className="h-36 bg-bg-secondary rounded-xl" />
    </div>
  );
}
