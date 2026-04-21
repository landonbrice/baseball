import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import PhaseEditorSlideOver from '../PhaseEditorSlideOver'

vi.mock('../../../api', () => ({
  updatePhase: vi.fn().mockResolvedValue({ status: 'stub' }),
  createPhase: vi.fn().mockResolvedValue({ status: 'stub' }),
  advancePhase: vi.fn().mockResolvedValue({ status: 'stub' }),
}))

vi.mock('../../shell/Toast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn(), warn: vi.fn() }),
}))

const PHASE = {
  phase_block_id: 'ph1',
  phase_name: 'Strength Block',
  start_date: '2026-04-01',
  end_date: '2026-05-15',
  emphasis: 'strength',
  notes: 'Focus on compound movements',
}

describe('<PhaseEditorSlideOver>', () => {
  it('renders "New Phase" in new mode', () => {
    render(<PhaseEditorSlideOver isNew onClose={vi.fn()} />)
    expect(screen.getByText('New Phase')).toBeInTheDocument()
  })

  it('renders "Edit Phase — {name}" in edit mode', () => {
    render(<PhaseEditorSlideOver phase={PHASE} onClose={vi.fn()} />)
    expect(screen.getByText(/Edit Phase — Strength Block/)).toBeInTheDocument()
  })

  it('pre-fills phase_name from phase prop', () => {
    render(<PhaseEditorSlideOver phase={PHASE} onClose={vi.fn()} />)
    expect(screen.getByDisplayValue('Strength Block')).toBeInTheDocument()
  })

  it('shows Advance button in edit mode', () => {
    render(<PhaseEditorSlideOver phase={PHASE} onClose={vi.fn()} />)
    expect(screen.getByRole('button', { name: /advance to next phase/i })).toBeInTheDocument()
  })

  it('shows confirmation when Advance is clicked', () => {
    render(<PhaseEditorSlideOver phase={PHASE} onClose={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /advance to next phase/i }))
    expect(screen.getByText(/End this phase and start the next/i)).toBeInTheDocument()
  })

  it('does NOT show Advance button in new mode', () => {
    render(<PhaseEditorSlideOver isNew onClose={vi.fn()} />)
    expect(screen.queryByRole('button', { name: /advance/i })).not.toBeInTheDocument()
  })
})
