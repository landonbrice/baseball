# Phase 3: LLM Review Pass + Proactive Suggestions

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor plan generation from "LLM builds entire plan" to "Python constructs plan instantly, LLM reviews/adjusts." This eliminates LLM timeout as a blocking failure (the plan ships immediately), improves plan quality by giving the LLM a reviewer role with richer context, and adds proactive next-day suggestions for relievers.

**Architecture:** `generate_plan()` is split into two passes. Pass 1 (Python, <1s) constructs a complete plan using exercise pool + pitcher model + triage — this always succeeds and is what the pitcher sees immediately. Pass 2 (LLM, async) reviews the plan for coherence, adjusts prescriptions, writes the morning brief and notes. If the LLM responds in time, the plan is enriched; if not, the Python-constructed plan is already saved. The proactive suggestion system runs `compute_next_day_suggestion()` after each check-in/outing to pre-compute tomorrow's direction.

**Tech Stack:** Python/FastAPI, DeepSeek LLM, Supabase

**Spec:** `docs/superpowers/specs/2026-04-01-pitcher-model-plan-quality-design.md` (Systems 4 & 5)

**Fixes:** Resolves check-in timeout errors ("plan generated from template due to slow AI response") by making LLM non-blocking.

---

## Current Problem

The plan generation pipeline blocks on the LLM call (90-120s timeout). When the LLM is slow:
- **Telegram:** Falls back to generic template with "slow AI response" message
- **Mini-app:** HTTP proxy times out before Python timeout fires → "something went wrong"

The fix: Python constructs the plan instantly (sub-second). LLM reviews afterward. No more blocking.

---

### Task 1: Create Next-Day Suggestion Module

**Files:**
- Create: `pitcher_program_app/bot/services/weekly_model.py`

This module computes what tomorrow's training should be based on the pitcher's week so far.

- [ ] **Step 1: Create the weekly model module**

