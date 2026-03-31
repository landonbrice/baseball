# Pitcher Training Intelligence — Claude Init

> Last updated: 2026-03-31
> Sprint status: Phases 1-6 + adoption push + dynamic exercise pool complete. Next: The Ledger (modification history), periodization, exercise progression curves.

## What This Is

A training intelligence system for the UChicago baseball pitching staff. Telegram bot + FastAPI API + React Mini App. Each pitcher gets personalized daily programs (lifting, arm care, recovery, throwing), evidence-based Q&A, and longitudinal tracking — driven by their individual profile, injury history, and conversation context.

**Three layers:**
- **Bot (Telegram)** — Conversational input layer. Morning check-ins, post-outing reports, free-text Q&A. The coaching relationship.
- **Mini App (React)** — Value/visibility layer. Programs, completion tracking, trajectory over time. Where compounding becomes tangible.
- **Intelligence Engine (Python/FastAPI)** — Triage, plan generation, knowledge retrieval, progression analysis. The thinking that connects input to output.

**The system is deployed and functional.** Morning notifications, WHOOP biometrics, dynamic exercise selection, and personalized onboarding are all live. Adoption push is in progress.

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
- `exercise_pool.py`: selects 7-8 exercises from the 95-exercise Supabase library per session
- Filters by day focus, rotation_day_usage, injury contraindications, modification_flags
- Prefers exercises not used in last 7 days (variety across weeks)
- Applies prescription from the exercise's phase data (strength/power/hypertrophy/endurance)
- LLM receives pre-selected exercises — adjusts prescriptions and writes narrative, cannot hallucinate IDs
- Arm care and throwing remain template-based (curated protocols)

### What's Not Yet Built
1. **The Ledger** — Modification history visualization. Data exists in `plan_generated.modifications_applied`. Needs frontend timeline on Profile.
2. **Periodization** — No multi-week phases (hypertrophy → strength → power). Template repeats identically each week. Exercise pool adds variety but not progressive structure.
3. **Exercise progression curves** — Volume/intensity trends for key lifts over time.
4. **Coach dashboard** — Staff-facing view of team readiness, flags, trends.
5. **Truncated JSON repair** — LLM sometimes returns cut-off JSON. `finish_reason` is surfaced but repair logic not yet built.

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
│   │   ├── exercise_pool.py      # Dynamic exercise selection from library (replaces static templates)
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
│   ├── knowledge/                # exercise_library.json (250+ exercises), research docs with YAML front matter
│   └── intake_responses.json     # Raw Google Form responses
│
├── mini-app/                     # React Telegram Mini App
│   ├── src/
│   │   ├── App.jsx / Layout.jsx  # Router, auth context, TelegramWebApp init, morning badge check
│   │   ├── hooks/                # useApi, usePitcher, useTelegram, useChatState
│   │   ├── components/           # DailyCard, WeekStrip, TrendChart, SessionProgress, Sparkline, StreakBadge, StaffPulse, CoachFAB, TrendInsightChart, ExerciseWhy, etc. (19 total)
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
Supabase-backed. `context_manager.py` queries recent `chat_messages` + `daily_entries` + `active_flags` from Supabase to build LLM context. JSON filesystem fallback available via `USE_JSON_FALLBACK=true`.

