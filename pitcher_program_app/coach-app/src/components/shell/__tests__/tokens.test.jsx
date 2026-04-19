import { describe, it, expect, beforeAll } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import { render, screen } from '@testing-library/react'
import Lede from '../Lede'

const TOKENS = path.resolve(__dirname, '../../../styles/tokens.css')

const REQUIRED_TOKENS = [
  '--font-serif', '--font-ui',
  '--color-maroon', '--color-maroon-ink', '--color-rose',
  '--color-crimson', '--color-amber', '--color-forest',
  '--color-cream', '--color-cream-dark', '--color-parchment', '--color-bone', '--color-hover',
  '--color-charcoal', '--color-graphite', '--color-subtle', '--color-muted', '--color-ghost',
  '--text-display', '--text-h1', '--text-h2', '--text-h3',
  '--text-kicker', '--text-eyebrow',
  '--text-body', '--text-body-sm', '--text-meta', '--text-micro',
]

let css = ''
beforeAll(() => { css = fs.readFileSync(TOKENS, 'utf8') })

describe('tokens.css contract', () => {
  it.each(REQUIRED_TOKENS)('declares %s', (token) => {
    expect(css).toContain(token + ':')
  })

  it('has all four @font-face declarations for Source Serif 4', () => {
    const matches = css.match(/@font-face/g) || []
    expect(matches.length).toBeGreaterThanOrEqual(4)
  })
})

describe('<Lede>', () => {
  it('renders children inside a serif italic block', () => {
    render(<Lede>Wade is back to good after Tuesday's outing.</Lede>)
    const node = screen.getByText(/wade is back to good/i).closest('div')
    expect(node.className).toContain('font-serif')
    expect(node.className).toContain('italic')
    expect(node.className).toContain('border-maroon')
  })

  it('respects maxWidth prop', () => {
    render(<Lede maxWidth="500px">x</Lede>)
    const node = screen.getByText('x').closest('div')
    expect(node.style.maxWidth).toBe('500px')
  })
})
