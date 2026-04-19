import { useEffect, useRef, useState } from 'react'
import Masthead from '../components/shell/Masthead'
import Scoreboard from '../components/shell/Scoreboard'
import Lede from '../components/shell/Lede'
import FlagPill from '../components/shell/FlagPill'
import EditorialState from '../components/shell/EditorialState'
import { useToast } from '../components/shell/Toast'

const SCOREBOARD_CELLS = [
  { label: 'Roster', value: '12', sub: 'pitchers' },
  { label: 'Checked In', value: '11/12', sub: '92%' },
  {
    label: 'Flags',
    value: (
      <>
        <span className="text-forest">9</span>
        <span> · </span>
        <span className="text-amber">2</span>
        <span> · </span>
        <span className="text-crimson">1</span>
      </>
    ),
    sub: 'G · Y · R',
  },
  { label: 'Active Block', value: 'Velo 12wk', sub: 'wk 4 of 12' },
  { label: 'Next Game', value: 'Apr 22', sub: 'vs Wash U' },
]

export default function DesignSandbox() {
  const root = useRef(null)
  const [axeReport, setAxeReport] = useState('axe not yet run')
  const toast = useToast()

  useEffect(() => {
    let cancelled = false
    import('axe-core').then(axe => {
      if (cancelled || !root.current) return
      axe.run(root.current).then(results => {
        if (cancelled) return
        const violations = results.violations || []
        setAxeReport(violations.length === 0
          ? 'axe: 0 violations'
          : `axe: ${violations.length} violations — ${violations.map(v => v.id).join(', ')}`)
      })
    })
    return () => { cancelled = true }
  }, [])

  return (
    <div ref={root} className="p-6 space-y-10">
      <Masthead
        kicker="Chicago · Pitching Staff"
        title="Design Sandbox"
        date="Sat · Apr 18"
        week="Week 3 of Pre-season"
        actionSlot={
          <button className="font-ui text-body-sm font-semibold text-bone bg-maroon hover:bg-maroon-ink px-3 py-1.5 rounded-[3px]">
            + New Program
          </button>
        }
      />

      <section>
        <h2 className="font-ui font-semibold uppercase text-kicker tracking-[0.2em] text-maroon mb-2">Scoreboard</h2>
        <Scoreboard cells={SCOREBOARD_CELLS} />
      </section>

      <section>
        <h2 className="font-ui font-semibold uppercase text-kicker tracking-[0.2em] text-maroon mb-2">Lede</h2>
        <Lede>
          <b>Wade Hartrick</b> is back to good after Tuesday's outing — full lift cleared.
        </Lede>
      </section>

      <section className="flex gap-2">
        <FlagPill level="green" />
        <FlagPill level="yellow" />
        <FlagPill level="red" />
        <FlagPill level="pending" />
      </section>

      <section className="grid grid-cols-3 gap-6">
        <EditorialState type="loading" copy="Gathering the morning check-ins…" />
        <EditorialState type="empty" copy="No outings reported yet today." />
        <EditorialState type="error" copy="Something's off on our end." retry={() => toast.success('Retried')} />
      </section>

      <section className="flex gap-2">
        <button className="font-ui text-body-sm font-semibold px-3 py-1.5 rounded-[3px] bg-forest text-bone" onClick={() => toast.success('Saved')}>Toast: success</button>
        <button className="font-ui text-body-sm font-semibold px-3 py-1.5 rounded-[3px] bg-amber text-charcoal" onClick={() => toast.warn('Watch this')}>Toast: warn</button>
        <button className="font-ui text-body-sm font-semibold px-3 py-1.5 rounded-[3px] bg-crimson text-bone" onClick={() => toast.error('Failed')}>Toast: error</button>
        <button className="font-ui text-body-sm font-semibold px-3 py-1.5 rounded-[3px] bg-maroon text-bone" onClick={() => toast.info('FYI')}>Toast: info</button>
      </section>

      <section>
        <h2 className="font-ui font-semibold uppercase text-kicker tracking-[0.2em] text-maroon mb-2">Accessibility</h2>
        <Lede>{axeReport}</Lede>
      </section>
    </div>
  )
}
