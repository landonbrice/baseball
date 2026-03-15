# Research: Advanced Workload Management, Periodization & Performance

## What's New Here (Beyond Existing Research Docs)

This doc covers material not in the existing three research files:
- Acute-to-Chronic workload ratio framework
- Blood Flow Restriction (BFR) for in-season maintenance
- Collagen/Vitamin C nutritional protocol for connective tissue
- In-season strength philosophy (volume vs. intensity)
- Pitch clock fatigue implications for flexor-pronator mass
- Eccentric and isometric FPM strengthening progressions

---

## Acute-to-Chronic (A:C) Workload Ratio

This is the most practically useful framework for managing throwing load over a season.

**The concept:** Compare your recent acute workload (last 9 days average) to your chronic workload (last 28 days average). The ratio tells you whether you're ramping up too fast or undertraining.

| A:C Ratio | Status | Implication |
|---|---|---|
| Below 0.7 | Undertrained | Under-stimulating — not building chronic capacity |
| 0.7 – 1.3 | Sweet spot | Productive training zone |
| Above 1.3 | Overreaching | Statistically elevated injury risk |

**For this bot:** Pitch count is a crude proxy for workload. A 90-pitch outing after a week of light throwing is a much higher A:C spike than 90 pitches mid-season when chronic load is built. When logging outings, consider whether this outing was unusually high relative to recent weeks — flag accordingly.

The PULSE sensor (Driveline's wearable IMU) tracks actual elbow valgus torque per throw, which is more precise than pitch count. If Lando ever uses PULSE, its A:C data should replace pitch count as the primary workload variable.

---

## In-Season Strength Philosophy

**Core principle: Reduce volume 40-50%, maintain intensity at 85-90% of baseline.**

High volume causes DOMS. High intensity preserves neuromuscular strength without significant muscle damage. In-season, the goal is maintenance — not gains.

**Avoid in-season:**
- Slow eccentric (negative) phases on major lifts — primary driver of DOMS
- Eccentric-emphasis forearm training — the arm is already under heavy eccentric load from pitching itself
- High-volume hypertrophy work

**Keep in-season:**
- Compound movements at high intensity, low volume (trap bar deadlift, goblet squat)
- Explosive work (medicine ball, box jumps) on Days 3-4 post-start
- Arm care as written — this is maintenance, not strength building

**Role-based scheduling note:**
- Day 0 (game day): Some elite programs recommend a heavy lower-body lift post-game to consolidate the high-stress window, freeing up more recovery days before next start. Worth experimenting with.
- Day 1: Active recovery only — no lifting
- Day 2: Total body strength (compound movements)
- Day 3: Medium intent bullpen + upper body power
- Day 4: Lower body power (speed-focused)

---

## Blood Flow Restriction (BFR) — In-Season Maintenance Tool

BFR uses a cuff to restrict venous return while maintaining arterial inflow. Creates a hypoxic environment that forces recruitment of Type II (fast-twitch) muscle fibers at only 20-30% of normal load.

**Why it matters for pitchers:**
- Maintains rotator cuff and forearm mass during season without joint stress of heavy lifting
- Post-game passive BFR (occlusion without exercise) stimulates muscle protein synthesis and accelerates metabolite clearance — similar mechanism to Marc Pro but different modality
- No DOMS risk at these low loads

**Practical use:** BFR for forearm/rotator cuff maintenance 1-2x per week in-season. Keep reps high (15-30), weight very low. This is additive to existing arm care program, not a replacement.

Not currently in Lando's program — flag as something to explore if forearm maintenance becomes a concern mid-season.

---

## Collagen + Vitamin C Protocol for Connective Tissue

**The protocol:** 15g of hydrolyzed collagen (or gelatin) + 50mg Vitamin C, taken 45-60 minutes before a throwing session or arm care work.

**Mechanism:** Collagen synthesis requires hydroxylation of proline and lysine (amino acids forming collagen's triple-helix structure). Vitamin C is the necessary cofactor for this process. Ingesting collagen pre-exercise roughly doubles the rate of collagen synthesis in the stressed tissue during and after the session.

**Why it's relevant here:** UCL and flexor-pronator tendons repair through collagen synthesis. Given Lando's 2024 injury history, supporting connective tissue repair during high-workload periods is directly relevant.

**Practical implementation:**
- Gelatin (Jello powder, Knox) is the cheap version — 1-2 tablespoons + OJ (natural Vitamin C source)
- Hydrolyzed collagen powder is cleaner and easier to mix
- Timing matters — must be 45-60 min pre-activity, not post
- Consider adding to Day 0 pre-game routine and Day 3 pre-bullpen

**Hydration:** Tendons and ligaments are highly hydration-dependent for viscoelastic properties. Dehydrated tissue is more brittle under shear forces. Basic but often underrated — stay hydrated on outing days.

---

## Pitch Clock Fatigue — New Risk Factor (2023-2025)

Relevant context for college baseball if pitch clock rules are in effect:

Reduced recovery time between pitches leads to cumulative intra-outing fatigue in the FPM. As the flexor-pronator mass fatigues, it loses rotational stiffness → stress transfers directly to the UCL. This is the same mechanism as late-game high pitch count fatigue, but accelerated.

MLB data: Forearm/flexor tendon injuries increased 29% from 2016-2024. 2024 saw highest total elbow and forearm injuries (128) in recorded history — coinciding with pitch clock era.

**Implication for protocol:** If pitching under a pitch clock, the FPM fatigue curve is steeper than historical baselines. Be more conservative with pitch count thresholds in the triage framework — consider 55 pitches as the meaningful degradation point rather than 60 when pitch clock is in effect.

---

## Advanced FPM Strengthening (Beyond Current Program)

The existing program is solid. These are additive exercises from the research worth considering if forearm symptoms recur or as off-season additions:

**Eccentric Pronation/Supination:** Using a weighted hammer or tubing, slow 5-second lowering phase (eccentric). Targets pronator teres tendon-bone interface — builds resilience specifically where overuse injuries originate. 2 sets x 12, 5-second eccentric.

**Two-Finger Kettlebell Carries:** Carry a light kettlebell using only index + middle fingers. Isolates FDS specifically — the muscle that fatigues first and is most correlated with medial elbow pain in pitchers. Short duration (20-30 sec), not heavy.

**Isometric Finger Flexion:** 3 sets x 20-second holds at ~70% max effort grip. Builds FDS/FDP endurance without eccentric load — appropriate for in-season when DOMS risk needs to be minimized.

These are NOT replacements for the current pronator focus program — they're targeted additions for off-season strengthening or return from tightness episodes.

---

## Notes for Bot

- A:C ratio logic: if outing pitch count is significantly above the trailing 2-week average, flag this as a workload spike even if absolute pitch count is moderate
- Collagen + Vitamin C should be suggested as a Day 0 pre-game addition whenever arm is in Yellow or Red flag status
- BFR is worth mentioning as an option if user asks about in-season arm maintenance
- Pitch clock: if user mentions pitch clock or short rest between batters, lower the forearm fatigue thresholds by ~10%
- Do NOT recommend eccentric forearm training during active tightness episodes — eccentric load on already-stressed tissue is counterproductive
