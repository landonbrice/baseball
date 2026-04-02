# Pitcher Training Model & Plan Quality Overhaul

> Design spec — 2026-04-01
> Status: Approved for implementation planning

## Problem Statement

Plans feel generic. The system personalizes based on **who you are** (profile) and **how you feel today** (triage), but has almost zero data on **what you actually did** — no weights lifted, no exercise preferences, no "I hate front squats," no "my gym doesn't have a landmine." Pitchers can't shape their own plans, and the system starts from scratch every morning instead of maintaining a running model of each pitcher's week.

Relievers and low-usage pitchers are especially underserved: the system doesn't track when they threw bullpens or appeared in games, so it can't proactively suggest the right recovery or training focus the next day.

### Core Principles

1. **The system gathers what it can, asks only what it can't derive.** Game appearances and pitch counts are scraped automatically. Recovery windows are inferred. The bot asks only for information that isn't public or derivable (next bullpen date, how the arm feels).
2. **Every interaction makes the next plan better.** Swaps, completions, skips, and coach conversations all feed a persistent pitcher model that compounds over time.
3. **The coach leads with a suggestion, not a question.** Morning notifications propose a plan direction with confidence, not "what do you want to do today?"

## Architecture Overview

Five interconnected systems, built in phases:

```
┌─────────────────────────────────────────────────────┐
│                  Data Sources                        │
│  Game scraper · Check-in · Exercise completion ·     │
│  Inline swaps · Coach conversation · WHOOP           │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│           Pitcher Training Model (Supabase)          │
│  Working weights · Preferences · Equipment ·         │
│  Swap history · Weekly state · Movement balance      │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│              Plan Construction (Python)              │
│  Exercise pool + pitcher model + triage + templates  │
│  → Structurally correct plan                         │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│              LLM Review Pass (DeepSeek)              │
│  Reviews plan for coherence, feel, arc ·             │
│  Adjusts prescriptions · Writes narrative/notes      │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│              Mini-App UI (React)                     │
│  DailyCard · Inline swap (Approach D) ·              │
│  Coach bridge · Mutation preview                     │
└─────────────────────────────────────────────────────┘
```

---

## System 1: Consolidated Pitcher Training Model

### What It Replaces

The `active_flags` table is absorbed. Its fields (`current_arm_feel`, `current_flag_level`, `days_since_outing`, `phase`, `active_modifications`) move into the pitcher training model. One fewer table, one source of truth.

The `weekly_summaries` table is enriched with structured data alongside the existing LLM narrative. No more recomputing weekly aggregations on every UI load.

`build_week_snapshot()` in `progression.py` shifts from a read function (recompute on page load) to a write function (update model after check-in).

### Schema: `pitcher_training_model`

```sql
CREATE TABLE pitcher_training_model (
  pitcher_id TEXT PRIMARY KEY REFERENCES pitchers(id),

  -- Absorbed from active_flags --
  current_arm_feel        INTEGER,
  current_flag_level      TEXT,         -- green/yellow/red/modified_green
  days_since_outing       INTEGER,
  last_outing_date        DATE,
  last_outing_pitches     INTEGER,
  phase                   TEXT,
  active_modifications    TEXT[],

  -- Exercise intelligence --
  working_weights         JSONB DEFAULT '{}',
    -- { "ex_001": 275, "ex_002": 185 }
  exercise_preferences    JSONB DEFAULT '{}',
    -- { "ex_002": "dislike", "ex_007": "prefer" }
    -- Inferred from swap history (3+ swaps away = dislike)
    -- and explicit feedback via coach conversation
  equipment_constraints   TEXT[] DEFAULT '{}',
    -- ["no_landmine", "no_cable_machine", "no_nordic_bench"]
    -- Set via onboarding, coach conversation, or "No equipment" swap reason
  recent_swap_history     JSONB DEFAULT '[]',
    -- Last 30 swaps: [{ date, from_id, to_id, reason, source }]
    -- source: "inline_swap" or "coach_suggestion"

  -- Weekly arc --
  current_week_state      JSONB DEFAULT '{}',
    -- {
    --   week_start: "2026-03-31",
    --   days: [
    --     { date: "2026-03-31", threw: false, lifted: true,
    --       lift_focus: "lower", throw_type: null, throw_intensity: null,
    --       exercises_completed: ["ex_001", "ex_007"],
    --       exercises_skipped: ["ex_002"],
    --       exercises_swapped: [{ from: "ex_013", to: "ex_011" }]
    --     }
    --   ],
    --   movement_pattern_tally: { hip_hinge: 3, squat: 2, push: 4, pull: 6, core: 4 },
    --   throwing_load: { total_throws: 140, sessions: 3, max_intensity: 85 },
    --   next_day_suggestion: {
    --     focus: "recovery_upper",
    --     throw_suggestion: "recovery",
    --     reasoning: "Day after bullpen — recovery mode",
    --     confidence: "high"
    --   }
    -- }

  updated_at              TIMESTAMPTZ DEFAULT now()
);
```

