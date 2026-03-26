import { useState } from 'react';
import ExerciseRow from './ExerciseRow';

const INTENT_LABELS = {
  power_development: 'Power',
  strength_development: 'Strength',
  strength_maintenance: 'Pull',
  recovery_flush: 'Recovery',
  activation_maintenance: 'Mobility',
  none: 'Rest',
};

export default function UpcomingDays({ upcoming = [], exerciseMap = {} }) {
  const [expandedIdx, setExpandedIdx] = useState(null);

  if (!upcoming.length) return null;

  return (
    <div className="bg-bg-secondary rounded-xl p-4">
      <h3 className="text-sm font-semibold text-text-primary mb-3">Coming up</h3>
      <div className="space-y-0">
        {upcoming.map((day, i) => {
          const expanded = expandedIdx === i;
          return (
            <div key={i}>
              <button
                onClick={() => setExpandedIdx(expanded ? null : i)}
                className={`w-full flex justify-between items-center py-2 text-left ${
                  i < upcoming.length - 1 && !expanded ? 'border-b border-bg-tertiary' : ''
                }`}
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium text-text-primary">
                    Day {day.rotation_day} · {INTENT_LABELS[day.training_intent] || day.training_intent}
                  </p>
                  <p className="text-[11px] text-text-secondary truncate">
                    {day.exercise_preview || day.label}
                  </p>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0 ml-2">
                  {day.duration_min && (
                    <span className="text-[11px] text-text-muted">
                      {day.duration_min} min
                    </span>
                  )}
                  <span className={`text-text-muted text-xs transition-transform ${expanded ? 'rotate-180' : ''}`}>
                    ▾
                  </span>
                </div>
              </button>

              {expanded && (
                <div className="pb-3 border-b border-bg-tertiary">
                  {day.blocks?.length > 0 ? (
                    <div className="space-y-2 mt-1">
                      {day.blocks.map((block, bi) => (
                        <div key={bi}>
                          {block.block_name && (
                            <p className="text-[10px] text-text-muted uppercase font-medium mt-1 mb-0.5">
                              {block.block_name}
                            </p>
                          )}
                          {block.exercises?.map((ex, ei) => {
                            const libEx = exerciseMap[ex.exercise_id] || ex;
                            return (
                              <ExerciseRow
                                key={ei}
                                exercise={{
                                  name: ex.name || libEx.name,
                                  muscles_primary: ex.muscles_primary || libEx.muscles_primary,
                                  youtube_url: ex.youtube_url || libEx.youtube_url,
                                }}
                                prescribed={ex.rx || ex.prescribed || ''}
                              />
                            );
                          })}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-text-muted py-1">No exercises scheduled</p>
                  )}

                  {day.throwing && (
                    <div className="mt-2 pt-1 border-t border-bg-tertiary">
                      <p className="text-[10px] text-text-muted uppercase font-medium">Throwing</p>
                      <p className="text-xs text-text-secondary">{typeof day.throwing === 'string' ? day.throwing : day.throwing.details || 'See plan'}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
