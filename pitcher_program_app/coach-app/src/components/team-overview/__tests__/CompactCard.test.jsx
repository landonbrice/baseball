import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import CompactCard from '../CompactCard'

const BASE = {
  pitcher_id: 'pitcher_alpha',
  name: 'Alpha Alpha',
  role: 'Starter (7-day)',
  flag_level: 'green',
  af_7d: 7.4,
  last_7_days: [
    { date: '2026-04-13', status: 'checked_in' },
    { date: '2026-04-14', status: 'checked_in' },
    { date: '2026-04-15', status: 'checked_in' },
    { date: '2026-04-16', status: 'checked_in' },
    { date: '2026-04-17', status: 'checked_in' },
    { date: '2026-04-18', status: 'checked_in' },
    { date: '2026-04-19', status: 'checked_in' },
  ],
  next_scheduled_start: '2026-04-23',
  today: { day_focus: 'bullpen', bullpen: { pitches: 35, intent_pct: 85, mix: 'FB/CH' } },
}

describe('<CompactCard>', () => {
  it('renders name, role, AF, and objective line', () => {
    render(<CompactCard pitcher={BASE} />)
    expect(screen.getByText('Alpha Alpha')).toBeInTheDocument()
    expect(screen.getByText('7.4')).toBeInTheDocument()
    expect(screen.getByText(/Bullpen/)).toBeInTheDocument()
    expect(screen.getByText(/35p · 85% · FB\/CH/)).toBeInTheDocument()
  })

  it('renders a forest left border', () => {
    const { container } = render(<CompactCard pitcher={BASE} />)
    expect(container.firstChild.className).toMatch(/border-l-forest/)
  })

  it('calls onOpen on click', async () => {
    const onOpen = vi.fn()
    render(<CompactCard pitcher={BASE} onOpen={onOpen} />)
    await userEvent.click(screen.getByRole('button', { name: /alpha alpha/i }))
    expect(onOpen).toHaveBeenCalledWith('pitcher_alpha')
  })

  it('handles null af_7d with em-dash', () => {
    render(<CompactCard pitcher={{ ...BASE, af_7d: null }} />)
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  // ---- C7: driving-category suffix ----

  it('omits driving suffix when green and all scores ≥ 4 (visually quiet)', () => {
    render(
      <CompactCard
        pitcher={{
          ...BASE,
          flag_level: 'green',
          category_scores: { tissue_score: 6.0, load_score: 7.5, recovery_score: 5.2 },
        }}
      />
    )
    expect(screen.queryByTestId('flag-driving-suffix')).toBeNull()
  })

  it('shows driving suffix on green when a category score is below 4 (early warning)', () => {
    render(
      <CompactCard
        pitcher={{
          ...BASE,
          flag_level: 'green',
          category_scores: { tissue_score: 3.4, load_score: 7.0, recovery_score: 6.0 },
        }}
      />
    )
    const suffix = screen.getByTestId('flag-driving-suffix')
    expect(suffix).toHaveTextContent(/tissue/i)
    expect(suffix).toHaveTextContent('3.4')
  })

  it('omits suffix when no category_scores present', () => {
    render(<CompactCard pitcher={{ ...BASE, category_scores: null }} />)
    expect(screen.queryByTestId('flag-driving-suffix')).toBeNull()
  })
})
