import { useNavigate } from 'react-router-dom';
import { useAuth } from '../App';
import { useAppContext } from '../hooks/useChatState';
import { usePitcher } from '../hooks/usePitcher';
import FlagBadge from '../components/FlagBadge';

export default function Profile() {
  const { pitcherId, initData } = useAuth();
  const navigate = useNavigate();
  const { addMessage } = useAppContext();
  const { profile, loading } = usePitcher(pitcherId, initData);

  if (loading) {
    return <ProfileSkeleton />;
  }

  if (!profile) {
    return (
      <div className="p-4">
        <p className="text-text-muted text-sm">Profile not found.</p>
      </div>
    );
  }

  const flags = profile.active_flags || {};

  return (
    <div className="p-4 space-y-4 pb-28">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-text-primary">{profile.name}</h1>
          <p className="text-text-muted text-xs">
            {profile.role} · {profile.throws}-handed · {profile.rotation_length}-day rotation
          </p>
        </div>
        <FlagBadge level={flags.current_flag_level || 'green'} />
      </div>

      {/* Current Status */}
      <Section title="Current Status">
        <Row label="Arm Feel" value={`${flags.current_arm_feel ?? '—'}/5`} />
        <Row label="Days Since Outing" value={flags.days_since_outing ?? '—'} />
        <Row label="Last Outing" value={`${flags.last_outing_pitches ?? '—'} pitches (${flags.last_outing_date ?? '—'})`} />
        {flags.active_modifications?.length > 0 && (
          <Row label="Modifications" value={flags.active_modifications.join(', ')} />
        )}
      </Section>

      {/* Pitching */}
      <Section title="Pitching">
        <Row label="FB Velocity" value={`${profile.pitching_profile?.avg_velocity_fb ?? '—'} mph`} />
        <Row label="Arsenal" value={profile.pitching_profile?.pitch_arsenal?.join(', ') || '—'} />
        <Row label="Typical Count" value={`${profile.pitching_profile?.typical_pitch_count ?? '—'} pitches`} />
      </Section>

      {/* Physical */}
      <Section title="Physical">
        <Row label="Height" value={profile.physical_profile?.height_in ? `${Math.floor(profile.physical_profile.height_in / 12)}'${profile.physical_profile.height_in % 12}"` : '—'} />
        <Row label="Weight" value={profile.physical_profile?.weight_lbs ? `${profile.physical_profile.weight_lbs} lbs` : '—'} />
        <Row label="Goal" value={profile.physical_profile?.body_comp_goal || '—'} />
      </Section>

      {/* Training */}
      <Section title="Training">
        <Row label="Experience" value={profile.current_training?.lifting_experience || '—'} />
        <Row label="Split" value={profile.current_training?.current_split || '—'} />
        {profile.current_training?.current_maxes && (
          <div className="mt-1">
            <p className="text-[10px] text-text-muted uppercase mb-1">Maxes</p>
            {Object.entries(profile.current_training.current_maxes).map(([lift, val]) => (
              <Row key={lift} label={lift.replace(/_/g, ' ')} value={String(val)} />
            ))}
          </div>
        )}
      </Section>

      {/* Goals */}
      <Section title="Goals">
        <Row label="Primary" value={profile.goals?.primary || '—'} />
        {profile.goals?.secondary && <Row label="Secondary" value={profile.goals.secondary} />}
      </Section>

      {/* Injury History */}
      {profile.injury_history?.length > 0 && (
        <Section title="Injury History">
          {profile.injury_history.map((injury, i) => (
            <div key={i} className="mb-2 last:mb-0">
              <p className="text-xs text-text-primary">
                {injury.date} — {injury.area.replace(/_/g, ' ')} ({injury.severity})
              </p>
              <p className="text-xs text-text-muted">{injury.description}</p>
              {injury.ongoing_considerations && (
                <p className="text-xs text-flag-yellow mt-0.5">{injury.ongoing_considerations}</p>
              )}
            </div>
          ))}
          <button
            onClick={() => {
              addMessage({
                role: 'user', type: 'text',
                content: 'How does my injury history affect my current training plan?',
              });
              navigate('/coach');
            }}
            style={{ marginTop: 8, fontSize: 11, color: 'var(--color-maroon)', background: 'none', border: 'none', cursor: 'pointer', fontWeight: 600 }}
          >
            Ask coach how this affects my plan {'\u2192'}
          </button>
        </Section>
      )}

      {/* Ask coach CTA */}
      <div
        onClick={() => {
          const flag = flags.current_flag_level || 'green';
          addMessage({
            role: 'user', type: 'text',
            content: `I'm currently ${flag} flag. What should I know about my training right now?`,
          });
          navigate('/coach');
        }}
        style={{
          background: 'var(--color-maroon)', borderRadius: 10,
          padding: '9px 14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          cursor: 'pointer',
        }}
      >
        <span style={{ fontSize: 11, fontWeight: 700, color: '#fff' }}>Ask coach about my training</span>
        <span style={{ color: '#e8a0aa' }}>{'\u2192'}</span>
      </div>

    </div>
  );
}

function Section({ title, children }) {
  return (
    <div className="bg-bg-secondary rounded-xl p-4">
      <h2 className="text-sm font-semibold text-text-primary mb-2">{title}</h2>
      {children}
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div className="flex justify-between items-start py-1">
      <span className="text-xs text-text-muted">{label}</span>
      <span className="text-xs text-text-secondary text-right ml-4">{value}</span>
    </div>
  );
}

function ProfileSkeleton() {
  return (
    <div className="p-4 space-y-4 animate-pulse">
      <div className="h-6 bg-bg-secondary rounded w-1/2" />
      {[...Array(4)].map((_, i) => (
        <div key={i} className="h-32 bg-bg-secondary rounded-xl" />
      ))}
    </div>
  );
}
