import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

// useCoachApi is mocked per-test by reassigning the array of values it returns
// (active → drafts → archived → holds, in that order).
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

const patchPhaseOverrideMock = vi.fn()

vi.mock('../../api', () => ({
  patchPhaseOverride: (...args) => patchPhaseOverrideMock(...args),
}))

import PlayerPrograms from '../PlayerPrograms'

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
  patchPhaseOverrideMock.mockReset()
})

describe('<PlayerPrograms>', () => {
  it('renders all five sections with their respective payloads', () => {
    setResponses([
      res({
        programs: [
          { program_id: 'a1', domain: 'throwing', parent_template_id: 'velocity_12wk_v1',
            current_day_index: 21, held_days_count: 0 },
        ],
      }),
      res({
        drafts: [
          { program_id: 'd1', domain: 'lifting', parent_template_id: 'hypertrophy_8wk_v1',
            current_day_index: 0, held_days_count: 0 },
        ],
      }),
      res({
        programs: [
          { program_id: 'h1', domain: 'throwing', parent_template_id: 'longtoss_6wk_v1',
            current_day_index: 41, held_days_count: 2, archive_reason: 'season ended' },
        ],
      }),
      res({
        events: [
          { hold_event_id: 'he1', program_id: 'a1', hold_date: '2026-05-10', reason_code: 'red' },
        ],
      }),
    ])
    render(<PlayerPrograms pitcherId="landon_brice" />)

    // Section headings (active / drafts / archived / holds / override).
    expect(screen.getByText(/Active Programs/i)).toBeInTheDocument()
    expect(screen.getByText(/Drafts/i)).toBeInTheDocument()
    expect(screen.getByText(/Archived/i)).toBeInTheDocument()
    expect(screen.getByText(/Hold Events/i)).toBeInTheDocument()
    expect(screen.getByText(/Coach Phase Override/i)).toBeInTheDocument()

    // Per-section row content.
    expect(screen.getByText(/\[Throwing\] velocity_12wk_v1/)).toBeInTheDocument()
    expect(screen.getByText(/\[Lifting\] hypertrophy_8wk_v1/)).toBeInTheDocument()
    expect(screen.getByText(/\[Throwing\] longtoss_6wk_v1/)).toBeInTheDocument()
    expect(screen.getByText(/season ended/)).toBeInTheDocument()
    // Hold log row uses hold_date as the visible label.
    expect(screen.getByText(/2026-05-10/)).toBeInTheDocument()
  })

  it('uses the four expected API paths in order', () => {
    setResponses([res(null), res(null), res(null), res(null)])
    render(<PlayerPrograms pitcherId="landon_brice" />)
    expect(useCoachApiCalls).toEqual([
      '/api/coach/pitcher/landon_brice/programs?status=active',
      '/api/coach/pitcher/landon_brice/drafts',
      '/api/coach/pitcher/landon_brice/programs?status=archived',
      '/api/coach/pitcher/landon_brice/program-holds?days=30',
    ])
  })

  it('renders empty-state copy when sections have no rows', () => {
    setResponses([res({ programs: [] }), res({ drafts: [] }), res({ programs: [] }), res({ events: [] })])
    render(<PlayerPrograms pitcherId="landon_brice" />)
    expect(screen.getByText(/No active programs/i)).toBeInTheDocument()
    expect(screen.getByText(/No saved drafts/i)).toBeInTheDocument()
    expect(screen.getByText(/No archived programs/i)).toBeInTheDocument()
    expect(screen.getByText(/No holds in the last 30 days/i)).toBeInTheDocument()
  })

  it('renders empty arrays gracefully when API returns null/undefined data', () => {
    setResponses([res(null), res(null), res(null), res(null)])
    render(<PlayerPrograms pitcherId="landon_brice" />)
    // Sections render with empty-state copy rather than crashing.
    expect(screen.getByText(/No active programs/i)).toBeInTheDocument()
    expect(screen.getByText(/No saved drafts/i)).toBeInTheDocument()
  })

  it('shows phase-divergence pill when throwing ≠ lifting', () => {
    setResponses([res({ programs: [] }), res({ drafts: [] }), res({ programs: [] }), res({ events: [] })])
    render(
      <PlayerPrograms
        pitcherId="landon_brice"
        initialOverrides={{ throwing_phase: 'off_season', lifting_phase: 'in_season' }}
      />
    )
    expect(screen.getByTestId('phase-divergence-pill')).toBeInTheDocument()
  })

  it('hides phase-divergence pill when phases match', () => {
    setResponses([res({ programs: [] }), res({ drafts: [] }), res({ programs: [] }), res({ events: [] })])
    render(
      <PlayerPrograms
        pitcherId="landon_brice"
        initialOverrides={{ throwing_phase: 'preseason', lifting_phase: 'preseason' }}
      />
    )
    expect(screen.queryByTestId('phase-divergence-pill')).not.toBeInTheDocument()
  })

  it('PATCHes only changed fields and updates UI on save', async () => {
    setResponses([res({ programs: [] }), res({ drafts: [] }), res({ programs: [] }), res({ events: [] })])
    patchPhaseOverrideMock.mockResolvedValue({
      coach_phase_overrides: { throwing_phase: 'preseason', lifting_phase: null },
    })

    render(
      <PlayerPrograms
        pitcherId="landon_brice"
        initialOverrides={{ throwing_phase: null, lifting_phase: null }}
      />
    )

    const throwingInput = screen.getByPlaceholderText(/off_season/i)
    fireEvent.change(throwingInput, { target: { value: 'preseason' } })
    fireEvent.click(screen.getByRole('button', { name: /save override/i }))

    await waitFor(() =>
      expect(patchPhaseOverrideMock).toHaveBeenCalledWith(
        'landon_brice',
        { throwing_phase: 'preseason' },
        'tok',
      )
    )
    await waitFor(() => expect(screen.getByText(/^Saved\.$/)).toBeInTheDocument())
  })

  it('shows error message when PATCH fails', async () => {
    setResponses([res({ programs: [] }), res({ drafts: [] }), res({ programs: [] }), res({ events: [] })])
    patchPhaseOverrideMock.mockRejectedValue(new Error('boom'))

    render(<PlayerPrograms pitcherId="landon_brice" initialOverrides={{}} />)
    fireEvent.change(screen.getByPlaceholderText(/off_season/i), { target: { value: 'preseason' } })
    fireEvent.click(screen.getByRole('button', { name: /save override/i }))

    await waitFor(() => expect(screen.getByText(/boom/i)).toBeInTheDocument())
  })

  it('blocks save with "No changes" when nothing is dirty', async () => {
    setResponses([res({ programs: [] }), res({ drafts: [] }), res({ programs: [] }), res({ events: [] })])
    render(
      <PlayerPrograms
        pitcherId="landon_brice"
        initialOverrides={{ throwing_phase: 'preseason', lifting_phase: 'in_season' }}
      />
    )
    fireEvent.click(screen.getByRole('button', { name: /save override/i }))
    await waitFor(() => expect(screen.getByText(/no changes/i)).toBeInTheDocument())
    expect(patchPhaseOverrideMock).not.toHaveBeenCalled()
  })
})

describe('<PlayerSlideOver> Programs tab integration', () => {
  it('renders Programs alongside Today / Week / History tabs', async () => {
    // The slide-over fetches its own pitcher payload. Provide a stub
    // response shape that the existing tab renderers tolerate, then
    // additionally service the four PlayerPrograms requests.
    setResponses([
      res({ training_model: {}, recent_check_ins: [], current_week: [], injuries: [] }),
      // PlayerPrograms calls (when activeTab === 'programs').
      res({ programs: [] }),
      res({ drafts: [] }),
      res({ programs: [] }),
      res({ events: [] }),
    ])
    const PlayerSlideOver = (await import('../PlayerSlideOver')).default
    render(<PlayerSlideOver pitcherId="landon_brice" onClose={() => {}} />)
    // Tab labels are uppercase in the markup so use a case-insensitive match.
    expect(screen.getByRole('button', { name: /^Today$/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Week$/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^History$/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Programs$/i })).toBeInTheDocument()
  })
})
