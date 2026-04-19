import { useState } from 'react'
import { useCoachApi } from '../hooks/useApi'
import ComplianceRing from '../components/ComplianceRing'
import RosterTable from '../components/RosterTable'
import PlayerSlideOver from '../components/PlayerSlideOver'
import Masthead from '../components/shell/Masthead'
import EditorialState from '../components/shell/EditorialState'
import { TODAY } from '../utils/formatToday'

export default function TeamOverview() {
  const { data, loading, error, refetch } = useCoachApi('/api/coach/team/overview')
  const [selectedPlayer, setSelectedPlayer] = useState(null)

  const stub = (
    <Masthead kicker="Chicago · Pitching Staff" title="Team Overview" date={TODAY} />
  )

  if (loading) return <>{stub}<div className="p-6"><EditorialState type="loading" copy="Gathering the morning check-ins…" /></div></>
  if (error)   return <>{stub}<div className="p-6"><EditorialState type="error" copy={error} retry={refetch} /></div></>
  if (!data)   return <>{stub}<div className="p-6" /></>

  const { team, compliance, roster, active_blocks, insights_summary } = data

  return (
    <>
      {stub}
      <div className="p-6">
        <div className="flex items-start gap-6">
          {/* Left sidebar cards */}
          <div className="w-56 flex-shrink-0 space-y-4">
            {/* Compliance */}
            <div className="bg-white rounded-lg border border-cream-dark p-4 flex flex-col items-center relative">
              <p className="text-xs text-subtle mb-2">Today's Check-ins</p>
              <ComplianceRing checkedIn={compliance.checked_in_today} total={compliance.total} />
              <div className="flex gap-3 mt-3 text-xs">
                <span style={{ color: '#2d5a3d' }}>{compliance.flags.green} green</span>
                <span style={{ color: '#d4a017' }}>{compliance.flags.yellow} yellow</span>
                <span style={{ color: '#c0392b' }}>{compliance.flags.red} red</span>
              </div>
            </div>

            {/* Schedule */}
            <div className="bg-white rounded-lg border border-cream-dark p-4">
              <p className="text-xs text-subtle mb-1">Today</p>
              <p className="text-sm font-medium text-charcoal">{team.today_schedule_summary}</p>
            </div>

            {/* Active Blocks */}
            {active_blocks.length > 0 && (
              <div className="bg-white rounded-lg border border-cream-dark p-4">
                <p className="text-xs text-subtle mb-1">Active Programs</p>
                {active_blocks.map(b => (
                  <p key={b.block_id} className="text-sm text-charcoal">{b.name}</p>
                ))}
              </div>
            )}

            {/* Insights Badge */}
            {insights_summary.pending_count > 0 && (
              <div className="bg-amber/10 border border-amber/30 rounded-lg p-4">
                <p className="text-xs font-medium text-amber">
                  {insights_summary.pending_count} insight{insights_summary.pending_count !== 1 ? 's' : ''} pending
                </p>
              </div>
            )}
          </div>

          {/* Main roster table */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-charcoal">{team.name}</h2>
              <span className="text-xs text-subtle px-2 py-1 bg-cream rounded">{team.training_phase}</span>
            </div>
            <RosterTable roster={roster} onSelectPlayer={setSelectedPlayer} />
          </div>
        </div>
      </div>
      <PlayerSlideOver pitcherId={selectedPlayer} onClose={() => setSelectedPlayer(null)} />
    </>
  )
}
