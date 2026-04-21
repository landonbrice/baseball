import { useState } from 'react'
import { useCoachAuth } from '../../hooks/useCoachAuth'
import { useToast } from '../shell/Toast'
import { nudgePitcher } from '../../api'

export default function PendingStrip({ pending, nudgeEnabled = false }) {
  const { getAccessToken } = useCoachAuth()
  const toast = useToast()
  const [nudged, setNudged] = useState(new Set())
  const [nudging, setNudging] = useState(null)

  if (!Array.isArray(pending) || pending.length === 0) return null

  async function handleNudge(p) {
    if (!nudgeEnabled || nudged.has(p.pitcher_id) || nudging === p.pitcher_id) return
    setNudging(p.pitcher_id)
    toast.info(`Nudging ${p.name}…`)
    try {
      const result = await nudgePitcher(p.pitcher_id, getAccessToken())
      if (result.sent) {
        const sentAt = new Date(result.sent_at).toLocaleTimeString('en-US', {
          hour: 'numeric', minute: '2-digit', timeZone: 'America/Chicago',
        })
        toast.success(`Nudge sent · ${sentAt}`, 3000)
        setNudged(prev => new Set([...prev, p.pitcher_id]))
      }
    } catch (err) {
      const msg = err.message?.includes('rate_limited')
        ? `${p.name} was nudged recently. Try again later.`
        : `Couldn't reach ${p.name}. Try again?`
      toast.error(msg)
    } finally {
      setNudging(null)
    }
  }

  return (
    <div className="border border-dashed border-cream-dark bg-black/[0.03] rounded-[3px] px-3.5 py-2.5 flex items-center gap-3 flex-wrap">
      <span className="font-ui font-semibold uppercase text-[9px] tracking-[0.16em] text-amber">
        Awaiting check-in
      </span>
      {pending.map(p => {
        const isNudged = nudged.has(p.pitcher_id)
        const isNudging = nudging === p.pitcher_id
        return (
          <span key={p.pitcher_id} className="flex items-center gap-1.5">
            <span className="font-ui text-body-sm text-charcoal">{p.name}</span>
            <span className="font-ui text-meta text-muted">
              {typeof p.hours_since_last === 'number' ? `${p.hours_since_last}h ago` : ''}
            </span>
            <button
              type="button"
              disabled={!nudgeEnabled || isNudged || isNudging}
              title={
                !nudgeEnabled ? 'Backend pending (Spec 3)'
                : isNudged ? 'Nudge sent'
                : isNudging ? 'Sending…'
                : 'Send a reminder'
              }
              onClick={() => handleNudge(p)}
              className="font-ui text-meta font-semibold text-maroon hover:text-maroon-ink disabled:text-muted disabled:cursor-not-allowed"
            >
              {isNudging ? '…' : isNudged ? '✓' : 'Nudge →'}
            </button>
          </span>
        )
      })}
    </div>
  )
}
