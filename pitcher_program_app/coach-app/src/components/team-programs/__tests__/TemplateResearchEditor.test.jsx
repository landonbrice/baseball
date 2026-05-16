/**
 * Plan 8 / C3 — TemplateResearchEditor tests.
 *
 * Mocks the api module + useCoachAuth so we exercise the component's state
 * machine (load → attach/detach → save) without hitting the network.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import TemplateResearchEditor from '../TemplateResearchEditor'

vi.mock('../../../hooks/useCoachAuth', () => ({
  useCoachAuth: () => ({ getAccessToken: () => 'token' }),
}))

// Hoist-safe pattern: declare bare vi.fn()s and wrap them in the factory so
// the factory body does not reference module-scope variables (Vitest hoists
// vi.mock to the top of the file, breaking direct references — see
// CreateProgramSlideOver.test.jsx / InsightCard.test.jsx for prior art).
const fetchResearchDocsMock = vi.fn()
const patchTemplateResearchDocsMock = vi.fn()
vi.mock('../../../api', () => ({
  fetchResearchDocs: (...args) => fetchResearchDocsMock(...args),
  patchTemplateResearchDocs: (...args) => patchTemplateResearchDocsMock(...args),
}))

beforeEach(() => {
  fetchResearchDocsMock.mockReset()
  patchTemplateResearchDocsMock.mockReset()
})

describe('TemplateResearchEditor', () => {
  it('loads available docs and shows currently-attached', async () => {
    fetchResearchDocsMock.mockResolvedValue({
      docs: [
        { id: 'a', title: 'Alpha', summary: 's', applies_to: [], priority: 'standard' },
        { id: 'b', title: 'Beta', summary: 's', applies_to: [], priority: 'high' },
      ],
    })
    render(
      <TemplateResearchEditor
        template={{ block_template_id: 'tpl_a', name: 'T A', research_doc_ids: ['a'] }}
        onClose={() => {}}
        onSaved={() => {}}
      />
    )
    await waitFor(() => expect(screen.getByText('Alpha')).toBeInTheDocument())
    // Attached column has Alpha; Available has Beta.
    expect(screen.getByTestId('attach-b')).toBeInTheDocument()
    expect(screen.getByTestId('detach-a')).toBeInTheDocument()
  })

  it('attach moves a doc from Available to Attached', async () => {
    fetchResearchDocsMock.mockResolvedValue({
      docs: [{ id: 'a', title: 'Alpha', summary: 's' }],
    })
    render(
      <TemplateResearchEditor
        template={{ block_template_id: 'tpl_a', name: 'T A', research_doc_ids: [] }}
        onClose={() => {}}
        onSaved={() => {}}
      />
    )
    await waitFor(() => expect(screen.getByTestId('attach-a')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('attach-a'))
    expect(screen.getByTestId('detach-a')).toBeInTheDocument()
  })

  it('save calls patch endpoint with the current attached list', async () => {
    fetchResearchDocsMock.mockResolvedValue({
      docs: [{ id: 'a', title: 'Alpha' }, { id: 'b', title: 'Beta' }],
    })
    patchTemplateResearchDocsMock.mockResolvedValue({
      template: { block_template_id: 'tpl_a', research_doc_ids: ['a'] },
    })
    const onSaved = vi.fn()
    render(
      <TemplateResearchEditor
        template={{ block_template_id: 'tpl_a', name: 'T A', research_doc_ids: ['a'] }}
        onClose={() => {}}
        onSaved={onSaved}
      />
    )
    await waitFor(() => screen.getByText('Alpha'))
    fireEvent.click(screen.getByTestId('research-save'))
    await waitFor(() => expect(patchTemplateResearchDocsMock).toHaveBeenCalledWith(
      'tpl_a', ['a'], 'token'
    ))
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
  })

  it('shows error and stays open when patch fails', async () => {
    fetchResearchDocsMock.mockResolvedValue({
      docs: [{ id: 'a', title: 'Alpha' }],
    })
    patchTemplateResearchDocsMock.mockRejectedValue(new Error('boom'))
    const onClose = vi.fn()
    render(
      <TemplateResearchEditor
        template={{ block_template_id: 'tpl_a', name: 'T A', research_doc_ids: ['a'] }}
        onClose={onClose}
        onSaved={() => {}}
      />
    )
    await waitFor(() => screen.getByText('Alpha'))
    fireEvent.click(screen.getByTestId('research-save'))
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(onClose).not.toHaveBeenCalled()
  })
})
