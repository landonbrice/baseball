import { useState } from 'react'
import { patchCoachApi } from '../api'
import { useCoachAuth } from '../hooks/useCoachAuth'

export default function GamePanel({ game, roster, onClose, onUpdated }) {
  const { getAccessToken } = useCoachAuth()
  const [starterId, setStarterId] = useState(game?.starting_pitcher_id || '')
  const [saving, setSaving] = useState(false)

  if (!game) return null

  async function handleAssignStarter() {
    setSaving(true)
    try {
      await patchCoachApi(`/api/coach/schedule/game/${game.game_id}`, { starting_pitcher_id: starterId || null }, getAccessToken())
      onUpdated?.()
    } catch (err) {
      alert(err.message)
    } finally {
      setSaving(false)
    }
  }

  const starters = (roster || []).filter(p => (p.role || '').includes('starter'))
  const relievers = (roster || []).filter(p => !(p.role || '').includes('starter'))

  return (
    <div className="fixed top-0 right-0 h-full w-80 bg-white shadow-xl z-50 flex flex-col border-l border-cream-dark">
      <div className="flex items-center justify-between p-4 border-b border-cream-dark">
        <h3 className="text-sm font-bold text-charcoal">Game Detail</h3>
        <button onClick={onClose} className="text-subtle hover:text-charcoal">&times;</button>
      </div>
      <div className="p-4 space-y-4 flex-1 overflow-auto">
        <div>
          <p className="text-xs text-subtle">Date</p>
          <p className="text-sm font-medium text-charcoal">{game.game_date}</p>
        </div>
        <div>
          <p className="text-xs text-subtle">Opponent</p>
          <p className="text-sm font-medium text-charcoal">{game.home_away === 'home' ? 'vs' : '@'} {game.opponent || 'TBD'}</p>
        </div>
        {game.game_time && (
          <div>
            <p className="text-xs text-subtle">Time</p>
            <p className="text-sm text-charcoal">{game.game_time}</p>
          </div>
        )}
        <div>
          <p className="text-xs text-subtle mb-1">Starting Pitcher</p>
          <select value={starterId} onChange={e => setStarterId(e.target.value)}
            className="w-full px-2 py-1.5 border border-cream-dark rounded text-sm">
            <option value="">— Not assigned —</option>
            {starters.length > 0 && <optgroup label="Starters">
              {starters.map(p => <option key={p.pitcher_id} value={p.pitcher_id}>{p.name}</option>)}
            </optgroup>}
            {relievers.length > 0 && <optgroup label="Relievers">
              {relievers.map(p => <option key={p.pitcher_id} value={p.pitcher_id}>{p.name}</option>)}
            </optgroup>}
          </select>
          <button onClick={handleAssignStarter} disabled={saving}
            className="mt-2 w-full py-1.5 bg-maroon text-white rounded text-sm font-medium hover:bg-maroon-light disabled:opacity-50">
            {saving ? 'Saving...' : 'Assign Starter'}
          </button>
        </div>
      </div>
    </div>
  )
}
