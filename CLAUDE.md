# Pitcher Training Intelligence — Claude Init

> Last updated: 2026-04-18
> Sprint status: Phases 1-20.1 + Sprint 0.5 + Tier 1 Hardening complete. Coach sidebar shows team name, exercise names hydrated at write, canonical morning_brief shape, snapshot cache for exercises. Next: continue Tier 2 or pivot to next sprint.

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

### What's Next
1. **Coach auth-exchange response enrichment** — `/api/coach/auth/exchange` + `/me` return only `coach_id/team_id/coach_name/role`. Shell sidebar falls back to "Dashboard" because `team_name` missing. Join `teams.name` into response.
2. **The Ledger** — Modification history timeline on Profile. Data exists in `plan_generated.modifications_applied` + `pitcher_training_model.recent_swap_history`.
3. **Weight logging UI** — `working_weights` column exists, no UI. Unblocks exercise progression curves.
4. **Exercise progression curves** — Volume/intensity trends for key lifts over time. Blocked on weight logging.
5. **Inline coach panel** — Coach button on lifting block for in-context refinement without navigating to Coach tab.

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
│   │   ├── team_scope.py         # Team-scoped queries for coach dashboard
│   │   ├── team_programs.py      # Active team blocks for plan gen, days_until_next_start
│   │   ├── coach_insights.py     # Pre-start nudge generation
│   │   ├── progression.py        # Trends, weekly summaries, season summary
│   │   ├── llm.py                # DeepSeek wrapper (call_llm + call_llm_reasoning)
│   │   └── web_research.py       # Tavily API fallback for Q&A
│   └── prompts/                  # LLM prompt templates (.md)
│
├── api/                          # FastAPI sidecar
│   ├── main.py                   # App, CORS (mini-app + coach-app origins), health check
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
│   │   ├── App.jsx               # Router, AuthProvider, ToastProvider
│   │   ├── api.js                # fetchCoachApi, postCoachApi, patchCoachApi, deleteCoachApi
│   │   ├── hooks/                # useCoachAuth (Supabase Auth + JWT exchange), useApi
│   │   ├── components/           # Shell, RosterTable, PlayerSlideOver, ComplianceRing, etc. (13)
│   │   └── pages/                # Login, TeamOverview, Schedule, TeamPrograms, Phases, Insights
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
- `swap_exercise` and `apply_mutations` search top-level `entry.lifting.exercises` FIRST, fall back to nested legacy locations, write back BOTH
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

### Check-in Flow
- Two paths: Telegram (`daily_checkin.py` → `process_checkin`) and mini-app (`/chat` → `process_checkin`). Mini-app fetch dies at ~60s.
- Morning notification arm feel buttons (1-5) are ConversationHandler entry points → full check-in flow
- `hasCheckedIn` requires actual plan data, not just `pre_training.arm_feel`
- Response assembly in `/chat` path is independently try/except-wrapped

### Template Selection (Lift Preference)
- **Explicit preference always wins**: "upper" → day_3, "lower" → day_2, "rest" → day_6
- **"Your call" / "auto" / empty**: falls back to rotation-based (`days_since_outing` → template day)

### Scheduled Jobs
- Morning check-in at pitcher's `notification_time`
- 6pm follow-up if unanswered
- Sunday 6pm weekly narrative + summary
- 6am daily WHOOP pull (sends re-link if auth expired)
- 9am daily health digest to admin
- 11pm post-game reliever check

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
| ADMIN_TELEGRAM_CHAT_ID | no | 8589499360 | Admin chat for health monitoring DMs |

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
python -m bot.main          # Bot
python -m api.main          # API (separate terminal)
cd mini-app && npm run dev  # Mini-app (separate terminal)
cd coach-app && npm run dev # Coach app (separate terminal)
```
No Python virtualenv locally — project runs on Railway. Use Supabase MCP for SQL operations.

## Known Issues & Tech Debt

- **Schema drift in `team_scope.py`** — file was written against an older schema (used `physical`/`pitching`/`flag_level`/`injury_history.status`). Realigned 2026-04-14. Follow-up sweep across `bot/services/` + `api/` (2026-04-14) confirmed no other offenders: remaining `flag_level` references are all triage-result dict keys, `daily_entries.pre_training` JSONB keys, or legitimate `injury_history.flag_level` column reads. `physical_profile`/`pitching_profile` already consistent.
- **FastAPI unhandled-exception responses skip CORS middleware** — a 500 from an uncaught exception surfaces as "Origin is not allowed by Access-Control-Allow-Origin" in Safari/Chrome, even though CORS is correctly configured. Always check Railway logs for the real traceback before chasing CORS.
- **Repo bloat from untracked dev artifacts** — `graphify-out/`, `past_arm_programs/*.xlsx`, root-level `scripts/`, `ui-elevation-mockup.jsx` have leaked into commits. Need proper `.gitignore` + `git rm --cached` pass.
- `morning_brief` string/dict coercion duplicated in 4 places — should normalize at checkin_service boundary
- `context_manager.py:173` `msg.get("content","")[:200]` — no `str()` coercion, latent TypeError if content is dict
- 10 exercises missing YouTube links (ex_121-123, ex_126-128, ex_156-159)
- `_load_exercise_library()` module-level cache — new exercises require Railway redeploy
- `/api/staff/pulse` returns 500 intermittently — undiagnosed crash in pitcher loop
- Guided flow `manuallyDonePhases` is ephemeral (resets on reload) — v2 deferral
- Dev commands (`/testnotify`, `/whooptest`, `/healthdigest`, `/testemergency`) exist — remove before broader rollout
- Reliever template uses text descriptions not exercise IDs — not validated
- `data_sync.py` disabled but still exists — can delete

## Bot Scope Boundaries

**Owns:** Lifting programs, arm care, plyocare, recovery, readiness triage, Q&A, longitudinal tracking, program modifications based on injury/biometrics.

**Does NOT own:** Mechanical instruction, medical diagnosis, supplement recommendations. Flags concerns → tells pitcher to see trainer.
