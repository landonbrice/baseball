# Coach Dashboard Redesign — Spec 1: Brand System & Shell

> Status: Design-approved 2026-04-18
> Phasing: Spec 1 of 3. Must merge before Spec 2 (Team Overview) and Spec 3 (Secondary Pages + Nudge Backend).

## Context

The coach dashboard (`pitcher_program_app/coach-app`) shipped end-to-end in Phase 20.1 but feels like a generic admin template: flat Tailwind defaults, thin typography, and a palette that doesn't signal UChicago Baseball. This spec establishes the visual foundation everything else hangs from.

Design language chosen: **Editorial + Numbers-First**. Think The Athletic's typographic authority with Baseball Savant's data-forward hierarchy. Maroon as featured brand color; crimson reserved for RED-flag alerts only. Source Serif 4 for display, Inter for UI.

Audience: UChicago pitching staff (HC / PC / S&C). One shared dashboard. Desktop-first, responsive to tablet. No dark mode, no mobile optimization, no role-based views in v1.

## Goals

- **Brand**: the dashboard looks unmistakably like a UChicago Baseball product, not a SaaS admin.
- **Density**: numbers lead; scoreboards and serif tabular numerals carry the weight.
- **Consistency**: every page uses the same shell (Sidebar + Masthead + Scoreboard), so Spec 2 and Spec 3 can focus on page-specific content.
- **Accessibility**: WCAG AA contrast, 12px body minimum, never rely on color alone for status.

## Non-goals

- Mobile < 768px
- Dark mode (defer — editorial cream palette is hostile to inversion)
- Role-based view filtering (same dashboard for HC / PC / S&C)
- Keyboard shortcuts / command palette
- New chart library (existing Chart.js stays)

## Typography

### Font families
- **Source Serif 4** (self-hosted from Google Fonts) — display, pitcher names, scoreboard values, section labels. Weights: 400, 600, 700. Load `woff2` subset (Latin + latin-ext, ~40kb).
- **Inter** (already in Tailwind stack) — UI, body, meta, captions. Weights: 400, 500, 600, 700.
- **Tabular numerals**: `font-variant-numeric: tabular-nums` applied globally on `.scoreboard-value`, `td.num`, `.stat-value`. Alignment matters for data scanning.

### Type scale
| Token | Size / Line | Family / Weight | Use |
|---|---|---|---|
| `display` | 32 / 1.05 | Source Serif 700 | page masthead titles |
| `h1` | 24 / 1.15 | Source Serif 700 | scoreboard values, hero-card names |
| `h2` | 17 / 1.25 | Source Serif 700 | hero-card names in context |
| `h3` | 14 / 1.35 | Source Serif 700 | compact-card names, row names |
| `kicker` | 10 / 1.0 | Inter 600 caps 0.2em | above-title labels, section headers |
| `eyebrow` | 9 / 1.0 | Inter 600 caps 0.16em | scoreboard/column labels |
| `body` | 13 / 1.5 | Inter 400 | lede, card content |
| `body-sm` | 12 / 1.4 | Inter 400 | card objective text |
| `meta` | 11 / 1.3 | Inter 400 | row sub-labels |
| `micro` | 10 / 1.2 | Inter 400 | pending strip, timestamps |

Expose as Tailwind `@theme` tokens: `--text-display`, `--text-h1`, etc. Each token pairs size + line-height; the family/weight applies via component classes (`.font-serif`, `.font-ui`).

### Font loading
- Add `<link rel="preconnect">` and self-hosted `@font-face` for Source Serif 4 in `coach-app/index.html`.
- `font-display: swap` to avoid FOIT.
- Inter continues via the existing system-font stack — no new network cost.

## Color system

Extend `coach-app/src/index.css` `@theme`:

```css
@theme {
  /* Brand — never alert */
  --color-maroon:       #5c1020;
  --color-maroon-ink:   #7a1a2e;  /* hover */
  --color-rose:         #e8a0aa;  /* decorative accent (hero-card wash, pending strip highlight) */

  /* Alert / flag — never brand */
  --color-crimson:      #c0392b;
  --color-amber:        #d4a017;
  --color-forest:       #2d5a3d;

  /* Surface */
  --color-cream:        #f7f1e3;
  --color-cream-dark:   #e4d9c5;
  --color-parchment:    #faf6ec;  /* masthead band, scoreboard band */
  --color-bone:         #ffffff;  /* cards, table rows */
  --color-hover:        #f4efe0;

  /* Ink */
  --color-charcoal:     #1a1613;
  --color-graphite:     #3a2e24;
  --color-subtle:       #6b5f53;
  --color-muted:        #8a7a6b;
  --color-ghost:        #b8a88f;
}
```

