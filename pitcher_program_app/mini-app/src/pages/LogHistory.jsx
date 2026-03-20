import { useState, useMemo } from 'react';
import { useAuth } from '../App';
import { usePitcher } from '../hooks/usePitcher';
import { useApi } from '../hooks/useApi';
import DailyCard from '../components/DailyCard';
import ChatBar from '../components/ChatBar';

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

function armFeelCellColor(feel) {
  if (feel >= 4) return 'bg-flag-green/30 text-flag-green';
  if (feel === 3) return 'bg-flag-yellow/20 text-flag-yellow';
  if (feel === 2) return 'bg-flag-red/30 text-flag-red';
  if (feel === 1) return 'bg-flag-red/50 text-flag-red';
  return 'bg-bg-tertiary text-text-muted';
}

export default function LogHistory() {
  const { pitcherId, initData } = useAuth();
  const { log, loading } = usePitcher(pitcherId, initData);
  const exercises = useApi('/api/exercises', initData);
  const slugs = useApi('/api/exercises/slugs', initData);
  const [selectedEntry, setSelectedEntry] = useState(null);

  const entries = log?.entries || [];

  const exerciseMap = useMemo(() => {
    if (!exercises.data?.exercises) return {};
    const map = {};
    for (const ex of exercises.data.exercises) map[ex.id] = ex;
    return map;
  }, [exercises.data]);

  const slugMap = useMemo(() => slugs.data || {}, [slugs.data]);

  // Group entries by month
  const months = useMemo(() => {
    const map = new Map();
    for (const entry of entries) {
      const d = new Date(entry.date + 'T00:00:00');
      const key = `${d.getFullYear()}-${d.getMonth()}`;
      if (!map.has(key)) {
        map.set(key, { year: d.getFullYear(), month: d.getMonth(), entries: [] });
      }
      map.get(key).entries.push(entry);
    }
    return [...map.values()].reverse();
  }, [entries]);

  if (loading) {
    return <HistorySkeleton />;
  }

  return (
    <div className="p-4 space-y-4 pb-28">
      <h1 className="text-lg font-bold text-text-primary">Log History</h1>

      {months.length === 0 && (
        <p className="text-text-muted text-sm">No log entries yet. Start with /checkin in the bot.</p>
      )}

      {months.map(({ year, month, entries: monthEntries }) => (
        <div key={`${year}-${month}`}>
          <h2 className="text-sm font-semibold text-text-secondary mb-2">
            {MONTHS[month]} {year}
          </h2>
          <CalendarGrid
            year={year}
            month={month}
            entries={monthEntries}
            onSelect={setSelectedEntry}
            selectedDate={selectedEntry?.date}
          />
        </div>
      ))}

      {/* Day detail panel with summary + full DailyCard */}
      {selectedEntry && (
        <div className="fixed inset-x-0 bottom-0 bg-bg-secondary rounded-t-2xl p-4 pb-24 border-t border-bg-tertiary shadow-lg max-h-[70vh] overflow-y-auto z-50">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-text-primary">{selectedEntry.date}</h3>
            <button onClick={() => setSelectedEntry(null)} className="text-text-muted text-lg px-2">x</button>
          </div>

          {/* Quick summary */}
          <DayDetailSummary entry={selectedEntry} exerciseMap={exerciseMap} slugMap={slugMap} />

          <DailyCard
            entry={selectedEntry}
            exerciseMap={exerciseMap}
            slugMap={slugMap}
            pitcherId={pitcherId}
            initData={initData}
            readOnly={true}
          />
        </div>
      )}

      <ChatBar />
    </div>
  );
}

