import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import PendingStrip from '../PendingStrip'

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

  it('renders Nudge button per pitcher, disabled when nudgeEnabled=false', () => {
    render(<PendingStrip pending={PENDING} nudgeEnabled={false} />)
    const buttons = screen.getAllByRole('button', { name: /nudge/i })
    expect(buttons).toHaveLength(2)
    buttons.forEach(b => expect(b).toBeDisabled())
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
