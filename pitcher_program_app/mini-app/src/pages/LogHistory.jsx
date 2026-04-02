import { useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../App';
import { useAppContext } from '../hooks/useChatState';
import { useApi } from '../hooks/useApi';
import SeasonTimeline from '../components/SeasonTimeline';
import SleepScatter from '../components/SleepScatter';
import WhoopWeekCard from '../components/WhoopWeekCard';
import RecoveryFingerprint from '../components/RecoveryFingerprint';
import {
  Chart, BarElement, BarController, LinearScale, CategoryScale, Tooltip,
} from 'chart.js';

Chart.register(BarElement, BarController, LinearScale, CategoryScale, Tooltip);

const MAROON = '#5c1020';
const YELLOW = '#BA7517';
const GREEN = '#1D9E75';
const INK = '#2a1a18';
const INK2 = '#6b5f58';
const MUTED = '#b0a89e';
const BG = '#f5f1eb';
const BORDER = '#e4dfd8';

function formatDate(dateStr) {
  const d = new Date(dateStr + 'T12:00:00');
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
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

  const { pitcher_name, season_label, stats, timeline, timeline_insight,
    rotation_signature, outings, upcoming_games, fingerprint_insight,
    sleep_correlation, has_whoop, whoop_week } = data;

  return (
    <div style={{ background: BG, minHeight: '100vh', paddingBottom: 100 }}>

      {/* ── Header ── */}
      <div style={{ background: MAROON, padding: '12px 16px 11px' }}>
        <div style={{ fontSize: 19, fontWeight: 800, color: '#fff', letterSpacing: -0.4 }}>📊 Season</div>
        <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)', marginTop: 2 }}>
          {pitcher_name} · {season_label}
        </div>
      </div>

      {/* ── Stat cards ── */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
        gap: 6, padding: '10px 12px 0',
      }}>
        <StatCard value={stats.avg_arm_feel ?? '—'} label="avg arm" color={MAROON} emoji="💪" />
        <StatCard value={stats.avg_sleep ? `${stats.avg_sleep}h` : '—'} label="avg sleep" color={INK} emoji="😴" />
        <StatCard value={stats.total_starts} label="starts" color={INK} emoji="⚾" />
        <StatCard value={stats.current_streak} label="streak" color={GREEN} emoji="🔥" />
      </div>

      <div style={{ height: 10 }} />

      {/* ── Arm feel + recovery ── */}
      {timeline.length >= 2 && (
        <Card label="📈 Arm Feel + Recovery">
          <SeasonTimeline timeline={timeline} hasWhoop={has_whoop} />
          {timeline_insight && (
            <div className="ins" style={{
              marginTop: 10, background: '#fdf8f8', borderRadius: 8,
              padding: '9px 11px', fontSize: 11, color: '#4a2228', lineHeight: 1.55,
            }}>
              {timeline_insight}
            </div>
          )}
          {timeline_insight && (
            <AskLink onClick={() => askCoach('Tell me about the relationship between my WHOOP recovery and arm feel this season.')}>
              Ask coach about recovery pattern ↗
            </AskLink>
          )}
        </Card>
      )}

      {/* ── WHOOP weekly card ── */}
      {has_whoop && whoop_week && (
        <WhoopWeekCard data={whoop_week} onAsk={askCoach} />
      )}

      {/* ── Rotation signature ── */}
      {rotation_signature ? (
        <Card label="🔄 Your Rotation Signature">
          <div style={{ fontSize: 11, color: INK2, marginBottom: 9, lineHeight: 1.5 }}>
            Average arm feel per rotation day, computed across all {stats.total_starts || ''} start{stats.total_starts !== 1 ? 's' : ''}.
          </div>
          <RotationChart bars={rotation_signature.bars} />
          {rotation_signature.insight && (
            <div style={{
              marginTop: 10, background: '#fdf8f8', borderRadius: 8,
              padding: '9px 11px', fontSize: 11, color: '#4a2228', lineHeight: 1.55,
            }}>
              {rotation_signature.insight}
            </div>
          )}
          {rotation_signature.ask_prompt && (
            <AskLink onClick={() => askCoach(rotation_signature.ask_prompt)}>
              {rotation_signature.ask_prompt} ↗
            </AskLink>
          )}
        </Card>
      ) : (
        <LockedCard label="🔄 Your Rotation Signature" hint="Unlocks after a few check-ins across your rotation cycle." />
      )}

      {/* ── Outing recovery fingerprint ── */}
      {(outings.length > 0 || (upcoming_games && upcoming_games.length > 0)) ? (
        <Card label="🩺 Outing Recovery Fingerprint">
          {outings.length > 0 && (
            <>
              <div style={{ fontSize: 11, color: INK2, marginBottom: 9, lineHeight: 1.5 }}>
                Arm feel in the days following each start. Your personal recovery curve.
              </div>
              <RecoveryFingerprint outings={outings} />
              {fingerprint_insight && (
                <div style={{
                  marginTop: 10, background: '#fdf8f8', borderRadius: 8,
                  padding: '9px 11px', fontSize: 11, color: '#4a2228', lineHeight: 1.55,
                }}>
                  {fingerprint_insight}
                </div>
              )}
              <AskLink onClick={() => askCoach('How should pitch count affect my recovery plan?')}>
                How should pitch count affect my recovery plan? ↗
              </AskLink>
            </>
          )}
          {!outings.length && (
            <div style={{ fontSize: 11, color: INK2, lineHeight: 1.5, marginBottom: 10, opacity: 0.6 }}>
              Log your first outing with /outing to see your recovery fingerprint.
            </div>
          )}
          {/* Upcoming games */}
          {upcoming_games && upcoming_games.slice(0, 3).map(g => (
            <UpcomingGameCard key={g.game_date + g.opponent} game={g} />
          ))}
        </Card>
      ) : (
        <LockedCard label="🩺 Outing Recovery Fingerprint" hint="Log your first outing with /outing in the bot to see recovery curves here." />
      )}

      {/* ── Sleep vs arm feel ── */}
      {sleep_correlation && sleep_correlation.points.length >= 5 ? (
        <Card label="😴 Sleep vs Arm Feel" last>
          <div style={{ fontSize: 11, color: INK2, lineHeight: 1.5, marginBottom: 9 }}>
            {sleep_correlation.insight}
          </div>
          <SleepScatter points={sleep_correlation.points} />
          <AskLink onClick={() => askCoach(sleep_correlation.ask_prompt)}>
            Analyze this pattern ↗
          </AskLink>
        </Card>
      ) : (
        <LockedCard label="😴 Sleep vs Arm Feel" hint={`Need ${5 - (sleep_correlation?.points?.length || 0)} more check-ins to map sleep → arm feel patterns.`} last />
      )}
    </div>
  );
}