```python
"""Weekly training model — proactive next-day suggestions.

Computes what tomorrow's training should be based on the pitcher's
week so far (throws, lifts, movement pattern balance). For relievers
without a fixed rotation, this replaces the rotation day template lookup.
"""

import logging
from datetime import datetime, timedelta
from bot.config import CHICAGO_TZ

logger = logging.getLogger(__name__)


def compute_next_day_suggestion(pitcher_profile: dict, training_model: dict) -> dict:
    """Compute a suggested training focus for tomorrow.

    Returns dict with: focus, throw_suggestion, reasoning, confidence.
    Confidence: "high" (lead with suggestion), "medium" (suggest softly),
                "low" (fall back to asking).
    """
    role = pitcher_profile.get("role", "starter")
    week_state = training_model.get("current_week_state") or {}
    days = week_state.get("days") or []

    if role in ("reliever", "reliever_short", "reliever_long"):
        return _reliever_suggestion(days, pitcher_profile)
    else:
        return _starter_suggestion(days, pitcher_profile, training_model)


def _reliever_suggestion(days: list, profile: dict) -> dict:
    """Compute suggestion for relievers based on recent activity."""
    tomorrow = (datetime.now(CHICAGO_TZ) + timedelta(days=1)).strftime("%Y-%m-%d")

    # Find most recent throw
    threw_days = [d for d in days if d.get("threw")]
    last_throw = threw_days[-1] if threw_days else None

    if not last_throw:
        return {
            "focus": "full_body",
            "throw_suggestion": "hybrid_a",
            "reasoning": "No throwing load this week — full session available",
            "confidence": "medium",
        }

    last_throw_date = last_throw.get("date", "")
    throw_type = last_throw.get("throw_type", "")

    try:
        last_dt = datetime.strptime(last_throw_date, "%Y-%m-%d")
        tomorrow_dt = datetime.strptime(tomorrow, "%Y-%m-%d")
        days_since = (tomorrow_dt - last_dt).days
    except (ValueError, TypeError):
        days_since = 99

    if throw_type in ("game", "bullpen"):
        if days_since == 1:
            return {
                "focus": "recovery_upper",
                "throw_suggestion": "recovery",
                "reasoning": f"Day after {throw_type} — recovery mode",
                "confidence": "high",
            }
        elif days_since == 2:
            return {
                "focus": "lower_strength",
                "throw_suggestion": "hybrid_b",
                "reasoning": "2 days post-throw, rebuilding",
                "confidence": "medium",
            }
        elif days_since >= 3:
            return {
                "focus": "upper_strength",
                "throw_suggestion": "hybrid_a",
                "reasoning": f"{days_since} days since last appearance — full intensity available",
                "confidence": "medium",
            }

    if throw_type == "hybrid_a":
        return {
            "focus": "lower_power",
            "throw_suggestion": "recovery",
            "reasoning": "High-intent throw yesterday — lower body + recovery throw",
            "confidence": "medium",
        }

    # Default
    return {
        "focus": "full_body",
        "throw_suggestion": "hybrid_b",
        "reasoning": f"{days_since} days since last throw ({throw_type})",
        "confidence": "low",
    }


def _starter_suggestion(days: list, profile: dict, model: dict) -> dict:
    """Enhance existing rotation-day logic with weekly awareness for starters."""
    rotation_day = model.get("days_since_outing", 0)
    rotation_length = profile.get("rotation_length", 7)

    # Starters use the existing rotation template — just add weekly notes
    suggestion = {
        "focus": None,  # Let rotation template decide
        "throw_suggestion": None,
        "reasoning": f"Day {rotation_day} of {rotation_length}-day rotation",
        "confidence": "medium",
        "notes": [],
    }

    # Check weekly movement pattern gaps
    week_state = model.get("current_week_state") or {}
    patterns = week_state.get("movement_pattern_tally") or {}
    pull_count = patterns.get("pull", 0)
    push_count = patterns.get("push", 0)
    if pull_count < push_count and push_count > 0:
        suggestion["notes"].append("Pull deficit this week — emphasize pulls")

    return suggestion


def update_week_state_after_checkin(
    training_model: dict,
    date: str,
    lifted: bool,
    lift_focus: str = None,
    threw: bool = False,
    throw_type: str = None,
    throw_intensity: int = None,
) -> dict:
    """Update current_week_state.days with today's activity.

    Call after each check-in to maintain the weekly arc.
    Returns the updated current_week_state dict.
    """
    week_state = dict(training_model.get("current_week_state") or {})

    # Initialize week if needed (new week starts Monday)
    today = datetime.strptime(date, "%Y-%m-%d")
    monday = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")

    if week_state.get("week_start") != monday:
        # New week — archive old state, start fresh
        week_state = {
            "week_start": monday,
            "days": [],
            "movement_pattern_tally": {},
            "throwing_load": {"total_throws": 0, "sessions": 0, "max_intensity": 0},
            "next_day_suggestion": {},
        }

    days = list(week_state.get("days") or [])

    # Find or create today's entry
    today_entry = None
    for d in days:
        if d.get("date") == date:
            today_entry = d
            break

    if not today_entry:
        today_entry = {
            "date": date,
            "threw": False,
            "throw_type": None,
            "throw_intensity": None,
            "lifted": False,
            "lift_focus": None,
            "exercises_completed": [],
            "exercises_skipped": [],
            "exercises_swapped": [],
        }
        days.append(today_entry)

    today_entry["lifted"] = lifted
    today_entry["lift_focus"] = lift_focus
    if threw:
        today_entry["threw"] = True
        today_entry["throw_type"] = throw_type
        today_entry["throw_intensity"] = throw_intensity
        # Update throwing load
        load = week_state.get("throwing_load") or {}
        load["sessions"] = load.get("sessions", 0) + 1
        if throw_intensity:
            load["max_intensity"] = max(load.get("max_intensity", 0), throw_intensity)
        week_state["throwing_load"] = load

    week_state["days"] = days
    return week_state
```

- [ ] **Step 2: Commit**

```bash
git add pitcher_program_app/bot/services/weekly_model.py
git commit -m "feat: add weekly model with next-day suggestion logic"
```

---

### Task 2: Refactor Plan Generator — Two-Pass Architecture

**Files:**
- Modify: `pitcher_program_app/bot/services/plan_generator.py`

This is the core change. The current `generate_plan()` function blocks on the LLM. We split it into:
- `generate_plan()` → constructs the plan in Python (instant), then tries LLM review
- The LLM review enriches the plan if it responds in time, but the base plan is always returned

