/**
 * ProgramRibbon — Plan 6 / B2.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import ProgramRibbon from '../ProgramRibbon';

function makeProgram(over = {}) {
  return {
    program_id: 'p1',
    pitcher_id: 'landon_brice',
    domain: 'throwing',
    status: 'active',
    start_date: '2026-05-01',
    nominal_end_date: '2026-07-23',
    current_day_index: 21,   // → day 22 displayed
    held_days_count: 2,
    ...over,
  };
}

describe('ProgramRibbon', () => {
  it('renders nothing when program is null', () => {
    const { container } = render(<ProgramRibbon program={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders domain label, day count, and held count', () => {
    render(<ProgramRibbon program={makeProgram()} />);
    expect(screen.getByText('Throwing')).toBeInTheDocument();
    // Day 22 of 84 (~12 wk × 7 = 84) · Held 2 days
    expect(screen.getByText(/Day 22 of 84/)).toBeInTheDocument();
    expect(screen.getByText(/Held 2 days/)).toBeInTheDocument();
  });

  it('omits held suffix when held_days_count is 0', () => {
    render(<ProgramRibbon program={makeProgram({ held_days_count: 0 })} />);
    expect(screen.queryByText(/Held/)).not.toBeInTheDocument();
  });

  it('singular "1 day" when held exactly 1 day', () => {
    render(<ProgramRibbon program={makeProgram({ held_days_count: 1 })} />);
    expect(screen.getByText(/Held 1 day(?!s)/)).toBeInTheDocument();
  });

  it('falls back gracefully when dates are missing', () => {
    render(<ProgramRibbon program={makeProgram({
      start_date: null, nominal_end_date: null, generated_schedule_json: null,
    })} />);
    // Should still render "Day X" without "of Y"
    expect(screen.getByText(/^Day 22(?! of)/)).toBeInTheDocument();
  });

  it('prefers generated_schedule_json.days.length over date math', () => {
    render(<ProgramRibbon program={makeProgram({
      start_date: '2026-05-01', nominal_end_date: '2099-01-01',  // huge gap
      generated_schedule_json: { days: Array.from({ length: 30 }, (_, i) => ({ day_index: i })) },
    })} />);
    expect(screen.getByText(/Day 22 of 30/)).toBeInTheDocument();
  });

  it('renders the paused-today pill when heldToday=true', () => {
    render(<ProgramRibbon program={makeProgram()} heldToday />);
    expect(screen.getByTestId('held-today-pill')).toBeInTheDocument();
    expect(screen.getByText(/Paused today/i)).toBeInTheDocument();
  });

  it('omits paused pill when heldToday=false', () => {
    render(<ProgramRibbon program={makeProgram()} heldToday={false} />);
    expect(screen.queryByTestId('held-today-pill')).not.toBeInTheDocument();
  });

  it('uses the domain-keyed testId so two ribbons can coexist on the page', () => {
    const { getByTestId, rerender } = render(
      <ProgramRibbon program={makeProgram({ domain: 'throwing' })} />
    );
    expect(getByTestId('program-ribbon-throwing')).toBeInTheDocument();
    rerender(<ProgramRibbon program={makeProgram({ domain: 'lifting' })} />);
    expect(getByTestId('program-ribbon-lifting')).toBeInTheDocument();
  });
});
