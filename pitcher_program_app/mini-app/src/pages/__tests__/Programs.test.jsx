/**
 * Programs page — Plan 6 / B1.
 *
 * Mocks the hooks + api + BuilderSlideOver so we test section composition
 * and interactions, not the components inside each section (those have
 * their own dedicated tests).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// ---- Mocks ----
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock('../../App', () => ({
  useAuth: () => ({ pitcherId: 'landon_brice', initData: 'fake-init' }),
}));

const apiResponses = {};
const useApiCalls = []; // paths passed to useApi each render (null = skipped)
vi.mock('../../hooks/useApi', () => ({
  useApi: (path) => {
    useApiCalls.push(path);
    if (!path) return { data: null, loading: false, error: null, refetch: vi.fn() };
    // Strip cache-bust suffix for keying
    const key = path.replace(/\?_r=\d+$/, '');
    const entry = apiResponses[key];
    return {
      data: entry?.data ?? null,
      loading: entry?.loading ?? false,
      error: entry?.error ?? null,
      refetch: vi.fn(),
    };
  },
}));

const mockProfile = vi.fn();
const mockLog = vi.fn();
vi.mock('../../hooks/usePitcher', () => ({
  usePitcher: () => ({
    profile: mockProfile(),
    log: mockLog(),
    progression: null, loading: false, error: null,
  }),
}));

const builderSpy = vi.fn();
vi.mock('../../components/BuilderSlideOver', () => ({
  default: (props) => {
    builderSpy(props);
    return <div data-testid="builder-slideover-mounted">
      <span data-testid="builder-initial-domain">{props.initialDomain}</span>
      <span data-testid="builder-initial-goal">{props.initialGoal ?? ''}</span>
      <button data-testid="builder-close" onClick={props.onClose}>close</button>
      <button data-testid="builder-activated" onClick={() => props.onProgramActivated?.({})}>
        activated
      </button>
    </div>;
  },
}));

import Programs from '../Programs';

function setApi(path, data, loading = false) {
  apiResponses[path] = { data, loading, error: null };
}

beforeEach(() => {
  for (const k of Object.keys(apiResponses)) delete apiResponses[k];
  useApiCalls.length = 0;
  vi.clearAllMocks();
  mockProfile.mockReturnValue({ name: 'Landon Brice' });
  mockLog.mockReturnValue({ entries: [] });
  // Defaults so the page renders without errors
  setApi('/api/programs/active', { throwing: null, lifting: null });
  setApi('/api/programs/drafts', { drafts: [] });
  setApi('/api/programs/history', { history: [] });
  setApi('/api/programs/holds-today', { throwing: false, lifting: false });
  setApi('/api/favorites', { favorites: [] });
});

// ---------- Masthead ----------

describe('Programs: Masthead', () => {
  it('renders the kicker, first name, and the date', () => {
    render(<Programs />);
    expect(screen.getByTestId('masthead')).toBeInTheDocument();
    expect(screen.getByText('My Programs')).toBeInTheDocument();
    expect(screen.getByText('Landon')).toBeInTheDocument();
  });

  it("falls back to 'Pitcher' when name is missing", () => {
    mockProfile.mockReturnValue({});
    render(<Programs />);
    expect(screen.getByText('Pitcher')).toBeInTheDocument();
  });
});

// ---------- Today section ----------

describe('Programs: Today section', () => {
  it('omits the section entirely when there is no today entry', () => {
    render(<Programs />);
    expect(screen.queryByTestId('today-section')).not.toBeInTheDocument();
  });

  it('shows day_focus and the plan source tag when available', () => {
    const todayStr = new Date().toLocaleDateString('en-CA', { timeZone: 'America/Chicago' });
    mockLog.mockReturnValue({
      entries: [{
        date: todayStr,
        plan_generated: { day_focus: 'Lower power', source: 'program_prescribed' },
      }],
    });
    render(<Programs />);
    expect(screen.getByTestId('today-section')).toBeInTheDocument();
    expect(screen.getByText('Lower power')).toBeInTheDocument();
    expect(screen.getByTestId('today-source-tag')).toBeInTheDocument();
    expect(screen.getByText(/Program prescribed/i)).toBeInTheDocument();
  });

  it('hides section when entry has neither day_focus nor source', () => {
    const todayStr = new Date().toLocaleDateString('en-CA', { timeZone: 'America/Chicago' });
    mockLog.mockReturnValue({
      entries: [{ date: todayStr, plan_generated: {} }],
    });
    render(<Programs />);
    expect(screen.queryByTestId('today-section')).not.toBeInTheDocument();
  });
});

// ---------- Active Programs ----------

describe('Programs: Active section', () => {
  it('shows empty hint when no active programs', () => {
    render(<Programs />);
    expect(screen.getByTestId('active-empty')).toBeInTheDocument();
  });

  it('renders one card per domain', () => {
    setApi('/api/programs/active', {
      throwing: {
        program_id: 'p1', domain: 'throwing',
        current_day_index: 21, held_days_count: 2,
        start_date: '2026-05-01', nominal_end_date: '2026-07-23',
      },
      lifting: {
        program_id: 'p2', domain: 'lifting',
        current_day_index: 7, held_days_count: 0,
        start_date: '2026-05-06', nominal_end_date: '2026-06-17',
      },
    });
    render(<Programs />);
    expect(screen.getByTestId('active-card-throwing')).toBeInTheDocument();
    expect(screen.getByTestId('active-card-lifting')).toBeInTheDocument();
    expect(screen.getByText(/Day 22 of 84/)).toBeInTheDocument();
    expect(screen.getByText(/Day 8 of 43/)).toBeInTheDocument();
    expect(screen.getByText(/Held 2 days total/)).toBeInTheDocument();
  });

  it('flags Paused today when holdsToday says so', () => {
    setApi('/api/programs/active', {
      throwing: { program_id: 'p1', domain: 'throwing', current_day_index: 0,
                  held_days_count: 0, start_date: '2026-05-12', nominal_end_date: '2026-05-19' },
      lifting: null,
    });
    setApi('/api/programs/holds-today', { throwing: true, lifting: false });
    render(<Programs />);
    expect(screen.getByText(/Paused today/i)).toBeInTheDocument();
  });

  it('View navigates to /programs/{id}; Replace opens Builder with the right domain', async () => {
    const user = userEvent.setup();
    setApi('/api/programs/active', {
      throwing: { program_id: 'p1', domain: 'throwing', current_day_index: 0,
                  held_days_count: 0, start_date: '2026-05-12', nominal_end_date: '2026-05-19' },
      lifting:  { program_id: 'p2', domain: 'lifting',  current_day_index: 0,
                  held_days_count: 0, start_date: '2026-05-12', nominal_end_date: '2026-05-19' },
    });
    render(<Programs />);
    const throwingCard = screen.getByTestId('active-card-throwing');
    await user.click(within(throwingCard).getByText('View'));
    expect(mockNavigate).toHaveBeenCalledWith('/programs/p1');
    const liftingCard = screen.getByTestId('active-card-lifting');
    await user.click(within(liftingCard).getByText('Replace'));
    expect(screen.getByTestId('builder-slideover-mounted')).toBeInTheDocument();
    expect(screen.getByTestId('builder-initial-domain')).toHaveTextContent('lifting');
  });
});

// ---------- Build CTA ----------

describe('Programs: Build CTA', () => {
  it('opens Builder with default domain when tapped', async () => {
    const user = userEvent.setup();
    render(<Programs />);
    expect(screen.queryByTestId('builder-slideover-mounted')).not.toBeInTheDocument();
    await user.click(screen.getByTestId('build-cta'));
    expect(screen.getByTestId('builder-slideover-mounted')).toBeInTheDocument();
    expect(screen.getByTestId('builder-initial-domain')).toHaveTextContent('throwing');
  });

  it('closes Builder when its onClose fires', async () => {
    const user = userEvent.setup();
    render(<Programs />);
    await user.click(screen.getByTestId('build-cta'));
    await user.click(screen.getByTestId('builder-close'));
    expect(screen.queryByTestId('builder-slideover-mounted')).not.toBeInTheDocument();
  });

  it('refetches data after Builder activates a program', async () => {
    const user = userEvent.setup();
    render(<Programs />);
    await user.click(screen.getByTestId('build-cta'));
    await user.click(screen.getByTestId('builder-activated'));
    // Slide-over closes after activation
    await waitFor(() =>
      expect(screen.queryByTestId('builder-slideover-mounted')).not.toBeInTheDocument()
    );
  });
});

// ---------- Drafts ----------

describe('Programs: Drafts section', () => {
  it('is hidden when there are no drafts', () => {
    render(<Programs />);
    expect(screen.queryByText('Drafts')).not.toBeInTheDocument();
  });

  it('renders one card per draft, tap navigates to detail page', async () => {
    const user = userEvent.setup();
    setApi('/api/programs/drafts', { drafts: [
      { program_id: 'd1', domain: 'throwing', start_date: '2026-05-20' },
      { program_id: 'd2', domain: 'lifting',  start_date: '2026-06-01' },
    ]});
    render(<Programs />);
    expect(screen.getByText('Drafts')).toBeInTheDocument();
    expect(screen.getByTestId('draft-d1')).toBeInTheDocument();
    await user.click(screen.getByTestId('draft-d1'));
    expect(mockNavigate).toHaveBeenCalledWith('/programs/d1');
  });
});

// ---------- Favorites ----------

describe('Programs: Favorites section', () => {
  const FAVS = [
    {
      favorite_id: 'f1', block_type: 'lifting',
      source_entry_date: '2026-05-12',
      block_snapshot_json: { exercises: [
        { exercise_id: 'ex_1', name: 'Bench', sets: 3, reps: 5 },
        { exercise_id: 'ex_2', name: 'Row',   sets: 3, reps: 8 },
      ]},
    },
    {
      favorite_id: 'f2', block_type: 'arm_care',
      source_entry_date: '2026-05-10',
      block_snapshot_json: { exercises: [
        { exercise_id: 'ex_3', name: 'External rotation', sets: 2, reps: 12 },
      ]},
    },
  ];

  it('shows empty hint when no favorites', () => {
    render(<Programs />);
    expect(screen.getByTestId('favorites-empty')).toBeInTheDocument();
  });

  it('lists favorites with summary metadata', () => {
    setApi('/api/favorites', { favorites: FAVS });
    render(<Programs />);
    expect(screen.getByTestId('favorite-f1')).toBeInTheDocument();
    expect(screen.getByText(/From 2026-05-12/)).toBeInTheDocument();
    expect(screen.getByText(/2 exercises/)).toBeInTheDocument();
  });

  it('inline-expands a favorite to show its snapshot exercises (D13 render-only)', async () => {
    const user = userEvent.setup();
    setApi('/api/favorites', { favorites: FAVS });
    render(<Programs />);
    expect(screen.queryByTestId('favorite-expanded-f1')).not.toBeInTheDocument();
    const row = screen.getByTestId('favorite-f1');
    await user.click(within(row).getByRole('button'));
    expect(screen.getByTestId('favorite-expanded-f1')).toBeInTheDocument();
    expect(screen.getByText('Bench')).toBeInTheDocument();
    expect(screen.getByText('Row')).toBeInTheDocument();
  });

  it('collapses when tapped again, never opens a route', async () => {
    const user = userEvent.setup();
    setApi('/api/favorites', { favorites: FAVS });
    render(<Programs />);
    const row = screen.getByTestId('favorite-f1');
    const toggle = within(row).getByRole('button');
    await user.click(toggle);
    expect(screen.getByTestId('favorite-expanded-f1')).toBeInTheDocument();
    await user.click(toggle);
    expect(screen.queryByTestId('favorite-expanded-f1')).not.toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('filter chips narrow the list by block_type', async () => {
    const user = userEvent.setup();
    setApi('/api/favorites', { favorites: FAVS });
    render(<Programs />);
    expect(screen.getByTestId('favorite-f1')).toBeInTheDocument();
    expect(screen.getByTestId('favorite-f2')).toBeInTheDocument();
    const filterRow = screen.getByTestId('favorites-filter');
    await user.click(within(filterRow).getByText('Arm care'));
    expect(screen.queryByTestId('favorite-f1')).not.toBeInTheDocument();
    expect(screen.getByTestId('favorite-f2')).toBeInTheDocument();
  });
});

// ---------- History ----------

describe('Programs: History section', () => {
  it('is hidden when no archived programs', () => {
    render(<Programs />);
    expect(screen.queryByText('Program History')).not.toBeInTheDocument();
  });

  it('renders archived programs with reason', () => {
    setApi('/api/programs/history', { history: [
      {
        program_id: 'h1', domain: 'throwing',
        start_date: '2026-03-01',
        archived_at: '2026-05-01T00:00:00Z',
        archive_reason: 'superseded',
      },
    ]});
    render(<Programs />);
    expect(screen.getByText('Program History')).toBeInTheDocument();
    expect(screen.getByTestId('history-h1')).toBeInTheDocument();
    expect(screen.getByText('superseded')).toBeInTheDocument();
  });
});

// ---------- Browse Templates (Plan 7 / B13) ----------

describe('Programs: Browse Templates section', () => {
  const TEMPLATES = [
    {
      block_template_id: 'tpl_velocity_12wk_v1',
      name: 'Velocity 12wk',
      description: '12-week velocity development block',
      domain: 'throwing',
      goal_tags: ['velocity', 'longtoss'],
      compatible_phases: ['off_season'],
      duration_range_weeks: '[10,14]',
    },
    {
      block_template_id: 'tpl_hypertrophy_8wk_v1',
      name: 'Hypertrophy 8wk',
      description: 'Off-season size phase',
      domain: 'lifting',
      goal_tags: ['hypertrophy'],
      compatible_phases: ['off_season'],
      duration_range_weeks: '[6,10)',
    },
  ];

  it('starts collapsed and does not fetch /api/programs/templates until expanded', () => {
    render(<Programs />);
    // The toggle is rendered…
    expect(screen.getByTestId('browse-templates-toggle')).toBeInTheDocument();
    // …but the body is not present and useApi was never called with the
    // templates URL (the section passes `null` while collapsed).
    expect(screen.queryByTestId('browse-templates-body')).not.toBeInTheDocument();
    const templatesCalls = useApiCalls.filter(p => p && p.startsWith('/api/programs/templates'));
    expect(templatesCalls).toHaveLength(0);
  });

  it('renders template rows on expand and opens Builder with the template domain + first goal_tag', async () => {
    const user = userEvent.setup();
    setApi('/api/programs/templates', { templates: TEMPLATES });
    render(<Programs />);

    // Expand the section.
    await user.click(screen.getByTestId('browse-templates-toggle'));
    expect(screen.getByTestId('browse-templates-body')).toBeInTheDocument();

    // Both template rows render.
    expect(screen.getByTestId('template-row-tpl_velocity_12wk_v1')).toBeInTheDocument();
    expect(screen.getByTestId('template-row-tpl_hypertrophy_8wk_v1')).toBeInTheDocument();
    expect(screen.getByText('Velocity 12wk')).toBeInTheDocument();
    expect(screen.getByText('Hypertrophy 8wk')).toBeInTheDocument();

    // useApi was called with the templates URL once the section opened.
    const templatesCalls = useApiCalls.filter(p => p && p.startsWith('/api/programs/templates'));
    expect(templatesCalls.length).toBeGreaterThan(0);

    // Tap "Build with this template" on the lifting row → Builder opens
    // with the template's domain and first goal_tag pre-selected.
    await user.click(screen.getByTestId('template-build-tpl_hypertrophy_8wk_v1'));
    expect(screen.getByTestId('builder-slideover-mounted')).toBeInTheDocument();
    expect(screen.getByTestId('builder-initial-domain')).toHaveTextContent('lifting');
    expect(screen.getByTestId('builder-initial-goal')).toHaveTextContent('hypertrophy');
  });
});