### Color semantics (enforced)
- **Maroon**: masthead underline, sidebar team-name, kicker labels, section headers, brand stamps, primary CTAs. Never used for RED flags.
- **Rose**: decorative-only. Hero-card background wash on hover, pending-strip subtle fill, serif drop-cap variants. Never carries meaning.
- **Parchment**: backgrounds for the masthead/scoreboard band, lede container, injury-context chips inside hero cards.
- **Crimson**: RED flag pill, RED hero-card left-border, RED flag dot, crimson-downstream error toasts.
- **Amber**: YELLOW flag variants, pending check-in strip border.
- **Forest**: GREEN flag variants, positive delta arrows, success toasts.

### Accessibility
- `charcoal on cream` ≥ 12:1
- `subtle on cream` ≥ 5.5:1
- `crimson on cream` ≥ 4.5:1 (verify pill text)
- `crimson (#fff) on crimson bg` for flag pills ≥ 4.5:1
- All flag pills pair color with text label ("Red", "Yellow", "Green"). No color-only status anywhere.
- Focus rings: 2px `--color-maroon` outline, 2px offset on every focusable element.

## Spacing, radius, borders

- Spacing: Tailwind default scale (4/8/12/16/20/24/32/48). No custom micro-steps.
- Radius: `3px` (cards, pills), `4px` (frame), `2px` (badges, flag pills). No `rounded-full` anywhere — editorial ≠ cute. Exception: sidebar active-state indicator may use `2px` radius inset.
- Border weights:
  - `1px` default (cards, table rows, dividers)
  - `1.5px` for section-defining rules (under section labels)
  - `2px` for masthead underline
  - `4px` for hero-card left border (color-tied to flag)
  - `3px` for compact-card left border (forest green for On Track)

## Shared components

All components live in `coach-app/src/components/shell/`.

### `<Sidebar>`
- Width: **192px** (down from 208px).
- Structure:
  - Top: `<TeamBrand>` — team name in Source Serif 700 17px maroon; coach name meta beneath in Inter 11px muted.
  - Middle: nav list (5 items). Active state = maroon text + `--color-hover` background + 2px inset maroon left-edge bar.
  - Bottom: sign-out button, Inter 11px, muted hover charcoal.
- Border-right: 1px `--color-cream-dark`.
- Props: none (reads team/coach from `useCoachAuth`).
- Responsive: fixed width at ≥ 1024px; below 1024px, collapses to a top bar with hamburger (out of scope for v1 — `overflow: hidden` until we redesign for tablet).

### `<Masthead kicker title date week actionSlot>`
- Full-width page header.
- Left: kicker (Inter caps maroon) over serif title (display size, charcoal, -0.015em tracking).
- Right: date in Inter 11px muted, week context in Inter 12px charcoal 600 below.
- Optional `actionSlot` — used on Team Programs (`+ New Program` button) and Phases (`+ Add Phase`).
- Below: 2px maroon underline, 14px bottom margin.
- Props:
  ```ts
  { kicker: string; title: string; date: string; week?: string; actionSlot?: ReactNode }
  ```

### `<Scoreboard cells>`
- 5-cell grid (`grid-cols-5`), top and bottom 1px rules in `--color-cream-dark`, `--color-parchment` background fill, 14px vertical padding.
- Each cell separated by 1px right-border (hidden on last).
- Cell structure: `eyebrow` label → serif `h1` value → Inter meta sub.
- Handles missing data: if `value` is nullish, cell shows label + "—" in `--color-muted`; no crash.
- Supports inline color spans inside the value (e.g., `<span class="text-forest">9</span> · <span class="text-amber">2</span> · <span class="text-crimson">1</span>` for flag counts).
- Props:
  ```ts
  {
    cells: Array<{
      label: string;
      value: ReactNode;
      sub?: string;
    }>  // length must be 5
  }
  ```

### `<Lede children maxWidth="720px">`
- Italic Source Serif, `body` size, 3px maroon left border, 10px top/bottom padding, 14px left padding, `--color-parchment` background, `0 3px 3px 0` radius.
- Max-width default 720px.
- Supports `<b>` inline for emphasized pitcher names (non-italic, maroon 700).

