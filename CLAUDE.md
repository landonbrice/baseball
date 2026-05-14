# Pitcher Training Intelligence — Claude Init

> Last updated: 2026-05-13
> Sprint status: Phases 1-20.1 + Sprint 0.5 + Tier 1 Hardening + Redesign Specs 1/2/3 + Check-in Hotfix + Hotfix #2 + **Phase 1 Trajectory-Aware Triage (absorbs Sprint 1a)** + Energy Capture UI + Team Daily Status Sync + WHOOP RLS Lockdown + LLM Enrichment Recovery + Public Schema Lockdown + **System Guardian V1 (PRs #15-#21)** complete. System Guardian V1 shipped end-to-end across six sequenced PRs: amendments doc (the build contract, `docs/superpowers/plans/2026-05-09-system-guardian-amendments.md`), migration `019_system_guardian_tables.sql` (three RLS-locked tables + `prune_old_observations()` SQL fn), `bot/services/system_guardian/` Python package (normalize/classify/cluster/incidents/debug_packet/store + A4 dual-pass redactor with synthetic-JWT test) plus 3am prune scheduler, `existing_health` collector wrapping `compute_daily_digest()` + `compute_plan_health_rolling()` with new Guardian summary section appended to the 9am admin Telegram digest, `app_health` + `supabase_app` collectors (in-process FastAPI probe via ASGITransport + Phase 1 telemetry queries), `/admin/guardian/*` admin API gated by `X-Guardian-Admin-Token` header (`GUARDIAN_ADMIN_TOKEN` env var) + `notify.py` Telegram dispatcher implementing A6's dedup contract + 24h shakedown window persisted via sentinel-row in `system_observations`, and finally the A1 runtime contract enforcement — `run_guardian_tick()` orchestrator with 30s wallclock budget, 5s per-collector belt-and-suspenders timeout, and consecutive-over-budget detection (info → warning on 2nd → critical on 5th) wired to a 15-minute periodic job. 222 Guardian tests, 556 in the full suite, all green. Next: coach-app Phase 1 surfacing (category scores on PlayerSlideOver + flagged-feed copy), Guardian Phase 2 (Railway + Supabase mgmt collectors, requires new env vars), Guardian Phase 3 (vision drift, blocked on `PRODUCT_VISION_DRAFT.md` + `PRODUCT_BUILD_PLAN.md`), Tier 2 hardening, The Ledger, weight logging UI, Regression #2 (Telegram getUpdates conflict — infra), and Issue #2 (energy capture defaulting to 3 across recovery/low-arm/Telegram paths — backend default lies, deferred from this hotfix).

## What This Is

A training intelligence system for the UChicago baseball pitching staff. Telegram bot + FastAPI API + React Mini App + Coach Dashboard. Each pitcher gets personalized daily programs (lifting, arm care, recovery, throwing), evidence-based Q&A, and longitudinal tracking — driven by their individual profile, injury history, and conversation context.

**Four layers:**
- **Bot (Telegram)** — Conversational input layer. Morning check-ins, post-outing reports, free-text Q&A.
- **Mini App (React)** — Pitcher-facing. Programs, completion tracking, guided day flow, trajectory over time.
- **Coach Dashboard (React)** — Staff-facing. Roster overview, schedule, team programs, phase management, AI-generated insights.
- **Intelligence Engine (Python/FastAPI)** — Triage, plan generation, knowledge retrieval, research resolver, progression analysis.

## Completed Phases

