import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import ProgramStrip from '../ProgramStrip'

describe('<ProgramStrip>', () => {
  it('renders one row per active program (throwing + lifting)', () => {
    const programs = [
      {
        program_id: '1',
        domain: 'throwing',
        parent_template_id: 'velocity_12wk_v1',
        current_day_index: 21,
        held_days_count: 0,
      },
      {
        program_id: '2',
        domain: 'lifting',
        parent_template_id: 'hypertrophy_8wk_v1',
        current_day_index: 7,
        held_days_count: 0,
      },
    ]
    render(<ProgramStrip programs={programs} />)
    // Both domain rows present.
    expect(screen.getByText(/\[Throwing\] velocity_12wk_v1 · Day 22/)).toBeInTheDocument()
    expect(screen.getByText(/\[Lifting\] hypertrophy_8wk_v1 · Day 8/)).toBeInTheDocument()
    // No held-days suffix when count is 0.
    expect(screen.queryByText(/Held/)).not.toBeInTheDocument()
  })

  it('returns null when no programs', () => {
    const { container } = render(<ProgramStrip programs={[]} />)
    expect(container.firstChild).toBeNull()
  })

  it('returns null when programs prop is undefined/null', () => {
    const { container: c1 } = render(<ProgramStrip programs={null} />)
    expect(c1.firstChild).toBeNull()
    const { container: c2 } = render(<ProgramStrip programs={undefined} />)
    expect(c2.firstChild).toBeNull()
  })

  it('renders "Held N" suffix when held_days_count > 0', () => {
    const programs = [
      {
        program_id: '1',
        domain: 'throwing',
        parent_template_id: 'velocity_12wk_v1',
        current_day_index: 21,
        held_days_count: 3,
      },
    ]
    render(<ProgramStrip programs={programs} />)
    expect(screen.getByText(/\[Throwing\] velocity_12wk_v1 · Day 22 · Held 3/)).toBeInTheDocument()
  })
})
