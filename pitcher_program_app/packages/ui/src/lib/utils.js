import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * cn — shadcn's class-merge helper. Combines clsx (conditional classes) with
 * tailwind-merge (dedupes conflicting Tailwind utilities, last-wins).
 * @param  {...any} inputs
 * @returns {string}
 */
export function cn(...inputs) {
  return twMerge(clsx(inputs));
}
