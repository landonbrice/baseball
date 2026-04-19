import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import FlagPill from '../FlagPill'

describe('<FlagPill>', () => {
  it('renders RED with crimson background and white text', () => {
    const { container } = render(<FlagPill level="red" />)
    const pill = container.firstChild
    expect(pill).toHaveTextContent(/red/i)
    expect(pill.className).toContain('bg-crimson')
    expect(pill.className).toContain('text-bone')
  })

  it('renders YELLOW with amber background and charcoal text', () => {
    const { container } = render(<FlagPill level="yellow" />)
    expect(container.firstChild.className).toContain('bg-amber')
    expect(container.firstChild.className).toContain('text-charcoal')
    expect(screen.getByText(/yellow/i)).toBeInTheDocument()
  })

  it('renders GREEN with forest background and white text', () => {
    const { container } = render(<FlagPill level="green" />)
    expect(container.firstChild.className).toContain('bg-forest')
    expect(container.firstChild.className).toContain('text-bone')
    expect(screen.getByText(/green/i)).toBeInTheDocument()
  })

  it('renders PENDING with transparent background and ghost border', () => {
    const { container } = render(<FlagPill level="pending" />)
    expect(container.firstChild.className).toContain('bg-transparent')
    expect(container.firstChild.className).toContain('border-ghost')
    expect(screen.getByText(/pending/i)).toBeInTheDocument()
  })
})
