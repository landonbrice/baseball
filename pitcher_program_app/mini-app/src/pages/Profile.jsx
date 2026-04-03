import { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../App';
import { useAppContext } from '../hooks/useChatState';
import { usePitcher } from '../hooks/usePitcher';
import { useApi } from '../hooks/useApi';
import { patchProfile, fetchTrainingLoad } from '../api';

// ── Design tokens ──
const T = {
  bgPrimary: '#f5f1eb',
  bgSecondary: '#ffffff',
  bgTertiary: '#e4dfd8',
  textPrimary: '#2a1a18',
  textSecondary: '#6b5f58',
  textMuted: '#b0a89e',
  maroon: '#5c1020',
  maroonMid: '#7a1a2e',
  maroonSoft: '#5c102012',
  flagGreen: '#1D9E75',
  flagYellow: '#BA7517',
  flagRed: '#A32D2D',
  roseBlush: '#e8a0aa',
};

const SECTION_HEADER = {
  fontSize: 10, fontWeight: 700, textTransform: 'uppercase',
  letterSpacing: 1, color: T.textMuted, margin: 0,
};

const CARD = {
  padding: '14px 16px', borderRadius: 12,
  background: T.bgSecondary, border: `1px solid ${T.bgTertiary}`,
};

const TRANSITION = { transition: 'all 150ms ease' };

// ── Helpers ──
function heightDisplay(inches) {
  if (!inches) return '—';
  const ft = Math.floor(inches / 12);
  const rem = inches % 12;
  return `${ft}'${rem}"`;
}

function formatMaxLabel(key) {
  const labels = {
    trap_bar_dl: 'Trap Bar DL', front_squat: 'Front Squat',
    db_bench: 'DB Bench', pullup: 'Pull-Up', bench_press: 'Bench',
  };
  return labels[key] || key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function formatConstraint(val) {
  return (val || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function flagDotColor(level) {
  if (level === 'red') return T.flagRed;
  if (level === 'yellow') return T.flagYellow;
  return T.flagGreen;
}

// ── Main Component ──
export default function Profile() {
  const { pitcherId, initData } = useAuth();
  const navigate = useNavigate();
  const { addMessage } = useAppContext();
  const { profile, loading } = usePitcher(pitcherId, initData);
  const whoopStatus = useApi(pitcherId ? `/api/pitcher/${pitcherId}/whoop-today` : null, initData);

  const [trainingLoad, setTrainingLoad] = useState(null);
  const [editSection, setEditSection] = useState(null);
  const [profileState, setProfileState] = useState(null);

  // Sync profile data into local state for optimistic edits
  useEffect(() => {
    if (profile) setProfileState(profile);
  }, [profile]);

  // Fetch training load separately (lazy)
  useEffect(() => {
    if (!pitcherId) return;
    fetchTrainingLoad(pitcherId, initData)
      .then(setTrainingLoad)
      .catch(() => setTrainingLoad({ weeks: [], streak: 0, current_week_pct: 0 }));
  }, [pitcherId, initData]);

  const handleSave = useCallback(async (partialData) => {
    // Optimistic update
    setProfileState(prev => deepMerge(prev, partialData));
    setEditSection(null);
    try {
      const updated = await patchProfile(pitcherId, partialData, initData);
      setProfileState(updated);
    } catch {
      // Revert on failure
      setProfileState(profile);
    }
  }, [pitcherId, initData, profile]);

  const startEdit = useCallback((section) => {
    setEditSection(section);
  }, []);

  const cancelEdit = useCallback(() => {
    setProfileState(profile);
    setEditSection(null);
  }, [profile]);

  if (loading) return <ProfileSkeleton />;
  if (!profileState) {
    return (
      <div style={{ padding: 16 }}>
        <p style={{ color: T.textMuted, fontSize: 13 }}>Profile not found.</p>
      </div>
    );
  }

  const p = profileState;
  const flags = p.active_flags || {};
  const tl = trainingLoad || { weeks: [], streak: 0, current_week_pct: 0 };

  return (
    <div style={{ background: T.bgPrimary, minHeight: '100vh', paddingBottom: 100 }}>
      {/* 1. Identity Header */}
      <IdentityHeader profile={p} flags={flags} trainingLoad={tl} />

      <div style={{ padding: '16px 16px 0', display: 'flex', flexDirection: 'column', gap: 16 }}>
        {/* 2. Connections */}
        <Connections profile={p} whoopStatus={whoopStatus} />

        {/* 3. Training Load Chart */}
        <Section label="Training Load">
          <TrainingLoadChart weeks={tl.weeks} />
        </Section>

        {/* 4. Goals */}
        <EditableSection
          label="Goals"
          editing={editSection === 'goals'}
          onEdit={() => startEdit('goals')}
          onCancel={cancelEdit}
        >
          <GoalsSection
            goals={p.goals || {}}
            editing={editSection === 'goals'}
            onSave={(goals) => handleSave({ goals })}
          />
        </EditableSection>

        {/* 5. Arsenal */}
        <EditableSection
          label="Arsenal"
          editing={editSection === 'arsenal'}
          onEdit={() => startEdit('arsenal')}
          onCancel={cancelEdit}
        >
          <ArsenalSection
            arsenal={(p.pitching_profile || {}).pitch_arsenal || []}
            editing={editSection === 'arsenal'}
            onSave={(arr) => handleSave({ pitching_profile: { pitch_arsenal: arr } })}
          />
        </EditableSection>

        {/* 6. Strength */}
        <EditableSection
          label="Strength"
          editing={editSection === 'strength'}
          onEdit={() => startEdit('strength')}
          onCancel={cancelEdit}
        >
          <StrengthSection
            maxes={(p.current_training || {}).current_maxes || {}}
            editing={editSection === 'strength'}
            onSave={(maxes) => handleSave({ current_training: { current_maxes: maxes } })}
          />
        </EditableSection>

        {/* 7. Physical */}
        <EditableSection
          label="Physical"
          editing={editSection === 'physical'}
          onEdit={() => startEdit('physical')}
          onCancel={cancelEdit}
        >
          <PhysicalSection
            physical={p.physical_profile || {}}
            editing={editSection === 'physical'}
            onSave={(phys) => handleSave({ physical_profile: phys })}
          />
        </EditableSection>

        {/* 8. Injury History & Modifications */}
        <Section label="Injury History">
          <InjurySection
            injuries={p.injury_history || []}
            modifications={(flags.active_modifications || [])}
            navigate={navigate}
            addMessage={addMessage}
          />
        </Section>

        {/* 9. Training Preferences */}
        <Section label="Training Preferences">
          <PreferencesSection training={p.current_training || {}} />
        </Section>

        {/* 10. Settings */}
        <EditableSection
          label="Settings"
          editing={editSection === 'settings'}
          onEdit={() => startEdit('settings')}
          onCancel={cancelEdit}
        >
          <SettingsSection
            prefs={p.preferences || {}}
            editing={editSection === 'settings'}
            onSave={(prefs) => handleSave({ preferences: prefs })}
          />
        </EditableSection>
      </div>
    </div>
  );
}

// ── Identity Header ──
function IdentityHeader({ profile, flags, trainingLoad }) {
  const roleLabel = profile.role === 'starter'
    ? `${profile.rotation_length || 7}-day starter`
    : profile.role === 'reliever'
      ? (profile.role_detail || 'Reliever')
      : profile.role || 'Pitcher';
  const throws = profile.throws === 'L' ? 'LHP' : 'RHP';
  const flagLevel = flags.current_flag_level || 'green';

  return (
    <div style={{
      background: 'linear-gradient(165deg, #5c1020 0%, #7a1a2e 100%)',
      padding: '28px 20px 24px',
    }}>
      {/* Icon + Name */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 14 }}>
        <div style={{
          width: 56, height: 56, borderRadius: 14,
          background: 'rgba(255,255,255,0.1)', border: '1.5px solid rgba(255,255,255,0.2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 28,
        }}>
          {'\u26BE'}
        </div>
        <div>
          <div style={{ fontSize: 22, fontWeight: 700, color: '#fff', letterSpacing: -0.5 }}>
            {profile.name}
          </div>
          <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
            <span style={pillBadge}>{roleLabel}</span>
            <span style={pillBadge}>{throws}</span>
          </div>
        </div>
      </div>

      {/* Stat row */}
      <div style={{
        background: 'rgba(255,255,255,0.06)', borderRadius: 12, padding: '12px 0',
        display: 'flex',
      }}>
        <StatCell
          label="Flag"
          value={
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, justifyContent: 'center' }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: flagDotColor(flagLevel) }} />
              <span>{flagLevel.charAt(0).toUpperCase() + flagLevel.slice(1)}</span>
            </div>
          }
        />
        <StatDivider />
        <StatCell label="Arm Feel" value={`${flags.current_arm_feel ?? '—'}/5`} />
        <StatDivider />
        <StatCell label="This Week" value={`${trainingLoad.current_week_pct}%`} />
        <StatDivider />
        <StatCell label="Streak" value={`${trainingLoad.streak}d`} />
      </div>
    </div>
  );
}

