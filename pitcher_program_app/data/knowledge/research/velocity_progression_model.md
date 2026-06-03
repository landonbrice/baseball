---
id: velocity_progression_model
title: Velocity Progression Model — 12-Week Phase Arc + ACWR Governor
keywords: [velocity, throwing, pulldowns, long toss, bullpen, acwr, acute chronic, deload, mound, ramp, phase, periodization, intensity, pitch design, plyo velo, weighted ball, on a line, compression]
type: core_research
applies_to:
  - any
triggers:
  - velocity
  - velocity_development
  - throwing
  - long_toss
  - pulldowns
  - mound_introduction
phase: any
priority: critical
contexts:
  - program_gen
  - coach_chat
  - daily_plan_why
summary: >
  Authoritative velocity-development progression model for the Program Engine.
  Synthesized from the golden Ramp up with Bullpen 12-week xlsx (ACWR-governed
  weekly load curve), Return to mound 9-week xlsx (gated phase model), the
  Driveline 16-week structure, FPM gated state machine, and the Phase 1
  trajectory-triage flag deltas. Defines the four-phase arc, the daily 5-tuple
  shape, the ACWR governor invariant the human coach scaffolded but never
  filled (the empty %increase / ACWLR columns), the phase gates that unlock
  mound work, and the lifting half (Hypertrophy → Strength → Strength-Power)
  that runs in parallel on the unified calendar.
---

# Velocity Progression Model

This is the velocity-program-generation reference. The LLM author (Program Engine `author.py`) reads this at generation time alongside the per-pitcher profile, the live `block_library.velocity_12wk_v1` row, and the golden xlsx exemplars to author a personalized 12-week velocity program.

## 1. The four-phase arc

```
Wk 1-3   Base Building          (45-75ft, 50% intent, 40-60 throws/week)
Wk 4-6   Distance Extension     (→105ft,  70% intent, 50-66 throws/week)
Wk 7-9   Compression + Pulldowns(→120ft,  80% intent, 55-70 throws/week)
Wk 10-12 Max Intent + Mound     (full + pulldowns 100%, mound work)
```

Phase data is in `block_library.velocity_12wk_v1.content.phases` (live Supabase). The doc you're reading is the **rationale layer** — it tells the LLM **why** the arc is shaped this way and **what governs deviation from it**.

### Phase 1 — Base Building (Wks 1-3)
- **Intent:** rebuild the throwing base; groove mechanics; establish daily warm-up ladder as invariant.
- **Throwing menu:** long toss + extension throws + light catch play. **No compression/pulldowns. No mound.**
- **Invariant warmup ladder every day** (from `Return to mound` xlsx Wk1 verbatim):
  - 45ft @ 50% (high/pec load 10@30ft, snap-snap rocker ×5, self-toss ×5)
  - 60ft @ 60%
  - 75ft @ 70%
- **Throws/week:** 40-60, distributed across 3 throwing sessions (`throws_per_week=3`).
- **Weekly G load anchor:** Wk1 ≈ 6,960 G-units; Wk3 ≈ 10,935 G-units (per golden curve).
- **Exit criterion to Phase 2:** 3 consecutive throwing days completed without arm-feel <7, no FPM flag triggered, baseline pull-volume met.

### Phase 2 — Distance Extension (Wks 4-6)
- **Intent:** add distance and intent progressively; introduce QB drop-back drills at 50%.
- **Throwing menu:** long toss extended to 90-105ft. Hybrid B days appear. **Pulldowns still NOT introduced.**
- **Wk 4 is the first deload** (Weekly G ≈ 10,375 < Wk3 10,935; 3-up-1-down undulation).
- **Throws/week:** 50-66.
- **Wk 5 ramps back up** (12,049 G); **Wk 6 peaks** (13,516 G).
- **Exit criterion to Phase 3:** sustained 105ft long-toss at 70%, no medial-elbow flag, ACWR rolling in [0.8, 1.3].

### Phase 3 — Compression + Pulldowns (Wks 7-9)
- **Intent:** introduce compression throws ("on a line", 80% intent) and pulldowns. Mound reintroduction first appears here.
- **Pulldowns first appear Wk7** (per `Ramp up` xlsx margin note: "Probable live ABs" Wk7). Start at 1.0× weight at 105/90ft @ 100%.
- **Wk 7 is a deload** (12,090 G, dipping below Wk6 13,516 — second deload of the program).
- **Wks 8-9 ramp:** 12,960 → 13,620.
- **Bullpen volume progression** (per `Return to mound` Wks 5-9): 15 → 20 → 25 → 30 → 40 throws. **Intent:** 85-90% → 90% → 90-95%.
- **Phase gates** (must clear before mound work begins):
  1. ACWR rolling in [0.8, 1.3] for 7 consecutive days.
  2. No active YELLOW/RED triage flag.
  3. No active FPM modification (`FPM.md` gate state must be cleared).