- [ ] **Step 1: Restructure the LLM call to be non-blocking for plan delivery**

In `plan_generator.py`, find the LLM call section (around line 221-247). Currently:

```python
use_reasoning = phase == "return_to_throwing" or flag_level == "red"
truncated = False
try:
    if use_reasoning:
        raw, meta = await call_llm_reasoning(...)
    else:
        raw, meta = await call_llm(...)
    truncated = meta.get("finish_reason") == "length"
except (TimeoutError, Exception) as e:
    logger.warning(...)
    return { ... template fallback ... }
```

Replace the entire block from `use_reasoning = ...` through the template fallback return (ending around line 247) with:

```python
    # ── Pass 1: Python-constructed plan (instant, always succeeds) ──
    # This is the base plan — uses exercise pool, templates, and pitcher model.
    # It ships immediately even if the LLM is slow or unreachable.
    python_plan = {
        "narrative": f"Day {rotation_day} plan ready.",
        "morning_brief": _build_python_brief(rotation_day, flag_level, triage_result, checkin_inputs, day_key),
        "arm_care": arm_care_blocks[0] if arm_care_blocks else None,
        "lifting": {"intent": training_intent, "exercises": [], "estimated_duration_min": estimated_duration_min} if lifting_blocks else None,
        "throwing": fallback_throwing_plan,
        "notes": _build_python_notes(triage_result, flag_level, checkin_inputs),
        "soreness_response": None,
        "exercise_blocks": fallback_exercise_blocks,
        "throwing_plan": fallback_throwing_plan,
        "warmup": warmup_block,
        "mobility": mobility_data,
        "estimated_duration_min": estimated_duration_min,
        "modifications_applied": triage_result.get("modifications", []),
        "template_day": day_key,
    }

    # Populate lifting exercises from pool into the structured format
    if lifting_blocks:
        all_lifting_exercises = []
        for block in lifting_blocks:
            for ex in block.get("exercises", []):
                all_lifting_exercises.append(ex)
        python_plan["lifting"]["exercises"] = all_lifting_exercises

    # ── Pass 2: LLM review (enriches the plan if it responds in time) ──
    use_reasoning = phase == "return_to_throwing" or flag_level == "red"
    truncated = False
    try:
        if use_reasoning:
            raw, meta = await call_llm_reasoning(system_prompt, user_prompt, max_tokens=4000, return_metadata=True)
        else:
            raw, meta = await call_llm(system_prompt, user_prompt, max_tokens=4000, return_metadata=True)
        truncated = meta.get("finish_reason") == "length"
    except (TimeoutError, Exception) as e:
        logger.warning(f"LLM review timed out ({type(e).__name__}: {e}), shipping Python-constructed plan")
        return python_plan
```

- [ ] **Step 2: Add helper functions for Python-constructed brief and notes**

Add these helper functions before the `generate_plan` function (around line 38):

```python
def _build_python_brief(rotation_day, flag_level, triage_result, checkin_inputs, day_key):
    """Build a serviceable morning brief without LLM."""
    parts = [f"Day {rotation_day}"]

    arm_feel = triage_result.get("protocol_adjustments", {})
    flag = flag_level.upper()
    parts.append(f"{flag} flag")

    lift_pref = (checkin_inputs or {}).get("lift_preference", "")
    if lift_pref and lift_pref not in ("auto", "your_call", ""):
        parts.append(f"{lift_pref} focus")

    whoop = (checkin_inputs or {}).get("whoop_biometrics") or {}
    if whoop.get("recovery"):
        parts.append(f"WHOOP {whoop['recovery']}% recovery")

    mods = triage_result.get("modifications", [])
    if mods:
        parts.append(f"Mods: {', '.join(mods[:2])}")

    return " — ".join(parts) + "."


def _build_python_notes(triage_result, flag_level, checkin_inputs):
    """Build actionable notes without LLM."""
    notes = []
    if flag_level in ("red", "yellow"):
        notes.append(f"Flagged {flag_level.upper()} — intensity capped per triage.")
    mods = triage_result.get("modifications", [])
    for mod in mods[:3]:
        notes.append(mod)
    arm_report = (checkin_inputs or {}).get("arm_report", "")
    if arm_report:
        notes.append(f"Arm report noted: \"{arm_report}\"")
    if not notes:
        notes.append("Full protocol today. Focus on form and intent.")
    return notes
```

