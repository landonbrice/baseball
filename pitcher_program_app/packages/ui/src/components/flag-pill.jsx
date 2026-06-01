import { cva } from 'class-variance-authority';
import { cn } from '../lib/utils';

/**
 * FlagPill — domain primitive for readiness state (green/yellow/red).
 * Uses the alert/domain token family (success/warning/danger), NOT brand colors.
 * Consolidates coach-app's FlagPill and mini-app's FlagBadge into one source.
 */
const pill = cva(
  'inline-flex items-center rounded-sm px-2 py-0.5 font-sans text-[10px] font-semibold uppercase tracking-[0.12em]',
  {
    variants: {
      level: {
        green: 'bg-success/12 text-success',
        yellow: 'bg-warning/15 text-warning',
        red: 'bg-danger/12 text-danger',
      },
    },
    defaultVariants: { level: 'green' },
  }
);

const LABEL = { green: 'Green', yellow: 'Yellow', red: 'Red' };

export function FlagPill({ level = 'green', className, children }) {
  const key = LABEL[level] ? level : 'green';
  return (
    <span className={cn(pill({ level: key }), className)}>
      {children ?? LABEL[key]}
    </span>
  );
}