| Phase | Name | Date | Summary |
|-------|------|------|---------|
| 1-5 | Foundation → Polish | 2026-03-28 | Supabase migration, state awareness, coaching quality, visible compounding, bug fixes |
| 6 | WHOOP Integration | 03-29 | Full biometric pipeline: OAuth PKCE, daily pulls, triage integration, WhoopCard UI |
| 7 | Adoption Push | 03-30 | Personalized `/start`, contextual morning notifications, arm feel → check-in flow |
| 8 | Dynamic Exercise Pool | 03-31 | 155-exercise library drives selection. Injury-aware, variety across weeks, explosive block |
| 9 | Exercise Enrichment + Mobility | 03-31 | Library → 155 exercises, 21 mobility videos in 10-week cycling rotation |
| 10 | Day Phases | 03-31 | Dynamic warmup (cuff/scap + FPM addon), tiered post-throw recovery (light/medium/full) |
| 11 | Onboarding UX | 03-31 | Welcome card, coach personalized intro, graceful degradation for sparse profiles |
| 12 | Pitcher Training Model | 04-01 | Consolidated `active_flags` + exercise intelligence + weekly arc into single table |
| 13 | Exercise Swap UI | 04-02 | Inline swap with reason pills, model-aware alternatives, auto-dislike after 3+ swaps |
| 14 | Two-Pass Plan Gen | 04-02 | Python builds instant plan, LLM reviews. No more timeout failures. Weekly model + proactive suggestions |
| 15 | Coach Bridge + Game Detection | 04-02 | Coach chat → mutation preview cards, `/apply-mutations`, game day detection, reliever prompts |
| 16 | Source Tagging + Hardening | 04-09 | Yellow-flag trim fix (7 exercises not 4), plan source/reason tagging, `plan_degraded` status gate |
| 17 | Silent Degradation Monitoring | 04-09 | 9am health digest, real-time emergency alerts (3+ failures/30min), Q&A tracking, admin commands |
| 18 | Guided Day Flow | 04-09 | 5-phase guided sequence (warmup→arm care→lifting→throwing→mobility), completion collapse, "NOW" accent |
| 18a | Swap Dual-Write Fix | 04-09 | `swap_exercise` + `apply_mutations` now search top-level `lifting.exercises` first, write both locations |
| 19 | Research-Aware Coaching | 04-10 | Unified resolver, frontmatter-driven research docs, structured coach chat, morning enrichment, "why" sheet |
| 20 | Coach Dashboard v0 | 04-12 | Full coach-facing app: 7 new DB tables, 30 API endpoints, JWT auth, 6 screens, 13 components. CORS blocker remains |
| 0.5 | Scale Migration | 04-13 | arm_feel/energy rescaled 1-5→1-10 across bot, API, mini-app, coach-app, prompts, data templates. Supabase data migrated ×2. Chart axes reworked. |
| 20.1 | Coach Dashboard Unblock | 04-14 | Coach app live end-to-end. CORS (`COACH_APP_URL=https://baseball-self.vercel.app`), ES256/JWKS JWT validator (`PyJWT[crypto]`), `Shell` children-render fix, `team_scope` schema realignment (`physical`→`physical_profile` dropped, `flag_level`→`current_flag_level`, `injury_history.status` removed). |
| Spec 1 | Coach Dashboard Redesign — Brand System & Shell | 04-19 | Editorial brand shell replaces generic Tailwind shell. `src/styles/tokens.css` adds 28 locked tokens (UChicago maroon `#5c1020` + cream `#f7f1e3`, alert crimson/amber/forest, 10-step type scale). Self-hosted Source Serif 4 (400/600/700 + 400 italic) + Inter. 7 shared components in `src/components/shell/` — `Sidebar`, `TeamBrand`, `Masthead`, `Scoreboard`, `Lede`, `FlagPill`, `EditorialState`, `Toast`. Vitest + RTL added (49 tests, token contract locked). Dev-only `/__design` sandbox w/ axe smoke check (lazy-loaded). `Shell.jsx` and old `Toast.jsx` deleted. Page bodies preserved — Specs 2 and 3 replace them. |
| Spec 2 | Coach Dashboard Redesign — Team Overview | 04-19 | Team Overview rebuilt as a triage feed. Backend: `team_scope.get_team_roster_overview` now returns `af_7d` (7-day arm-feel mean) and `today` object per roster row — `day_focus` derived from plan content (plan_generator never persists it) and modification list normalized from triage strings to `{tag, reason}` dicts at the boundary. Frontend: 2 pure formatter utils (`buildTodayObjective`, `buildTeamLede`) with 16 fixtures total, 5 new components in `components/team-overview/` (`LastSevenStrip`, `HeroCard`, `CompactCard`, `PendingStrip`, `TeamLede`), TeamOverview rewritten with 90s `visibilityState`-gated auto-refresh. `PlayerSlideOver` header redesigned with 3-stat mini scoreboard, ESC-to-close, 480px width; `PlayerToday` / `PlayerWeek` / `PlayerHistory` (inline-SVG sparklines) all rebuilt editorially. `RosterTable` + `ComplianceRing` deleted. Shared `formatToday.js` helper extracted. Tests: 81 frontend + 55 Python. |
| Spec 3 | Coach Dashboard Redesign — Secondary Pages + Nudge | 04-21 | Remaining four coach pages rebuilt on the Spec 2 Scoreboard-anchored editorial pattern. Insights: editorial `InsightCard` + scoreboard-anchored Insights page. Schedule: `WeekStrip` + `GameCard` + `GamePanel` restyle with roster dot cap documented. Team Programs: `BlockCard` + `LibraryCard` + `CreateProgramSlideOver` + TeamPrograms rebuild with error state + catch-branch safety + autoFocus on name. Phases: `PhaseTimeline` + `PhaseEditorSlideOver` + `PhaseDetailSection` + Phases rebuild (orphaned flat components deleted, new cards keyboard-accessible). Nudge backend: `007_coach_actions.sql` migration, `send_nudge` service with audit insert, `POST /api/coach/pitcher/{id}/nudge` endpoint, `nudgePitcher` api.js stub, `PendingStrip.nudgeEnabled = true`. Energy capture UI (D3 UI follow-up) also landed — mini-app Coach.jsx check-in conversation now captures energy before sending to backend. |
| Phase 1 | Trajectory-Aware Triage + Baselines (Sprint 1a absorbed) | 04-21 | Intelligence engine rewrite. `triage.py` 300→~1,000 lines with dual-path architecture: legacy flat-trigger path preserved for pitchers without a baseline (43 golden snapshots), new three-category path for pitchers with a baseline — `_compute_tissue_score`/`_compute_load_score`/`_compute_recovery_score` (0-10 each) then `_apply_interaction_rules` with per-tier tolerance bands. `_evaluate_recovery_curve` handles stall/reversal/on-track, late-rotation readiness, chronic drift, and trend flags. New `baselines.py` (273 lines): per-pitcher recovery curves + tier classification + chronic drift detection + cache-aware refresh with TTL and outing-event invalidation. `population_baselines.yaml` seeds defaults; `007_baseline_snapshot.sql` persists per-pitcher snapshots. `checkin_service.py` wired to pull baseline and persist category scores. Observability: structured logging on every triage call + persisted category scores in `daily_entries`. `phase1-runbook.md` documents operation. Tests: ~1,500 lines across `test_triage_phase1.py` (947 lines), `test_baselines.py` (230 lines), `test_checkin_service_phase1.py` (307 lines). **Sprint 1a trend signals (rate-of-change, persistence, slope) absorbed directly into the new triage scoring** rather than built as standalone `detect_trends()` metadata layer. `bb2da39` fixed 6 bugs (C1-C4, I1-I2) found in code review. |
| Team Daily Status Sync | Shared check-in contract | 04-30 | `bot/services/team_daily_status.py` is now the canonical owner for team daily check-in, plan, work, Chicago-date, and team_id-scoped roster status. Check-in means `daily_entries.pre_training.arm_feel is not null` (legacy in-memory fallback: top-level `arm_feel` if present); plan status is separate (`generated` / `pending` / `not_applicable`); work status is separate (`not_started` / `in_progress` / `completed` / `unknown`). `/api/coach/team/overview` and `/api/staff/pulse` both adapt this service while preserving legacy response shapes. Staff pulse is team-aware via `GET /api/staff/pulse?team_id=uchicago_baseball` with a safe default. Mini-app profile now exposes `team_id` and Home passes it to staff pulse. Frontend helpers prefer canonical `checkin_status` with legacy `today_status` / `checked_in` fallback. Production hardening: team status Supabase selects intentionally avoid optional/non-guaranteed `daily_entries` columns (`arm_feel`, `rationale`, `arm_care`, `mobility`) to tolerate migration drift. Tests: `test_team_daily_status_contract.py`, `test_profile_team_scope.py`, `coach-app/src/utils/__tests__/teamDailyStatus.test.js`. |
| WHOOP RLS Lockdown + LLM Enrichment Recovery | Security hotfix + LLM regression fix | 04-30 | Two prod-impacting issues caught by Supabase advisor + `daily_entries.plan_generated.source_reason` telemetry, fixed in one pass. **Security**: `whoop_tokens` / `whoop_daily` / `whoop_pending_auth` had full CRUD grants for `anon` + `authenticated` and no RLS — `access_token` and `refresh_token` were readable (and writable/deletable) via the project anon key. Migration `010_whoop_rls_lockdown.sql` revokes those grants, enables + forces RLS, and adds explicit `service_role full access` policies. Anon SELECT now returns `permission denied`; advisor `rls_disabled_in_public` and `sensitive_columns_exposed` lints clear for these tables. **LLM regression**: source_reason on `python_fallback` rows showed 23/25 timed out at exactly `20s`, with the research injection pinning at `12014` chars on every call (44/44 plan_gen rows in `research_load_log`). `LLM_REVIEW_TIMEOUT` raised 20s→45s (still inside mini-app's ~60s fetch ceiling); `resolve_research(..., max_chars=4000)` cuts injection ~3× without losing critical-priority docs (resolver budget logic preserves criticals first). **Observability**: `compute_plan_health_rolling(days=7)` in `health_monitor.py` smooths the per-day enrichment ratio (1-3 check-ins/day was too sparse to detect drift); wired into `format_digest_message` with thresholds at 60%/40% so the next regression class surfaces in the existing 9am digest. All 323 tests pass. Action item logged: rotate the two pitchers' WHOOP refresh tokens (existing tokens must be considered compromised). Issue #2 (energy capture defaulting to 3) deferred — separate ticket. |
| Public Schema Lockdown + Function search_path | Security follow-up to 010 | 04-30 | Generalized the WHOOP lockdown pattern to every remaining `public` table that PostgREST exposes. Pre-state: 13 tables (`teams`, `coaches`, `team_games`, `block_library`, `coach_actions`, `team_assigned_blocks`, `coach_suggestions`, `training_phase_blocks`, `research_load_log`, `ui_fallback_log`, `schedule`, `training_programs`, `program_templates`) all granted full CRUD to anon + authenticated and ran with RLS disabled — the anon key could enumerate coach emails/Supabase user IDs, read coaching-action audit logs, and overwrite team rosters. Migration `012_public_tables_rls_lockdown.sql` revokes the grants, force-enables RLS, and installs explicit `service_role full access` policies (DO-block + array of table names so adding a future table to the list is one-line). Migration `011_pin_function_search_path.sql` pins `search_path = public, pg_temp` on `update_updated_at_column`, `update_updated_at`, and `set_daily_entry_team_id_from_pitcher`, closing the three `function_search_path_mutable` advisor warnings. Migration `009_daily_entries_team_id_sync.sql` (which had been applied via the dashboard SQL editor on 04-30 but never recorded in `supabase_migrations.schema_migrations`) was reconciled by re-running through `apply_migration` — every statement is idempotent so the re-run was a no-op data-wise but registered the history row, making the trigger visible to `supabase db pull`. **Result**: 0 `rls_disabled_in_public` ERRORs and 0 `function_search_path_mutable` WARNs left. Remaining advisor noise is 11 `rls_policy_always_true` WARNs (pre-existing tables that have RLS enabled but with `USING (true)` policies — separate cleanup, low risk because no anon path reaches them) and the dashboard-toggleable `auth_leaked_password_protection` WARN. Browser-side `supabase-js` use is auth-only (`auth` schema, not `public`) — confirmed in `coach-app/src/hooks/useCoachAuth.jsx`; mini-app doesn't use supabase-js at all. |
| System Guardian V1 (PRs #15-#21) | Self-monitoring observability + admin surface | 05-13 | Full V1 build across six sequenced PRs. **#15 amendments doc** (`docs/superpowers/plans/2026-05-09-system-guardian-amendments.md`) — the build contract: 15 decisions (D1-D15), 7 amendments (A1-A7), 11 V1 acceptance criteria. **#16 migration `019_system_guardian_tables.sql`** — three RLS-locked tables (`system_observations`, `system_incidents`, `guardian_reviews`) following the 010/012 idiom + `prune_old_observations()` SQL fn (14d retention, `search_path` pinned per 011 pattern) + indexes on `observed_at DESC`, `signature`, `(status, last_seen DESC)`. **#17 `bot/services/system_guardian/` Python package** — `normalize.py` (A4 dual-pass write+read-time secret redactor: JWT, Telegram bot tokens, Supabase `sbp_*`/`sbs_*`, OAuth bearer, generic `api_key`/`secret`/`password`), `classify.py` (severity classification per §9), `cluster.py` (signature generation per §13 — strips UUIDs/timestamps/large ints before SHA-1+base32, 64-char cap), `incidents.py` (upsert with severity escalation, `last_notified_at` advances only on status change or severity escalation per A6 — NEVER count increment), `debug_packet.py` (§12 JSON contract, athlete context per D5, `git log` shelled out per D10/D14, NO file artifacts per A7), `store.py` (Supabase CRUD), + 3am `guardian_prune_observations` scheduler job per D15. **#18 `existing_health` collector** — wraps `compute_daily_digest()` + `compute_plan_health_rolling()` per D13; 9am admin digest now ends with `🛡️ Guardian:` summary section (severity-ordered, signature-clustered, read-time redacted). D13 plan-enrichment-health observation has explicit `signature=plan_enrichment_health` so a digest schema change cannot mask the LLM regression class. **#19 `app_health` + `supabase_app` collectors** — in-process FastAPI probe via `httpx.AsyncClient(transport=httpx.ASGITransport(app=api_app))` (no loopback hop) + Phase 1 telemetry queries against `daily_entries`/`research_load_log`/`ui_fallback_log`/`whoop_daily`. `supabase_mgmt` (Phase 2) is explicitly NOT this PR. **#20 admin surface + Telegram notifier** — `notify.py` implements A6's 5 dedup rules; 24h shakedown window persists via sentinel-row in `system_observations` (signature `guardian_shakedown_state`) — no new migration; auto-arms on first observation insert ever, auto-expires after 24h, manually re-armable; `admin_router.py` mounts 8 routes under `/admin/guardian/*` gated by `X-Guardian-Admin-Token` shared-secret header vs `GUARDIAN_ADMIN_TOKEN` env (unset → 503, wrong/missing → 401); hourly `check_shakedown_expiry` scheduler job; `insert_observation_with_notify` async wrapper that callers use when they want notification (sync `insert_observation` stays for write-only paths like the prune self-obs). **#21 A1 runtime contract enforcement** — `run_guardian_tick()` orchestrator with 30s wallclock budget via `asyncio.wait_for` AROUND `asyncio.gather(..., return_exceptions=True)`, 5s per-collector ceiling as belt-and-suspenders, process-local consecutive-over-budget counter (1st over-budget → info, 2nd → warning per A1's "twice in a row", 5th → critical), 15-min `guardian_tick` scheduler job (first run 5 min after startup), `POST /admin/guardian/tick` manual trigger. **Tests:** 222 Guardian tests, 556 in full suite. **Env var:** new `GUARDIAN_ADMIN_TOKEN` (required for admin routes, 503 otherwise). **Deferred:** Phase 2 (Railway + Supabase mgmt collectors, needs `RAILWAY_TOKEN` + `SUPABASE_ACCESS_TOKEN`), Phase 3 (vision drift, blocked on `PRODUCT_VISION_DRAFT.md` + `PRODUCT_BUILD_PLAN.md`). |

### What's Next
1. **Coach-app Phase 1 surfacing** — Category scores (tissue/load/recovery) are computed and persisted but not yet displayed. PlayerSlideOver Today tab needs a 3-stat row; flagged-feed copy should cite the driving category. No engine change; purely frontend read-through.
2. **Baselines backfill / cold-start UX** — Pitchers without a baseline snapshot silently fall through to the legacy flat-trigger path. Decide: auto-seed a baseline after N check-ins vs. require coach to trigger, and how to indicate this in the coach UI.
3. **Tier 2 hardening** — Continuation of the Tier 1 sprint (not yet scoped — open question).
4. **The Ledger** — Modification history timeline on Profile. Data exists in `plan_generated.modifications_applied` + `pitcher_training_model.recent_swap_history`.
5. **Weight logging UI** — `working_weights` column exists, no UI. Unblocks exercise progression curves.
6. **Exercise progression curves** — Volume/intensity trends for key lifts over time. Blocked on weight logging.
7. **Inline coach panel** — Coach button on lifting block for in-context refinement without navigating to Coach tab.
8. **Persist `day_focus` in `plan_generated`** — Today it's derived at read time in `team_daily_status.py`. Moving the write into `plan_generator.py` removes a derivation hop and makes the field authoritative.
9. **Regression #2** — Telegram `getUpdates` conflict (infra).
10. **Guardian Phase 2 — Railway + Supabase mgmt collectors** — Pulls Railway service logs/metrics (new env var `RAILWAY_TOKEN`, pinned GraphQL query, kill switch via token absence) and Supabase Management API advisor lints / RLS posture / migration drift (new env vars `SUPABASE_ACCESS_TOKEN` + `SUPABASE_PROJECT_REF`). Slot into the existing `run_guardian_tick()` orchestrator as two more collectors; both feature-flagged so unset env vars short-circuit.
11. **Guardian Phase 3 — Vision drift rules** — File-anchored hooks + structural AST fallback (A5) for the 10 §11 principles in the original spec. **Blocked on D11**: owner to write `PRODUCT_VISION_DRAFT.md` and `PRODUCT_BUILD_PLAN.md` first. Examples of structural rules: "plan path missing `source_reason`", "new public table without RLS", "deterministic constraint logic leaking into LLM prompts".
12. **Guardian Phase 4 — Debug packet dispatch** — Per A7, packets must NOT be written to `docs/guardian/incidents/`. Surfaces: Telegram admin DM (already wired via `notify.py`), `/admin/guardian/incidents/{id}/debug-packet` JSON (already wired), and redacted GitHub issue body (`--redact-pii` flag, athlete IDs stripped) — the GitHub issue path is the one outstanding item.

## Stack

| Layer | Tech | Where |
|-------|------|-------|
| Bot | Python 3.11 / python-telegram-bot v20+ / APScheduler | Railway (long-polling) |
| API | FastAPI / Uvicorn | Railway (same service, Procfile) |
| LLM | DeepSeek (OpenAI-compatible wrapper) | DeepSeek API |
| Mini App | React 18 / Vite / Tailwind CSS | Vercel |
| Coach App | React 18 / Vite / Tailwind CSS / Supabase Auth | Vercel (separate project) |
| Data | Supabase (Postgres) | Supabase |

**Deployment URLs:**
- API: `https://baseball-production-9d28.up.railway.app`
- Mini App: Vercel (configured in `mini-app/.env.production`)
- Coach App: `baseball-self.vercel.app`
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
│   │   ├── post_outing.py        # /outing ConversationHandler
│   │   └── qa.py                 # Free-text Q&A with dual LLM routing
│   ├── services/
│   │   ├── db.py                 # Supabase client, all CRUD operations
│   │   ├── context_manager.py    # Profile/log/context CRUD — Supabase-backed
│   │   ├── checkin_service.py    # Check-in → triage → plan generation pipeline
│   │   ├── outing_service.py     # Outing → recovery protocol pipeline
│   │   ├── triage.py             # Rule-based readiness triage (green/yellow/red)
│   │   ├── triage_llm.py         # LLM refinement for ambiguous triage
│   │   ├── exercise_pool.py      # Dynamic exercise selection, explosive block, phase emphasis hook
│   │   ├── exercise_alternatives.py # Alternatives for inline swaps
│   │   ├── plan_generator.py     # Two-pass plan gen + team block/start-date hooks
│   │   ├── weekly_model.py       # Next-day suggestions, weekly state management
│   │   ├── game_scraper.py       # Game day detection, reliever appearance tracking
│   │   ├── mobility.py           # 10-week cycling mobility video rotation
│   │   ├── research_resolver.py  # Unified frontmatter-driven research doc routing
│   │   ├── vocabulary.py         # Canonical injury areas + modification tags
│   │   ├── knowledge_retrieval.py # Thin wrappers around resolver
│   │   ├── health_monitor.py     # Daily digest, emergency alerts, Q&A tracking
│   │   ├── team_daily_status.py  # Canonical team daily check-in/plan/work status service
│   │   ├── team_scope.py         # Compatibility wrappers + remaining team-scoped coach helpers
│   │   ├── team_programs.py      # Active team blocks for plan gen, days_until_next_start
│   │   ├── coach_insights.py     # Pre-start nudge generation
│   │   ├── progression.py        # Trends, weekly summaries, season summary
│   │   ├── llm.py                # DeepSeek wrapper (call_llm + call_llm_reasoning)
│   │   ├── web_research.py       # Tavily API fallback for Q&A
│   │   └── system_guardian/      # Self-monitoring observability (Guardian V1)
│   │       ├── __init__.py       # Public API: run_guardian_tick, run_observation_prune, insert_observation*, check_shakedown_expiry
│   │       ├── normalize.py      # A4 dual-pass redactor (JWT, Telegram, Supabase, OAuth, generic) + observation normalization
│   │       ├── classify.py       # Severity classification (critical/warning/info) per spec §9
│   │       ├── cluster.py        # generate_signature() — strips volatile parts → SHA-1+base32, 64-char cap
│   │       ├── incidents.py      # Upsert + status transitions, A6 last_notified_at semantics
│   │       ├── debug_packet.py   # §12 JSON contract; git log shelled out per D14; NO file artifacts (A7)
│   │       ├── store.py          # Supabase CRUD + shakedown sentinel-row helpers + insert_observation_with_notify
│   │       ├── notify.py         # Telegram dispatcher with A6 dedup + shakedown summary
│   │       ├── tick.py           # A1 orchestrator — 30s budget, asyncio.gather, consecutive-over-budget counter
│   │       ├── admin_router.py   # /admin/guardian/* FastAPI routes (X-Guardian-Admin-Token header auth)
│   │       └── collectors/
│   │           ├── existing_health.py  # Wraps compute_daily_digest() + compute_plan_health_rolling() (D13)
│   │           ├── app_health.py       # In-process FastAPI probe via ASGITransport
│   │           └── supabase_app.py     # Phase 1 telemetry queries (daily_entries/research_load_log/ui_fallback_log/whoop_daily)
│   └── prompts/                  # LLM prompt templates (.md)
│
├── api/                          # FastAPI sidecar
│   ├── main.py                   # App, CORS (mini-app + coach-app origins), health check, mounts coach_routes + /admin/guardian
│   ├── auth.py                   # Telegram initData HMAC validation
│   ├── coach_auth.py             # Supabase JWT validation for coach dashboard
│   ├── coach_routes.py           # 30 /api/coach/* endpoints
│   └── routes.py                 # 25+ pitcher-facing endpoints
│
├── mini-app/                     # React Telegram Mini App (pitcher-facing)
│   ├── src/
│   │   ├── App.jsx / Layout.jsx  # Router, auth context, TelegramWebApp init
│   │   ├── hooks/                # useApi, usePitcher, useTelegram, useChatState
│   │   ├── components/           # DailyCard, ExerciseSwap, MutationPreview, etc. (20+)
│   │   └── pages/                # Home, Coach, Plans, PlanDetail, ExerciseLibrary, LogHistory, Profile
│   └── .env.production
│
├── coach-app/                    # React Coach Dashboard (staff-facing)
│   ├── src/
│   │   ├── App.jsx               # Router, AuthProvider, ToastProvider, Sidebar shell + DEV /__design lazy route
│   │   ├── api.js                # fetchCoachApi, postCoachApi, patchCoachApi, deleteCoachApi
│   │   ├── hooks/                # useCoachAuth (Supabase Auth + JWT exchange), useApi
│   │   ├── styles/tokens.css     # Brand tokens — 28 locked (maroon/cream/type scale) + @font-face for Source Serif 4
│   │   ├── components/           # PlayerSlideOver, PlayerToday/Week/History, BlockCard, GamePanel, etc. (legacy + redesigned)
│   │   ├── components/shell/     # Brand shell — Sidebar, TeamBrand, Masthead, Scoreboard, Lede, FlagPill, EditorialState, Toast (+ __tests__)
│   │   ├── components/team-overview/ # Spec 2 — HeroCard, CompactCard, PendingStrip, TeamLede, LastSevenStrip (+ __tests__)
│   │   ├── utils/                # formatToday, todayObjective, teamLede (pure fns, + __tests__)
│   │   ├── pages/                # Login, TeamOverview, Schedule, TeamPrograms, Phases, Insights, DesignSandbox (DEV-only)
│   │   └── test/                 # Vitest bootstrap (sanity.test.js + setup.js)
│   ├── public/fonts/             # Self-hosted Source Serif 4 woff2 (400/600/700/400-italic)
│   └── .env.production
│
├── data/
│   ├── pitchers/                 # Per-pitcher profile.json, context.md (12 active)
│   ├── templates/                # 9 training templates
│   ├── knowledge/                # exercise_library.json (159), mobility_videos.json (21), research/ (14 docs)
│   └── intake_responses.json
│
├── scripts/                      # Seed scripts, migrations, data ops
├── Procfile                      # Railway: web: python -m bot.run
├── railway.toml                  # Build config (nixpacks)
└── requirements.txt
```

## Key Patterns

### Triage → Plan Pipeline (Critical Path)
1. Rule-based triage (`triage.py`) → green/yellow/red + modification tags from `vocabulary.py`
2. Ambiguous cases → LLM refinement (`triage_llm.py`)
3. **Partial entry saved to Supabase BEFORE plan generation** (data persists even if LLM fails)
4. Dynamic warmup from `dynamic_warmup.json` (cuff/scap activation + FPM addon for injury history)
5. Dynamic exercise pool selects 7-8 lifting exercises + 1 explosive from 159-exercise library
6. Tiered post-throw recovery (light/medium/full) based on throwing day type
7. **Python constructs complete plan** (instant) — always succeeds
8. **LLM reviews plan** (async, 20s timeout) — adjusts prescriptions, writes morning brief. Timeout → Python plan ships as-is
9. Full entry upserted, results persist to `pitcher_training_model`
10. `days_since_outing` incremented AFTER first successful check-in (re-check-ins don't double-increment)
11. Weekly state updated in `pitcher_training_model.current_week_state`
12. Plan tagged with `source` (`python_fallback` | `llm_enriched`) + `source_reason` for observability

**Arm feel scale (1-10, migrated from 1-5 on 2026-04-13):** Critical RED ≤2 (shutdown), RED ≤4, YELLOW trigger ≤6, Green ≥7. Energy low trigger ≤4. Avg trend thresholds: <5.0 low, ≥5.0 solid, ≥7.0 strong. Recovery "back to good" ≥7.

### Exercise Selection (`exercise_pool.py`)
- Filters by: day focus, rotation_day_usage, contraindications, modification_flags
- Prefers exercises NOT used in last 7 days
- **Flag-aware session structure**: GREEN → 2 compounds + 3 accessories + 2 core + 1 explosive = 8. YELLOW → minus 1 accessory = 7. RED → light (1 + 2 + 1 + 0 = 4). Check at `exercise_pool.py:172`.
- **Model-aware**: exercise_preferences (dislike → deprioritized), equipment_constraints (hard filter), swap history (3+ swaps → auto-dislike)
- **Phase emphasis hook**: `team_programs.py` can override `training_intent` based on active team phase block
- LLM adjusts prescriptions but CANNOT add exercises outside the pre-selected pool

### DailyCard Rendering — Dual Data Sources (Critical Gotcha)
- Lifting has TWO data sources: `lifting.exercises` (LLM structured plan) and `plan_generated.exercise_blocks` (Python fallback)
- `exercise_blocks` has `block_name` on parent objects — individual exercises do NOT have a `block` field
- `lifting.exercises` has flat exercises with optional `superset_group`
- Block stratification must read from `exercise_blocks` for sub-headers, NOT from individual exercise fields
- Props thread: DailyCard → ExerciseBlock → SupersetList → ExerciseItem — missing a prop silently fails
- Swap overrides: `entry` prop is immutable — use local `swapOverrides` state map

### Swap / Mutation Dual-Write (Critical Gotcha)
- `daily_entries` has **two places** lifting lives: top-level `lifting` column (written by `checkin_service`) AND nested `plan_generated.lifting` (written by `apply_mutations`)
- `swap_exercise` and `apply_mutations` search top-level `entry.lifting.exercises` FIRST, then `plan_generated.lifting.exercises`, then non-arm-care `plan_generated.exercise_blocks[*].exercises`
- `apply_mutations` writes the final lifting list back to BOTH `entry.lifting` and `plan_generated.lifting`, and updates matching `plan_generated.exercise_blocks` exercises in place so block labels/structure are preserved
- `swap` / `modify` / `remove` missing targets fail loudly with 404; mutation preview uses the same helper on a deep copy and must not call `upsert_daily_entry` or `upsert_training_model`
- Coach mutation preview lives at `POST /api/coach/pitcher/{pitcher_id}/preview-mutations`, uses `require_coach_auth`, verifies `pitcher.team_id`, and shares the pitcher preview dry-run logic
- Frontend reads: `lifting: entry.lifting || plan_generated?.lifting` — top-level first

### Two-Pass Plan Generation
- Pass 1 (Python) builds `python_plan` — `training_intent`, `day_focus` MUST be defined before the try/except around `build_exercise_pool()`, not inside it
- `active_modifications` is TEXT[] in `pitcher_training_model`. PostgREST handles list↔TEXT[] conversion
- Both timeout and parse-failure paths must have all fields `checkin_service.py` expects
- **`morning_brief` can be string OR dict** — always coerce to string before using in messages. Coercion duplicated in 4 places (tech debt)
- `generate_plan()` returns `python_plan` on any LLM failure — new plan fields must be added to BOTH paths

### Research Resolver (`bot/services/research_resolver.py`)
- **Single door for all surfaces** — `resolve_research(profile, context, triage, user_message, max_chars)`. Context: `plan_gen`, `coach_chat`, `morning`, `daily_plan_why`.
- Each research doc in `data/knowledge/research/` has YAML frontmatter: `id`, `applies_to`, `triggers`, `priority`, `contexts`
- Four-step selection: (1) critical + injury area match, (2) triage mod trigger intersection, (3) keyword match (coach_chat), (4) standard docs for remaining budget
- `should_fire_research()` gates all surfaces: non-green flag OR active modifications OR injury keyword in message
- Logs every call to `research_load_log` table

### Vocabulary (`bot/services/vocabulary.py`)
- `INJURY_AREAS` (8) and `MODIFICATION_TAGS` (14) — single source of truth
- Consumed by: triage (emits tag keys), exercise_pool, research_resolver, plan_generator (`get_mod_description`)

### Coach Dashboard Auth
- Coach app uses Supabase Auth (email/password) → exchanges Supabase JWT for backend validation
- `coach_auth.py`: `require_coach_auth` dependency extracts `supabase_user_id`, looks up `coaches` row, provides `team_id` scope
- All `/api/coach/*` endpoints are team-scoped — a coach only sees their team's data
- `COACH_APP_URL` must be in Railway CORS origins for auth exchange to work
- **JWT signing**: Supabase issues `ES256` (asymmetric) JWTs on newer projects, `HS256` on legacy. `_decode_token()` inspects `alg` and routes to JWKS (`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`, cached by `PyJWKClient`) or `SUPABASE_JWT_SECRET`. `PyJWT[crypto]` extra is required for ES256 verification.
- **Local dev gotcha:** if coach-app login bounces back to `/login` without error, `VITE_API_URL` likely points at a local FastAPI that doesn't have `coach_routes` mounted. Either run `python -m api.main` from `pitcher_program_app/` (with `.env` populated including `SUPABASE_JWT_SECRET`), or point `VITE_API_URL` at Railway: `https://baseball-production-9d28.up.railway.app`. Supabase issues the JWT fine; the failure is the `/api/coach/auth/exchange` POST returning 404/405, which `useCoachAuth` catches and converts to `coach=null` → redirect to `/login`.

### Team Daily Status Contract
- **Canonical service:** `bot/services/team_daily_status.py`. Do not re-derive team check-in semantics in routes or React.
- **Check-in status:** `checked_in` means `daily_entries.pre_training.arm_feel is not null`. Do **not** use `plan_generated`, `completed_exercises`, or workout completion as check-in signals.
- **Plan status:** `generated` when `plan_generated` exists, `pending` when check-in exists but plan is missing, `not_applicable` when no check-in exists.
- **Work status:** separate from check-in; first-pass statuses are `not_started`, `in_progress`, `completed`, `unknown`.
- **Date convention:** team daily status defaults to `datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d")`.
- **Team scoping:** team reads must filter `daily_entries` by `team_id`; check-in writes inherit `team_id` in `db.upsert_daily_entry()` and DB trigger `daily_entries_set_team_id` should remain applied.
- **Frontend naming:** coach-app helper `src/utils/teamDailyStatus.js` prefers `checkin_status`, with legacy `today_status` / `checked_in` fallback. Mini-app `StaffPulse` does the same.
- **Staff pulse:** use `GET https://baseball-production-9d28.up.railway.app/api/staff/pulse?team_id=uchicago_baseball`; old unscoped calls still default to UChicago.
- **Supabase schema drift guard:** explicit status-service selects should stay on stable `daily_entries` columns only. Do not add optional/newer columns such as top-level `arm_feel`, `rationale`, `arm_care`, or `mobility` unless the migration is guaranteed in production and tests cover the select list.

### Coach Dashboard Brand Shell (Spec 1 — 2026-04-19)
- **Tokens live in one place:** `coach-app/src/styles/tokens.css` declares all colors, type sizes, and font families inside a `@theme` block. Tailwind v4 auto-generates utilities (`bg-maroon`, `text-charcoal`, `text-display`, `font-serif`, etc.) from those keys — do NOT hardcode hex values in components.
- **Brand vs alert separation is load-bearing:** `--color-maroon*` / `--color-rose` are brand chrome only; `--color-crimson` / `--color-amber` / `--color-forest` are flag/alert only. Crossing the two breaks the system — if you need a red that isn't a flag, push back.
- **Shared components:** `components/shell/` holds `Sidebar`, `TeamBrand`, `Masthead`, `Scoreboard`, `Lede`, `FlagPill`, `EditorialState`, `Toast`. Every page sits inside `<main>` with a top `<Masthead kicker title date [week] [actionSlot] />`. Scoreboard requires EXACTLY 5 cells (throws otherwise).
- **Contract test:** `components/shell/__tests__/tokens.test.jsx` asserts every brand token name still exists. Run `npm run test:run -- tokens` before touching `tokens.css`.
- **Dev-only sandbox:** `/__design` renders every shell component + runs axe-core. Route is gated by `import.meta.env.DEV` AND `DesignSandbox` is `React.lazy()`-imported so production tree-shakes it. Visit locally in dev mode to smoke-test a11y after shell changes.
- **Toast API:** `useToast()` returns `{ success, warn, error, info }`, each `(msg, ttl?)`. Tone-aware border + bone fill (`shell/Toast.jsx`).
- **Deferred for Specs 2–3:** Page bodies still use legacy layouts (roster cards, grid tables). Spec 2 replaces Team Overview first, anchored by a real `<Scoreboard>`.

### Check-in Flow
- Two paths: Telegram (`daily_checkin.py` → `process_checkin`) and mini-app (`/chat` → `process_checkin`). Mini-app fetch dies at ~60s.
- Morning notification arm feel buttons (1-5) are ConversationHandler entry points → full check-in flow
- `hasCheckedIn` means submitted check-in input exists (`pre_training.arm_feel`), even if plan generation is still pending
- Response assembly in `/chat` path is independently try/except-wrapped

### Template Selection (Lift Preference)
- **Explicit preference always wins**: "upper" → day_3, "lower" → day_2, "rest" → day_6
- **"Your call" / "auto" / empty**: falls back to rotation-based (`days_since_outing` → template day)

### System Guardian (V1 — PRs #15-#21)
- **Canonical package:** `bot/services/system_guardian/`. Do not re-derive observability semantics elsewhere — both `health_monitor.py`'s 9am digest path and any future admin tooling go through this package.
- **Three new tables:** `system_observations` (every observation, 14d retention via `prune_old_observations()`), `system_incidents` (clustered by `signature` UNIQUE, count/severity escalation, `last_notified_at`), `guardian_reviews` (audit row written on every `update_incident_status` call). All three run RLS-locked under `service_role` only — matches the 010/012 idiom.
- **Three new scheduled jobs** (registered in `bot/main.py`):
  - `guardian_prune_observations` — 3am Chicago, calls `prune_old_observations()` SQL fn, emits a `guardian_self` self-observation with rows-pruned count.
  - `guardian_shakedown_check` — hourly, calls `check_shakedown_expiry()`. Auto-fires the end-of-window summary DM and flips the shakedown flag if 24h elapsed.
  - `guardian_tick` — every 15 minutes (first run 5 min after startup), fans out three Phase 1 collectors in parallel under a 30s wallclock budget.
- **A4 dual-pass secret redaction** in `normalize.py`: write-time regex (JWT, Telegram bot token, Supabase `sbp_*`/`sbs_*`, OAuth bearer, generic `api_key`/`secret`/`password`) runs INSIDE `insert_observation` so secrets never hit Supabase; read-time fallback (`redact_observation_for_emit`) wraps `title`/`message`/`stack`/`sample_messages` on every digest/packet/API emit. Synthetic-JWT end-to-end test locked into the contract.
- **A6 notification dedup rules** in `notify.py`:
  1. Shakedown active → suppress.
  2. First occurrence of a signature → DM + advance `last_notified_at`.
  3. Severity escalation on existing incident → DM + advance.
  4. Status transition (open→resolved→open re-open) → DM.
  5. Otherwise (count++ at same severity) → SILENT. The most common mistake is to notify on count alone — DO NOT.
- **24h shakedown window** persisted via SENTINEL ROW in `system_observations` (signature `guardian_shakedown_state`, `category=guardian_self`, `details.active` + `details.started_at`). No new migration. Auto-arms on the FIRST-ever observation insert when no sentinel exists; auto-expires after 24h; manually re-armable via `POST /admin/guardian/shakedown/rearm` for major deploys. When you see `category=guardian_self` rows in production, that's the audit trail — not anomalies.
- **`insert_observation` (sync, no-notify) vs `insert_observation_with_notify` (async, notifies)**: the prune job's self-observation uses the sync no-notify path (heartbeats should never DM); the 9am digest's Guardian-observation persistence loop and `POST /admin/guardian/collect-now` use the async-with-notify path. Pick the right one when adding a new caller.
- **D13 `plan_enrichment_health` signature is explicit** — `existing_health.py` sets the signature string LITERALLY rather than letting `generate_signature` derive it. A digest schema change cannot accidentally rehash this into a different bucket. This is the canary for the late-April LLM regression class.
- **A1 runtime contract** in `tick.py`: 30s wallclock budget via `asyncio.wait_for` AROUND `asyncio.gather(..., return_exceptions=True)` — this is the only way to bound true wallclock total. Per-collector 5s ceilings are belt-and-suspenders inside `_run_one_collector_bounded`. Consecutive-over-budget counter: 1st over-budget tick → severity=info, 2nd consecutive → warning (A1's "twice in a row"), 5th → critical. Counter resets on any under-budget tick. Counter is process-local — restart resets to 0 by design.
- **Admin surface** under `/admin/guardian/*` (8 routes), gated by `X-Guardian-Admin-Token` shared-secret header vs `GUARDIAN_ADMIN_TOKEN` env var. **Unset env → 503** (deliberate, surfaces misconfigured deploys); wrong/missing header → 401. NOT reused: coach-app Supabase JWT (pitcher-scoped, wrong surface) or the Telegram bot token (different concern). Routes: `GET /`, `GET /incidents`, `GET /incidents/{id}`, `GET /incidents/{id}/debug-packet`, `POST /incidents/{id}/status`, `POST /shakedown/ack`, `POST /shakedown/rearm`, `POST /collect-now`, `POST /tick`.
- **A7 debug packet artifact policy:** packets are JSON return values from `debug_packet.build_debug_packet(incident)` only. Surfaces: Telegram admin DM (notify.py), `/admin/guardian/incidents/{id}/debug-packet` JSON response. NEVER written to `docs/guardian/incidents/` or any in-repo path. GitHub issue body export (Phase 4) requires `--redact-pii` flag and is not yet implemented.

### Scheduled Jobs
- Morning check-in at pitcher's `notification_time`
- 6pm follow-up if unanswered
- Sunday 6pm weekly narrative + summary
- 6am daily WHOOP pull (sends re-link if auth expired)
- 9am daily health digest to admin (now ends with `🛡️ Guardian:` summary section per PR-3)
- 11pm post-game reliever check
- 3am `guardian_prune_observations` (Guardian self-prune, 14d retention)
- Hourly `guardian_shakedown_check` (auto-expires the 24h shakedown window)
- Every 15 min `guardian_tick` (fans out the three Phase 1 collectors, first run 5 min after startup)

### WHOOP Integration
- Per-pitcher OAuth PKCE, tokens in `whoop_tokens`, daily 6am pull → `whoop_daily`
- Check-in always pulls fresh (`force_refresh=True`); 6am pull may get partial data (`PENDING_SCORE` → re-pull later)
- Feeds into triage (`whoop_hrv`, `whoop_hrv_7day_avg`, `whoop_sleep_perf`), plan gen context, weekly narrative
- All code paths handle `whoop_data=None` — non-WHOOP pitchers unaffected

### Dual LLM Routing
- `call_llm()` — fast model (deepseek-chat, 90s timeout) for Q&A, plan review, weekly narrative
- `call_llm_reasoning()` — reasoning model (deepseek-reasoner, 120s timeout) for multi-day protocols
- `return_metadata=True` surfaces `finish_reason` for truncation detection

### Timezone
All dates use `CHICAGO_TZ` (from `bot/config.py`). Server: `datetime.now(CHICAGO_TZ)`. Client: `toLocaleDateString('en-CA', { timeZone: 'America/Chicago' })`.

### DB Patterns
- `_DAILY_ENTRY_COLUMNS` whitelist in `db.py` strips unknown fields before upsert
- `pitchers` PK is `pitcher_id` (not `id`). FK references must use `REFERENCES pitchers(pitcher_id)`
- `pitcher_training_model` consolidates old `active_flags` + exercise intelligence. `profile["active_flags"]` populated via compat layer in `_profile_from_row()`
- `daily_entries.pre_training` JSONB uses key `overall_energy` (NOT `energy`) — matters for any SQL migration touching energy values
- `daily_entries.pre_training` is JSONB, not separate visible columns in Supabase table view. Verify arm feel with `pre_training->>'arm_feel'`.

### Exercise library workflow (2026-04-18)
- **Supabase `exercises` is canonical** at runtime. `/api/exercises`, plan gen, swap, and mutations all read live from Supabase via `exercise_pool` (15-min snapshot cache + lazy-miss).
- **JSON is seed-only.** `data/knowledge/exercise_library.json` is the source of truth in git for review/history. A pre-commit hook (`scripts/hooks/pre-commit`) runs `scripts/seed_exercises_from_json.py` on every commit that touches the JSON. Upsert-only — never deletes.
- **Hook install:** one-time `ln -sf ../../pitcher_program_app/scripts/hooks/pre-commit .git/hooks/pre-commit` from repo root.
- **Hook failure:** warns + proceeds (D11). Manual re-run: `cd pitcher_program_app && python -m scripts.seed_exercises_from_json`.
- **Removing an exercise:** delete from JSON for new plans, but historical `plan_generated` rows still reference it — orphans in Supabase are tolerated (D12).

### Chart.js Axis Gotcha
With explicit `min`/`max` + `stepSize`, Chart.js silently adds `max` as an extra tick when `max` isn't on the stepSize grid (produces spurious labels like "11/10"). For dot headroom at y=max, use chart-level `clip: false` + `layout.padding.top` — do NOT inflate `max` to create space. Example in `SeasonTimeline.jsx` and `SleepScatter.jsx`.

### Handler Registration
`register_handlers(application)` in `bot/main.py` is the **single source of truth** for all bot handlers. Both `main.py` (local) and `run.py` (Railway) call it. **Add new commands here only.**

## Current Pitchers

| ID | Name | Role | Notes |
|----|------|------|-------|
| landon_brice | Landon Brice | Starter (7-day) | Primary user/developer |
| pitcher_benner_001 | Preston Benner | Starter (7-day) | LHP, UCL sprain history (PRP) |
| pitcher_hartrick_001 | Wade Hartrick | Reliever (short) | Flexor/pronator strain history |
| pitcher_heron_001 | Carter Heron | Reliever (long) | YELLOW — TJ + olecranon, 1yr post-op |
| pitcher_kamat_001 | Taran Kamat | Reliever (short) | Shoulder impingement/GIRD (95%, recurs), whoop |
| pitcher_kwinter_001 | Russell Kwinter | Starter (7-day) | LHP, partial UCL tear (2023), low back, whoop |
| pitcher_lazar_001 | Jonathan Lazar | Reliever (short) | Labrum surgery (~3yr ago), beginner lifter |
| pitcher_reed_001 | Lucien Reed | Reliever (short) | Recurring ulnar nerve impingement |
| pitcher_richert_001 | Matthew Richert | Reliever (long) | UCL strain (2024), scap/shoulder soreness, whoop |
| pitcher_sosna_001 | Mike Sosna | Reliever (short) | Active oblique strain, forearm tightness, very strong |
| pitcher_wilson_001 | Wilson | Reliever (short) | YELLOW — active ulnar nerve symptoms |
| test_pitcher_001 | Test Pitcher | Starter (7-day) | Test account |

## Supabase Schema

Project: `pitcher-training-intel` (us-east-1)

| Table | Purpose |
|-------|---------|
| `pitchers` | Profiles — id, name, role, physical/pitching/training JSONB fields |
| `injury_history` | Per-pitcher injury records with severity, area, flag_level |
| `pitcher_training_model` | Consolidated state — flags, modifications, exercise prefs, equipment, swap history, weekly arc |
| `daily_entries` | Daily logs — pre_training, plan_generated, lifting, completed_exercises, warmup, research_sources |
| `exercises` | Library (159) — prescription, tags, contraindications, youtube_url |
| `templates` | Training templates (9) — rotation day structure |
| `saved_plans` | Pitcher-specific saved/generated plans |
| `chat_messages` | Cross-platform conversation persistence |
| `weekly_summaries` | Aggregated weekly data + LLM narrative |
| `whoop_tokens` | Per-pitcher WHOOP OAuth tokens |
| `whoop_daily` | Daily biometrics — recovery, HRV, sleep, strain |
| `mobility_videos` | 21 follow-along mobility videos |
| `mobility_weekly_rotation` | 10-week rotation schedule |
| `research_load_log` | Observability for research resolver calls |
| `teams` | Team identity — name, level, training_phase, timezone |
| `coaches` | Coach accounts — Supabase Auth user link, team_id scoped |
| `team_games` | Game schedule — date, opponent, starter assignment |
| `block_library` | Throwing program templates (velocity_12wk, longtoss_6wk, etc.) |
| `team_assigned_blocks` | Active team programs — links block_library to team with dates |
| `coach_suggestions` | AI-generated insights — pre_start_nudge, accept/dismiss workflow |
| `training_phase_blocks` | Off-season phase timeline — GPP, Strength, Power, Preseason, In-Season |
| `system_observations` | Guardian — every observation persisted before clustering. 14d retention via `prune_old_observations()`. Includes the `guardian_shakedown_state` sentinel row that tracks the 24h shakedown window. |
| `system_incidents` | Guardian — clustered incidents keyed by `signature` (UNIQUE). Severity escalates but never de-escalates; `last_notified_at` advances only on status change or severity escalation. |
| `guardian_reviews` | Guardian — audit log written by `update_incident_status`. `ON DELETE CASCADE` to `system_incidents.id`. |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| TELEGRAM_BOT_TOKEN | yes | — | From @BotFather |
| DEEPSEEK_API_KEY | yes | — | DeepSeek API key |
| SUPABASE_URL | yes | — | Supabase project URL |
| SUPABASE_SERVICE_KEY | yes | — | Supabase service role key |
| SUPABASE_JWT_SECRET | yes | — | For coach dashboard JWT validation |
| MINI_APP_URL | no | — | Vercel mini-app URL |
| COACH_APP_URL | no | — | Vercel coach-app URL (must match exactly for CORS) |
| WHOOP_CLIENT_ID | yes (WHOOP) | — | WHOOP developer portal |
| WHOOP_CLIENT_SECRET | yes (WHOOP) | — | WHOOP developer portal |
| TAVILY_API_KEY | no | — | Web research fallback |
| PORT | no | 8000 | API port |
| DISABLE_AUTH | no | false | Skip HMAC auth (dev only) |
| ADMIN_TELEGRAM_CHAT_ID | no | 8589499360 | Admin chat for health monitoring DMs + Guardian notifications |
| GUARDIAN_ADMIN_TOKEN | yes (admin routes) | — | Shared-secret header (`X-Guardian-Admin-Token`) for `/admin/guardian/*`. Unset → routes return 503. Generate with `openssl rand -hex 32`. |

## Deployment

### Architecture
```
GitHub (landonbrice/baseball)
  └─ pitcher_program_app/
       ├─ bot/ + api/              ← Python backend (Railway)
       ├─ mini-app/                ← Pitcher frontend (Vercel)
       ├─ coach-app/               ← Coach dashboard (Vercel, separate project)
       └─ data/                    ← JSON (read-only, Supabase is primary)
```

### Railway (Bot + API)
- Single process: `Procfile: web: python -m bot.run`
- Root directory: `pitcher_program_app`
- Auto-deploy on push to `main`

### Vercel (Mini App)
- Root: `pitcher_program_app/mini-app`, Vite, `npm run build` → `dist/`
- Env: `VITE_API_URL=https://baseball-production-9d28.up.railway.app`

### Vercel (Coach App)
- Root: `pitcher_program_app/coach-app`, Vite
- URL: `baseball-self.vercel.app`
- Env: `VITE_API_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`
- **CORS**: `COACH_APP_URL` in Railway must match exactly (no trailing slash)

### Supabase
- Project: `pitcher-training-intel` (us-east-1)
- URL: `https://beyolhukpbvvoxvjnwtd.supabase.co`
- FK pattern: `pitchers` PK is `pitcher_id` (not `id`)
- **MCP is HTTP-based** (`.mcp.json` → `https://mcp.supabase.com/mcp?project_ref=beyolhukpbvvoxvjnwtd`), auths via Supabase OAuth login. **No `SUPABASE_ACCESS_TOKEN` / `SUPABASE_DB_URL` / `SUPABASE_PROJECT_REF` env vars needed** — and intentionally not set locally. Project ref is `beyolhukpbvvoxvjnwtd`.
- **No local `.env`** — only `.env.example`. Runtime secrets live in Railway/Vercel; SQL ops go through MCP. Minimizes secrets-on-disk surface (cf. WHOOP token incident in Known Issues).
- **Capabilities deferred** (add only when needed): Supabase CLI scripting / CI migrations (needs PAT), `psql` + `pg_dump` + GUI clients + multi-statement TX (needs `DB_URL`). All `010`/`011`/`012` lockdown migrations ran fine via `apply_migration` MCP — no DB URL required for current ops surface. **Note:** Guardian Phase 2 (What's Next #10) plans to add `SUPABASE_ACCESS_TOKEN` + `SUPABASE_PROJECT_REF` for a Management API collector (advisor lints / RLS posture) — that's a *different* use case from CLI/psql, and the same PAT can serve both if/when added. `DB_URL` is not on any roadmap.

### Deploy Checklist
1. Push to `main` → Railway + Vercel auto-deploy
2. New Supabase tables/columns → apply migration first via MCP or dashboard
3. New env vars → update in Railway/Vercel dashboards
4. Verify: bot `/checkin`, API health, mini-app loads in Telegram

### Data Safety
- **Supabase is source of truth.** JSON files are read-only fallback.
- **JSONB guard pattern:** `(x.get("field") or {}).get()` in Python, `Array.isArray()`/`typeof` in React.

### Running Locally
```bash
cd pitcher_program_app
pip install -r requirements.txt
python -m bot.run           # Bot + API in one process (same as Railway)
cd mini-app && npm run dev  # Mini-app (separate terminal)
cd coach-app && npm run dev # Coach app (separate terminal)
```
No Python virtualenv locally — project runs on Railway. Use Supabase MCP for SQL operations.

## Known Issues & Tech Debt

- **WHOOP token rotation pending (post-2026-04-30 lockdown)** — `010_whoop_rls_lockdown.sql` closed the door, but `whoop_tokens.access_token` / `refresh_token` for the linked pitchers (Kamat, Kwinter, Richert per WHOOP-linked roster) were exposed via the anon key for an unknown window. Action: revoke their grants in the WHOOP developer portal and have them re-link via `/whoop`. Optionally rotate the project's anon publishable key in the Supabase dashboard since it's shipped in `mini-app/.env.production` and `coach-app/.env.production` build artifacts.
- **`rls_policy_always_true` WARN cleanup outstanding** — 11 tables (`chat_messages`, `daily_entries`, `exercises`, `injury_history`, `mobility_videos`, `mobility_weekly_rotation`, `pitcher_training_model`, `pitchers`, `saved_plans`, `templates`, `weekly_summaries`) have RLS enabled with permissive `USING (true) WITH CHECK (true)` policies. Practical risk is zero today (anon/authenticated have no path to them now that 010+012 revoked the grants on the rest of the schema), but the moment a second team or a direct browser read appears, this becomes the next WHOOP-class incident. Cleanup pattern: scope each policy to `TO service_role` and drop the unrestricted `USING (true)` for non-service roles. One targeted migration when ready.
- **Orphan tables awaiting drop decision** — `schedule` (31 rows), `training_programs` (12), `program_templates` (4) were superseded by `team_games` / `team_assigned_blocks` / `block_library` on 2026-04-10 but never dropped. Locked down by `012` so they're no longer an attack surface. `pitcher_training_model.active_program_id` still has an FK to `training_programs(id)` — that FK has to drop first if/when the orphan tables go.
- **LLM enrichment depends on a 45s budget** — `LLM_REVIEW_TIMEOUT = 45` in `plan_generator.py` is the live value. If DeepSeek `chat` median latency creeps above ~30s, enrichment quietly fails again. The 9am digest's `7d enrichment` line is the canary — if it drops below 60% for more than two consecutive days, look at DeepSeek-side latency directly, not the timeout. The reasoning-model path (red flag / return-to-throwing) still uses the 120s timeout in `bot/services/llm.py::call_llm_reasoning`.
- **Schema drift in `team_scope.py` / team daily status selects** — `team_scope.py` was realigned 2026-04-14, and 2026-04-30 moved daily status ownership to `team_daily_status.py`. Keep team status selects conservative: selecting missing PostgREST columns causes production 500s. Known production-safe daily status fields: `pitcher_id`, `date`, `team_id`, `pre_training`, `plan_generated`, `completed_exercises`, `warmup`, `lifting`, `throwing`, `plan_narrative`.
- **FastAPI unhandled-exception responses skip CORS middleware** — a 500 from an uncaught exception surfaces as "Origin is not allowed by Access-Control-Allow-Origin" in Safari/Chrome, even though CORS is correctly configured. Always check Railway logs for the real traceback before chasing CORS.
- **Repo bloat from untracked dev artifacts** — `graphify-out/`, `past_arm_programs/*.xlsx`, root-level `scripts/`, `ui-elevation-mockup.jsx` have leaked into commits. Need proper `.gitignore` + `git rm --cached` pass.
- **Historical `overall_energy: 3` in `daily_entries`** (fixed 2026-04-19 for new rows): prior to the checkin-hotfix merge, the `/api/chat` checkin handler never threaded `energy` from the request body to `process_checkin`, so every mini-app check-in stored the parameter default `3`. Historical rows are not backfilled — triage tolerates missing/default values. New rows carry real energy values *only once the Coach.jsx check-in flow captures energy* (UI step spawned as follow-up task 2026-04-19; backend is ready). If doing retrospective analytics on energy, filter `created_at >= <hotfix-deploy-timestamp>` AND after the UI capture step lands.
- `morning_brief` string/dict coercion duplicated in 4 places — should normalize at checkin_service boundary. 2026-04-19 check-in hotfix added a 5th copy (saved-plan subtitle at `api/routes.py:2185`); consolidation into a single `_unwrap_morning_brief(raw) -> str` helper is a clean follow-up.
- `context_manager.py:173` `msg.get("content","")[:200]` — no `str()` coercion, latent TypeError if content is dict
- **`tests/test_coach_chat.py` — 5 pre-existing failures from `python-telegram-bot` version drift.** `AttributeError: type object 'object' has no attribute 'DEFAULT_TYPE'` at `bot/handlers/qa.py:37` (`ContextTypes.DEFAULT_TYPE`). Only surfaces when that file runs in isolation; the full pytest suite ordering incidentally repairs it. Not introduced by the Guardian PRs — verified against clean `main` pre-Guardian. Likely root cause: the file installs a `types.ModuleType` shim for `telegram` at import time that doesn't export `BotCommand` etc., or `python-telegram-bot` upgraded incompatibly. Surfaced repeatedly across PRs #17-#21 — worth a small dedicated cleanup PR.
- **Guardian admin token must be set in Railway** — `GUARDIAN_ADMIN_TOKEN` (`openssl rand -hex 32`) must be added in Railway env vars before `/admin/guardian/*` routes work. Without it the routes return 503 with a clear "not configured" message (safe-fail). Everything else in Guardian (collectors, prune, digest section, the auto-shakedown window) operates fine without it — only the admin pages and notifier short-circuit.
- **Guardian shakedown sentinel row in production** — Expect to see `category=guardian_self` rows with signature `guardian_shakedown_state` in `system_observations`. That is the deliberate shakedown audit trail, not anomalies. Multiple sentinel rows over time (one per `set_shakedown_active` call) are normal — readers look at the most-recent one.
- **Phase 4 GitHub-issue debug-packet dispatch not implemented** — A7 forbids in-repo paths and requires `--redact-pii`. Current packet surfaces are Telegram DM + `/admin/guardian/incidents/{id}/debug-packet` JSON only. Adding the GitHub issue path is a small follow-up.
- 10 exercises missing YouTube links (ex_121-123, ex_126-128, ex_156-159)
- `_load_exercise_library()` module-level cache — new exercises require Railway redeploy
- Guided flow `manuallyDonePhases` is ephemeral (resets on reload) — v2 deferral
- Dev commands (`/testnotify`, `/whooptest`, `/healthdigest`, `/testemergency`) exist — remove before broader rollout
- Reliever template uses text descriptions not exercise IDs — not validated
- `data_sync.py` disabled but still exists — can delete
- **Coach-app redesign carryovers (post-Spec 1 + Spec 2):**
  - `"Chicago · Pitching Staff"` kicker hardcoded in 6 sites — should feed from `coach.team_name` (auth-exchange enrichment is live via Tier 1; wiring in component props is a quick follow-up)
  - `TeamPrograms` Masthead has no `actionSlot` — Spec 3 should wire a real "+ New Program" entry point through the assign modal
  - `Schedule.jsx`, `TeamPrograms.jsx`, `Phases.jsx` still use inline "Loading..." strings instead of `<EditorialState type="loading">` — Spec 2 only rebuilt Team Overview; the other 4 pages wait for their own page-body spec
  - `alert()` / `confirm()` calls in `Phases` + `TeamPrograms` predate Spec 1; now that `useToast` exists they should migrate to `toast.error` / inline confirmation
  - `<Sidebar>` Sign out `<button>` missing `type="button"` (no form context, no functional bug)
  - `useCoachAuth.getAccessToken` isn't `useCallback`-wrapped and the context value isn't `useMemo`-wrapped — causes `useCoachApi.refetch` reference to churn, which re-arms the 90s TeamOverview interval on every AuthProvider re-render. Harmless but inefficient; fix with a context-value memoization pass
  - Spec 2 scoreboard cell 1 ("Check-ins") sub drops the spec's "avg {time}am" — we don't compute check-in timestamps on the overview payload. Logged for Spec 3 polish
  - Spec 2 scoreboard cell 5 ("Next Start") sub shows pitcher name only, not "{name} · vs {opponent}". Requires a second join on `team_games`; defer to Spec 3
  - Spec 2 pending strip `hours_since_last` is always `null` in the frontend partition — no backend field for "hours since last check-in" on not-yet-checked-in pitchers. Spec 3 adds the field
  - Spec 2 PlayerHistory header says "Last 30 days" but `coach_routes.py::coach_pitcher_detail` returns `.limit(10)` — label should say "Last 10 check-ins" OR the query should expand to 30
  - `plan_generator.py` never writes `day_focus` into `plan_generated`; Spec 2's `team_scope.py` derives it at read time. Moving the write upstream would remove the derivation hop

## Bot Scope Boundaries

**Owns:** Lifting programs, arm care, plyocare, recovery, readiness triage, Q&A, longitudinal tracking, program modifications based on injury/biometrics.

**Does NOT own:** Mechanical instruction, medical diagnosis, supplement recommendations. Flags concerns → tells pitcher to see trainer.
