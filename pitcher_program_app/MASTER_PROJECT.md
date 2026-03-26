> **SUPERSEDED:** This document is historical. See `/PROJECT_VISION.md` for the current vision and sprint plan (March 2026).

# MASTER PROJECT DOCUMENT: UChicago Pitcher Training System
# Claude Code: Read this file FIRST before touching anything else.

---

## WHAT THIS IS

A complete individualized training intelligence system for the University of Chicago baseball pitching staff. Deployed as a Telegram bot with an in-app Mini App dashboard. Each pitcher gets personalized daily lifting programs, arm care protocols, throwing program guidance, recovery programming, evidence-based Q&A, and longitudinal tracking.

## WHAT THE BOT OWNS vs. DOESN'T OWN

### Bot OWNS:
- Individualized lifting programs (off-season and in-season, periodized by rotation day)
- Individualized arm care protocols (FPM work, scapular stability, shoulder health)
- Throwing warm-up and recovery routines (J-bands, wrist weights, plyo ball drills)
- Recovery programming coordinated with lifting and pitching schedule
- Daily readiness triage (arm feel, sleep, soreness → Green/Yellow/Red)
- Post-outing recovery protocols
- Evidence-based Q&A (pitcher asks a question → bot answers from research base or searches web)
- Longitudinal tracking (arm feel trends, progression, pattern detection)
- Individual modifications based on injury history and recovery data
- Lifting + arm care coordination (programs work in conjunction, not in isolation)

### Bot DOES NOT OWN:
- Mechanical/pitching instruction
- Medical diagnosis or treatment
- Supplement/medication recommendations

---

## FILE CLASSIFICATION

### SOURCE MATERIAL (Reference only — do NOT deploy as system files)
These informed the research base but are not part of the running system:
```
./Gemeni Researching Lifting.md    — Gemini v3 exercise database output
./FPM.md                           — Gemini deep-dive on flexor-pronator mass
./research_gap_analysis.md         — Gap analysis between research sources
./Lifting/*.gsheet                 — Existing team lift programs (context only)
```

### SYSTEM COMPONENTS (Core data files the bot reads and uses)
```
./files/ARCHITECTURE.md                — Project structure reference
./files/exercise_library_schema.json   — Exercise database (schema + examples, needs populating)
./files/starter_7day_template.json     — 7-day rotation template
./files/pitcher_profile_schema.json    — Individual pitcher profile schema
./files/daily_log_schema.json          — Daily log entry schema
./FINAL_research_base.md              — Complete synthesized research base (Tier 1 knowledge)
```

### TO BE CREATED (What Claude Code builds)
```
bot/
  main.py                    — Telegram bot entry point
  handlers/
    daily_checkin.py         — Morning check-in flow (arm feel, sleep, soreness)
    post_outing.py           — Post-outing protocol generation
    qa.py                    — Question answering against knowledge base
    logging.py               — Workout/activity logging from pitcher input
  services/
    plan_generator.py        — Takes template + pitcher context → daily protocol
    triage.py                — Green/Yellow/Red flag system + decision logic
    knowledge_retrieval.py   — Search research base → answer questions
    web_research.py          — Web search fallback when knowledge base lacks answer
    context_manager.py       — Reads/writes/updates pitcher context files
    progression.py           — Tracks progression, detects patterns, suggests adjustments
  prompts/
    system_prompt.md         — Core bot personality and behavior rules
    plan_generation.md       — Prompt template for daily protocol generation
    qa_prompt.md             — Prompt template for answering pitcher questions
    triage_prompt.md         — Prompt template for readiness assessment

data/
  knowledge/
    FINAL_research_base.md   — Tier 1: Curated core knowledge (COPY from root)
    extended_knowledge.md    — Tier 2: Bot-discovered knowledge (starts empty)
    exercise_library.json    — Full exercise database (POPULATE from schema)
  templates/
    starter_7day.json        — Starter rotation template (COPY from files/)
    reliever_flexible.json   — Reliever template (TO CREATE)
    recovery_protocols.json  — Post-outing and daily recovery protocols (TO CREATE)
  pitchers/
    example_pitcher.json         — Example profile (COPY from files/)
    example_pitcher_context.md   — Example growing context file
    example_pitcher_log.json     — Example daily log

mini-app/
  public/
    manifest.json              — PWA manifest (installable on home screen)
  src/
    App.jsx                    — Entry point + routing
    api.js                     — Data fetching layer (reads pitcher JSON/logs)
    pages/
      Home.jsx                 — Week view + today's card + arm feel trend
      ExerciseLibrary.jsx      — Searchable exercise browser with video embeds
      LogHistory.jsx           — Calendar view of past days
      Profile.jsx              — View/edit pitcher profile + preferences
    components/
      WeekStrip.jsx            — 7-day color-coded rotation strip
      DailyCard.jsx            — Single day: exercises with checkboxes + video links
      ArmFeelInput.jsx         — Quick arm feel logger (1-5 buttons)
      TrendChart.jsx           — Arm feel line chart (last 4 weeks)
      ExerciseCard.jsx         — Exercise detail: name, muscles, protocol, video
      FlagBadge.jsx            — Green/Yellow/Red status indicator
  package.json

scripts/
  intake_to_profile.py       — Google Form response → pitcher profile JSON + context .md
  populate_exercise_library.py — Parse research base → full exercise_library.json
  seed_test_pitcher.py       — Create a test pitcher for development
```

