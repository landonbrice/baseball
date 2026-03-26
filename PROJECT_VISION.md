# Pitcher Training Intelligence — Project Vision

> Last updated: 2025-03-25
> Status: Active development, focused sprint

## What This Is

A training intelligence system for the UChicago pitching staff. Each pitcher gets personalized daily programs (lifting, arm care, recovery, throwing), evidence-based Q&A, and longitudinal tracking — driven by their individual profile, injury history, biometric context, and conversation history.

The system has three layers:
- **Bot (Telegram)** — The conversational input layer. Morning check-ins, post-outing reports, free-text Q&A. This is where the coaching relationship lives.
- **Mini App (React)** — The value/visibility layer. See your program, track completion, view your trajectory over time. This is where compounding becomes tangible.
- **Intelligence Engine (Python/FastAPI)** — Triage, plan generation, knowledge retrieval, progression analysis. The thinking that connects input to output.

---

## Current State (Honest Assessment)

### What's Built and Working

**Intelligence layer — strong.** The core pipeline (check-in → triage → plan generation → delivery) is complete and sophisticated. Rule-based triage with LLM refinement, injury-aware modifications, multi-template plan generation with exercise library integration (250+ exercises), progression tracking with arm feel trend detection, and auto-research generation for Q&A gaps. This is the real IP of the project.

**API layer — complete.** 25+ endpoints covering auth, check-in, outing, chat, plans CRUD, exercise tracking, exercise library, progression, and morning status. The unified `/chat` endpoint handles check-in, outing, and free-text Q&A in a single interface, returning structured message types (text, buttons, status, save_plan).

**Mini app — structurally complete, UX incomplete.** All pages exist (Home, Coach, Plans, PlanDetail, ExerciseLibrary, LogHistory, Profile). All API calls have corresponding backend endpoints. But conversation history is lost on page reload, check-in status isn't fully synchronized across sessions, and the visual experience doesn't yet communicate the "compounding over time" story.

**Data — rich but fragile.** 12 pitcher profiles with full injury histories, training preferences, and active flags. Daily logs with exercise-level completion tracking. Templates for 7-day starters and flexible relievers. But it all lives as JSON on Railway's ephemeral filesystem with a backup-to-GitHub strategy that isn't verified or guaranteed.

### What's Not Working

**Adoption is low.** The system works technically but hasn't become a daily habit for the pitching staff. This is the central problem. The causes:

1. **The bot check-in feels like a form, not a coach.** Five sequential multiple-choice states before you get value. A great pitching coach adapts the conversation to what you say — this system runs the same script every morning regardless. The *content* of each step is right (arm feel, lift preference, throw intent, schedule), but the *interaction pattern* needs to feel more like a conversation and less like a survey.

2. **The mini app doesn't show the payoff of consistency.** There's no visible streak, no arm feel trajectory that makes you think "my program is working," no insight that references your history ("your post-outing recovery has been faster this month"). The data exists in daily logs but isn't surfaced as narrative.

3. **State doesn't persist across sessions.** Coach conversation history is React state — gone on reload. Check-in status is detected indirectly. A pitcher who checks in via Telegram and opens the mini app has no continuity. The system should know everything about you without you having to re-establish context.

4. **WHOOP integration is a stub.** Schema fields exist but no API calls. Sleep defaults to 7.0. This was supposed to be a differentiator — the system that actually knows your biometrics.

### What's Intentionally Out of Scope

- Mechanical/pitching instruction (coaches own this)
- Medical diagnosis (system flags concerns → tells pitcher to see trainer)
- Supplement recommendations
- Nutrition programming

---

## Target State

### Product Thesis

This is a **training intelligence layer that knows each pitcher's body, history, and trajectory** — and makes that knowledge feel tangible through a daily interface that's as natural as talking to your pitching coach.

The bot is the coaching conversation. The mini app is the mirror that shows you your progress. Together, they create a system where every check-in compounds into a more personalized, more effective program.

### Core Principles

**1. The system always knows where you are.**
No asking questions it should already know the answer to. If you checked in this morning, the bot knows. If you threw yesterday, it knows. If your arm feel has been trending down, it brings that up proactively. State awareness across bot and mini app, persisted in a real database.

