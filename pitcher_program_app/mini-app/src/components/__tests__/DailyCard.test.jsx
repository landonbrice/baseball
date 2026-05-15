/**
 * DailyCard — Active-only sub-phase collapse (2026-05-15).
 *
 * Covers four scenarios from the spec:
 *   (a) default-mount derives active from completion state
 *   (b) tapping a non-active phase makes it active
 *   (c) auto-advance fires when the active phase completes
 *   (d) active header carries the maroon visual signal (aria-current="true")
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('../../api', () => ({
  toggleExercise: vi.fn(() => Promise.resolve()),
  submitThrowFeel: vi.fn(() => Promise.resolve()),
  postApi: vi.fn(() => Promise.resolve({})),
}));

// MobilityCard makes a fetch inside DailyCard's effect — mock it out so
// jsdom doesn't choke on missing globals.
vi.mock('../MobilityCard', () => ({
  default: () => null,
}));

// FavoriteHeart triggers postApi — render an inert stub so we don't have
// to wire mock auth context.
vi.mock('../FavoriteHeart', () => ({
  default: () => null,
}));

import DailyCard from '../DailyCard';
import { ToastProvider } from '../../hooks/useToast';

beforeEach(() => {
  vi.clearAllMocks();
  // jsdom doesn't implement fetch; the mobility effect needs *something*.
  globalThis.fetch = vi.fn(() => Promise.resolve({ ok: false, json: () => Promise.resolve({}) }));
});

// ---------------------------------------------------------------------------
// Fixture builders
// ---------------------------------------------------------------------------

function makeThrowingEntry(over = {}) {
  return {
    date: '2026-05-15',
    pre_training: { arm_feel: 8 },
    completed_exercises: {},
    throwing: {
      type: 'recovery',
      day_type_label: 'recovery day',
      phases: [
        {
          phase_name: 'Wrist Weight Series',
          exercises: [
            { exercise_id: 'ww_1', name: 'Wrist Weight Pronation Swings', rx: '1x10' },
            { exercise_id: 'ww_2', name: 'Wrist Weight Two-Arm Throws', rx: '1x10' },
          ],
        },
        {
          phase_name: 'Plyo Drills - Recovery',
          exercises: [
            { exercise_id: 'plyo_1', name: 'Plyo Reverse Throws', rx: '1x8' },
            { exercise_id: 'plyo_2', name: 'Plyo Pivot Picks', rx: '1x8' },
          ],
        },
        {
          phase_name: 'Catch Play',
          exercises: [
            { exercise_id: 'catch_1', name: 'Light Catch Play', rx: '20-30 throws' },
          ],
        },
      ],
    },
    ...over,
  };
}

function renderWithToast(ui) {
  return render(<ToastProvider>{ui}</ToastProvider>);
}

function findPhaseHeader(name) {
  // Phase headers have uppercase text with the chevron prefix; match the
  // bare uppercase phase name (the chevron + " · NOW" floats around it).
  return screen.getByText(
    (_, node) => {
      if (!node || node.tagName !== 'SPAN') return false;
      const txt = node.textContent || '';
      return txt.toUpperCase().includes(name.toUpperCase());
    },
    { selector: 'span' },
  );
}

function getActiveHeader(container) {
  return container.querySelector('[data-active="true"]');
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('DailyCard · active-only sub-phase collapse', () => {
  it('(a) defaults to the first incomplete throwing phase on mount', () => {
    const entry = makeThrowingEntry();
    const { container } = renderWithToast(
      <DailyCard
        entry={entry}
        exerciseMap={{}}
        pitcherId="landon_brice"
        initData="fake"
      />
    );

    // Active phase header has aria-current="true". First phase ("Wrist
    // Weight Series") is the default since nothing is completed.
    const active = getActiveHeader(container);
    expect(active).not.toBeNull();
    expect(active.textContent).toMatch(/WRIST WEIGHT SERIES/i);
    expect(active.textContent).toMatch(/NOW/);
  });

  it('(a) skips completed phases when deriving default active', () => {
    const entry = makeThrowingEntry({
      completed_exercises: {
        ww_1: true,
        ww_2: true,
        // First phase fully done → second phase should be active by default
      },
    });
    const { container } = renderWithToast(
      <DailyCard
        entry={entry}
        exerciseMap={{}}
        pitcherId="landon_brice"
        initData="fake"
      />
    );

    const active = getActiveHeader(container);
    expect(active.textContent).toMatch(/PLYO DRILLS/i);
  });

  it('(b) tapping a non-active phase header makes it active', async () => {
    const user = userEvent.setup();
    const entry = makeThrowingEntry();
    const { container } = renderWithToast(
      <DailyCard
        entry={entry}
        exerciseMap={{}}
        pitcherId="landon_brice"
        initData="fake"
      />
    );

    // Start: Wrist Weight Series is active
    expect(getActiveHeader(container).textContent).toMatch(/WRIST WEIGHT SERIES/i);

    // Tap "Plyo Drills - Recovery" header (uppercase rendered)
    const plyoSpan = findPhaseHeader('Plyo Drills');
    // The clickable header is the parent <div> of the span
    await user.click(plyoSpan.closest('[data-active]') || plyoSpan.parentElement);

    expect(getActiveHeader(container).textContent).toMatch(/PLYO DRILLS/i);
    // Prior active should no longer be marked active
    const allActive = container.querySelectorAll('[data-active="true"]');
    expect(allActive.length).toBe(1);
  });

  it('(c) auto-advances when the active phase completes', async () => {
    const user = userEvent.setup();
    const entry = makeThrowingEntry();
    const { container } = renderWithToast(
      <DailyCard
        entry={entry}
        exerciseMap={{}}
        pitcherId="landon_brice"
        initData="fake"
      />
    );
    expect(getActiveHeader(container).textContent).toMatch(/WRIST WEIGHT SERIES/i);

    // Click the toggle circles for both exercises in the first phase.
    // The circle button label is "·" when uncompleted (no superset letter),
    // and the click handler bubbles up through onToggle → setCompleted →
    // auto-advance effect.
    const circles = container.querySelectorAll('button');
    // Filter to the toggle circles inside the active phase's exercise list.
    const toggleButtons = Array.from(circles).filter(b => {
      const txt = (b.textContent || '').trim();
      return txt === '·' || txt === '✓';
    });
    // Click first two — they belong to the first phase (Wrist Weight Series)
    expect(toggleButtons.length).toBeGreaterThanOrEqual(2);
    await user.click(toggleButtons[0]);
    await user.click(toggleButtons[1]);

    // After the first phase is fully done, active should auto-advance to plyo
    expect(getActiveHeader(container).textContent).toMatch(/PLYO DRILLS/i);
  });

  it('(d) active header carries maroon styling (aria-current + maroon color)', () => {
    const entry = makeThrowingEntry();
    const { container } = renderWithToast(
      <DailyCard
        entry={entry}
        exerciseMap={{}}
        pitcherId="landon_brice"
        initData="fake"
      />
    );

    const active = getActiveHeader(container);
    expect(active).not.toBeNull();
    expect(active.getAttribute('aria-current')).toBe('true');

    // Active visual contract: maroon wash + 3px inset shadow rail
    const style = active.getAttribute('style') || '';
    expect(style).toMatch(/rgba\(\s*92,\s*16,\s*32,\s*0\.05\s*\)/);
    expect(style).toMatch(/inset 3px 0 0 rgba\(\s*92,\s*16,\s*32,\s*0\.22\s*\)/);

    // The name span inside the active header should be maroon-colored
    const nameSpan = active.querySelector('span');
    const nameStyle = nameSpan.getAttribute('style') || '';
    expect(nameStyle).toMatch(/var\(--color-maroon\)/);

    // Active header includes the ' · NOW' suffix
    expect(nameSpan.textContent).toMatch(/· NOW/);
  });

  it('(d) idle phase headers carry the cream-bg style + ▶ chevron', () => {
    const entry = makeThrowingEntry();
    const { container } = renderWithToast(
      <DailyCard
        entry={entry}
        exerciseMap={{}}
        pitcherId="landon_brice"
        initData="fake"
      />
    );

    const idleHeaders = container.querySelectorAll('[data-active="false"]');
    expect(idleHeaders.length).toBeGreaterThan(0);
    for (const h of idleHeaders) {
      const style = h.getAttribute('style') || '';
      // No inset maroon rail on idle headers
      expect(style).not.toMatch(/inset 3px 0 0 rgba\(\s*92,\s*16,\s*32/);
      // Chevron is ▶ when collapsed
      const nameSpan = h.querySelector('span');
      expect(nameSpan.textContent.trim().startsWith('▶')).toBe(true);
    }
  });
});
