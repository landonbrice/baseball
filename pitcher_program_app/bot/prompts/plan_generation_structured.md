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

### Flag-Based Modifications
- RED: Mobility and arm care only. No lifting. No high-intent throwing.
- YELLOW: Reduce loads to RPE 6-7. Remove plyo throws. Keep FPM. Reduce compound intensity.
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

## Pitcher Context
{pitcher_context}

## Rotation Day
{rotation_day}

## Triage Result
{triage_result}

## Today's Templates
{templates}

## Recent Logs
{recent_logs}