---

## TECHNICAL STACK

### Bot Backend
- **Language:** Python 3.11+
- **Telegram library:** python-telegram-bot (v20+)
- **LLM API:** Start with Claude Haiku for cost efficiency during testing. Structure API calls so the model is swappable (DeepSeek, Sonnet, GPT-4o-mini) via a single config variable.
- **Data storage:** JSON files + Markdown context files. No database. File-based storage is sufficient for 15 pitchers.
- **Hosting:** Railway, Render, or a cheap VPS. Bot runs as a long-polling or webhook process.

### Mini App Dashboard
- **Framework:** React (single-file .jsx artifacts where possible)
- **Styling:** Tailwind CSS
- **Hosting:** Vercel or Netlify (free tier)
- **Data source:** Reads from the same JSON files the bot writes to (served via a simple API endpoint or static file hosting)
- **Registration:** Registered as a Telegram Mini App (opens inside Telegram via a button in the bot chat)

### LLM API Architecture
```python
# Config — swap model by changing one line
LLM_CONFIG = {
    "provider": "anthropic",  # or "deepseek", "openai"
    "model": "claude-haiku-4-5-20251001",
    "max_tokens": 1000,
    "temperature": 0.3  # Low temp for consistent, evidence-based outputs
}

# Every LLM call follows this pattern:
def generate_response(system_prompt: str, user_message: str, context: str) -> str:
    """
    system_prompt: from prompts/ directory
    user_message: what the pitcher said
    context: pitcher's profile + context.md + relevant research base sections
    """
    # Construct messages with context-stuffed system prompt
    # Call LLM API
    # Return response text
```

### Context Window Management (CRITICAL)
Do NOT dump the entire research base into every API call. That wastes tokens and money.

```
For DAILY PROTOCOL generation:
  System prompt (~500 tokens)
  + Pitcher profile JSON (~400 tokens)
  + Pitcher context.md summary (~300 tokens)
  + Relevant template day (~300 tokens)
  + Relevant exercises from library (~400 tokens)
  = ~1,900 tokens in → ~800 tokens out
  
For Q&A:
  System prompt (~500 tokens)
  + Pitcher context.md summary (~300 tokens)
  + RETRIEVED sections from research base (~500-1000 tokens, not the whole file)
  + Conversation history (~200 tokens)
  = ~1,500-2,000 tokens in → ~500 tokens out

For TRIAGE:
  System prompt (~300 tokens)
  + Pitcher profile (flags + injury history only) (~200 tokens)
  + Today's readiness inputs (~100 tokens)
  + Triage rules (~300 tokens)
  = ~900 tokens in → ~200 tokens out
```

Use simple keyword/section matching to retrieve relevant chunks from the research base rather than embedding the whole thing. Full RAG with vector embeddings is overkill for this scale.

---

## UI SPECIFICATION

### Architecture: Telegram Bot + Web Dashboard PWA

**Telegram Bot** = primary daily interface (80% of interactions)
**Web Dashboard** = visual companion (20% — weekly view, trends, exercise library)

Both read/write to the same data files. Pitcher uses Telegram for daily check-ins, logging, Q&A. Dashboard for reviewing plans, checking trends, browsing exercises with videos.

