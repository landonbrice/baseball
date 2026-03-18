import { useState, useMemo } from 'react';
import { useAuth } from '../App';
import { usePitcher } from '../hooks/usePitcher';
import FlagBadge from '../components/FlagBadge';
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
  const [selectedEntry, setSelectedEntry] = useState(null);

  const entries = log?.entries || [];

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

      {/* Day detail panel */}
      {selectedEntry && (
        <DayDetail entry={selectedEntry} onClose={() => setSelectedEntry(null)} />
      )}

      <ChatBar />
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

function DayDetail({ entry, onClose }) {
  const armCareCount = entry.arm_care?.exercises?.length || 0;
  const liftingCount = entry.lifting?.exercises?.length || 0;
  const completedCount = Object.values(entry.completed_exercises || {}).filter(Boolean).length;
  const totalExercises = armCareCount + liftingCount ||
    entry.plan_generated?.exercise_blocks?.reduce((sum, b) => sum + (b.exercises?.length || 0), 0) || 0;

  return (
    <div className="fixed inset-x-0 bottom-0 bg-bg-secondary rounded-t-2xl p-4 pb-24 border-t border-bg-tertiary shadow-lg max-h-[60vh] overflow-y-auto z-50">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-text-primary">{entry.date}</h3>
        <button onClick={onClose} className="text-text-muted text-lg px-2">×</button>
      </div>

      <div className="space-y-3">
        {/* Status row */}
        <div className="flex items-center gap-2 flex-wrap">
          <FlagBadge level={entry.pre_training?.flag_level || 'green'} />
          {entry.pre_training?.arm_feel != null && (
            <span className="text-[10px] bg-bg-tertiary text-text-muted px-2 py-0.5 rounded-full">
              Arm {entry.pre_training.arm_feel}/5
            </span>
          )}
          {entry.pre_training?.sleep_hours != null && (
            <span className="text-[10px] bg-bg-tertiary text-text-muted px-2 py-0.5 rounded-full">
              Sleep {entry.pre_training.sleep_hours}h
            </span>
          )}
          {entry.rotation_day != null && (
            <span className="text-[10px] bg-bg-tertiary text-text-muted px-2 py-0.5 rounded-full">
              Day {entry.rotation_day}
            </span>
          )}
        </div>

        {/* Morning brief */}
        {(entry.morning_brief || entry.plan_narrative) && (
          <p className="text-xs text-text-secondary">
            {entry.morning_brief || entry.plan_narrative?.split('\n')[0]?.slice(0, 120)}
          </p>
        )}

        {/* Training intent */}
        {entry.lifting?.intent && (
          <p className="text-[10px] text-text-muted uppercase">{entry.lifting.intent}</p>
        )}

        {/* Exercise completion */}
        {totalExercises > 0 && (
          <div className="flex items-center gap-2">
            <div className="flex-1 h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
              <div
                className="h-full bg-accent-blue rounded-full transition-all"
                style={{ width: `${totalExercises ? (completedCount / totalExercises * 100) : 0}%` }}
              />
            </div>
            <span className="text-[10px] text-text-muted flex-shrink-0">
              {completedCount}/{totalExercises}
            </span>
          </div>
        )}

        {/* Outing */}
        {entry.outing && (
          <div className="bg-bg-tertiary rounded-lg p-3">
            <p className="text-xs text-accent-blue font-medium">Outing</p>
            <p className="text-sm text-text-primary">
              {entry.outing.pitch_count} pitches · Post feel: {entry.outing.arm_feel ?? entry.outing.post_arm_feel}/5
            </p>
            {entry.outing.notes && (
              <p className="text-xs text-text-muted mt-1">{entry.outing.notes}</p>
            )}
          </div>
        )}

        {/* Soreness */}
        {entry.soreness_response && (
          <div className="bg-flag-yellow/10 rounded-lg p-3">
            <p className="text-[10px] text-flag-yellow font-medium mb-1">Soreness note</p>
            <p className="text-xs text-text-secondary">{entry.soreness_response}</p>
          </div>
        )}

        {/* Bot observations */}
        {entry.bot_observations && (
          <div>
            <p className="text-[10px] text-text-muted uppercase font-medium mb-1">Patterns</p>
            {Array.isArray(entry.bot_observations)
              ? entry.bot_observations.map((obs, i) => (
                  <p key={i} className="text-xs text-text-secondary">{obs}</p>
                ))
              : <>
                  {entry.bot_observations.progression_notes && (
                    <p className="text-xs text-text-secondary">{entry.bot_observations.progression_notes}</p>
                  )}
                  {entry.bot_observations.pattern_notes && (
                    <p className="text-xs text-text-muted">{entry.bot_observations.pattern_notes}</p>
                  )}
                </>
            }
          </div>
        )}
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
