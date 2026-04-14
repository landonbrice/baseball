---
id: research_gap_analysis
title: Research Gap Analysis & Exercise Library Additions
keywords: [exercise, library, gap, missing, front squat, split squat, nordic, hip thrust, sled, upper body, pull, push, core, plyo]
type: system_reference
applies_to:
  - any
triggers:
  - reference
phase: any
priority: reference
contexts:
  - coach_chat
summary: >
  Documents gaps in the original exercise library and adds missing exercises across
  lower body, upper body, and core categories based on Gemini v3 research output.
---

# Research Gap Analysis & Additions
## Based on Gemini v3 Output — What to Add Before Parsing

---

## GAP 1: EXERCISE LIBRARY IS STILL INCOMPLETE
Gemini gave us ~20 exercises. A functional training system needs 45-60. Missing categories:

### Lower Body — Missing Exercises
- **Front Squat** — not mentioned at all. Key quad/core compound for pitchers. 
  Protocol: 3x4-6 @ 75-85% 1RM. Day 4 (second lower body session).
  Source: Cressey, Driveline standard programming
  
- **Rear-Foot-Elevated Split Squat (Bulgarian)** — the best unilateral lower body exercise for pitchers.
  Single-leg force production directly mimics the delivery stride.
  Protocol: 3x6-8/side @ RPE 7-8. Day 2 or Day 4.
  Source: Cressey Sports Performance staple

- **Hip Thrust (Barbell)** — glute max horizontal force production, directly relevant to stride power.
  Protocol: 3x8-10 @ 70-80% 1RM. Day 1 or Day 4.
  Source: Bret Contreras research, widely adopted in baseball S&C

- **Nordic Hamstring Curl** — eccentric hamstring strength for deceleration and injury prevention.
  Protocol: 3x3-5 (build slowly — these are brutal). Day 2 or Day 4.
  Source: van der Horst et al. injury prevention meta-analyses

- **Sled Push/Drag** — low-eccentric-load conditioning that won't create soreness.
  Protocol: 4-6 pushes × 20-30 yards. Day 1 or Day 3 (recovery-friendly).
  Source: Driveline, TRACT Performance

- **Single-Leg RDL (Loaded)** — Gemini only mentioned unloaded version on Day 3.
  Loaded version: 3x8/side @ moderate DB. Day 2 or Day 4.
  Source: Standard posterior chain programming

### Rotational Power — Missing Exercises  
- **Med Ball Scoop Toss** — rotational power from low-to-high, mimics sequencing of pitching delivery.
  Protocol: 3x5-6 throws/side, max intent, 4-6 lb ball.
  Day 2 or Day 4. Source: Driveline, Premier Pitching

- **Med Ball Overhead Slam** — anti-flexion power, lat engagement, deceleration training.
  Protocol: 3x6-8 slams, 6-10 lb ball. Day 2 or Day 4.
  Source: Cressey Sports Performance

- **Pivot Pickoff Med Ball Throw** — rotational pattern specific to pick-off move and trunk rotation.
  Protocol: 2x5/side. Day 2 or Day 4.
  Source: Driveline rotational power series

### Upper Body — Missing Exercises
- **Weighted Chin-Up/Pull-Up** — primary vertical pull, lat and grip development.
  Protocol: 3x5-6 @ BW+ (add load when BW×8 is easy). Day 2.
  Source: Universal strength programming

- **Half-Kneeling Cable Row** — rotary stability + horizontal pull. Better for pitchers than seated row.
  Protocol: 3x10-12/side @ moderate. Day 2, Day 4.
  Source: Cressey Sports Performance

- **Push-Up Plus** — specifically targets serratus anterior protraction at end-range.
  Protocol: 3x12-15. Day 1, Day 3, Day 5 (can be daily activation).
  Source: Reinold, ASMI Thrower's Ten

- **Band Pull-Apart** — daily posterior shoulder and mid-trap activation.
  Protocol: 3x15-20 (can be done daily as warm-up).
  Source: Universal arm care, Jaeger protocol

### Core — Missing Exercises
- **Pallof Press** — was mentioned but no protocol.
  Protocol: 3x8-10/side, 3-second hold at extension. Day 2, Day 4.
  Source: Standard anti-rotation programming

- **Dead Bug** — was mentioned but no protocol.
  Protocol: 3x8-10/side (opposite arm/leg). Day 1-5 as warm-up.
  Source: DNS-based core training

- **Ab Wheel Rollout** — anti-extension, builds anterior core stiffness for trunk rotation transfer.
  Protocol: 3x8-10 (from knees). Day 2 or Day 4.
  Source: McGill core stability research

- **Side Plank with Row (Copenhagen variation)** — adductor + lateral core integration.
  Protocol: 3x20-30 seconds/side. Day 2, Day 4.
  Source: Cressey Sports Performance


---

## GAP 2: THE 7-DAY TEMPLATE NEEDS MORE FLESH

Gemini's template is a good skeleton but each day needs:
- **Warm-up protocol** (5-8 min) — not just "movement flow" but actual exercises
- **Throwing integration** — what throwing happens each day and how does it affect the lift
- **Session duration** — pitchers need to know if this is a 25-min or 55-min commitment
- **Recovery notes** — nutrition timing, sleep emphasis, etc.

### Proposed Warm-Up Templates (to add to each day)