/* ── Shared sub-components ── */

function Card({ label, children, last }) {
  return (
    <div style={{
      background: '#fff', borderRadius: 12, padding: 14,
      margin: `0 12px ${last ? 16 : 10}px`,
    }}>
      <div style={{
        fontSize: 11, fontWeight: 700, color: MAROON,
        letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 10,
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
      margin: `0 12px ${last ? 16 : 10}px`, opacity: 0.55,
    }}>
      <div style={{
        fontSize: 11, fontWeight: 700, color: MAROON,
        letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 6,
      }}>
        {label}
      </div>
      <div style={{ fontSize: 11, color: INK2, lineHeight: 1.5 }}>{hint}</div>
    </div>
  );
}

function StatCard({ value, label, color, emoji }) {
  return (
    <div style={{
      background: '#fff', borderRadius: 9, padding: '8px 4px', textAlign: 'center',
    }}>
      {emoji && <div style={{ fontSize: 16, marginBottom: 4 }}>{emoji}</div>}
      <div style={{ fontSize: 17, fontWeight: 800, color, lineHeight: 1 }}>{value}</div>
      <div style={{ fontSize: 11, color: MUTED, marginTop: 2 }}>{label}</div>
    </div>
  );
}

function AskLink({ onClick, children }) {
  return (
    <div onClick={onClick} style={{
      marginTop: 9, display: 'flex', alignItems: 'center',
      justifyContent: 'space-between', cursor: 'pointer',
    }}>
      <span style={{ fontSize: 11, color: MAROON, fontWeight: 700 }}>{children}</span>
      <span />
    </div>
  );
}