- **Exit criterion to Phase 4:** mound bullpen at 30+ throws, 85-90% intent, no flag trigger.

### Phase 4 — Max Intent + Mound (Wks 10-12)
- **Intent:** realize the velocity gain. Pulldowns at 100%, mound work at 90-95%+. Bullpen volume 45-50 throws.
- **Live ABs are probable Wk 7-8** (per golden) but cleared for game activity Wk 8 + onward.
- **Weekly G load peaks Wk 12** at ~14,616 G.
- **Wk 12 is NOT a deload** in the velocity arc — the program ends at peak; rest-and-reassess phase follows post-program.

## 2. The ACWR governor (the empty columns)

The `Ramp up with Bullpen` xlsx has columns **H (%increase)** and **I (ACWLR)** scaffolded but EMPTY. **This is the human coach's mental model surfaced as a structural artifact — they knew ACWR governed the ramp but never filled the cells.** The Program Engine fills them deterministically.

**Definitions:**
- **Daily throwing load (G):** `≈ throws × intensity_factor × distance_factor`. Verified anchor: Wk1D1 `(45ft × 40 throws × 0.50 intent) → G ≈ 2145`. Implies `load_factor ≈ 0.894` at the (45ft, 50%) reference; calibration is in Phase 2.1 of the engine plan.
- **Acute load (7d):** rolling sum of daily G over the trailing 7 days.
- **Chronic load (28d):** rolling average of weekly G over the trailing 28 days.
- **ACWR (acute:chronic ratio):** acute / chronic.

**Bands:**
- **Sweet spot:** 0.8 ≤ ACWR ≤ 1.3.
- **Caution above 1.3:** non-deload acceleration; flag for review at the next generation.
- **Hard cap 1.5:** Phase 2's `check_acwr_invariant` rejects any program where ACWR exceeds 1.5 at any computed point. Reject → repair → re-prompt → fallback (per Task 2.4 orchestrator).

**Deload cadence:** 3-up-1-down undulation. The golden curve dips at Wk 4 and Wk 7 — the engine reproduces this. Deload weeks have weekly G `≤ 0.85 × prior week` per the structural invariant.

**Weekly G reference curve** (use as a regression target, not a prescription):
```
Wk:    1     2      3      4      5      6      7      8      9      10     11     12
G: 6960  9194  10935  10375  12049  13516  12090  12960  13620  14000  14300  14616
                       ↑deload                     ↑deload
```

## 3. Throwing taxonomy

Day types (from `driveline_throwing_program.md` and `PITCHING-PROGRAM-FINAL.pdf`):

| Day Type | Intent % | Typical Use |
|---|---|---|
| Recovery | 50-60 | Day after high-intent or game; restore blood flow |
| Hybrid B | 60-70 | Base-building, on-ramp |
| Hybrid A | 80-90 | Velocity-development workhorse |
| Velo | 100 | Long-toss with intent + plyo-velo work |
| Plyo Velo | 100 | Heavy plyo balls + crow-hop throws |
| WB Mound Velo | 100 | Weighted ball mound work |
| Mound Velo | 100 | Game-speed mound bullpen |
| Short Box | 60-80 | Half-distance bullpen tune-up |
| Game Day | — | competition |
| No Throw | — | rest day |

**The 5-tuple is the day's atomic unit:** `(distance_ft, throw_count, intent_pct, drill, note)`. The Program Engine schema (`bot/services/program_engine/schemas.py`) encodes this as `ThrowingFiveTuple` — every throwing-day's content must serialize to that shape.

## 4. Lifting half — unified calendar

Velocity is throwing + lifting on the same calendar (the ACWR governor couples them). The lifting arc runs **in parallel** with throwing per `periodized_lifting.xlsx`:

| Lifting Phase | Wks | Weight Range | Rest | Day 1 | Day 2 |
|---|---|---|---|---|---|
| Hypertrophy | 6-8 (begins 6wk post-op equivalent) | 50-75% 1RM | 30s | Posterior Chain | Push/Pull |
| Strength | 9-12 | 80-90% 1RM | 60-120s | Posterior Chain | Push/Pull |
| Strength-Power | 13+ | 87-95% 1RM (+ 75-95% accessories) | 2-5min | Posterior Chain | Push/Pull |

**Mapping into the 12-week velocity arc:**
- **Wks 1-3 (Base Building):** Hypertrophy lifting. 2× per week.
- **Wks 4-6 (Distance Extension):** Hypertrophy → Strength transition by Wk6. 2× per week.
- **Wks 7-9 (Compression + Pulldowns):** Strength. Volume drops with mound introduction.
- **Wks 10-12 (Max Intent + Mound):** Strength-Power emphasis on Day 1; maintenance on Day 2.

