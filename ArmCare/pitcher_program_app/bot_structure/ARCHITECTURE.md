# UChicago Pitcher Training System — Architecture Overview

## Project Structure

```
uchi-pitcher-bot/
├── data/
│   ├── templates/
│   │   ├── starter_7day.json          ← Base program: 7-day rotation starters
│   │   ├── reliever_variable.json     ← Base program: relievers (build after Gemini research)
│   │   └── recovery_protocol.json     ← Universal recovery protocols by day
│   │
│   ├── exercises/
│   │   └── exercise_library.json      ← All exercises with tags, prescriptions, YouTube links
│   │
│   ├── knowledge/
│   │   ├── research_base.json         ← Parsed Gemini output — evidence base for reasoning
│   │   ├── faq.json                   ← Common questions + evidence-based answers
│   │   └── modification_rules.json    ← If [condition] then [adjustment] logic
│   │
│   ├── pitchers/
│   │   ├── pitcher_001.json           ← Individual context files (from intake form)
│   │   ├── pitcher_002.json
│   │   └── ...
│   │
│   └── logs/
│       ├── pitcher_001_log.json       ← Daily log entries per pitcher
│       └── ...
│
├── bot/
│   ├── main.py                        ← Telegram bot entry point
│   ├── plan_generator.py              ← Takes template + pitcher context → daily plan
│   ├── logger.py                      ← Handles input parsing and log writes
│   ├── retrieval.py                   ← RAG-lite: searches knowledge base for Q&A
│   ├── whoop_integration.py           ← WHOOP API calls (you already have this)
│   └── prompts/
│       ├── system_prompt.md           ← Core system prompt for the bot
│       ├── plan_generation_prompt.md  ← Prompt template for daily plan generation
│       └── qa_prompt.md              ← Prompt template for answering pitcher questions
│
├── mini-app/
│   ├── src/
│   │   ├── App.jsx                    ← Telegram Mini App (React)
│   │   ├── WeekView.jsx              ← 7-day visual plan
│   │   ├── LogEntry.jsx              ← Quick logging UI
│   │   ├── TrendChart.jsx            ← Arm feel / recovery trends over time
│   │   └── ExerciseCard.jsx          ← Exercise detail with YouTube embed
│   └── package.json
│
├── scripts/
│   ├── intake_to_profile.py          ← Google Form response → pitcher JSON
│   ├── parse_gemini_research.py      ← Gemini output → structured JSON files
│   └── seed_exercise_library.py      ← Populate exercise library from research
│
└── README.md
```

## Data Flow

```
1. ONBOARDING
   Google Form → intake_to_profile.py → pitcher_XXX.json

2. DAILY PLAN GENERATION  
   pitcher_XXX.json + starter_7day.json + exercise_library.json + WHOOP data
     → plan_generator.py 
     → LLM generates personalized plan
     → Sends via Telegram + writes to daily log

3. PITCHER INTERACTION
   Pitcher messages bot (logs workout, asks question, reports arm feel)
     → logger.py parses input → updates daily log
     → OR retrieval.py searches knowledge base → LLM answers question

4. DASHBOARD VIEW
   Pitcher opens Mini App
     → Reads from pitcher log + current plan
     → Renders week view, trends, exercise details

5. PROGRESSION
   bot_observations in daily log accumulate
     → Bot detects patterns (e.g., "ready to increase weight")
     → Adjusts next plan generation accordingly
```

## Key Design Decisions

### Why JSON over a database?
- File-based = version controllable, inspectable, portable
- 15 pitchers × 365 days = ~5,500 log entries/year = trivially small
- Google Sheets sync as the "human-readable database" layer
- Can always migrate to Supabase later if needed

### Why Telegram Mini App over separate web app?
- Zero additional app to download or bookmark
- Opens inside the same interface where they talk to the bot
- Still just a React app — can be deployed separately later if needed
- Telegram handles auth (user identity comes from Telegram user ID)

### Why hybrid templates over pure LLM generation?
- Templates encode expert knowledge (from Gemini research + your experience)
- LLM makes bounded adjustments, not open-ended programming
- Consistent quality floor — worst case is the base template, which is solid
- Easier to audit and improve over time

### API Cost Estimate (DeepSeek or Claude Haiku)
- Daily plan generation: ~1,500 tokens in, ~800 tokens out per pitcher
- 15 pitchers × daily = ~22,500 in / ~12,000 out per day
- Q&A: estimate 5 questions/day across all pitchers = ~10,000 tokens
- **Monthly total: ~1M-1.5M tokens ≈ $1-3/month on DeepSeek, $5-10 on Haiku**
- Cost is negligible. Optimize for quality, not cost.
