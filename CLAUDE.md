# Pitcher Training Bot — Claude Init

> Last updated: 2026-03-23

## What This Is

A live, production training intelligence system for the UChicago baseball pitching staff. Telegram bot + FastAPI sidecar + React Mini App dashboard. Each pitcher gets personalized daily lifting programs, arm care protocols, recovery programming, evidence-based Q&A, and longitudinal tracking — all driven by their individual profile, injury history, biometric data, and conversation context.

**The system is deployed and actively used by real pitchers.**

## Stack

| Layer | Tech | Where |
|-------|------|-------|
| Bot | Python 3.11 / python-telegram-bot v20+ / APScheduler | Railway (long-polling) |
| API | FastAPI / Uvicorn | Railway (same service, Procfile) |
| LLM | DeepSeek (OpenAI-compatible wrapper) | DeepSeek API |
| Mini App | React 18 / Vite / Tailwind CSS | Vercel |
| Data | JSON files + Markdown context per pitcher | Railway filesystem |

**Deployment URLs:**
- API: `https://baseball-production-9d28.up.railway.app`
- Mini App: Vercel (configured in `mini-app/.env.production`)
- Bot: `@uchi_pitcher_bot` on Telegram

## Repo Structure

```
pitcher_program_app/
├── bot/                          # Telegram bot (long-polling)
│   ├── main.py                   # Entry point, all handlers, scheduled jobs
│   ├── config.py                 # Env vars, paths, CONTEXT_WINDOW_CHARS=500
│   ├── run.py                    # Railway entry (Procfile: python -m bot.run)
│   ├── utils.py                  # Shared keyboard builders
│   ├── handlers/
│   │   ├── daily_checkin.py      # /checkin ConversationHandler
│   │   ├── post_outing.py        # /outing ConversationHandler
│   │   └── qa.py                 # Free-text Q&A with conversation history
│   ├── services/
│   │   ├── context_manager.py    # Profile/log/context CRUD, pitcher lookup
│   │   ├── checkin_service.py    # Check-in → triage → plan generation
│   │   ├── outing_service.py     # Outing → recovery protocol
│   │   ├── triage.py             # Rule-based readiness triage (green/yellow/red)
│   │   ├── triage_llm.py         # LLM refinement for ambiguous triage
│   │   ├── plan_generator.py     # LLM-powered daily plan from templates
│   │   ├── progression.py        # Arm feel trends, weekly summaries
│   │   ├── llm.py                # DeepSeek wrapper (model swappable via config)
│   │   ├── knowledge_retrieval.py # Exercise library + knowledge search
│   │   └── web_research.py       # Tavily API fallback
│   └── prompts/                  # LLM prompt templates (.md)
│
├── api/                          # FastAPI sidecar for mini-app
│   ├── main.py                   # App, CORS, health check
│   ├── auth.py                   # Telegram initData HMAC validation
│   └── routes.py                 # All /api/* endpoints (authed)
│
├── data/
│   ├── pitchers/                 # Per-pitcher dirs: profile.json, context.md, daily_log.json
│   ├── templates/                # Training program templates (JSON + MD)
│   ├── knowledge/                # exercise_library.json, research base, extended knowledge
│   └── intake_responses.json     # Raw Google Form responses
│
├── mini-app/                     # React Telegram Mini App
│   ├── src/
│   │   ├── App.jsx / Layout.jsx  # Router, ChatProvider, TelegramWebApp init
│   │   ├── hooks/                # useApi, usePitcher, useTelegram, useChatState
│   │   ├── components/           # ChatBar, DailyCard, WeekStrip, TrendChart, etc.
│   │   └── pages/                # Home, Plans, ExerciseLibrary, LogHistory, Profile
│   └── .env.production           # VITE_API_URL
│
├── research/                     # Reference material (NOT loaded at runtime)
├── scripts/                      # intake_to_profile.py, seed scripts, backup
├── bot_structure/                # Design docs (reference)
├── files/                        # Architecture + pipeline docs
├── past_arm_programs/            # Historical spreadsheets (reference)
│
├── MASTER_PROJECT.md             # Original project specification
├── Procfile                      # Railway: web: python -m bot.run
├── railway.toml                  # Build config (nixpacks)
└── requirements.txt              # Python deps
```

## Key Patterns

### Pitcher Lookup
`get_pitcher_id_by_telegram(telegram_id, username)` — matches by telegram_id first, falls back to telegram_username with auto-backfill on first message.

### Context System (context.md per pitcher)
Two sections:
- **Persistent facts** — role, rotation, injury history, active mods (auto-rebuilt from profile)
- **Recent interactions** — timestamped entries, trimmed to 15 most recent

Truncated to `CONTEXT_WINDOW_CHARS` (500) for LLM calls.

### Conversation History
- **Telegram:** Last 3 exchanges in `context.user_data` (in-memory, per-session)
- **Mini App:** ChatProvider holds messages in React state, sends to `/api/ask`
- **Cross-platform gap:** Both read context.md but don't share real-time conversation state

### Triage → Plan Pipeline
1. Rule-based triage (`triage.py`) → green/yellow/red + modifications
2. Ambiguous → LLM refinement (`triage_llm.py`)
3. Templates + triage + context → LLM → structured protocol
4. Results persist to profile.json active_flags

### Scheduled Jobs
- Morning check-in at pitcher's `notification_time`
- 6pm follow-up if unanswered
- Sunday 6pm weekly summary
- `/gamestart` → 2hr delayed outing reminder

### Onboarding Pipeline
1. Pitcher fills Google Form → export to `data/intake_responses.json`
2. `python scripts/intake_to_profile.py --json data/intake_responses.json`
3. Creates `data/pitchers/{pitcher_id}/` (profile.json, context.md, daily_log.json)
4. `telegram_id` backfills on first bot message via username match

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

## Critical: Data Backup

Railway filesystem resets on redeploy. Run `scripts/backup_data.sh` after any day of real usage to pull pitcher data and commit to repo.

## Bot Scope Boundaries

**Owns:** Lifting programs, arm care, plyocare, recovery, readiness triage, Q&A, longitudinal tracking, program modifications based on injury/biometrics.

**Does NOT own:** Mechanical instruction, medical diagnosis, supplement recommendations. Flags concerns → tells pitcher to see trainer.