### Telegram Message Design

The bot sends structured, formatted messages using Telegram's MarkdownV2 or HTML parsing mode. Each protocol message follows this pattern:

```
🟢 Day 3 — Recovery + Bullpen

ARM CARE (post-pen):
▫️ Cross-body stretch — 3×30s/side [▶](youtube_link)
▫️ Rhythmic stab — 3×30s [▶](youtube_link)
▫️ Rice bucket — 3×60s
▫️ Wrist flexion — 2×12 light [▶](youtube_link)

🎯 Pen: 25-30 pitches, recovery intent
```

Below each protocol message, attach an InlineKeyboardMarkup with buttons:
- Row 1: `[✅ All done]` `[⏭ Skipped some]`
- Row 2: `[📊 View dashboard]` (opens Mini App / web dashboard link)

For the morning check-in, use inline keyboard for arm feel:
- `[1 😣]` `[2]` `[3 😐]` `[4]` `[5 💪]`

YouTube links render as native Telegram link previews when sent as standalone URLs. When embedded in protocol messages, use inline hyperlinks `[▶ video](url)` to keep messages compact.

### Web Dashboard (PWA)

Built as a React app, hosted on Vercel (free tier). Registered as a Telegram Mini App so it can also open inside Telegram via the `[📊 View dashboard]` button.

Can be added to phone home screen as a PWA for native-app feel.

**Dashboard pages:**

1. **Home / Week View**
   - Pitcher name, role, current flag status (Green/Yellow/Red badge)
   - 7-day rotation strip (color-coded: game day red, strength amber, speed blue, recovery gray, pre-start light)
   - Today's card expanded: exercises with checkboxes + video links
   - Arm feel trend chart (line graph, last 4 weeks)

2. **Exercise Library**
   - Searchable/filterable list of all exercises
   - Each exercise: name, muscles, protocol, video embed, when to use
   - Filter by category: FPM, shoulder, lower body, core, etc.

3. **Log History**
   - Calendar view of past days
   - Tap a day → see what was prescribed, what was completed, arm feel, notes

4. **Profile**
   - View/edit intake data (injury history, role, goals)
   - Notification preferences
   - Current rotation day display

**Authentication:** Telegram user ID passed via Mini App launch params. No separate login needed. For standalone web access, use a simple token/code system (bot sends a unique link).

### Onboarding Flow

**Step 1: Google Form (before bot interaction)**
Pitcher fills out intake form capturing:
- Name, year, throws (L/R)
- Role (starter/reliever), rotation length
- Injury history (free text + checkboxes for common: UCL, shoulder, lat, etc.)
- Current lifting maxes (optional)
- Mechanical focus areas (optional)
- Goals (primary, secondary)
- Telegram username (for linking)
- Notification time preference

**Step 2: Script processes form → generates pitcher files**
`intake_to_profile.py` runs on form submission:
- Creates `pitcher_xxx.json` (structured profile)
- Creates `pitcher_xxx_context.md` (initial context with intake data)
- Creates empty `pitcher_xxx_log.json`
- Maps Telegram username to pitcher_id

**Step 3: Bot first interaction (confirmation)**
When the pitcher first messages the bot (or bot sends welcome message):
```
"Hey [name], I'm set up with your info. Quick confirmation — 
you're a [starter] on a [7]-day rotation, and you've had some 
[medial elbow] history. That right?

I'll check in each morning around [8am] with your arm care plan 
for the day. After outings, just tell me 'I pitched' with your 
pitch count and how the arm feels, and I'll set up your recovery.

Any questions about how this works, just ask."
```

### Rotation Day Tracking

**The pitcher manually logs outings. The bot does NOT try to auto-track the schedule.**

When a pitcher sends "I pitched today" or "I pitched, 82 pitches, arm feels 4":
1. Bot parses the message (pitch count, arm feel if provided)
2. Resets rotation counter to Day 0
3. Generates post-outing recovery protocol
4. All subsequent days auto-increment (Day 1, Day 2, etc.)

If the bot hasn't received an outing log and it's been 8+ days since the last one (for starters), the morning check-in includes:
```
"It's been [X] days since your last logged outing. Did you pitch 
recently? I want to make sure your plan is calibrated right."
```

