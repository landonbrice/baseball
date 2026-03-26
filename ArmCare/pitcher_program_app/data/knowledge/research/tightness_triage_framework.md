---
keywords: [triage, protocol, flag, red, yellow, green, worried, concern, sharp, numb, tingling, swelling, shut down, skip, day off, should i throw, modify, modification, back off, push through, can i throw, what should i do]
type: core_research
---

# Tightness Triage: Protocol Decision Framework

## Purpose

This document codifies the clinical reasoning the bot should apply when generating protocols. It translates symptom inputs into protocol adjustments, based on Lando's injury history and the research on FPM/UCL protection.

---

## Input Variables (Collected at Outing Log)

1. **Pitch count** — proxy for FPM fatigue load
2. **Forearm tightness level** — None / Mild / Moderate / Significant
3. **UCL-area sensation on extension** — None / Present
4. **Arm feel rating** — 1-10
5. **WHOOP HRV** — vs. 7-day rolling average
6. **WHOOP sleep performance** — last night %
7. **Days until next outing**

---

## Decision Tree

### RED FLAG — Escalate Immediately

Trigger: Any of the following:
- UCL-area sensation on extension IS PRESENT
- Forearm tightness = Significant
- Arm feel 1-4

**Protocol:**
- Day 1: Arm Care Light ONLY + nerve glides + soft tissue work. No throwing of any kind.
- Day 2: Re-assess. If symptoms persist → no throwing, repeat Day 1 protocol. If improving → recovery throws only (sock throws or ball holds, max 50% effort, 15-20 throws)
- Switch to Pronator Focus Adjustment Program for all arm care
- Flag: consider reaching out to trainer/athletic trainer if symptoms persist beyond Day 2
- Do NOT proceed to Arm Care Heavy until tightness is fully resolved

---

### YELLOW FLAG — Modified Protocol

Trigger: Any of the following (no red flags present):
- Forearm tightness = Mild or Moderate
- Arm feel 5-6
- HRV >15% below 7-day rolling average
- Pitch count 80+

**Protocol adjustments:**
- Day 1: Arm Care Light + add nerve glides + extra pronator work (pronator press out 3x12, full pronation 3x12)
- Day 2: Arm Care Heavy but substitute Pronator Focus Adjustment Program
- Day 3: Assess before proceeding to command bullpen. If any tightness remains → reduce intensity, shorten bullpen, include extra warm-up
- Defer high-intent throwing (extension long toss, full plyo heavy) until tightness is cleared
- Soft tissue work before every session, not just as needed

---

### GREEN — Standard Protocol

Trigger: All of the following:
- No forearm tightness (or resolved from previous)
- No UCL sensation
- Arm feel 7-10
- HRV at or above 7-day rolling average
- Sleep performance >70%
- Pitch count under 80

**Protocol:** Follow standard 7-day split as written. No modifications needed.

---

### MODIFIED GREEN — Minor Adjustment

Trigger: Green conditions EXCEPT:
- HRV 10-15% below rolling average (but not further)
- OR Sleep performance 50-70%
- OR Pitch count 60-80
- No arm symptoms

**Protocol:** Standard 7-day split with these adjustments:
- Day 1: Add 1 set of nerve glides and pronator press out to Arm Care Light
- Day 3 command bullpen: cap at planned pitch count, don't extend
- Day 5 extended long toss: go to comfort, don't push beyond

---

## Pitch Count Guidelines

| Pitch Count | FPM Status | Protocol Flag |
|---|---|---|
| Under 60 | Mostly intact | Green / Modified Green |
| 60-79 | Meaningfully degraded | Modified Green — add pronator work |
| 80-99 | Significantly degraded | Yellow Flag |
| 100+ | Substantially degraded | Yellow Flag minimum, assess for Red |

---

## Special Case: Returning from Tightness Episode

If previous outing was logged as Red or Yellow Flag and symptoms have resolved:
- First outing back = treat as Yellow Flag regardless of how arm feels
- Rebuild one outing at a time, do not jump back to full protocol
- Increase pronator maintenance work for 2-3 weeks post-recovery

---

## Rocksauce / Pre-Throw Activation

Always include in Day 0 protocol. Applied to forearm before throwing. This is personal preference that works for Lando — include as a standard pre-throw step.

---

## Notes for Bot

- Arm feel and UCL sensation always override HRV. If HRV is green but arm symptoms are present, follow symptom-based protocol.
- When in doubt, be conservative. A missed day of throwing has far less cost than a setback.
- Always explain the reason for any protocol modification so Lando understands the logic.
- If two or more yellow flag triggers are present simultaneously, escalate to Red Flag protocol.
