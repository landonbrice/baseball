# Pitcher Training Intelligence — Claude Init

> Last updated: 2026-03-28
> Sprint status: Phases 1-5 complete. Next: WHOOP integration (see WHOOP_INTEGRATION_PLAN.md) + The Ledger (modification history).

## What This Is

A training intelligence system for the UChicago baseball pitching staff. Telegram bot + FastAPI API + React Mini App. Each pitcher gets personalized daily programs (lifting, arm care, recovery, throwing), evidence-based Q&A, and longitudinal tracking — driven by their individual profile, injury history, and conversation context.

**Three layers:**
- **Bot (Telegram)** — Conversational input layer. Morning check-ins, post-outing reports, free-text Q&A. The coaching relationship.
- **Mini App (React)** — Value/visibility layer. Programs, completion tracking, trajectory over time. Where compounding becomes tangible.
- **Intelligence Engine (Python/FastAPI)** — Triage, plan generation, knowledge retrieval, progression analysis. The thinking that connects input to output.

**The system is deployed but adoption is low.** The intelligence layer is solid. The problems are UX friction, fragile data persistence, and lack of visible payoff for consistency. This sprint fixes that.

## Active Sprint (March 2026)

> Full details in PROJECT_VISION.md. This section is the quick reference.

### Phase 1: Supabase Migration (Priority)
Migrate from JSON-on-Railway-filesystem to Supabase Postgres. This unblocks everything else.

**Key tables:** `pitchers`, `injury_history`, `active_flags`, `daily_entries`, `exercises`, `templates`, `saved_plans`, `chat_messages`, `weekly_summaries`

**Critical addition:** `chat_messages` table — both Telegram and mini app write here, both read. Solves the cross-platform conversation gap.

**Approach:**
- Create `bot/services/db.py` — async Supabase client, all CRUD operations
- Swap `context_manager.py` to read/write Supabase instead of filesystem
- Keep JSON files as read-only fallback during transition
- Migration script reads existing JSON data → inserts into Supabase

**New env vars needed:** `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`

### Phase 2: State Awareness
Bot and mini app share unified pitcher state. Morning status endpoint, cross-platform conversation history, explicit check-in tracking.

### Phase 3: Coaching Conversation Quality
Same data captured, but the bot *responds* to each step before asking the next. Context-aware prompts that reference yesterday's data. Smart defaults where rotation position is known. Preserve space for real pitcher input — the coaching is in the response, not the removal of steps.

### Phase 4: Visible Compounding
Mini app home redesign: arm feel trends, consistency streaks, LLM-generated weekly insights, exercise progression, plan modification history.

### Phase 5: Polish + Adoption Push
Update docs, fix broken flows, in-person onboarding with 2-3 pitchers, team monitoring dashboard.

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
│   │   ├── plan_generator.py     # LLM-powered daily plan from templates (674 lines, most complex service)
│   │   ├── progression.py        # Arm feel trends, sleep patterns, recovery curves, weekly summaries
│   │   ├── llm.py                # DeepSeek wrapper (call_llm + call_llm_reasoning)
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
1. Rule-based triage (`triage.py`) → green/yellow/red + modifications
2. Ambiguous cases → LLM refinement (`triage_llm.py`)
3. **Partial entry saved to Supabase BEFORE plan generation** (check-in data persists even if LLM fails)
4. Templates + triage + context → LLM → structured JSON protocol
5. Fallback to template-derived blocks if LLM fails
6. Full entry upserted (same date = updates partial), results persist to active_flags
7. `days_since_outing` incremented AFTER successful check-in (not before)

### Template Selection
- Normal rotation: `days_since_outing % rotation_length` → template day
- Extended time off (past rotation cycle): uses `lift_preference` to pick template
- `lift_preference = "rest"` → day_6 template (arm care + mobility only, no lifting) for ALL pitchers
- Return-to-throwing: always uses lift preference

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

### WHOOP Integration (Planned)
See `WHOOP_INTEGRATION_PLAN.md` for full technical plan. Not yet implemented.
- Per-pitcher OAuth PKCE linking via Supabase `whoop_tokens` table
- Daily 6am pull: recovery, HRV, sleep, strain → `whoop_daily` table
- Feeds into triage (HRV thresholds), plan generation (LLM context), weekly narrative

### Dual LLM Routing
- `call_llm()` — fast model (deepseek-chat) for simple Q&A, check-in responses, weekly narrative
- `call_llm_reasoning()` — reasoning model (deepseek-reasoner) for multi-day protocols, complex recovery plans
- Keyword detection in qa.py routes to appropriate model

### API Endpoints (routes.py)
**Auth:** `/api/auth/resolve`
**Data:** `/api/pitcher/{id}/profile`, `/log`, `/progression`, `/upcoming`, `/week-summary`, `/morning-status`, `/weekly-narrative`
**Actions:** `POST /checkin`, `/outing`, `/chat` (unified), `/set-next-outing`, `/complete-exercise`
**Plans:** `GET/POST /plans`, `/plans/{id}/activate`, `/deactivate`, `/apply-plan/{id}`, `/generate-plan`
**Library:** `/api/exercises`, `/api/exercises/slugs`
**Team:** `/api/staff/pulse`
**Trends:** `/api/pitcher/{id}/trend`, `/api/pitcher/{id}/chat-history`

### Scheduled Jobs (all from Supabase, not filesystem)
- Morning check-in at pitcher's `notification_time`
- 6pm follow-up if unanswered
- Sunday 6pm weekly narrative + summary
- `/gamestart` → 2hr delayed outing reminder
- (Planned) 6am daily WHOOP pull for linked pitchers

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

### Deploy Checklist
1. Push to `main` → Railway + Vercel auto-deploy
2. If adding new Supabase tables/columns → apply migration first via MCP or dashboard
3. If changing env vars → update in Railway dashboard, trigger redeploy
4. Verify: bot responds to `/checkin`, API health at `/api/staff/pulse`, mini-app loads in Telegram

### Data Safety
- **Supabase is source of truth.** JSON files are read-only fallback (`USE_JSON_FALLBACK=true`).
- **`data_sync.py` is disabled.** No more auto-push to GitHub on writes.
- **JSONB guard pattern:** Always use `(x.get("field") or {}).get()` in Python, `Array.isArray()`/`typeof` in React. See `mini-app/src/utils/sanitize.js`.

## Known Issues & Tech Debt

- Exercise library has YouTube link gaps (see `unmatched_youtube.csv`)
- Templates reference exercise IDs that must exist in library — no validation
- WHOOP API integration is a stub (schema fields exist, no API calls)
- `data_sync.py` still exists but is disabled — can be removed entirely
- Bot `/checkin` may hang if DeepSeek API is slow — needs timeout on LLM calls

## Bot Scope Boundaries

**Owns:** Lifting programs, arm care, plyocare, recovery, readiness triage, Q&A, longitudinal tracking, program modifications based on injury/biometrics.

**Does NOT own:** Mechanical instruction, medical diagnosis, supplement recommendations. Flags concerns → tells pitcher to see trainer.
