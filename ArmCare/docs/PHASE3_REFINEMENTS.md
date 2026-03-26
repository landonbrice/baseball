# Phase 3 Refinements — Coaching Conversation Quality

> Implementation spec for Claude Code. Context: Phase 3 shipped scenario-based branching
> and coaching tone. These refinements add pitcher agency and history awareness.

## Refinement 1: Recovery Day Choice

**Current:** arm → plan (skips everything on day 0-1)
**Target:** arm → coaching response with recommendation + choice → plan

**Implementation:**
- In `daily_checkin.py`, when recovery day is detected (days_since_outing 0-1), don't skip to plan generation
- After arm feel report, bot responds with a recovery recommendation that reflects their arm report
- Offer a simple choice: "Want me to build a recovery day, or are you thinking something different?"
  - "Recovery day" / "sounds good" / affirmative → generate recovery plan (current behavior)
  - Anything else → capture their preference as free text, pass to plan_generator as lift_pref override
- This should be ONE additional exchange, not a return to the full 5-step flow
- The coaching response should reference their arm feel: "Day after, arm's at a [X] — [contextual comment]. I'd keep it to recovery flush and blood flow. Want me to build that?"

## Refinement 2: Arm Feel 1-2 Probing

**Current:** arm feel 1-2 → plan (assumes protective)
**Target:** arm feel 1-2 → targeted follow-up question → plan with appropriate triage

**Implementation:**
- In `daily_checkin.py`, when arm_feel classification returns 1-2, add a follow-up state
- Bot asks a targeted clarifying question: "That's on the lower end — is this soreness you'd expect given where you are in rotation, or does something feel different?"
- Two paths from their response:
  - "Expected / normal soreness / typical" → triage as modified green, proceed with smart defaults (still protective but not shutdown)
  - "Something feels off / different / concerned" → triage as yellow/red, proceed to protective plan
- Pass their clarification to triage as additional context (the `notes` or `clarification` field)
- The LLM triage refinement (`triage_llm.py`) should receive this clarification to make a better call
- Do NOT ask "what's your number?" again — they already gave it. This is a qualitative follow-up.

## Refinement 3: History-Aware Coaching Responses

**Current:** Coaching responses are contextual to TODAY's input only
**Target:** Responses reference recent patterns from the last 3-5 days

**Implementation:**
- In `checkin_service.py` (or wherever the check-in prompt is assembled), query the last 5 `daily_entries` from Supabase for this pitcher
- Format as condensed context: date, arm_feel, flag_level, key notes, areas of concern
- Inject into the check-in coaching prompt (the prompt that generates the bot's conversational responses between steps)
- Update the system prompt / check-in prompt template to instruct the LLM:
  - Reference patterns when relevant ("forearm tightness again — that's the third time this week")
  - Note improvements ("arm feel trending up since Monday, nice")
  - Don't force references — only mention history when it's genuinely relevant
  - Never be alarmist — flag patterns calmly, like a coach who's paying attention
- This depends on Supabase `daily_entries` being populated (Phase 1 complete ✅)

## What NOT to Change

- The 5-scenario branching logic from Phase 3 stays — it's the right architecture
- Normal day flow (5 steps) stays unchanged
- Schedule-already-known optimization stays
- Rest day selected optimization stays
- The data captured at each step stays the same — we're changing the *conversation*, not the schema

## Testing

- Test recovery day flow: verify pitcher gets a choice, both paths generate appropriate plans
- Test arm feel 1-2: verify follow-up question fires, both response paths triage correctly
- Test history injection: verify recent entries appear in prompt context, LLM references them naturally
- Test normal day: verify no regression in the standard 5-step flow
