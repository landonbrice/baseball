# Program Builder v1 — Plan 6: Mini-App + Coach-App UX & Completion

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development for backend tasks; **superpowers:frontend-design:frontend-design** for the React UI rebuilds. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Land the user-visible half of Program Builder v1: rebuild the mini-app `Programs` tab (single editorial scrolling page per spec D10), add the Builder slide-over (Layer 1 form → Socratic chat → preview), surface programs in Coach Team Overview + a new Coach Team Programs page + PlayerSlideOver Programs tab, wire the three coach builder entry points (build for pitcher / build team program / author template), and **complete Plan 4 by migrating live entry points to the new `checkin_inputs` kwarg shape** so the program-aware fork stops being dormant.

**Architecture:** Two layers of work split into deliberately separated phases — **Phase A (backend)** wires entry points + adds favorites/drafts/lifecycle endpoints + completes Plan 4's parity gaps. **Phase B (UI)** rebuilds the Programs tab, builds the Builder slide-over, rebuilds Team Programs, adds Coach PlayerSlideOver Programs tab. Phase B uses the `frontend-design` skill for new components, and the existing brand shell (tokens, Masthead, Scoreboard, Lede, FlagPill, EditorialState) for layout. **Phase A must be 100% green before Phase B starts** — the UI calls Phase A's endpoints and a half-wired backend leaves the UI undebuggable.

**Tech Stack:** Python 3.11 / FastAPI (backend); React 18 / Vite / Tailwind v4 / shadcn-style components / brand shell from Spec 1-3 (frontend). Tests: pytest + Vitest + RTL.

**Builds on Plans 1–5 (`program-builder-v1-anchoring` tag):** all backend services, atomic counter advance, anchoring, Socratic interview, dormant program-aware fork.

---

## Phase A — Backend completion (must land before UI)

### Task A1: Entry-point migration — wire the dormant Plan 4 fork live

> Plan 4 Task 4.5 left `process_checkin` with an early-return fork that only fires when callers pass `checkin_inputs=` kwarg. No live caller does. Migrate live callers AND complete the legacy-vs-program-path parity (rich entry persistence, two-pass LLM review).

**Files (need inspection by implementer):**
- `pitcher_program_app/bot/handlers/daily_checkin.py` (Telegram bot path)
- `pitcher_program_app/api/routes.py` (`/api/chat` and any check-in endpoint)
- `pitcher_program_app/bot/services/checkin_service.py` (program path needs parity)

**Risk:** This change affects daily check-ins for all 12 pitchers. Goldens stay green only if the legacy positional path remains byte-identical AND the program path is gated correctly.

**Mitigations:**
1. Make the migration backward-compatible — both old positional and new kwarg shapes work.
2. Gate the program-path-with-rich-entry behavior on `feature_flags.program_aware_plan_gen` AND `_has_any_active_program(pitcher_id)` (already implemented).
3. Goldens MUST run between every step.

**Steps:**
- [ ] Audit every caller of `checkin_service.process_checkin`
- [ ] Decide the new signature shape: `process_checkin(pitcher_id, *, arm_feel=None, ..., checkin_inputs=None, ...)` where if `checkin_inputs` is None, build it from positional/legacy kwargs at the top
- [ ] Refactor `process_checkin` so the early-return fork ALWAYS fires for callers with `_is_program_aware_enabled` AND `_has_any_active_program`
- [ ] Add full-fidelity entry persistence on the program path (parity with legacy `pre_training`, rationale, weekly state, progression, context note, etc.)
- [ ] Wire two-pass LLM review onto the program path (extract `_run_two_pass_llm_review(plan, profile, triage_result)` from `plan_generator.generate_plan` if needed; otherwise call `plan_generator.generate_plan` with a pre-composed plan as `pre_composed_plan` kwarg added via small refactor)
- [ ] Run goldens after each refactor — they MUST stay green
- [ ] Smoke test: have `landon_brice` check in via Telegram; verify `daily_entries.plan_generated.source = 'program_prescribed'` and `programs.current_day_index` advanced

