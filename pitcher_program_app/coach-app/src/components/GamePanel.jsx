import { useEffect, useState } from 'react'
import { patchCoachApi } from '../api'
import { useCoachAuth } from '../hooks/useCoachAuth'
import { useToast } from './shell/Toast'

export default function GamePanel({ game, roster, onClose, onUpdated }) {
  const { getAccessToken } = useCoachAuth()
  const toast = useToast()
  const [starterId, setStarterId] = useState(game?.starting_pitcher_id || '')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    function onKey(e) { if (e.key === 'Escape') onClose?.() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  if (!game) return null

  async function handleAssignStarter() {
    setSaving(true)
    try {
      await patchCoachApi(
        `/api/coach/schedule/game/${game.game_id}`,
        { starting_pitcher_id: starterId || null },
        getAccessToken()
      )
      toast.success('Starter assigned')
      onUpdated?.()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  const starters = (roster || []).filter(p => (p.role || '').includes('starter'))
  const relievers = (roster || []).filter(p => !(p.role || '').includes('starter'))
  const dateStr = new Date(game.game_date + 'T12:00:00').toLocaleDateString('en-US', {
    weekday: 'long', month: 'long', day: 'numeric', timeZone: 'America/Chicago',
  })

  return (
    <div className="fixed top-0 right-0 h-full w-[480px] bg-bone shadow-xl z-50 flex flex-col border-l border-cream-dark">
      <div className="flex items-center justify-between px-6 py-4 border-b border-cream-dark">
        <div>
          <p className="font-ui text-eyebrow uppercase tracking-[0.2em] text-subtle">Game</p>
          <h3 className="font-serif font-bold text-h1 text-charcoal mt-0.5">
            {game.home_away === 'home' ? 'vs' : '@'} {game.opponent || 'TBD'}
          </h3>
          <p className="font-ui text-body-sm text-subtle">{dateStr}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="font-ui text-h1 text-muted hover:text-charcoal leading-none"
          aria-label="Close"
        >
          ×
        </button>
      </div>
      <div className="p-6 space-y-5 flex-1 overflow-auto">
        <div>
          <p className="font-ui text-eyebrow uppercase tracking-[0.16em] text-subtle mb-2">
            Starting Pitcher
          </p>
          <select
            value={starterId}
            onChange={e => setStarterId(e.target.value)}
            className="w-full px-3 py-2 border border-cream-dark rounded-[3px] font-ui text-body-sm bg-bone text-charcoal"
          >
            <option value="">— Not assigned —</option>
            {starters.length > 0 && (
              <optgroup label="Starters">
                {starters.map(p => <option key={p.pitcher_id} value={p.pitcher_id}>{p.name}</option>)}
              </optgroup>
            )}
            {relievers.length > 0 && (
              <optgroup label="Relievers">
                {relievers.map(p => <option key={p.pitcher_id} value={p.pitcher_id}>{p.name}</option>)}
              </optgroup>
            )}
          </select>
          <button
            type="button"
            onClick={handleAssignStarter}
            disabled={saving}
            className="mt-3 w-full py-2 bg-maroon text-bone font-ui font-semibold text-body-sm rounded-[3px] hover:bg-maroon-ink disabled:opacity-50"
          >
            {saving ? 'Saving…' : 'Assign Starter'}
          </button>
        </div>
        {game.game_time && (
          <div>
            <p className="font-ui text-eyebrow uppercase tracking-[0.16em] text-subtle mb-1">Game Time</p>
            <p className="font-ui text-body text-charcoal">{game.game_time}</p>
          </div>
        )}
        {game.notes && (
          <div>
            <p className="font-ui text-eyebrow uppercase tracking-[0.16em] text-subtle mb-1">Notes</p>
            <p className="font-ui text-body text-subtle">{game.notes}</p>
          </div>
        )}
      </div>
    </div>
  )
}
