/**
 * BuilderSlideOver — state machine + API glue tests (Plan 6 / B3).
 *
 * Mocks ../../api so we exercise pure UI orchestration without touching fetch.
 * Also mocks ../../App to provide a stable useAuth context.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import BuilderSlideOver, { BUILDER_STATES } from '../BuilderSlideOver';

// ---- Mocks ----
vi.mock('../../App', () => ({
  useAuth: () => ({ pitcherId: 'landon_brice', initData: 'fake-init-data' }),
}));

vi.mock('../../api', () => ({
  fetchBuilderCandidates: vi.fn(),
  sendBuilderTurn: vi.fn(),
  finalizeBuilder: vi.fn(),
  activateProgram: vi.fn(),
  archiveProgram: vi.fn(),
  interpretGoal: vi.fn(),
}));

import {
  fetchBuilderCandidates,
  sendBuilderTurn,
  finalizeBuilder,
  activateProgram,
  archiveProgram,
  interpretGoal,
} from '../../api';

const PROG = {
  program_id: 'prog-1',
  pitcher_id: 'landon_brice',
  domain: 'throwing',
  status: 'draft',
  start_date: '2026-05-15',
  nominal_end_date: '2026-08-07',
  generated_schedule_json: {
    scaffold_kind: 'calendar_relative_repeating_7day',
    days: [
      { day_index: 0, template_key: 'day_0', date: '2026-05-15' },
      { day_index: 1, template_key: 'day_1', date: '2026-05-16' },
      { day_index: 2, template_key: 'day_2', date: '2026-05-17' },
    ],
  },
};

beforeEach(() => {
  vi.clearAllMocks();
});

// ---------- State A: INPUTS ----------

describe('BuilderSlideOver: Inputs state', () => {
  it('renders the inputs form with default chips selected', () => {
    render(<BuilderSlideOver onClose={() => {}} />);
    expect(screen.getByTestId('inputs-form')).toBeInTheDocument();
    expect(screen.getByText('Throwing')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByText('12 wk')).toHaveAttribute('aria-pressed', 'true');
  });

  it('blocks Continue when goal is empty', async () => {
    const user = userEvent.setup();
    render(<BuilderSlideOver onClose={() => {}} />);
    await user.click(screen.getByText('Continue'));
    expect(screen.getByRole('alert')).toHaveTextContent(/goal/i);
    expect(fetchBuilderCandidates).not.toHaveBeenCalled();
  });

  it('shows inline error and stays on inputs when 0 candidates returned', async () => {
    const user = userEvent.setup();
    fetchBuilderCandidates.mockResolvedValue({ session_id: 'sess-1', candidates: [] });
    render(<BuilderSlideOver onClose={() => {}} />);
    await user.click(screen.getByText('Velocity'));
    await user.click(screen.getByText('Continue'));
    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/no templates match/i);
    });
    expect(screen.getByTestId('inputs-form')).toBeInTheDocument();
  });

  it('transitions to socratic on successful candidates fetch and kicks off first turn', async () => {
    const user = userEvent.setup();
    fetchBuilderCandidates.mockResolvedValue({
      session_id: 'sess-1',
      candidates: [{ block_template_id: 'tpl_a', name: 'A' }],
    });
    sendBuilderTurn.mockResolvedValue({ kind: 'question', text: 'What is your top priority?' });
    render(<BuilderSlideOver onClose={() => {}} />);
    await user.click(screen.getByText('Velocity'));
    await user.click(screen.getByText('Continue'));
    await waitFor(() => {
      expect(screen.getByTestId('socratic-chat')).toBeInTheDocument();
    });
    expect(sendBuilderTurn).toHaveBeenCalledWith('sess-1', '', 'fake-init-data');
    expect(screen.getByText('What is your top priority?')).toBeInTheDocument();
  });

  it('passes the full envelope (domain, goal, duration, phase, hard_constraints) to /candidates', async () => {
    const user = userEvent.setup();
    fetchBuilderCandidates.mockResolvedValue({
      session_id: 'sess-1',
      candidates: [{ block_template_id: 'tpl_a' }],
    });
    sendBuilderTurn.mockResolvedValue({ kind: 'question', text: '?' });
    render(<BuilderSlideOver onClose={() => {}} />);
    // Stay on Throwing (Lifting has no goals seeded yet)
    await user.click(screen.getByText('8 wk'));
    await user.click(screen.getByText('Preseason'));
    await user.click(screen.getByText('No max effort'));
    await user.click(screen.getByText('Off-season base'));
    await user.click(screen.getByText('Continue'));
    await waitFor(() => expect(fetchBuilderCandidates).toHaveBeenCalled());
    expect(fetchBuilderCandidates.mock.calls[0][0]).toEqual({
      domain: 'throwing',
      goal: 'offseason_base',
      duration_weeks: 8,
      effective_phase: 'preseason',
      hard_constraints: ['no_max_effort'],
    });
  });

  it('shows "coming soon" for Lifting and disables Continue with empty goal', async () => {
    const user = userEvent.setup();
    render(<BuilderSlideOver onClose={() => {}} />);
    await user.click(screen.getByText('Lifting'));
    expect(screen.getByTestId('goal-domain-unsupported')).toBeInTheDocument();
    expect(screen.queryByTestId('goal-chips')).not.toBeInTheDocument();
    await user.click(screen.getByText('Continue'));
    expect(screen.getByRole('alert')).toHaveTextContent(/goal/i);
    expect(fetchBuilderCandidates).not.toHaveBeenCalled();
  });

  it('clears goal selection when domain switches', async () => {
    const user = userEvent.setup();
    fetchBuilderCandidates.mockResolvedValue({
      session_id: 'sess-1', candidates: [{ block_template_id: 'tpl_a' }],
    });
    render(<BuilderSlideOver onClose={() => {}} />);
    await user.click(screen.getByText('Velocity'));  // pick throwing goal
    expect(screen.getByText('Velocity')).toHaveAttribute('aria-pressed', 'true');
    await user.click(screen.getByText('Lifting'));    // switch domain
    await user.click(screen.getByText('Throwing'));   // switch back
    // Goal must be cleared — Continue with no selection should error
    await user.click(screen.getByText('Continue'));
    expect(screen.getByRole('alert')).toHaveTextContent(/goal/i);
    expect(fetchBuilderCandidates).not.toHaveBeenCalled();
  });
});

// ---------- State B: SOCRATIC ----------

describe('BuilderSlideOver: Socratic state', () => {
  async function arriveAtSocratic(user) {
    fetchBuilderCandidates.mockResolvedValue({
      session_id: 'sess-1',
      candidates: [{ block_template_id: 'tpl_a' }],
    });
    sendBuilderTurn.mockResolvedValueOnce({ kind: 'question', text: 'Q1' });
    await user.click(screen.getByText('Velocity'));
    await user.click(screen.getByText('Continue'));
    // Wait for the kickoff response to settle (Q1 visible → input enabled)
    await waitFor(() => expect(screen.getByText('Q1')).toBeInTheDocument());
  }

  it("loops /turn with user answers until {kind: 'ready'}", async () => {
    const user = userEvent.setup();
    render(<BuilderSlideOver onClose={() => {}} />);
    await arriveAtSocratic(user);

    sendBuilderTurn.mockResolvedValueOnce({ kind: 'question', text: 'Q2' });
    await user.type(screen.getByLabelText('Chat input'), 'velocity');
    await user.click(screen.getByText('Send'));
    await waitFor(() => expect(screen.getByText('Q2')).toBeInTheDocument());

    sendBuilderTurn.mockResolvedValueOnce({
      kind: 'ready',
      chosen_template_id: 'tpl_a',
      tuned_spec: { weeks: 12 },
    });
    await user.type(screen.getByLabelText('Chat input'), '12 weeks please');
    await user.click(screen.getByText('Send'));
    await waitFor(() => {
      expect(screen.getByText('See the program')).toBeInTheDocument();
    });
    // Input + I-don't-know hidden when ready
    expect(screen.queryByLabelText('Chat input')).not.toBeInTheDocument();
    expect(screen.queryByText(/I don't know/i)).not.toBeInTheDocument();
  });

  it("'I don't know — you decide' sends the canonical message", async () => {
    const user = userEvent.setup();
    render(<BuilderSlideOver onClose={() => {}} />);
    await arriveAtSocratic(user);

    sendBuilderTurn.mockResolvedValueOnce({ kind: 'question', text: 'Q2' });
    await user.click(screen.getByText(/I don't know/i));
    await waitFor(() => {
      const calls = sendBuilderTurn.mock.calls;
      const second = calls[1];  // [0] was the kickoff empty turn
      expect(second[1]).toMatch(/I don't know/);
    });
  });

  it('finalizing transitions to preview with program + citations', async () => {
    const user = userEvent.setup();
    render(<BuilderSlideOver onClose={() => {}} />);
    await arriveAtSocratic(user);

    sendBuilderTurn.mockResolvedValueOnce({
      kind: 'ready',
      chosen_template_id: 'tpl_a',
      tuned_spec: { weeks: 12 },
    });
    await user.type(screen.getByLabelText('Chat input'), 'ready');
    await user.click(screen.getByText('Send'));
    await waitFor(() => expect(screen.getByText('See the program')).toBeInTheDocument());

    finalizeBuilder.mockResolvedValue({
      program: PROG,
      citations: [{ id: 'velocity_arc', title: 'Velocity Programming', summary: 'why' }],
    });
    await user.click(screen.getByText('See the program'));
    await waitFor(() => expect(screen.getByTestId('preview-pane')).toBeInTheDocument());
    expect(screen.getByTestId('citations')).toBeInTheDocument();
    expect(screen.getByText('Velocity Programming')).toBeInTheDocument();
  });
});

// ---------- State C: PREVIEW ----------

describe('BuilderSlideOver: Preview state', () => {
  async function arriveAtPreview(user, { withCitations = true } = {}) {
    fetchBuilderCandidates.mockResolvedValue({
      session_id: 'sess-1', candidates: [{ block_template_id: 'tpl_a' }],
    });
    sendBuilderTurn
      .mockResolvedValueOnce({ kind: 'question', text: 'Q1' })  // kickoff
      .mockResolvedValueOnce({
        kind: 'ready', chosen_template_id: 'tpl_a', tuned_spec: { weeks: 12 },
      });  // after user types
    finalizeBuilder.mockResolvedValue({
      program: PROG,
      citations: withCitations ? [{ id: 'c1', title: 'Cite', summary: 's' }] : [],
    });

    await user.click(screen.getByText('Velocity'));
    await user.click(screen.getByText('Continue'));
    // Wait for the kickoff response to settle (Q1 visible → input enabled)
    await waitFor(() => expect(screen.getByText('Q1')).toBeInTheDocument());
    await user.type(screen.getByLabelText('Chat input'), 'ready');
    await user.click(screen.getByText('Send'));
    await waitFor(() => expect(screen.getByText('See the program')).toBeInTheDocument());
    await user.click(screen.getByText('See the program'));
    await waitFor(() => expect(screen.getByTestId('preview-pane')).toBeInTheDocument());
  }

  it('renders header stats from the program payload', async () => {
    const user = userEvent.setup();
    render(<BuilderSlideOver onClose={() => {}} />);
    await arriveAtPreview(user);
    expect(screen.getByText('throwing')).toBeInTheDocument();  // domain
    expect(screen.getByText('1 wk')).toBeInTheDocument();      // 3 days → 1 wk
    expect(screen.getByText('3')).toBeInTheDocument();          // total days
  });

  it('expandable timeline toggles open and renders day rows', async () => {
    const user = userEvent.setup();
    render(<BuilderSlideOver onClose={() => {}} />);
    await arriveAtPreview(user);
    const toggle = screen.getByRole('button', { name: /Day-by-day timeline/i });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    await user.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByTestId('timeline')).toBeInTheDocument();
    expect(screen.getByText('day_0')).toBeInTheDocument();
    expect(screen.getByText('day_2')).toBeInTheDocument();
  });

  it('hides citations section when none returned', async () => {
    const user = userEvent.setup();
    render(<BuilderSlideOver onClose={() => {}} />);
    await arriveAtPreview(user, { withCitations: false });
    expect(screen.queryByTestId('citations')).not.toBeInTheDocument();
  });

  it('Activate calls activateProgram + onProgramActivated + onClose', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const onActivated = vi.fn();
    activateProgram.mockResolvedValue({ ...PROG, status: 'active' });
    render(<BuilderSlideOver onClose={onClose} onProgramActivated={onActivated} />);
    await arriveAtPreview(user);
    await user.click(screen.getByText('Activate'));
    await waitFor(() => expect(activateProgram).toHaveBeenCalledWith('prog-1', 'fake-init-data'));
    expect(onActivated).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  it('Save as draft closes without activating', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const onDraft = vi.fn();
    render(<BuilderSlideOver onClose={onClose} onDraftSaved={onDraft} />);
    await arriveAtPreview(user);
    await user.click(screen.getByText('Save as draft'));
    expect(activateProgram).not.toHaveBeenCalled();
    expect(onDraft).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  it('Tweak archives current draft, increments regen counter, returns to socratic', async () => {
    const user = userEvent.setup();
    archiveProgram.mockResolvedValue({ ok: true });
    render(<BuilderSlideOver onClose={() => {}} />);
    await arriveAtPreview(user);
    // After tweak, the Socratic continuation turn fires
    sendBuilderTurn.mockResolvedValueOnce({ kind: 'question', text: 'Tweaked Q' });
    await user.click(screen.getByText(/^Tweak/));
    await waitFor(() => expect(archiveProgram).toHaveBeenCalledWith(
      'prog-1', 'rebuilt_in_builder', 'fake-init-data'));
    await waitFor(() => expect(screen.getByTestId('socratic-chat')).toBeInTheDocument());
  });

  it('disables Tweak after 3 regenerations (cap)', async () => {
    const user = userEvent.setup();
    archiveProgram.mockResolvedValue({ ok: true });
    finalizeBuilder.mockResolvedValue({
      program: PROG, citations: [],
    });
    render(<BuilderSlideOver onClose={() => {}} />);
    await arriveAtPreview(user);

    // Tweak x3 — after each, get back to preview
    for (let i = 0; i < 3; i++) {
      sendBuilderTurn.mockResolvedValueOnce({ kind: 'question', text: 'Q' });
      sendBuilderTurn.mockResolvedValueOnce({
        kind: 'ready', chosen_template_id: 'tpl_a', tuned_spec: {},
      });
      await user.click(screen.getByText(/^Tweak/));
      await waitFor(() => expect(screen.getByTestId('socratic-chat')).toBeInTheDocument());
      await user.type(screen.getByLabelText('Chat input'), 'ok');
      await user.click(screen.getByText('Send'));
      await waitFor(() => expect(screen.getByText('See the program')).toBeInTheDocument());
      await user.click(screen.getByText('See the program'));
      await waitFor(() => expect(screen.getByTestId('preview-pane')).toBeInTheDocument());
    }

    const tweakBtn = screen.getByRole('button', { name: /^Tweak/i });
    expect(tweakBtn).toBeDisabled();
    expect(tweakBtn).toHaveAttribute('title', expect.stringMatching(/limit/i));
  });
});

// ---------- Plan 7 / B11: "Other / describe…" goal chip ----------

describe('BuilderSlideOver: Other goal chip + LLM interpreter', () => {
  it('reveals text input when "Other / describe…" chip is selected', async () => {
    const user = userEvent.setup();
    render(<BuilderSlideOver onClose={() => {}} />);
    // Input is hidden before the chip is picked
    expect(screen.queryByTestId('goal-other-input')).not.toBeInTheDocument();
    await user.click(screen.getByText('Other / describe…'));
    const input = await screen.findByTestId('goal-other-input');
    expect(input).toHaveAttribute('aria-label', 'Goal description');
    expect(input).toHaveAttribute(
      'placeholder',
      expect.stringMatching(/describe your goal/i),
    );
  });

  it('calls interpretGoal then proceeds to candidates when LLM returns a real tag', async () => {
    const user = userEvent.setup();
    interpretGoal.mockResolvedValue({ tag: 'velocity', confidence: 'matched' });
    fetchBuilderCandidates.mockResolvedValue({
      session_id: 'sess-1',
      candidates: [{ block_template_id: 'tpl_a' }],
    });
    sendBuilderTurn.mockResolvedValue({ kind: 'question', text: 'Kick off?' });
    render(<BuilderSlideOver onClose={() => {}} />);

    await user.click(screen.getByText('Other / describe…'));
    await user.type(
      screen.getByTestId('goal-other-input'),
      'I want to throw harder',
    );
    await user.click(screen.getByText('Continue'));

    await waitFor(() => expect(interpretGoal).toHaveBeenCalledWith(
      'I want to throw harder', 'throwing', 'fake-init-data',
    ));
    await waitFor(() => expect(fetchBuilderCandidates).toHaveBeenCalled());
    // Resolved tag must be forwarded into the candidates envelope
    expect(fetchBuilderCandidates.mock.calls[0][0]).toMatchObject({
      domain: 'throwing',
      goal: 'velocity',
    });
    // And we should have advanced to the Socratic state
    await waitFor(() => {
      expect(screen.getByTestId('socratic-chat')).toBeInTheDocument();
    });
  });

  it('shows inline error when LLM confidence is unknown — stays on inputs, no /candidates call', async () => {
    const user = userEvent.setup();
    interpretGoal.mockResolvedValue({ tag: 'unknown', confidence: 'unknown' });
    render(<BuilderSlideOver onClose={() => {}} />);

    await user.click(screen.getByText('Other / describe…'));
    await user.type(screen.getByTestId('goal-other-input'), 'abracadabra');
    await user.click(screen.getByText('Continue'));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/couldn't match/i);
    });
    expect(fetchBuilderCandidates).not.toHaveBeenCalled();
    expect(screen.getByTestId('inputs-form')).toBeInTheDocument();
  });

  it('blocks Continue with empty Other text and never calls interpretGoal', async () => {
    const user = userEvent.setup();
    render(<BuilderSlideOver onClose={() => {}} />);

    await user.click(screen.getByText('Other / describe…'));
    await user.click(screen.getByText('Continue'));

    expect(screen.getByRole('alert')).toHaveTextContent(/describe your goal/i);
    expect(interpretGoal).not.toHaveBeenCalled();
    expect(fetchBuilderCandidates).not.toHaveBeenCalled();
  });
});

// ---------- BUILDER_STATES export ----------

describe('BUILDER_STATES export', () => {
  it('exposes the three state keys for callers', () => {
    expect(BUILDER_STATES).toEqual({
      INPUTS: 'inputs', SOCRATIC: 'socratic', PREVIEW: 'preview',
    });
  });
});