For relievers: bot asks "Did you throw in a game yesterday?" as part of the morning check-in on days after scheduled games, since relievers have unpredictable usage.

**The bot also accepts manual rotation day corrections:**
- "Actually I'm on Day 4" → bot adjusts
- "I got pushed back, pitching Friday not Thursday" → bot shifts the schedule

### Coach / Trainer Visibility

**MVP: Private only.** Each pitcher's data is between them and the bot. No coach dashboard at launch.

**Future (post-MVP):** 
- Opt-in team dashboard: pitcher must explicitly consent to sharing data
- Coach view shows: arm feel trends (anonymous or named), flag statuses, who's in yellow/red
- Aggregate team health metrics (average arm feel by rotation day, etc.)
- Individual pitcher detail only with pitcher's consent

**Why private first:** Pitchers will report honestly (arm feel 2, slept 5 hours, skipped exercises) only if they trust the data stays private. If the coach sees everything from day one, pitchers will game the system and report 4s and 5s regardless of how they feel. Build trust first, add transparency later.

### Notification Cadence

| Trigger | Timing | Message |
|---------|--------|---------|
| Morning check-in | Pitcher's preferred time (default 8am) | Arm feel prompt + inline keyboard |
| Post-outing prompt | 2 hours after typical game end time, OR when pitcher messages "I pitched" | Recovery protocol |
| No response follow-up | 6pm if morning check-in unanswered | "Hey, just checking in — how's the arm today?" |
| Missed day | Next morning | Rolls forward, no guilt trip. "Morning [name]. Yesterday was Day [X] — here's today's plan for Day [X+1]." |
| Arm feel concern | Immediately after arm feel ≤2 is reported | "That's lower than usual. [contextual follow-up based on history]" |
| Pattern alert | Weekly (Sunday evening) | "Quick weekly note: [observation, e.g., arm feel has been trending down / sleep has been low]" |

**Never send more than 2 unprompted messages per day.** Morning check-in + one follow-up max. Pitcher-initiated conversations have no limit.

---

## BOT PERSONALITY & BEHAVIOR

### Voice
- Knowledgeable training partner, not a coach or doctor
- Direct and evidence-based but not clinical
- Speaks like a smart teammate who reads research, not a textbook
- Uses baseball language naturally ("outing" not "pitching session", "pen" not "bullpen session")
- Concise by default, detailed when asked or when the situation warrants it

### Behavior Rules
1. **Always check context before answering.** Even simple questions like "should I stretch?" depend on who's asking, what day of rotation, and their history.
2. **Flag, don't diagnose.** "That pattern is worth getting checked out" not "You might have UCL damage."
3. **Cite the reasoning.** When making a recommendation, briefly explain why. Pitchers trust the system more when they understand the logic.
4. **Remember across conversations.** Use the context.md file to track what this pitcher has asked about, what's worked for them, and what patterns are emerging.
5. **Escalate appropriately.** Arm feel ≤2 for 2+ days → "I'd recommend talking to [trainer name] about this." Sharp pain at any point → "Stop the activity and see your trainer today."
6. **Respect the team program.** Never contradict the S&C coach's lifts. The bot's job is to wrap individualized arm care and recovery AROUND the existing program, not replace it.
7. **Be honest about uncertainty.** "The evidence on this is limited, but here's what we know..." is better than false confidence.

### Core User Flows

**Flow 1: Morning Check-In (Daily)**
```
Bot sends push notification at pitcher's preferred time (default 8am)
→ "Morning [name]. How's the arm today? (1-5)"
→ Pitcher responds with number
→ Bot asks: "How'd you sleep? (hours or 1-5 quality)"
→ Pitcher responds
→ Bot runs triage:
   - Checks rotation day, arm feel, sleep, any active flags
   - Generates today's protocol (arm care exercises, recovery work, notes)
   - Sends protocol with YouTube links for exercises
   - If Yellow/Red flag: adds caution note + modification
→ "Here's your arm care for today. [exercises with links]. 
    Any questions or anything feel off?"
```

