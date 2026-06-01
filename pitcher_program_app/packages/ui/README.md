# @cue/ui

Shared design system for the **Cue** (B2B, general) and **UChicago Baseball** (first tenant) apps.
Built on **shadcn / Tailwind-v4 conventions** so Claude-Design → Claude-Code ship-to-code
handoffs land natively.

> Status: Phase 0.1 (foundation). Self-contained and **additive** — not yet wired into the live
> mini-app/coach-app. See `docs/frontend-design-system-roadmap.md`.

## Conventions

- **Semantic tokens** (`background`, `foreground`, `card`, `primary`, `secondary`, `muted`,
  `accent`, `destructive`, `border`, `input`, `ring`) + **domain tokens** for readiness flags
  (`success`/`warning`/`danger`). Brand (maroon/rose) and alert (crimson/amber/forest) families
  are kept strictly separate — never cross them.
- **Dual-brand** via `<html data-brand="uchicago">` (default) or `data-brand="cue"`. Switching the
  attribute live re-skins everything (`@theme inline` resolves vars at use-time).
- **`cn()`** (clsx + tailwind-merge) for class composition; **cva** for variants — the shadcn idiom.
- Tokens-in / components-out. Claude Design output is a *spec* to fold in here, or it conforms to
  these tokens. `brand-guidelines.md` is the binding contract.

## Usage (once wired in — Convergence phase)

```css
/* app entry CSS */
@import "tailwindcss";
@import "@cue/ui/styles/tokens.css";
```

```jsx
import { Button, Card, FlagPill } from '@cue/ui';
```

## Adding a shadcn component

Drop the component into `src/components/`, swap its imports to `../lib/utils`, ensure every color
is a semantic token (no raw hex), export it from `src/index.js`, and add a render test.

## Cue brand is a PLACEHOLDER

`[data-brand='cue']` in `tokens.css` ships an obviously-distinct indigo/teal placeholder so the
brand switch is demonstrable. Replace with the real palette from the owner's Claude Design
`brand-guidelines.md` (roadmap phase 0.3).

## Test

```bash
pnpm install      # first time
pnpm test:run     # token contract + component render tests
```
