import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import EditorialState from '../EditorialState'

describe('<EditorialState>', () => {
  it('renders loading copy and a skeleton placeholder for type=loading', () => {
    render(<EditorialState type="loading" copy="Gathering the morning check-ins…" />)
    expect(screen.getByText(/gathering the morning check-ins/i)).toBeInTheDocument()
    expect(screen.getByTestId('editorial-skeleton')).toBeInTheDocument()
  })

  it('renders empty copy without a skeleton or retry button for type=empty', () => {
    render(<EditorialState type="empty" copy="No reports filed yet." />)
    expect(screen.getByText(/no reports filed yet/i)).toBeInTheDocument()
    expect(screen.queryByTestId('editorial-skeleton')).not.toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('renders error copy and retry button for type=error', async () => {
    const onRetry = vi.fn()
    render(<EditorialState type="error" copy="Something's off on our end." retry={onRetry} />)
    expect(screen.getByText(/something's off on our end/i)).toBeInTheDocument()
    const btn = screen.getByRole('button', { name: /try again/i })
    await userEvent.click(btn)
    expect(onRetry).toHaveBeenCalledOnce()
  })

  it('omits retry button for type=error when no callback is given', () => {
    render(<EditorialState type="error" copy="x" />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
