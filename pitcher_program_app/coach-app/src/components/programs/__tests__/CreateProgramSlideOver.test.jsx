import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import CreateProgramSlideOver from '../CreateProgramSlideOver'

vi.mock('../../../api', () => ({
  createTeamProgram: vi.fn().mockResolvedValue({ status: 'stub' }),
}))

vi.mock('../../shell/Toast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn(), warn: vi.fn() }),
}))

const LIBRARY = [
  {
    block_template_id: 'b1',
    name: 'Velocity 12wk',
    block_type: 'throwing',
    duration_days: 84,
    content: { phases: [{ name: 'Foundation', weeks: [1, 2], effort_pct: 70 }] },
  },
]

describe('<CreateProgramSlideOver>', () => {
  it('renders header and name field', () => {
    render(<CreateProgramSlideOver library={[]} onClose={vi.fn()} />)
    expect(screen.getByText('New Program')).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/Spring Velocity/i)).toBeInTheDocument()
  })

  it('calls onClose when × button clicked', () => {
    const onClose = vi.fn()
    render(<CreateProgramSlideOver library={[]} onClose={onClose} />)
    fireEvent.click(screen.getByRole('button', { name: /close/i }))
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('shows library block in base-block dropdown', () => {
    render(<CreateProgramSlideOver library={LIBRARY} onClose={vi.fn()} />)
    expect(screen.getByText(/Velocity 12wk/)).toBeInTheDocument()
  })

  it('calls createTeamProgram and onClose on valid submit', async () => {
    const { createTeamProgram } = await import('../../../api')
    const onClose = vi.fn()
    render(<CreateProgramSlideOver library={LIBRARY} onClose={onClose} />)
    fireEvent.change(screen.getByPlaceholderText(/Spring Velocity/i), {
      target: { value: 'My Program' },
    })
    fireEvent.click(screen.getByRole('button', { name: /create program/i }))
    await waitFor(() => {
      expect(createTeamProgram).toHaveBeenCalledWith(
        expect.objectContaining({ name: 'My Program' })
      )
      expect(onClose).toHaveBeenCalled()
    })
  })

  it('does not call createTeamProgram when name is empty', async () => {
    const { createTeamProgram } = await import('../../../api')
    createTeamProgram.mockClear()
    render(<CreateProgramSlideOver library={[]} onClose={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /create program/i }))
    await waitFor(() => {
      expect(createTeamProgram).not.toHaveBeenCalled()
    })
  })
})
