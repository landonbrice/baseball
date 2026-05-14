import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

// useCoachApi is mocked per-test by reassigning the array of values it
// returns in fetch order: (1) /team-programs/active, (2) /coach/programs/templates,
// (3) /api/coach/programs/recent-player-built?limit=20
const useCoachApiCalls = []
const useCoachApiResponses = []

vi.mock('../../hooks/useApi', () => ({
  useCoachApi: vi.fn((path) => {
    useCoachApiCalls.push(path)
    return (
      useCoachApiResponses[useCoachApiCalls.length - 1] || {
        data: null,
        loading: false,
        error: null,
        refetch: vi.fn(),
      }
    )
  }),
}))

vi.mock('../../hooks/useCoachAuth', () => ({
  useCoachAuth: () => ({ getAccessToken: () => 'tok' }),
}))

vi.mock('../../components/shell/Toast', () => ({
  useToast: () => ({
    success: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  }),
}))

import TeamPrograms from '../TeamPrograms'

function setResponses(responses) {
  useCoachApiResponses.length = 0
  responses.forEach(r => useCoachApiResponses.push(r))
}

function res(data) {
  return { data, loading: false, error: null, refetch: vi.fn() }
}

beforeEach(() => {
  useCoachApiCalls.length = 0
  useCoachApiResponses.length = 0
})

describe('<TeamPrograms>', () => {
  it('renders all five page sections in order', () => {
    setResponses([
      res({
        blocks: [
          {
            block_id: 'b1',
            block_type: 'throwing',
            block_template_id: 'velocity_12wk_v1',
            start_date: '2026-05-01',
            duration_days: 84,
            status: 'active',
          },
        ],
      }),
      res({
        templates: [
          {
            block_template_id: 'velocity_12wk_v1',
            name: 'Velocity 12 Week',
            domain: 'throwing',
            duration_range_weeks: [10, 14],
            implied_phase: 'off_season',
          },
        ],
      }),
      res({
        programs: [
          {
            program_id: 'p1',
            pitcher_id: 'landon_brice',
            pitcher_name: 'Landon Brice',
            parent_template_id: 'velocity_12wk_v1',
            domain: 'throwing',
            status: 'active',
            created_at: '2026-05-12T10:00:00Z',
            created_by_role: 'pitcher',
          },
        ],
      }),
    ])
    render(<TeamPrograms />)

    // Masthead + actionSlot
    expect(screen.getByRole('heading', { name: /Team Programs/i })).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /\+ Build Program/i }),
    ).toBeInTheDocument()

    // Scoreboard cells
    expect(screen.getByText(/Active Blocks/i)).toBeInTheDocument()
    expect(screen.getByText(/Templates$/i)).toBeInTheDocument()

    // Three body sections
    expect(screen.getByText(/^Active Programs$/i)).toBeInTheDocument()
    expect(screen.getByText(/^Library$/i)).toBeInTheDocument()
    expect(screen.getByText(/^Recent Player-Built Programs$/i)).toBeInTheDocument()
  })

  it('library section populates from /api/coach/programs/templates', () => {
    setResponses([
      res({ blocks: [] }),
      res({
        templates: [
          {
            block_template_id: 'longtoss_6wk_v1',
            name: 'Long Toss 6 Week',
            domain: 'throwing',
            duration_range_weeks: [4, 8],
            implied_phase: 'preseason',
          },
        ],
      }),
      res({ programs: [] }),
    ])
    render(<TeamPrograms />)

    // Verify the templates path was requested (coach mirror — see
    // api/coach_routes.py::coach_get_program_templates; the pitcher-facing
    // /api/programs/templates rejects Supabase Bearer JWTs).
    expect(useCoachApiCalls).toContain('/api/coach/programs/templates')
    // Template name + duration range render.
    expect(screen.getByText(/Long Toss 6 Week/)).toBeInTheDocument()
    expect(screen.getByText(/4–8wk/)).toBeInTheDocument()
    // Each template row has a Build button (in addition to the Masthead one).
    const buildButtons = screen.getAllByRole('button', { name: /^Build$/ })
    expect(buildButtons).toHaveLength(1)
  })

  it('recent player-built strip renders rows from coach endpoint', () => {
    setResponses([
      res({ blocks: [] }),
      res({ templates: [] }),
      res({
        programs: [
          {
            program_id: 'p1',
            pitcher_id: 'landon_brice',
            pitcher_name: 'Landon Brice',
            parent_template_id: 'velocity_12wk_v1',
            domain: 'throwing',
            status: 'active',
            created_at: '2026-05-12T10:00:00Z',
          },
          {
            program_id: 'p2',
            pitcher_id: 'pitcher_benner_001',
            pitcher_name: 'Preston Benner',
            parent_template_id: 'longtoss_6wk_v1',
            domain: 'throwing',
            status: 'draft',
            created_at: '2026-05-11T09:00:00Z',
          },
        ],
      }),
    ])
    render(<TeamPrograms />)

    // Endpoint was hit with the default limit.
    expect(useCoachApiCalls).toContain(
      '/api/coach/programs/recent-player-built?limit=20',
    )

    // Both rows render with their pitcher names + template ids.
    expect(screen.getByText(/Landon Brice/)).toBeInTheDocument()
    expect(screen.getByText(/Preston Benner/)).toBeInTheDocument()
    expect(screen.getAllByText(/velocity_12wk_v1/).length).toBeGreaterThan(0)
    expect(screen.getByText(/longtoss_6wk_v1/)).toBeInTheDocument()
    // Status pills render.
    expect(screen.getByText(/^active$/i)).toBeInTheDocument()
    expect(screen.getByText(/^draft$/i)).toBeInTheDocument()
  })

  it('"+ Build Program" Masthead button opens BuildEntrypointSelector', () => {
    setResponses([
      res({ blocks: [] }),
      res({ templates: [] }),
      res({ programs: [] }),
    ])
    render(<TeamPrograms />)

    // Selector not initially mounted — its "Build a Program" heading is absent.
    expect(
      screen.queryByRole('heading', { name: /Build a Program/i }),
    ).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /\+ Build Program/i }))

    // Plan 7 / C4: CreateProgramSlideOver now renders the BuildEntrypointSelector
    // first. The three build options are visible.
    expect(
      screen.getByRole('heading', { name: /Build a Program/i }),
    ).toBeInTheDocument()
    expect(screen.getByText(/Build a team program/i)).toBeInTheDocument()
    expect(screen.getByText(/Build for a specific pitcher/i)).toBeInTheDocument()
    expect(screen.getByText(/Author a new template/i)).toBeInTheDocument()
  })
})