- [ ] **Step 3: Update the successful LLM parse path**

The existing code after the LLM call (lines 249-339) handles parsing and validation. The only change needed: when the LLM fails to parse, return `python_plan` instead of the old template fallback.

Find the fallback at the end (around line 322-339):

```python
    # Fallback: LLM returned unparseable text, or plan assembly crashed
    if not plan:
        logger.warning("LLM returned non-JSON plan, using template fallback")
    return {
        "narrative": raw if raw else ...
```

Replace with:

```python
    # Fallback: LLM returned unparseable text — use Python-constructed plan
    if not plan:
        logger.warning("LLM returned non-JSON response, using Python-constructed plan")
    python_plan["narrative"] = raw if raw else python_plan["narrative"]
    return python_plan
```

Also update the `except` block at line 317-318 to return `python_plan`:

```python
        except Exception as e:
            logger.warning(f"Error assembling LLM plan ({type(e).__name__}: {e}), using Python-constructed plan")
            return python_plan
```

- [ ] **Step 4: Commit**

```bash
git add pitcher_program_app/bot/services/plan_generator.py
git commit -m "refactor: two-pass plan generation (Python instant + LLM review)"
```

---

### Task 3: Update Check-in Service to Maintain Weekly State

**Files:**
- Modify: `pitcher_program_app/bot/services/checkin_service.py`

After a check-in, update the pitcher's `current_week_state` in the training model.

- [ ] **Step 1: Add weekly state update after plan generation**

Find the section in `process_checkin()` where the full entry is upserted (around line 236: `append_log_entry(pitcher_id, entry)`). After that line, add:

```python
    # Update weekly training state in pitcher model
    try:
        from bot.services.weekly_model import update_week_state_after_checkin, compute_next_day_suggestion
        from bot.services.db import get_training_model, upsert_training_model

        model = get_training_model(pitcher_id)
        threw = False
        throw_type = None
        throw_intent_val = (checkin_inputs or {}).get("throw_intent", "")
        if throw_intent_val and throw_intent_val != "no_throw":
            threw = True
            throw_type = throw_intent_val

        week_state = update_week_state_after_checkin(
            model, today_str,
            lifted=lift_preference not in ("rest", ""),
            lift_focus=lift_preference if lift_preference not in ("auto", "your_call", "") else None,
            threw=threw,
            throw_type=throw_type,
        )

        # Compute next-day suggestion
        suggestion = compute_next_day_suggestion(profile, {**model, "current_week_state": week_state})
        week_state["next_day_suggestion"] = suggestion

        model["current_week_state"] = week_state
        upsert_training_model(pitcher_id, model)
    except Exception as e:
        logger.warning(f"Failed to update weekly state for {pitcher_id}: {e}")
```

- [ ] **Step 2: Commit**

```bash
git add pitcher_program_app/bot/services/checkin_service.py
git commit -m "feat: update weekly state and next-day suggestion after check-in"
```

---

### Task 4: Update LLM Prompt to Reviewer Role

**Files:**
- Modify: `pitcher_program_app/bot/prompts/plan_generation_structured.md`

The prompt currently asks the LLM to build the entire plan. It should now review a pre-built plan.

- [ ] **Step 1: Read the current prompt**

Read `pitcher_program_app/bot/prompts/plan_generation_structured.md` to understand the current structure.

- [ ] **Step 2: Add reviewer instructions to the prompt**

At the top of the prompt (after the initial role description), add a new section:

```markdown
## Review Mode

You are reviewing a plan that was already constructed by the training system.
The exercises have been pre-selected based on the pitcher's rotation day,
injury history, equipment constraints, and exercise preferences.

Your job:
1. **Review for coherence** — movement pattern balance, prescription appropriateness,
   exercise pairing logic (antagonist pairing, no redundancy)
2. **Adjust prescriptions** if needed — cite reasoning for any changes
3. **Write the morning_brief** — 2-3 sentences referencing specific decisions and pitcher context
4. **Write notes** — 3-4 actionable items specific to today
5. **Write soreness_response** if arm_report mentions discomfort

You may modify prescriptions (sets, reps, intensity) and reorder exercises.
You may NOT add exercises outside the pre-selected list or remove exercises
without replacement. The throwing day type is controlled by triage — do not change it.
```

