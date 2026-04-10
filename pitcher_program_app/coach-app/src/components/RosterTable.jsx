import { useState, useMemo } from 'react'

const FLAG_COLORS = { red: '#c0392b', yellow: '#d4a017', green: '#2d5a3d' }

function StatusDot({ status }) {
  const color = status === 'checked_in' ? '#2d5a3d' : '#e4dfd8'
  return <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', backgroundColor: color }} />
}

function WeekStrip({ days }) {
  return (
    <div style={{ display: 'flex', gap: 2 }}>
      {(days || []).map((d, i) => (
        <div key={i} style={{
          width: 10, height: 10, borderRadius: 2,
          backgroundColor: d.status === 'checked_in' ? '#2d5a3d' : d.status === 'partial' ? '#d4a017' : '#e4dfd8',
        }} />
      ))}
    </div>
  )
}

export default function RosterTable({ roster, onSelectPlayer }) {
  const [sortKey, setSortKey] = useState('name')
  const [sortDir, setSortDir] = useState('asc')
  const [filter, setFilter] = useState('all')

  const filtered = useMemo(() => {
    let list = [...(roster || [])]
    if (filter === 'checked_in') list = list.filter(r => r.today_status === 'checked_in')
    if (filter === 'not_yet') list = list.filter(r => r.today_status !== 'checked_in')
    if (filter === 'flagged') list = list.filter(r => r.flag_level !== 'green')

    list.sort((a, b) => {
      let va = a[sortKey] || '', vb = b[sortKey] || ''
      if (typeof va === 'string') va = va.toLowerCase()
      if (typeof vb === 'string') vb = vb.toLowerCase()
      if (va < vb) return sortDir === 'asc' ? -1 : 1
      if (va > vb) return sortDir === 'asc' ? 1 : -1
      return 0
    })
    return list
  }, [roster, sortKey, sortDir, filter])

  function handleSort(key) {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('asc') }
  }

  const SortHeader = ({ k, children }) => (
    <th onClick={() => handleSort(k)} className="px-3 py-2 text-left text-xs font-medium text-subtle cursor-pointer hover:text-charcoal select-none">
      {children} {sortKey === k && (sortDir === 'asc' ? '↑' : '↓')}
    </th>
  )

  return (
    <div>
      <div className="flex gap-2 mb-3">
        {['all', 'checked_in', 'not_yet', 'flagged'].map(f => (
          <button key={f} onClick={() => setFilter(f)}
            className={`px-3 py-1 rounded-full text-xs font-medium ${filter === f ? 'bg-maroon text-white' : 'bg-cream-dark text-charcoal'}`}>
            {f === 'all' ? 'All' : f === 'checked_in' ? 'Checked In' : f === 'not_yet' ? 'Not Yet' : 'Flagged'}
          </button>
        ))}
      </div>
      <div className="bg-white rounded-lg border border-cream-dark overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-cream">
            <tr>
              <SortHeader k="name">Player</SortHeader>
              <SortHeader k="role">Pos</SortHeader>
              <th className="px-3 py-2 text-left text-xs font-medium text-subtle">Status</th>
              <th className="px-3 py-2 text-left text-xs font-medium text-subtle">Last 7</th>
              <SortHeader k="streak">Streak</SortHeader>
              <th className="px-3 py-2 text-left text-xs font-medium text-subtle">Flags</th>
              <SortHeader k="next_scheduled_start">Next Start</SortHeader>
            </tr>
          </thead>
          <tbody>
            {filtered.map(p => (
              <tr key={p.pitcher_id} onClick={() => onSelectPlayer?.(p.pitcher_id)}
                className="border-t border-cream-dark hover:bg-cream/50 cursor-pointer">
                <td className="px-3 py-2 font-medium text-charcoal">
                  <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', backgroundColor: FLAG_COLORS[p.flag_level] || FLAG_COLORS.green, marginRight: 6 }} />
                  {p.name}
                </td>
                <td className="px-3 py-2 text-subtle">{(p.role || '').replace(/_/g, ' ')}</td>
                <td className="px-3 py-2"><StatusDot status={p.today_status} /></td>
                <td className="px-3 py-2"><WeekStrip days={p.last_7_days} /></td>
                <td className="px-3 py-2 text-charcoal">{p.streak || 0}</td>
                <td className="px-3 py-2 text-xs text-subtle">{(p.active_injury_flags || []).join(', ') || '-'}</td>
                <td className="px-3 py-2 text-xs text-subtle">{p.next_scheduled_start || '-'}</td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr><td colSpan={7} className="px-3 py-8 text-center text-subtle">No pitchers match filter</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
