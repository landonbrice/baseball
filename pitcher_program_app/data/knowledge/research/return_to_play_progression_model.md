---
id: return_to_play_progression_model
title: Return-to-Play Progression Model — Ramp + 9-Week Mound Reintroduction
keywords: [return to play, return to mound, rtp, rtt, post injury, ramp, mound, bullpen, on a line, compression, pulldowns, acwr, deload, groove fastball, 50 feet, flat ground, gate, arm health]
type: core_research
applies_to:
  - any
triggers:
  - return_to_play
  - return_to_mound
  - post_injury
  - ramp_up
  - mound_introduction
  - throwing
phase: any
priority: critical
contexts:
  - program_gen
  - coach_chat
  - daily_plan_why
summary: >
  Authoritative return-to-play progression model for the Program Engine.
  Synthesized from the two recovered golden macrocycles (Ramp up with Bullpen
  12-week and Return to Mound 9-week — full day-by-day data in
  data/knowledge/golden_programs/), the FPM gated state machine, and UCL/
  flexor-pronator protection rules. Defines the two-stage RTP arc (ramp →
  mound reintroduction), the gates between and within stages, the ACWR
  governor, conservative flag deltas (a RED day never advances RTP
  progression), and the regression rule for symptom recurrence.
---

# Return-to-Play Progression Model

This is the return-to-play program-generation reference. The LLM author
(Program Engine `author.py`) reads this at generation time alongside the
per-pitcher profile + injury history, the live `block_library.return_to_mound_9wk_v1`
row, and the golden exemplars (`data/knowledge/golden_programs/`) to author a
personalized return-to-play program. **The prime directive differs from the
velocity pack: the goal is a durable, pain-free arm on the mound — velocity is
a by-product, never a target, until RTP completes.**

## 1. The two-stage arc

RTP is two chained macrocycles. The engine authors whichever stage the pitcher
is entering (or both, chained), based on where their current throwing base is.

```
STAGE 1 — Ramp (≈6–12 wk, golden: Ramp up with Bullpen 12wk)
  Intensity 50% → 95%, distance 45 → 120ft, ACWR-governed weekly G curve
  (6960 → 14616 load units), deloads wk4 + wk7 (3-up-1-down).
  Bullpen introduced at 50ft ("on the bump, move plate in — groove fastball")
  around wk5-6; pitch mix only after FB command (wk9+); full-intent pen wk11-12.

STAGE 2 — Mound Reintroduction (9 wk, golden: Return to Mound 9wk)
  PRESUMES a completed ramp ("Following phase 1 pending appropriate ramp up").
  3 → 4 throwing days/wk; weekly throws 178 → 254; flat-ground intent reaches
  100% (pulldowns) by wk3 while MOUND volume gates separately and slowly.
  Compression work "on a line" at 80% → 85-90%. Distance capped at 120ft.
```

Weekly throw-count reference for Stage 2 (from the golden, weeks 1–9):
`178, 203, 241, 223, 237, 247, 247, 249, 254` — note the wk4 dip (223 < 241):
the deload undulation persists even in the mound stage.

## 2. Gates (these are hard, not advisory)

1. **Stage 1 → Stage 2 gate:** full ramp completed; 120ft long toss sustained;
   bullpen at 50ft pain-free; no active modification flags; ACWR in [0.8, 1.3]
   for 7 consecutive days.
2. **FPM gate (flexor-pronator history — see `fpm_strain_protocol`):** any
   active FPM modification pauses throwing progression entirely; cleared by
   pain-free Thinker test + 30 reps ×2 consecutive pain-free days.
3. **Mound-volume gate within Stage 2:** flat-ground intent may reach 100%
   (pulldowns) by wk3, but mound/bullpen throw counts follow their own ladder
   (15 → 20 → 25 → 30 → 40 → 45 → 50) and never jump a rung.
4. **Forearm tightness is the stop sign** — not "work through it." Any forearm
   tightness report = RED-day handling + no progression advance.

## 3. ACWR governor (identical maths to the velocity pack)

Band [0.8, 1.3], hard cap 1.5; acute = trailing 7d, chronic = trailing 28d.
The golden curves are the regression fixtures (`tests/fixtures/golden_acwr_curve.json`
carries the full recovered daily grid). For RTP the governor is applied MORE
conservatively: on band breach, the engine shrinks the week — it never
"absorbs" an over-cap week the way a healthy velocity block might tolerate.

## 4. The invariant warm-up ladder

Every throwing day in both stages opens with the golden ladder:
`45ft @ 50% (high/pec load 10@30, snap-snap rocker ×5, self-toss ×5) →
60ft @ 60% (figure-8 rocker / half-kneel / in-the-hole / step-back quarters) →
75ft @ 70% (QB drop-back 50%, lateral bound 50%)`. It is never modified,
never skipped, and does not count toward progression volume decisions.

## 5. Flag deltas (RTP-conservative)

- **GREEN** — run prescribed day; advance program counter.
- **YELLOW** — drop one intent tier AND freeze the mound-volume ladder (repeat
  the current rung next mound day); counter advances.
- **RED** — recovery-only throwing capped at min(prescribed, 20 throws / 45ft /
  50%); **counter pauses (hold event)**; mound ladder steps BACK one rung on
  the next mound day.
- **CRITICAL_RED** — full shutdown, mobility only; hold event; coach surfaced.
- **Regression rule:** two RED days inside any rolling 7 days, or any symptom
  recurrence at the injury site, regresses the program one full week (the
  engine re-projects; the reschedule is proposed to the player per the drive
  policy — propose-and-confirm).

## 6. Individualization hooks the author must honor

- **UCL / flexor-pronator history** (`ucl_flexor_pronator_protection`, `fpm_strain_protocol`):
  no fixed-scap pressing or vertical pulling while flagged; FPM work ≥4/7 days.
- **Labrum / shoulder history:** cuff/scap activation is load-bearing in the
  warm-up; avoid end-range distraction drills early in Stage 1.
- **WHOOP-linked pitchers:** recovery score <33% on a planned high-intent day
  should be treated as YELLOW even if arm feel is fine.
- **Lifting runs in parallel** on the unified calendar (same integration table
  as the velocity pack) but stays one intensity tier below the throwing stage:
  Stage 1 = hypertrophy → hypertrophy/strength; Stage 2 = strength, no
  strength-power block until RTP completes.

## 7. Tunables the Socratic interview may set

- `stage` (ramp | mound_reintroduction | full_chain) — where the pitcher enters.
- `stage2_weeks` (8–10, default 9) and `throwing_days_per_week` (3–4).
- `mound_ladder_start_rung` (default 15 throws) and `bullpen_distance_start_ft`
  (default 50).
- `conservatism` (standard | post_surgical) — post_surgical halves weekly
  throw-count increases and doubles gate dwell times.

## Sources

- `data/knowledge/golden_programs/golden_ramp_up_bullpen_12wk.csv` (recovered 2026-07-12)
- `data/knowledge/golden_programs/golden_return_to_mound_8wk.csv` (recovered 2026-07-12; contains 9 weeks)
- `fpm_strain_protocol`, `ucl_flexor_pronator_protection`, `advanced_workload_performance`, `final_research_base`
