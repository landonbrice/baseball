export default function PlayerHistory({ data }) {
  const recent = data?.recent_check_ins || []
  const injuries = data?.injuries || []
  const model = data?.training_model || {}

  return (
    <div className="space-y-4">
      {/* Arm feel trend */}
      <div>
        <p className="text-xs text-subtle mb-2">Arm Feel (Last 10)</p>
        <div className="flex items-end gap-1 h-16">
          {recent
            .slice()
            .reverse()
            .map((e, i) => {
              const feel = e.pre_training?.arm_feel || 0
              const h = Math.max(4, (feel / 5) * 100)
              const color =
                feel >= 4 ? '#2d5a3d' : feel >= 3 ? '#d4a017' : '#c0392b'
              return (
                <div key={i} className="flex-1 flex flex-col items-center gap-0.5">
                  <div
                    style={{
                      height: `${h}%`,
                      backgroundColor: color,
                      borderRadius: 2,
                      width: '100%',
                      minHeight: 4,
                    }}
                  />
                  <span className="text-[8px] text-subtle">{e.date?.slice(5)}</span>
                </div>
              )
            })}
        </div>
      </div>

      {/* Compliance calendar */}
      <div>
        <p className="text-xs text-subtle mb-2">Check-in History</p>
        <div className="space-y-1">
          {recent.map(e => (
            <div key={e.date} className="flex items-center gap-3 py-1">
              <span className="text-xs text-charcoal w-20">{e.date}</span>
              <span
                className={`w-2 h-2 rounded-full ${
                  e.completed_exercises ? 'bg-forest' : 'bg-cream-dark'
                }`}
              />
              <span className="text-xs text-subtle">
                Arm: {e.pre_training?.arm_feel || '-'}
                {e.completed_exercises
                  ? ` · ${Object.keys(e.completed_exercises).length} exercises`
                  : ''}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Injury history */}
      {injuries.length > 0 && (
        <div>
          <p className="text-xs text-subtle mb-2">Injury History</p>
          {injuries.map((inj, i) => (
            <div key={i} className="bg-cream rounded p-2 mb-1">
              <p className="text-xs font-medium text-charcoal">{inj.area}</p>
              <p className="text-[10px] text-subtle">
                {inj.status} · {inj.flag_level} · {inj.notes || ''}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Active restrictions / preferences */}
      {model.exercise_preferences &&
        Object.keys(model.exercise_preferences).length > 0 && (
          <div>
            <p className="text-xs text-subtle mb-2">Exercise Preferences / Restrictions</p>
            {Object.entries(model.exercise_preferences).map(([key, val]) => (
              <div key={key} className="text-xs bg-cream rounded p-1.5 mb-1">
                <span className="font-medium text-charcoal">{key}</span>:{' '}
                {typeof val === 'string' ? val : val?.status || JSON.stringify(val)}
              </div>
            ))}
          </div>
        )}
    </div>
  )
}
