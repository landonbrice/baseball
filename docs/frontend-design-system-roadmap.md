# Frontend / Design-System Split — Living Roadmap

> Owner: Landon · Started: 2026-05-31 · Branch: `claude/magical-knuth-CfIm9`
> This is the **source of truth** for the FE decoupling + dual-brand design-system effort.
> Update the "Status" column as phases land. Verify each phase is correct before advancing.

## Goal (in the owner's words)

1. Stop backend changes from breaking the UI, and stop UI changes from bleeding into the backend.
2. A polished, themeable UI I can *think through* and change specific things without breaking others.
3. Split into two products on **one shared backend**:
   - **UChicago Baseball** — the existing team (first tenant).
   - **Cue** — the same product (B2B, other programs) under a different brand.
4. Two fixed brand themes **for now**, architected so per-team theming can be added later.
5. `packages/ui` follows **Claude Design / shadcn conventions** so Claude-Design → Claude-Code ship-to-code handoffs land natively.

## The reframe (from the audit)

The literal FE/BE *split already exists and is clean* — the boundary is pure HTTP (no JS↔Python imports). The real problems are three:

| # | Problem | Evidence |
|---|---------|----------|
| 1 | **No contract** on the clean HTTP boundary | 0 `response_model=` on ~100 FastAPI endpoints; 0 TypeScript; 0 fixtures; 0 mocks. ~110 call sites read raw JSONB by convention. |
| 2 | **Two frontends diverged into two stacks** | coach-app: React 19 / Vite 8 / Tailwind 4 / Vitest 4. mini-app: React 18 / Vite 6 / Tailwind 3 / Vitest 2. ~295 hardcoded hex in mini-app (incl. wrong maroon `#800000`). Shared layer = 2 loose files behind fragile per-file Vite aliases. |
| 3 | **Single-tenant assumptions in a multi-tenant-ready backend** | ~6 hardcoded `uchicago_baseball` defaults; `pitchers.team_id DEFAULT 'uchicago_baseball'`; unauth `/api/staff/pulse` default; single-team 9am insight loop. Backend data model + auth + read service are otherwise team-scoped (~70% ready). |

## Working agreement (parallel tracks)

- **Track A — Brand (owner, in Claude Design):** onboard, explore UChicago + Cue, produce a `brand-guidelines.md`. Output = a *spec*, not repo code. Don't ship-to-code into the live apps yet.
- **Track B — Receptacle (Claude, in repo):** build `packages/ui` (shadcn conventions) + theming + catalog, then the convergence + contract work.
- **Rendezvous:** when `packages/ui` exists **and** the brand is settled, re-onboard Claude Design against the clean codebase + `brand-guidelines.md` and ship-to-code the primitives.
- **Discipline:** `packages/ui` = tokens-in / components-out. Claude Design output is treated as a spec to extract tokens/contracts from — or it conforms to the converged package. `brand-guidelines.md` is the binding contract.

## Repo strategy (decided)

Monorepo with shared JS packages **inside `pitcher_program_app/`** (keeps Railway/Vercel roots sane). NOT a repo split (would solve the already-clean boundary while worsening the real need: sharing JS + a design system + Cue). Backend (`bot/` + `api/`) stays a single Railway process, untouched except the tenant-leak patches.

Target shape (end state):
```
pitcher_program_app/
  apps/      mini-app, coach-app        (thin Vite apps)
  packages/  ui (tokens + primitives), api-client, fixtures, config
  bot/ api/  (Python backend — unchanged)
  pnpm-workspace.yaml
```
> Note: workspace consolidation + moving apps under `apps/` is deferred to the **Convergence** phase. Until then `packages/ui` is self-contained (its own install) so it is **additive and zero-risk** to the live apps. npm in each app is unaffected as long as no ancestor `package.json` declares a `workspaces` field.

## Phases

