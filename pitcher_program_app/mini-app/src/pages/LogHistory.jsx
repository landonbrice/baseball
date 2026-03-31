import { useNavigate } from 'react-router-dom';
import { useAuth } from '../App';
import { useAppContext } from '../hooks/useChatState';
import { useApi } from '../hooks/useApi';
import SeasonTimeline from '../components/SeasonTimeline';
import SleepScatter from '../components/SleepScatter';

const MAROON = '#5c1020';
const YELLOW = '#BA7517';
const GREEN = '#1D9E75';
const INK = '#2a1a18';
const INK2 = '#6b5f58';
const MUTED = '#b0a89e';
const BG = '#f5f1eb';
const BORDER = '#e4dfd8';

function armFeelColor(feel) {
  if (feel >= 4) return GREEN;
  if (feel === 3) return YELLOW;
  return '#A32D2D';
}

function armFeelBadge(feel) {
  if (feel >= 4) return { bg: '#EAF3DE', color: '#27500A' };
  if (feel === 3) return { bg: '#FFF3D6', color: '#7A5A00' };
  return { bg: '#FDDEDE', color: '#8B1A1A' };
}

function formatDate(dateStr) {
  const d = new Date(dateStr + 'T12:00:00');
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function formatWeekLabel(weekStart) {
  const d = new Date(weekStart + 'T12:00:00');
  return 'Week of ' + d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export default function LogHistory() {
  const { pitcherId, initData } = useAuth();
  const navigate = useNavigate();
  const { addMessage } = useAppContext();

  const { data, loading } = useApi(
    pitcherId ? `/api/pitcher/${pitcherId}/season-summary` : null,
    initData,
  );

  function askCoach(prompt) {
    addMessage({ role: 'user', type: 'text', content: prompt });
    navigate('/coach');
  }

  if (loading) return <SeasonSkeleton />;
  if (!data) return <EmptyState />;

  const { pitcher_name, season_label, total_checkins, stats, timeline,
    rotation_signature, outings, upcoming_games, sleep_correlation,
    weekly_narratives, has_whoop } = data;

  return (
    <div style={{ background: BG, minHeight: '100vh', paddingBottom: 100 }}>

      {/* ── Header ── */}
      <div style={{ background: MAROON, padding: '14px 16px 12px' }}>
        <div style={{ fontSize: 20, fontWeight: 800, color: '#fff', letterSpacing: -0.4 }}>Season</div>
        <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.45)', marginTop: 2 }}>
          {pitcher_name} · {season_label} · {total_checkins} check-in{total_checkins !== 1 ? 's' : ''}
        </div>
      </div>

      <div style={{ height: 8 }} />

      {/* ── Summary stat cards ── */}
      <div style={{ padding: '0 12px 8px', display: 'flex', gap: 8 }}>
        <StatCard value={stats.avg_arm_feel ?? '—'} label="avg arm feel" color={MAROON} />
        <StatCard value={stats.avg_sleep ? `${stats.avg_sleep}h` : '—'} label="avg sleep" color={INK} />
        <StatCard value={stats.total_starts} label={stats.total_starts === 1 ? 'start logged' : 'starts logged'} color={INK} />
        <StatCard value={stats.current_streak} label="day streak" color={GREEN} />
      </div>

      {/* ── Season arm feel timeline ── */}
      {timeline.length >= 2 && (
        <Card label="Season arm feel timeline">
          <SeasonTimeline timeline={timeline} hasWhoop={has_whoop} />
        </Card>
      )}

      {/* ── Rotation signature ── */}
      {rotation_signature ? (
        <Card label="Your rotation signature">
          <div style={{ fontSize: 10, color: INK2, lineHeight: 1.5, marginBottom: 10 }}>
            Average arm feel per day of your rotation, across all starts this season.
          </div>
          <RotationBars
            bars={rotation_signature.bars}
            bestDay={rotation_signature.best_day}
            lowDays={rotation_signature.low_days}
          />
          {rotation_signature.insight && (
            <div style={{
              background: '#fdf8f8', borderRadius: 8, padding: '8px 10px',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 8,
            }}>
              <div style={{ fontSize: 10, color: '#4a2228', lineHeight: 1.4 }}>{rotation_signature.insight}</div>
              {rotation_signature.ask_prompt && (
                <div
                  onClick={() => askCoach(rotation_signature.ask_prompt)}
                  style={{ fontSize: 9, color: MAROON, fontWeight: 700, cursor: 'pointer', whiteSpace: 'nowrap', marginLeft: 8 }}
                >
                  Ask ↗
                </div>
              )}
            </div>
          )}
        </Card>
      ) : (
        <LockedCard label="Your rotation signature" hint="Unlocks after a few check-ins across your rotation cycle." />
      )}

      {/* ── Starts this season ── */}
      {(outings.length > 0 || (upcoming_games && upcoming_games.length > 0)) ? (
        <Card label="Starts this season">
          {/* Upcoming games (not yet logged) — show next 3 */}
          {upcoming_games && upcoming_games.slice(0, 3).map(g => (
            <UpcomingGameCard key={g.game_date + g.opponent} game={g} />
          ))}
          {/* Logged outings */}
          {outings.map((o, idx) => (
            <OutingCard
              key={o.date}
              outing={o}
              opacity={idx === 0 ? 1 : idx === 1 ? 0.75 : 0.6}
              isLast={idx === outings.length - 1 && !(upcoming_games && upcoming_games.length)}
              onAsk={askCoach}
            />
          ))}
        </Card>
      ) : (
        <LockedCard label="Starts this season" hint="Log your first outing with /outing in the bot to see recovery curves here." />
      )}

      {/* ── Weekly coaching notes ── */}
      {weekly_narratives.length > 0 ? (
        <Card label="Weekly coaching notes">
          {weekly_narratives.map((n, idx) => (
            <div
              key={n.week_start}
              style={{
                borderLeft: idx === 0 ? `3px solid ${MAROON}` : `2px solid ${BORDER}`,
                borderRadius: '0 8px 8px 0',
                background: idx === 0 ? 'rgba(92,16,32,0.04)' : 'transparent',
                padding: idx === 0 ? '10px 12px' : '8px 10px',
                marginBottom: idx < weekly_narratives.length - 1 ? 10 : 0,
                opacity: idx === 0 ? 1 : idx === 1 ? 0.7 : 0.5,
              }}
            >
              <div style={{
                fontSize: idx === 0 ? 10 : 9, fontWeight: 700,
                color: idx === 0 ? INK : INK2, marginBottom: idx === 0 ? 3 : 2,
              }}>
                {formatWeekLabel(n.week_start)}
              </div>
              <div style={{ fontSize: 10, color: idx === 0 ? '#4a2228' : INK2, lineHeight: 1.65, fontStyle: 'italic' }}>
                "{n.narrative}"
              </div>
            </div>
          ))}
        </Card>
      ) : (
        <LockedCard label="Weekly coaching notes" hint="Your first coaching narrative generates Sunday evening after a week of check-ins." />
      )}

      {/* ── Sleep vs arm feel ── */}
      {sleep_correlation && sleep_correlation.points.length >= 5 ? (
        <Card label="Sleep vs arm feel" last>
          <div style={{ fontSize: 10, color: INK2, lineHeight: 1.5, marginBottom: 10 }}>
            {sleep_correlation.insight}
          </div>
          <SleepScatter points={sleep_correlation.points} />
          {sleep_correlation.ask_prompt && (
            <div
              onClick={() => askCoach(sleep_correlation.ask_prompt)}
              style={{
                marginTop: 10, background: BG, borderRadius: 8, padding: '7px 10px 7px 10px',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                cursor: 'pointer', border: `0.5px solid ${BORDER}`,
              }}
            >
              <span style={{ fontSize: 10, color: MAROON, fontWeight: 700 }}>Ask coach to analyze this pattern</span>
              <span style={{ color: '#e8a0aa', fontSize: 13 }}>↗</span>
            </div>
          )}
        </Card>
      ) : (
        <LockedCard label="Sleep vs arm feel" hint={`Need ${5 - (sleep_correlation?.points?.length || 0)} more check-ins to map sleep → arm feel patterns.`} last />
      )}
    </div>
  );
}

/* ── Sub-components ── */

function Card({ label, children, last }) {
  return (
    <div style={{
      background: '#fff', borderRadius: 12, padding: 14,
      margin: `0 12px ${last ? 20 : 10}px`,
    }}>
      <div style={{
        fontSize: 9, fontWeight: 700, color: MAROON,
        letterSpacing: '0.07em', textTransform: 'uppercase', marginBottom: 10,
      }}>
        {label}
      </div>
      {children}
    </div>
  );
}

function LockedCard({ label, hint, last }) {
  return (
    <div style={{
      background: '#fff', borderRadius: 12, padding: 14,
      margin: `0 12px ${last ? 20 : 10}px`, opacity: 0.55,
    }}>
      <div style={{
        fontSize: 9, fontWeight: 700, color: MAROON,
        letterSpacing: '0.07em', textTransform: 'uppercase', marginBottom: 6,
      }}>
        {label}
      </div>
      <div style={{ fontSize: 10, color: INK2, lineHeight: 1.5 }}>{hint}</div>
    </div>
  );
}

function StatCard({ value, label, color }) {
  return (
    <div style={{
      flex: 1, background: '#fff', borderRadius: 10, padding: '10px 12px', textAlign: 'center',
    }}>
      <div style={{ fontSize: 20, fontWeight: 800, color }}>{value}</div>
      <div style={{ fontSize: 8, color: MUTED, marginTop: 1 }}>{label}</div>
    </div>
  );
}

function RotationBars({ bars, bestDay, lowDays }) {
  const validBars = bars.filter(b => b.avg_feel !== null);
  if (validBars.length === 0) return null;
  const maxFeel = Math.max(...validBars.map(b => b.avg_feel));
  const maxH = 52;

  return (
    <div style={{ display: 'flex', gap: 3, alignItems: 'flex-end', height: 60, marginBottom: 6 }}>
      {bars.map(b => {
        if (b.avg_feel === null) {
          return (
            <div key={b.day} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}>
              <div style={{ fontSize: 8, color: MUTED }}>—</div>
              <div style={{ width: '100%', background: '#eee', borderRadius: '3px 3px 0 0', height: 4 }} />
              <div style={{ fontSize: 8, color: MUTED }}>{b.day}</div>
            </div>
          );
        }
        const isBest = b.day === bestDay;
        const isLow = lowDays.includes(b.day);
        const barColor = isLow ? YELLOW : MAROON;
        const h = (b.avg_feel / maxFeel) * maxH;
        const opacity = isBest ? 1 : isLow ? 0.7 : 0.65 + (b.avg_feel / maxFeel) * 0.3;

        return (
          <div key={b.day} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}>
            <div style={{ fontSize: 8, fontWeight: isBest ? 800 : 700, color: barColor }}>{b.avg_feel}</div>
            <div style={{
              width: '100%', background: barColor, borderRadius: '3px 3px 0 0',
              height: h, opacity,
              border: isBest ? `1.5px solid ${MAROON}` : 'none',
            }} />
            <div style={{
              fontSize: 8,
              color: isBest ? MAROON : MUTED,
              fontWeight: isBest ? 700 : 400,
            }}>
              {b.day}{isBest ? ' ★' : ''}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function OutingCard({ outing, opacity, isLast, onAsk }) {
  const badge = armFeelBadge(outing.post_arm_feel);

  return (
    <div style={{
      borderBottom: isLast ? 'none' : `0.5px solid ${BORDER}`,
      paddingBottom: isLast ? 0 : 10,
      marginBottom: isLast ? 0 : 10,
      opacity,
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 6 }}>
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, color: INK }}>
            {formatDate(outing.date)}{outing.opponent ? ` · ${outing.home_away === 'away' ? '@ ' : 'vs. '}${outing.opponent}` : ''}
          </div>
          <div style={{ fontSize: 9, color: MUTED, marginTop: 1 }}>
            {outing.pitch_count ? `${outing.pitch_count} pitches · ` : ''}
            post-arm {outing.post_arm_feel}/5
          </div>
        </div>
        {outing.post_arm_feel != null && (
          <div style={{
            background: badge.bg, borderRadius: 6, padding: '2px 7px',
            fontSize: 9, fontWeight: 700, color: badge.color,
          }}>
            {outing.post_arm_feel}/5
          </div>
        )}
      </div>

      {outing.recovery.length > 0 && (
        <>
          <div style={{ fontSize: 9, color: INK2, marginBottom: 6 }}>Recovery curve after outing:</div>
          <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
            {outing.recovery.map((r, idx) => (
              <RecoveryDot key={r.day} r={r} isLast={idx === outing.recovery.length - 1} />
            ))}
          </div>
        </>
      )}

      {outing.insight && (
        <div style={{ marginTop: 8, fontSize: 9, color: INK2, fontStyle: 'italic' }}>{outing.insight}</div>
      )}

      {opacity === 1 && outing.ask_prompt && (
        <div
          onClick={() => onAsk(outing.ask_prompt)}
          style={{ marginTop: 6, fontSize: 9, color: MAROON, fontWeight: 700, cursor: 'pointer' }}
        >
          Ask coach about this start ↗
        </div>
      )}
    </div>
  );
}

function RecoveryDot({ r, isLast }) {
  const color = armFeelColor(r.arm_feel);
  return (
    <>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: 9, fontWeight: 700, color }}>{r.arm_feel}</div>
        <div style={{ width: 28, height: 3, background: color, borderRadius: 2, margin: '2px auto' }} />
        <div style={{ fontSize: 8, color: MUTED }}>{r.day}</div>
      </div>
      {!isLast && <div style={{ flex: 1, height: 1, background: BORDER }} />}
    </>
  );
}

function UpcomingGameCard({ game }) {
  return (
    <div style={{
      borderBottom: `0.5px solid ${BORDER}`,
      paddingBottom: 10, marginBottom: 10, opacity: 0.5,
      border: `1px dashed ${BORDER}`, borderRadius: 8, padding: '8px 10px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, color: INK2 }}>
            {formatDate(game.game_date)} · {game.home_away === 'away' ? '@ ' : 'vs. '}{game.opponent}
          </div>
          {game.start_time && (
            <div style={{ fontSize: 9, color: MUTED, marginTop: 1 }}>{game.start_time}</div>
          )}
        </div>
        <div style={{ fontSize: 8, color: MUTED, fontWeight: 600, textTransform: 'uppercase' }}>upcoming</div>
      </div>
    </div>
  );
}

function SeasonSkeleton() {
  return (
    <div style={{ background: BG, minHeight: '100vh' }}>
      <div style={{ background: MAROON, padding: '14px 16px 20px' }}>
        <div style={{ width: 80, height: 20, background: 'rgba(255,255,255,0.15)', borderRadius: 6 }} />
        <div style={{ width: 160, height: 10, background: 'rgba(255,255,255,0.08)', borderRadius: 4, marginTop: 6 }} />
      </div>
      <div style={{ padding: '16px 12px', display: 'flex', gap: 8 }}>
        {[1,2,3,4].map(i => (
          <div key={i} style={{ flex: 1, background: '#fff', borderRadius: 10, padding: 14, height: 56 }} />
        ))}
      </div>
      {[200, 120, 160].map((h, i) => (
        <div key={i} style={{ background: '#fff', borderRadius: 12, margin: '0 12px 10px', height: h }} />
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <div style={{ background: BG, minHeight: '100vh' }}>
      <div style={{ background: MAROON, padding: '14px 16px 12px' }}>
        <div style={{ fontSize: 20, fontWeight: 800, color: '#fff' }}>Season</div>
      </div>
      <div style={{ padding: '40px 24px', textAlign: 'center' }}>
        <div style={{ fontSize: 13, color: INK2, lineHeight: 1.6 }}>
          No check-in data yet. Start with <span style={{ fontWeight: 700 }}>/checkin</span> in the bot to see your season trends here.
        </div>
      </div>
    </div>
  );
}