### Task A2: Favorites endpoints

**Files:**
- `pitcher_program_app/bot/services/favorites.py` — service layer
- `pitcher_program_app/api/routes.py` — `POST /api/favorites`, `DELETE /api/favorites/{favorite_id}`, `GET /api/favorites?type=...`

Backed by the existing `favorited_blocks` table (Plan 1). `block_type` is one of `lifting | arm_care | throwing | warmup`. Source ref is the new `(source_pitcher_id, source_entry_date)` shape from Plan 1 corrections.

### Task A3: Drafts + History endpoints

- `GET /api/programs/drafts` — pitcher's drafts (status='draft')
- `GET /api/programs/history` — pitcher's archived programs
- `GET /api/programs/active` — pitcher's active programs (per domain)
- Coach mirrors:
  - `GET /api/coach/pitcher/{id}/programs` — all programs for a pitcher (filter by status)
  - `GET /api/coach/pitcher/{id}/drafts` — completed-drafts-only per locked answer (`builder_session.status='completed' AND program.status='draft'`)

### Task A4: Coach Insights additions

Add insight types to existing `coach_insights` / `coach_suggestions` writers:
- "N pitchers' velocity programs have drifted >5 days — consider archiving"
- "{pitcher} built themself an Off-Season Strength block but is currently flagged YELLOW"
- "Team is N weeks into {team_program} — average completion X%, M pitchers at <50%"

### Task A5: Anchoring API + conflict prompt

Wire `program_anchoring.recompute_program_schedule` into:
- `POST /api/programs/{program_id}/recompute` — called by `WeekArc.onAddThrow` (UI Phase B)
- Conflict prompt logic: if a scheduled throw collides with a program-prohibited day, return 409 with `{conflict: ..., requires_confirmation: true}`. UI shows the prompt; on user confirm, retry with `?confirm=true`. Both paths log to `coach_visible_override_events` (the `coach_visible` events when a player overrides the program-prescribed day).

### Task A6: Verification + tag

- Goldens green throughout
- Backend test count target: ~440+
- Tag `program-builder-v1-backend-complete`

---

## Phase B — UI Rebuild (after Phase A is fully green)

> **REQUIRED:** invoke `superpowers:frontend-design:frontend-design` for B1, B3, B4. Brand shell (Spec 1-3) is the substrate — use `Masthead`, `Scoreboard`, `Lede`, `FlagPill`, `EditorialState`, `Toast` from `coach-app/src/components/shell/`.

### Task B1: Mini-app Programs tab rebuild

Replace `mini-app/src/pages/Programs.jsx` with a single editorial scrolling page (spec D10). Sections top-to-bottom:
1. Masthead — kicker "My Programs", title with first name, today's date
2. **Today** — compact summary, source-tagged
3. **Active Programs** — up to 2 cards (throwing + lifting), each with day X/Y, hold count, scheduled-throw anchors, View / Replace
4. **Build a Program** — single primary maroon CTA opening the slide-over
5. **Drafts** — saved-but-not-activated programs
6. **Favorites** — block snapshots, filterable by type
7. **Program History** — archived programs chronologically
8. **Browse Templates** — collapsed canonical templates

### Task B2: Mini-app Home additions

- **Program ribbon** above daily card when active (Velocity 12wk · Day 22 of 84 · Held 2 days)
- **Per-block Favorite button** (heart icon, top-right of each block header)
- **Held affordance** inline note when triage paused a program

### Task B3: Builder slide-over (mini-app)

Three states inside one slide-over:
- **State A: Inputs form** (Layer 1) — domain, goal, duration, start date, hard constraints, "Continue" CTA shows live match count, refuses zero-match
- **State B: Socratic chat** (Layer 2) — bubble UI matching `Coach.jsx`; "I don't know — you decide" tap target on every AI turn; progress indicator
- **State C: Preview** (Layer 4) — header summary + expandable timeline + research citations + Activate / Save as draft / Tweak