function RotationChart({ bars }) {
  const canvasRef = useRef(null);
  const chartRef = useRef(null);

  const validBars = bars.filter(b => b.avg_feel !== null);

  useEffect(() => {
    if (!canvasRef.current || validBars.length === 0) return;
    if (chartRef.current) chartRef.current.destroy();

    const labels = bars.map(b => 'D' + b.day);
    const data = bars.map(b => b.avg_feel);
    const colors = bars.map(b => {
      if (b.avg_feel === null) return '#eee';
      if (b.avg_feel <= 3.5) return YELLOW;
      if (b.avg_feel <= 4) return 'rgba(92,16,32,0.5)';
      return MAROON;
    });

    chartRef.current = new Chart(canvasRef.current, {
      type: 'bar',
      data: {
        labels,
        datasets: [{ data, backgroundColor: colors, borderRadius: 4, barPercentage: 0.7 }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: ctx => 'Avg arm: ' + (ctx.parsed.y?.toFixed(1) ?? '—') + '/5' } },
        },
        scales: {
          y: {
            min: 1, max: 5,
            ticks: { stepSize: 1, font: { size: 11 }, color: '#b0a89e', callback: v => v + '/5' },
            grid: { color: 'rgba(0,0,0,0.04)' },
            border: { display: false },
          },
          x: {
            ticks: { font: { size: 11, weight: 'bold' }, color: MAROON, autoSkip: false },
            grid: { display: false },
            border: { display: false },
          },
        },
      },
    });

    return () => { if (chartRef.current) chartRef.current.destroy(); };
  }, [bars]);

  if (validBars.length === 0) return null;

  return (
    <div style={{ position: 'relative', width: '100%', height: 140 }}>
      <canvas ref={canvasRef} />
    </div>
  );
}

function UpcomingGameCard({ game }) {
  return (
    <div style={{
      border: `1px dashed ${BORDER}`, borderRadius: 8, padding: '8px 10px',
      marginTop: 8, opacity: 0.5,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, color: INK2 }}>
            {formatDate(game.game_date)} · {game.home_away === 'away' ? '@ ' : 'vs. '}{game.opponent}
          </div>
          {game.start_time && (
            <div style={{ fontSize: 11, color: MUTED, marginTop: 1 }}>{game.start_time}</div>
          )}
        </div>
        <div style={{ fontSize: 9, color: MUTED, fontWeight: 600, textTransform: 'uppercase' }}>upcoming</div>
      </div>
    </div>
  );
}

function SeasonSkeleton() {
  return (
    <div style={{ background: BG, minHeight: '100vh' }}>
      <div style={{ background: MAROON, padding: '12px 16px 18px' }}>
        <div style={{ width: 80, height: 18, background: 'rgba(255,255,255,0.15)', borderRadius: 6 }} />
        <div style={{ width: 140, height: 10, background: 'rgba(255,255,255,0.08)', borderRadius: 4, marginTop: 6 }} />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 6, padding: '10px 12px' }}>
        {[1,2,3,4].map(i => (
          <div key={i} style={{ background: '#fff', borderRadius: 9, height: 52 }} />
        ))}
      </div>
      {[200, 140, 160, 120].map((h, i) => (
        <div key={i} style={{ background: '#fff', borderRadius: 12, margin: '0 12px 10px', height: h }} />
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <div style={{ background: BG, minHeight: '100vh' }}>
      <div style={{ background: MAROON, padding: '12px 16px 11px' }}>
        <div style={{ fontSize: 19, fontWeight: 800, color: '#fff' }}>📊 Season</div>
      </div>
      <div style={{ padding: '40px 24px', textAlign: 'center' }}>
        <div style={{ fontSize: 13, color: INK2, lineHeight: 1.6 }}>
          No check-in data yet. Start with <span style={{ fontWeight: 700 }}>/checkin</span> in the bot to see your season trends here.
        </div>
      </div>
    </div>
  );
}