**Flow 2: Post-Outing Protocol (Game Day)**
```
Pitcher messages bot after outing (or bot prompts at expected time)
→ Bot asks: "How'd it go? Pitch count and arm feel?"
→ Pitcher responds: "78 pitches, arm feels like a 4"
→ Bot generates post-outing protocol:
   - Immediate recovery (band work, stretches, nutrition)
   - Flags anything based on pitch count + arm feel
   - Sets up next 2-3 days of recovery plan
   - Updates pitcher log + context
→ "Nice. Here's your recovery protocol for tonight and tomorrow. 
    [protocol]. I'll check in tomorrow morning."
```

**Flow 3: Q&A (On-Demand)**
```
Pitcher messages: "Should I do lax ball work on my forearm right now?"
→ Bot checks:
   1. Pitcher context (injury history, current status, rotation day)
   2. Research base (soft tissue mobilization evidence)
   3. Previous interactions (has this come up before?)
→ Generates contextual answer
→ Updates interaction memory in context.md if relevant
```

**Flow 4: Dashboard View (Mini App)**
```
Pitcher taps "Dashboard" button in Telegram chat
→ Mini App opens inside Telegram
→ Shows:
   - This week's arm care schedule (7-day view, color-coded)
   - Today's protocol (exercises with completion checkboxes)
   - Arm feel trend (line chart, last 4 weeks)
   - Quick-log buttons (arm feel, completed exercises)
```

---

## DATA FLOW

```
                    ┌─────────────────┐
                    │  Google Form    │
                    │  (Intake)       │
                    └────────┬────────┘
                             │ intake_to_profile.py
                             ▼
              ┌──────────────────────────────┐
              │  pitcher_xxx.json (profile)   │
              │  pitcher_xxx_context.md       │
              └──────────────┬───────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
  ┌─────────────┐   ┌──────────────┐   ┌──────────────┐
  │ Telegram Bot │   │  Mini App    │   │  Log Files   │
  │             │   │  Dashboard   │   │  (.json)     │
  │ • Check-in  │──▶│ • Week view  │   │              │
  │ • Post-out  │   │ • Trends     │◀──│ Daily logs   │
  │ • Q&A       │   │ • Log input  │   │ accumulate   │
  │ • Logging   │   │              │   │ here         │
  └──────┬──────┘   └──────────────┘   └──────────────┘
         │                                     ▲
         │         ┌──────────────────┐        │
         │         │  Knowledge Base  │        │
         ├────────▶│                  │        │
         │         │ Tier 1: Research │        │
         │         │ Tier 2: Extended │        │
         │         │ Exercise Library │        │
         │         └──────────────────┘        │
         │                                     │
         └─────────────────────────────────────┘
              Bot writes to logs + context
              after every interaction
```

---

## BUILD ORDER (for Claude Code)

### Phase 1: Core Bot (Days 1-3)
1. Set up project structure (directories, config, dependencies)
2. Populate exercise_library.json from FINAL_research_base.md (the full ~40 exercises with protocols, YouTube links TBD)
3. Create the system prompt (prompts/system_prompt.md)
4. Build the Telegram bot skeleton (main.py + basic message handling)
5. Implement daily check-in flow (handlers/daily_checkin.py)
6. Implement plan_generator.py (template + context → daily arm care protocol)
7. Implement triage.py (arm feel + sleep → Green/Yellow/Red → protocol adjustments)
8. Test with a seed pitcher profile (scripts/seed_test_pitcher.py)

