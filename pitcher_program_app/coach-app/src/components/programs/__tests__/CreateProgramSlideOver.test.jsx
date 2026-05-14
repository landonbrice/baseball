/**
 * Plan 7 / C4: CreateProgramSlideOver state-machine tests.
 *
 * Verifies the three-step flow:
 *   selector → (optional) pitcher picker → BuilderSlideOver
 *
 * The shared BuilderSlideOver is mocked so we can assert on the props the
 * adapter forwards (interview_mode, pitcherIdForCoach) without exercising
 * its internal state machine in this suite.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

// useCoachApi is mocked per-test (PitcherPicker's `/api/coach/team/overview` call).
const useCoachApiResponses = []
let lastUseCoachApiPath = null

vi.mock('../../../hooks/useApi', () => ({
  useCoachApi: vi.fn((path) => {
    lastUseCoachApiPath = path
    return (
      useCoachApiResponses.shift() || {
        data: null,
        loading: false,
        error: null,
        refetch: vi.fn(),
      }
    )
  }),
}))

vi.mock('../../../hooks/useCoachAuth', () => ({
  useCoachAuth: () => ({ getAccessToken: () => 'tok' }),
}))

// Capture the props BuilderSlideOver was rendered with.
const builderSlideOverProps = vi.fn()
vi.mock('@shared/builder/BuilderSlideOver.jsx', () => ({
  default: (props) => {
    builderSlideOverProps(props)
    return <div data-testid="builder-mock">BuilderSlideOver mock</div>
  },
}))

import CreateProgramSlideOver from '../CreateProgramSlideOver'

function setUseCoachApiResponses(responses) {
  useCoachApiResponses.length = 0
  responses.forEach((r) => useCoachApiResponses.push(r))
}

function res(data) {
  return { data, loading: false, error: null, refetch: vi.fn() }
}

beforeEach(() => {
  useCoachApiResponses.length = 0
  lastUseCoachApiPath = null
  builderSlideOverProps.mockClear()
})

describe('<CreateProgramSlideOver> Plan 7 / C4', () => {
  it('renders the BuildEntrypointSelector first (3 build options)', () => {
    render(<CreateProgramSlideOver onClose={vi.fn()} />)
    expect(screen.getByRole('heading', { name: /Build a Program/i })).toBeInTheDocument()
    expect(screen.getByText(/Build a team program/i)).toBeInTheDocument()
    expect(screen.getByText(/Build for a specific pitcher/i)).toBeInTheDocument()
    expect(screen.getByText(/Author a new template/i)).toBeInTheDocument()
    // BuilderSlideOver is NOT mounted on the selector screen.
    expect(builderSlideOverProps).not.toHaveBeenCalled()
  })

  it('picking "team program" jumps straight to BuilderSlideOver with interview_mode=team_personalize', () => {
    render(<CreateProgramSlideOver onClose={vi.fn()} />)
    fireEvent.click(screen.getByTestId('entrypoint-team_personalize'))

    expect(screen.getByTestId('builder-mock')).toBeInTheDocument()
    expect(builderSlideOverProps).toHaveBeenCalledTimes(1)
    const props = builderSlideOverProps.mock.calls[0][0]
    expect(props.interview_mode).toBe('team_personalize')
    expect(props.pitcherIdForCoach).toBeNull()
    // The API adapter is wired with the six coach builder fns.
    expect(typeof props.api.fetchCandidates).toBe('function')
    expect(typeof props.api.sendTurn).toBe('function')
    expect(typeof props.api.finalize).toBe('function')
    expect(typeof props.api.activateProgram).toBe('function')
    expect(typeof props.api.archiveProgram).toBe('function')
    expect(typeof props.api.interpretGoal).toBe('function')
  })

  it('picking "authoring" jumps straight to BuilderSlideOver with interview_mode=authoring', () => {
    render(<CreateProgramSlideOver onClose={vi.fn()} />)
    fireEvent.click(screen.getByTestId('entrypoint-authoring'))

    expect(screen.getByTestId('builder-mock')).toBeInTheDocument()
    const props = builderSlideOverProps.mock.calls[0][0]
    expect(props.interview_mode).toBe('authoring')
    expect(props.pitcherIdForCoach).toBeNull()
  })

  it('picking "personalize" routes through PitcherPicker → BuilderSlideOver with pitcherIdForCoach', () => {
    setUseCoachApiResponses([
      res({
        roster: [
          { pitcher_id: 'landon_brice', name: 'Landon Brice', role: 'Starter (7-day)' },
          { pitcher_id: 'pitcher_benner_001', name: 'Preston Benner', role: 'Starter (7-day)' },
        ],
      }),
    ])

    render(<CreateProgramSlideOver onClose={vi.fn()} />)
    fireEvent.click(screen.getByTestId('entrypoint-personalize_for_pitcher'))

    // Now we're on the pitcher picker. BuilderSlideOver still not mounted.
    expect(screen.getByRole('heading', { name: /Pick a Pitcher/i })).toBeInTheDocument()
    expect(lastUseCoachApiPath).toBe('/api/coach/team/overview')
    expect(builderSlideOverProps).not.toHaveBeenCalled()

    // Roster rows render.
    expect(screen.getByText('Landon Brice')).toBeInTheDocument()
    expect(screen.getByText('Preston Benner')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('pick-pitcher-landon_brice'))

    // BuilderSlideOver mounts with interview_mode='personalize' + pitcherIdForCoach='landon_brice'.
    expect(screen.getByTestId('builder-mock')).toBeInTheDocument()
    const props = builderSlideOverProps.mock.calls[0][0]
    expect(props.interview_mode).toBe('personalize')
    expect(props.pitcherIdForCoach).toBe('landon_brice')
  })

  it('PitcherPicker Back button returns to the selector', () => {
    setUseCoachApiResponses([res({ roster: [] })])
    render(<CreateProgramSlideOver onClose={vi.fn()} />)
    fireEvent.click(screen.getByTestId('entrypoint-personalize_for_pitcher'))
    expect(screen.getByRole('heading', { name: /Pick a Pitcher/i })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Back/i }))
    expect(screen.getByRole('heading', { name: /Build a Program/i })).toBeInTheDocument()
  })

  it('selector × button calls onClose without entering the picker', () => {
    const onClose = vi.fn()
    render(<CreateProgramSlideOver onClose={onClose} />)
    fireEvent.click(screen.getByRole('button', { name: /Close/i }))
    expect(onClose).toHaveBeenCalledOnce()
  })
})
