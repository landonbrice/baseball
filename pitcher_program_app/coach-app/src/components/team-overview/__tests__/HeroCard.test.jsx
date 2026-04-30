import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import HeroCard from '../HeroCard'

const BASE = {
  pitcher_id: 'pitcher_heron_001',
  name: 'Carter Heron',
  role: 'Reliever (long)',
  flag_level: 'yellow',
  af_7d: 6.1,
  active_injury_flags: ['ulnar nerve (yellow)'],
  last_7_days: [
    { date: '2026-04-13', status: 'checked_in' },
    { date: '2026-04-14', status: 'checked_in' },
    { date: '2026-04-15', status: 'partial' },
    { date: '2026-04-16', status: 'none' },
    { date: '2026-04-17', status: 'checked_in' },
    { date: '2026-04-18', status: 'checked_in' },
    { date: '2026-04-19', status: 'checked_in' },
  ],
  next_scheduled_start: '2026-04-22',
  today: { day_focus: 'lift', lifting_summary: 'Lower pull — RDL, row', modifications: [] },
}

describe('<HeroCard>', () => {
  it('renders name, role, AF stat, and injury chip', () => {
    render(<HeroCard pitcher={BASE} />)
    expect(screen.getByText('Carter Heron')).toBeInTheDocument()
    expect(screen.getByText(/Reliever \(long\)/i)).toBeInTheDocument()
    expect(screen.getByText('6.1')).toBeInTheDocument()
    expect(screen.getByText(/ulnar nerve/i)).toBeInTheDocument()
  })

  it('renders the FlagPill at the correct level', () => {
    render(<HeroCard pitcher={BASE} />)
    expect(screen.getAllByText(/yellow/i).length).toBeGreaterThan(0)
  })

  it('red flag renders crimson left border', () => {
    const { container } = render(<HeroCard pitcher={{ ...BASE, flag_level: 'red' }} />)
    expect(container.firstChild.className).toMatch(/border-l-crimson/)
  })

  it('yellow flag renders amber left border', () => {
    const { container } = render(<HeroCard pitcher={BASE} />)
    expect(container.firstChild.className).toMatch(/border-l-amber/)
  })

  it('renders today objective mark + text from buildTodayObjective', () => {
    render(<HeroCard pitcher={BASE} />)
    expect(screen.getByText(/Today · Lift/i)).toBeInTheDocument()
    expect(screen.getByText(/Lower pull — RDL, row/)).toBeInTheDocument()
  })

  it('handles null af_7d with em-dash', () => {
    render(<HeroCard pitcher={{ ...BASE, af_7d: null }} />)
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('calls onOpen with pitcher_id when clicked', async () => {
    const onOpen = vi.fn()
    render(<HeroCard pitcher={BASE} onOpen={onOpen} />)
    await userEvent.click(screen.getByRole('button', { name: /carter heron/i }))
    expect(onOpen).toHaveBeenCalledWith('pitcher_heron_001')
  })

  it('renders baseline establishing subscript for cold-start pitchers', () => {
    render(
      <HeroCard
        pitcher={{
          ...BASE,
          baseline_state: 'no_baseline',
          total_check_ins: 3,
          today: { rationale_short: 'Arm feel down to 5.', day_focus: 'lift', modifications: [] },
        }}
      />
    )
    expect(screen.getByText(/baseline establishing 3\/14/i)).toBeInTheDocument()
  })

  it('does NOT render subscript for full-baseline pitchers', () => {
    render(
      <HeroCard
        pitcher={{
          ...BASE,
          baseline_state: 'full',
          total_check_ins: 40,
          today: { rationale_short: 'All systems good.', day_focus: 'lift', modifications: [] },
        }}
      />
    )
    expect(screen.queryByText(/establishing/i)).not.toBeInTheDocument()
  })

  it('shows 0/14 when total_check_ins missing', () => {
    render(
      <HeroCard
        pitcher={{
          ...BASE,
          baseline_state: 'no_baseline',
          today: { rationale_short: 'New pitcher.', day_focus: 'lift', modifications: [] },
        }}
      />
    )
    expect(screen.getByText(/baseline establishing 0\/14/i)).toBeInTheDocument()
  })
})
