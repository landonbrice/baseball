# Pitcher Training Intelligence — Claude Init

> Last updated: 2026-04-13
> Sprint status: Phases 1-19 complete. Coach Dashboard v0 built + pushed (not yet fully deployed). Next: finish coach dashboard deployment, The Ledger, periodization, exercise progression curves, inline coach panel.

## What This Is

A training intelligence system for the UChicago baseball pitching staff. Telegram bot + FastAPI API + React Mini App. Each pitcher gets personalized daily programs (lifting, arm care, recovery, throwing), evidence-based Q&A, and longitudinal tracking — driven by their individual profile, injury history, and conversation context.

**Three layers:**
- **Bot (Telegram)** — Conversational input layer. Morning check-ins, post-outing reports, free-text Q&A. The coaching relationship.
- **Mini App (React)** — Value/visibility layer. Programs, completion tracking, trajectory over time. Where compounding becomes tangible.
- **Intelligence Engine (Python/FastAPI)** — Triage, plan generation, knowledge retrieval, progression analysis. The thinking that connects input to output.

**The system is deployed and functional.** Morning notifications, WHOOP biometrics, dynamic exercise selection, personalized onboarding, dynamic warmup, and tiered post-throw recovery are all live. Onboarding push April 1.

## Completed Phases

> Phases 1-5: Supabase migration, state awareness, coaching conversation quality, visible compounding, polish. All complete as of 2026-03-28.

### Phase 6: WHOOP Integration (2026-03-29) — COMPLETE
Full biometric pipeline. See WHOOP Integration section below.

