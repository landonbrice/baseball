import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import PendingStrip from '../PendingStrip'

vi.mock('../../../api', () => ({
  nudgePitcher: vi.fn().mockResolvedValue({
    sent: true,
    sent_at: '2026-04-21T15:30:00Z',
    telegram_message_id: 1,
  }),
}))

vi.mock('../../shell/Toast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn(), warn: vi.fn() }),
}))

vi.mock('../../../hooks/useCoachAuth', () => ({
  useCoachAuth: () => ({ getAccessToken: () => 'token123' }),
}))

const PENDING = [
  { pitcher_id: 'p1', name: 'Alpha', hours_since_last: 11 },
  { pitcher_id: 'p2', name: 'Beta', hours_since_last: 8 },
]

describe('<PendingStrip>', () => {
  it('renders pitcher names and last-seen hours', () => {
    render(<PendingStrip pending={PENDING} nudgeEnabled={false} />)
    expect(screen.getByText(/Alpha/)).toBeInTheDocument()
    expect(screen.getByText(/Beta/)).toBeInTheDocument()
    expect(screen.getByText(/11h ago/)).toBeInTheDocument()
    expect(screen.getByText(/8h ago/)).toBeInTheDocument()
  })

  it('renders "Awaiting check-in" eyebrow label', () => {
    render(<PendingStrip pending={PENDING} nudgeEnabled={false} />)
    expect(screen.getByText(/Awaiting check-in/i)).toBeInTheDocument()
  })

  it('Nudge buttons are disabled when nudgeEnabled=false', () => {
    render(<PendingStrip pending={PENDING} nudgeEnabled={false} />)
    const buttons = screen.getAllByRole('button', { name: /nudge/i })
    expect(buttons).toHaveLength(2)
    buttons.forEach(b => expect(b).toBeDisabled())
  })

  it('Nudge buttons are enabled when nudgeEnabled=true', () => {
    render(<PendingStrip pending={PENDING} nudgeEnabled />)
    const buttons = screen.getAllByRole('button', { name: /nudge/i })
    buttons.forEach(b => expect(b).not.toBeDisabled())
  })

  it('disables nudge button after successful send', async () => {
    render(<PendingStrip pending={[PENDING[0]]} nudgeEnabled />)
    const btn = screen.getByRole('button', { name: /nudge/i })
    fireEvent.click(btn)
    await waitFor(() => expect(btn).toBeDisabled())
  })

  it('renders nothing when pending is empty', () => {
    const { container } = render(<PendingStrip pending={[]} nudgeEnabled={false} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders nothing when pending is not an array', () => {
    const { container } = render(<PendingStrip pending={null} nudgeEnabled={false} />)
    expect(container.firstChild).toBeNull()
  })
})
