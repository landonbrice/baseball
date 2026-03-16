# Post-Outing Recovery Prompt

You are generating a post-outing recovery protocol for a pitcher who just finished throwing. Use the system prompt guidelines for voice and personality.

## Outing Data
{outing_data}

## Pitcher Context
{pitcher_context}

## Recovery Templates
{recovery_templates}

## Recent Logs
{recent_logs}

## Your Task
Generate a recovery plan with these sections:

### Tonight's Recovery
- Post-throw stretch routine (from template)
- Arm care light routine (from template)
- Any additional recovery notes based on outing intensity

### Tomorrow Preview
- Brief note on what tomorrow's training should look like given today's outing
- Flag if pitch count was notably high or arm feel is concerning

### Notes
- Address any pitcher notes from the outing
- Acknowledge effort and keep tone supportive

## Decision Rules
- **Arm feel ≤ 2**: Flag for trainer evaluation. Emphasize rest over recovery exercises. Say: "I'd flag this for your trainer before doing anything tomorrow."
- **Pitch count > typical + 15**: Add extended recovery note. Suggest extra soft tissue work and hydration emphasis.
- **Arm feel 3**: Standard recovery but note to monitor closely tomorrow morning.
- **Arm feel 4-5**: Standard recovery, positive reinforcement.

## Format
Output as a clean Telegram message. Keep it under 2000 characters. Be specific to their outing, not generic.
