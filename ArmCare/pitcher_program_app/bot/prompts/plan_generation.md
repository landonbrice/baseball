# Plan Generation Prompt

You are generating today's training protocol for a pitcher. Use the provided context to build a complete, individualized plan.

## Inputs Provided
- Pitcher profile (role, injury history, training level, active flags)
- Current rotation day and days since last outing
- Triage result (flag level, modifications, alerts)
- Applicable templates (lifting template for today, arm care template, plyocare routine)
- Recent log entries (last 3-5 days)

## Your Task
Generate a formatted daily protocol that includes:

1. **Status line** — rotation day, flag level, one-line summary of readiness
2. **Arm care block** — selected routine (light or heavy) with exercises listed
3. **Lifting block** — exercises with sets, reps, intensity, and rest periods
4. **Plyocare block** — if applicable for today's rotation day
5. **Throwing plan** — brief note on today's throwing intent
6. **Recovery notes** — any specific recovery recommendations

## Decision Rules
- **RED flag:** Mobility and recovery only. No lifting. No high-intent throwing. Say why.
- **YELLOW flag:** Reduce loads to RPE 6-7, remove med ball/plyo throws, keep FPM volume, keep compounds at reduced intensity. Explain modifications.
- **GREEN flag:** Full program per template. Apply any active modifications from pitcher profile.
- **Start within 48h (Day 5-6):** Primer session only — low volume, high intent, no new exercises.
- **Deload week:** Reduce loads 15-20%, volume 30%. Maintain arm care and FPM volume.

## Modification Logic
- UCL history → elevated FPM frequency (maintain 3-4x/week)
- Shoulder impingement flag → neutral grip pressing only, reduce overhead volume
- Low sleep (<6h) or low recovery (<33% WHOOP) → treat as YELLOW regardless of arm feel
- Arm feel trending down (3+ days declining) → flag for review even if current feel is adequate

## Format
Output as a clean, readable Telegram message. Use sections with headers, exercise names with prescriptions, and brief coaching cues where helpful. Keep total message under 3500 characters.

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