### `<FlagPill level>`
- `level ∈ {'red' | 'yellow' | 'green' | 'pending'}`.
- Inter 600 9px caps 0.12em, 3/7 padding, 2px radius.
- Color map:
  - `red` → bg `--color-crimson`, text `--color-bone`
  - `yellow` → bg `--color-amber`, text `--color-charcoal`
  - `green` → bg `--color-forest`, text `--color-bone`
  - `pending` → bg transparent, border 1px `--color-ghost`, text `--color-ghost`

### `<EditorialState type copy retry?>`
- `type ∈ {'loading' | 'empty' | 'error'}`.
- Renders: optional skeleton shape (for `loading`), italic serif caption in Lede styling, optional retry button for `error`.
- Loading copy provided per-context (e.g., "Gathering the morning check-ins...").
- Empty copy provided per-context.
- Error copy default: "Something's off on our end. Try again in a moment." Override via `copy` prop.
- Props:
  ```ts
  { type: 'loading' | 'empty' | 'error'; copy: string; retry?: () => void }
  ```

### `<Toast tone ttl>`
- `tone ∈ {'success' | 'warn' | 'error' | 'info'}`.
- Fixed bottom-right, 3px radius, 1px border matching tone.
- Tone colors: success → forest, warn → amber, error → crimson, info → maroon.
- Replaces current `Toast.jsx`.

## File structure

```
coach-app/src/
├── components/
│   ├── shell/
│   │   ├── Sidebar.jsx        (replaces Shell.jsx sidebar portion)
│   │   ├── TeamBrand.jsx
│   │   ├── Masthead.jsx
│   │   ├── Scoreboard.jsx
│   │   ├── Lede.jsx
│   │   ├── FlagPill.jsx
│   │   ├── EditorialState.jsx
│   │   └── Toast.jsx          (restyled)
│   └── ... (existing page-specific components, unchanged in Spec 1)
├── styles/
│   └── tokens.css             (new — imports fonts, defines @theme extensions)
└── index.css                  (imports tokens.css)
```

## Data flow

- Spec 1 is pure presentation; no new endpoints, no schema changes, no data-fetching logic.
- `<Sidebar>` reads `coach.team_name` + `coach.coach_name` from `useCoachAuth()` context. **Known blocker**: `/api/coach/auth/exchange` currently returns only `coach_id / team_id / coach_name / role` — missing `team_name`. Spec 1 assumes this is fixed before merge (it's already the next-up item per CLAUDE.md). If not fixed, Sidebar falls back to "Dashboard" as it does today.

## Migration

- Spec 1 does NOT touch page contents; only the outer `Shell` is swapped. All 5 existing pages continue to work — they're wrapped in the new Sidebar + a stub Masthead until Specs 2 and 3 replace the internals.
- For each existing page, add a temporary Masthead at the top during Spec 1 rollout (`<Masthead kicker="Chicago · Pitching Staff" title={pageTitle} date={today} />`) so pages aren't un-styled mid-transition.
- Old `Shell.jsx` is deleted once every page imports the new `<Sidebar>` + `<Masthead>` directly.

## Testing

- **Component tests** (Vitest + React Testing Library):
  - `<Scoreboard>` — renders 5 cells, missing value shows em-dash, accepts ReactNode value.
  - `<Masthead>` — renders kicker/title/date/week + optional actionSlot.
  - `<FlagPill>` — all 4 levels render with correct colors and text.
  - `<EditorialState>` — renders correct skeleton/copy per type, retry fires callback.
- **Visual smoke test**: Storybook-lite page at `/__design` (only in dev, gated by `import.meta.env.DEV`) rendering each shared component in isolation.
- **Accessibility**: axe-core automated run on the `/__design` page. Manual keyboard-only nav through sidebar.
- **Token contract test**: simple unit test asserting every CSS custom prop the spec defines actually exists in the compiled CSS.

## Acceptance criteria

1. Every existing coach-app page renders with the new Sidebar and a stub Masthead — no visual regressions beyond intended redesign.
2. Source Serif 4 loads and renders at all weights; falls back gracefully to Georgia if blocked.
3. No crimson appears anywhere on pages except where tied to a RED flag. No maroon appears on anything flag-status-tied.
4. Shared components render correctly in the `/__design` page and pass accessibility checks.
5. All colors meet WCAG AA contrast thresholds listed in the Accessibility section.
6. `/api/coach/auth/exchange` returns `team_name` — verified by the sidebar rendering the real team name, not "Dashboard".

## Open questions (pre-plan)

None. All design decisions locked via brainstorming.
