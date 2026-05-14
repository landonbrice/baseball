import { describe, it, expect } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import PhaseTimeline, { phaseToTemplatePhaseIds } from '../PhaseTimeline'

const PHASES = [
  {
    phase_block_id: 'ph_off',
    phase_name: 'Fall GPP',
    emphasis: 'hypertrophy',
    start_date: '2025-10-01',
    end_date: '2025-10-28',
  },
  {
    phase_block_id: 'ph_pre',
    phase_name: 'Preseason Ramp',
    emphasis: 'maintenance',
    start_date: '2026-02-08',
    end_date: '2026-02-28',
  },
  {
    phase_block_id: 'ph_in',
    phase_name: 'In-Season',
    emphasis: 'maintenance',
    start_date: '2026-03-01',
    end_date: '2026-05-31',
  },
]

const TEMPLATES = [
  {
    block_template_id: 'tpl_a',
    name: 'Hypertrophy 8wk',
    compatible_phases: ['off_season'],
  },
  {
    block_template_id: 'tpl_b',
    name: 'Velocity Ramp 6wk',
    compatible_phases: ['preseason', 'off_season'],
  },
  {
    block_template_id: 'tpl_c',
    name: 'In-Season Maintenance',
    compatible_phases: ['in_season'],
  },
]

describe('phaseToTemplatePhaseIds()', () => {
  it('maps phase_name "In-Season" to both in_season variants', () => {
    expect(phaseToTemplatePhaseIds({ phase_name: 'In-Season' })).toEqual([
      'in_season',
      'in_season_active',
    ])
  })

  it('maps phase_name "Preseason Ramp" to preseason', () => {
    expect(phaseToTemplatePhaseIds({ phase_name: 'Preseason Ramp', emphasis: 'maintenance' })).toEqual([
      'preseason',
    ])
  })

  it('falls back to emphasis when name has no match', () => {
    expect(phaseToTemplatePhaseIds({ phase_name: 'Block A', emphasis: 'strength' })).toEqual([
      'off_season',
    ])
    expect(phaseToTemplatePhaseIds({ phase_name: 'Block B', emphasis: 'power' })).toEqual([
      'preseason',
    ])
  })

  it('returns empty array when neither name nor emphasis match', () => {
    expect(phaseToTemplatePhaseIds({ phase_name: 'X', emphasis: 'unknown' })).toEqual([])
    expect(phaseToTemplatePhaseIds(null)).toEqual([])
  })
})

describe('<PhaseTimeline> Templates column', () => {
  it('renders templates compatible with each phase row', () => {
    render(<PhaseTimeline phases={PHASES} templates={TEMPLATES} />)

    // off_season phase ("Fall GPP") gets the off_season-only template AND the
    // multi-phase template that includes off_season.
    const offCard = screen.getByText('Fall GPP').closest('button')
    expect(within(offCard).getByText('Hypertrophy 8wk')).toBeInTheDocument()
    expect(within(offCard).getByText('Velocity Ramp 6wk')).toBeInTheDocument()
    expect(within(offCard).queryByText('In-Season Maintenance')).not.toBeInTheDocument()

    // preseason phase ("Preseason Ramp") gets the multi-phase template only.
    const preCard = screen.getByText('Preseason Ramp').closest('button')
    expect(within(preCard).getByText('Velocity Ramp 6wk')).toBeInTheDocument()
    expect(within(preCard).queryByText('Hypertrophy 8wk')).not.toBeInTheDocument()

    // in_season phase ("In-Season") gets only the in_season-keyed template.
    const inCard = screen.getByText('In-Season').closest('button')
    expect(within(inCard).getByText('In-Season Maintenance')).toBeInTheDocument()
    expect(within(inCard).queryByText('Hypertrophy 8wk')).not.toBeInTheDocument()
  })

  it('renders no chips when no templates are compatible with a phase', () => {
    render(<PhaseTimeline phases={PHASES} templates={[]} />)
    // No "Templates" eyebrow should appear when the matched list is empty.
    expect(screen.queryByText('Templates')).not.toBeInTheDocument()
  })
})
