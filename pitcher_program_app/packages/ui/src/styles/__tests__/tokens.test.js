import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const css = readFileSync(resolve(__dirname, '../tokens.css'), 'utf8');

/**
 * Token contract: locks the semantic token surface so a stray edit to tokens.css
 * cannot silently drop a role that components depend on. Mirrors coach-app's
 * tokens.test.jsx pattern, extended to enforce the dual-brand structure.
 */
const REQUIRED_TOKENS = [
  '--background',
  '--foreground',
  '--card',
  '--card-foreground',
  '--popover',
  '--popover-foreground',
  '--primary',
  '--primary-foreground',
  '--primary-ink',
  '--secondary',
  '--secondary-foreground',
  '--muted',
  '--muted-foreground',
  '--accent',
  '--accent-foreground',
  '--destructive',
  '--destructive-foreground',
  '--border',
  '--input',
  '--ring',
  '--success',
  '--warning',
  '--danger',
  '--radius',
  '--font-serif',
  '--font-sans',
];

/**
 * sliceBlock — returns the brace-balanced body that follows the first occurrence
 * of `marker`. Used to scope assertions to a single brand block.
 */
function sliceBlock(marker) {
  const start = css.indexOf(marker);
  if (start === -1) return '';
  const open = css.indexOf('{', start);
  if (open === -1) return '';
  let depth = 1;
  let i = open + 1;
  while (i < css.length && depth > 0) {
    if (css[i] === '{') depth += 1;
    else if (css[i] === '}') depth -= 1;
    i += 1;
  }
  return css.slice(open + 1, i - 1);
}

const uchicago = sliceBlock("[data-brand='uchicago']");
const cue = sliceBlock("[data-brand='cue']");

describe('design tokens contract', () => {
  it('declares both brand layers', () => {
    expect(css).toContain("data-brand='uchicago'");
    expect(css).toContain("data-brand='cue'");
  });

  it.each(REQUIRED_TOKENS)('UChicago brand defines %s', (token) => {
    expect(uchicago).toContain(`${token}:`);
  });

  it.each(REQUIRED_TOKENS)('Cue brand overrides %s', (token) => {
    expect(cue).toContain(`${token}:`);
  });

  it('maps semantic vars into Tailwind via @theme inline', () => {
    // These mapping strings are unique to the @theme inline block, so assert
    // against the whole stylesheet — no fragile block extraction needed.
    expect(css).toContain('--color-primary: var(--primary)');
    expect(css).toContain('--color-background: var(--background)');
    expect(css).toContain('--color-success: var(--success)');
    expect(css).toContain('@theme inline');
  });

  it('keeps brand (maroon) distinct from the alert family', () => {
    // UChicago primary is maroon; destructive/danger is crimson — never equal.
    expect(uchicago).toContain('--primary: #5c1020');
    expect(uchicago).toContain('--danger: #c0392b');
  });

  it('Cue is visibly different from UChicago primary (placeholder sanity)', () => {
    expect(uchicago).toContain('--primary: #5c1020');
    expect(cue).not.toContain('--primary: #5c1020');
  });
});
