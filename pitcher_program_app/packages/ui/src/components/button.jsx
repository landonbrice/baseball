import { forwardRef } from 'react';
import { cva } from 'class-variance-authority';
import { cn } from '../lib/utils';

/**
 * Button — shadcn-convention button driven by cva variants + design tokens.
 * Every color is a semantic token, so it re-skins automatically under [data-brand].
 */
export const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium font-sans transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground hover:bg-primary-ink',
        secondary: 'bg-secondary text-secondary-foreground hover:bg-muted',
        outline:
          'border border-input bg-card text-foreground hover:bg-muted',
        ghost: 'text-foreground hover:bg-muted',
        destructive:
          'bg-destructive text-destructive-foreground hover:opacity-90',
        link: 'text-primary underline-offset-4 hover:underline',
      },
      size: {
        sm: 'h-8 px-3 text-xs',
        md: 'h-9 px-4',
        lg: 'h-10 px-6',
        icon: 'h-9 w-9',
      },
    },
    defaultVariants: { variant: 'default', size: 'md' },
  }
);

export const Button = forwardRef(function Button(
  { className, variant, size, type = 'button', ...props },
  ref
) {
  return (
    <button
      ref={ref}
      type={type}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  );
});