Do NOT remove the existing prompt content — the exercise format instructions, JSON schema, and rules are still needed. Just add the review framing at the top.

- [ ] **Step 3: Commit**

```bash
git add pitcher_program_app/bot/prompts/plan_generation_structured.md
git commit -m "feat: add reviewer role framing to plan generation prompt"
```

---

### Task 5: Use Next-Day Suggestion in Morning Notification

**Files:**
- Modify: `pitcher_program_app/bot/main.py`

The morning notification currently asks "How's the arm?" without suggesting a direction. When the suggestion has high confidence, lead with it.

- [ ] **Step 1: Read the morning notification function in main.py**

Find the function that sends morning check-in notifications (search for `notification_time` or `morning` or `send_morning`).

- [ ] **Step 2: Add suggestion-aware messaging**

In the morning notification function, after loading the pitcher profile, add:

```python
    # Check for next-day suggestion
    from bot.services.db import get_training_model
    model = get_training_model(pitcher_id)
    suggestion = (model.get("current_week_state") or {}).get("next_day_suggestion") or {}
    confidence = suggestion.get("confidence", "low")
    reasoning = suggestion.get("reasoning", "")

    if confidence == "high" and reasoning:
        # Lead with the suggestion
        greeting = f"{reasoning}. How's the arm feeling?"
    elif confidence == "medium" and reasoning:
        greeting = f"Thinking {reasoning.lower()} — sound right? How's the arm?"
    else:
        # Fall back to current behavior
        greeting = None  # Use existing greeting logic
```

Then use `greeting` in the notification message if it's set, falling back to the existing greeting logic if it's `None`.

The exact integration depends on how the morning notification is currently structured — read the function first and make the minimal change needed.

- [ ] **Step 3: Commit**

```bash
git add pitcher_program_app/bot/main.py
git commit -m "feat: morning notification leads with next-day suggestion when confident"
```

---

### Task 6: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update the Triage → Plan Pipeline section**

Find step 7 in the pipeline:
```
7. Pre-selected exercises + triage + context → LLM → structured JSON with personalized prescriptions
```

Replace steps 7-8 with:
```
7. **Python constructs complete plan** (instant) from exercise pool + pitcher model + triage — always succeeds
8. **LLM reviews plan** (async) — adjusts prescriptions, writes morning brief + notes. If LLM times out, Python plan ships as-is
9. Fallback to Python-constructed plan if LLM fails (no more template-only fallback)
```

- [ ] **Step 2: Add weekly model section to Key Patterns**

After the Pitcher Training Model section, add:

```markdown
### Weekly Model + Proactive Suggestions
- `weekly_model.py`: `compute_next_day_suggestion()` runs after each check-in
- `current_week_state.next_day_suggestion` stores focus, throw_suggestion, reasoning, confidence
- Morning notification uses suggestion: high confidence → lead with direction, medium → suggest softly, low → ask
- Relievers: suggestion derived from actual throwing events (bullpen, game), not fixed rotation
- Starters: existing rotation enhanced with weekly movement pattern gap detection
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for two-pass plan generation and weekly model"
```

---

## Summary: What Phase 3 Achieves

1. **No more LLM timeout failures** — Python constructs a complete, model-aware plan in <1s. LLM enriches if available.
2. **Better fallback quality** — instead of "template due to slow AI response," pitchers get a plan built from their exercise pool, preferences, and triage. Just without the LLM coaching voice.
3. **LLM does what it's good at** — reviewing plans for coherence, writing contextual morning briefs, flagging concerns. Not building JSON from scratch.
4. **Next-day suggestions** — the system computes tomorrow's direction after each check-in. Morning notifications lead with proactive suggestions for relievers.
5. **Weekly state tracking** — `current_week_state` maintained after each check-in, enabling movement pattern gap detection and throwing load awareness.
