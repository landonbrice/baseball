import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
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
