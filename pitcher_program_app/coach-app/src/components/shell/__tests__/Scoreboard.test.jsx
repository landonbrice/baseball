import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import Scoreboard from '../Scoreboard'

const FIVE = [
  { label: 'Roster', value: '12', sub: 'pitchers' },
  { label: 'Checked In', value: '11/12', sub: '92%' },
  { label: 'Flags', value: '9 · 2 · 1', sub: 'G · Y · R' },
  { label: 'Active Block', value: 'Velo 12wk', sub: 'wk 4 of 12' },
  { label: 'Next Game', value: 'Apr 22', sub: 'vs Wash U' },
]

describe('<Scoreboard>', () => {
  it('renders all 5 cells with label, value, and sub', () => {
    render(<Scoreboard cells={FIVE} />)
    for (const cell of FIVE) {
      expect(screen.getByText(cell.label)).toBeInTheDocument()
      expect(screen.getByText(cell.value)).toBeInTheDocument()
      expect(screen.getByText(cell.sub)).toBeInTheDocument()
    }
  })

  it('renders an em-dash placeholder when value is null/undefined', () => {
    const cells = [...FIVE]
    cells[1] = { ...cells[1], value: null }
    render(<Scoreboard cells={cells} />)
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('accepts ReactNode value (e.g. inline color spans)', () => {
    const cells = [...FIVE]
    cells[2] = {
      label: 'Flags',
      value: (
        <>
          <span data-testid="g" className="text-forest">9</span>
          <span> · </span>
          <span data-testid="y" className="text-amber">2</span>
          <span> · </span>
          <span data-testid="r" className="text-crimson">1</span>
        </>
      ),
      sub: 'G · Y · R',
    }
    render(<Scoreboard cells={cells} />)
    expect(screen.getByTestId('g')).toHaveTextContent('9')
    expect(screen.getByTestId('y')).toHaveTextContent('2')
    expect(screen.getByTestId('r')).toHaveTextContent('1')
  })

  it('throws if not given exactly 5 cells', () => {
    expect(() => render(<Scoreboard cells={FIVE.slice(0, 4)} />)).toThrow(/exactly 5/i)
  })
})
