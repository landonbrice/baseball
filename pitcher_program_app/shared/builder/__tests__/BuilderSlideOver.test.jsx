/**
 * BuilderSlideOver — state machine + API glue tests (Plan 6 / B3, hoisted in
 * Plan 7 / C0).
 *
 * The component now takes its API + auth concerns as PROPS, so these tests
 * construct a fake `api` object with vi.fn() stubs and pass it directly. No
 * module mocks needed (the old `../../api` + `../../App` mocks are gone).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import BuilderSlideOver, { BUILDER_STATES } from '../BuilderSlideOver';

// ---- Fake api factory ----
// Each test gets its own fresh object so per-test mockResolvedValueOnce ordering
// doesn't leak across cases.
function makeFakeApi() {
  return {
    fetchCandidates:  vi.fn(),
    sendTurn:         vi.fn(),
    finalize:         vi.fn(),
    activateProgram:  vi.fn(),
    archiveProgram:   vi.fn(),
    interpretGoal:    vi.fn(),
  };
}

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

// Hoisted per-test fake; recreated in beforeEach so each test sees a clean slate.
let api;
beforeEach(() => {
  api = makeFakeApi();
});

// ---------- State A: INPUTS ----------

describe('BuilderSlideOver: Inputs state', () => {
  it('renders the inputs form with default chips selected', () => {
    render(<BuilderSlideOver api={api} onClose={() => {}} />);
    expect(screen.getByTestId('inputs-form')).toBeInTheDocument();
    expect(screen.getByText('Throwing')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByText('12 wk')).toHaveAttribute('aria-pressed', 'true');
  });

  it('blocks Continue when goal is empty', async () => {
    const user = userEvent.setup();
    render(<BuilderSlideOver api={api} onClose={() => {}} />);
    await user.click(screen.getByText('Continue'));
    expect(screen.getByRole('alert')).toHaveTextContent(/goal/i);
    expect(api.fetchCandidates).not.toHaveBeenCalled();
  });

  it('shows inline error and stays on inputs when 0 candidates returned', async () => {
    const user = userEvent.setup();
    api.fetchCandidates.mockResolvedValue({ session_id: 'sess-1', candidates: [] });
    render(<BuilderSlideOver api={api} onClose={() => {}} />);
    await user.click(screen.getByText('Velocity'));
    await user.click(screen.getByText('Continue'));
    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/no templates match/i);
    });
    expect(screen.getByTestId('inputs-form')).toBeInTheDocument();
  });

  it('transitions to socratic on successful candidates fetch and kicks off first turn', async () => {
    const user = userEvent.setup();
    api.fetchCandidates.mockResolvedValue({
      session_id: 'sess-1',
      candidates: [{ block_template_id: 'tpl_a', name: 'A' }],
    });
    api.sendTurn.mockResolvedValue({ kind: 'question', text: 'What is your top priority?' });
    render(<BuilderSlideOver api={api} onClose={() => {}} />);
    await user.click(screen.getByText('Velocity'));
    await user.click(screen.getByText('Continue'));
    await waitFor(() => {
      expect(screen.getByTestId('socratic-chat')).toBeInTheDocument();
    });
    expect(api.sendTurn).toHaveBeenCalledWith('sess-1', '');
    expect(screen.getByText('What is your top priority?')).toBeInTheDocument();
  });

  it('passes the full envelope (domain, goal, duration, phase, hard_constraints, interview_mode) to /candidates', async () => {
    const user = userEvent.setup();
    api.fetchCandidates.mockResolvedValue({
      session_id: 'sess-1',
      candidates: [{ block_template_id: 'tpl_a' }],
    });
    api.sendTurn.mockResolvedValue({ kind: 'question', text: '?' });
    render(<BuilderSlideOver api={api} onClose={() => {}} />);
    // Stay on Throwing (Lifting has no goals seeded yet)
    await user.click(screen.getByText('8 wk'));
    await user.click(screen.getByText('Preseason'));
    await user.click(screen.getByText('No max effort'));
    await user.click(screen.getByText('Off-season base'));
    await user.click(screen.getByText('Continue'));
    await waitFor(() => expect(api.fetchCandidates).toHaveBeenCalled());
    expect(api.fetchCandidates.mock.calls[0][0]).toEqual({
      domain: 'throwing',
      goal: 'offseason_base',
      duration_weeks: 8,
      effective_phase: 'preseason',
      hard_constraints: ['no_max_effort'],
      interview_mode: 'personalize',  // default
    });
  });

  it('renders lifting goal chips when domain is lifting (no "coming soon")', async () => {
    const user = userEvent.setup();
    render(<BuilderSlideOver api={api} onClose={() => {}} />);
    await user.click(screen.getByText('Lifting'));
    // Chips render; banner is gone.
    expect(screen.getByTestId('goal-chips')).toBeInTheDocument();
    expect(screen.queryByTestId('goal-domain-unsupported')).not.toBeInTheDocument();
    expect(screen.queryByText(/coming soon/i)).not.toBeInTheDocument();
    // All four lifting chips visible
    expect(screen.getByText('Hypertrophy')).toBeInTheDocument();
    expect(screen.getByText('Strength maintenance')).toBeInTheDocument();
    expect(screen.getByText('In-season lifting')).toBeInTheDocument();
    expect(screen.getByText('Other / describe…')).toBeInTheDocument();
    // Continue with no chip selected still blocks
    await user.click(screen.getByText('Continue'));
    expect(screen.getByRole('alert')).toHaveTextContent(/goal/i);
    expect(api.fetchCandidates).not.toHaveBeenCalled();
  });

  it('switching to lifting defaults duration to 8 wk', async () => {
    const user = userEvent.setup();
    render(<BuilderSlideOver api={api} onClose={() => {}} />);
    // Throwing default is 12 wk
    expect(screen.getByText('12 wk')).toHaveAttribute('aria-pressed', 'true');
    await user.click(screen.getByText('Lifting'));
    expect(screen.getByText('8 wk')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByText('12 wk')).toHaveAttribute('aria-pressed', 'false');
    // Switch back to throwing — duration returns to 12 wk
    await user.click(screen.getByText('Throwing'));
    expect(screen.getByText('12 wk')).toHaveAttribute('aria-pressed', 'true');
  });

  it('hypertrophy chip on lifting domain → /candidates called with goal=hypertrophy', async () => {
    const user = userEvent.setup();
    api.fetchCandidates.mockResolvedValue({
      session_id: 'sess-1',
      candidates: [{ block_template_id: 'hypertrophy_8wk_v1' }],
    });
    api.sendTurn.mockResolvedValue({ kind: 'question', text: 'Kick off?' });
    render(<BuilderSlideOver api={api} onClose={() => {}} />);

    await user.click(screen.getByText('Lifting'));
    await user.click(screen.getByText('Hypertrophy'));
    // Default duration auto-flipped to 8 wk; pick off-season explicitly.
    await user.click(screen.getByText('Off-season'));
    await user.click(screen.getByText('Continue'));

    await waitFor(() => expect(api.fetchCandidates).toHaveBeenCalled());
    expect(api.fetchCandidates.mock.calls[0][0]).toEqual({
      domain: 'lifting',
      goal: 'hypertrophy',
      duration_weeks: 8,
      effective_phase: 'off_season',
      hard_constraints: [],
      interview_mode: 'personalize',
    });
    await waitFor(() => {
      expect(screen.getByTestId('socratic-chat')).toBeInTheDocument();
    });
  });

  it('Other / describe… on lifting domain reveals the text input', async () => {
    const user = userEvent.setup();
    render(<BuilderSlideOver api={api} onClose={() => {}} />);
    await user.click(screen.getByText('Lifting'));
    expect(screen.queryByTestId('goal-other-input')).not.toBeInTheDocument();
    await user.click(screen.getByText('Other / describe…'));
    const input = await screen.findByTestId('goal-other-input');
    expect(input).toHaveAttribute('aria-label', 'Goal description');
  });

  it('clears goal selection when domain switches', async () => {
    const user = userEvent.setup();
    api.fetchCandidates.mockResolvedValue({
      session_id: 'sess-1', candidates: [{ block_template_id: 'tpl_a' }],
    });
    render(<BuilderSlideOver api={api} onClose={() => {}} />);
    await user.click(screen.getByText('Velocity'));  // pick throwing goal
    expect(screen.getByText('Velocity')).toHaveAttribute('aria-pressed', 'true');
    await user.click(screen.getByText('Lifting'));    // switch domain
    await user.click(screen.getByText('Throwing'));   // switch back
    // Goal must be cleared — Continue with no selection should error
    await user.click(screen.getByText('Continue'));
    expect(screen.getByRole('alert')).toHaveTextContent(/goal/i);
    expect(api.fetchCandidates).not.toHaveBeenCalled();
  });
});

// ---------- State B: SOCRATIC ----------

describe('BuilderSlideOver: Socratic state', () => {
  async function arriveAtSocratic(user) {
    api.fetchCandidates.mockResolvedValue({
      session_id: 'sess-1',
      candidates: [{ block_template_id: 'tpl_a' }],
    });
    api.sendTurn.mockResolvedValueOnce({ kind: 'question', text: 'Q1' });
    await user.click(screen.getByText('Velocity'));
    await user.click(screen.getByText('Continue'));
    // Wait for the kickoff response to settle (Q1 visible → input enabled)
    await waitFor(() => expect(screen.getByText('Q1')).toBeInTheDocument());
  }

  it("loops /turn with user answers until {kind: 'ready'}", async () => {
    const user = userEvent.setup();
    render(<BuilderSlideOver api={api} onClose={() => {}} />);
    await arriveAtSocratic(user);

    api.sendTurn.mockResolvedValueOnce({ kind: 'question', text: 'Q2' });
    await user.type(screen.getByLabelText('Chat input'), 'velocity');
    await user.click(screen.getByText('Send'));
    await waitFor(() => expect(screen.getByText('Q2')).toBeInTheDocument());

    api.sendTurn.mockResolvedValueOnce({
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
    render(<BuilderSlideOver api={api} onClose={() => {}} />);
    await arriveAtSocratic(user);

    api.sendTurn.mockResolvedValueOnce({ kind: 'question', text: 'Q2' });
    await user.click(screen.getByText(/I don't know/i));
    await waitFor(() => {
      const calls = api.sendTurn.mock.calls;
      const second = calls[1];  // [0] was the kickoff empty turn
      expect(second[1]).toMatch(/I don't know/);
    });
  });

  it('finalizing transitions to preview with program + citations', async () => {
    const user = userEvent.setup();
    render(<BuilderSlideOver api={api} onClose={() => {}} />);
    await arriveAtSocratic(user);

    api.sendTurn.mockResolvedValueOnce({
      kind: 'ready',
      chosen_template_id: 'tpl_a',
      tuned_spec: { weeks: 12 },
    });
    await user.type(screen.getByLabelText('Chat input'), 'ready');
    await user.click(screen.getByText('Send'));
    await waitFor(() => expect(screen.getByText('See the program')).toBeInTheDocument());

    api.finalize.mockResolvedValue({
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
    api.fetchCandidates.mockResolvedValue({
      session_id: 'sess-1', candidates: [{ block_template_id: 'tpl_a' }],
    });
    api.sendTurn
      .mockResolvedValueOnce({ kind: 'question', text: 'Q1' })  // kickoff
      .mockResolvedValueOnce({
        kind: 'ready', chosen_template_id: 'tpl_a', tuned_spec: { weeks: 12 },
      });  // after user types
    api.finalize.mockResolvedValue({
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
    render(<BuilderSlideOver api={api} onClose={() => {}} />);
    await arriveAtPreview(user);
    expect(screen.getByText('throwing')).toBeInTheDocument();  // domain
    expect(screen.getByText('1 wk')).toBeInTheDocument();      // 3 days → 1 wk
    expect(screen.getByText('3')).toBeInTheDocument();          // total days
  });

  it('expandable timeline toggles open and renders day rows', async () => {
    const user = userEvent.setup();
    render(<BuilderSlideOver api={api} onClose={() => {}} />);
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
    render(<BuilderSlideOver api={api} onClose={() => {}} />);
    await arriveAtPreview(user, { withCitations: false });
    expect(screen.queryByTestId('citations')).not.toBeInTheDocument();
  });

  it('Activate calls activateProgram + onProgramActivated + onClose', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const onActivated = vi.fn();
    api.activateProgram.mockResolvedValue({ ...PROG, status: 'active' });
    render(<BuilderSlideOver api={api} onClose={onClose} onProgramActivated={onActivated} />);
    await arriveAtPreview(user);
    await user.click(screen.getByText('Activate'));
    await waitFor(() => expect(api.activateProgram).toHaveBeenCalledWith('prog-1'));
    expect(onActivated).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  it('Save as draft closes without activating', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const onDraft = vi.fn();
    render(<BuilderSlideOver api={api} onClose={onClose} onDraftSaved={onDraft} />);
    await arriveAtPreview(user);
    await user.click(screen.getByText('Save as draft'));
    expect(api.activateProgram).not.toHaveBeenCalled();
    expect(onDraft).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  it('Tweak archives current draft, increments regen counter, returns to socratic', async () => {
    const user = userEvent.setup();
    api.archiveProgram.mockResolvedValue({ ok: true });
    render(<BuilderSlideOver api={api} onClose={() => {}} />);
    await arriveAtPreview(user);
    // After tweak, the Socratic continuation turn fires
    api.sendTurn.mockResolvedValueOnce({ kind: 'question', text: 'Tweaked Q' });
    await user.click(screen.getByText(/^Tweak/));
    await waitFor(() => expect(api.archiveProgram).toHaveBeenCalledWith(
      'prog-1', 'rebuilt_in_builder'));
    await waitFor(() => expect(screen.getByTestId('socratic-chat')).toBeInTheDocument());
  });

  it('disables Tweak after 3 regenerations (cap)', async () => {
    const user = userEvent.setup();
    api.archiveProgram.mockResolvedValue({ ok: true });
    api.finalize.mockResolvedValue({
      program: PROG, citations: [],
    });
    render(<BuilderSlideOver api={api} onClose={() => {}} />);
    await arriveAtPreview(user);

    // Tweak x3 — after each, get back to preview
    for (let i = 0; i < 3; i++) {
      api.sendTurn.mockResolvedValueOnce({ kind: 'question', text: 'Q' });
      api.sendTurn.mockResolvedValueOnce({
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
    render(<BuilderSlideOver api={api} onClose={() => {}} />);
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
    api.interpretGoal.mockResolvedValue({ tag: 'velocity', confidence: 'matched' });
    api.fetchCandidates.mockResolvedValue({
      session_id: 'sess-1',
      candidates: [{ block_template_id: 'tpl_a' }],
    });
    api.sendTurn.mockResolvedValue({ kind: 'question', text: 'Kick off?' });
    render(<BuilderSlideOver api={api} onClose={() => {}} />);

    await user.click(screen.getByText('Other / describe…'));
    await user.type(
      screen.getByTestId('goal-other-input'),
      'I want to throw harder',
    );
    await user.click(screen.getByText('Continue'));

    await waitFor(() => expect(api.interpretGoal).toHaveBeenCalledWith(
      'I want to throw harder', 'throwing',
    ));
    await waitFor(() => expect(api.fetchCandidates).toHaveBeenCalled());
    // Resolved tag must be forwarded into the candidates envelope
    expect(api.fetchCandidates.mock.calls[0][0]).toMatchObject({
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
    api.interpretGoal.mockResolvedValue({ tag: 'unknown', confidence: 'unknown' });
    render(<BuilderSlideOver api={api} onClose={() => {}} />);

    await user.click(screen.getByText('Other / describe…'));
    await user.type(screen.getByTestId('goal-other-input'), 'abracadabra');
    await user.click(screen.getByText('Continue'));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/couldn't match/i);
    });
    expect(api.fetchCandidates).not.toHaveBeenCalled();
    expect(screen.getByTestId('inputs-form')).toBeInTheDocument();
  });

  it('blocks Continue with empty Other text and never calls interpretGoal', async () => {
    const user = userEvent.setup();
    render(<BuilderSlideOver api={api} onClose={() => {}} />);

    await user.click(screen.getByText('Other / describe…'));
    await user.click(screen.getByText('Continue'));

    expect(screen.getByRole('alert')).toHaveTextContent(/describe your goal/i);
    expect(api.interpretGoal).not.toHaveBeenCalled();
    expect(api.fetchCandidates).not.toHaveBeenCalled();
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
