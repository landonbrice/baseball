import { useMemo, useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../App';
import { useAppContext } from '../hooks/useChatState';
import { usePitcher } from '../hooks/usePitcher';
import { useApi } from '../hooks/useApi';
import WeekStrip from '../components/WeekStrip';
import DailyCard from '../components/DailyCard';
import UpcomingDays from '../components/UpcomingDays';
import ThrowingWeekPreview from '../components/ThrowingWeekPreview';
import InsightsCard from '../components/InsightsCard';
import SessionProgress from '../components/SessionProgress';
import Sparkline from '../components/Sparkline';
import StreakBadge from '../components/StreakBadge';
import StaffPulse from '../components/StaffPulse';
import FlagBadge from '../components/FlagBadge';
import WhoopCard from '../components/WhoopCard';
import LockedState from '../components/LockedState';

const BRIEF_STATUS_COLORS = {
  green: '#1D9E75',
  yellow: '#BA7517',
  red: '#A32D2D',
};

function MorningBriefCard({ brief, rotationDay, rotationLength }) {
  const todayDate = new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', timeZone: 'America/Chicago' });
  const nuggets = [
    brief.arm_verdict && { key: 'arm', emoji: '\uD83D\uDCAA', heading: 'Arm Feel', value: brief.arm_verdict.value, verdict: brief.arm_verdict.label, status: brief.arm_verdict.status },
    brief.sleep_verdict && { key: 'sleep', emoji: '\uD83D\uDE34', heading: 'Sleep', value: brief.sleep_verdict.value, verdict: brief.sleep_verdict.label, status: brief.sleep_verdict.status },
    brief.today_focus && { key: 'today', emoji: '\uD83C\uDFAF', heading: 'Today', value: brief.today_focus.value, verdict: brief.today_focus.label },
    brief.watch_item ? { key: 'watch', emoji: '\u26A1', heading: 'Watch', value: brief.watch_item.value, verdict: brief.watch_item.label, status: brief.watch_item.status }
      : { key: 'watch', emoji: '\u2705', heading: 'Watch', value: 'All clear', verdict: 'No concerns', status: 'green' },
  ].filter(Boolean);

  return (
    <div style={{ background: '#fff', borderRadius: 12, padding: 14 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 10 }}>
        <span style={{ fontSize: 14 }}>{'\u2600\uFE0F'}</span>
        <span style={{ fontSize: 14, fontWeight: 700, color: '#2a1a18' }}>Morning Brief</span>
        <span style={{ fontSize: 11, color: '#b0a89e', marginLeft: 'auto' }}>
          Day {rotationDay ?? '?'} of {rotationLength ?? 7} {'\u00B7'} {todayDate}
        </span>
      </div>

      {/* 2x2 nugget grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: brief.coaching_note ? 12 : 0 }}>
        {nuggets.map(n => (
          <div key={n.key} style={{
            background: '#f5f1eb', borderRadius: 10, padding: '10px 12px',
            border: '1px solid #e4dfd8',
          }}>
            <div style={{ fontSize: 10, fontWeight: 600, color: '#b0a89e', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 4 }}>
              {n.emoji} {n.heading}
            </div>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#2a1a18', lineHeight: 1.2 }}>
              {n.value}
            </div>
            <div style={{
              fontSize: 11, marginTop: 2,
              color: BRIEF_STATUS_COLORS[n.status] || '#6b5f58',
            }}>
              {n.verdict}
            </div>
          </div>
        ))}
      </div>

      {/* Coaching note */}
      {brief.coaching_note && (
        <div style={{
          borderLeft: '3px solid #BA7517',
          background: 'rgba(186,117,23,0.08)',
          borderRadius: '0 8px 8px 0',
          padding: '10px 12px',
        }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: '#BA7517', marginBottom: 4 }}>
            {'\uD83D\uDCA1'} Coach's Note
          </div>
          <div style={{ fontSize: 12, color: '#6b5f58', lineHeight: 1.5 }}>
            {brief.coaching_note}
          </div>
        </div>
      )}
    </div>
  );
}