Wire to Plan 2 + Plan 3 endpoints (`/builder/candidates`, `/builder/turn`, `/builder/finalize`, `/{program_id}/activate`, `/{program_id}/archive`).

### Task B4: Coach app — Team Overview additions

- HeroCard / CompactCard gain a 2-row program strip per pitcher
- Phase divergence pill per domain (Plan 1 enabled the data; surface in UI)
- Scoreboard cell 5 → "Programs Drifted" (count of `expected_end > nominal_end + 3 days`)

### Task B5: Coach app — PlayerSlideOver Programs tab

Fifth tab alongside Today / Week / History / Profile. Active programs (read-only, Replace opens Build-for-Pitcher); drafts (visible per D14 locked answer = completed-only); history; phase override controls (audited); hold-event log.

### Task B6: Coach app — Team Programs rebuild

Replaces current `coach-app/src/pages/TeamPrograms.jsx`. Masthead with "+ Build Program" actionSlot. Scoreboard. Active Team Programs grid. Library of canonical templates. Player-built programs roster strip.

### Task B7: Coach app — Build Program entry-point selector

Modal sheet from + button:
- Build a team program (Socratic team_personalize mode)
- Build for a specific pitcher (Socratic personalize mode, pitcher-picker first)
- Author a new template (Socratic authoring mode → READY_TO_AUTHOR)

All entry points reuse the same slide-over from B3 with `interview_mode` driving prompt variants.

### Task B8: Coach app — Phases page small update

Each phase in the timeline gains "Templates available in this phase" column.

### Task B9: Coach app — Insights additions wired to the UI

Surface the new insight types from Task A4 in the existing Insights page editorial cards.

### Task B10: Final verification + tag

- All Phase A backend tests + new Vitest UI tests green
- Manual smoke flow for both pitcher (mini-app) and coach (coach-app):
  - Player builds → activates → checks in → sees ribbon → favorites a block → re-uses favorite render-only
  - Coach builds for a pitcher → fans out a team program → views phase divergence pill → archives a drifted program
- Tag `program-builder-v1-complete`

---

## Carry-overs from Plans 1–4 to address in Plan 6

(All flagged in CLAUDE.md follow-ups during Plans 1-4 execution.)

1. **Dormant Plan 4 fork** — A1 lands this
2. **Two-pass LLM review missing on program path** — A1 lands this
3. **Minimal persistence on program path** — A1 lands this
4. **Wrapper-vs-rename `get_pitcher_training_model`** — consolidate at the boundary; low priority
5. **`INT4RANGE` vs `min/max INT` decision** — defer until UI runs into PostgREST friction
6. **Missing CHECK on `block_library.implied_phase`** — add CHECK once phase vocabulary locks
7. **Stray test_pitcher_001 lifting program** — delete during A6 verification
8. **`saved_plans` retention** — decide drop vs read-only archive after A2 ships
9. **`day_focus` derivation in team_scope** — move into plan_generator persistence
10. **Coach app legacy carryovers** (Spec 1/2/3 follow-ups) — sweep during B4-B6

---

## Acceptance criteria

Per the design spec:
1. ✅ A pitcher can build → activate → run → complete a program end-to-end
2. ✅ A coach can build a team program that fans out
3. ✅ A coach can build a program for a specific pitcher
4. ✅ A coach can author a new template
5. ✅ Legacy `plan_generator` produces byte-identical output for pitchers without an active program (goldens)
6. ✅ Triage holds correctly pause counters across Yellow / Red / Critical Red
7. ✅ Phase precedence resolves correctly for all four input combinations
8. ✅ Scheduled-throw add/move/delete recomputes program schedules
9. ✅ Builder slide-over works from both player Programs tab and coach Team Programs page
10. ✅ Per-block Favorites store immutable snapshots that re-run in render-only mode

## Execution

Phase A first (subagent-driven). Then Phase B with `frontend-design` skill explicitly invoked for B1, B3, B4. Phase B should NOT start until A6 tag lands. Goldens are the immune system — every refactor in either phase MUST keep them green.