### Phase 2: Intelligence Layer (Days 3-5)
9. Implement post-outing flow (handlers/post_outing.py)
10. Implement Q&A flow (handlers/qa.py + knowledge_retrieval.py)
11. Implement context_manager.py (read/write/update pitcher context.md files)
12. Implement web_research.py (fallback web search when knowledge base doesn't have the answer)
13. Implement progression.py (track trends, flag patterns)
14. Build intake form → profile generator (scripts/intake_to_profile.py)

### Phase 3: Mini App Dashboard (Days 5-6)
15. Build React Mini App (WeekView, DailyCard, ArmFeelLogger, TrendChart, ExerciseCard)
16. Set up data API (simple endpoint that serves pitcher JSON/log data to the Mini App)
17. Register Mini App with Telegram BotFather
18. Style and polish

### Phase 4: Polish & Deploy (Day 7)
19. Deploy bot (Railway/Render)
20. Deploy Mini App (Vercel)
21. Onboard yourself as test pitcher
22. Test all flows end-to-end
23. Iterate on prompt quality based on real outputs

---

## KEY IMPLEMENTATION DETAILS

### Exercise Library Population
The exercise_library_schema.json has 2 example entries. It needs to be populated with ALL exercises from FINAL_research_base.md. There are ~40 exercises across 8 categories. Each entry needs:
- id, name, aliases
- category, subcategory
- muscles_primary, muscles_secondary
- pitching_relevance (one sentence)
- prescription (by mode: strength, hypertrophy, power, endurance, warmup)
- rotation_day_usage (recommended, acceptable, avoid)
- tags
- contraindications
- modification_flags (ucl_history, shoulder_impingement, etc.)
- youtube_url (leave empty for now, populate later)
- evidence_level, source_notes

### Pitcher Context File Growth
After every meaningful interaction, the bot appends to pitcher_xxx_context.md:
```python
def update_context(pitcher_id: str, update_type: str, content: str):
    """
    update_type: 'status' | 'interaction' | 'pattern' | 'flag'
    Appends timestamped entry to the appropriate section of context.md
    """
    context_path = f"data/pitchers/{pitcher_id}_context.md"
    timestamp = datetime.now().isoformat()
    entry = f"\n- [{timestamp}] ({update_type}) {content}"
    # Append to appropriate section
```

### Triage Decision Logic
```python
def triage(pitcher_profile: dict, daily_input: dict) -> dict:
    """
    Returns: {
        'flag_level': 'green' | 'yellow' | 'red',
        'modifications': [...],
        'alerts': [...],
        'protocol_adjustments': {...}
    }
    """
    arm_feel = daily_input['arm_feel']  # 1-5
    sleep_hours = daily_input.get('sleep_hours')
    days_since_outing = pitcher_profile['active_flags']['days_since_outing']
    injury_history = pitcher_profile['injury_history']
    
    # Sequential triage (from bot_intelligence_architecture.md):
    # 1. Pain > 2/10 or new swelling? → RED → medical eval
    # 2. ROM red flags? → YELLOW → mobility focus
    # 3. Grip drop vs baseline? → YELLOW → reduce forearm load
    # 4. Start within 48h? → primer session only
    # 5. None of above → full protocol per template
```

### LLM Call Pattern
```python
async def call_llm(system_prompt: str, messages: list, context: str = "") -> str:
    """
    Unified LLM call that works with any provider.
    Context is injected into the system prompt, not as a separate message.
    """
    full_system = f"{system_prompt}\n\n## PITCHER CONTEXT\n{context}"
    
    # Provider-specific API call
    if CONFIG['provider'] == 'anthropic':
        response = anthropic_client.messages.create(
            model=CONFIG['model'],
            max_tokens=CONFIG['max_tokens'],
            system=full_system,
            messages=messages
        )
        return response.content[0].text
    elif CONFIG['provider'] == 'deepseek':
        # DeepSeek-compatible call
        pass
    elif CONFIG['provider'] == 'openai':
        # OpenAI-compatible call
        pass
```

---

## WHAT SUCCESS LOOKS LIKE

### Week 1 (Launch)
- Bot sends daily check-ins to test pitcher (you)
- Generates personalized arm care protocols based on rotation day + readiness
- Answers basic questions from research base
- Logs daily data to JSON files

### Week 2-3 (Pilot)
- Onboard 2-3 teammates
- Bot handles multiple pitcher profiles simultaneously
- Context files growing with useful longitudinal data
- Mini App dashboard shows weekly plans and trends

### Month 2+ (Scale)
- Full pitching staff onboarded
- Bot detecting patterns ("your arm feel consistently dips after 80+ pitch outings")
- Extended knowledge base growing from pitcher Q&A
- Coaches/trainers can review pitcher context files for insights

---

## FILES TO READ IN ORDER

Claude Code should read these files in this exact order before writing code:

1. **This file** (MASTER_PROJECT.md) — the blueprint
2. **FINAL_research_base.md** — the complete knowledge base
3. **files/ARCHITECTURE.md** — project structure reference
4. **files/exercise_library_schema.json** — exercise data shape
5. **files/starter_7day_template.json** — template data shape
6. **files/pitcher_profile_schema.json** — pitcher profile data shape
7. **files/daily_log_schema.json** — log entry data shape

Everything else in the repo is source material / reference. Do not deploy Gemini outputs, GPT outputs, or .gsheet files as system components.
