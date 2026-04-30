import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import MutationPreview from '../MutationPreview'

describe('MutationPreview', () => {
  it('renders exercise rationale diffs when present', () => {
    render(
      <MutationPreview
        proposed={{
          exercise_rationale_diff: [
            { exercise_id: 'e2', before: 'trimmed volume', after: 'progression — weight up' },
          ],
          day_summary_before: 'Lift-focused day — trimmed.',
          day_summary_after: 'Lift-focused day — full program.',
        }}
      />
    )
    expect(screen.getByText(/trimmed volume/i)).toBeInTheDocument()
    expect(screen.getByText(/progression — weight up/i)).toBeInTheDocument()
    expect(screen.getByText(/full program/i)).toBeInTheDocument()
  })

  it('renders only day summary when no exercise diffs', () => {
    render(
      <MutationPreview
        proposed={{
          exercise_rationale_diff: [],
          day_summary_before: 'A.',
          day_summary_after: 'B.',
        }}
      />
    )
    expect(screen.getByText('A.')).toBeInTheDocument()
    expect(screen.getByText('B.')).toBeInTheDocument()
  })

  it('renders em-dash placeholders when before/after rationale is null', () => {
    render(
      <MutationPreview
        proposed={{
          exercise_rationale_diff: [
            { exercise_id: 'e1', before: null, after: 'newly added' },
            { exercise_id: 'e2', before: 'old reason', after: null },
          ],
        }}
      />
    )
    expect(screen.getByText(/newly added/i)).toBeInTheDocument()
    expect(screen.getByText(/old reason/i)).toBeInTheDocument()
    // two — placeholders, one for each missing side
    expect(screen.getAllByText('—').length).toBe(2)
  })

  it('renders nothing for null proposed', () => {
    const { container } = render(<MutationPreview proposed={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing when proposed has no day summary and no diffs', () => {
    const { container } = render(
      <MutationPreview
        proposed={{ exercise_rationale_diff: [], day_summary_before: null, day_summary_after: null }}
      />
    )
    expect(container).toBeEmptyDOMElement()
  })
})