function NewPitcherWelcome({ profile, navigate }) {
  const firstName = (profile?.name || '').split(' ')[0];
  const role = profile?.role || 'starter';
  const roleLabel = role === 'starter' ? 'Starter' : 'Reliever';
  const rotLen = profile?.rotation_length || 7;
  const arsenal = (profile?.pitching_profile || {}).pitch_arsenal || [];
  const training = profile?.current_training || {};
  const maxes = training.current_maxes || {};
  const experience = training.lifting_experience;
  const split = training.current_split;
  const injuries = profile?.injury_history || [];

  const hasMaxes = Object.values(maxes).some(v => v && v !== 0 && v !== '0');

  const maxLabels = { trap_bar_dl: 'Trap Bar DL', front_squat: 'Front Squat', db_bench: 'DB Bench', pullup: 'Pull-Up' };
  const maxEntries = Object.entries(maxes)
    .filter(([, v]) => v && v !== 0 && v !== '0')
    .map(([k, v]) => [maxLabels[k] || k, typeof v === 'number' ? `${v} lbs` : String(v)]);

  const splitLabels = { upper_lower_2x: 'Upper/Lower 2x', full_body_3x: 'Full Body 3x', push_pull_legs: 'PPL', upper_lower: 'Upper/Lower' };
  const expLabels = { beginner: 'Beginner', intermediate: 'Intermediate', advanced: 'Advanced' };

  return (
    <div style={{ marginTop: 12 }}>
      {/* Welcome Card */}
      <div style={{ background: '#fff', borderRadius: 12, padding: 16 }}>
        <p style={{ fontSize: 13, color: '#6b5f58', margin: '0 0 12px', lineHeight: 1.5 }}>
          {"I've loaded your intake data and built a profile for you. Here's what I know so far:"}
        </p>

        {/* Arsenal pills */}
        {arsenal.length > 0 && (
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 10, fontWeight: 600, color: '#b0a89e', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6 }}>Arsenal</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {arsenal.map((pitch, i) => (
                <span key={i} className="bg-accent-blue/10 text-accent-blue" style={{ padding: '4px 10px', borderRadius: 99, fontSize: 11, fontWeight: 500 }}>{pitch}</span>
              ))}
            </div>
          </div>
        )}

        {/* Training snapshot grid */}
        {(hasMaxes || experience || split) && (
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 10, fontWeight: 600, color: '#b0a89e', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6 }}>Training Snapshot</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              {maxEntries.map(([label, val]) => (
                <div key={label} style={{ background: '#f5f1eb', borderRadius: 8, padding: '8px 10px' }}>
                  <div style={{ fontSize: 10, color: '#b0a89e' }}>{label}</div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: '#2a1a18', marginTop: 2 }}>{val}</div>
                </div>
              ))}
              {experience && (
                <div style={{ background: '#f5f1eb', borderRadius: 8, padding: '8px 10px' }}>
                  <div style={{ fontSize: 10, color: '#b0a89e' }}>Experience</div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: '#2a1a18', marginTop: 2 }}>{expLabels[experience] || experience}</div>
                </div>
              )}
              {split && (
                <div style={{ background: '#f5f1eb', borderRadius: 8, padding: '8px 10px' }}>
                  <div style={{ fontSize: 10, color: '#b0a89e' }}>Current Split</div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: '#2a1a18', marginTop: 2 }}>{splitLabels[split] || split}</div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Injury awareness banner */}
        {injuries.length > 0 && (
          <div style={{ background: 'rgba(186,117,23,0.08)', border: '1px solid rgba(186,117,23,0.25)', borderRadius: 8, padding: '10px 12px', marginBottom: 12 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: '#BA7517', marginBottom: 4 }}>Injury-Aware Programming</div>
            <div style={{ fontSize: 11, color: '#6b5f58', lineHeight: 1.5 }}>
              {injuries.map(inj => `${inj.area?.replace(/_/g, ' ')}${inj.severity ? ` (${inj.severity})` : ''}`).join(' + ')}
              {'. Your plans will account for these with modified loads and elevated monitoring.'}
            </div>
          </div>
        )}

        {/* CTA */}
        <button
          onClick={() => navigate('/coach')}
          style={{ width: '100%', background: '#5c1020', color: '#fff', border: 'none', borderRadius: 12, padding: '14px 0', fontSize: 14, fontWeight: 600, cursor: 'pointer' }}
        >
          {'\uD83D\uDCAC Start your first check-in'}
        </button>
        <p style={{ fontSize: 11, color: '#b0a89e', textAlign: 'center', marginTop: 6, marginBottom: 0 }}>{"Takes ~2 minutes. I'll build your plan from there."}</p>
      </div>

      {/* What you'll get each day */}
      <div style={{ background: '#fff', borderRadius: 12, padding: 16, marginTop: 10 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: '#2a1a18', marginBottom: 10 }}>What you get each day</div>
        {[
          ['\uD83C\uDFCB\uFE0F', 'Personalized lifting plan', 'Exercises selected from 95+ options based on your rotation day and injury profile'],
          ['\uD83D\uDCAA', 'Arm care prescription', 'Targeted shoulder, elbow, and forearm work matched to your history'],
          ['\u26BE', 'Throwing program', 'Plyo drills, long toss, and bullpen plans calibrated to your schedule'],
          ['\uD83D\uDCC8', 'Season trends', 'Arm feel tracking, recovery patterns, and weekly coaching insights'],
        ].map(([icon, title, desc], i) => (
          <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', marginBottom: i < 3 ? 10 : 0 }}>
            <span style={{ fontSize: 18, lineHeight: 1 }}>{icon}</span>
            <div>
              <div style={{ fontSize: 12, fontWeight: 600, color: '#2a1a18' }}>{title}</div>
              <div style={{ fontSize: 11, color: '#6b5f58', lineHeight: 1.4, marginTop: 1 }}>{desc}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Home() {
  const { pitcherId, initData } = useAuth();
  const { globalRefreshKey, checkinCompleted } = useAppContext();
  const navigate = useNavigate();
  const suffix = globalRefreshKey ? `?_r=${globalRefreshKey}` : '';
  const { profile, log, progression, loading, error } = usePitcher(pitcherId, initData, suffix);
  const exercises = useApi('/api/exercises', initData);
  const slugs = useApi('/api/exercises/slugs', initData);
  const upcoming = useApi(pitcherId ? `/api/pitcher/${pitcherId}/upcoming${suffix}` : null, initData);
  const weekSummary = useApi(pitcherId ? `/api/pitcher/${pitcherId}/week-summary${suffix}` : null, initData);
  const trendData = useApi(pitcherId ? `/api/pitcher/${pitcherId}/trend${suffix}` : null, initData);
  const narrativeData = useApi(pitcherId ? `/api/pitcher/${pitcherId}/weekly-narrative${suffix}` : null, initData);
  const staffPulse = useApi('/api/staff/pulse', initData);
  const whoopData = useApi(pitcherId ? `/api/pitcher/${pitcherId}/whoop-today${suffix}` : null, initData);

  const exerciseMap = useMemo(() => {
    if (!exercises.data?.exercises) return {};
    const map = {};
    for (const ex of exercises.data.exercises) map[ex.id] = ex;
    return map;
  }, [exercises.data]);
  const slugMap = useMemo(() => slugs.data || {}, [slugs.data]);
  const [selectedDate, setSelectedDate] = useState(null);
  const [showUpcoming, setShowUpcoming] = useState(false);

  const entries = log?.entries || [];
  const todayStr = new Date().toLocaleDateString('en-CA', { timeZone: 'America/Chicago' });
  const exactTodayEntry = entries.find(e => e.date === todayStr);
  const todayEntry = exactTodayEntry || entries[entries.length - 1];
  const isShowingStaleEntry = !exactTodayEntry && !!todayEntry;
  const checkinSavedButNoPlan = exactTodayEntry && !exactTodayEntry.plan_narrative && !!exactTodayEntry.pre_training;
  const displayEntry = useMemo(() => {
    if (!selectedDate) return todayEntry;
    return entries.find(e => e.date === selectedDate) || null;
  }, [selectedDate, entries, todayEntry]);

  if (loading) return <div style={{ padding: 20 }}><p>Loading...</p></div>;

  const flags = profile?.active_flags || {};
  const firstName = String((profile?.name || 'Dashboard').split(' ')[0]);
  const role = String(profile?.role || 'starter');
  const roleLabel = role === 'starter' ? 'Starter' : 'Reliever';
  const flagLevel = String(flags.current_flag_level || 'green');
  const armFeel = typeof flags.current_arm_feel === 'number' ? flags.current_arm_feel : null;
  const isNewPitcher = !entries.length && !flags.last_outing_date;
  const hasPlan = !!(todayEntry?.plan_narrative || todayEntry?.plan_generated?.exercise_blocks?.length);
  const hasCheckedIn = checkinCompleted || !!((todayEntry?.pre_training || {}).arm_feel && hasPlan);
  const isViewingPast = selectedDate && selectedDate !== todayStr;

  const rawBrief = todayEntry?.morning_brief || (todayEntry?.plan_generated || {}).morning_brief;
  const parsedBrief = useMemo(() => {
    if (!rawBrief) return null;
    if (typeof rawBrief === 'object' && rawBrief.arm_verdict) return rawBrief;
    if (typeof rawBrief === 'string') {
      try {
        const obj = JSON.parse(rawBrief);
        if (obj && obj.arm_verdict) return obj;
      } catch { /* plain text fallback */ }
    }
    return null;
  }, [rawBrief]);
  const morningBrief = parsedBrief ? null : (typeof rawBrief === 'string' ? rawBrief : null);
  const sleepHours = typeof (todayEntry?.pre_training || {}).sleep_hours === 'number' ? todayEntry.pre_training.sleep_hours : null;
  const rawDur = (todayEntry?.lifting || {}).estimated_duration_min || (todayEntry?.plan_generated || {}).estimated_duration_min;
  const estDuration = typeof rawDur === 'number' ? rawDur : null;

  const rawCE = todayEntry?.completed_exercises;
  const completed = (rawCE && typeof rawCE === 'object' && !Array.isArray(rawCE)) ? rawCE : {};
  const allEx = [
    ...((todayEntry?.arm_care || {}).exercises || (todayEntry?.plan_generated?.arm_care || {}).exercises || []),
    ...((todayEntry?.lifting || {}).exercises || (todayEntry?.plan_generated?.lifting || {}).exercises || []),
  ];
  const totalEx = allEx.length;
  const doneEx = allEx.filter(ex => completed[ex.exercise_id] === true).length;
  const sparkline = Array.isArray(trendData.data?.sparkline) ? trendData.data.sparkline : [];
  const outingIdx = Array.isArray(trendData.data?.outing_day_indices) ? trendData.data.outing_day_indices : [];
  const streak = typeof trendData.data?.current_streak === 'number' ? trendData.data.current_streak : 0;
  const weekDots = Array.isArray(weekSummary.data?.week) ? weekSummary.data.week.map(d => !!d.flag_level) : [];
  const daysUntil = typeof flags.next_outing_days === 'number' ? flags.next_outing_days : null;
  const nextLabel = daysUntil == null ? null : daysUntil === 0 ? 'Today' : daysUntil === 1 ? 'Tomorrow' : new Date(Date.now() + daysUntil * 86400000).toLocaleDateString('en-US', { weekday: 'long' });

  return (
    <div style={{ paddingBottom: 20 }}>
      {/* Header */}
      <div style={{ background: '#5c1020', padding: '14px 16px 0' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 }}>
          {/* Left: name + role + flag */}
          <div>
            <div style={{ fontSize: 20, fontWeight: 800, color: '#fff', letterSpacing: -0.3 }}>{firstName}</div>
            <div style={{ fontSize: 10, color: '#e8a0aa', marginTop: 2, letterSpacing: 0.3 }}>
              {'UChicago Baseball \u00B7 '}<span style={{ color: '#fff', fontWeight: 600 }}>{roleLabel}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
              <FlagBadge level={flagLevel} />
              <span style={{ fontSize: 11, color: '#e8a0aa' }}>
                {'Day '}{flags.days_since_outing ?? '?'}{' of '}{profile?.rotation_length ?? 7}
              </span>
            </div>
          </div>
          {/* Right: arm feel big + sparkline */}
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 30, fontWeight: 800, lineHeight: 1, color: '#fff' }}>{armFeel != null ? String(armFeel) : '\u2013'}</div>
            <div style={{ fontSize: 8, textTransform: 'uppercase', letterSpacing: 1, color: '#e8a0aa', marginTop: 2 }}>Arm Feel</div>
            <div style={{ marginTop: 4 }}>
              <Sparkline data={sparkline} outingIndices={outingIdx} width={100} height={20} />
            </div>
          </div>
        </div>
        {/* Footer row */}
        <div style={{ borderTop: '0.5px solid rgba(255,255,255,0.12)', padding: '8px 0 12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            {nextLabel != null && <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)' }}>{'Next: '}<strong style={{ color: '#fff' }}>{String(nextLabel)}</strong></span>}
            {totalEx > 0 && <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)' }}>{String(totalEx) + ' exercises'}</span>}
            {sleepHours != null && <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)' }}>{'Sleep: '}<strong style={{ color: '#fff' }}>{sleepHours + 'h'}</strong></span>}
            {estDuration != null && <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)' }}>{'~'}<strong style={{ color: '#fff' }}>{estDuration + ' min'}</strong></span>}
          </div>
          <StreakBadge streak={streak} weekDots={weekDots} />
        </div>
      </div>

      {/* WHOOP Biometrics — data card or locked state */}
      {whoopData?.data?.linked && whoopData?.data?.data ? (
        <div style={{ padding: '8px 12px 0' }}>
          <WhoopCard data={whoopData.data.data} averages={whoopData.data.averages} />
        </div>
      ) : !isNewPitcher && whoopData?.data && !whoopData.data.linked ? (
        <div style={{ padding: '8px 12px 0' }}>
          <LockedState
            emoji={'\u231A'}
            title="Connect WHOOP for recovery data"
            description="See HRV, strain, and recovery alongside your daily plan"
            cta="Connect WHOOP"
            onCtaPress={() => navigate('/profile')}
          />
        </div>
      ) : null}

      {/* SessionProgress */}
      {totalEx > 0 && hasCheckedIn && (
        <div style={{ padding: '8px 12px 0' }}><SessionProgress doneCount={doneEx} totalCount={totalEx} /></div>
      )}

      {/* Check-in banner */}
      {!isNewPitcher && !hasCheckedIn && (
        <div onClick={() => navigate('/coach')} style={{ margin: '8px 12px 0', border: '1.5px solid #e8a0aa', background: 'rgba(92,16,32,0.05)', borderRadius: 12, padding: '10px 14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}>
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#2a1a18' }}>{'Morning check-in'}</div>
            <div style={{ fontSize: 10, color: '#b0a89e', marginTop: 2 }}>
              {morningBrief || "Check in to get today's personalized plan"}
            </div>
          </div>
          <div style={{ background: '#5c1020', borderRadius: 8, padding: '6px 14px', fontSize: 11, fontWeight: 700, color: '#fff' }}>{'Check In'}</div>
        </div>
      )}

      {/* Stale plan warning */}
      {isShowingStaleEntry && !selectedDate && (
        <div onClick={() => navigate('/coach')} style={{ margin: '8px 12px 0', background: '#fff3cd', border: '1px solid #ffc107', borderRadius: 8, padding: '8px 12px', fontSize: 11, color: '#856404', cursor: 'pointer' }}>
          {'Showing plan from '}{todayEntry.date}{'. Check in to get today\u2019s plan \u2192'}
        </div>
      )}

      {/* Partial check-in (data saved but plan generation failed) */}
      {checkinSavedButNoPlan && !selectedDate && (
        <div onClick={() => navigate('/coach')} style={{ margin: '8px 12px 0', background: '#d4edda', border: '1px solid #28a745', borderRadius: 8, padding: '8px 12px', fontSize: 11, color: '#155724', cursor: 'pointer' }}>
          {'Check-in saved. Plan generation had an issue \u2014 showing template exercises. Tap to retry \u2192'}
        </div>
      )}

      {/* WeekStrip */}
      {!isNewPitcher && (
        <div style={{ padding: '8px 12px 0' }}>
          <WeekStrip week={weekSummary.data?.week || []} selectedDate={selectedDate} onDayClick={(d) => setSelectedDate(prev => prev === d ? null : d)} />
        </div>
      )}

      {/* Morning brief — structured card or plain text fallback */}
      {hasCheckedIn && parsedBrief && (
        <div style={{ padding: '8px 12px 0' }}>
          <MorningBriefCard brief={parsedBrief} rotationDay={flags.days_since_outing} rotationLength={profile?.rotation_length} />
        </div>
      )}
      {hasCheckedIn && !parsedBrief && morningBrief && (
        <div style={{ padding: '4px 12px 0' }}>
          <p style={{ fontSize: 11, color: '#6b5f58', lineHeight: 1.6, fontStyle: 'italic', margin: 0 }}>{morningBrief}</p>
        </div>
      )}

      <div style={{ padding: '0 12px' }}>
        {isNewPitcher ? (
          <NewPitcherWelcome profile={profile} navigate={navigate} />
        ) : (
          <div>
            {isViewingPast && (
              <div style={{ textAlign: 'center', marginTop: 8 }}>
                <button onClick={() => setSelectedDate(null)} style={{ padding: '4px 14px', fontSize: 11, fontWeight: 600, background: '#5c1020', color: '#fff', border: 'none', borderRadius: 14, cursor: 'pointer' }}>{'Back to today'}</button>
              </div>
            )}
            <div style={{ marginTop: 12 }}>
              <DailyCard entry={displayEntry || todayEntry} exerciseMap={exerciseMap} slugMap={slugMap} pitcherId={pitcherId} initData={initData} readOnly={!!isViewingPast} />
            </div>
          </div>
        )}

        {/* Upcoming — collapsed by default */}
        {upcoming.data?.upcoming?.length > 0 && (
          <div style={{ marginTop: 12 }}>
            <button
              onClick={() => setShowUpcoming(!showUpcoming)}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '8px 14px', background: 'var(--color-white)', borderRadius: 12,
                border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: 600,
                color: 'var(--color-ink-secondary)',
              }}
            >
              <span>Upcoming Days</span>
              <span style={{ fontSize: 10, color: 'var(--color-ink-muted)' }}>{showUpcoming ? '\u25BE' : '\u25B8'}</span>
            </button>
            {showUpcoming && <UpcomingDays upcoming={upcoming.data.upcoming} exerciseMap={exerciseMap} />}
          </div>
        )}

        {upcoming.data?.upcoming?.length > 0 ? (
          <div style={{ marginTop: 12 }}>
            <ThrowingWeekPreview days={upcoming.data.upcoming} />
          </div>
        ) : !isNewPitcher && (
          <div style={{ marginTop: 12 }}>
            <LockedState
              emoji={'\uD83D\uDCC5'}
              title="Set your next outing"
              description={"I'll build your throwing week around your start date"}
              cta={"Tell Coach your next start \u2192"}
              onCtaPress={() => navigate('/coach')}
            />
          </div>
        )}

        <InsightsCard
          observations={progression?.observations}
          trendWeeks={Array.isArray(trendData.data?.weeks) ? trendData.data.weeks : []}
          narrative={narrativeData.data?.narrative}
          narrativeHeadline={narrativeData.data?.headline}
          narrativeWeek={narrativeData.data?.week_start}
        />
        {staffPulse.data && staffPulse.data.total_pitchers > 0 ? (
          <div style={{ marginTop: 12 }}><StaffPulse data={staffPulse.data} /></div>
        ) : !isNewPitcher && (
          <div style={{ marginTop: 12 }}>
            <LockedState
              emoji={'\uD83D\uDC65'}
              title="Your teammates will appear as they join"
              description="See who's checked in today and how the staff is tracking"
            />
          </div>
        )}
      </div>
    </div>
  );
}