**Lifting Day Warm-Up (Day 1, 2, 4):**
1. Foam roll: lats, T-spine, hip flexors (2 min)
2. 90/90 hip switches × 5/side
3. World's greatest stretch × 3/side  
4. Band pull-apart × 15
5. Band external rotation × 10/side
6. Lateral mini-band walks × 10/side
7. Squat to stand × 5

**Recovery Day Warm-Up (Day 3, 5):**
1. Foam roll: full body (3-4 min)
2. T-spine rotation on roller × 8/side
3. Hip 90/90 × 5/side
4. Cross-body stretch × 30s/side
5. Cat-cow × 10
6. Deep squat hold × 30s

### Proposed Throwing Integration

| Day | Throwing Activity | Lift Timing |
|-----|------------------|-------------|
| 0 | Game outing | No lift |
| 1 | None or light catch (10 min, <90 ft) | Lift in afternoon |
| 2 | Long toss or flat ground (building) | Throw first, lift after |
| 3 | Bullpen (recovery pen, 25-30 pitches) | Mobility/recovery only |
| 4 | Flat ground (moderate intent) | Throw first, lift after |
| 5 | Light catch or command work | Mobility focus |
| 6 | Pre-game light catch | No lift |


---

## GAP 3: PROGRESSION MODEL IS MISSING

Gemini gave static protocols but no system for how to progress over weeks.
The bot needs rules for when and how to increase load:

### Progressive Overload Rules for Bot
- **Compound lifts (Trap Bar DL, Front Squat, Hip Thrust):** 
  If pitcher completes all prescribed reps for 2 consecutive sessions → increase by 5-10 lbs
- **Accessory lifts (Split squat, RDL, rows):**
  If all reps completed at current RPE for 2 sessions → increase by 2.5-5 lbs
- **FPM/Arm care work:**
  Progress by adding 1 set or 2-3 reps before increasing load. Load increases in 1-2 lb increments.
- **Plyometrics/Med ball:**
  Do NOT increase load. Progress by increasing intent or adding 1-2 throws per set.
- **Deload protocol:**
  Every 4th week: reduce all loads by 15-20%, reduce volume by 30%. 
  Maintain FPM and arm care volume (these don't deload).


---

## GAP 4: INDIVIDUAL MODIFICATION RULES ARE THIN

The Yellow/Red flag system is good but needs more granularity for the bot:

### Expanded Modification Matrix

| Condition | Exercises to EMPHASIZE | Exercises to REDUCE/AVOID | Duration |
|-----------|----------------------|--------------------------|----------|
| UCL history (resolved) | FPM 4-5x/week, eccentric wrist flexion, BFR forearm | Weighted balls, max-intent throwing | Ongoing |
| Active medial elbow tightness | Isometric wrist flexion holds, rice bucket only | ALL loaded FPM work, heavy pulling | Until pain-free 7 days |
| Shoulder impingement history | Serratus work, low trap raises, cross-body stretch | All pressing overhead, lat pulldown behind neck | Ongoing |
| Lat strain history | Eccentric lat work (slow pulldowns), thoracic mobility | Heavy pulling, high-volume rowing | 4-6 weeks post-clearance |
| Low hip IR (<30°) | 90/90 hip flow, half-kneeling hip flexor stretch, lateral lunges | Heavy bilateral squats at depth | Until IR > 35° |
| Low T-spine rotation | T-spine rotation drills, open books, foam roller extensions | Heavy overhead work | Ongoing |
| Post-TJ surgery (cleared to lift) | FPM progressive loading, scapular stability emphasis | Max-effort throwing, weighted balls | Per surgeon protocol |
| Undersized/mass gain goal | Increase accessory volume by 20%, add calories | Don't sacrifice compound intensity | 8-12 week blocks |
| High-velocity durability focus | Deceleration work (nordics, eccentrics), FPM volume | Ultra-high pitch counts, max-effort weighted balls | Ongoing |


---

## GAP 5: RECOVERY PROTOCOLS NEED SPECIFICS

Gemini's v2 output had good conceptual content on recovery. 
Combine with this for actionable protocols:

### Post-Outing Recovery Protocol (Day 0 evening + Day 1 morning)
**Immediately post-game:**
- Light band work: ER/IR × 15/side, band pull-aparts × 20 (blood flow, NOT strengthening)
- Arm circles: 10 forward, 10 backward (gentle ROM)
- Cross-body stretch: 2 × 30s/side
- NO ICE unless acute injury/swelling (evidence: ice delays inflammatory healing cascade)
- NO NSAIDs (evidence: interfere with satellite cell activation and tissue remodeling)

**Nutrition (within 45 min post-outing):**
- 30-40g protein (whey or whole food)
- 60-80g carbohydrates (glycogen replenishment)
- Hydration: 16-24oz water + electrolytes

**Sleep target:** 8-9 hours (this is the #1 recovery variable)

**Day 1 morning check-in (what the bot should ask):**
- Arm feel: 1-10 scale
- Grip strength: subjective comparison to baseline
- Sleep hours + quality (1-10)
- Any new pain locations?
- WHOOP recovery % (if connected)

### What the Bot Does With This Data:
- Arm feel ≥ 4 + WHOOP ≥ 66% → Green: full Day 1 program
- Arm feel 3 + WHOOP 33-66% → Yellow: reduce upper body volume, maintain lower body, increase FPM
- Arm feel ≤ 2 OR WHOOP < 33% → Red: recovery/mobility only, flag for follow-up next day
- Arm feel ≤ 2 for 2+ consecutive days → flag for trainer/coach evaluation
