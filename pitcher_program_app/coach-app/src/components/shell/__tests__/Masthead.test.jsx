import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import Masthead from '../Masthead'

describe('<Masthead>', () => {
  it('renders kicker, title, and date', () => {
    render(<Masthead kicker="Chicago · Pitching Staff" title="Team Overview" date="Sat · Apr 18" />)
    expect(screen.getByText('Chicago · Pitching Staff')).toBeInTheDocument()
    expect(screen.getByText('Team Overview')).toBeInTheDocument()
    expect(screen.getByText('Sat · Apr 18')).toBeInTheDocument()
  })

  it('renders week context when provided', () => {
    render(<Masthead kicker="K" title="T" date="D" week="Week 3 of Pre-season" />)
    expect(screen.getByText('Week 3 of Pre-season')).toBeInTheDocument()
  })

  it('omits the week line when not provided', () => {
    render(<Masthead kicker="K" title="T" date="D" />)
    expect(screen.queryByText(/week/i)).not.toBeInTheDocument()
  })

  it('renders an actionSlot when provided', () => {
    render(
      <Masthead
        kicker="K"
        title="T"
        date="D"
        actionSlot={<button>+ New Program</button>}
      />
    )
    expect(screen.getByRole('button', { name: /new program/i })).toBeInTheDocument()
  })

  it('renders the title in serif at display size', () => {
    render(<Masthead kicker="K" title="Team Overview" date="D" />)
    const heading = screen.getByRole('heading', { name: 'Team Overview' })
    expect(heading.className).toContain('font-serif')
    expect(heading.className).toContain('text-display')
  })
})
