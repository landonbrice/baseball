# Program Builder — v1 Design

> **Date:** 2026-04-30
> **Status:** Brainstorm-approved, awaiting plan
> **Scope:** Player- and coach-initiated AI-assisted program building with a unified data model. Includes mini-app Programs tab redesign, coach-app Team Programs rebuild, and a daily-composition pipeline rewrite.

## Why this exists

Players have no path to build their own training programs. The current 7-day starter cadence is the only program model in the system, so non-pitching in-season players, returning-from-injury pitchers, and anyone with off-season strength goals fall through the cracks. The core pain: *"there's a number of players who aren't actually pitching during the season; the seven-day program isn't effective for them."*

The fix is two parallel capabilities, both grounded in the same builder:
- **Players** can build programs from structured inputs + a Socratic AI interview, save sessions they like, and run their own multi-week blocks.
- **Coaches** can build templates, build programs for individual pitchers, or fan out team-wide programs — all through the same builder with mode-specific prompts.

The Coach app remains *the back-end view of what every player is doing*, with three high-leverage write paths layered on top.

## Decisions locked during brainstorming

These were debated and resolved one at a time. They are not up for renegotiation in implementation.

| # | Decision | Rationale |
|---|---|---|
| D1 | Two object types: **Session** (a day's plan, immutable, favoritable) and **Program** (multi-week scheduler producing daily sessions). | Separates lifecycles cleanly; favoriting and program-state never collide. |
| D2 | Programs are **hybrid-typed**: one Throwing slot + one Lifting slot active per pitcher simultaneously. | Real cases compose this way (e.g., return-to-mound throwing + off-season strength). |
| D3 | Builder is **template-anchored** with structured inputs as the front door, AI Socratic interview as the funnel, LLM reasoning + research docs as the substrate. | Templates are the safety floor; AI personalizes within vetted bounds. |
| D4 | Sessions favorited from Home are **orthogonal** — pure snapshots in a Library/Favorites shelf, separate from program state. Verb is "favorite," not "save." | Player asked for it; clean isolation prevents Home logic from leaking into Programs logic. |
| D5 | Coach v1 builder scope: **author templates + build for pitcher + AI-uplifted team assign**. Approval/review loop deferred. | High-leverage authoring; symmetric capability with player; minimal new UI. |
| D6 | Season phase is **per-domain (throwing / lifting), computed via precedence stack**: active program implied phase > coach per-pitcher override > team default. Coach roster surfaces divergence. | No conflict between coach and player; phase always answerable from observable state. |
| D7 | Triage composition for v1: **B — program holds, triage pauses counter** when downgraded. C (modify-within-program) is the v2 target. | Smallest engine change; preserves safety story; honest about what work happened. |
| D8 | Per-block favorite from Home (Lifting OR Arm Care OR Throwing OR Warmup), each its own snapshot. | Captures intent at the block grain where players feel it. |
| D9 | Activating a new program in an occupied slot triggers **confirm-then-archive** with progress preserved in History. | Prevents accidental clobber of weeks of progress. |
| D10 | Programs tab IA is a **single scrolling editorial page** with sections (Today / Active / Build CTA / Drafts / Favorites / History / Browse Templates). | Matches Spec 1/2/3 brand pattern; avoids tab fragmentation. |
| D11 | Coach AI uplift on team assign reuses **the same Socratic builder in coach mode**. | One builder, three entry points; ~95% shared code. |
| D12 | **Scheduled throws are program anchors, not conflicts.** Templates may declare anchor-relative days that re-position around `team_games` and player-scheduled throws. | Player calendar agency wins; program intensity intent wins; no fight. |
| D13 | Favorites Run-Again is **render-only** — does not write to `daily_entries` or touch program state. | Preserves strict orthogonality of Sessions vs Programs. |
| D14 | Coaches **can** see player drafts (always-on); **cannot** see player Favorites (privacy). | Drafts are conversation-worthy signals; Favorites are personal bookmarks. |
| D15 | Hand-edit of generated weeks is **out of v1**. Players regenerate to change a week. | Preserves the safety story (no unvalidated schedules). |
| D16 | Builder regeneration is **capped at 3** per session, soft-warned at 2. | Cost control + prevents indecision spirals. |
| D17 | Builder sessions are **persistent for 24h** so a player can resume a Socratic conversation. | Small UX win, disproportionate value. |

Three deferred decisions are documented in memory for future revisits:
- Coach review/approve/edit governance loop on player-built programs (`project_program_builder_governance_deferred.md`)
- Triage approach C — modify-within-program (`project_program_triage_composition_v2.md`)
- Coach manual program-counter override (`project_program_coach_counter_override_deferred.md`)

## Section 1 — Object & Data Model

### Three first-class objects

**Template** — canonical multi-week scaffold. Lives in expanded `block_library`. Adds columns:
- `domain` — `'throwing' | 'lifting'`
- `goal_tags` — text[] (e.g., `['return_to_mound']`)
- `duration_range_weeks` — int4range
- `compatible_phases` — text[]
- `tunable_parameters_schema` — jsonb (declares which parameters the Socratic interview may set, with type + bounds)
- `week_scaffold_json` — jsonb (canonical week-by-week structure with placeholders; supports calendar-relative *and* anchor-relative day declarations)
- `research_doc_ids` — text[] (which research docs the resolver should pull)
- `modification_rules_json` — jsonb, **nullable, unused in v1** (reserved for v2 triage approach C)
- `implied_phase` — text (the phase activating this template implies — e.g., `return_to_mound`)

**Program** — personalized, activatable instance. New table `programs`:
```
program_id           uuid pk
pitcher_id           text fk → pitchers(pitcher_id)
parent_template_id   uuid fk → block_library
domain               text -- 'throwing' | 'lifting'
tuned_spec_json      jsonb -- output of Socratic interview
generated_schedule_json jsonb -- day-by-day schedule
start_date           date
nominal_end_date     date
current_day_index    int default 0
held_days_count      int default 0
status               text -- 'draft' | 'active' | 'archived' | 'error'
created_by           text -- pitcher_id or coach_id
created_by_role      text -- 'pitcher' | 'coach'
approval_required    bool default false -- reserved for v1.5 governance
created_at           timestamptz
activated_at         timestamptz nullable
archived_at          timestamptz nullable
archive_reason       text nullable
```
Partial unique index on `(pitcher_id, domain) WHERE status = 'active'` enforces "one active per slot per pitcher."

**Favorite** — immutable block snapshot. New table `favorited_blocks`:
```
favorite_id           uuid pk
pitcher_id            text fk
source_daily_entry_id uuid fk
block_type            text -- 'lifting' | 'arm_care' | 'throwing' | 'warmup'
block_snapshot_json   jsonb
note                  text nullable
favorited_at          timestamptz
```
No update path. No mutations. Pure snapshot.

### Phase model

`pitcher_training_model` adds two nullable columns:
- `coach_throwing_phase_override` text
- `coach_lifting_phase_override` text

A new helper:
```python
def get_effective_phase(pitcher_id: str, domain: str) -> str:
    active = programs.select_active(pitcher_id, domain)
    if active:
        return active.parent_template.implied_phase
    override = pitcher_training_model.get(f'coach_{domain}_phase_override')
    if override:
        return override
    return team.training_phase
```
Consumed by: builder gate, coach roster phase pill, daily composition pipeline.

### Builder session telemetry

New table `program_builder_sessions`:
```
session_id            uuid pk
pitcher_id            text fk
initiator_id          text -- pitcher_id or coach_id
initiator_role        text -- 'pitcher' | 'coach'
interview_mode        text -- 'personalize' | 'team_personalize' | 'authoring'
constraint_envelope_json jsonb -- Layer 1 output
candidate_template_ids text[] -- Layer 1 narrowed set
turns_jsonb           jsonb -- ordered conversation
chosen_template_id    uuid nullable
tuned_spec_json       jsonb nullable
status                text -- 'in_progress' | 'completed' | 'abandoned'
started_at            timestamptz
last_activity_at      timestamptz
generated_program_id  uuid nullable fk → programs
```
Sessions auto-abandon after 24h of inactivity.

### Operational tables

- `program_hold_events` — `(program_id, hold_date, triage_result, reason_code, created_at)` — every triage-paused day
- `program_schedule_revisions` — `(program_id, revised_at, trigger_type, old_schedule, new_schedule)` — every recompute
- `program_generation_failures` — `(session_id, attempt_number, validation_failure_kind, llm_response, created_at)` — drives prompt tuning
- `coach_visible_override_events` — `(pitcher_id, program_id, event_kind, event_date, details)` — surfaces intentional player overrides to coaches

### Schema extensions on existing tables

- `daily_entries.plan_generated.source` — gains value `program_prescribed`
- `daily_entries.plan_generated.program_prescription_snapshot` — new jsonb field, the prescribed plan before triage modification (powers Why-sheet + v2 mod-rule analysis)
- `team_assigned_blocks` — gains nullable `fanned_out_program_ids` text[] linking to per-pitcher programs

### Migrations

All schema changes are additive. Nullable columns with sane defaults. Existing data unchanged. `saved_plans` is not migrated — it remains as historical data accessible via Profile.

## Section 2 — The Builder Funnel

Four layers. Layers 1, 2, 4 are UI; Layer 3 is backend reasoning.

### Layer 1 — Structured Inputs (form, no LLM)

Fields:
- **Domain** — Throwing | Lifting (drives everything below)
- **Goal** — chips, filtered by `domain` + `effective_phase`
- **Duration** — chips: 4 / 6 / 8 / 12 weeks (constrained by template `duration_range_weeks`)
- **Start date** — defaults next Monday
- **Hard constraints** — multi-select: Active injury (pre-checked from `injury_history.status='active'`), Equipment limited, Travel weeks expected, No bullpen access

Endpoint: `POST /api/programs/builder/candidates` returns 1–3 templates with one-line explanations. Zero matches blocks the form with explanation. The form's job is to make the candidate set tractable for the Socratic interview.

### Layer 2 — Socratic Interview (chat, LLM-driven)

LLM context: constraint envelope + 1–3 candidate templates + pitcher profile + injury history + 14-day arm feel/energy + WHOOP trend if present + research docs (resolved via `research_resolver` with context=`program_builder`).

System prompt rules:
- 4–6 questions max
- Only ask about parameters that distinguish candidates or change tuning
- Never ask about info already in the profile
- Honor "I don't know — you decide" on every turn
- End with structured `READY_TO_GENERATE` containing `chosen_template_id` + `tuned_spec` (validated against template's `tunable_parameters_schema`)

Schema validation failure → engine re-prompts the LLM with the error. Two failures → fall back to default tuning + log to `program_generation_failures`.

Every turn persists to `program_builder_sessions.turns_jsonb`.

### Layer 3 — Generation (backend, no UI)

`generate_program(pitcher_id, template_id, tuned_spec, constraints) -> Program`:
1. Load template scaffold from `block_library`
2. Pull research docs via `research_resolver` (context=`program_generation`, budget capped)
3. Call `call_llm_reasoning` with scaffold + research + tuned spec + profile → day-by-day schedule
4. **Validate hard invariants:**
   - Every exercise referenced exists in live `exercises` table
   - No contraindicated exercise for active injuries
   - Intensity ramp monotonic where template requires
   - Total duration matches chosen weeks
   - Per-week volume within template caps
5. Validation fail → retry once with error explanation. Second fail → return default-tuned scaffold + log to `program_generation_failures` (same safety pattern as `plan_generator`'s python_fallback)
6. Persist to `programs` with `status='draft'`. Return program ID.

### Layer 4 — Review & Activate (UI)

Preview screen:
- Header: name, domain, weeks, start date, "why this template" one-liner
- Week-by-week timeline (collapsed by default)
- Citations strip (research docs, linkable)
- Buttons: **Activate** · **Save as draft** · **Tweak inputs and regenerate**

Activate = confirm-then-archive flow (D9). Save as draft = `status='draft'`. Tweak = re-open Layer 1 with answers prefilled.

Regeneration cap: soft warning at 2, hard stop at 3.

## Section 3 — Daily Composition Pipeline

**This section's implementation gets its own session with strict, narrowly scoped parameters when we move to writing-plans.** Highest engineering risk.

### The new pipeline

```
build_daily_plan(pitcher_id, date, checkin_inputs):
    throwing_rx = get_active_program_day(pitcher_id, 'throwing', date)
    lifting_rx  = get_active_program_day(pitcher_id, 'lifting', date)
    prescribed = compose_prescribed_plan(throwing_rx, lifting_rx, profile)
    triage_result = run_triage(checkin_inputs, profile)
    final_plan, hold_events = apply_triage_to_program_plan(prescribed, triage_result)
    update_program_counters(pitcher_id, hold_events, date)  # atomic with daily_entries write
    enriched = llm_review_plan(final_plan, profile, triage_result)  # existing two-pass
    return enriched
```

### Triage interaction (approach B)

| Triage flag | Throwing | Lifting | Counter |
|---|---|---|---|
| Green | Program prescription verbatim | Program prescription verbatim | Both advance |
| Yellow | Flag-aware variant (existing exercise_pool YELLOW logic, applied to program's exercise set) | Drops one accessory per existing rules | Both advance |
| Red | Replaced with recovery-only protocol | Light/recovery block | Both **hold** (counter does not advance, `held_days_count++`, `nominal_end_date` recomputed) |
| Critical Red (≤2 arm feel) | Hard shutdown — no throwing | Light or rest only | Both **hold** + `auto_alert_coach` flag |

### Cold-start fallback

Pitcher with no active program in a domain → existing `plan_generator` runs for that domain. Pitcher with no programs at all → identical to today's behavior. Legacy path preserved verbatim, golden-snapshot tested.

### Scheduled-throw anchoring

Templates support two day-declaration modes:
- **Calendar-relative** — `Day 12 = lower-body lift block 2`, fixed offset from `start_date`
- **Anchor-relative** — `T-3 from next bullpen = high-effort plyo`, repositions around scheduled throws

When a player adds/moves/deletes a scheduled throw via existing `WeekArc.onAddThrow`:
1. `recompute_program_schedule(program_id)` fires
2. Past days (`day_index < current_day_index`) frozen — they happened
3. Future days re-anchor
4. `generated_schedule_json` rewritten in place; event logged to `program_schedule_revisions`
5. Home re-renders

Conflict resolution: scheduling a throw on a program-prohibited day prompts *"Your No-Throw Recovery program prescribes no throwing through April 28. Schedule anyway?"* — player decides; if they proceed, the program day is overridden for that date and a `coach_visible_override_events` row records it.

### Critical engineering invariants

1. `compose_prescribed_plan` is pure — never calls the LLM
2. Triage runs against the prescribed plan, not raw inputs — same `triage.py` module, same scoring
3. Counter updates atomic with `daily_entries` write (single transaction touching `daily_entries` + `programs.current_day_index` + `program_hold_events`)
4. `daily_entries.plan_generated.program_prescription_snapshot` always written when a program prescribed today's plan
5. Program lookup failure → log + fall through to legacy `plan_generator` + flag program as `status='error'`. Programs failing 3 days in a row alert the coach (24h grace) before auto-archiving.

### What dies in `plan_generator.py`

- Build-from-rotation-day becomes the *fallback*, not the default
- Exercise selection still flows through `exercise_pool`, but called *with* a target exercise set from the program (program says "pick from this 8-exercise candidate set")
- Two-pass LLM review unchanged — it just reviews program-derived plans

## Section 4 — Mini-App UX

UI build phase should invoke `frontend-design:frontend-design` for the Programs tab redesign and Builder slide-over. Brand shell continues Spec 1/2/3 patterns (Masthead + Scoreboard + editorial sections).

### Home — minimal additive changes

1. **Program ribbon** above daily card when programs are active:
   - `Velocity 12wk · Day 22 of 84 · Held 2 days` (throwing slot)
   - `Off-Season Strength · Day 8 of 56` (lifting slot)
   - Tap → jumps to Programs tab program detail
   - Absent when no programs active (Home looks identical to today)
2. **Per-block Favorite button** (heart icon, top-right of each block header). One tap = snapshot frozen, brief toast. Tap again = un-favorite.
3. **Held affordance** — inline note when triage paused a program: *"Velocity 12wk Day 22 paused — recovery day instead. Day 22 resumes when cleared."*

No "build a program" CTA on Home — Home is for executing today.

### Programs tab — single scrolling editorial page

Replaces current `Programs.jsx`. Top-to-bottom:

1. Masthead — kicker "My Programs", title with first name, today's date
2. **Today** — compact summary of today's session, source-tagged ("From Velocity 12wk · Day 22" or "No active program · cadence-based")
3. **Active Programs** — up to two cards (one Throwing + one Lifting). Each: name, parent template, day X/Y, hold count, expected end date, scheduled-throw anchor list, "View" → program detail (read-only Layer 4 timeline). Inline "Replace" link opens builder with same domain pre-selected.
4. **Build a Program** — single primary maroon CTA, opens Layer 1 slide-over
5. **Drafts** — saved-but-not-activated programs. Card list with Activate button; tapping opens preview.
6. **Favorites** — block snapshots, filterable by type (All / Lifting / Arm Care / Throwing / Warmup). Each card has "Run again" → render-only mode.
7. **Program History** — completed/archived programs chronologically
8. **Browse Templates** — collapsed-by-default canonical templates, "Build from this" pre-fills Layer 1

### Builder slide-over

Three states inside one slide-over:
- **State A: Inputs form** (Layer 1) — Continue button shows live match count, refuses zero-match
- **State B: Socratic chat** (Layer 2) — bubble UI matching `Coach.jsx` style; "I don't know — you decide" tap target on every AI turn; top-of-slide-over progress indicator ("1 of ~5 questions")
- **State C: Preview** (Layer 4) — header summary + expandable timeline + research citations + Activate / Save as draft / Tweak

Slide-over closes on:
- Escape (mid-conversation = confirmation prompt)
- Backdrop tap (no confirmation; abandons; `program_builder_sessions.status='abandoned'`)
- Activate/Save success

### Confirm-then-archive on Activate

Modal-on-modal: *"Activate Return-to-Mound 8wk? This archives your active Velocity 12wk at Day 22/84. Your progress is preserved in History."* — Cancel · Activate.

### Empty states (editorial)

- No programs ever built: Lede block — *"Build your first program."* + paragraph explainer. Drafts/Favorites/History collapsed.
- No favorites: *"Heart any block on Home to save it here. Favorites are yours alone."*
- Builder zero matches: *"No template fits velocity + 4 weeks + active flexor injury. Try 8 weeks, or build a 'Return to Mound' program first."*

## Section 5 — Coach App UX

Continues Spec 1/2/3 brand pattern. Principle: *"the Coach app is the back-end view of what every player is doing with a polished UI."*

### Team Overview — additions

1. **HeroCard / CompactCard** gain a 2-row program strip:
   - `THROW · Velocity 12wk · Day 22/84 · held 2d`
   - `LIFT · Off-Season Strength · Day 8/56`
   - When no active program: `THROW · Cadence-based`
2. **Phase divergence pill** per domain. Highlighted when effective phase differs from team default. Tap → popover with precedence stack ("set by activating Return-to-Mound 8wk on Apr 24; team default is in_season_active") + **Override** button → inline editor for `coach_*_phase_override`. First time a coach sees a pill, one-time tooltip explains per-domain phase model.
3. **Scoreboard** — replace "Next Milestone" placeholder with **Programs Drifted** (count of active programs where `expected_end > nominal_end + 3 days`).

### PlayerSlideOver — new Programs tab

Fifth tab alongside Today / Week / History / Profile:
- Active Programs (read-only, Replace link opens Build-for-Pitcher)
- Drafts the player has saved (always visible to coach — D14)
- History (completed/archived)
- Phase override controls (audited)
- Hold-event log (every triage-driven hold with date, reason, flag)

PlayerSlideOver does **not** show Favorites (privacy).

### Team Programs page — rebuilt

Replaces current `TeamPrograms.jsx`:
1. Masthead — `actionSlot` holds **+ Build Program** primary CTA
2. Scoreboard — Active team programs / Pitchers on player-built programs / Drafts in review (always 0 v1) / Templates in library / Avg drift across active programs
3. **Active Team Programs** — existing card grid, kept
4. **Library** — canonical templates, browsable; "Build a team program from this" + "Edit template" (for coach-authored)
5. **Player-built programs roster strip** — horizontal row at bottom: "Players currently on programs they built themselves: Landon, Wade, Carter…" → tap opens PlayerSlideOver Programs tab

### Build Program entry-point selector

Modal sheet from + button:
- **Build a team program** — Socratic builder scoped to whole team (or roster multi-select). Constraint envelope = team training_phase + upcoming `team_games` + roster injury aggregate. Activation fans out N program rows.
- **Build for a specific pitcher** — pitcher picker → Socratic builder with that pitcher's profile. Output = single program in selected pitcher's slot.
- **Author a new template** — Socratic builder in `interview_mode='authoring'`. Asks template-shaped questions (target goal, duration range, compatible phases, tunable parameters). Output = `block_library` row, `status='draft'`, published by separate coach action.

All entry points reuse same slide-over states (Inputs → Socratic → Preview), with `interview_mode` driving prompt variants.

### Team fan-out operational details

Build-a-team-program: Layer 1 → AI recommends templates with reasoning → 4-question Socratic → preview → fan-out activate. Fan-out is serial with 250ms gap, progress indicator ("Generating Wade's program… 3 of 12"). All-or-nothing commit — any validation failure holds the assignment in draft for coach review. Per-coach daily fan-out cap (default 3, configurable).

### Phases page — small read-side update

Each phase in the timeline gains a **Templates available in this phase** column (read-only count, tap to expand).

### Insights page — program-aware additions

New insight types plug into existing `coach_insights` / `coach_suggestions`:
- "3 pitchers' velocity programs have drifted >5 days — consider archiving"
- "Wade Hartrick built himself an Off-Season Strength block but is currently flagged YELLOW — review his approach"
- "Team is 4 weeks into Velocity 12wk — average completion 78%, 2 pitchers at <50%"

### Explicit coach-app non-goals (v1)

- No coach-initiated program edits — only build new / replace / archive
- No bulk re-anchor (game reschedule = per-pitcher recompute via existing path)
- No template diffing or version history (programs freeze against generated schedule; `parent_template_id` is provenance only)
- No coach view of player Favorites (designed-out, not deferred)

## Section 6 — v1 Scope, Template Seed, Telemetry, Risks

### v1 in / out

**In:** new tables (`programs`, `favorited_blocks`, `program_builder_sessions`, `program_hold_events`, `program_schedule_revisions`, `program_generation_failures`, `coach_visible_override_events`); schema extensions on `block_library`, `pitcher_training_model`, `daily_entries`, `team_assigned_blocks`; player Builder Layers 1–4; coach builder with three entry points; daily composition pipeline rewrite with cold-start fallback; scheduled-throw anchoring; mini-app Programs tab redesign + Home additions; coach-app PlayerSlideOver Programs tab + Team Programs rebuild + phase divergence pill + program-aware Insights; per-domain phase precedence; 10 seeded templates.

**Out (deferred or designed-out):** governance/approval loop, triage approach C, coach manual counter override, hand-edit of generated weeks, template version history, bulk schedule re-anchor, coach view of Favorites.

### Template seed (10 templates ship in v1)

**Throwing (6):**
1. Return to Mound — 8 weeks · post-injury ramp · anchor-relative
2. Velocity 12wk — long-term velocity development · mixed
3. Long Toss 6wk — distance-progression · calendar
4. In-Season Maintenance — 4-week cycle, repeatable · anchor-relative around outings
5. No-Throw Recovery — 2 weeks · pure rest + arm care + mobility · calendar
6. Bullpen-Heavy 4wk — high-volume pen block · anchor-relative

**Lifting (4):**
7. Off-Season GPP — 6 weeks · foundation · calendar
8. Off-Season Strength — 8 weeks · hypertrophy → strength · calendar
9. In-Season Maintenance — 4-week cycle, repeatable · 2 lifts/week · calendar
10. Power / Pre-Comp — 4 weeks · explosive emphasis, taper · calendar

Each template ships with `compatible_phases`, `tunable_parameters_schema`, `research_doc_ids`. Authored by Landon + reviewed by a coach before launch. Builder is gated for a pitcher's domain only when a template exists for their phase.

### Telemetry instrumented from day one

- `program_builder_sessions` (full conversation, abandonment per layer, structured-input combos producing zero candidates)
- `program_hold_events` (foundation for v2 modification rules)
- `program_schedule_revisions` (recompute triggers)
- `program_generation_failures` (validation-failure kinds, drives prompt tuning)
- `coach_visible_override_events`

No dashboards in v1 — raw query access is sufficient.

### Risks and mitigations

| # | Risk | Mitigation |
|---|---|---|
| R1 | Daily composition pipeline rewrite is highest-risk change | Legacy `plan_generator` preserved verbatim as cold-start fallback; atomic transactions on counter updates; feature flag `PROGRAM_AWARE_PLAN_GEN` scoped initially to 1–2 pitchers; golden-snapshot tests on legacy path; **own implementation session with strict, narrow parameters** |
| R2 | Template content quality is launch blocker | All 10 templates ship only after coach review; written rationale doc per template in `data/knowledge/research/`; Builder gated until template exists for pitcher's phase |
| R3 | LLM cost on team fan-out | Serial with 250ms gap; per-coach daily fan-out cap (default 3); aggressive Layer 1 envelope caching |
| R4 | Phase divergence pill proliferation | Pill shown only when phase differs from team default; first-time tooltip explains per-domain model |
| R5 | Existing data migration | Additive-only schema; new columns nullable with defaults; existing `team_assigned_blocks` rows continue working without retroactive fan-out |
| R6 | Builder slide-over routing conflicts in Telegram WebApp | Reuse `Coach.jsx` BackButton + swipe pattern |
| R7 | Auto-archive on 3-day validation failure could trigger from template authoring bug | Coach alert ("Program X failing validation, will archive in 24h unless reviewed") instead of silent archive |

### Acceptance criteria for launch

1. A pitcher can build → activate → run → complete a program end-to-end
2. A coach can build a team program that fans out across the staff successfully
3. A coach can build a program for a specific pitcher
4. A coach can author a new template
5. Legacy `plan_generator` produces byte-identical output for pitchers with no active programs (golden snapshot)
6. Triage holds correctly pause counters across Yellow / Red / Critical Red
7. Phase precedence resolves correctly for all four input combinations
8. Scheduled-throw add/move/delete recomputes program schedules correctly
9. Builder slide-over works from both player Programs tab and coach Team Programs page
10. Per-block Favorites store immutable snapshots that re-run in render-only mode

### Implementation sequencing

1. Schema + cold-start safety (new tables, extensions, golden tests for legacy `plan_generator`)
2. Builder funnel Layers 1, 3, 4 (deterministic + generation; mock template-picker for Layer 2)
3. Layer 2 — Socratic interview (LLM + prompt tuning)
4. **Daily composition rewrite** ← own session, strict params, feature-flagged rollout
5. Scheduled-throw anchoring + recompute
6. Mini-app Programs tab + Home additions
7. Coach app — PlayerSlideOver Programs tab + Team Programs rebuild + phase divergence pill
8. Coach app — three builder entry points + team fan-out
9. Telemetry + Insights additions
10. Template seed authoring (parallel; needs coach review pass before launch)

The riskiest piece (#4) lands with surrounding infrastructure shipped and the legacy path proven still working.

## Open items for the implementation plan

- Confirm feature-flag mechanism (env var? per-pitcher flag column? `pitcher_training_model.feature_flags` jsonb?)
- Confirm where Layer 2 prompt variants live (`bot/prompts/program_builder_*.md`?)
- Confirm `frontend-design` skill is the right tool for the Programs tab redesign + Builder slide-over (vs. continuing in plain React with the existing tokens)
- Confirm the 10-template seed list with a coach before the writing-plans session
