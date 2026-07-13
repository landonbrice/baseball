import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../App';
import { useApi } from '../hooks/useApi';

const DOMAIN_LABEL = { throwing: 'Throwing', lifting: 'Lifting' };

function chicagoToday() {
  return new Date().toLocaleDateString('en-CA', { timeZone: 'America/Chicago' });
}

function dayLabel(day) {
  if (day.label) return day.label;
  if (day.phase_name) return day.phase_name;
  const key = day.template_key || '';
  return key.replace(/_/g, ' ');
}

export default function ProgramDetail() {
  const { programId } = useParams();
  const navigate = useNavigate();
  const { initData } = useAuth();
  const { data, loading } = useApi(programId ? `/api/programs/${programId}` : null, initData);

  if (loading) return <div style={{ padding: 16 }}>Loading...</div>;
  if (!data?.program) return <div style={{ padding: 16 }}>Program not found.</div>;

  const { program, template } = data;
  const days = program.generated_schedule_json?.days || [];
  const today = chicagoToday();
  const currentIdx = program.current_day_index ?? 0;

  // Group days into weeks of 7 by day_index.
  const weeks = [];
  for (const day of days) {
    const w = Math.floor((day.day_index ?? 0) / 7);
    (weeks[w] ||= []).push(day);
  }

  return (
    <div style={{ paddingBottom: 100 }}>
      <div style={{ background: 'var(--color-maroon)', padding: '14px 16px 12px' }}>
        <button
          onClick={() => navigate(-1)}
          style={{ background: 'transparent', border: 'none', color: 'var(--color-rose-blush)', fontSize: 12, cursor: 'pointer', padding: 0 }}
        >‹ Back</button>
        <div style={{ fontSize: 19, fontWeight: 700, color: '#fff', marginTop: 4, letterSpacing: -0.3 }}>
          {template?.name || `${DOMAIN_LABEL[program.domain] || program.domain} program`}
        </div>
        <div style={{ fontSize: 11, color: 'var(--color-rose-blush)', marginTop: 4 }}>
          {DOMAIN_LABEL[program.domain] || program.domain}
          {' · '}{program.status}
          {' · '}{program.start_date}{program.nominal_end_date ? ` — ${program.nominal_end_date}` : ''}
          {program.held_days_count > 0 && ` · held ${program.held_days_count}d`}
        </div>
      </div>

      <div style={{ padding: 16 }}>
        <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--color-ink-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 10 }}>
          Schedule · day {Math.min(currentIdx + 1, Math.max(days.length, 1))} of {days.length}
        </div>

        {weeks.map((weekDays, wi) => (
          <div key={wi} style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--color-ink-secondary)', marginBottom: 6 }}>
              Week {wi + 1}
            </div>
            {weekDays.map((day) => {
              const isCurrent = day.day_index === currentIdx;
              const isPast = day.date && day.date < today;
              return (
                <div
                  key={day.day_index}
                  style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
                    padding: '8px 12px', borderRadius: 8, marginBottom: 4,
                    background: isCurrent ? 'rgba(92,16,32,0.06)' : '#fff',
                    border: `1px solid ${isCurrent ? 'rgba(92,16,32,0.3)' : 'var(--color-cream-border)'}`,
                    opacity: isPast && !isCurrent ? 0.55 : 1,
                  }}
                >
                  <div style={{ minWidth: 0 }}>
                    <span style={{ fontSize: 12.5, fontWeight: isCurrent ? 700 : 500, color: 'var(--color-ink-primary)' }}>
                      {dayLabel(day)}
                    </span>
                    {day.is_deload && (
                      <span style={{ fontSize: 9, fontWeight: 700, color: 'var(--color-ink-muted)', marginLeft: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                        deload
                      </span>
                    )}
                    {isCurrent && (
                      <span style={{ fontSize: 9, fontWeight: 700, color: 'var(--color-maroon)', marginLeft: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                        now
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: 10.5, color: 'var(--color-ink-muted)', whiteSpace: 'nowrap', marginLeft: 10 }}>
                    {typeof day.intent_pct === 'number' && `${day.intent_pct}% · `}{day.date}
                  </div>
                </div>
              );
            })}
          </div>
        ))}

        {days.length === 0 && (
          <div style={{ fontSize: 12.5, color: 'var(--color-ink-secondary)' }}>
            No schedule days on this program yet.
          </div>
        )}
      </div>
    </div>
  );
}
