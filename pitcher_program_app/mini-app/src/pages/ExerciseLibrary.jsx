import { useState, useMemo, useEffect } from 'react';
import { useAuth } from '../App';
import { useApi } from '../hooks/useApi';
import { submitAsk } from '../api';
import ChatBar from '../components/ChatBar';

const CATEGORIES = [
  { key: 'all', label: 'All' },
  { key: 'lower_body_compound', label: 'Lower' },
  { key: 'upper_body_pull', label: 'Pull' },
  { key: 'upper_body_push', label: 'Push' },
  { key: 'power', label: 'Power' },
  { key: 'core', label: 'Core' },
  { key: 'arm_care', label: 'Arm Care' },
  { key: 'fpm', label: 'FPM' },
  { key: 'shoulder_care', label: 'Shoulder' },
  { key: 'mobility', label: 'Mobility' },
];

function formatDayList(days) {
  if (!days?.length) return null;
  return days.map(d => d.replace('day_', 'Day ')).join(', ');
}

export default function ExerciseLibrary() {
  const { pitcherId, initData } = useAuth();
  const { data, loading, error } = useApi('/api/exercises', initData);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('all');
  const [expandedId, setExpandedId] = useState(null);

  // Cache exercises in localStorage
  useEffect(() => {
    if (data?.exercises) {
      try { localStorage.setItem('exercise_library', JSON.stringify(data)); } catch {}
    }
  }, [data]);

  // Use cached data as fallback
  const exercises = useMemo(() => {
    const source = data || (() => {
      try { return JSON.parse(localStorage.getItem('exercise_library')); } catch { return null; }
    })();
    return source?.exercises || [];
  }, [data]);

  const filtered = useMemo(() => {
    let result = exercises;
    if (category !== 'all') {
      result = result.filter(ex =>
        ex.category === category ||
        ex.subcategory === category ||
        ex.tags?.includes(category)
      );
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(ex =>
        ex.name.toLowerCase().includes(q) ||
        ex.aliases?.some(a => a.toLowerCase().includes(q)) ||
        ex.tags?.some(t => t.toLowerCase().includes(q))
      );
    }
    return result;
  }, [exercises, category, search]);

  if (loading && !exercises.length) {
    return <LibrarySkeleton />;
  }

  return (
    <div className="p-4 space-y-3 pb-28">
      <h1 className="text-lg font-bold text-text-primary">Exercise Library</h1>

      {/* Search */}
      <input
        type="text"
        placeholder="Search exercises..."
        value={search}
        onChange={e => setSearch(e.target.value)}
        className="w-full bg-bg-secondary text-text-primary text-sm rounded-lg px-3 py-2.5 border border-bg-tertiary focus:border-accent-blue focus:outline-none"
      />

      {/* Category pills */}
      <div className="flex gap-1.5 overflow-x-auto pb-1 -mx-1 px-1 scrollbar-none">
        {CATEGORIES.map(cat => (
          <button
            key={cat.key}
            onClick={() => setCategory(cat.key)}
            className={`px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap shrink-0 transition-colors ${
              category === cat.key
                ? 'bg-accent-blue text-white'
                : 'bg-bg-secondary text-text-muted'
            }`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Results */}
      <p className="text-text-muted text-xs">{filtered.length} exercises</p>

      <div className="space-y-2">
        {filtered.map(ex => (
          <ExerciseCard
            key={ex.id}
            exercise={ex}
            expanded={expandedId === ex.id}
            onToggle={() => setExpandedId(expandedId === ex.id ? null : ex.id)}
            pitcherId={pitcherId}
            initData={initData}
          />
        ))}
      </div>

      {error && !exercises.length && (
        <p className="text-flag-red text-sm">Failed to load exercises.</p>
      )}

      <ChatBar />
    </div>
  );
}

function ExerciseCard({ exercise, expanded, onToggle, pitcherId, initData }) {
  const [whyAnswer, setWhyAnswer] = useState(null);
  const [whyLoading, setWhyLoading] = useState(false);

  const handleWhy = async () => {
    if (whyAnswer || whyLoading) return;
    setWhyLoading(true);
    try {
      const res = await submitAsk(
        pitcherId,
        `Why is "${exercise.name}" in my program? Given my profile and training history, explain why this specific exercise matters for me.`,
        [],
        initData
      );
      setWhyAnswer(res.answer);
    } catch {
      setWhyAnswer('Could not load explanation right now.');
    } finally {
      setWhyLoading(false);
    }
  };

  const recommended = formatDayList(exercise.rotation_day_usage?.recommended);
  const avoid = formatDayList(exercise.rotation_day_usage?.avoid);

  return (
    <div className="bg-bg-secondary rounded-xl overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full text-left px-4 py-3 flex items-center justify-between"
      >
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-sm font-medium text-text-primary truncate">{exercise.name}</p>
            {exercise.youtube_url && (
              <a
                href={exercise.youtube_url}
                target="_blank"
                rel="noopener noreferrer"
                onClick={e => e.stopPropagation()}
                className="text-[11px] text-accent-blue flex-shrink-0"
              >
                ▶ vid
              </a>
            )}
          </div>
          <p className="text-xs text-text-muted truncate">
            {exercise.muscles_primary?.join(' · ')}
          </p>
        </div>
        <span className={`text-text-muted text-xs ml-2 transition-transform ${expanded ? 'rotate-180' : ''}`}>
          ▾
        </span>
      </button>

      {expanded && (
        <div className="px-4 pb-3 space-y-2.5 border-t border-bg-tertiary pt-2">
          {/* Pitching relevance card */}
          {exercise.pitching_relevance && (
            <div className="bg-accent-blue/5 border border-accent-blue/20 rounded-lg p-3">
              <p className="text-[10px] text-accent-blue font-medium mb-1">Why this matters</p>
              <p className="text-xs text-text-secondary">{exercise.pitching_relevance}</p>
            </div>
          )}

          {/* Prescriptions */}
          {exercise.prescription && (
            <div className="space-y-1">
              <p className="text-[10px] text-text-muted uppercase font-medium">Protocol</p>
              {Object.entries(exercise.prescription).map(([mode, rx]) => (
                <div key={mode} className="flex items-center gap-2">
                  <span className="text-[10px] bg-bg-tertiary text-text-muted px-1.5 py-0.5 rounded">{mode}</span>
                  <span className="text-xs text-text-secondary">
                    {rx.sets}×{rx.reps} @ {rx.intensity}{rx.rest_min ? ` · ${rx.rest_min}min rest` : ''}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Muscle tags */}
          {exercise.muscles_primary?.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {exercise.muscles_primary.map(m => (
                <span key={m} className="text-[10px] bg-accent-blue/10 text-accent-blue px-1.5 py-0.5 rounded">
                  {m}
                </span>
              ))}
              {exercise.muscles_secondary?.map(m => (
                <span key={m} className="text-[10px] bg-bg-tertiary text-text-muted px-1.5 py-0.5 rounded">
                  {m}
                </span>
              ))}
            </div>
          )}

          {/* Rotation timing */}
          {(recommended || avoid) && (
            <div className="space-y-0.5">
              {recommended && (
                <p className="text-xs text-text-secondary">Use on: {recommended}</p>
              )}
              {avoid && (
                <p className="text-xs text-text-muted">Avoid: {avoid}</p>
              )}
            </div>
          )}

          {/* Contraindications */}
          {exercise.contraindications?.length > 0 && (
            <p className="text-xs text-flag-yellow">
              Stop if: {exercise.contraindications.map(c => c.replace(/_/g, ' ')).join(', ')}
            </p>
          )}

          {/* Tags */}
          {exercise.tags && (
            <div className="flex flex-wrap gap-1">
              {exercise.tags.map(tag => (
                <span key={tag} className="text-[10px] bg-bg-tertiary text-text-muted px-1.5 py-0.5 rounded">
                  {tag}
                </span>
              ))}
            </div>
          )}

          {/* "Why is this in my program?" */}
          {pitcherId && (
            <div className="pt-1">
              {whyAnswer ? (
                <div className="bg-bg-tertiary rounded-lg p-3">
                  <p className="text-xs text-text-secondary whitespace-pre-wrap">{whyAnswer}</p>
                </div>
              ) : (
                <button
                  onClick={handleWhy}
                  disabled={whyLoading}
                  className="text-xs text-accent-blue disabled:opacity-50"
                >
                  {whyLoading ? 'Loading...' : 'Why is this in my program?'}
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function LibrarySkeleton() {
  return (
    <div className="p-4 space-y-3 animate-pulse">
      <div className="h-6 bg-bg-secondary rounded w-1/3" />
      <div className="h-10 bg-bg-secondary rounded-lg" />
      <div className="flex gap-2">
        {[...Array(5)].map((_, i) => <div key={i} className="h-7 w-16 bg-bg-secondary rounded-full" />)}
      </div>
      {[...Array(6)].map((_, i) => <div key={i} className="h-16 bg-bg-secondary rounded-xl" />)}
    </div>
  );
}
