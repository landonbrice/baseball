import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../App';
import { useApi } from '../hooks/useApi';

export default function ProgramDetail() {
  const { programId } = useParams();
  const navigate = useNavigate();
  const { initData } = useAuth();
  const { data, loading } = useApi(programId ? `/api/program/${programId}` : null, initData);

  if (loading) return <div style={{ padding: 16 }}>Loading...</div>;
  if (!data?.program) return <div style={{ padding: 16 }}>Program not found.</div>;

  const { program, template, current_phase } = data;
  const phases = program.phases_snapshot || [];

  return (
    <div style={{ paddingBottom: 100 }}>
      <div style={{ background: 'var(--color-maroon)', padding: '14px 16px 12px' }}>
        <button
          onClick={() => navigate(-1)}
          style={{ background: 'transparent', border: 'none', color: 'var(--color-rose-blush)', fontSize: 12, cursor: 'pointer', padding: 0 }}
        >‹ Back</button>
        <div style={{ fontSize: 19, fontWeight: 700, color: '#fff', marginTop: 4, letterSpacing: -0.3 }}>
          {program.name}
        </div>
        <div style={{ fontSize: 11, color: 'var(--color-rose-blush)', marginTop: 4 }}>
          {program.start_date}{program.end_date ? ` — ${program.end_date}` : ' — ongoing'} · {template?.role}
        </div>
      </div>

      <div style={{ padding: 16 }}>
        <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--color-ink-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 10 }}>
          Phases
        </div>
        {phases.map((phase, i) => {
          const isCurrent = current_phase?.phase_id === phase.phase_id && !current_phase?.is_past_end;
          return (
            <div key={phase.phase_id} style={{
              padding: '12px 14px', borderRadius: 10,
              background: isCurrent ? 'rgba(92,16,32,0.05)' : '#fff',
              border: `1px solid ${isCurrent ? 'rgba(92,16,32,0.25)' : 'var(--color-cream-border)'}`,
              marginBottom: 8,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-ink-primary)' }}>
                  {i + 1}. {phase.name}
                </div>
                <div style={{ fontSize: 10, color: 'var(--color-ink-muted)' }}>
                  {phase.week_count} week{phase.week_count === 1 ? '' : 's'}
                </div>
              </div>
              <div style={{ fontSize: 11, color: 'var(--color-ink-secondary)', marginTop: 4 }}>
                Type: {phase.phase_type}
                {phase.default_training_intent && ` · Intent: ${phase.default_training_intent}`}
              </div>
              {isCurrent && (
                <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--color-maroon)', marginTop: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                  Current · week {current_phase.week_in_phase} of {phase.week_count}
                </div>
              )}
            </div>
          );
        })}

        {template && (
          <>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--color-ink-muted)', textTransform: 'uppercase', letterSpacing: 1, marginTop: 20, marginBottom: 10 }}>
              Template
            </div>
            <div style={{ padding: '12px 14px', borderRadius: 10, background: '#fff', border: '1px solid var(--color-cream-border)' }}>
              <div style={{ fontSize: 12, color: 'var(--color-ink-secondary)' }}>{template.description}</div>
              <div style={{ fontSize: 11, color: 'var(--color-ink-muted)', marginTop: 6 }}>
                Rotation length: {template.rotation_length} days · Templates: {(template.rotation_template_keys || []).join(', ')}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