### Phase 7: Adoption Push (2026-03-30) — COMPLETE
- `/start` reworked: personalized intro referencing injury history + rotation day, auto-launches check-in
- Morning notification: contextual (references yesterday's arm feel, post-outing status, WHOOP recovery as conversational sentence)
- Morning arm feel buttons enter full ConversationHandler check-in flow (not orphaned)
- Evening follow-up: human, normalizes skipping
- `post_init` fix: scheduler now fires on Railway (was silently not running)

### Phase 8: Dynamic Exercise Pool (2026-03-31) — COMPLETE
- `exercise_pool.py`: selects 7-8 exercises from the 155-exercise Supabase library per session
- Filters by day focus, rotation_day_usage, injury contraindications, modification_flags
- Prefers exercises not used in last 7 days (variety across weeks)
- Applies prescription from the exercise's phase data (strength/power/hypertrophy/endurance)
- LLM receives pre-selected exercises — adjusts prescriptions and writes narrative, cannot hallucinate IDs
- Arm care and throwing remain template-based (curated protocols)
- **Explosive block**: Every non-recovery/non-light lift includes 1 plyometric_power exercise (med ball, plyo pushups, jumps) as the first block

### Phase 9: Exercise Enrichment + Mobility Videos (2026-03-31) — COMPLETE
- Exercise library expanded from 120 → 155 exercises via `scripts/enrich_exercises.py`
- 6 YouTube URL backfills on existing exercises, 35 new exercises added (ex_121–ex_155)
- New exercises: arm isolation (curls, skull crushers, pushdowns) as `upper_body_push`/`upper_body_pull`, med ball variations (10 new) as `plyometric_power`, core exercises (copenhagen plank, hanging leg raises, rope crunch), lower body accessories
- **Mobility video system**: 21 follow-along YouTube videos in a 10-week cycling rotation (3 P/R + 1 targeted per week)
- `mobility_videos` + `mobility_weekly_rotation` Supabase tables
- `bot/services/mobility.py`: `get_today_mobility()` cycles by ISO week number mod 10
- `GET /api/pitcher/{id}/mobility-today` endpoint
- `MobilityCard` component on daily plan page — renders after all exercise blocks with clickable YouTube video links
- Plan generator includes `mobility` key in output; DailyCard falls back to API fetch for pre-existing plans

### Phase 10: Day Phases — Dynamic Warmup + Post-Throw Recovery (2026-03-31) — COMPLETE
- **Dynamic warmup block** injected as first block in every daily plan from `dynamic_warmup.json`
- `_build_warmup_block()`: picks cuff activation (days 0,1,2,5,6) vs scap activation (days 3,4), auto-includes FPM addon for UCL/forearm history pitchers
- **Tiered post-throw recovery** from `post_throw_protocols.json` replaces static 2-exercise post-throw:
  - Light (5 exercises, 6 min): recovery, recovery_short_box days
  - Medium (11 exercises, 10 min): hybrid_b days
  - Full (15 exercises, 15 min): hybrid_a, bullpen, game days
- 4 new mobility exercises added (ex_156-ex_159): Sleeper Stretch, Cross-Body Posterior Shoulder, Thoracic Rotation, Standing Lat Stretch
- Exercise library now 159 exercises (ex_001-ex_159), all synced to Supabase
- `warmup` JSONB column on `daily_entries`, passed through checkin_service + routes
- DailyCard renders warmup as first block, collapsed by default with expand toggle, exercises grouped by block name
- Post-throw recovery phases have green-tinted background in ThrowingBlock
- LLM prompt references warmup existence but does not generate it

### Phase 11: Onboarding UX — First Experience Overhaul (2026-03-31) — COMPLETE
- **Home welcome card** for new pitchers: arsenal pills, training snapshot grid (maxes, experience, split), injury-aware banner, CTA button, value prop card
- **Coach personalized welcome**: dynamic message referencing role, rotation, arsenal, pitch count, injury history, goals
- All sections degrade gracefully for sparse profiles
- Pre-onboarding bug fixes: 25 missing exercises migrated, 38 slug-to-ID mappings, RetryPlan signature fix, chat history race condition, days_since_outing cap

### Phase 12: Pitcher Training Model (2026-04-01) — COMPLETE
- `pitcher_training_model` table consolidates `active_flags` + exercise intelligence + weekly arc
- Compatibility layer: `profile["active_flags"]` still works, reads from new table
- `active_flags` table dropped; `weekly_summaries` enriched with structured columns
- `load_training_model()` helper for full model access (preferences, equipment, week state)

### Phase 13: Exercise Swap UI (2026-04-02) — COMPLETE
- Approach D inline swap: reason pills (No equipment / Doesn't feel right / Just swap it)
- `exercise_alternatives.py`: finds 3-4 alternatives by category + muscle overlap
- Model-aware exercise pool: filters by equipment_constraints, scores by exercise_preferences
- Swap history → auto-dislike after 3+ swaps from same exercise
- `ExerciseSwap` component renders in DailyCard lifting block only

### Phase 14: Two-Pass Plan Generation (2026-04-02) — COMPLETE
- Python constructs complete plan instantly (<1s) — no more LLM timeout failures
- LLM reviews plan for coherence, adjusts prescriptions, writes morning brief
- If LLM times out, pitcher gets model-aware plan (not generic template)
- `weekly_model.py`: next-day suggestions, weekly state tracking after each check-in
- Morning notifications lead with proactive suggestion when confidence is high

### Phase 15: Coach Bridge + Game Detection (2026-04-02) — COMPLETE
- Coach chat detects `plan_mutation` JSON → returns mutation preview cards
- `MutationPreview` component: diff cards with Apply/Keep buttons
- `POST /apply-mutations` handles swap/add/remove/modify operations
- `game_scraper.py`: detects game days, prompts unreported relievers at 11pm
- Coach mutations feed back into pitcher model preferences (auto-dislike learning)

### Phase 16: Plan Source Tagging + Error-Path Hardening (2026-04-09) — COMPLETE
- **Yellow-flag trim fix** — `exercise_pool.py:172` was collapsing ANY yellow or red flag to the "light" session structure (1 compound + 2 accessories + 1 core = 4 exercises). Roughly half the roster has chronic managed conditions keeping them persistently yellow, so they were getting 4-exercise plans daily. Fix: red still collapses to light, yellow now trims -1 accessory from the normal day_focus structure (7 exercises instead of 4). Red behavior unchanged.
- **Plan source tagging** — `plan_generator.py` now tags every plan with `source` (`"python_fallback"` | `"llm_enriched"`) and `source_reason` (`llm_timeout:X`, `llm_unparseable_json`, `llm_assembly_error:X`). Threaded through `checkin_service.py` into `daily_entries.plan_generated.source`/`source_reason` JSONB, and into the return dict.
- **`plan_degraded` status** — `/chat` checkin response gate previously keyed off emptiness (`not narrative AND not brief AND not blocks`), which almost never fired because `python_plan` always populated those. New gate: `source is None` → `plan_failed`, `source == "python_fallback"` → `plan_degraded`, otherwise `plan_loaded`. `Coach.jsx` handles `plan_degraded` with a warning toast and `planDegraded` derived state (from `todayEntry.plan_generated.source`) so the retry pill survives reload with label "Retry for coach brief".
- **Custom plan endpoint fix** — `/api/pitcher/{id}/generate-plan` was near-deterministically 500ing. Root causes: (a) strict `_parse_plan_json` requires a top-level `morning_brief` that the custom-plan prompt never asked for, (b) 2 unsubstituted prompt placeholders leaking as literal `{var}` strings. Fix: substitute all placeholders, append explicit JSON schema instruction to prompt, add local `_relaxed_parse_custom_plan` that injects a default `morning_brief` when missing (shared `_parse_plan_json` left untouched — load-bearing for the check-in path). Specific HTTP codes: 504 on timeout, 502 on upstream errors, 502 with actionable detail on unparseable.
- **`postApi` error detail surfacing** — `mini-app/src/api.js` `postApi` now attaches `.status` and `.detail` to thrown Errors by parsing the FastAPI `detail` field out of error response bodies. Additive/backward-compatible (`.message` format unchanged). Callers like `PlanBuilder.jsx` and `ExerciseSwap.jsx` use `err?.detail` to show real backend reasons instead of generic toasts.

### Phase 17: Silent Degradation Monitoring (2026-04-09) — COMPLETE
Closes the observability gap that let a DeepSeek 402 "Insufficient Balance" outage go unnoticed for a full day.
- **`bot/services/health_monitor.py`** — new stateless service module. Queries `daily_entries.plan_generated.source`, WHOOP pull completeness, Sunday weekly narrative presence, and in-memory Q&A counters. Composes a daily digest dict.
- **Daily digest** — scheduled 9am Chicago via APScheduler. Telegram-DMs the admin (`ADMIN_TELEGRAM_CHAT_ID`, defaults to Landon's 8589499360). Shows plan source breakdown (enriched vs fallback), source_reason counts, degraded pitcher IDs, WHOOP pull count, weekly narrative status, Q&A error rate.
- **Real-time emergency alerts** — `record_and_check_emergency` tracks failure patterns in-memory. Fires when 3+ matching `source_reason` values (APIStatusError, AuthenticationError, InsufficientBalance, RateLimitError, etc.) hit within a 30-min window. 2-hour per-pattern dedup prevents spam. Hooked into `plan_generator.py` at all 3 `source_reason` assignment sites via `_emergency_alert` key on `python_plan` dict; `checkin_service._send_emergency_alert_if_present()` pops and Telegrams the alert, strips the key before persistence.
- **Q&A tracking** — in-memory success/error counters with midnight-Chicago reset. Hooked into both `routes.py /chat` Q&A branch and `bot/handlers/qa.py handle_question`. Included in digest under the Q&A section.
- **Admin commands** — `/healthdigest` (force digest now), `/healthcheck` (on-demand digest), `/testemergency` (simulate 3 failures to verify the alert path). All gated on `effective_chat.id == ADMIN_TELEGRAM_CHAT_ID`.
- **Admin endpoint** — `GET /api/admin/health` returns the raw digest JSON. Admin-authenticated via initData resolving to `ADMIN_TELEGRAM_CHAT_ID`. Future-proof for dashboards.
- **All monitoring wrapped in try/except with `pass`** — monitoring must never regress the user path.

### Phase 18: Guided Day Flow (2026-04-09) — COMPLETE
Every daily phase (warmup → arm care → lifting → throwing → mobility) now guides the pitcher through in order without dimming future content or hiding anything on first open.
- **Phase computation** — `computePhaseOrder(entry, mobility)` in `DailyCard.jsx` builds a 5-phase sequence per-render. Respects `arm_care.timing` (`pre_throw` vs `pre_lift`) and the presence of throwing. Skips phases with no items. Post-throw recovery is NOT a separate phase — it's nested inside throwing.
- **Phase completion** — `isPhaseComplete(phaseId, entry, completed, manuallyDone)`: mobility is always "complete" (terminal/optional), empty phases are complete, phases in `manuallyDonePhases` Set are complete, otherwise all items must be in `completed_exercises`.
- **Active phase accent** — 3px maroon `box-shadow: inset` stripe on the block's left edge (respects the block's `borderRadius: 12`), subtle `rgba(92,16,32,0.018)` bg tint (felt more than seen), and a floating "NOW" pill absolutely positioned at `top: -6px, right: 14px` with a maroon gradient (matches the Profile identity header treatment). Pill fades in with `transition: opacity 0.2s`.
- **No dimming** — locked phases render at full opacity and remain fully tappable. The guide is additive (active accent + completion collapse), not subtractive. Preserves full-plan readability on first open.
- **Completion collapse** — when all items in a phase are checked OR the pitcher taps "Mark done", the block collapses to a one-line `CompletedPhaseSummary` row: [green check badge] phase name [tabular-nums count pill `6/6`] [chevron]. Tap anywhere to re-expand.
- **"Done with [phase] →" button** — maroon gradient button (same `165deg #5c1020 → #7a1a2e` as identity header), sentence-case label, tactile hover (`translateY(-1px)` + shadow lift) and tap (`scale(0.98)`) micro-interactions. Renders only on the active phase, never on mobility. Tapping adds the phase to `manuallyDonePhases` Set, which advances `activePhaseId` via `useMemo` re-derivation.
- **Re-collapse affordance** — when a completed phase is re-expanded, a subtle outline-maroon `CollapsePhaseButton` appears at the bottom: "Collapse [phase] ↑". Taps `handleToggleCompletedPhaseExpand(key)`.
- **Ephemeral state** — `manuallyDonePhases` and `expandedCompletedPhases` Sets are component-local. Lost on reload; re-derives from `completed_exercises` via the first-incomplete-phase rule. Persistence is deliberately deferred to v2.
- **Guided flow bypassed when `readOnly=true`** (e.g. past-day log views). Past entries render in the pre-guided-flow shape.
- **`wrapperStyle` prop** added to `ExerciseBlock` and `ThrowingBlock` — merges into their outer divs for the stripe + tint. Backward-compatible (undefined in readOnly / non-guided paths).

### Phase 18a: Swap endpoint dual-write fix (2026-04-09) — COMPLETE
Pre-existing bug surfaced during guided-flow testing: `swap_exercise` and `apply_mutations` were reading from `entry.plan_generated.lifting.exercises` (nested JSONB) but `checkin_service` writes the plan to `entry.lifting.exercises` (top-level column). The swap endpoint returned 404 on every modern plan; the only reason it appeared to work before was that `ExerciseSwap` uses frontend-only `swapOverrides` state that masks backend failures visually. Fix: both endpoints now search top-level `entry.lifting.exercises` first, fall back to nested legacy locations, and write back BOTH locations for consistency. One-off `UPDATE` cleaned a ghost `plan_generated.lifting` from landon_brice's 2026-04-09 entry.

### Phase 19: Research-Aware Coaching Layer (2026-04-10) — COMPLETE
Wires the knowledge base into four surfaces through a unified resolver with deterministic safety guarantees.
- **`bot/services/vocabulary.py`** — Canonical `INJURY_AREAS` (8 areas) and `MODIFICATION_TAGS` (14 tags). Single source of truth for injury keywords, research triggers, and modification descriptions. Triage now emits tag keys (e.g. `"fpm_volume"`) instead of freeform strings; `get_mod_description(tag)` converts back to human-readable for display.
- **`bot/services/research_resolver.py`** — Unified resolver replacing split routing in `knowledge_retrieval.py`. Parses YAML frontmatter (`id`, `applies_to`, `triggers`, `priority`, `contexts`, `summary`) from all 14 research docs. Four-step selection: (1) critical docs matching `applies_to` ∩ pitcher's injury areas, (2) trigger-intersection from triage modifications, (3) user message keyword match (coach_chat only), (4) standard docs filling remaining char budget. Returns `ResearchPayload(combined_text, loaded_docs, trigger_reason)`. Module-level `_index_cache` with `clear_cache()`.
- **`should_fire_research(profile, triage, user_message)`** — Three OR'd conditions: non-green flag, active modifications, injury keyword in message. Gates all four surfaces.
- **Research doc frontmatter** — All 14 docs in `data/knowledge/research/` migrated to new schema. Old `keywords` + `type` kept for backward compat; new fields: `id`, `title`, `applies_to`, `triggers`, `phase`, `priority` (critical/standard/reference), `contexts` (plan_gen/coach_chat/morning/daily_plan_why), `summary`.
- **Coach chat structured output** — `bot/prompts/coach_chat_prompt.md` instructs LLM to return JSON `{reply, mutation_card, lookahead}`. `mutation_card` has `type` (swap/rest/hold/addition), `title`, `rationale` (must cite loaded research), `actions[]`, `applies_to_date`. Parsed by `_parse_coach_response()` in `qa.py`; fallback via `_extract_reply_fallback()`. API `/chat` returns mutation cards as `type: "plan_mutation"` messages for the mini-app MutationPreview component.
- **Morning notification two-pass** — Pass 1 builds deterministic draft (unchanged). Pass 2: if `should_fire_research()`, loads `morning_message.md` prompt, calls `call_llm()` with 15s timeout to rewrite draft with research context woven in. Falls back to draft on failure.
- **Daily plan "why" affordance** — `ResearchWhySheet` component in `DailyCard.jsx`. "ⓘ why" button on lifting block header (visible when `research_sources.length > 0` and `!readOnly`). Bottom sheet fetches `GET /api/research/docs?ids=...` and displays doc titles + summaries.
- **`research_sources` persistence** — `plan_generator.py` adds `research_sources: [doc.id, ...]` to both `python_plan` and LLM success path. Stored in `daily_entries.research_sources` (text[] column). `research_load_log` table tracks every resolver call (pitcher, context, trigger_reason, doc_ids, total_chars, degraded).
- **Coverage tests** — `test_research_coverage.py`: every mod tag's triggers exist in some doc's frontmatter, every injury area has a critical doc, no orphan docs. `test_vocabulary.py` (5), `test_research_resolver.py` (8), `test_coach_chat.py` (5) = 21 total tests.
- **Dead file audit** — `data/knowledge/FINAL_research_base.md` (top-level) moved to `_archive/` (superseded by research/ copy). `extended_knowledge.md` left in place (empty stub). Repo-root `research/` left as strategic reference (not runtime).

### Phase 20: Coach Dashboard v0 (2026-04-12) — CODE COMPLETE, DEPLOYMENT IN PROGRESS
Full coach-facing web dashboard. Monorepo sibling app (`coach-app/`) with Supabase Auth.

**Backend (pushed to main, deployed on Railway):**
- Migration 006: 7 new tables (`teams`, `coaches`, `team_games`, `block_library`, `team_assigned_blocks`, `coach_suggestions`, `training_phase_blocks`) + `team_id` column on 5 existing tables
- `api/coach_auth.py` — Supabase JWT validation middleware, `require_coach_auth` dependency
- `api/coach_routes.py` — 30 endpoints under `/api/coach/*` (auth, team overview, player detail, overrides, schedule CRUD, team programs, phases CRUD, insights accept/dismiss, block compliance)
- `bot/services/team_scope.py` — Team-scoped query helpers (roster overview, compliance, game queries)
- `bot/services/team_programs.py` — Resolves active team blocks for plan gen, `days_until_next_start`
- `bot/services/coach_insights.py` — Pre-start nudge generation (heuristic: >12 sets within 2 days of start)
- Engine hooks: `plan_generator.py` (team block → throwing override, start date → rotation override), `exercise_pool.py` (phase emphasis → training_intent)
- `_apply_mutations_to_entry()` extracted from `routes.py` for reuse by coach routes
- 3 seed scripts: `seed_schedule.py`, `seed_block_library.py`, `seed_demo_coach.py`
- Mini-app: `team_block_tag` rendered in DailyCard throwing section

**Frontend (pushed to main, Vercel project created):**
- `coach-app/` — React 18 + Vite + Tailwind CSS, Supabase Auth (email/password)
- Auth: `useCoachAuth` hook (Supabase session → JWT exchange with backend), `api.js` (fetch/post/patch/delete with Bearer token)
- Shell: sidebar nav, protected routes, `ToastProvider`
- 6 screens: Login, TeamOverview, Schedule, TeamPrograms, Phases, Insights
- 13 components: ComplianceRing, RosterTable, PlayerSlideOver, PlayerToday/Week/History, AdjustTodayModal, AddRestrictionModal, GamePanel, BlockCard, PhaseTimeline, InsightCard, Toast

**Deployment status (as of 2026-04-12):**
- DB migration applied ✅, block library seeded ✅, phases seeded ✅, coach row created ✅
- Railway env vars set (`SUPABASE_JWT_SECRET`) ✅, coach routes live at `/api/coach/*` ✅
- Vercel project created at `baseball-copiblin-landonbrices-projects.vercel.app`
- **BLOCKED: CORS error on login.** The `COACH_APP_URL` env var in Railway must be set to exactly `https://baseball-copiblin-landonbrices-projects.vercel.app` (no trailing slash). Once set, Railway needs a redeploy so `api/main.py` picks up the new origin in `ALLOWED_ORIGINS`. This is the only remaining blocker — auth exchange POST to `/api/coach/auth/exchange` is rejected by CORS preflight.
- `VITE_SUPABASE_ANON_KEY` confirmed set in Vercel env vars
- Auth user: `landonbrice2005@gmail.com` in Supabase Auth, linked to coaches row via `supabase_user_id`

**Design spec:** `docs/superpowers/specs/2026-04-09-coach-dashboard-v0-design.md`
**Implementation plan:** `docs/superpowers/plans/2026-04-10-coach-dashboard-v0.md`

### What's Not Yet Built
1. **The Ledger** — Modification history visualization. Data exists in `plan_generated.modifications_applied` and `pitcher_training_model.recent_swap_history`. Needs frontend timeline on Profile.
2. **Periodization** — No multi-week phases (hypertrophy → strength → power → deload). Template repeats identically each week. Exercise pool adds variety but not progressive block structure. Biggest remaining architectural item in the PROJECT_VISION.
3. **Exercise progression curves** — Volume/intensity trends for key lifts over time. Blocked on weight logging (#7).
4. **Truncated JSON repair** — `_repair_truncated_json` exists in `plan_generator.py:439` and runs when `finish_reason == "length"`, but doesn't handle non-length cutoffs (network drops mid-stream). Minor — two-pass plan gen ships Python fallback on any failure.
5. **Weight logging** — `pitcher_training_model.working_weights` column exists but no UI to log actual weights lifted. Currently completion is binary (done/not done). Unblocks #3.
6. **Inline coach panel on lifting block** — Coach button on lifting section for in-context refinement without navigating to Coach tab. Coach tab works for now.
7. **UChicago box score scraping** — `game_scraper.py` detects game days and prompts relievers, but doesn't auto-scrape box scores.
8. **Guided flow v2 persistence** — `manuallyDonePhases` is ephemeral (resets on reload). v2 would persist a `phase_progress` JSONB column on `daily_entries` so "mark done" survives reloads. Low priority — most pitchers don't reopen mid-session.
9. **Guided flow progress dots** — v2 polish. Horizontal row of phase dots at the top of DailyCard showing sequence (●○○○○). Click a dot to scroll to that phase.

## Stack

| Layer | Tech | Where |
|-------|------|-------|
| Bot | Python 3.11 / python-telegram-bot v20+ / APScheduler | Railway (long-polling) |
| API | FastAPI / Uvicorn | Railway (same service, Procfile) |
| LLM | DeepSeek (OpenAI-compatible wrapper) | DeepSeek API |
| Mini App | React 18 / Vite / Tailwind CSS | Vercel |
| Data | Supabase (Postgres) | Supabase |

**Deployment URLs:**
- API: `https://baseball-production-9d28.up.railway.app`
- Mini App: Vercel (configured in `mini-app/.env.production`)
- Bot: `@uchi_pitcher_bot` on Telegram

## Repo Structure

```
pitcher_program_app/
├── bot/                          # Telegram bot (long-polling)
│   ├── main.py                   # Entry point, all handlers, scheduled jobs
│   ├── config.py                 # Env vars, paths, CONTEXT_WINDOW_CHARS=12000
│   ├── run.py                    # Railway entry (Procfile: python -m bot.run)
│   ├── utils.py                  # Shared keyboard builders
│   ├── handlers/
│   │   ├── daily_checkin.py      # /checkin ConversationHandler (5 states, reliever branching)
│   │   ├── post_outing.py        # /outing ConversationHandler (pitch count → arm feel → tightness → UCL → notes)
│   │   └── qa.py                 # Free-text Q&A with dual LLM routing (fast vs reasoning)
│   ├── services/
│   │   ├── db.py                 # Supabase client, all CRUD operations
│   │   ├── context_manager.py    # Profile/log/context CRUD — Supabase-backed with JSON fallback
│   │   ├── checkin_service.py    # Check-in → triage → plan generation pipeline
│   │   ├── outing_service.py     # Outing → recovery protocol pipeline
│   │   ├── triage.py             # Rule-based readiness triage (green/yellow/red), injury-aware
│   │   ├── triage_llm.py         # LLM refinement for ambiguous triage cases
│   │   ├── exercise_pool.py      # Dynamic exercise selection from library (replaces static templates), explosive block
│   │   ├── exercise_alternatives.py # Smart alternative-finding for inline exercise swaps
│   │   ├── weekly_model.py       # Next-day suggestion logic, weekly state management
│   │   ├── game_scraper.py       # Game day detection, reliever appearance tracking
│   │   ├── mobility.py           # 10-week cycling mobility video rotation service
│   │   ├── plan_generator.py     # Two-pass plan gen: Python constructs instant plan, LLM reviews/enriches. Team block + days_until_start hooks.
│   │   ├── team_scope.py         # Team-scoped query helpers for coach dashboard (roster overview, compliance, game queries)
│   │   ├── team_programs.py      # Resolves active team blocks for plan gen, days_until_next_start computation
│   │   ├── coach_insights.py     # Pre-start nudge generation for coach suggestions
│   │   ├── progression.py        # Arm feel trends, sleep patterns, recovery curves, weekly summaries, season summary
│   │   ├── llm.py                # DeepSeek wrapper (call_llm + call_llm_reasoning, defaults 90s/120s, plan review uses 20s)
│   │   ├── knowledge_retrieval.py # Exercise library search + auto-research generation (thin wrappers around resolver)
│   │   ├── research_resolver.py  # Unified research resolver — frontmatter-driven doc routing for all surfaces
│   │   ├── vocabulary.py         # Canonical injury areas + modification tags (single source of truth)
│   │   └── web_research.py       # Tavily API fallback for Q&A
│   └── prompts/                  # LLM prompt templates (.md): system, qa, plan_generation, triage, recovery, coach_chat, morning_message
│
├── api/                          # FastAPI sidecar for mini-app + coach dashboard
│   ├── main.py                   # App, CORS (mini-app + coach-app origins), health check
│   ├── auth.py                   # Telegram initData HMAC validation
│   ├── coach_auth.py             # Supabase JWT validation, require_coach_auth decorator
│   ├── coach_routes.py           # 30 /api/coach/* endpoints (auth, overview, detail, overrides, schedule, programs, phases, insights)
│   └── routes.py                 # 25+ endpoints: auth, checkin, outing, chat, plans, exercises, progression
│
├── data/
│   ├── pitchers/                 # Per-pitcher dirs: profile.json, context.md, daily_log.json (12 active)
│   ├── templates/                # 9 training templates (starter_7day, reliever_flexible, arm_care, plyocare, recovery, etc.)
│   ├── knowledge/                # exercise_library.json (155 exercises), mobility_videos.json (21 videos, 10-week rotation), research docs
│   └── intake_responses.json     # Raw Google Form responses
│
├── mini-app/                     # React Telegram Mini App
│   ├── src/
│   │   ├── App.jsx / Layout.jsx  # Router, auth context, TelegramWebApp init, morning badge check
│   │   ├── hooks/                # useApi, usePitcher, useTelegram, useChatState
│   │   ├── components/           # DailyCard, WeekStrip, TrendChart, SessionProgress, Sparkline, StreakBadge, StaffPulse, CoachFAB, TrendInsightChart, ExerciseWhy, MobilityCard, etc. (20 total)
│   │   ├── ExerciseSwap.jsx      # Inline swap UI (Approach D: reason pills + alternatives)
│   │   ├── MutationPreview.jsx   # Coach mutation diff card with Apply/Keep buttons
│   │   └── pages/                # Home, Coach, Plans, PlanDetail, ExerciseLibrary, LogHistory, Profile (7 total)
│   └── .env.production           # VITE_API_URL
│
├── coach-app/                    # React Coach Dashboard (Vercel)
│   ├── src/
│   │   ├── App.jsx               # Router, AuthProvider, ToastProvider
│   │   ├── api.js                # fetchCoachApi, postCoachApi, patchCoachApi, deleteCoachApi
│   │   ├── hooks/                # useCoachAuth (Supabase Auth + JWT exchange), useApi
│   │   ├── components/           # Shell, ComplianceRing, RosterTable, PlayerSlideOver, PlayerToday/Week/History, AdjustTodayModal, AddRestrictionModal, GamePanel, BlockCard, PhaseTimeline, InsightCard, Toast (13 total)
│   │   └── pages/                # Login, TeamOverview, Schedule, TeamPrograms, Phases, Insights (6 total)
│   ├── .env.production           # VITE_API_URL, VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY
│   └── vercel.json               # SPA rewrites
│
├── scripts/                      # intake_to_profile.py, seed scripts, data_sync.py, backup_data.sh
├── research/                     # Reference material (NOT loaded at runtime)
├── bot_structure/                # Design docs (reference)
├── files/                        # Architecture + pipeline docs
├── past_arm_programs/            # Historical spreadsheets (reference)
│
├── PROJECT_VISION.md             # CURRENT: Vision, architecture decisions, sprint plan
├── MASTER_PROJECT.md             # LEGACY: Original specification (superseded by PROJECT_VISION.md)
├── Procfile                      # Railway: web: python -m bot.run
├── railway.toml                  # Build config (nixpacks)
└── requirements.txt              # Python deps
```

## Key Patterns

### Pitcher Lookup
`get_pitcher_id_by_telegram(telegram_id, username)` — matches by telegram_id first, falls back to telegram_username with auto-backfill on first message.

### Context System
Supabase-only. `context_manager.py` queries recent `chat_messages` + `daily_entries` + `pitcher_training_model` from Supabase to build LLM context. The `pitcher_training_model` table consolidates what was previously `active_flags` plus exercise intelligence (preferences, equipment constraints, swap history) and weekly training arc state. JSON fallback was removed 2026-04-01 — no filesystem dependencies remain.

### Triage → Plan Pipeline
1. Rule-based triage (`triage.py`) → green/yellow/red + modifications (includes WHOOP HRV/recovery/sleep thresholds)
2. Ambiguous cases → LLM refinement (`triage_llm.py`)
3. **Partial entry saved to Supabase BEFORE plan generation** (check-in data persists even if LLM fails)
4. **Dynamic warmup** (`_build_warmup_block`) loads `dynamic_warmup.json`, picks activation option + FPM addon
5. **Dynamic exercise pool** (`exercise_pool.py`) selects 7-8 lifting exercises + 1 explosive from the 159-exercise library
6. **Tiered post-throw** (`_select_post_throw_protocol`) selects light/medium/full recovery based on throwing day type
7. **Python constructs complete plan** (instant) from exercise pool + pitcher model + triage — always succeeds
8. **LLM reviews plan** (async) — adjusts prescriptions, writes morning brief + notes. If LLM times out, Python plan ships as-is
9. Fallback to Python-constructed plan if LLM fails (model-aware exercises, not generic template)
10. Full entry upserted (same date = updates partial), results persist to pitcher_training_model
11. `days_since_outing` incremented AFTER first successful check-in of the day (re-check-ins don't double-increment), capped at `rotation_length * 3`
12. Weekly state updated in `pitcher_training_model.current_week_state` after each check-in

### Exercise Selection (`exercise_pool.py`)
- Filters library by: day focus (upper/lower/full), rotation_day_usage, contraindications, modification_flags
- Prefers exercises NOT used in last 7 days (weekly variety)
- **Session structure (flag-aware, 2026-04-09)**: green → full day_focus structure (2 compounds + 3 accessories + 2 core + 1 explosive = 8). YELLOW → day_focus minus 1 accessory (2 + 2 + 2 + 1 = 7) — caution trim, not shutdown. RED → light structure (1 + 2 + 1 + 0 = 4). The flag-level check is at `exercise_pool.py:172`. Prior to the fix, any yellow OR red collapsed to light (4 exercises) regardless of day_focus — undercutting roughly half the roster who are persistently yellow.
- Explosive block: 1 `plyometric_power` exercise (med ball slams, plyo pushups, jumps) inserted as first block on all green + yellow days (red skips)
- Training intent mapped from rotation day + triage: power (day 2), strength (day 3-4), endurance (recovery/flagged)
- Injury modification flags appended as notes (e.g., "reduce to 5 reps" for UCL history)
- **Model-aware filtering**: exercise_preferences ("dislike" → deprioritized), equipment_constraints (hard filter), swap history (3+ swaps away → auto-dislike)
- LLM adjusts prescriptions but CANNOT add exercises outside the pre-selected pool

### DailyCard Rendering — Dual Data Sources (Critical Gotcha)
- Lifting has TWO data sources: `lifting.exercises` (from LLM structured plan) and `plan_generated.exercise_blocks` (from Python fallback pool)
- `exercise_blocks` has `block_name` on parent objects ("Strength", "Accessories", "Core + Stability") — individual exercises do NOT have a `block` field
- `lifting.exercises` has flat exercises with optional `superset_group` for superset rendering (A1, A2, B1)
- Block stratification must read from `exercise_blocks` for sub-headers, NOT from individual exercise fields
- Props thread: DailyCard → ExerciseBlock → SupersetList → ExerciseItem — missing a prop at any level silently fails
- Swap overrides: `entry` prop is immutable from DailyCard — use local `swapOverrides` state map to reflect swaps without page refresh

### Day Phases (DailyCard Block Order)
Each daily plan has 5 phases rendered as blocks in the mini-app:
1. **Dynamic Warmup** — template-driven, collapsed by default, cuff vs scap activation, FPM addon for injury history
2. **Arm Care** — heavy or light arm care template (curated)
3. **Lifting** — exercise pool selection (dynamic)
4. **Throwing** — phased: pre-throw warmup → plyo drills → catch/long toss/bullpen → post-throw recovery
5. **Post-Throw Recovery** — tiered: light (5 ex) / medium (11 ex) / full (15 ex) based on throwing day type

Warmup and post-throw are template-driven (not LLM-generated). Stored in `warmup` JSONB column on `daily_entries`.

### Template Selection (Lift Preference)
- **Explicit preference always wins**: "upper" → day_3 template, "lower" → day_2, "rest" → day_6, regardless of rotation day
- **"Your call" / "auto" / empty**: falls back to rotation-based (`days_since_outing` → template day)
- Extended time off (past rotation cycle): uses preference if given, else mid-rotation
- Arm care templates (heavy/light) and throwing plans remain template-based (curated protocols)

### Timezone
All dates use `CHICAGO_TZ` (from `bot/config.py`). Server-side: `datetime.now(CHICAGO_TZ)`. Client-side: `toLocaleDateString('en-CA', { timeZone: 'America/Chicago' })`.

### DB Column Whitelist
`db.py` uses `_DAILY_ENTRY_COLUMNS` whitelist to strip unknown fields before upsert, preventing PostgREST 400 errors from schema mismatches.

### Pitcher Training Model
- Consolidates the old `active_flags` table + new exercise intelligence fields
- `profile["active_flags"]` dict is still populated via compatibility layer in `_profile_from_row()` — reads from `pitcher_training_model` table
- New fields (exercise_preferences, equipment_constraints, working_weights, recent_swap_history, current_week_state) accessed via `load_training_model(pitcher_id)` in context_manager
- `update_active_flags()` writes to `pitcher_training_model` (filtered to flag columns only)
- `weekly_summaries` table enriched with structured columns (avg_arm_feel, exercise_completion_rate, flag_distribution, etc.) alongside LLM narrative

### Two-Pass Plan Generation (Critical Path)
- Pass 1 (Python) builds `python_plan` — variables `training_intent`, `day_focus` MUST be defined before the try/except block around `build_exercise_pool()`, not inside it
- `active_modifications` is TEXT[] in `pitcher_training_model` (was JSONB in old `active_flags`). PostgREST handles list↔TEXT[] conversion. All callers pass Python lists.
- LLM timeout → `python_plan` ships. LLM parse failure → `python_plan` ships with raw LLM text as narrative. Both paths must have all fields `checkin_service.py` expects.

### Weekly Model + Proactive Suggestions
- `weekly_model.py`: `compute_next_day_suggestion()` runs after each check-in
- `current_week_state.next_day_suggestion` stores focus, throw_suggestion, reasoning, confidence
- Morning notification uses suggestion: high confidence → lead with direction, medium → suggest softly, low → ask
- Relievers: suggestion derived from actual throwing events (bullpen, game), not fixed rotation
- Starters: existing rotation enhanced with weekly movement pattern gap detection

### Coach-to-Plan Bridge
- Coach chat detects `plan_mutation` JSON blocks in LLM responses → returns `type: "plan_mutation"` message with `mutations` array
- `MutationPreview` component renders diff cards with Apply/Keep buttons
- `POST /apply-mutations` applies swap/add/remove/modify operations to daily entry
- Mutation format: `{ action: "swap|add|remove|modify", exercise_id, from_exercise_id, to_exercise_id, rx, note }`
- Applied mutations recorded in `pitcher_training_model.recent_swap_history`

### Game Appearance Detection
- `game_scraper.py`: detects game days from `schedule` table, prompts unreported relievers via Telegram
- 11pm daily job checks for relievers who didn't log outings on game days
- `update_pitcher_game_appearance()` records game appearances in weekly state and recomputes next-day suggestion

### Exercise Library (Dual Source)
- `exercise_library.json` — read by `_load_exercise_library()` in routes.py (cached with `lru_cache`). This serves the `/api/exercises` and `/api/exercises/slugs` endpoints.
- Supabase `exercises` table — read by `db.get_exercises()` and `exercise_pool.py` for plan generation.
- **Both must be updated** when adding/modifying exercises. JSON is the source of truth; sync to Supabase via migration script or MCP SQL.
- Currently 159 exercises (ex_001-ex_159). 10 still missing YouTube links (6 major lifts + 4 mobility stretches).

### Weekly Coaching Narrative
- `generate_weekly_narrative(pitcher_id)` in `progression.py` — LLM-generated Sunday evening
- `build_week_snapshot()` collects arm feel, sleep, exercise completion, throwing, modifications
- Stored in `weekly_summaries` table, served via `/api/pitcher/{id}/weekly-narrative`
- Displayed in `InsightsCard` on Home with maroon accent border
- Falls back to stats-only summary if LLM fails

### Mobility Video Rotation
- 21 YouTube follow-along videos in `data/knowledge/mobility_videos.json` and `mobility_videos` Supabase table
- 10-week rotation: 4 videos/week (3 P/R postural restoration + 1 targeted: Hip, Full, Back, Lower, Shoulder, Spine)
- Cycles endlessly: `cycle_week = (iso_week % 10) + 1`
- `bot/services/mobility.py`: `get_today_mobility()` returns week number + 4 video objects
- Plan generator includes `mobility` in plan output; DailyCard falls back to `GET /api/pitcher/{id}/mobility-today`
- `MobilityCard` renders after all exercise blocks — clickable YouTube video links, not checkable exercises

### Toast Notifications (Mini-App)
- `useToast` hook + `ToastProvider` in `hooks/useToast.jsx`
- Success toasts: plan generated, outing logged, plan activated/applied
- Error toasts: exercise save failed, plan update failed
- Auto-dismiss after 3.5 seconds

### WHOOP Integration (Live)
Fully implemented 2026-03-29, v2 API migration 2026-03-31, PKCE state persistence fix 2026-04-01.
- **API v2** — migrated from v1 (deprecated, returning 404s on recovery/sleep endpoints)
- Per-pitcher OAuth PKCE linking via `/whoop` command + `/api/whoop/callback`
- PKCE state persisted in `whoop_pending_auth` Supabase table (survives Railway restarts)
- Tokens stored in Supabase `whoop_tokens` table, auto-refresh on expiry
- Daily 6am pull: recovery, HRV, sleep, strain → `whoop_daily` table
- **Smart cache with force_refresh**: check-in always pulls fresh (`force_refresh=True`), morning message pulls live (not cache-only). 6am pull may get partial data (strain arrives before recovery/sleep); cache stays incomplete → next pull fills in.
- **`score_state` guard**: only extracts metrics when WHOOP returns `SCORED`. `PENDING_SCORE` (common at 6am) is logged and treated as no-data so cache triggers re-pull later.
- **Type casting**: recovery_score and sleep_performance cast to int before Supabase upsert (v2 returns floats, Postgres columns are integer)
- Feeds into triage (`whoop_hrv`, `whoop_hrv_7day_avg`, `whoop_sleep_perf` params), plan generation (LLM context block), weekly narrative
- `WhoopCard` component on Home page (recovery ring + HRV/sleep/strain satellites), only renders for linked pitchers
- Profile page shows "WHOOP Connected" badge or link instructions
- `/whooptest` command: force-pulls fresh data and displays all fields + raw endpoint status for debugging
- All code paths gracefully handle `whoop_data=None` — non-WHOOP pitchers unaffected

### Dual LLM Routing
- `call_llm()` — fast model (deepseek-chat, 90s timeout) for Q&A, plan personalization, weekly narrative
- `call_llm_reasoning()` — reasoning model (deepseek-reasoner, 120s timeout) for multi-day protocols, complex recovery plans
- `return_metadata=True` option surfaces `finish_reason` — plan generator uses this to detect truncated JSON
- Plan gen uses `max_tokens=4000` for both models
- Keyword detection in qa.py routes to appropriate model

### Plan Source Tagging
- `generate_plan()` returns `source: "python_fallback" | "llm_enriched"` + `source_reason` on every plan
- `source_reason` captures the specific failure mode when the LLM path degrades: `llm_timeout:{ExcType}`, `llm_unparseable_json`, `llm_assembly_error:{ExcType}`
- Threaded through `checkin_service.py` into `daily_entries.plan_generated.source` (JSONB) — persists for later analysis
- `/chat` checkin response status gate: `None → plan_failed`, `"python_fallback" → plan_degraded`, else `plan_loaded`
- `Coach.jsx` listens for `plan_degraded` and shows a warning toast + "Retry for coach brief" pill (derived from `todayEntry.plan_generated.source === 'python_fallback'` so it survives reload)
- The `_emergency_alert` key on `python_plan` is an internal carry-up to checkin_service for real-time Telegram alerts; `_send_emergency_alert_if_present()` pops it before persistence so it never reaches Supabase

### Silent Degradation Monitoring (`bot/services/health_monitor.py`)
- **Daily digest**: 9am Chicago Telegram DM to `ADMIN_TELEGRAM_CHAT_ID` (defaults to Landon's 8589499360). Shows plan source breakdown, source_reason counts, degraded pitcher IDs, WHOOP pull completeness, Sunday weekly narrative presence, Q&A error rate.
- **Emergency alerts**: real-time Telegram DM when 3+ matching failure patterns hit in 30 min. Known-bad patterns: `APIStatusError`, `APIError`, `AuthenticationError`, `PermissionDeniedError`, `InsufficientBalance`, `insufficient_balance`, `RateLimitError`, `rate_limit`. Per-pattern 2-hour dedup prevents spam. State is in-memory — Railway restart wipes counters (acceptable loss).
- **Q&A tracking**: in-memory success/error counters with midnight-Chicago reset. Hooked into both `routes.py /chat` Q&A branch and `bot/handlers/qa.py`.
- **Admin commands**: `/healthdigest` (force send), `/healthcheck` (on-demand), `/testemergency` (simulate 3 failures). All gated on `effective_chat.id == ADMIN_TELEGRAM_CHAT_ID`.
- **Admin endpoint**: `GET /api/admin/health` returns raw digest JSON, auth via initData match.
- **All instrumentation is try/except-wrapped with `pass`** — monitoring must never regress the user path.
- `ADMIN_TELEGRAM_CHAT_ID` env var in `bot/config.py` overrides the default.

### Guided Day Flow (DailyCard.jsx)
- **5 phases** computed per-entry via `computePhaseOrder(entry, mobility)`: warmup → arm_care → lifting → throwing → mobility. Order respects `arm_care.timing` (`pre_throw` vs `pre_lift`). Post-throw recovery is NOT a separate phase — nested inside throwing. Empty phases are skipped.
- **Active phase** = first-incomplete via `useMemo`. Derived from `completed_exercises` + `manuallyDonePhases` Set. Completion rule: mobility is always complete (terminal), empty phases are complete, manually-marked phases are complete, otherwise all items must be in `completed_exercises`.
- **Visual states**: `active` (3px maroon `box-shadow: inset` stripe + subtle `rgba(92,16,32,0.018)` bg tint + floating "NOW" pill + "Done with [phase] →" gradient button), `locked` (full opacity, tappable, no extra chrome), `complete` (collapsed one-line `CompletedPhaseSummary` row with check badge + count pill + chevron, re-expandable).
- **"Mark done" button** — maroon gradient, sentence case, advances `manuallyDonePhases`. Auto-advance also happens when all items are checked (derived).
- **Re-collapse** — re-expanded completed phases get a subtle `CollapsePhaseButton` (outline maroon) at the bottom.
- **Ephemeral state** — `manuallyDonePhases` and `expandedCompletedPhases` are component-local. V1 scope; persistence is v2.
- **Bypassed when `readOnly=true`** (past-day log views).
- **Helper functions are pure and module-level**: `PHASE_DEFS`, `computePhaseOrder`, `getPhaseItems`, `isPhaseComplete`. All in DailyCard.jsx.
- **`wrapperStyle` prop** on `ExerciseBlock` and `ThrowingBlock` — merges into the outer div for the stripe + tint. Backward-compatible.

### Swap / Mutation Dual-Write (Critical Gotcha)
- `daily_entries` has **two places** lifting can live: top-level `lifting` JSONB column (written by `checkin_service`) AND nested `plan_generated.lifting` (written by `apply_mutations` / coach chat). Before 2026-04-09 these could drift, causing 404s on `swap_exercise`.
- `swap_exercise` and `apply_mutations` now search top-level `entry.lifting.exercises` FIRST (canonical modern path), fall back to `plan_generated.lifting.exercises`, then `plan_generated.exercise_blocks`. On success, both locations are written back for consistency.
- The frontend (DailyCard line ~88: `lifting: entry.lifting || plan_generated?.lifting`) always reads top-level first, so "what the frontend shows" is the source of truth.

### Research Resolver (`bot/services/research_resolver.py`)
- **Single door for all surfaces** — `resolve_research(profile, context, triage, user_message, max_chars)` replaces all research routing. Context is one of: `plan_gen`, `coach_chat`, `morning`, `daily_plan_why`.
- **Frontmatter-driven** — each research doc in `data/knowledge/research/` has YAML with `id`, `applies_to` (injury areas or `any`), `triggers` (tag keys), `priority` (critical/standard/reference), `contexts` (which surfaces can load it).
- **Four-step selection** — (1) critical + applies_to match, (2) trigger intersection from triage mods, (3) user message keyword match (coach_chat only), (4) standard docs for remaining budget.
- **`should_fire_research(profile, triage, user_message)`** — gates all surfaces. Three OR'd conditions: non-green flag, active modifications, injury keyword in message.
- **Observability** — every `resolve_research()` call logs to `research_load_log` table (pitcher_id, context, trigger_reason, loaded_doc_ids, total_chars, degraded). Non-blocking.
- **Module-level `_index_cache`** — persists for process lifetime. `clear_cache()` resets. Called when new research is generated via `classify_and_generate_research()`.

### Vocabulary (`bot/services/vocabulary.py`)
- **`INJURY_AREAS`** — 8 canonical areas (medial_elbow, forearm, shoulder, lower_back, oblique, hip, knee, ulnar_nerve). Each has `keywords` (for free-text matching) and `research_triggers` (for doc routing).
- **`MODIFICATION_TAGS`** — 14 canonical tags (fpm_volume, rpe_cap_56, no_lifting, etc.). Each has `description` (human-readable) and `research_triggers`. Triage emits tag keys; `get_mod_description(tag)` converts to description for display.
- **Consumed by** — `triage.py` (emits tag keys), `exercise_pool.py` (imports `INJURY_AREAS`), `research_resolver.py` (uses triggers for routing), `plan_generator.py` (uses `get_mod_description` for brief/notes).

### Research-Aware Coach Chat
- **Structured output** — when `should_fire_research()` fires, coach chat uses `coach_chat_prompt.md` which instructs LLM to return JSON `{reply, mutation_card, lookahead}`. `_parse_coach_response()` in `qa.py` handles parsing; `_extract_reply_fallback()` extracts reply from malformed JSON.
- **mutation_card** — `{type, title, rationale, actions[], applies_to_date}`. Actions use same format as existing `apply_mutations` endpoint. API `/chat` returns cards as `type: "plan_mutation"` messages.
- **Fallback** — if research doesn't fire, standard Q&A path runs (qa_prompt.md + retrieve_knowledge). Both paths coexist in `api/routes.py` `post_chat`.

### API Endpoints (routes.py)
**Auth:** `/api/auth/resolve`
**Admin:** `GET /admin/health` (admin-only, initData match to `ADMIN_TELEGRAM_CHAT_ID`)
**Data:** `/api/pitcher/{id}/profile`, `/log`, `/progression`, `/upcoming`, `/week-summary`, `/morning-status`, `/weekly-narrative`
**Actions:** `POST /checkin`, `/outing`, `/chat` (unified), `/set-next-outing`, `/complete-exercise`
**Mobility:** `GET /pitcher/{id}/mobility-today`
**Swap:** `GET /exercises/{id}/alternatives?pitcher_id=X`, `POST /pitcher/{id}/swap-exercise`
**Mutations:** `POST /pitcher/{id}/apply-mutations` (coach-suggested plan changes)
**WHOOP:** `GET /pitcher/{id}/whoop-today`, `GET /whoop/callback` (OAuth)
**Plans:** `GET/POST /plans`, `/plans/{id}/activate`, `/deactivate`, `/apply-plan/{id}`, `/generate-plan`
**Research:** `GET /research/docs?ids=...` (doc metadata for daily plan "why" bottom sheet)
**Library:** `/api/exercises`, `/api/exercises/slugs`
**Team:** `/api/staff/pulse` (known issue: intermittent 500s)
**Trends:** `/api/pitcher/{id}/trend`, `/api/pitcher/{id}/chat-history`

### Scheduled Jobs (all from Supabase, not filesystem)
- Morning check-in at pitcher's `notification_time`
- 6pm follow-up if unanswered
- Sunday 6pm weekly narrative + summary
- `/gamestart` → 2hr delayed outing reminder
- 6am daily WHOOP pull for all linked pitchers (sends re-link message if auth expired)
- **9am daily health digest** to admin (`health_monitor._send_health_digest`)
- 11pm post-game reliever check

## Current Pitchers

| ID | Name | Role | Notes |
|----|------|------|-------|
| landon_brice | Landon Brice | Starter (7-day) | Primary user/developer |
| pitcher_benner_001 | Preston Benner | Starter (7-day) | LHP, UCL sprain history (PRP) |
| pitcher_hartrick_001 | Wade Hartrick | Reliever (short) | Flexor/pronator strain history |
| pitcher_heron_001 | Carter Heron | Reliever (long) | YELLOW — TJ + olecranon, 1yr post-op |
| pitcher_kamat_001 | Taran Kamat | Reliever (short) | Shoulder impingement/GIRD (95%, recurs), whoop |
| pitcher_kwinter_001 | Russell Kwinter | Starter (7-day) | LHP, partial UCL tear (2023, not fully resolved), low back, whoop |
| pitcher_lazar_001 | Jonathan Lazar | Reliever (short) | Labrum surgery (~3yr ago), beginner lifter, no pull-ups |
| pitcher_reed_001 | Lucien Reed | Reliever (short) | Recurring ulnar nerve impingement |
| pitcher_richert_001 | Matthew Richert | Reliever (long) | UCL strain (2024), scap/shoulder soreness, whoop |
| pitcher_sosna_001 | Mike Sosna | Reliever (short) | Active oblique strain, forearm tightness, very strong (585 trap bar) |
| pitcher_wilson_001 | Wilson | Reliever (short) | YELLOW — active ulnar nerve symptoms |
| test_pitcher_001 | Test Pitcher | Starter (7-day) | Test account |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| TELEGRAM_BOT_TOKEN | yes | — | From @BotFather |
| DEEPSEEK_API_KEY | yes | — | DeepSeek API key |
| SUPABASE_URL | yes | — | Supabase project URL |
| SUPABASE_SERVICE_KEY | yes | — | Supabase service role key |
| MINI_APP_URL | no | — | Vercel mini-app URL |
| LLM_PROVIDER | no | deepseek | Provider name |
| LLM_MODEL | no | deepseek-chat | Model identifier |
| WHOOP_CLIENT_ID | yes (for WHOOP) | — | From WHOOP developer portal |
| WHOOP_CLIENT_SECRET | yes (for WHOOP) | — | From WHOOP developer portal |
| WHOOP_REDIRECT_URI | no | Railway callback URL | OAuth redirect URI |
| TAVILY_API_KEY | no | — | Web research fallback |
| PORT | no | 8000 | API port |
| DISABLE_AUTH | no | false | Skip HMAC auth (dev only) |
| ADMIN_TELEGRAM_CHAT_ID | no | 8589499360 (Landon) | Admin chat for health monitoring DMs |

## Running Locally

```bash
cd pitcher_program_app
pip install -r requirements.txt

# Bot
python -m bot.main

# API (separate terminal)
python -m api.main

# Mini-app (separate terminal)
cd mini-app && npm install && npm run dev
```

**Note:** No Python virtualenv exists locally — the project runs on Railway. Use Supabase MCP for SQL operations and database queries. Python scripts (migrations, data ops) should be run via Supabase SQL when possible, or deployed to Railway for execution.

## Supabase Schema

Project: `pitcher-training-intel` (us-east-1)

| Table | Purpose |
|-------|---------|
| `pitchers` | Pitcher profiles — id, name, role, physical/pitching/training/biometric JSONB fields |
| `injury_history` | Per-pitcher injury records with severity, area, flag_level, red_flags |
| `pitcher_training_model` | Consolidated pitcher state — arm_feel, flag_level, days_since_outing, modifications, exercise preferences, equipment constraints, swap history, weekly arc |
| `daily_entries` | Daily training logs — pre_training, plan_generated, actual_logged, completed_exercises |
| `exercises` | Exercise library (159 exercises) — prescription, tags, contraindications, youtube_url |
| `templates` | Training templates (9) — rotation day structure, exercise blocks |
| `saved_plans` | Pitcher-specific saved/generated plans with plan_data JSONB |
| `chat_messages` | Cross-platform conversation persistence — source (telegram/mini_app), role, content |
| `weekly_summaries` | Aggregated weekly data for long-term tracking |
| `whoop_tokens` | Per-pitcher WHOOP OAuth tokens (access, refresh, expiry) |
| `whoop_daily` | Daily WHOOP biometrics — recovery, HRV, sleep, strain, raw API data |
| `mobility_videos` | 21 follow-along mobility videos — id, title, youtube_url, type (P/R, Hip, Full, etc.) |
| `mobility_weekly_rotation` | 10-week rotation schedule — week (1-10), slot (1-4), video_id FK |
| `research_load_log` | Observability: every `resolve_research()` call — pitcher_id, context, trigger_reason, loaded_doc_ids, total_chars, degraded |
| `teams` | Team identity — team_id, name, level, training_phase, timezone, settings |
| `coaches` | Coach accounts — links to Supabase Auth user, team_id scoped |
| `team_games` | Schedule (replaces old `schedule` table) — game_date, opponent, starter assignment, status |
| `block_library` | Throwing program templates — velocity_12wk, longtoss_6wk, offseason_4wk |
| `team_assigned_blocks` | Active team programs — links block_library template to team with start_date |
| `coach_suggestions` | AI-generated coaching insights — pre_start_nudge category, accept/dismiss workflow |
| `training_phase_blocks` | Off-season phase timeline — GPP, Strength, Power, Preseason, In-Season with emphasis |

## Deployment

### Architecture
```
GitHub (landonbrice/baseball)
  └─ pitcher_program_app/          ← Railway root
       ├─ bot/ + api/              ← Python backend (Railway) — includes coach_routes + coach_auth
       ├─ mini-app/                ← React pitcher frontend (Vercel)
       ├─ coach-app/               ← React coach dashboard (Vercel, separate project)
       └─ data/                    ← JSON fallback (read-only, Supabase is primary)
```

### Railway (Bot + API)
- **Service:** Single process via `Procfile: web: python -m bot.run`
- **Root directory:** `pitcher_program_app` (or repo root with `cd pitcher_program_app`)
- **Auto-deploy:** On push to `main`
- **Required env vars:** `TELEGRAM_BOT_TOKEN`, `DEEPSEEK_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_JWT_SECRET`
- **Optional env vars:** `MINI_APP_URL`, `COACH_APP_URL`, `DISABLE_AUTH` (dev only)

### Vercel (Mini App)
- **Root directory:** `pitcher_program_app/mini-app`
- **Framework:** Vite (auto-detected)
- **Build:** `npm run build` → `dist/`
- **Auto-deploy:** On push to `main`
- **Env vars:** `VITE_API_URL=https://baseball-production-9d28.up.railway.app` (set in `.env.production`)

### Vercel (Coach App)
- **Root directory:** `pitcher_program_app/coach-app`
- **Framework:** Vite
- **Build:** `npm run build` → `dist/`
- **URL:** `baseball-copiblin-landonbrices-projects.vercel.app`
- **Env vars:** `VITE_API_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`
- **CORS:** `COACH_APP_URL` in Railway must match the Vercel URL exactly (no trailing slash)

### Supabase (Database)
- **Project:** `pitcher-training-intel` (us-east-1, free tier)
- **URL:** `https://beyolhukpbvvoxvjnwtd.supabase.co`
- **Migrations:** Applied via Supabase MCP or dashboard SQL editor
- **Migration script:** `python -m scripts.migrate_to_supabase` (idempotent, safe to re-run)
- **Backup:** Supabase handles persistence. JSON files in `data/` are read-only fallback.
- **FK pattern**: `pitchers` table PK is `pitcher_id` (not `id`). FK references must use `REFERENCES pitchers(pitcher_id)`

### Handler Registration
`register_handlers(application)` in `bot/main.py` is the **single source of truth** for all bot command/message handlers. Both `main.py` (local dev) and `run.py` (Railway) call this function. **Add new commands in `register_handlers()` only** — never add handlers directly in `run.py`.

### Deploy Checklist
1. Push to `main` → Railway + Vercel auto-deploy
2. If adding new Supabase tables/columns → apply migration first via MCP or dashboard
3. If changing env vars → update in Railway dashboard, trigger redeploy
4. If modifying templates → run `python -m scripts.validate_templates` to check exercise IDs
5. Verify: bot responds to `/checkin`, API health at `/api/staff/pulse`, mini-app loads in Telegram

### Data Safety
- **Supabase is source of truth.** JSON files are read-only fallback (`USE_JSON_FALLBACK=true`).
- **`data_sync.py` is disabled.** No more auto-push to GitHub on writes.
- **JSONB guard pattern:** Always use `(x.get("field") or {}).get()` in Python, `Array.isArray()`/`typeof` in React. See `mini-app/src/utils/sanitize.js`.

### Check-in Flow
- Morning notification arm feel buttons (1-5) are ConversationHandler entry points → full check-in flow
- API sends `plan_failed` status (not `plan_loaded`) when plan generation fails
- `hasCheckedIn` in Coach.jsx and Home.jsx requires actual plan data, not just `pre_training.arm_feel`
- "Retry plan" button re-triggers triage + plan gen with saved check-in data
- "Re-check-in" button allows re-running full check-in on same day (upserts, doesn't duplicate)
- Rotation day only increments on first successful check-in of the day
- **Two check-in paths exist:** Telegram (`daily_checkin.py` → `process_checkin`) and mini-app (`/chat` endpoint → `process_checkin`). Both call `process_checkin` but the `/chat` wrapper has its own response assembly that can crash independently. Telegram has no browser timeout; mini-app fetch dies at ~60s.
- Response assembly in `/chat` checkin path is wrapped in its own try/except — if it crashes, returns `plan_loaded` anyway (plan is already saved by `process_checkin`)

### Onboarding (`/start`)
- Personalized intro: references pitcher's role, injury history, rotation day
- If not checked in today: ends with arm feel keyboard (one tap to enter check-in flow)
- If already checked in: acknowledges plan, invites questions
- No command list shown — the interaction IS the onboarding

### Plan Generation Resilience
- Exercise pool builder guarantees valid exercise IDs from the library (no LLM hallucination)
- `_validate_plan()` strips unknown exercise IDs before minimum-count check, backfills from pool
- `_parse_plan_json()` surfaces `finish_reason: "length"` for truncation detection
- `max_tokens=4000` for both fast and reasoning models; LLM review timeout=20s (normal), 120s (red/RTT)
- `generate_plan()` returns `python_plan` dict on any LLM failure — new plan fields must be added to `python_plan` AND the LLM success path
- **`morning_brief` can be a string OR a JSON-serialized dict** — always coerce to string before using in message content. The structured brief dict has a `coaching_note` key for the text portion.
- Template-driven blocks (warmup, post-throw) are injected by plan_generator, not LLM-generated

### UI Change Process
- Before any DailyCard rendering change, query actual `daily_entries` data from Supabase to verify the shape of `lifting`, `exercise_blocks`, and `plan_generated`
- Test with at least 2 different dates — LLM-generated plans and Python fallback plans have different field structures

## Known Issues & Tech Debt

- 10 exercises missing YouTube links: ex_121-123, ex_126-128 (major lifts — not in source xlsx), ex_156-159 (new mobility stretches)
- `data_sync.py` still exists but is disabled — can be removed entirely
- WHOOP 6am pull may get partial data (strain before recovery/sleep) — handled by force_refresh on check-in and score_state guards
- Reliever template (`reliever_flexible.json`) uses text descriptions, not exercise IDs — not validated
- No periodization layer — exercise pool adds variety but not multi-week progressive structure
- Truncated JSON repair exists (`plan_generator.py:439` `_repair_truncated_json`) but only runs when `finish_reason == "length"`. Doesn't handle network cutoffs that leave `finish_reason == "stop"` on a partial body. Low priority — two-pass gen ships `python_plan` on any parse failure.
- `/testnotify`, `/whooptest`, `/healthdigest`, `/testemergency` dev commands exist — can be removed before team rollout
- `_load_exercise_library()` and `_EXERCISE_CACHE` both use module-level caching with no invalidation — new exercises in JSON/Supabase require a Railway redeploy
- `/api/staff/pulse` returns 500 intermittently — likely a crash in the pitcher loop (undiagnosed). Home page `StaffPulse` component handles gracefully but the endpoint needs debugging.
- **Coach dashboard CORS blocker** — `COACH_APP_URL` env var in Railway must be set to exactly `https://baseball-copiblin-landonbrices-projects.vercel.app` (no trailing slash). Without it, the Supabase JWT exchange POST to `/api/coach/auth/exchange` is blocked by CORS preflight. Backend routes are verified live (`/openapi.json` shows all 30 `/api/coach/*` endpoints). Auth user + coaches row exist. The fix is setting the env var and redeploying Railway. Confirmed: `SUPABASE_JWT_SECRET` is set (invalid tokens return 401, not crash), `VITE_SUPABASE_ANON_KEY` is set in Vercel.
- `morning_brief` string/dict coercion is duplicated in 4 places: `plan_generator.py:314`, `routes.py:636`, `Coach.jsx:130`, and the /chat response assembly. Every consumer has to re-coerce. Should be normalized once at the checkin_service return boundary.
- `context_manager.py:173` does `msg.get("content","")[:200]` with no `str()` coercion. If any `chat_messages` row has a dict in `content`, slicing raises TypeError. Currently not triggering in practice (`_persist_chat` only writes strings) but latent.
- Guided flow state is ephemeral — `manuallyDonePhases` resets on reload. Not a bug, a v2 deferral.

## Bot Scope Boundaries

**Owns:** Lifting programs, arm care, plyocare, recovery, readiness triage, Q&A, longitudinal tracking, program modifications based on injury/biometrics.

**Does NOT own:** Mechanical instruction, medical diagnosis, supplement recommendations. Flags concerns → tells pitcher to see trainer.