const pillBadge = {
  fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 6,
  background: 'rgba(255,255,255,0.15)', color: T.roseBlush,
};

function StatCell({ label, value }) {
  return (
    <div style={{ flex: 1, textAlign: 'center' }}>
      <div style={{ fontSize: 18, fontWeight: 700, color: '#fff' }}>{value}</div>
      <div style={{ fontSize: 9, textTransform: 'uppercase', color: T.roseBlush, marginTop: 2 }}>{label}</div>
    </div>
  );
}

function StatDivider() {
  return <div style={{ width: 1, background: 'rgba(255,255,255,0.08)', margin: '4px 0' }} />;
}

// ── Connections ──
function Connections({ profile, whoopStatus }) {
  const whoopLinked = whoopStatus?.data?.linked;
  const whoopRecovery = whoopStatus?.data?.recovery_score;
  const telegramConnected = !!profile.telegram_id;
  const telegramHandle = profile.telegram_username ? `@${profile.telegram_username}` : null;

  return (
    <div style={{ display: 'flex', gap: 8 }}>
      <ConnectionCard
        label="WHOOP"
        connected={whoopLinked}
        detail={whoopLinked ? `${whoopRecovery ?? '—'}% recovery` : 'Not connected'}
      />
      <ConnectionCard
        label="Telegram"
        connected={telegramConnected}
        detail={telegramConnected ? (telegramHandle || 'Connected') : 'Not connected'}
      />
    </div>
  );
}

