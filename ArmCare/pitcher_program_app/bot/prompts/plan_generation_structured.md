# Structured Plan Generation

Generate today's training plan as a JSON object. Return ONLY the JSON — no markdown fences, no preamble, no explanation outside the JSON.

## JSON Schema

```
{
  "morning_brief": "1-2 sentence summary of the day and readiness",

  "arm_care": {
    "timing": "pre-lift" or "post-lift" or "standalone",
    "exercises": [
      {
        "name": "Exercise Name",
        "rx": "2x10 each direction",
        "superset_group": null or "A",
        "exercise_id": "ex_064",
        "note": null or "elevated FPM" or coaching cue
      }
    ]
  },

  "lifting": {
    "intent": "strength — lower body emphasis",
    "estimated_duration_min": 45,
    "exercises": [
      {
        "name": "Exercise Name",
        "rx": "3x5 @ 295 lbs",
        "superset_group": null or "A",
        "exercise_id": "ex_001",
        "note": null or coaching cue
      }
    ]
  },

  "throwing": {
    "type": "none" or "long_toss" or "bullpen" or "flat_ground" or "light_catch" or "game",
    "intent": null or "recovery" or "build" or "compete",
    "detail": "Description of today's throwing plan"
  },

  "notes": [
    "4-6 actionable notes: hydration, sleep, recovery, injury-specific, nutrition timing, mobility tips"
  ],

  "soreness_response": null or "Response to any reported soreness, explaining modifications made"
}
```

## Rules

### Prescriptions
- Use the pitcher's ACTUAL maxes to calculate weights. Example: if trap_bar_dl max is 350 and the template says 85% 1RM, prescribe "3x5 @ 295 lbs"
- If no max is known for an exercise, use RPE notation: "3x5 @ RPE 8"
- For bodyweight exercises, just sets x reps: "3x8 each side"
- For band/light exercises: "2x15 light band"

### Superset Groups
- Pair exercises that make sense together (e.g., compound + power, push + pull)
- Use letters: "A" for first pair, "B" for second, "C" for third
- Set superset_group to null for standalone exercises
- Not every exercise needs to be paired

### Exercise IDs
- Use exercise_id from the template or exercise library. Always include it.
- Use the EXACT name from the exercise library.

### Exercise Volume Requirements
- **Full lifting days (Day 2, 3, 4):** Minimum 6 exercises, target 7-8. The session should take 45-60 minutes.
- **Light days (Day 1, 5):** 4-6 exercises, 25-35 minutes.
- **Rest days (Day 0, 6):** Arm care and mobility only. No lifting.
- If the template provides 9 exercises, you may trim to 7-8 if time-constrained, but NEVER below 6 on a full day.
- Every full lifting day needs: 1-2 compound movements, 2-3 accessories, 1-2 core/stability.

### Template Adherence
- The template's exercise_ids are your PRIMARY source. Use them.
- Do NOT substitute lower body exercises on upper body days or vice versa.
- Day 2 (Lower Power) and Day 4 (Lower Strength) = lower body compound focus. No bench press, no overhead press.
- Day 3 (Upper Pull) = upper body emphasis. No squat, no deadlift (trap bar DL is a LOWER BODY exercise).
- Day 5 (Light Upper) = light upper + pre-game. Keep intensity low.
- If a pitcher's saved plan modification changes the focus, that overrides the template's body part focus but NOT the volume requirements.

### Duration Estimates
- Include `estimated_duration_min` in the lifting object.
- Compound exercise: ~5 min per exercise (including rest)
- Accessory: ~3-4 min per exercise
- Superset pair: ~4-5 min (shared rest)
- Core/stability: ~3 min
- 7 exercises with 2 supersets = ~42-48 min. That's the sweet spot.

### Pitcher Goals & Phase
- Read the pitcher's primary goal and current phase from context
- If phase is "return to throwing": the pitcher is building back, NOT shutting down. They should still get real training sessions with appropriate modifications:
  - Respect their lift preference (if they asked for lower body, give them a full lower session)
  - Moderate intensity (RPE 6-7 on compounds, not maximal)
  - Include FPM and arm care work regardless of lift type
  - Adjust throwing based on where they are in return (light catch → flat ground → bullpen progression)
  - Do NOT default to a 2-exercise recovery flush unless they specifically asked for rest day
- If time_constraints are noted, adjust exercise count to fit
- Match communication verbosity to detail_level preference

### Flag-Based Modifications
- RED: Mobility and arm care only. No lifting. No high-intent throwing.
- YELLOW: Reduce loads to RPE 6-7. Remove plyo throws. Keep FPM. Reduce compound intensity.
- MODIFIED GREEN: Full program but with awareness — cap intensity at RPE 7-8. Monitor throughout. Mention the borderline factor in your morning brief.
- GREEN: Full program per template.

### Injury Modifications
- UCL history → elevated FPM frequency, keep pronator and wrist work
- Shoulder impingement → neutral grip pressing only, reduce overhead
- Low sleep (<6h) → treat as YELLOW

### Notes Content
Include 4-6 notes covering:
- Pronator/FPM work importance (if applicable)
- Hydration target (half bodyweight in oz as floor)
- Sleep observation (compare to recent average if data available)
- Recovery guidance (no ice unless acute, movement > static)
- Post-lift nutrition timing
- Any injury-specific callouts

## Relevant Research
Use this research to inform your exercise selection, protocol decisions, and notes. Cite specific findings when making programming decisions.
{relevant_research}

## Pitcher Context
{pitcher_context}

## Rotation Day
{rotation_day}

## Triage Result
{triage_result}

## Today's Templates
{templates}

## Pitcher's Check-In Input
Incorporate these preferences into the plan. The arm report is in the pitcher's own words — use it for context on how they're feeling.
{checkin_inputs}

## Recent Logs
{recent_logs}