**Pull:push ratio invariant:** weekly pull-volume ≥ 2× weekly push-volume (FINAL_research_base.md + Gemini lifting). Phase 2.2 enforces.

**FPM cadence:** flexor-pronator-mass exercise present ≥ 4 of 7 days. Phase 2.2 enforces. `FPM.md` provides the gated state machine — a YELLOW/RED FPM flag pauses progression and switches to Phase-1 isometrics until cleared via Thinker Test.

## 5. Flag modifications (per Phase 1 trajectory triage)

The triage system classifies daily readiness into category scores `tissue / load / recovery` plus an overall flag `GREEN | YELLOW | RED | CRITICAL_RED`. The velocity program responds:

| Flag | Throwing | Lifting | Program-level |
|---|---|---|---|
| GREEN (arm ≥7, energy ≥5, ACWR in band) | Run prescribed day | Run prescribed day | counter advances |
| YELLOW (arm 5-6 OR ACWR 1.3-1.5 OR tissue score <4) | Drop 1 intent tier (Velo → Hybrid A → Hybrid B → Recovery) | Drop 1 accessory; keep compounds | counter advances |
| RED (arm ≤4 OR active mod flag) | Recovery-only (no compression, no pulldowns, no mound) | Light: 1 compound + 2 accessories + 1 core, no explosive | counter pauses (hold event written) |
| CRITICAL_RED (arm ≤2) | Shutdown | Mobility only | counter pauses |

**Banked vs planned:** the engine tracks `progression_state.banked_vs_planned` (delivered:prescribed load ratio). Drifting below 0.75 over a rolling 14-day window triggers a `program_drift` insight to the coach (Plan 8 A4).

## 6. Re-pacing under "the drive" (Phase 4 designed-spike)

If a YELLOW/RED day demands the engine bank a deviation, the **drive policy** decides how the remainder re-paces:
- **silent_absorb:** today's reduction stays today's; remaining weeks unchanged. Risk: end-of-program goal slips.
- **immediate_repace:** remaining weeks shift forward by the missed load. Risk: ACWR spike.
- **banked_deviation:** missed load accrues; the next planned deload absorbs by being demoted to a maintenance week. Recommended default but **decision deferred to v2** per Plan §L7.

## 7. Tunables (operator-visible knobs)

These map directly to `block_library.velocity_12wk_v1.tunable_parameters_schema`:

| Tunable | Type | Default | Notes |
|---|---|---|---|
| `target_velocity_gain_mph` | int | 3 | Realistic 12-week target; 5+ requires extension to 16-week. |
| `deload_preference` | enum: `every_4th_week` \| `acwr_driven` | `every_4th_week` | The golden does both — Wk4 and Wk7 dips are pattern + ACWR-driven. |
| `mound_introduction_week` | int 6-10 | 7 | Earliest reasonable; later for slower ramps or post-op pitchers. |
| `pulldowns_introduction_week` | int 6-10 | 7 | Co-introduce with mound for `mound_introduction_week` ≤ 7. |
| `lifting_domain` | enum: `unified` \| `throwing_only` | `unified` | When `throwing_only`, lifting blocks are empty; lifting tracked via separate program. |
| `bullpen_volume_max` | int | 50 | The `Ramp up` xlsx Wk9 peak. Higher for advanced pitchers. |
| `weekly_throws_band` | [int, int] | [3, 4] | Default 3-day throwing schedule, expandable to 4. |

## 8. Citations

The Program Engine should always cite these when authoring a velocity program:

- `final_research_base` — universal training principles, exercise selection rules
- `driveline_throwing_program` — 16-week phase arc + day-type taxonomy
- `driveline_lifting_programs` — week-over-week set notation + periodization
- `advanced_workload_performance` — acute:chronic ratio bands, deload triggers
- `FPM` — gated return-to-throw state machine (CRITICAL for any pitcher with medial-elbow history)
- `ucl_flexor_pronator_protection` — UCL/flexor protection rules
- `gemini_researching_lifting` — exercise alternatives, push/pull ratio
- `research_gap_analysis` — progression rules (GAP 3)
- `velocity_progression_model` — this doc

## 9. What this doc deliberately does NOT specify

- **Exact exercise IDs.** The LLM author picks exercises from the live `exercises` table per the per-pitcher equipment_constraints / contraindications. Phase 2.3 verifies every id resolves via `exercise_alias`.
- **Specific sets/reps per exercise.** The `periodized_lifting.xlsx` exemplar provides the RIR-based template; the LLM adapts.
- **Calendar dates.** The engine computes `Day.date` from `target_date` (last day) backwards.
- **Coach-individualization narrative.** The LLM authors `Rationale.individualization_notes` based on the pitcher's profile + injury history + baseline.
