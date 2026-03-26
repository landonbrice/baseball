# Pitcher Training Intelligence — Claude Init

> Last updated: 2026-03-25
> Sprint status: Active — Supabase migration + UX overhaul (see PROJECT_VISION.md for full plan)

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
| Data | **Migrating:** JSON files → Supabase (Postgres) | Supabase (target) / Railway filesystem (current) |

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
│   │   ├── context_manager.py    # Profile/log/context CRUD, pitcher lookup, plan persistence — MIGRATING TO SUPABASE
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
│   │   ├── components/           # DailyCard, WeekStrip, TrendChart, ChatBar, FlagBadge, PlanBuilder (12 total)
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
**Current (being migrated):** context.md per pitcher with persistent facts + recent interactions (15 most recent, truncated to 12000 chars for LLM calls).

**Target:** Query recent `chat_messages` + `daily_entries` + `active_flags` from Supabase directly. No more maintaining a text file.

### Triage → Plan Pipeline
1. Rule-based triage (`triage.py`) → green/yellow/red + modifications
2. Ambiguous cases → LLM refinement (`triage_llm.py`)
3. Templates + triage + context → LLM → structured JSON protocol
4. Fallback to template-derived blocks if LLM fails
5. Results persist to active_flags

### Dual LLM Routing
- `call_llm()` — fast model (deepseek-chat) for simple Q&A, check-in responses
- `call_llm_reasoning()` — reasoning model (deepseek-reasoner) for multi-day protocols, complex recovery plans
- Keyword detection in qa.py routes to appropriate model

### API Endpoints (routes.py)
**Auth:** `/api/auth/resolve`
**Data:** `/api/pitcher/{id}/profile`, `/log`, `/progression`, `/upcoming`, `/week-summary`, `/morning-status`
**Actions:** `POST /checkin`, `/outing`, `/chat` (unified), `/set-next-outing`, `/complete-exercise`
**Plans:** `GET/POST /plans`, `/plans/{id}/activate`, `/deactivate`, `/apply-plan/{id}`, `/generate-plan`
**Library:** `/api/exercises`, `/api/exercises/slugs`

### Scheduled Jobs
- Morning check-in at pitcher's `notification_time`
- 6pm follow-up if unanswered
- Sunday 6pm weekly summary
- `/gamestart` → 2hr delayed outing reminder

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
| SUPABASE_URL | yes (new) | — | Supabase project URL |
| SUPABASE_SERVICE_KEY | yes (new) | — | Supabase service role key |
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

## Known Issues & Tech Debt

- Railway filesystem is ephemeral — data loss risk on redeploy (Supabase migration fixes this)
- context.md rebuild logic is complex — Supabase queries will replace it
- Exercise library has YouTube link gaps (see `unmatched_youtube.csv`)
- Conversation history lost on mini app reload (chat_messages table fixes this)
- Bot and mini app don't share real-time conversation state (unified chat_messages fixes this)
- No concurrent write protection for JSON files (Supabase transactions fix this)

## Bot Scope Boundaries

**Owns:** Lifting programs, arm care, plyocare, recovery, readiness triage, Q&A, longitudinal tracking, program modifications based on injury/biometrics.

**Does NOT own:** Mechanical instruction, medical diagnosis, supplement recommendations. Flags concerns → tells pitcher to see trainer.