### Schema: `weekly_summaries` (enriched, existing table)

```sql
ALTER TABLE weekly_summaries ADD COLUMN IF NOT EXISTS
  avg_arm_feel            FLOAT,
  avg_sleep               FLOAT,
  exercise_completion_rate FLOAT,
  exercises_skipped       JSONB,
    -- { "ex_002": 3, "ex_007": 2 } — count of times skipped that week
  throwing_sessions       INTEGER,
  total_throws            INTEGER,
  flag_distribution       JSONB,
    -- { "green": 5, "yellow": 1, "red": 0 }
  movement_pattern_balance JSONB;
    -- { "hip_hinge": 6, "squat": 4, "push": 8, "pull": 12, "core": 8 }
```

### How the Model Gets Updated

| Event | What Updates |
|-------|-------------|
| Check-in completed | `current_arm_feel`, `current_flag_level`, `phase`, today's day entry in `current_week_state.days` |
| Exercise completed | `current_week_state.days[today].exercises_completed`, `movement_pattern_tally` |
| Exercise skipped (end-of-day rollover, midnight CT) | `current_week_state.days[today].exercises_skipped`, `exercise_preferences` (inferred after pattern) |
| Inline swap | `recent_swap_history`, `current_week_state.days[today].exercises_swapped`, `exercise_preferences` (after 3+ swaps from same exercise → "dislike") |
| Equipment constraint swap | `equipment_constraints` (persists permanently until removed) |
| Coach conversation with plan mutation | `recent_swap_history`, preferences if coach explicitly sets them |
| Outing report | `last_outing_date`, `last_outing_pitches`, `days_since_outing` reset to 0, `current_week_state.days[today].threw/throw_type/throw_intensity` |
| Game scraper detects appearance | Same as outing report, populated automatically |
| Weight logged (future) | `working_weights` |
| Week rolls over (Monday) | `current_week_state` resets, previous week writes structured data to `weekly_summaries` |
| Daily increment | `days_since_outing` incremented (same as current `active_flags` logic) |

### How It Feeds Plan Generation

Current flow:
```
exercise_pool.build() → filter by injury/rotation → pick by freshness
```

New flow:
```
read pitcher_training_model →
  exercise_pool.build() →
    filter by injury/rotation/contraindications (unchanged) →
    filter out equipment_constraints →
    filter out "dislike" preferences →
    boost "prefer" preferences in scoring →
    score by freshness + preference + movement pattern gaps this week →
    pick with weekly balance awareness
```

The exercise pool builder gains three new filter/scoring inputs from the model. The existing injury, rotation_day_usage, and contraindication filters remain unchanged.

### What Gets Simpler in the Codebase

| Current | After |
|---------|-------|
| `context_manager.py` has ~6 functions reading/writing `active_flags` | Point at `pitcher_training_model` instead |
| `build_week_snapshot()` recomputes on every page load | Reads precomputed `current_week_state` |
| Trend endpoint groups raw entries by ISO week | Reads structured `weekly_summaries` |
| `analyze_progression()` re-derives arm feel trends from raw entries | Reads `current_week_state` + recent `weekly_summaries` |
| `active_flags` table | Dropped (absorbed) |

---

## System 2: Exercise Swap UI (Approach D — Coach Hybrid)

### Interaction Flow

Two speeds, same mutation format:

