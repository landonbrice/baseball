import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Button, buttonVariants } from '../button';
import { FlagPill } from '../flag-pill';
import { Card, CardTitle } from '../card';

describe('Button', () => {
  it('renders children and defaults to type=button', () => {
    render(<Button>Save</Button>);
    const btn = screen.getByRole('button', { name: 'Save' });
    expect(btn).toBeInTheDocument();
    expect(btn).toHaveAttribute('type', 'button');
  });

  it('applies token-driven variant classes', () => {
    render(<Button variant="destructive">Delete</Button>);
    const btn = screen.getByRole('button', { name: 'Delete' });
    expect(btn.className).toContain('bg-destructive');
  });

  it('default variant uses the brand primary token', () => {
    expect(buttonVariants({ variant: 'default' })).toContain('bg-primary');
  });

  it('fires onClick', async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Go</Button>);
    await userEvent.click(screen.getByRole('button', { name: 'Go' }));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('merges custom className last (tailwind-merge)', () => {
    render(<Button className="bg-card">Override</Button>);
    const btn = screen.getByRole('button', { name: 'Override' });
    const classes = btn.className.split(/\s+/);
    // tailwind-merge drops the conflicting default bg-primary, last-wins.
    // Split on whitespace so `hover:bg-primary-ink` doesn't false-match.
    expect(classes).toContain('bg-card');
    expect(classes).not.toContain('bg-primary');
  });
});

describe('FlagPill', () => {
  it('renders the level label and alert-family token', () => {
    render(<FlagPill level="red" />);
    const pill = screen.getByText('Red');
    expect(pill.className).toContain('text-danger');
  });

  it('falls back to green for unknown levels', () => {
    render(<FlagPill level="purple" />);
    expect(screen.getByText('Green')).toBeInTheDocument();
  });
});

describe('Card', () => {
  it('renders a token-driven surface', () => {
    render(
      <Card data-testid="c">
        <CardTitle>Hi</CardTitle>
      </Card>
    );
    expect(screen.getByTestId('c').className).toContain('bg-card');
    expect(screen.getByText('Hi').tagName).toBe('H3');
  });
});
