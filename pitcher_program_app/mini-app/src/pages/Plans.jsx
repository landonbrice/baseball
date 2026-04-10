import { useAuth } from '../App';
import { useApi } from '../hooks/useApi';
import ProgramHero from '../components/ProgramHero';
import WeekArc from '../components/WeekArc';
import ScheduleCard from '../components/ScheduleCard';
import TodayDetailCard from '../components/TodayDetailCard';
import ProgramHistoryTimeline from '../components/ProgramHistoryTimeline';

export default function Programs() {
  const { pitcherId, initData } = useAuth();
  const { data, loading, refetch } = useApi(
    pitcherId ? `/api/pitcher/${pitcherId}/program` : null,
    initData
  );
  const { data: historyData } = useApi(
    pitcherId ? `/api/pitcher/${pitcherId}/program/history` : null,
    initData
  );

  async function handleAddThrow(throwData) {
    const resp = await fetch(`/api/pitcher/${pitcherId}/scheduled-throw`, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'X-Telegram-Init-Data': initData || '',
      },
      body: JSON.stringify(throwData),
    });
    if (!resp.ok) {
      console.error('Failed to add throw:', await resp.text());
      return;
    }
    refetch();
  }

  if (loading) {
    return (
      <div style={{ padding: 16 }}>
        <div style={{ height: 24, background: 'var(--color-cream-border)', borderRadius: 6, width: '40%', marginBottom: 16 }} />
        <div style={{ height: 120, background: 'var(--color-cream-border)', borderRadius: 16, marginBottom: 16 }} />
        <div style={{ height: 200, background: 'var(--color-cream-border)', borderRadius: 16 }} />
      </div>
    );
  }

  if (!data?.program) {
    return (
      <div style={{ padding: 24, textAlign: 'center', color: 'var(--color-ink-muted)' }}>
        No active program. Ask your coach to set one up.
      </div>
    );
  }

  return (
    <div style={{ paddingBottom: 100 }}>
      <div style={{ background: 'var(--color-maroon)', padding: '14px 16px 12px' }}>
        <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--color-rose-blush)', textTransform: 'uppercase', letterSpacing: 1.5 }}>
          My Program
        </div>
        <div style={{ fontSize: 19, fontWeight: 700, color: '#fff', marginTop: 4, letterSpacing: -0.3 }}>
          {data.program.name}
        </div>
      </div>
      <ProgramHero program={data.program} />
      <WeekArc arc={data.week_arc} onAddThrow={handleAddThrow} />
      <ScheduleCard schedule={data.schedule} />
      <TodayDetailCard today={data.today_detail} />
      <ProgramHistoryTimeline programs={historyData?.programs} />
    </div>
  );
}