**Fast path ("Just swap it"):**
```
Tap swap button on exercise →
  Reason pills appear: [No equipment] [Doesn't feel right] [Just swap it] →
  Pitcher taps "Just swap it" →
  3-4 alternatives appear instantly (no LLM call) →
  Pitcher taps one →
  Exercise replaced in plan immediately →
  Swap recorded in pitcher_training_model
```

**Learning path ("No equipment" or "Doesn't feel right"):**
```
Tap swap button on exercise →
  Reason pills appear →
  Pitcher taps "No equipment" →
  Inline mini-chat: auto-sent message "No equipment for Nordic Curl — can you swap it?" →
  Coach responds with contextual alternatives + reasoning →
  Pitcher taps preferred alternative →
  Exercise replaced in plan immediately →
  Swap + reason recorded in pitcher_training_model →
  Equipment constraint persisted (future plans skip this exercise)
```

### API: `GET /api/exercises/{exercise_id}/alternatives`

Query params: `pitcher_id`, `date`, `reason` (optional)

Returns 3-4 alternative exercises, selected by:
1. Same `category` as the original exercise
2. Overlapping `muscles_primary`
3. Not in `rotation_day_usage.avoid` for today's rotation day
4. Not contraindicated for this pitcher's injury history
5. Not in `equipment_constraints`
6. Not already in today's plan
7. Sorted by: preference score (`prefer` > neutral > `dislike`) + freshness (not used in last 7 days) + `recommended` for today's rotation day

Response shape:
```json
{
  "alternatives": [
    {
      "exercise_id": "ex_011",
      "name": "Glute Ham Raise",
      "rx": "3×6",
      "match_reason": "Same muscles — posterior chain",
      "tag": "Best match",
      "youtube_url": "https://..."
    }
  ]
}
```

### API: `POST /api/pitcher/{id}/swap-exercise`

Body:
```json
{
  "date": "2026-04-01",
  "from_exercise_id": "ex_013",
  "to_exercise_id": "ex_011",
  "reason": "no_equipment",
  "source": "inline_swap"
}
```

Server actions:
1. Update `daily_entries[date].plan_generated` — replace exercise in lifting block
2. Append to `pitcher_training_model.recent_swap_history`
3. Update `current_week_state.days[today].exercises_swapped`
4. If reason is `no_equipment` → add to `equipment_constraints` (permanent)
5. If this exercise has been swapped away 3+ times → set `exercise_preferences[from_id]` to `"dislike"`
6. Return updated plan block for UI re-render

### UI Behavior

- Swap icon appears on each exercise in the **lifting block only** (warmup, arm care, and post-throw are curated protocols — no swaps)
- Tapping shows reason pills inline (below the exercise row)
- Alternatives appear in a compact panel (same visual as Approach D mockup)
- One tap to swap — animation transitions the exercise row
- Post-swap: new exercise shows with subtle "Swapped" badge and "was: [original]" line
- The rest of the lifting block stays visible but faded during swap selection

---

## System 3: Coach-to-Plan Bridge

### The Problem

Today, coach chat and plan rendering are disconnected. A pitcher can ask the coach to change their plan, get a text response with suggestions, but the DailyCard never updates.

### Solution: Plan Mutation Messages

When a coach conversation involves plan changes, the LLM returns a structured `plan_mutation` alongside its text response.

### Mutation Format

```json
{
  "type": "plan_mutation",
  "message": "Your pull ratio is solid — let's swap the Pallof Press for a heavier cable row and add an RDL set.",
  "mutations": [
    { "action": "swap", "from_exercise_id": "ex_044", "to_exercise_id": "ex_021", "rx": "3×8 @ 135" },
    { "action": "add", "exercise_id": "ex_005", "rx": "3×8 @ 185", "after_exercise_id": "ex_023" },
    { "action": "remove", "exercise_id": "ex_032" },
    { "action": "modify", "exercise_id": "ex_001", "rx": "3×3 @ 315", "note": "Deload week" }
  ]
}
```

Four mutation types: `swap`, `add`, `remove`, `modify`. Same format used by inline swaps (just a single `swap` mutation).

### Interaction Flow

**From the lifting block (inline coach):**
```
Pitcher taps "Refine with Coach" button on lifting section →
  Inline coach panel opens below the block →
  Preloaded context: current exercises, pitcher model, weekly state →
  Pitcher types request →
  Coach responds with text + mutation preview →
  UI shows diff: "+ Inverted Row 3×10" / "Pallof Press → Cable Row 3×8" →
  [Apply Changes] [Keep Current] buttons →
  Pitcher taps Apply →
  Mutations applied to daily_entry, pitcher_model updated →
  DailyCard re-renders with new exercises
```

