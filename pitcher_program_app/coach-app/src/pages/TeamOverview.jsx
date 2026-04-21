import { useEffect, useMemo, useState } from 'react'
import { useCoachApi } from '../hooks/useApi'
import { TODAY } from '../utils/formatToday'
import Masthead from '../components/shell/Masthead'
import Scoreboard from '../components/shell/Scoreboard'
import EditorialState from '../components/shell/EditorialState'
import TeamLede from '../components/team-overview/TeamLede'
import HeroCard from '../components/team-overview/HeroCard'
import CompactCard from '../components/team-overview/CompactCard'
import PendingStrip from '../components/team-overview/PendingStrip'
import PlayerSlideOver from '../components/PlayerSlideOver'

const REFRESH_INTERVAL_MS = 90_000

function formatWeek(trainingPhase) {
  if (!trainingPhase) return undefined
  return trainingPhase
}

function formatDateShort(iso) {
  if (!iso) return '—'
  const d = new Date(iso + 'T12:00:00')
  return d.toLocaleDateString('en-US', { weekday: 'short', timeZone: 'America/Chicago' })
}

function buildScoreboardCells(data) {
  const { compliance, roster } = data || {}
  if (!compliance || !roster) return null

  const g = compliance.flags?.green ?? 0
  const y = compliance.flags?.yellow ?? 0
  const r = compliance.flags?.red ?? 0

  const afVals = roster.map(p => p.af_7d).filter(v => typeof v === 'number')
  const afMean = afVals.length > 0 ? Math.round((afVals.reduce((a, b) => a + b, 0) / afVals.length) * 10) / 10 : null

  const bp = roster.filter(p => p.today?.day_focus === 'bullpen').length
  const sim = roster.filter(p => p.today?.day_focus === 'throw').length
  const recov = roster.filter(p => p.today?.day_focus === 'recovery').length

  const upcoming = roster
    .filter(p => p.next_scheduled_start)
    .sort((a, b) => a.next_scheduled_start.localeCompare(b.next_scheduled_start))
  const nextStart = upcoming[0]

  const outstanding = Math.max(0, (compliance.total || 0) - (compliance.checked_in_today || 0))

  return [
    {
      label: 'Check-ins',
      value: `${compliance.checked_in_today}/${compliance.total}`,
      sub: outstanding > 0 ? `${outstanding} outstanding` : 'all in',
    },
    {
      label: 'Flags',
      value: (
        <>
          <span className="text-forest">{g}</span>
          <span> · </span>
          <span className="text-amber">{y}</span>
          <span> · </span>
          <span className="text-crimson">{r}</span>
        </>
      ),
      sub: 'G · Y · R',
    },
    {
      label: 'Avg Arm Feel',
      value: afMean != null ? afMean.toFixed(1) : null,
      sub: afVals.length > 0 ? `${afVals.length} logged` : '—',
    },
    {
      label: "Today's Work",
      value: `${bp} bp`,
      sub: `${sim} sim · ${recov} recov`,
    },
    {
      label: 'Next Start',
      value: nextStart ? formatDateShort(nextStart.next_scheduled_start) : null,
      sub: nextStart ? nextStart.name : '—',
    },
  ]
}

function partitionRoster(roster) {
  const flagged = []
  const pending = []
  const onTrack = []
  for (const p of roster) {
    const isPending = p.today_status !== 'checked_in'
    if (p.flag_level === 'red' || p.flag_level === 'yellow') {
      flagged.push(p)
    } else if (isPending) {
      pending.push({
        pitcher_id: p.pitcher_id,
        name: p.name,
        hours_since_last: null,
      })
    } else {
      onTrack.push(p)
    }
  }
  flagged.sort((a, b) => {
    if (a.flag_level !== b.flag_level) return a.flag_level === 'red' ? -1 : 1
    return (a.af_7d ?? 10) - (b.af_7d ?? 10)
  })
  return { flagged, pending, onTrack }
}

export default function TeamOverview() {
  const { data, loading, error, refetch } = useCoachApi('/api/coach/team/overview')
  const [selectedPlayer, setSelectedPlayer] = useState(null)

  useEffect(() => {
    let intervalId = null
    const tick = () => {
      if (document.visibilityState === 'visible') refetch()
    }
    const start = () => {
      if (intervalId == null) intervalId = setInterval(tick, REFRESH_INTERVAL_MS)
    }
    const stop = () => {
      if (intervalId != null) { clearInterval(intervalId); intervalId = null }
    }
    if (document.visibilityState === 'visible') start()
    const onVis = () => (document.visibilityState === 'visible' ? start() : stop())
    document.addEventListener('visibilitychange', onVis)
    return () => { stop(); document.removeEventListener('visibilitychange', onVis) }
  }, [refetch])

  const stub = (
    <Masthead
      kicker="Chicago · Pitching Staff"
      title="Team Overview"
      date={TODAY}
      week={formatWeek(data?.team?.training_phase)}
    />
  )

  const sections = useMemo(() => (data ? partitionRoster(data.roster || []) : null), [data])
  const scoreboardCells = useMemo(() => (data ? buildScoreboardCells(data) : null), [data])

  if (loading && !data) {
    return (
      <>
        {stub}
        <div className="p-6">
          <EditorialState type="loading" copy="Gathering the morning check-ins…" />
        </div>
      </>
    )
  }
  if (error) {
    return (
      <>
        {stub}
        <div className="p-6">
          <EditorialState type="error" copy={error} retry={refetch} />
        </div>
      </>
    )
  }
  if (!data || !sections || !scoreboardCells) {
    return <>{stub}<div className="p-6" /></>
  }
  if ((data.roster || []).length === 0) {
    return (
      <>
        {stub}
        <div className="p-6">
          <EditorialState type="empty" copy="No pitchers on this staff yet. Set up your roster in the admin area." />
        </div>
      </>
    )
  }

  return (
    <>
      {stub}
      <Scoreboard cells={scoreboardCells} />
      <div className="px-6 py-4 space-y-6">
        <TeamLede roster={data.roster} compliance={data.compliance} />

        {sections.flagged.length > 0 && (
          <section>
            <h2 className="font-ui font-semibold uppercase text-[10px] tracking-[0.2em] text-maroon mb-2">
              Needs Attention
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
              {sections.flagged.slice(0, 6).map(p => (
                <HeroCard key={p.pitcher_id} pitcher={p} onOpen={setSelectedPlayer} />
              ))}
            </div>
          </section>
        )}

        {sections.onTrack.length > 0 && (
          <section>
            <h2 className="font-ui font-semibold uppercase text-[10px] tracking-[0.2em] text-maroon mb-2">
              On Track
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-2.5">
              {sections.onTrack.map(p => (
                <CompactCard key={p.pitcher_id} pitcher={p} onOpen={setSelectedPlayer} />
              ))}
            </div>
          </section>
        )}

        <PendingStrip pending={sections.pending} nudgeEnabled={true} />
      </div>

      <PlayerSlideOver pitcherId={selectedPlayer} onClose={() => setSelectedPlayer(null)} />
    </>
  )
}
