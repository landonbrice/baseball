import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../App';
import { useAppContext } from '../hooks/useChatState';
import { usePitcher } from '../hooks/usePitcher';
import { useApi } from '../hooks/useApi';
import DailyCard from '../components/DailyCard';

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
  const navigate = useNavigate();
  const { addMessage } = useAppContext();
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

      {/* Day detail panel with full DailyCard */}
      {selectedEntry && (
        <div className="fixed inset-x-0 bottom-0 bg-bg-secondary rounded-t-2xl p-4 pb-24 border-t border-bg-tertiary shadow-lg max-h-[70vh] overflow-y-auto z-50">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-text-primary">{selectedEntry.date}</h3>
            <button onClick={() => setSelectedEntry(null)} className="text-text-muted text-lg px-2">x</button>
          </div>
          <DailyCard
            entry={selectedEntry}
            exerciseMap={exerciseMap}
            slugMap={slugMap}
            pitcherId={pitcherId}
            initData={initData}
            readOnly={true}
          />
          <div
            onClick={() => {
              const flag = selectedEntry.pre_training?.flag_level || 'green';
              const feel = selectedEntry.pre_training?.arm_feel;
              addMessage({
                role: 'user', type: 'text',
                content: `Tell me about my ${selectedEntry.date} session — I was ${flag} flag${feel ? `, arm feel ${feel}/5` : ''}. Why did I get that plan?`,
              });
              setSelectedEntry(null);
              navigate('/coach');
            }}
            style={{
              marginTop: 10, background: 'var(--color-maroon)', borderRadius: 10,
              padding: '9px 14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              cursor: 'pointer',
            }}
          >
            <span style={{ fontSize: 11, fontWeight: 700, color: '#fff' }}>Ask coach about this day</span>
            <span style={{ color: '#e8a0aa' }}>{'\u2192'}</span>
          </div>
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
