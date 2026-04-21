import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import WeekStrip from '../WeekStrip'

const ROSTER = [
  { pitcher_id: 'p1', name: 'Alpha', current_flag_level: 'green' },
  { pitcher_id: 'p2', name: 'Beta', current_flag_level: 'yellow' },
]

const GAME_MAP = {
  '2026-04-21': { game_date: '2026-04-21', opponent: 'UIC', home_away: 'home' },
}

describe('<WeekStrip>', () => {
  it('renders exactly 7 day cells', () => {
    render(<WeekStrip roster={ROSTER} gameMap={GAME_MAP} today="2026-04-21" />)
    const days = screen.getAllByText(/^(Sun|Mon|Tue|Wed|Thu|Fri|Sat)$/i)
    expect(days).toHaveLength(7)
  })

  it('shows game label for a day with a game', () => {
    render(<WeekStrip roster={ROSTER} gameMap={GAME_MAP} today="2026-04-21" />)
    expect(screen.getByText(/vs UIC/i)).toBeInTheDocument()
  })

  it('shows Rest for days without a game', () => {
    render(<WeekStrip roster={ROSTER} gameMap={GAME_MAP} today="2026-04-21" />)
    const restCells = screen.getAllByText('Rest')
    expect(restCells.length).toBeGreaterThan(0)
  })

  it('renders a compliance dot per roster pitcher', () => {
    const { container } = render(<WeekStrip roster={ROSTER} gameMap={{}} today="2026-04-21" />)
    // 7 days × 2 pitchers = 14 dots
    const dots = container.querySelectorAll('.rounded-full.w-2')
    expect(dots.length).toBe(14)
  })
})