**2. Check-ins are coaching conversations, not forms.**
The information gathered (arm feel, energy, sleep, intent) stays the same. But the interaction adapts. If you said your arm feels great and you're 3 days out from an outing, the conversation is different than if you're day-after with lingering tightness. The bot should respond to what you actually say, not just slot it into a category.

**3. The mini app shows you your trajectory.**
Open the app and immediately see: your arm feel over time, your consistency streak, your program modifications and why they were made, insights that reference your actual history. The daily plan matters, but the *story of your season* is what creates buy-in.

**4. Data is durable, queryable, and the foundation for everything.**
Real database (Supabase/Postgres). Proper schemas. Cross-pitcher queries for team-level insights. No more JSON-on-ephemeral-filesystem anxiety.

---

## Architecture Decisions

### Data Layer: Supabase Migration

**Decision:** Migrate from JSON-on-filesystem to Supabase (Postgres).

**Why:**
- Railway filesystem is ephemeral — data loss risk on every redeploy
- JSON files can't be queried across pitchers efficiently
- Concurrent writes from bot + API are a race condition
- Supabase free tier covers our needs (500MB, 50K MAU)
- Enables features that are impossible with flat files: team dashboards, cross-pitcher trend queries, real-time subscriptions
- Built-in auth that can replace custom HMAC validation

**Schema Design (from current JSON):**