**From the Coach tab (full page):**
```
Pitcher navigates to Coach tab (optionally from lifting block with context) →
  Same conversation, bigger canvas →
  Mutation preview shows as a card in the chat →
  Pitcher taps Apply →
  Changes persist to daily_entry →
  When pitcher navigates back to Home, DailyCard reflects changes on reload
```

### API Changes

`POST /api/chat` response gains an optional `mutations` field:

```json
{
  "response": "Your pull ratio is solid — let's swap...",
  "plan_context": { ... },
  "mutations": [
    { "action": "swap", "from_exercise_id": "ex_044", "to_exercise_id": "ex_021", "rx": "3×8 @ 135" }
  ]
}
```

New endpoint: `POST /api/pitcher/{id}/apply-mutations`

Body:
```json
{
  "date": "2026-04-01",
  "mutations": [ ... ],
  "source": "coach_suggestion",
  "chat_message_id": "msg_123"
}
```

Server applies each mutation to the daily entry's `plan_generated`, records in pitcher model, returns updated plan.

### LLM Prompt Addition

The coach/QA prompt gains a new instruction block:

```
When the pitcher asks to change their plan (add, remove, swap, or modify exercises),
respond with your reasoning AND include a plan_mutation JSON block:

{
  "type": "plan_mutation",
  "mutations": [
    { "action": "swap|add|remove|modify", "exercise_id": "ex_###", ... }
  ]
}

Rules:
- Only reference exercises from the exercise library (ex_### format)
- Swap alternatives must be same category as the original
- Respect injury contraindications — never suggest contraindicated exercises
- Check equipment_constraints from the pitcher model before suggesting
```

---

## System 4: Proactive Weekly Model

### Game Data Scraper

A scheduled job (runs after games, ~11pm CT) scrapes the UChicago athletics site for:
- Which pitchers appeared
- Innings pitched
- Pitch count (if available, otherwise estimate ~15 pitches per IP)
- Date

This data feeds directly into the pitcher training model:
- `last_outing_date`, `last_outing_pitches` updated
- `days_since_outing` reset to 0
- `current_week_state.days[game_date]` updated with `threw: true`, `throw_type: "game"`, `throw_intensity: 100`

For pitchers whose game data is scraped, the morning notification the next day leads with context:

> "Saw you got 1.2 innings last night, 28 pitches. Recovery day — light arm care, upper body pulls, recovery throwing. How's the arm?"

### Next-Day Suggestion Logic

`compute_next_day_suggestion()` runs after every check-in, outing report, and game scrape. It writes to `pitcher_training_model.current_week_state.next_day_suggestion`.

**For relievers (no fixed rotation):**

```python
def compute_reliever_suggestion(model, profile):
    week = model.current_week_state
    last_throw = most_recent_throw(week.days)

    if not last_throw:
        # No throwing this week — ready day
        return { focus: "full_body", throw_suggestion: "hybrid_a",
                 reasoning: "No throwing load this week — full session",
                 confidence: "medium" }

    days_since = days_between(last_throw.date, tomorrow)

    if last_throw.throw_type in ("game", "bullpen"):
        if days_since == 1:
            return { focus: "recovery_upper", throw_suggestion: "recovery",
                     reasoning: f"Day after {last_throw.throw_type}",
                     confidence: "high" }
        elif days_since == 2:
            return { focus: "lower_strength", throw_suggestion: "hybrid_b",
                     reasoning: "2 days post-throw, rebuilding",
                     confidence: "medium" }
        elif days_since >= 3:
            return { focus: "upper_strength", throw_suggestion: "hybrid_a",
                     reasoning: f"{days_since} days since last appearance — full intensity available",
                     confidence: "medium" }

    if last_throw.throw_type == "hybrid_a":
        return { focus: "lower_power", throw_suggestion: "recovery",
                 reasoning: "High-intent throw yesterday — lower body + recovery throw",
                 confidence: "medium" }

    # Factor in weekly movement gaps
    patterns = week.movement_pattern_tally
    if patterns.get("pull", 0) < patterns.get("push", 0):
        suggestion.notes = "Pull deficit — emphasize pulls"

    return suggestion
```