### Triage → Plan Pipeline
1. Rule-based triage (`triage.py`) → green/yellow/red + modifications (includes WHOOP HRV/recovery/sleep thresholds)
2. Ambiguous cases → LLM refinement (`triage_llm.py`)
3. **Partial entry saved to Supabase BEFORE plan generation** (check-in data persists even if LLM fails)
4. **Dynamic exercise pool** (`exercise_pool.py`) selects 7-8 lifting exercises from the 95-exercise library
5. Pre-selected exercises + triage + context → LLM → structured JSON with personalized prescriptions
6. Fallback to exercise pool blocks if LLM fails (guaranteed valid exercise IDs)
7. Full entry upserted (same date = updates partial), results persist to active_flags
8. `days_since_outing` incremented AFTER first successful check-in of the day (re-check-ins don't double-increment)

### Exercise Selection (`exercise_pool.py`)
- Filters library by: day focus (upper/lower/full), rotation_day_usage, contraindications, modification_flags
- Prefers exercises NOT used in last 7 days (weekly variety)
- Session structure: 2 compounds + 3 accessories + 2 core (full day), fewer for light/flagged days
- Training intent mapped from rotation day + triage: power (day 2), strength (day 3-4), endurance (recovery/flagged)
- Injury modification flags appended as notes (e.g., "reduce to 5 reps" for UCL history)
- LLM adjusts prescriptions but CANNOT add exercises outside the pre-selected pool

### Template Selection (Lift Preference)
- **Explicit preference always wins**: "upper" → day_3 template, "lower" → day_2, "rest" → day_6, regardless of rotation day
- **"Your call" / "auto" / empty**: falls back to rotation-based (`days_since_outing` → template day)
- Extended time off (past rotation cycle): uses preference if given, else mid-rotation
- Arm care templates (heavy/light) and throwing plans remain template-based (curated protocols)

### Timezone
All dates use `CHICAGO_TZ` (from `bot/config.py`). Server-side: `datetime.now(CHICAGO_TZ)`. Client-side: `toLocaleDateString('en-CA', { timeZone: 'America/Chicago' })`.

### DB Column Whitelist
`db.py` uses `_DAILY_ENTRY_COLUMNS` whitelist to strip unknown fields before upsert, preventing PostgREST 400 errors from schema mismatches.

### Weekly Coaching Narrative
- `generate_weekly_narrative(pitcher_id)` in `progression.py` — LLM-generated Sunday evening
- `build_week_snapshot()` collects arm feel, sleep, exercise completion, throwing, modifications
- Stored in `weekly_summaries` table, served via `/api/pitcher/{id}/weekly-narrative`
- Displayed in `InsightsCard` on Home with maroon accent border
- Falls back to stats-only summary if LLM fails

### Toast Notifications (Mini-App)
- `useToast` hook + `ToastProvider` in `hooks/useToast.jsx`
- Success toasts: plan generated, outing logged, plan activated/applied
- Error toasts: exercise save failed, plan update failed
- Auto-dismiss after 3.5 seconds

### WHOOP Integration (Live)
See `WHOOP_INTEGRATION_PLAN.md` for original technical plan. Fully implemented 2026-03-29.
- Per-pitcher OAuth PKCE linking via `/whoop` command + `/api/whoop/callback`
- Tokens stored in Supabase `whoop_tokens` table, auto-refresh on expiry
- Daily 6am pull: recovery, HRV, sleep, strain → `whoop_daily` table
- Smart cache: re-pulls when core metrics (recovery/HRV/sleep) are null (WHOOP processes sleep data ~1-2hr after wake)
- Feeds into triage (`whoop_hrv`, `whoop_hrv_7day_avg`, `whoop_sleep_perf` params), plan generation (LLM context block), weekly narrative
- `WhoopCard` component on Home page (recovery ring + HRV/sleep/strain satellites), only renders for linked pitchers
- Profile page shows "WHOOP Connected" badge or link instructions
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
| `active_flags` | Current state per pitcher — arm_feel, flag_level, days_since_outing, modifications |
| `daily_entries` | Daily training logs — pre_training, plan_generated, actual_logged, completed_exercises |
| `exercises` | Exercise library (95 exercises) — prescription, tags, contraindications, youtube_url |
| `templates` | Training templates (9) — rotation day structure, exercise blocks |
| `saved_plans` | Pitcher-specific saved/generated plans with plan_data JSONB |
| `chat_messages` | Cross-platform conversation persistence — source (telegram/mini_app), role, content |
| `weekly_summaries` | Aggregated weekly data for long-term tracking |
| `whoop_tokens` | Per-pitcher WHOOP OAuth tokens (access, refresh, expiry) |
| `whoop_daily` | Daily WHOOP biometrics — recovery, HRV, sleep, strain, raw API data |

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

## Known Issues & Tech Debt

- Exercise library has YouTube link gaps (see `unmatched_youtube.csv`)
- `data_sync.py` still exists but is disabled — can be removed entirely
- WHOOP recovery/HRV/sleep data may be null if WHOOP hasn't processed overnight sleep yet (strain available first)
- Reliever template (`reliever_flexible.json`) uses text descriptions, not exercise IDs — not validated
- No periodization layer — exercise pool adds variety but not multi-week progressive structure
- No truncated JSON repair — `finish_reason` is surfaced but repair logic not built
- `/testnotify` command exists for dev testing — can be removed before team rollout

## Bot Scope Boundaries

**Owns:** Lifting programs, arm care, plyocare, recovery, readiness triage, Q&A, longitudinal tracking, program modifications based on injury/biometrics.

**Does NOT own:** Mechanical instruction, medical diagnosis, supplement recommendations. Flags concerns → tells pitcher to see trainer.