| Table | Source | Key Fields |
|-------|--------|------------|
| `pitchers` | profile.json | pitcher_id (PK), telegram_id, name, role, rotation_length, throws, physical_profile (JSONB), pitching_profile (JSONB), current_training (JSONB), goals (JSONB), preferences (JSONB), biometric_integration (JSONB) |
| `injury_history` | profile.json → injury_history[] | id (PK), pitcher_id (FK), date, area, severity, description, resolution, flag_level, red_flags (JSONB) |
| `active_flags` | profile.json → active_flags | pitcher_id (FK, unique), current_arm_feel, current_flag_level, days_since_outing, phase, active_modifications (JSONB), next_outing_days |
| `daily_entries` | daily_log.json → entries[] | id (PK), pitcher_id (FK), date, rotation_day, pre_training (JSONB), plan_narrative, morning_brief, arm_care (JSONB), lifting (JSONB), throwing (JSONB), notes (JSONB), completed_exercises (JSONB), plan_generated (JSONB) |
| `exercises` | exercise_library.json | id (PK), name, slug, category, subcategory, muscles_primary (JSONB), pitching_relevance, prescription (JSONB), tags (JSONB), contraindications (JSONB), youtube_url |
| `templates` | templates/*.json | id (PK), role, rotation_length, days (JSONB), global_rules (JSONB) |
| `saved_plans` | saved_plans.json | id (PK), pitcher_id (FK), plan_data (JSONB), active (bool), created_at |
| `chat_messages` | NEW | id (PK), pitcher_id (FK), source (telegram/mini_app), role (user/assistant), content, metadata (JSONB), created_at |
| `weekly_summaries` | profile.json → weekly_summaries | id (PK), pitcher_id (FK), week_start, summary (JSONB) |

**Key addition:** `chat_messages` table. This solves the conversation persistence gap — both Telegram and mini app write to the same table, both can read history. The coaching relationship has memory.

### LLM Layer: Keep DeepSeek, Abstract Provider

Current DeepSeek integration works. Keep the provider-swappable architecture (LLM_PROVIDER + LLM_MODEL config). No changes needed here — the prompt templates and dual-model routing (fast chat vs. reasoning for complex protocols) are solid.

### Deployment: Keep Railway + Vercel

Railway for bot + API (single process via Procfile). Vercel for mini app. Add Supabase as the persistence layer. This is the right architecture — no changes needed.

---

## Sprint Plan (1-2 Weeks)

### Phase 1: Foundation (Days 1-3) — Data Migration

**Goal:** Get off ephemeral filesystem. Every feature after this depends on durable data.

- [ ] Set up Supabase project with schema from table above
- [ ] Write migration script: read all JSON files → insert into Supabase tables
- [ ] Create `db.py` service layer (async Supabase client, CRUD operations)
- [ ] Swap `context_manager.py` to read/write from Supabase instead of filesystem
- [ ] Add `chat_messages` table and write adapter for both bot and API
- [ ] Verify: bot check-in → data in Supabase → mini app reads it correctly
- [ ] Keep JSON files as read-only fallback during transition

### Phase 2: State Awareness (Days 3-5) — The System Knows You

**Goal:** The bot and mini app share a unified understanding of each pitcher's current state.

- [ ] Implement cross-platform conversation history (bot writes to chat_messages, mini app reads it)
- [ ] Morning status endpoint returns: checked_in_today, last_interaction, arm_feel_trend, days_until_outing
- [ ] Bot check-in adapts opening based on yesterday's data and current state
- [ ] Mini app Coach page loads recent conversation history on open
- [ ] Check-in completion state is explicit and queryable (not inferred from log fields)

### Phase 3: Coaching Conversation Quality (Days 5-8) — Check-in That Feels Like a Coach

**Goal:** Same information gathered, but the interaction feels adaptive and personal.

- [ ] Redesign check-in flow: bot responds to arm feel report before asking next question (acknowledges what you said, adjusts follow-ups)
- [ ] Smart defaults: if you're day 1 post-outing, pre-fill "recovery" as lift intent, skip throw intent (you're not throwing)
- [ ] Context-aware prompts: "Yesterday you mentioned some forearm tightness — how's that feeling today?" instead of generic "How's the arm?"
- [ ] Reduce steps where data is already known (rotation day auto-calculated, don't ask schedule if next outing is set)
- [ ] Preserve the space for real input — arm feel report stays free-text, lift preference stays a choice. The coaching is in the *response*, not the removal of steps.

### Phase 4: Visible Compounding (Days 8-12) — The Mirror

**Goal:** Open the mini app and immediately see the story of your season.

- [ ] Home page redesign: arm feel trend chart (last 4 weeks), consistency streak, current rotation position
- [ ] Insights card: LLM-generated weekly observations referencing actual data ("Your arm feel averaged 4.2 this week, up from 3.6 last week. Recovery times are getting shorter.")
- [ ] Plan history view: see past plans with what was completed vs skipped, with modification rationale
- [ ] Exercise progression: for key lifts, show volume/intensity trends over time
- [ ] Team context (lightweight): "8 of 12 pitchers checked in today" — peer visibility without competition

### Phase 5: Polish & Adoption Push (Days 12-14)

- [ ] Update CLAUDE.md to reflect actual architecture
- [ ] Fix any broken mini app flows discovered during testing
- [ ] Onboard 2-3 pitchers in person (walk through, get feedback)
- [ ] Set up Supabase dashboard for quick team-level monitoring
- [ ] Document deployment + backup procedures (Supabase handles persistence, but document the new flow)

---

## Future Considerations (Post-Sprint)

These are real but not urgent. Captured here so they don't get lost.

- **WHOOP API integration** — Pull real sleep, HRV, recovery scores. Requires OAuth flow and pitcher consent. High value for triage accuracy.
- **Coach dashboard** — Staff-facing view showing team readiness, flag levels, concerning trends. Depends on Supabase cross-pitcher queries.
- **Generalization** — Multi-team support, configurable templates, white-label potential. Requires tenant isolation in Supabase. Only pursue after UChicago adoption is solid.
- **Push notifications** — Mini app push for morning check-in reminder (supplement Telegram notifications).
- **Outing data integration** — If pitch tracking data (Trackman/Rapsodo) becomes available, ingest it alongside subjective reports.

---

## Technical Debt to Address During Sprint

- `CONTEXT_WINDOW_CHARS` documented as 500 in CLAUDE.md, actually 12000 in code — update docs
- `context.md` rebuild logic is complex and fragile — Supabase migration simplifies this (query recent entries directly instead of maintaining a text file)
- Exercise library YouTube links have gaps (`unmatched_youtube.csv` exists) — fill during Phase 4
- Templates reference exercise IDs that must exist in library — add validation
- No error handling for concurrent bot + API writes to same pitcher — Supabase transactions solve this

---

## Success Metrics

After this sprint, we should see:
1. **Data durability** — Zero risk of data loss on redeploy
2. **State coherence** — Bot and mini app share the same view of each pitcher's state
3. **Check-in quality** — Pitchers report the interaction feels more like talking to a coach
4. **Visible progress** — At least 3 pitchers reference their trend data or insights unprompted
5. **Daily active check-ins** — Target: 6+ of 12 pitchers checking in daily within 2 weeks of push