**For starters (existing rotation enhanced):**

The current `days_since_outing` → rotation day mapping still works. The weekly model enriches it with:
- Movement pattern gap detection ("pull deficit this week")
- Throwing load awareness ("high volume long toss yesterday — lighter today")
- Deload detection ("third consecutive heavy squat week")

**Confidence levels determine the morning message format:**

| Confidence | Morning Message |
|-----------|-----------------|
| `high` | Leads with suggestion: "Recovery upper today after yesterday's pen. How's the arm?" |
| `medium` | Leads with suggestion but softer: "Thinking lower strength today — you're 2 days out. Sound right?" |
| `low` | Falls back to current flow: "How's the arm? What are you thinking for today?" |

### Check-In Flow Changes

Current:
```
Arm feel → Sleep → Energy → Lift preference → Throw intent → Generate plan
```

New (when suggestion confidence is high):
```
Morning message leads with plan direction →
  Arm feel buttons (1-5) →
  If arm feel ≥ 3: "Got it — generating your [suggested focus] day" →
    Plan generates with pre-set direction, no lift preference question needed
  If arm feel < 3: triage overrides as usual, may change direction
```

The check-in is shorter. The system already knows the direction; it just needs the arm feel to confirm or override via triage.

---

## System 5: LLM Review Pass

### Role Shift

The LLM moves from **plan architect** to **coaching reviewer**. Python constructs a structurally correct plan. The LLM reviews it with the full pitcher context and makes judgment-call adjustments.

### Two-Pass Plan Generation

**Pass 1 — Python construction (exercise_pool + pitcher_model + triage):**
- Select exercises from pool (filtered by model preferences, equipment, injury)
- Apply prescriptions based on training intent
- Build warmup, arm care, throwing blocks from templates
- Structure the plan as JSON

**Pass 2 — LLM review:**

The LLM receives:
```
## Today's Plan (constructed)
[Full exercise list with rx, organized by block]

## Why It Was Built This Way
- Pitcher model: preferences, working weights, recent swaps, equipment constraints
- Weekly state: what happened this week, movement pattern tally, throwing load
- Triage: flag level, modifications, reasoning
- Next-day suggestion: focus, reasoning, confidence

## Your Job
1. Review for coherence:
   - Movement pattern balance within today's session
   - Prescription appropriateness given recent history and arm feel
   - Exercise pairing logic (antagonist pairing, no redundancy)

2. Make adjustments (you may):
   - Modify prescriptions (sets, reps, intensity) — cite reasoning
   - Swap exercises within the same category — cite reasoning
   - Reorder exercises within a block
   - Flag a concern for the pitcher in notes

3. You may NOT:
   - Add exercises from outside the pre-selected pool
   - Remove exercises without replacement
   - Change the throwing day type (triage controls this)
   - Override injury contraindications

4. Write:
   - morning_brief: 2-3 sentences referencing specific decisions and pitcher context
   - notes: 3-4 actionable items specific to today
   - soreness_response: if arm_report mentions discomfort

Return the adjusted plan as JSON with a "review_reasoning" field explaining any changes you made.
```

### What This Achieves

| Before (current) | After |
|-------------------|-------|
| LLM receives exercises and must structure the entire plan | LLM receives a structured plan and reviews it |
| LLM can hallucinate exercise IDs | Exercise IDs are pre-validated; LLM can only swap within the pool |
| Morning brief is often generic | Morning brief references specific model data (swaps, weekly patterns, recovery trajectory) |
| Notes are filler | Notes are informed by weekly state and pitcher model |
| LLM timeout → template fallback (no personality) | LLM timeout → Python-constructed plan still ships (correct if not personalized), narrative falls back to template |
| Prescriptions don't reflect actual training history | LLM sees working weights and recent loads from pitcher model |

### Fallback

If the LLM times out or returns unparseable output, the Python-constructed plan ships as-is with a template narrative. This is the same fallback pattern as today, but the base plan is now better because it's informed by the pitcher model (preferences, equipment, weekly state) rather than just the exercise pool's freshness scoring.

---

## Implementation Phases