| Phase | Name | Risk | Depends on | Status |
|------|------|------|-----------|--------|
| 0.1 | `packages/ui` foundation — shadcn tokens + theming + seed primitives + contract test | none (additive) | — | **done** (PR #33, 64 tests) |
| 0.2 | Storybook 10 + brand-switcher toolbar + story-driven DOM snapshot regression guard | none (additive) | 0.1 | **in progress** |
| 0.3 | Fill Cue brand tokens from `brand-guidelines.md` | none | Track A, 0.1 | todo (needs owner) |
| 1.0 | Convergence: pnpm workspace; mini-app → React 19 + Tailwind 4 + Vite/Vitest/Router bumps; `shared/` → package | **high** (touches live mini-app) | 0.1 | todo |
| 1.1 | Tokenize mini-app: eliminate ~295 hex; both apps consume `packages/ui` tokens | med | 1.0 | todo |
| 1.2 | Extract + de-dupe primitives (Button, Card, SlideOver/Modal, Toast×2→1, FlagPill/FlagBadge→1, EditorialState, WeekStrip×2→1); fix shared `BuilderSlideOver` var refs | med | 1.0, 1.1 | todo |
| 2.0 | Fixtures + MSW + `VITE_USE_MOCKS` → both apps run with **zero backend** | low | 1.0 | todo |
| 2.1 | Graduate `/__design` into a real in-app catalog (full inventory + live brand switch) | low | 1.2, 0.2 | todo |
| 3.0 | Contract hardening: `response_model` on ~10 hotspot endpoints → OpenAPI → generated types/fixtures | med | — | todo |
| 3.1 | View-model adapter layer for hottest JSONB consumers; route 2 rogue `DailyCard` fetches through the client; structure `/chat` string-sentinels | med | 3.0 | todo |
| 4.0 | **Tenant-leak patches** (do early; security): drop `pitchers.team_id` default, require `team_id` on `/api/staff/pulse`, remove `uchicago_baseball` fallbacks in `plan_generator`/`exercise_pool` | low | — | todo |
| 4.1 | Cue/UChicago tenancy: per-team 9am insight loop; multi-origin CORS; replace 6 hardcoded coach kickers with `coach.team_name`; parameterize bot greeting + coach-chat prompt; per-brand titles/manifest/favicons | med | 4.0 | todo |
| 4.2 | Deployment topology decision (one dynamically-themed FE vs per-brand Vercel projects w/ `VITE_BRAND`) | — | 4.1 | todo |

## Token reconciliation decisions (pending owner ratification)

Canonical = **coach-app editorial palette** (the intentional redesign brand). mini-app values mapped onto it. Deltas to ratify:

| Role | coach-app (canonical) | mini-app (legacy) | Decision |
|------|----------------------|-------------------|----------|
| surface/background | cream `#f7f1e3` | `#f5f1eb` | use coach `#f7f1e3` |
| ink/foreground | charcoal `#1a1613` | `#2a1a18` | use coach `#1a1613` |
| border | cream-dark `#e4d9c5` | `#e4dfd8` | use coach `#e4d9c5` |
| flag green (success) | forest `#2d5a3d` | `#1D9E75` | use coach `#2d5a3d` |
| flag amber (warning) | amber `#d4a017` | `#BA7517` | use coach `#d4a017` |
| flag red (danger) | crimson `#c0392b` | `#A32D2D` | use coach `#c0392b` |
| primary (maroon) | `#5c1020` | `#5c1020` | identical ✓ |

> These are *defaults I'm proceeding on*. If your Claude Design `brand-guidelines.md` says otherwise for UChicago, it wins — tell me and I'll re-point the tokens.

## What I need from the owner

- **Cue palette** (background / primary / accent / flags / fonts / radius) — from Claude Design. Until then `packages/ui` ships a clearly-labeled **placeholder** Cue theme so the brand switch is demonstrable.
- The `brand-guidelines.md` at rendezvous (drives 0.3 + the convergence visuals).
- Ratify the reconciliation table above (or correct it).

## Open questions / parked

- shadcn semantic-token naming vs the editorial vocabulary (`charcoal`/`graphite`/`cream`) — bridged: semantic tokens are canonical in `packages/ui`; editorial names kept as aliases during migration.
- **Visual-regression host — DECIDED (0.2):** this sandbox has no browser (no Chrome/Playwright), so pixel-diff (Chromatic/Playwright) can't run here and Chromatic would need an owner-supplied token. 0.2 ships **story-driven DOM snapshots** via `composeStories` + Vitest — the headless regression guard that runs in CI today. Pixel-diff layers on top of the *same stories* later with zero rework (decide host when a browser/CI runner + token are available).
- Deployment topology (4.2) — decide once Cue is real.
