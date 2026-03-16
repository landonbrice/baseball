# Pitcher Training Bot — Claude Init

## Project Overview

Telegram bot + FastAPI data API + React mini-app for managing daily pitcher training (lifting, arm care, plyocare, recovery). Built for Landon Brice, UChicago baseball starter.

**Stack:** Python 3.11 / python-telegram-bot v20+ / FastAPI / DeepSeek API / React + Vite + Tailwind (mini-app)
**Deployment:** Bot + API on Railway, Mini-app on Vercel
**Spec:** `pitcher_program_app/MASTER_PROJECT.md`

## Repo Structure

```
pitcher_program_app/
  bot/                    # Telegram bot (long-polling)
    main.py               # Entry point, handlers, scheduled jobs (APScheduler)
    config.py             # Env vars, paths, CONTEXT_WINDOW_CHARS
    utils.py              # Shared keyboard builders
    handlers/
      daily_checkin.py    # /checkin ConversationHandler (arm feel → sleep → energy → triage → plan)
      post_outing.py      # /outing ConversationHandler (pitch count → arm feel → notes → recovery plan)
      qa.py               # Free-text Q&A via LLM
    services/
      context_manager.py  # Profile/log/context CRUD, pitcher lookup by telegram_id
      triage.py           # Rule-based readiness triage (green/yellow/red)
      plan_generator.py   # LLM-powered daily plan from templates + triage
      progression.py      # Arm feel trends, sleep patterns, recovery curves
      llm.py              # DeepSeek API wrapper (OpenAI-compatible)
      knowledge_retrieval.py  # Exercise library + knowledge search
      web_research.py     # Stub for web search fallback
    prompts/              # LLM prompt templates (.md)
  api/                    # FastAPI data API (sidecar)
    main.py               # FastAPI app, CORS
    auth.py               # Telegram initData HMAC validation
    routes.py             # /api/pitcher/{id}/*, /api/exercises (authed)
  data/
    pitchers/             # Per-pitcher dirs (profile.json, daily_log.json, context.md)
    templates/            # Training templates (starter_7day, arm_care_*, plyocare, reliever, recovery)
    knowledge/            # exercise_library.json, extended_knowledge.md
  mini-app/               # React Telegram Mini App
    src/
      constants.js        # Shared FLAG_COLORS palette
      components/         # FlagBadge, WeekStrip, TrendChart, DailyCard, ExerciseRow
      pages/              # Home, ExerciseLibrary, LogHistory, Profile
      hooks/              # useApi, usePitcher, useTelegram
  research/               # Reference material (not loaded by bot)
  scripts/                # seed_test_data, seed_test_pitcher, intake_to_profile
```

## Current State (after 2026-03-16 audit)

All 17 audit fixes have been implemented but **not yet pushed or tested live**:

### What was fixed
- **Rotation day now increments** on each /checkin (was stuck at Day 0)
- **Triage results persist** to profile (flag_level + arm_feel written back)
- **Completion keyboard** on every plan ([All done] [Skipped some] [Dashboard])
- **HMAC auth fixed** (key/message order corrected)
- **API routes authed** via X-Telegram-Init-Data header
- **Reliever branching** — "Did you throw?" before check-in
- **8+ day outing detection** for starters
- **Scheduled morning check-ins** via JobQueue at pitcher's notification_time
- **/setday command** for manual rotation day correction
- **Sunday 6pm weekly summary** sent proactively
- **New templates** — reliever_flexible.json, recovery_protocols.json
- **Shared utils** — keyboard builders, CONTEXT_WINDOW_CHARS, mini-app color constants
- **Cleanup** — stale pitcher files merged into profile.json, source material moved to research/

### What still needs work

**High priority:**
- [ ] **Push and deploy** — all changes are local. Push to trigger Railway/Vercel deploys
- [ ] **Test /checkin end-to-end** — verify arm feel → sleep → energy → triage → plan with completion buttons
- [ ] **Test /outing end-to-end** — verify outing → Day 0 reset → next /checkin shows Day 1
- [ ] **Test /setday** — verify rotation day correction works
- [ ] **Test API auth** — `curl /api/pitcher/pitcher_brice_001/profile` without header should 401
- [ ] **Verify scheduler** — morning check-in and Sunday summary jobs run (needs telegram_id set)
- [ ] **Landon's telegram_id** — still null in profile.json; will auto-backfill on first message via username match

**Medium priority (implemented, needs testing):**
- [x] **6pm follow-up** if morning check-in unanswered → `_send_evening_followup()` in main.py
- [x] **Post-outing prompt** → `/gamestart` command schedules 2hr delayed reminder via JobQueue
- [x] **Natural language rotation day** → regex in qa.py detects "I'm on day X" and updates profile
- [x] **LLM-driven triage** → triage.py flags ambiguous cases, triage_llm.py refines via LLM
- [x] **Web search fallback** → Tavily API integration in web_research.py (needs TAVILY_API_KEY env var)
- [x] **Workout logging** → "Skipped some" button asks what was skipped, logs to daily_log

**Low priority:**
- [ ] Intake form to profile script (`scripts/intake_to_profile.py` exists but incomplete)
- [ ] Trainer escalation mechanism (bot flags but no trainer notification channel)
- [ ] Deload week auto-detection in progression.py
- [ ] LLM prompt caching (system prompts loaded fresh each call)

## Key Patterns

- **Pitcher lookup:** `get_pitcher_id_by_telegram(telegram_id, username)` — first match by telegram_id, fallback by telegram_username with auto-backfill
- **Triage flow:** Pure Python rules in triage.py → green/yellow/red flag + modifications + protocol_adjustments
- **Plan generation:** Templates (starter_7day.json) + triage result → LLM prompt → formatted protocol
- **Context:** Append-only context.md per pitcher, truncated to CONTEXT_WINDOW_CHARS (500) for LLM calls
- **Daily log:** JSON array of entries with pre_training, plan_generated, actual_logged, bot_observations

## Running Locally

```bash
cd pitcher_program_app
pip install -r requirements.txt

# Bot (needs TELEGRAM_BOT_TOKEN + DEEPSEEK_API_KEY in .env)
python -m bot.main

# API (separate process)
python -m api.main

# Mini-app
cd mini-app && npm install && npm run dev
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| TELEGRAM_BOT_TOKEN | yes | Bot token from @BotFather |
| DEEPSEEK_API_KEY | yes | DeepSeek API key |
| MINI_APP_URL | no | Deployed mini-app URL (Vercel) |
| LLM_MODEL | no | Default: deepseek-chat |
| TAVILY_API_KEY | no | Tavily search API key for web research fallback |
| PORT | no | API port, default 8000 |