### Phase 1: Data Foundation
- Create `pitcher_training_model` table
- Migrate `active_flags` data into it
- Enrich `weekly_summaries` with structured columns
- Update `context_manager.py` to read/write `pitcher_training_model` instead of `active_flags`
- Update all references to `active_flags` across codebase
- `build_week_snapshot()` becomes a write function (update model after events)
- Drop `active_flags` table

### Phase 2: Exercise Swap UI + Model-Aware Pool
- `GET /api/exercises/{id}/alternatives` endpoint
- `POST /api/pitcher/{id}/swap-exercise` endpoint
- Approach D swap UI in DailyCard (reason pills, fast path, learning path)
- Exercise pool builder reads pitcher model (preferences, equipment, movement gaps)
- Swap history → preference inference logic

### Phase 3: LLM Review Pass + Proactive Suggestions
- Refactor `plan_generator.py`: Python construction → LLM review (two-pass)
- New plan generation prompt (reviewer role, not architect)
- `compute_next_day_suggestion()` logic
- Morning notification uses suggestion (high/medium confidence → lead with direction)
- Shortened check-in flow when suggestion confidence is high

### Phase 4: Coach Bridge + Game Scraper
- `plan_mutation` response type in chat endpoint
- `POST /api/pitcher/{id}/apply-mutations` endpoint
- Mutation preview UI (diff card in coach chat)
- Inline coach panel on lifting block
- UChicago game scraper (scheduled job, feeds pitcher model)
- Auto-detection of reliever appearances

### Dependencies Between Phases

```
Phase 1 ──→ Phase 2 (swap needs pitcher model to filter/score)
Phase 1 ──→ Phase 3 (LLM review needs model context, suggestions need week state)
Phase 2 ──→ Phase 4 (coach bridge uses same mutation format as swaps)
Phase 3 ──→ Phase 4 (game scraper feeds next-day suggestions)
```

Phase 1 is the foundation. Phases 2 and 3 can be built in parallel after Phase 1. Phase 4 depends on both.

---

## Key Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Migration from `active_flags` breaks existing code | Comprehensive search of all `active_flags` references before migration. Feature flag for cutover. |
| LLM review pass adds latency to plan generation | Python-constructed plan is the fallback. If LLM is slow, pitcher gets a good plan immediately, narrative arrives async. |
| Game scraper breaks if athletics site changes format | Scraper is best-effort. If it fails, system falls back to manual outing reports (current behavior). Scraper failures are logged, not user-facing. |
| Equipment constraints accumulate incorrectly | Equipment constraints can be cleared via coach conversation ("I have a Nordic bench now"). Surfaced on Profile page for manual review. |
| Preference inference from swaps is too aggressive | 3-swap threshold within a 30-day rolling window before marking "dislike." Preferences are suggestions to the pool scorer, not hard filters — a "dislike" exercise can still appear if the pool is thin. Preferences decay after 90 days without a swap. |

## Files Affected

### Modified (significant changes)
- `bot/services/context_manager.py` — active_flags → pitcher_training_model
- `bot/services/exercise_pool.py` — model-aware filtering and scoring
- `bot/services/plan_generator.py` — two-pass architecture (construct → review)
- `bot/services/checkin_service.py` — model updates, shortened check-in flow
- `bot/services/progression.py` — build_week_snapshot writes to model
- `bot/services/db.py` — new CRUD for pitcher_training_model
- `bot/main.py` — game scraper job, updated morning notification
- `bot/prompts/plan_generation_structured.md` — reviewer role prompt
- `api/routes.py` — new endpoints (alternatives, swap, mutations)
- `mini-app/src/components/DailyCard.jsx` — swap UI, coach button
- `mini-app/src/pages/Home.jsx` — inline coach panel
- `mini-app/src/pages/Coach.jsx` — mutation preview cards

### New Files
- `bot/services/game_scraper.py` — UChicago athletics scraper
- `bot/services/weekly_model.py` — next-day suggestion logic, week state management
- `mini-app/src/components/ExerciseSwap.jsx` — Approach D swap component
- `mini-app/src/components/MutationPreview.jsx` — coach mutation diff card

### Removed
- `active_flags` table (after migration)
- `active_flags` references in `context_manager.py`, `db.py`, `checkin_service.py`, `triage.py`