function ConnectionCard({ label, connected, detail }) {
  return (
    <div style={{ ...CARD, flex: 1, padding: '10px 12px', display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{
        width: 8, height: 8, borderRadius: '50%',
        background: connected ? T.flagGreen : T.textMuted,
      }} />
      <div>
        <div style={{ fontSize: 11, fontWeight: 600, color: T.textPrimary }}>{label}</div>
        <div style={{ fontSize: 10, color: connected ? T.textSecondary : T.textMuted }}>{detail}</div>
      </div>
    </div>
  );
}

// ── Training Load Chart ──
function TrainingLoadChart({ weeks }) {
  if (!weeks || weeks.length === 0) {
    return <div style={{ ...CARD, padding: 16, textAlign: 'center' }}>
      <p style={{ fontSize: 11, color: T.textMuted }}>No training data yet</p>
    </div>;
  }

  // Reverse so oldest is on the left
  const ordered = [...weeks].reverse();

  return (
    <div style={{ ...CARD, padding: 16 }}>
      <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end', height: 80, justifyContent: 'center' }}>
        {ordered.map((w, i) => {
          const isCurrent = i === ordered.length - 1;
          const barH = 20 + (w.pct * 0.6);
          return (
            <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 1, maxWidth: 52 }}>
              <div style={{
                fontSize: 11, fontWeight: 700, marginBottom: 4,
                color: isCurrent ? T.maroon : T.textSecondary,
              }}>
                {w.pct}%
              </div>
              <div style={{
                width: '100%', height: barH, borderRadius: 6, ...TRANSITION,
                background: isCurrent
                  ? 'linear-gradient(180deg, #5c1020, #7a1a2e)'
                  : `${T.bgTertiary}`,
              }} />
            </div>
          );
        })}
      </div>
      <div style={{ display: 'flex', gap: 10, marginTop: 8, justifyContent: 'center' }}>
        {ordered.map((w, i) => {
          const isCurrent = i === ordered.length - 1;
          return (
            <div key={i} style={{
              flex: 1, maxWidth: 52, textAlign: 'center',
              fontSize: 10, fontWeight: isCurrent ? 600 : 400,
              color: isCurrent ? T.maroon : T.textMuted,
            }}>
              {w.week_label}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Section wrappers ──
function Section({ label, children }) {
  return (
    <div>
      <p style={{ ...SECTION_HEADER, marginBottom: 8 }}>{label}</p>
      {children}
    </div>
  );
}

function EditableSection({ label, editing, onEdit, onCancel, children }) {
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <p style={{ ...SECTION_HEADER, marginBottom: 0 }}>{label}</p>
        {!editing && (
          <button onClick={onEdit} style={{
            background: 'none', border: 'none', cursor: 'pointer',
            fontSize: 11, fontWeight: 600, color: T.maroon, padding: 0,
          }}>Edit</button>
        )}
      </div>
      {children}
    </div>
  );
}

function SaveCancelButtons({ onSave, onCancel }) {
  return (
    <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 10 }}>
      <button onClick={onCancel} style={{
        background: 'none', border: 'none', cursor: 'pointer',
        fontSize: 11, color: T.textMuted, padding: 0,
      }}>Cancel</button>
      <button onClick={onSave} style={{
        background: T.maroon, color: '#fff', border: 'none', cursor: 'pointer',
        fontSize: 11, fontWeight: 600, padding: '3px 10px', borderRadius: 6,
      }}>Save</button>
    </div>
  );
}

// ── Goals ──
function GoalsSection({ goals, editing, onSave }) {
  const [primary, setPrimary] = useState(goals.primary || '');
  const [secondary, setSecondary] = useState(goals.secondary || '');

  useEffect(() => {
    setPrimary(goals.primary || '');
    setSecondary(goals.secondary || '');
  }, [goals, editing]);

  if (!editing) {
    return (
      <div style={CARD}>
        <GoalRow label="Primary goal" name={goals.primary || '—'} color={T.maroon} />
        {goals.secondary && <GoalRow label="Secondary goal" name={goals.secondary} color={T.textMuted} />}
      </div>
    );
  }

  return (
    <div style={{ ...CARD, border: `1.5px solid ${T.maroon}26` }}>
      <label style={{ fontSize: 10, color: T.textMuted }}>Primary goal</label>
      <input value={primary} onChange={e => setPrimary(e.target.value)}
        style={editInput} />
      <label style={{ fontSize: 10, color: T.textMuted, marginTop: 8, display: 'block' }}>Secondary goal</label>
      <input value={secondary} onChange={e => setSecondary(e.target.value)}
        style={editInput} />
      <SaveCancelButtons onSave={() => onSave({ primary, secondary })} onCancel={() => {}} />
    </div>
  );
}

function GoalRow({ label, name, color }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0' }}>
      <div style={{ width: 6, height: 6, borderRadius: '50%', background: color, flexShrink: 0 }} />
      <div>
        <div style={{ fontSize: 13, fontWeight: 500, color: T.textPrimary }}>{name}</div>
        <div style={{ fontSize: 10, color: T.textMuted }}>{label}</div>
      </div>
    </div>
  );
}

// ── Arsenal ──
function ArsenalSection({ arsenal, editing, onSave }) {
  const [pitches, setPitches] = useState([...arsenal]);
  const [newPitch, setNewPitch] = useState('');

  useEffect(() => {
    setPitches([...arsenal]);
    setNewPitch('');
  }, [arsenal, editing]);

  const removePitch = (idx) => setPitches(p => p.filter((_, i) => i !== idx));
  const addPitch = () => {
    const trimmed = newPitch.trim();
    if (trimmed && !pitches.includes(trimmed)) {
      setPitches(p => [...p, trimmed]);
      setNewPitch('');
    }
  };

  return (
    <div style={{ ...CARD, ...(editing ? { border: `1.5px solid ${T.maroon}26` } : {}) }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {(editing ? pitches : arsenal).map((pitch, i) => (
          <span key={i} style={{
            fontSize: 12, padding: '5px 14px', borderRadius: 20,
            background: T.maroonSoft, color: T.maroon, fontWeight: 600,
            display: 'flex', alignItems: 'center', gap: 6,
          }}>
            {pitch}
            {editing && (
              <span onClick={() => removePitch(i)} style={{
                cursor: 'pointer', color: T.flagRed, fontWeight: 700, fontSize: 14, lineHeight: 1,
              }}>{'\u00D7'}</span>
            )}
          </span>
        ))}
        {editing && (
          <input
            value={newPitch}
            onChange={e => setNewPitch(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && addPitch()}
            placeholder="Add pitch..."
            style={{
              padding: '5px 10px', borderRadius: 20,
              border: `1.5px dashed ${T.maroon}40`, background: 'transparent',
              fontSize: 12, color: T.textPrimary, outline: 'none', width: 100,
            }}
          />
        )}
      </div>
      {editing && <SaveCancelButtons onSave={() => onSave(pitches)} onCancel={() => {}} />}
    </div>
  );
}

// ── Strength ──
function StrengthSection({ maxes, editing, onSave }) {
  const [vals, setVals] = useState({ ...maxes });

  useEffect(() => { setVals({ ...maxes }); }, [maxes, editing]);

  const entries = Object.entries(editing ? vals : maxes);
  if (entries.length === 0) {
    return <div style={CARD}><p style={{ fontSize: 11, color: T.textMuted }}>No maxes recorded</p></div>;
  }

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
        {entries.map(([key, val]) => (
          <div key={key} style={{
            ...CARD, padding: '12px 10px', textAlign: 'center',
            ...(editing ? { border: `1.5px solid ${T.maroon}40` } : {}),
          }}>
            {editing ? (
              <input
                value={vals[key] || ''}
                onChange={e => setVals(v => ({ ...v, [key]: e.target.value === '' ? '' : Number(e.target.value) || e.target.value }))}
                type="number"
                style={{
                  width: '100%', textAlign: 'center', fontSize: 20, fontWeight: 700,
                  color: T.textPrimary, background: 'transparent', border: 'none',
                  borderBottom: `2px solid ${T.maroon}`, outline: 'none',
                }}
              />
            ) : (
              <div style={{ fontSize: 20, fontWeight: 700, color: T.textPrimary }}>
                {val || '—'}
                {val && <span style={{ fontSize: 11, color: T.textMuted }}> lbs</span>}
              </div>
            )}
            <div style={{ fontSize: 10, color: T.textMuted, marginTop: 2 }}>{formatMaxLabel(key)}</div>
          </div>
        ))}
      </div>
      {editing && (
        <SaveCancelButtons
          onSave={() => {
            const numeric = {};
            for (const [k, v] of Object.entries(vals)) {
              numeric[k] = typeof v === 'number' ? v : (parseFloat(v) || 0);
            }
            onSave(numeric);
          }}
          onCancel={() => {}}
        />
      )}
    </div>
  );
}

// ── Physical ──
function PhysicalSection({ physical, editing, onSave }) {
  const [height, setHeight] = useState(physical.height_in || '');
  const [weight, setWeight] = useState(physical.weight_lbs || '');
  const [bodyComp, setBodyComp] = useState(physical.body_comp_goal || 'Maintain');

  useEffect(() => {
    setHeight(physical.height_in || '');
    setWeight(physical.weight_lbs || '');
    setBodyComp(physical.body_comp_goal || 'Maintain');
  }, [physical, editing]);

  const cards = [
    {
      label: 'Height', value: heightDisplay(physical.height_in),
      editContent: (
        <input type="number" value={height} onChange={e => setHeight(e.target.value)}
          placeholder="inches"
          style={gridEditInput} />
      ),
    },
    {
      label: 'Weight', value: physical.weight_lbs ? `${physical.weight_lbs}lbs` : '—',
      editContent: (
        <input type="number" value={weight} onChange={e => setWeight(e.target.value)}
          placeholder="lbs"
          style={gridEditInput} />
      ),
    },
    {
      label: 'Body Comp', value: physical.body_comp_goal || '—',
      editContent: (
        <select value={bodyComp} onChange={e => setBodyComp(e.target.value)}
          style={{ ...gridEditInput, appearance: 'auto' }}>
          <option>Maintain</option>
          <option>Gain</option>
          <option>Cut</option>
        </select>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
        {cards.map(c => (
          <div key={c.label} style={{
            ...CARD, padding: '12px 10px', textAlign: 'center',
            ...(editing ? { border: `1.5px solid ${T.maroon}40` } : {}),
          }}>
            {editing ? c.editContent : (
              <div style={{ fontSize: 20, fontWeight: 700, color: T.textPrimary }}>{c.value}</div>
            )}
            <div style={{ fontSize: 10, color: T.textMuted, marginTop: 2 }}>{c.label}</div>
          </div>
        ))}
      </div>
      {editing && (
        <SaveCancelButtons
          onSave={() => onSave({
            height_in: parseInt(height) || physical.height_in,
            weight_lbs: parseInt(weight) || physical.weight_lbs,
            body_comp_goal: bodyComp,
          })}
          onCancel={() => {}}
        />
      )}
    </div>
  );
}

// ── Injury History ──
function InjurySection({ injuries, modifications, navigate, addMessage }) {
  if (!injuries || injuries.length === 0) {
    return <div style={CARD}><p style={{ fontSize: 11, color: T.textMuted }}>No injury history recorded</p></div>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {injuries.map((injury, i) => {
        const resolved = (injury.severity || '').toLowerCase() === 'resolved'
          || (injury.status || '').toLowerCase() === 'resolved';
        const statusColor = resolved ? T.flagGreen : T.flagYellow;
        const statusLabel = resolved ? 'Resolved' : 'Active';

        return (
          <div key={i} style={CARD}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ width: 10, height: 10, borderRadius: '50%', background: statusColor, flexShrink: 0 }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 500, color: T.textPrimary }}>
                  {(injury.area || '').replace(/_/g, ' ')}
                </div>
                <div style={{ fontSize: 11, color: T.textMuted }}>
                  {[injury.severity, injury.date].filter(Boolean).join(' — ')}
                </div>
              </div>
              <span style={{
                fontSize: 9, textTransform: 'uppercase', fontWeight: 600,
                padding: '2px 8px', borderRadius: 10,
                color: statusColor, background: `${statusColor}14`,
              }}>{statusLabel}</span>
            </div>

            {/* Nested modifications for this injury */}
            {!resolved && modifications.length > 0 && (
              <div style={{
                marginLeft: 20, paddingLeft: 12, marginTop: 8,
                borderLeft: `2px solid ${T.bgTertiary}`,
              }}>
                <div style={{ fontSize: 9, textTransform: 'uppercase', fontWeight: 700, color: T.textMuted, marginBottom: 4 }}>
                  Currently applied
                </div>
                {modifications.map((mod, j) => (
                  <div key={j} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '2px 0' }}>
                    <div style={{ width: 5, height: 5, borderRadius: '50%', background: T.flagYellow }} />
                    <span style={{ fontSize: 12, fontWeight: 500, color: T.textPrimary }}>{mod}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}

      <button
        onClick={() => {
          addMessage({ role: 'user', type: 'text', content: 'How does my injury history affect my current training plan?' });
          navigate('/coach');
        }}
        style={{
          background: 'none', border: 'none', cursor: 'pointer', padding: 0,
          fontSize: 11, color: T.maroon, fontWeight: 600, textAlign: 'left',
        }}
      >
        Ask coach how this affects my plan {'\u2192'}
      </button>
    </div>
  );
}

// ── Training Preferences ──
function PreferencesSection({ training }) {
  const preferred = training.preferred_exercises || [];
  const avoided = training.disliked_or_avoided || [];
  const equipment = training.equipment_constraints || [];

  const hasAnything = preferred.length > 0 || avoided.length > 0 || equipment.length > 0;

  if (!hasAnything) {
    return <div style={CARD}><p style={{ fontSize: 11, color: T.textMuted }}>No preferences learned yet — use the swap system to teach me</p></div>;
  }

  return (
    <div style={CARD}>
      {equipment.length > 0 && (
        <div style={{ marginBottom: preferred.length + avoided.length > 0 ? 10 : 0 }}>
          <div style={{ fontSize: 9, textTransform: 'uppercase', fontWeight: 700, color: T.textMuted, marginBottom: 6 }}>
            Equipment Constraints
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {equipment.map((c, i) => (
              <span key={i} style={constraintPill(T.flagRed)}>{formatConstraint(c)}</span>
            ))}
          </div>
        </div>
      )}
      {avoided.length > 0 && (
        <div style={{ marginBottom: preferred.length > 0 ? 10 : 0 }}>
          <div style={{ fontSize: 9, textTransform: 'uppercase', fontWeight: 700, color: T.textMuted, marginBottom: 6 }}>
            Avoids
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {avoided.map((c, i) => (
              <span key={i} style={constraintPill(T.flagRed)}>{formatConstraint(c)}</span>
            ))}
          </div>
        </div>
      )}
      {preferred.length > 0 && (
        <div>
          <div style={{ fontSize: 9, textTransform: 'uppercase', fontWeight: 700, color: T.textMuted, marginBottom: 6 }}>
            Preferred
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {preferred.map((c, i) => (
              <span key={i} style={constraintPill(T.flagGreen)}>{formatConstraint(c)}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function constraintPill(color) {
  return {
    fontSize: 11, padding: '4px 10px', borderRadius: 16,
    background: `${color}0F`, color: color, fontWeight: 500,
  };
}

// ── Settings ──
function SettingsSection({ prefs, editing, onSave }) {
  const [notifTime, setNotifTime] = useState(prefs.notification_time || '9:00 AM');
  const [detailLevel, setDetailLevel] = useState(prefs.detail_level || 'normal');

  useEffect(() => {
    setNotifTime(prefs.notification_time || '9:00 AM');
    setDetailLevel(prefs.detail_level || 'normal');
  }, [prefs, editing]);

  const rows = [
    { label: 'Notification time', value: prefs.notification_time || '9:00 AM' },
    { label: 'Detail level', value: prefs.detail_level || 'normal' },
  ];

  if (!editing) {
    return (
      <div style={CARD}>
        {rows.map((r, i) => (
          <div key={i} style={{
            display: 'flex', justifyContent: 'space-between', padding: '8px 0',
            borderBottom: i < rows.length - 1 ? `0.5px solid ${T.bgTertiary}` : 'none',
          }}>
            <span style={{ fontSize: 12, color: T.textSecondary }}>{r.label}</span>
            <span style={{ fontSize: 13, fontWeight: 600, color: T.textPrimary }}>{r.value}</span>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div style={{ ...CARD, border: `1.5px solid ${T.maroon}26` }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: `0.5px solid ${T.bgTertiary}` }}>
        <span style={{ fontSize: 12, color: T.textSecondary }}>Notification time</span>
        <input value={notifTime} onChange={e => setNotifTime(e.target.value)}
          style={{ ...editInputRight, width: 90 }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
        <span style={{ fontSize: 12, color: T.textSecondary }}>Detail level</span>
        <select value={detailLevel} onChange={e => setDetailLevel(e.target.value)}
          style={{ ...editInputRight, appearance: 'auto', width: 100 }}>
          <option value="brief">Brief</option>
          <option value="normal">Normal</option>
          <option value="detailed">Detailed</option>
        </select>
      </div>
      <SaveCancelButtons
        onSave={() => onSave({ notification_time: notifTime, detail_level: detailLevel })}
        onCancel={() => {}}
      />
    </div>
  );
}

// ── Shared input styles ──
const editInput = {
  width: '100%', padding: '8px 10px', borderRadius: 8,
  border: `1.5px solid ${T.maroon}30`, background: T.bgPrimary,
  fontSize: 13, color: T.textPrimary, outline: 'none',
  marginTop: 4,
};

const gridEditInput = {
  width: '100%', textAlign: 'center', fontSize: 20, fontWeight: 700,
  color: T.textPrimary, background: 'transparent', border: 'none',
  borderBottom: `2px solid ${T.maroon}`, outline: 'none',
};

const editInputRight = {
  textAlign: 'right', fontSize: 13, fontWeight: 600,
  color: T.textPrimary, background: 'transparent',
  border: 'none', borderBottom: `2px solid ${T.maroon}`,
  outline: 'none',
};

// ── Skeleton ──
function ProfileSkeleton() {
  return (
    <div style={{ background: T.bgPrimary, minHeight: '100vh' }}>
      <div style={{ background: 'linear-gradient(165deg, #5c1020, #7a1a2e)', height: 180 }} />
      <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
        {[...Array(5)].map((_, i) => (
          <div key={i} style={{
            height: 80, background: T.bgSecondary, borderRadius: 12,
            opacity: 0.6,
          }} />
        ))}
      </div>
    </div>
  );
}

// ── Deep merge utility ──
function deepMerge(base, update) {
  if (!base || typeof base !== 'object') return update;
  const merged = { ...base };
  for (const key of Object.keys(update)) {
    if (merged[key] && typeof merged[key] === 'object' && typeof update[key] === 'object' && !Array.isArray(update[key])) {
      merged[key] = deepMerge(merged[key], update[key]);
    } else {
      merged[key] = update[key];
    }
  }
  return merged;
}
