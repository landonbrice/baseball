import { describe, it, expect, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import PlayerToday from '../PlayerToday'

vi.mock('../../hooks/useExerciseName', () => ({
  useExerciseName: ({ item }) => item?.name || '—',
}))

const TODAY = new Date().toLocaleDateString('en-CA', { timeZone: 'America/Chicago' })

function buildData(entry) {
  return {
    current_week: [{ date: TODAY, plan_generated: {}, ...entry }],
  }
}

const RATIONALE_DETAIL = {
  status_line: 'Modified green — tissue concern',
  signal_line: 'Arm feel 8 → 7 → 6 over three check-ins.',
  response_line: 'Holding compounds. Trimmed accessories 20%.',
}

const LIFTING = {
  exercises: [
    { id: 'e1', name: 'Squat', prescribed: '3x5 @ 185', rationale: 'progression — weight up' },
    { id: 'e2', name: 'Row', prescribed: '3x8 @ 115', rationale: 'trimmed volume for tissue concern' },
  ],
}

describe('<PlayerToday> F4 rationale layer', () => {
  it('renders day_summary_rationale when present', () => {
    const data = buildData({
      rationale: { day_summary_rationale: 'Lift-focused day — trimmed accessories 20%.' },
      lifting: LIFTING,
    })
    render(<PlayerToday data={data} />)
    expect(screen.getByText(/trimmed accessories 20%/i)).toBeInTheDocument()
  })

  it('renders rationale_detail three-line block', () => {
    const data = buildData({
      rationale: { rationale_detail: RATIONALE_DETAIL },
      lifting: LIFTING,
    })
    render(<PlayerToday data={data} />)
    expect(screen.getByText(/Modified green/i)).toBeInTheDocument()
    expect(screen.getByText(/8 → 7 → 6/)).toBeInTheDocument()
    expect(screen.getByText(/Holding compounds/i)).toBeInTheDocument()
  })

  it('renders per-exercise rationale under each exercise', () => {
    const data = buildData({ lifting: LIFTING })
    render(<PlayerToday data={data} />)
    expect(screen.getByText(/progression — weight up/i)).toBeInTheDocument()
    expect(screen.getByText(/trimmed volume/i)).toBeInTheDocument()
  })

  it('omits rationale row for null per-exercise rationale', () => {
    const data = buildData({
      lifting: {
        exercises: [
          { id: 'e1', name: 'Banded row', prescribed: '2x15', rationale: null },
        ],
      },
    })
    render(<PlayerToday data={data} />)
    expect(screen.queryByText(/progression/i)).not.toBeInTheDocument()
    expect(screen.getByText('Banded row')).toBeInTheDocument()
  })

  it('skips rationale_detail block when not provided', () => {
    const data = buildData({ lifting: LIFTING })
    render(<PlayerToday data={data} />)
    expect(screen.queryByText(/^Status:/)).not.toBeInTheDocument()
    expect(screen.queryByText(/^Signal:/)).not.toBeInTheDocument()
  })

  it('renders only the lines present in rationale_detail', () => {
    const data = buildData({
      rationale: { rationale_detail: { status_line: 'Modified green — only status' } },
      lifting: LIFTING,
    })
    render(<PlayerToday data={data} />)
    expect(screen.getByText(/only status/i)).toBeInTheDocument()
    expect(screen.queryByText(/Signal:/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Response:/)).not.toBeInTheDocument()
  })
})

describe('<PlayerToday> C7 category scores 3-stat row', () => {
  it('renders 3-stat row when category_scores present and marks lowest as driving', () => {
    const data = buildData({
      pre_training: {
        arm_feel: 6,
        category_scores: { tissue_score: 2.3, load_score: 6.1, recovery_score: 5.4 },
      },
      lifting: LIFTING,
    })
    render(<PlayerToday data={data} />)
    const row = screen.getByTestId('category-scores')
    expect(row).toBeInTheDocument()
    expect(within(row).getByText(/Tissue/i)).toBeInTheDocument()
    expect(within(row).getByText(/Load/i)).toBeInTheDocument()
    expect(within(row).getByText(/Recovery/i)).toBeInTheDocument()
    expect(within(row).getByText('2.3')).toBeInTheDocument()
    expect(within(row).getByText('6.1')).toBeInTheDocument()
    expect(within(row).getByText('5.4')).toBeInTheDocument()
    expect(within(row).getByText(/driving/i)).toBeInTheDocument()
  })

  it('omits 3-stat row when no category_scores', () => {
    const data = buildData({ pre_training: { arm_feel: 7 }, lifting: LIFTING })
    render(<PlayerToday data={data} />)
    expect(screen.queryByTestId('category-scores')).toBeNull()
  })

  it('omits 3-stat row when pre_training missing entirely', () => {
    const data = buildData({ lifting: LIFTING })
    render(<PlayerToday data={data} />)
    expect(screen.queryByTestId('category-scores')).toBeNull()
  })

  it('renders driving on tissue when tissue is the lowest', () => {
    const data = buildData({
      pre_training: {
        category_scores: { tissue_score: 2.0, load_score: 8.0, recovery_score: 7.0 },
      },
      lifting: LIFTING,
    })
    render(<PlayerToday data={data} />)
    const row = screen.getByTestId('category-scores')
    expect(row).toBeInTheDocument()
    // "driving" label sits in the same cell as "Tissue" — verify it renders once
    expect(within(row).getAllByText(/driving/i).length).toBe(1)
  })
})
