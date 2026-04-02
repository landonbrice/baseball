# Pitcher Training Intelligence — Claude Init

> Last updated: 2026-04-01
> Sprint status: Phases 1-11 complete. WHOOP PKCE fixed, JSON fallback removed. Next: The Ledger, periodization, exercise progression curves.

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

### What's Not Yet Built
1. **The Ledger** — Modification history visualization. Data exists in `plan_generated.modifications_applied`. Needs frontend timeline on Profile.
2. **Periodization** — No multi-week phases (hypertrophy → strength → power). Template repeats identically each week. Exercise pool adds variety but not progressive structure.
3. **Exercise progression curves** — Volume/intensity trends for key lifts over time.
4. **Coach dashboard** — Staff-facing view of team readiness, flags, trends.
5. **Truncated JSON repair** — LLM sometimes returns cut-off JSON. `finish_reason` is surfaced but repair logic not yet built.
6. **Guided day flow** — Sequential phase unlocking in DailyCard (complete warmup → arm care unlocks → lifting → throwing → post-throw). Data structure supports it, frontend not yet wired.

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
│   │   ├── mobility.py           # 10-week cycling mobility video rotation service
│   │   ├── plan_generator.py     # LLM-powered daily plan with exercise pool + template fallback
│   │   ├── progression.py        # Arm feel trends, sleep patterns, recovery curves, weekly summaries, season summary
│   │   ├── llm.py                # DeepSeek wrapper (call_llm + call_llm_reasoning, 90s/120s timeouts)
│   │   ├── knowledge_retrieval.py # Exercise library search + auto-research generation
│   │   └── web_research.py       # Tavily API fallback for Q&A
│   └── prompts/                  # LLM prompt templates (.md): system, qa, plan_generation, triage, recovery
│
├── api/                          # FastAPI sidecar for mini-app
│   ├── main.py                   # App, CORS, health check
│   ├── auth.py                   # Telegram initData HMAC validation
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
│   │   └── pages/                # Home, Coach, Plans, PlanDetail, ExerciseLibrary, LogHistory, Profile (7 total)
│   └── .env.production           # VITE_API_URL
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
7. Pre-selected exercises + triage + context → LLM → structured JSON with personalized prescriptions
8. Fallback to exercise pool blocks if LLM fails (guaranteed valid exercise IDs)
9. Full entry upserted (same date = updates partial), results persist to pitcher_training_model
10. `days_since_outing` incremented AFTER first successful check-in of the day (re-check-ins don't double-increment), capped at `rotation_length * 3`

### Exercise Selection (`exercise_pool.py`)
- Filters library by: day focus (upper/lower/full), rotation_day_usage, contraindications, modification_flags
- Prefers exercises NOT used in last 7 days (weekly variety)
- Session structure: 1 explosive + 2 compounds + 3 accessories + 2 core (full day), fewer for light/flagged days
- Explosive block: 1 `plyometric_power` exercise (med ball slams, plyo pushups, jumps) inserted as first block on all non-recovery/non-light days
- Training intent mapped from rotation day + triage: power (day 2), strength (day 3-4), endurance (recovery/flagged)
- Injury modification flags appended as notes (e.g., "reduce to 5 reps" for UCL history)
- **Model-aware filtering**: exercise_preferences ("dislike" → deprioritized), equipment_constraints (hard filter), swap history (3+ swaps away → auto-dislike)
- LLM adjusts prescriptions but CANNOT add exercises outside the pre-selected pool

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

### API Endpoints (routes.py)
**Auth:** `/api/auth/resolve`
**Data:** `/api/pitcher/{id}/profile`, `/log`, `/progression`, `/upcoming`, `/week-summary`, `/morning-status`, `/weekly-narrative`
**Actions:** `POST /checkin`, `/outing`, `/chat` (unified), `/set-next-outing`, `/complete-exercise`
**Mobility:** `GET /pitcher/{id}/mobility-today`
**Swap:** `GET /exercises/{id}/alternatives?pitcher_id=X`, `POST /pitcher/{id}/swap-exercise`
**WHOOP:** `GET /pitcher/{id}/whoop-today`, `GET /whoop/callback` (OAuth)
**Plans:** `GET/POST /plans`, `/plans/{id}/activate`, `/deactivate`, `/apply-plan/{id}`, `/generate-plan`
**Library:** `/api/exercises`, `/api/exercises/slugs`
**Team:** `/api/staff/pulse`
**Trends:** `/api/pitcher/{id}/trend`, `/api/pitcher/{id}/chat-history`

### Scheduled Jobs (all from Supabase, not filesystem)
- Morning check-in at pitcher's `notification_time`
- 6pm follow-up if unanswered
- Sunday 6pm weekly narrative + summary
- `/gamestart` → 2hr delayed outing reminder
- 6am daily WHOOP pull for all linked pitchers (sends re-link message if auth expired)

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

## Deployment

### Architecture
```
GitHub (landonbrice/baseball)
  └─ pitcher_program_app/          ← Railway root
       ├─ bot/ + api/              ← Python backend (Railway)
       ├─ mini-app/                ← React frontend (Vercel)
       └─ data/                    ← JSON fallback (read-only, Supabase is primary)
```

### Railway (Bot + API)
- **Service:** Single process via `Procfile: web: python -m bot.run`
- **Root directory:** `pitcher_program_app` (or repo root with `cd pitcher_program_app`)
- **Auto-deploy:** On push to `main`
- **Required env vars:** `TELEGRAM_BOT_TOKEN`, `DEEPSEEK_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
- **Optional env vars:** `MINI_APP_URL`, `DISABLE_AUTH` (dev only)

### Vercel (Mini App)
- **Root directory:** `pitcher_program_app/mini-app`
- **Framework:** Vite (auto-detected)
- **Build:** `npm run build` → `dist/`
- **Auto-deploy:** On push to `main`
- **Env vars:** `VITE_API_URL=https://baseball-production-9d28.up.railway.app` (set in `.env.production`)

### Supabase (Database)
- **Project:** `pitcher-training-intel` (us-east-1, free tier)
- **URL:** `https://beyolhukpbvvoxvjnwtd.supabase.co`
- **Migrations:** Applied via Supabase MCP or dashboard SQL editor
- **Migration script:** `python -m scripts.migrate_to_supabase` (idempotent, safe to re-run)
- **Backup:** Supabase handles persistence. JSON files in `data/` are read-only fallback.

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

### Onboarding (`/start`)
- Personalized intro: references pitcher's role, injury history, rotation day
- If not checked in today: ends with arm feel keyboard (one tap to enter check-in flow)
- If already checked in: acknowledges plan, invites questions
- No command list shown — the interaction IS the onboarding

### Plan Generation Resilience
- Exercise pool builder guarantees valid exercise IDs from the library (no LLM hallucination)
- `_validate_plan()` strips unknown exercise IDs before minimum-count check, backfills from pool
- `_parse_plan_json()` surfaces `finish_reason: "length"` for truncation detection
- `max_tokens=4000` for both fast and reasoning models; `FAST_TIMEOUT=90s`, `REASONING_TIMEOUT=120s`
- `generate_plan()` has 3 return paths (LLM timeout fallback, successful parse, unparseable fallback) — new plan fields must be added to ALL THREE
- Template-driven blocks (warmup, post-throw) are injected by plan_generator, not LLM-generated

## Known Issues & Tech Debt

- 10 exercises missing YouTube links: ex_121-123, ex_126-128 (major lifts — not in source xlsx), ex_156-159 (new mobility stretches)
- `data_sync.py` still exists but is disabled — can be removed entirely
- WHOOP 6am pull may get partial data (strain before recovery/sleep) — handled by force_refresh on check-in and score_state guards
- Reliever template (`reliever_flexible.json`) uses text descriptions, not exercise IDs — not validated
- No periodization layer — exercise pool adds variety but not multi-week progressive structure
- No truncated JSON repair — `finish_reason` is surfaced but repair logic not built
- `/testnotify` and `/whooptest` commands exist for dev testing — can be removed before team rollout
- `_load_exercise_library()` uses `lru_cache(maxsize=1)` — cache never invalidates during a Railway process lifetime. New exercises in JSON require redeploy.

## Bot Scope Boundaries

**Owns:** Lifting programs, arm care, plyocare, recovery, readiness triage, Q&A, longitudinal tracking, program modifications based on injury/biometrics.

**Does NOT own:** Mechanical instruction, medical diagnosis, supplement recommendations. Flags concerns → tells pitcher to see trainer.
