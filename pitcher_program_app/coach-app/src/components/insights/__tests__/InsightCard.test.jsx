import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import InsightCard from '../InsightCard'

const NUDGE = {
  suggestion_id: 's1',
  pitcher_id: 'p1',
  pitcher_name: 'Landon Brice',
  category: 'pre_start_nudge',
  title: 'Consider reducing BP intensity',
  reasoning: 'Arm feel has trended down 3 consecutive days.',
  status: 'pending',
  created_at: '2026-04-20T10:00:00Z',
}

const TREND = { ...NUDGE, suggestion_id: 's2', category: 'trend_warning' }
const ACCEPTED = { ...NUDGE, suggestion_id: 's3', category: 'suggestion', status: 'accepted' }

// react-router-dom's useNavigate is hoist-mocked so the program-insight CTAs
// can be asserted without an actual router transition.
const navigateMock = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => navigateMock }
})

describe('<InsightCard variant="hero">', () => {
  it('renders amber left border for pre_start_nudge', () => {
    const { container } = render(<InsightCard suggestion={NUDGE} variant="hero" />)
    expect(container.firstChild.style.borderLeft).toContain('var(--color-amber)')
  })

  it('renders crimson left border for trend_warning', () => {
    const { container } = render(<InsightCard suggestion={TREND} variant="hero" />)
    expect(container.firstChild.style.borderLeft).toContain('var(--color-crimson)')
  })

  it('renders pitcher chip, type label, title, and body', () => {
    render(<InsightCard suggestion={NUDGE} variant="hero" />)
    expect(screen.getByText('Landon Brice')).toBeInTheDocument()
    expect(screen.getByText(/Pre-Start/i)).toBeInTheDocument()
    expect(screen.getByText('Consider reducing BP intensity')).toBeInTheDocument()
    expect(screen.getByText(/Arm feel has trended/i)).toBeInTheDocument()
  })

  it('calls onAccept when Accept clicked', () => {
    const onAccept = vi.fn()
    render(<InsightCard suggestion={NUDGE} variant="hero" onAccept={onAccept} />)
    fireEvent.click(screen.getByRole('button', { name: /accept/i }))
    expect(onAccept).toHaveBeenCalledOnce()
  })

  it('calls onDismiss when Dismiss clicked', () => {
    const onDismiss = vi.fn()
    render(<InsightCard suggestion={NUDGE} variant="hero" onDismiss={onDismiss} />)
    fireEvent.click(screen.getByRole('button', { name: /dismiss/i }))
    expect(onDismiss).toHaveBeenCalledOnce()
  })
})

describe('<InsightCard variant="compact">', () => {
  it('renders forest left border for accepted status', () => {
    const { container } = render(<InsightCard suggestion={ACCEPTED} variant="compact" />)
    expect(container.firstChild.style.borderLeft).toContain('var(--color-forest)')
  })

  it('renders pitcher name and status text', () => {
    render(<InsightCard suggestion={ACCEPTED} variant="compact" />)
    expect(screen.getByText('Landon Brice')).toBeInTheDocument()
    expect(screen.getByText('accepted')).toBeInTheDocument()
  })
})

describe('<InsightCard /> — A4 program-builder categories', () => {
  beforeEach(() => {
    navigateMock.mockClear()
  })

  it('renders program_drift insight with body + Archive/Accept CTAs', () => {
    const drift = {
      suggestion_id: 'd1',
      pitcher_id: 'p1',
      pitcher_name: 'Landon Brice',
      category: 'program_drift',
      title: 'Program drifted 8 days behind',
      reasoning:
        'Throwing program velocity_12wk_v1 is on day 14 but should be on day 22. Held 3 days lifetime. Consider archiving and rebuilding.',
      proposed_action: {
        type: 'review_drift',
        program_id: 'prog_abc',
        drift_days: 8,
        expected_day: 21,
        actual_day: 13,
      },
      status: 'pending',
    }
    render(
      <MemoryRouter>
        <InsightCard suggestion={drift} variant="hero" />
      </MemoryRouter>
    )
    expect(screen.getByText('Program drifted 8 days behind')).toBeInTheDocument()
    expect(screen.getByText(/velocity_12wk_v1/i)).toBeInTheDocument()
    // Type label is uppercased + tracked — assert the exact label, not the title.
    expect(screen.getByText('Program Drift')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /archive program/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /accept new pace/i })).toBeInTheDocument()
    // No standard Accept/Dismiss/Defer for program-builder insights.
    expect(screen.queryByRole('button', { name: /^accept$/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^dismiss$/i })).not.toBeInTheDocument()
  })

  it('renders program_flag_mismatch with Open Programs CTA that navigates to roster', () => {
    const mismatch = {
      suggestion_id: 'm1',
      pitcher_id: 'pitcher_kamat_001',
      pitcher_name: 'Taran Kamat',
      category: 'program_flag_mismatch',
      title: 'Taran Kamat on high-intent program while YELLOW',
      reasoning:
        'Pitcher built velocity_12wk_v1 (high-intent phase) but current flag level is YELLOW.',
      proposed_action: {
        type: 'review_mismatch',
        program_id: 'prog_xyz',
        flag_level: 'yellow',
        template: 'velocity_12wk_v1',
      },
      status: 'pending',
    }
    render(
      <MemoryRouter>
        <InsightCard suggestion={mismatch} variant="hero" />
      </MemoryRouter>
    )
    expect(screen.getByText(/on high-intent program while YELLOW/i)).toBeInTheDocument()
    expect(screen.getByText(/Program Mismatch/i)).toBeInTheDocument()
    const cta = screen.getByRole('button', { name: /open programs/i })
    fireEvent.click(cta)
    expect(navigateMock).toHaveBeenCalledWith('/', {
      state: { openPitcherId: 'pitcher_kamat_001' },
    })
  })

  it('renders team_program_lagging with Open Team Programs CTA that navigates to /programs', () => {
    const lagging = {
      suggestion_id: 't1',
      pitcher_id: 'pitcher_lazar_001',
      pitcher_name: 'Jonathan Lazar',
      category: 'team_program_lagging',
      title: '3 pitchers <50% on longtoss_6wk_v1',
      reasoning:
        'Team is ~3.5 weeks into longtoss_6wk_v1. Average completion 42%. Behind: pitcher_lazar_001, pitcher_reed_001, pitcher_wilson_001.',
      proposed_action: {
        type: 'review_team_lag',
        block_id: 'blk_123',
        block_template_id: 'longtoss_6wk_v1',
        mean_completion_pct: 0.42,
        lagger_pitcher_ids: [
          'pitcher_lazar_001',
          'pitcher_reed_001',
          'pitcher_wilson_001',
        ],
        scope: 'team',
      },
      status: 'pending',
    }
    render(
      <MemoryRouter>
        <InsightCard suggestion={lagging} variant="hero" />
      </MemoryRouter>
    )
    expect(screen.getByText(/3 pitchers <50% on longtoss_6wk_v1/i)).toBeInTheDocument()
    expect(screen.getByText(/Team Lag/i)).toBeInTheDocument()
    const cta = screen.getByRole('button', { name: /open team programs/i })
    fireEvent.click(cta)
    expect(navigateMock).toHaveBeenCalledWith('/programs')
  })
})
