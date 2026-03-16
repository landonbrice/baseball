import { useState, useMemo, useEffect } from 'react';
import { useAuth } from '../App';
import { useApi } from '../hooks/useApi';

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

export default function ExerciseLibrary() {
  const { initData } = useAuth();
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
    <div className="p-4 space-y-3">
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
          />
        ))}
      </div>

      {error && !exercises.length && (
        <p className="text-flag-red text-sm">Failed to load exercises.</p>
      )}
    </div>
  );
}

function ExerciseCard({ exercise, expanded, onToggle }) {
  return (
    <div className="bg-bg-secondary rounded-xl overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full text-left px-4 py-3 flex items-center justify-between"
      >
        <div className="min-w-0">
          <p className="text-sm font-medium text-text-primary truncate">{exercise.name}</p>
          <p className="text-xs text-text-muted truncate">
            {exercise.muscles_primary?.join(', ')}
          </p>
        </div>
        <span className={`text-text-muted text-xs ml-2 transition-transform ${expanded ? 'rotate-180' : ''}`}>
          ▾
        </span>
      </button>

      {expanded && (
        <div className="px-4 pb-3 space-y-2 border-t border-bg-tertiary pt-2">
          <p className="text-xs text-text-secondary">{exercise.pitching_relevance}</p>

          {exercise.prescription && (
            <div className="space-y-1">
              <p className="text-[10px] text-text-muted uppercase font-medium">Prescriptions</p>
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

          {exercise.tags && (
            <div className="flex flex-wrap gap-1">
              {exercise.tags.map(tag => (
                <span key={tag} className="text-[10px] bg-bg-tertiary text-text-muted px-1.5 py-0.5 rounded">
                  {tag}
                </span>
              ))}
            </div>
          )}

          {exercise.youtube_url && (
            <a
              href={exercise.youtube_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block text-xs text-accent-blue mt-1"
            >
              Watch video →
            </a>
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
