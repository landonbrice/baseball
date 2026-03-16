import { useMemo } from 'react';
import { useAuth } from '../App';
import { usePitcher } from '../hooks/usePitcher';
import { useApi } from '../hooks/useApi';
import FlagBadge from '../components/FlagBadge';
import WeekStrip from '../components/WeekStrip';
import DailyCard from '../components/DailyCard';
import TrendChart from '../components/TrendChart';

export default function Home() {
  const { pitcherId, initData } = useAuth();
  const { profile, log, progression, loading, error } = usePitcher(pitcherId, initData);
  const exercises = useApi('/api/exercises', initData);
  const slugs = useApi('/api/exercises/slugs', initData);

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

  return (
    <div className="p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-text-primary">
            {profile?.name || 'Dashboard'}
          </h1>
          <p className="text-text-muted text-xs">
            Day {profile?.active_flags?.days_since_outing ?? '—'} since last outing
          </p>
        </div>
        <FlagBadge level={flagLevel} />
      </div>

      {/* Week strip */}
      <WeekStrip
        entries={entries}
        todayRotationDay={todayEntry?.rotation_day || 0}
      />

      {/* Today's plan */}
      <DailyCard
        entry={todayEntry}
        exerciseMap={exerciseMap}
        slugMap={slugMap}
      />

      {/* Trend chart */}
      <TrendChart entries={entries} />

      {/* Progression observations */}
      {progression?.observations?.length > 0 && (
        <div className="bg-bg-secondary rounded-xl p-4">
          <h3 className="text-sm font-semibold text-text-primary mb-2">Observations</h3>
          {progression.observations.map((obs, i) => (
            <p key={i} className="text-xs text-text-secondary mb-1">{obs}</p>
          ))}
        </div>
      )}
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
      <div className="h-36 bg-bg-secondary rounded-xl" />
    </div>
  );
}