function DayDetailSummary({ entry, exerciseMap, slugMap }) {
  const pre = entry.pre_training;
  const lifting = entry.lifting || entry.plan_generated?.lifting;
  const armCare = entry.arm_care || entry.plan_generated?.arm_care;
  const completed = entry.completed_exercises || {};
  const soreness = pre?.soreness;
  const morningBrief = entry.morning_brief || entry.plan_generated?.morning_brief;

  // Count completions
  const countExercises = (exercises) => {
    if (!exercises?.length) return { total: 0, done: 0 };
    const total = exercises.length;
    const done = exercises.filter(ex => completed[ex.exercise_id] === true).length;
    return { total, done };
  };

  const armCounts = countExercises(armCare?.exercises);
  const liftCounts = countExercises(lifting?.exercises);

  // Training intent from lifting or template
  const intent = lifting?.intent || entry.plan_generated?.template_day;
  const rotationDay = entry.rotation_day;

  return (
    <div className="mb-3 space-y-2">
      {/* Status pills row */}
      <div className="flex flex-wrap gap-1.5">
        {pre?.flag_level && (
          <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
            pre.flag_level === 'green' ? 'bg-flag-green/20 text-flag-green' :
            pre.flag_level === 'yellow' ? 'bg-flag-yellow/20 text-flag-yellow' :
            'bg-flag-red/20 text-flag-red'
          }`}>{pre.flag_level.toUpperCase()}</span>
        )}
        {pre?.arm_feel != null && (
          <span className="text-[10px] bg-bg-tertiary text-text-muted px-2 py-0.5 rounded-full">Arm {pre.arm_feel}/5</span>
        )}
        {pre?.sleep_hours != null && (
          <span className="text-[10px] bg-bg-tertiary text-text-muted px-2 py-0.5 rounded-full">Sleep {pre.sleep_hours}h</span>
        )}
      </div>

      {/* Training intent */}
      {(rotationDay != null || intent) && (
        <p className="text-xs text-text-secondary">
          {rotationDay != null && `Day ${rotationDay}`}
          {rotationDay != null && intent && ' — '}
          {intent && <span className="capitalize">{intent}</span>}
        </p>
      )}

      {/* Soreness */}
      {soreness && soreness.area && (
        <p className="text-xs text-flag-yellow">
          Soreness: {soreness.area} ({soreness.severity || 'noted'})
        </p>
      )}

      {/* Completion counts */}
      {(armCounts.total > 0 || liftCounts.total > 0) && (
        <div className="flex gap-3">
          {armCounts.total > 0 && (
            <span className="text-[10px] text-text-muted">
              Arm care: {armCounts.done}/{armCounts.total}
            </span>
          )}
          {liftCounts.total > 0 && (
            <span className="text-[10px] text-text-muted">
              Lifting: {liftCounts.done}/{liftCounts.total}
            </span>
          )}
        </div>
      )}

      {/* Morning brief excerpt */}
      {morningBrief && (
        <p className="text-xs text-text-muted italic truncate">{morningBrief}</p>
      )}

      {/* Outing data */}
      {entry.outing && (
        <div className="text-xs text-accent-blue">
          Outing: {entry.outing.pitch_count} pitches · Post feel {entry.outing.arm_feel ?? entry.outing.post_arm_feel}/5
          {entry.outing.notes && ` · ${entry.outing.notes}`}
        </div>
      )}
    </div>
  );
}

function CalendarGrid({ year, month, entries, onSelect, selectedDate }) {
  const entryMap = useMemo(() => {
    const map = {};
    for (const e of entries) map[e.date] = e;
    return map;
  }, [entries]);

  // Build calendar grid
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const cells = [];
  for (let i = 0; i < firstDay; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
    cells.push({ day: d, entry: entryMap[dateStr], dateStr });
  }

  return (
    <div>
      <div className="grid grid-cols-7 gap-1 mb-1">
        {['S','M','T','W','T','F','S'].map((d, i) => (
          <div key={i} className="text-[10px] text-text-muted text-center">{d}</div>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {cells.map((cell, i) => {
          if (!cell) return <div key={i} />;
          const feel = cell.entry?.pre_training?.arm_feel;
          const isSelected = cell.dateStr === selectedDate;
          const hasOuting = !!cell.entry?.outing;

          return (
            <button
              key={i}
              onClick={() => cell.entry && onSelect(cell.entry)}
              className={`relative aspect-square rounded-md flex items-center justify-center text-xs font-medium transition-colors ${
                feel != null ? armFeelCellColor(feel) : 'bg-bg-secondary text-text-muted'
              } ${isSelected ? 'ring-2 ring-accent-blue' : ''} ${
                cell.entry ? 'cursor-pointer' : 'cursor-default'
              }`}
            >
              {cell.day}
              {hasOuting && (
                <div className="absolute bottom-0.5 w-1 h-1 rounded-full bg-accent-blue" />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function HistorySkeleton() {
  return (
    <div className="p-4 space-y-4 animate-pulse">
      <div className="h-6 bg-bg-secondary rounded w-1/3" />
      <div className="grid grid-cols-7 gap-1">
        {[...Array(35)].map((_, i) => (
          <div key={i} className="aspect-square bg-bg-secondary rounded-md" />
        ))}
      </div>
    </div>
  );
}
