import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import TierLabel from '../TierLabel'

describe('TierLabel', () => {
  it('renders nothing for default tier (Standard, non-provisional)', () => {
    const { container } = render(<TierLabel tier={2} baselineState="full" />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing when tier is missing', () => {
    const { container } = render(<TierLabel tier={null} baselineState="full" />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders Sensitive for tier 1', () => {
    render(<TierLabel tier={1} baselineState="full" />)
    expect(screen.getByText('Sensitive')).toBeInTheDocument()
  })

  it('renders Resilient for tier 3', () => {
    render(<TierLabel tier={3} baselineState="full" />)
    expect(screen.getByText('Resilient')).toBeInTheDocument()
  })

  it('renders (provisional) suffix for provisional Standard', () => {
    render(<TierLabel tier={2} baselineState="provisional" />)
    expect(screen.getByText(/Standard \(provisional\)/)).toBeInTheDocument()
  })

  it('renders (provisional) suffix for provisional Sensitive', () => {
    render(<TierLabel tier={1} baselineState="provisional" />)
    expect(screen.getByText(/Sensitive \(provisional\)/)).toBeInTheDocument()
  })

  it('tooltip explains the concept', () => {
    render(<TierLabel tier={1} baselineState="full" />)
    const el = screen.getByText('Sensitive')
    expect(el.getAttribute('title')).toMatch(/tolerance/i)
  })
})
