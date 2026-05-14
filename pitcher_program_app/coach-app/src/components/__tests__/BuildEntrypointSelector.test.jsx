/**
 * Plan 7 / C4: BuildEntrypointSelector contract tests.
 *
 * Pure UI — verifies the three options render and pick callbacks fire with
 * the correct selector ids. CreateProgramSlideOver.test.jsx covers the
 * mode→BuilderSlideOver propagation; this file locks the leaf component.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import BuildEntrypointSelector from '../BuildEntrypointSelector'

describe('<BuildEntrypointSelector>', () => {
  it('renders 3 build options', () => {
    render(<BuildEntrypointSelector onPick={vi.fn()} onClose={vi.fn()} />)
    expect(screen.getByText(/Build a team program/i)).toBeInTheDocument()
    expect(screen.getByText(/Build for a specific pitcher/i)).toBeInTheDocument()
    expect(screen.getByText(/Author a new template/i)).toBeInTheDocument()
  })

  it('calls onPick with team_personalize on first button', () => {
    const onPick = vi.fn()
    render(<BuildEntrypointSelector onPick={onPick} onClose={vi.fn()} />)
    fireEvent.click(screen.getByTestId('entrypoint-team_personalize'))
    expect(onPick).toHaveBeenCalledWith({ mode: 'team_personalize' })
  })

  it('calls onPick with personalize_for_pitcher on second button', () => {
    const onPick = vi.fn()
    render(<BuildEntrypointSelector onPick={onPick} onClose={vi.fn()} />)
    fireEvent.click(screen.getByTestId('entrypoint-personalize_for_pitcher'))
    expect(onPick).toHaveBeenCalledWith({ mode: 'personalize_for_pitcher' })
  })

  it('calls onPick with authoring on third button', () => {
    const onPick = vi.fn()
    render(<BuildEntrypointSelector onPick={onPick} onClose={vi.fn()} />)
    fireEvent.click(screen.getByTestId('entrypoint-authoring'))
    expect(onPick).toHaveBeenCalledWith({ mode: 'authoring' })
  })

  it('Close button fires onClose', () => {
    const onClose = vi.fn()
    render(<BuildEntrypointSelector onPick={vi.fn()} onClose={onClose} />)
    fireEvent.click(screen.getByRole('button', { name: /Close/i }))
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('ESC key fires onClose', () => {
    const onClose = vi.fn()
    render(<BuildEntrypointSelector onPick={vi.fn()} onClose={onClose} />)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledOnce()
  })
})
