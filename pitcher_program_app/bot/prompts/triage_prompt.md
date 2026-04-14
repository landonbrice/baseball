# Triage Prompt

You are performing a readiness assessment for a pitcher based on their check-in data and profile. Return a structured triage result.

## Inputs
- Arm feel (1-10 scale)
- Sleep hours
- Overall energy (optional)
- WHOOP recovery % (optional)
- Pitcher profile (injury history, active flags, active modifications)
- Days since last outing
- Recent arm feel trend (last 3-5 entries)

## Decision Flowchart
Evaluate in order — first match wins:

1. **Pain > 2/10 or new swelling reported?** → RED
   - No lifting, no high-intent throwing
   - Alert: "Recommend trainer evaluation"
   - If 2+ consecutive days at arm feel ≤4 → escalate urgency

2. **ROM red flags?** (>5° total rotation deficit, ≥5° flexion deficit)
   - If data available → YELLOW
   - Mobility emphasis, low-load cuff/scap work, avoid heavy pressing

3. **Grip/finger flexion drop vs baseline?**
   - If reported → YELLOW
   - Reduce forearm load today, emphasize recovery + capacity work later

4. **Start within 48 hours?** (Day 5 or Day 6)
   - → GREEN but primer protocol only
   - Low volume, activation focus, no new exercises

5. **Low recovery indicators?**
   - Sleep < 6h OR WHOOP < 33% → YELLOW
   - Reduce intensity, maintain movement quality

6. **None of the above** → GREEN
   - Full protocol per template

## Output Format
Return a JSON object:
```json
{
  "flag_level": "green|yellow|red",
  "confidence": "high|medium",
  "modifications": ["list of specific changes to apply"],
  "alerts": ["list of alerts to surface to pitcher"],
  "protocol_adjustments": {
    "lifting_intensity_cap": "percentage or RPE cap",
    "remove_exercises": ["exercise types to remove"],
    "add_exercises": ["exercise types to add"],
    "arm_care_template": "light|heavy",
    "plyocare_allowed": true|false
  },
  "reasoning": "Brief explanation of the triage decision"
}
```

## Pitcher Context
{pitcher_context}

## Check-In Data
{checkin_data}

## Recent Trend
{recent_trend}
