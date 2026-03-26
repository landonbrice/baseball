# Post-Outing Recovery Protocol

Generate a detailed day-by-day recovery protocol for a pitcher who just finished throwing. Use the research base to inform decisions — don't give generic advice.

## Outing Data
{outing_data}

## Pitcher Context
{pitcher_context}

## Relevant Research
{relevant_research}

## Recovery Templates
{recovery_templates}

## Recent Logs
{recent_logs}

## Your Task

Generate a **day-by-day recovery protocol** (Day 1 through Day 5-7 depending on rotation) with specific:

### For each day:
- **Arm care** — specific exercises, sets, reps (light vs heavy based on recovery day)
- **Throwing** — if applicable: distance, throw count, intent % cap, what to watch for
- **Lifting** — if applicable: what track (upper/lower/full), intensity cap, exercises to avoid
- **Recovery** — soft tissue, mobility, nutrition timing

### Shutdown criteria
- What should stop training immediately
- What warrants a call to the trainer
- What symptoms mean "regress to yesterday's protocol"

### Based on the triage flag:
- **RED**: No throwing. Arm care light only. Trainer eval. Day-by-day with re-evaluation gates.
- **YELLOW**: Conservative recovery. Delayed return to throwing. Extra FPM if applicable.
- **MODIFIED GREEN**: Standard recovery with awareness. Monitor the borderline factor.
- **GREEN**: Standard recovery per rotation.

### Rules
- Be specific to THIS pitcher's injury history and active modifications
- Reference research when making decisions (ice, NSAIDs, recovery timelines, FPM fatigue)
- Include pre-throw and post-throw templates for throw days
- If pitch count was high (>typical+15), extend the recovery timeline
- If forearm tightness or UCL sensation present, address explicitly with protocol adjustments

## Format
Day-by-day with clear headers. Include specific exercises, sets, reps. Be thorough — this is the pitcher's roadmap for the next week. Include a `save_plan` JSON block so this can be saved.
