# Program Engine — Reconnaissance Dossier

> Date: 2026-05-31 · Companion to `docs/superpowers/specs/2026-05-31-program-engine-design.md`
> Purpose: persist the findings from a 6-front parallel recon so implementation (post-compaction) has the evidence, file:line refs, and extracted numbers without re-running the agents.
> Method: 6 parallel agents — backend plan-gen, JSON templates, research base, frontend UI, golden xlsx/PDF programs, Supabase programs data model.

---

## TL;DR diagnosis

**There is no program engine — there's a stateless daily slot-filler wearing a program costume, and the LLM is contractually forbidden from adding intelligence.** The raw material (golden quantified programs, deep research base, 159-exercise library, trajectory triage) is rich, but it's stranded in formats the engine can't read, inside an architecture with nowhere to put it. The slop is specifically the **layer that turns the material into what the player sees**. The redesign replaces that layer and keeps the substrate. See the spec for the chosen architecture (LLM-forward generation + deterministic guardrails + living knowledge; program is the primary artifact that projects into days).

---

## Front 1 — Backend plan-generation pipeline

**Verdict:** single-day plans only; Python does all the (shallow) programming, LLM is a cosmetic reviewer.

- `plan_generator.py :: generate_plan()` (lines **105-494**) — two-pass. Template selection (**132-181**) is pure rotation arithmetic: lift_preference→day map, else `day_{days_since_outing}`. **45s LLM timeout (373)** ships the Python plan on failure (**382-394**). LLM is given pre-selected exercises and told it **may NOT add any (244-251)**. `_validate_plan` (**634-689**) strips hallucinated IDs and refills to a 6-exercise floor (a count target, not a programming rule).
- `exercise_pool.py :: build_exercise_pool()` (**137-338**) — the actual "programming" engine = slot-filling. `SESSION_STRUCTURE` (**119-125**): GREEN full `(2 compounds,3 accessories,2 core,1 explosive)`; YELLOW drops one accessory; RED light `(1,2,1,0)`. `_pick()` (**341-357**) scores by `(preference, freshness-vs-last-7d, rotation_recommended, random.random())` — **`random.random()` tiebreak ⇒ non-deterministic day-to-day**. No progressive overload, no prior-week awareness, no pairing logic. Prescription from a static per-intent dict (**360-392**).
- `starter_7day.json` `global_rules` (**239-245**) ENCODE the real coaching logic (2:1 pull:push, FPM 4/7 days, +5-10lb after 2 consecutive hit sessions, WHOOP<33%→recovery) — but as **prose strings, never parsed or enforced**.
- `block_library` + `team_programs.py :: resolve_team_block` (**15-91**) — the ONLY genuine periodization (effort% ramps 50→70→80→90), but **throwing-only**, activates only if a coach assigns a `team_assigned_blocks` row (`coach_routes.py:444`), and just **replaces the day's throwing dict** (`plan_generator.py:1241-1256`) with no progression state.
- `triage.py :: _build_protocol_adjustments` (**803-865**) — a **safety gate**, not a brain: only caps/downgrades/removes. Returns `flag_level, modifications, protocol_adjustments, category_scores{tissue,load,recovery}, baseline_tier, reasoning`.
- `get_upcoming_days()` (**1360-1412**, consumed `api/routes.py:258`) — the only forward view; reads the **static template**, bypassing the pool and triage. Preview ≠ reality.
- Research is **citation-only**: `resolve_research` dumps doc text into the prompt; LLM told to "cite" but can't change the program.

## Front 2 — JSON / MD templates

**Verdict:** a single-day rotation model; no week axis anywhere in JSON.

- Anchors: `starter_7day.json` (lifting) + `throwing_rotation_map.json` + `throwing_day_types.json`, keyed `day_0..day_6` where **day_0 = game/appearance**, rest are recovery-to-readiness positions relative to last outing.
- The only multi-week content — `throwing_ramp_up.md` (6wk), `return_to_mound.md` (8wk) — is **prose Markdown, no parseable schema** (the unconverted shadows of the golden xlsx).
- Reusable primitives worth keeping: **`prescription_mode`** abstraction (power/strength/hypertrophy/endurance/warmup → resolved at runtime); **`template_ref` dotted-path composition** (e.g. `jband_routine_v1.pre_throw`); **`volume_summary {total_throws_estimate, max_distance_ft, max_intent_pct}`** (the quantitative spine that should become the periodized axis); `throwing_day_types` hierarchy (no_throw<recovery<recovery_short_box<hybrid_b<hybrid_a<bullpen); **`mobility_videos.json` weekly_rotation** (the ONE working multi-week JSON — week→slots[]).
- Problems: **4+ incompatible "block of exercises" schemas**; free-text prescriptions ("Work out to max distance"); orphan/missing exercise_ids; data bugs (`dynamic_warmup` reuses `ex_080` for 3 scap moves; mobility week-5 lists `mob_015` twice; `arm_care_heavy` reuses `ex_041`); `reliever_flexible.json` uses bare name strings; `throwing` tag in `starter_7day` doesn't map to `throwing_day_types` keys (two drifting vocabularies).

## Front 3 — Research knowledge base

**Verdict:** a **serialization gap, not a research gap.** The content to build programs exists; it's trapped in prose.

- `FINAL_research_base.md` ≈ **"80% of a compilable program engine"**: 40-exercise DB (strength/power %1RM, tempo, rotation-day, contraindication→substitution), a complete 7-day starter template, flag modifications (GREEN/YELLOW/RED with concrete deltas), deload (every 4th wk −15-20% load/−30% vol, FPM exempt), progression (+5-10lb after 2 clean sessions), screening thresholds.
- `driveline_lifting_programs.md` — **week-over-week sets as notation** (`3x6 → 4x6 → 3x6` = wks 1→2→3); periodization wk1-3 base / wk4-5 peak / wk6 deload; pull:push 2:1.
- `driveline_throwing_program.md` — day-type taxonomy keyed to intent% (Recovery 50-60 / Hybrid B 60-70 / Hybrid A 80-90 / Velo 100), plyo drill order, weighted-ball ladders, **16-week phase arc**.
- `FPM.md` — **gated return-to-throw state machine** (Phase 1 isometrics until "Thinker Test" pain-free → Phase 2 high-rep wrist flexion; advance load only after 30 reps × 2 consecutive pain-free days).
- `tightness_triage_framework.md`, `recovery_physiology.md`, `ucl_flexor_pronator_protection.md`, `advanced_workload_performance.md` (A:C ratio bands), `supplamentation.md`, `arm_care_program.md`, `brice_arm_care_reference.md` (personal), `bot_intelligence_architecture.md` (origin of the "retrieval+citation" posture), **`research_gap_analysis.md` (self-diagnoses "GAP 3: PROGRESSION MODEL IS MISSING" and supplies the rules — a de-facto requirements doc)**.
- **13/14 docs have resolver frontmatter** (id/applies_to/triggers/priority/contexts). **But the richest *generative* docs are tagged `contexts: coach_chat` / `priority: reference` — NOT routed into plan_gen.** The system injects the "why" (physiology) into plan-gen and reserves the "how" (templates, sets/reps, progression) for chat. **Backwards.**
- **No canonical exercise key** — doc names don't reconcile with each other or the 159-row `exercises` table ("Seal Row"/"Chest-Supported Row", "RFE Split Squat"/"Bulgarian"). An alias map is a prerequisite.

## Front 4 — Frontend program/plan UI

**Verdict:** `DailyCard` is the crown jewel; the *program* surface is a header with no real arc (4/10).

- `DailyCard.jsx` — mature 5-phase guided flow (warmup→arm care→lifting→throwing→mobility), completion state machine (`computePhaseOrder`/`isPhaseComplete`/`getPhaseItems`), swaps, research "why" sheet, dual-source lifting. **Preserve.**
- `Plans.jsx` → `ProgramHero` + `WeekArc` + `ScheduleCard` + `TodayDetailCard` + `ProgramHistoryTimeline`. `ProgramHero` shows only a **flat single-phase bar** (`completionPct = currentWeek/totalWeeks`), never phases end-to-end. `WeekArc` shows **one rotation window with hardcoded day-index labels** (`_day_emoji_and_label` → "Heavy lift/Bullpen/Side"), not actual program content. **Zero progression metrics** on the program page.
- `PlanBuilder.jsx` — a goal-less **one-off single-day** generator (`/generatePlan` with `{plan_type, duration_min, emphasis[]}`), disconnected from programs.
- **Two disconnected mental models**: "Programs" (coach-assigned rotation wrapper) vs "Plans" (pitcher one-off days), no bridge.
- Data shapes: `program = {name, current_phase:{name}, phase_progress:{week,total}}`; `ProgramDetail` consumes `phases_snapshot[] = {phase_id, name, week_count, phase_type, default_training_intent}`. **The existing components can render a new program if the backend emits these shapes (zero new components).**
- Reuse: DailyCard phase state machine, ProgramHero segmented bar+ring, DayBubble/WeekArc strip, ProgramHistoryTimeline vertical timeline, the maroon/cream token system + bottom-sheet pattern.

## Front 5 — Golden human-authored programs (the reference implementations)

**Verdict:** a two-level periodization-as-state-machine — `(microcycle of session types) × (content library per type)` — plus fully-quantified multi-week throwing macrocycles. This is the model to reproduce.

- **`Return to mound progression … (4).xlsx`** (CROWN JEWEL #1, rehab/RTT, actually 9 weeks): 5-col grid `(day, distance_ft, throw_count, intensity_decimal, drill/instruction)`. **Invariant warmup ladder every day**: 45ft@0.5 (high/pec load 10@30, snap-snap rocker ×5, self-toss ×5) → 60@0.6 → 75@0.7. Pulldowns (1.0 @105/90ft) first appear **Wk3**. Mound reintroduction gated: bullpen volume ramps **15→20→25→30→40→45→50** throws (Wks 5-9); intensity 85-90%→90%→90-95%. **Margin-note phase gates**: "Probable live ABs" (Wk7), "Probable clearance for game activity" (Wk8).
- **`Ramp up with Bullpen … (1).xlsx`** (CROWN JEWEL #2, 12 weeks, richest schema — the ONLY file with a header row): cols `B=Distance, C=Throws, D=Intent, E=Drill, F=daily total throws, G=Volume (load units), H=%increase, I=ACWLR`. **Verified load math:** F = Σ daily throws; **G ≈ intensity-weighted volume** (Wk1D1: 40 throws, dist×throws=2400, G=2145 ≈ ×0.89). **Weekly G ramps `6960 → 9194 → 10935 → 10375 → 12049 → 13516 → 12090 → 12960 → 13620 → … → 14616`** — a **3-up-1-down deload undulation** (Wk4 and Wk7 dip). **H (%increase) and I (ACWLR) columns are present but EMPTY — the coach scaffolded acute:chronic-workload-ratio governance but never filled it.** This is the single most important "gold" signal: **the human mental model is ACWR-governed progression.**
- **`The Program  (1).xlsx`** (flagship, 7 tabs): Tab 1 = a **type matrix** (two 7-day starter rotations + a reliever rotation) where each "Day N" is a list of session *types*, not exercises. Tabs 2-7 = the *content* per type (Dynamic Warmup, Post Throw Stretch, Arm Care Light, Arm Care Heavy, Plyocare, Dugout). **Anti-phased intensity rule**: heavy arm-care + full/heavy plyos on outing-distal days (D2/D3/D5); light arm-care + recovery throws on outing-adjacent days (D1/D4). **Plyocare = 6-level ladder** (weight + climbing %effort + named drill; Velo Plyo tops at "high intent baseball throws 100%"). Arm Care Heavy is superset-structured (A1/A2…).
- **`PITCHING-PROGRAM-FINAL.pdf`** (36pp, text-extractable): day-type vocabulary (**Recovery / Hybrid A / Hybrid B / Velo / Plyo Velo / WB Mound Velo / Mound Velo / Short Box / Game Day / No Throw**); named phase macrocycles (**Velocity Phase**; **Pitch Design: Base Line → Shape → Execution**; **In-Season reliever block**); weighted-ball protocol (warmup% → throwing program → WB pulldowns → recovery; 9/7/5/3oz); **RIR-based lifting tables** (A1/A2…D2 supersets, rest-in-min, week-block sets/reps, RIR targets "2RIR"/"Near Maximal", paired plyo/sprint row).
- `Landon Starters.xlsx` (consolidated starter reference + soft-tissue "tightness map"), `Arm care adjustment.xlsx` (**pronator-focus** arm-care variant — injury-specific superset swap), `Brice Thoughts .xlsx` (A/B nerve-glide/ulnar protocol + standing-orders block), `uchi_exercise_library.xlsx` (Lower/Upper + muscle-target taxonomy + Med Ball tab), `mobility_links.xlsx` (weekly mobility rotation — origin of the 10-week cycling concept).
- **Data hygiene:** the two crown-jewel files exist on disk only as **macOS aliases into Google Drive** (`~/Library/CloudStorage/GoogleDrive-…/My Drive/…`) — openpyxl sees "not a zip file". WB weights corrupted to Excel dates (`9/7oz`→`2023-09-07`). Free-text exercise names, no IDs. PDF is image-heavy (spacing shredded on text extract).

## Front 6 — Supabase programs data model

**Verdict:** the ambitious schema exists but is empty/unwired; the periodized content is disconnected from the day scaffold; nothing is assigned.

- `block_library` columns: `block_template_id, name, description, block_type, duration_days, content(jsonb), source, domain, goal_tags(array), duration_range_weeks(int4range), compatible_phases(array), tunable_parameters_schema(jsonb), week_scaffold_json(jsonb), research_doc_ids(array), modification_rules_json(jsonb), implied_phase`.
- **6 blocks** (goal_tags populated — the goal taxonomy exists): `velocity_12wk_v1` [velocity], `longtoss_ramp_6wk_v1` [longtoss, return_to_throwing], `offseason_base_4wk_v1` [offseason_base], `tpl_starter_7day_cadence_v1` [in_season_maintenance], `hypertrophy_8wk_v1` [hypertrophy] (lifting), `in_season_lifting_starter_v1` (lifting). **Lifting blocks `content` is a 98-118 char shell**; throwing richer (velocity 1096, longtoss 569).
- **On ALL 6 blocks: `tunable_parameters_schema = {}`, `modification_rules_json = null`, `research_doc_ids = []`.** The ambitious primitives are columns with no content.
- **`velocity_12wk_v1` `content`** = real 12-week periodization: 4 phases — Base Building (wk1-3, 45-75ft, 50%, 40-60 throws), Distance Extension (wk4-6, →105ft, 70%), Compression+Pulldowns (wk7-9, →120ft, 80%), Max Intent+Mound (wk10-12, 90%, pulldowns 100%); `throws_per_week:3`, `rest_days_pattern:[3,7]`. **`week_scaffold_json` = a flat repeating 7-day rotation** (`scaffold_kind: "calendar_relative_repeating_7day"`, day_0..day_6 labels, note "Day-content resolution defers to exercise_pool at consume time") — **it does NOT reference the phases.** Periodization and day scaffold live in the same row, disconnected.
- `team_assigned_blocks = 0 rows` (nothing in use). `training_phase_blocks = 5`. `saved_plans = 11`. `daily_entries with plan_generated = 124`. `training_programs` (orphan, ~12 rows) has `pitcher_id, template_id, phases_snapshot(jsonb), total_weeks, start/end, deactivated_at` — the natural home for a `PitcherProgram` instance.
- `scripts/seed_block_library.py` is the builder (source string `spec_program_builder_v1`); it never populated modification_rules/tunable/research. No spec existed in `docs/superpowers/specs/` before this redesign.

---

## What this implies (carried into the spec)

1. Reproduce the golden **two-level model** (session-types × content library) and the **ACWR-governed weekly load** (the empty `%increase`/`ACWLR` columns are the intended governor).
2. The gold is **content, not code** — keep research/templates/golden programs as editable, retrievable knowledge; the LLM authors from it; determinism enforces content-independent invariants.
3. **Reuse** the substrate (exercise library, research docs, trajectory triage as readiness, WHOOP, DailyCard, the existing program-view component shapes). **Retire** the `exercise_pool` slot-fill selector + the LLM-as-formatter contract.
4. Prereqs: **exercise alias map**; **copy the two Drive-alias xlsx into the repo**; author the velocity knowledge pack as content; **make throwing a first-class quantified block (the 5-tuple)**.

---

## Front 7 — The SHIPPED Program Builder (added 2026-05-31, post-initial-recon)

**Verdict:** a fully-built funnel + lifecycle + projection seam already exists; the slop is one generation function. This **supersedes** the earlier assumption that we're working against the old `plan_generator` path or building greenfield. Full reuse/replace/conflict map + open questions live in **spec §14**.

- **Shipped scope:** Plans 1–8, merged via PRs #31/#32, last commit `c3c1d16`. Funnel: `program_builder.match_candidates` → `program_builder_socratic.advance` (LLM interview, ≤6 Qs) → `program_generator.generate_program` → `program_lifecycle` (draft/activate/archive) → `program_runtime` + `program_aware_planner` (projection) → `checkin_service._select_plan_path` (dispatch).
- **New `programs` table** (`migration 020_programs_core.sql`) — the live, wired artifact store: `generated_schedule_json {days:[{day_index, template_key, date, anchor_kind?}]}`, counters, holds, `created_by_role pitcher|coach`, partial-unique-index one-active-per-(pitcher,domain). Companion tables: `program_builder_sessions`, `program_hold_events`, `program_schedule_revisions`, `program_generation_failures`, `coach_visible_override_events`.
- **Live prod state (queried):** `programs` = 6 rows (5 active incl. `landon_brice` throwing on `tpl_starter_7day_cadence_v1`); **`program_aware_plan_gen` flag ON for `landon_brice` only**; `program_builder_sessions`=19; holds/failures=0. Legacy: `training_programs`=12 active (orphan, `active_program_id` FK), `team_assigned_blocks`=0 (dead).
- **Generation core (THE SLOP):** `program_generator._build_schedule_from_scaffold` = `days[i] = rotation_template_keys[i % 7]` — pure 7-day rotation repeat, no phases/progression/intensity/deload. The periodized `block_library.content.phases` (velocity 4-phase arc) is **read by no one in this path**. `_validate_schedule` = day-count only. The Socratic LLM only emits `{chosen_template_id, tuned_spec}` — it **cannot author structure**.
- **Projection seam (already wired, behind flag):** `program_runtime.get_active_program_day` → `program_aware_planner.compose_program_aware_plan` calls **legacy `generate_plan` with `rotation_day_override`** (`"day_3"`→rotation day 3 → `exercise_pool` slot-filler); tagged `source='program_prescribed'`. Green/Yellow advances `current_day_index`; Red writes `program_hold_events` and holds (Approach B). **This is the `project()` seam OPEN-#1 wanted — reuse + deepen.**
- **Rich `block_library` columns are mostly dead:** `week_scaffold_json.rotation_template_keys` used (rotation repeat); `goal_tags`/`compatible_phases`/`duration_range_weeks`/`implied_phase` used (candidate match); **`tunable_parameters_schema`=`{}`, `modification_rules_json`=null, `research_doc_ids`=[]` on all rows** → tuning/mods/citations effectively no-ops (citations panel always empty). `content.phases` read by nobody in the new funnel.
- **API:** `POST /api/programs/builder/{candidates,turn,finalize,generate,interpret-goal}`, `/api/programs/{id}/{activate,archive,recompute}`, `GET /api/programs/{active,drafts,history,templates,holds-today}`; coach mirrors at `/api/coach/programs/*`. (Legacy `GET /api/pitcher/{id}/program*` still reads `training_programs` for the OLD Plans tab.)
- **UI:** mini-app `pages/Programs.jsx` + `ProgramRibbon.jsx` + shared `BuilderSlideOver.jsx` (INPUTS→Socratic chat→PREVIEW→Activate); coach `TeamPrograms.jsx` + `BuildEntrypointSelector` + `PitcherPicker` + `components/programs/*`. **UI gap:** preview/active cards show only `template_key` + `Day N of M` — no intensity/phase/progression, because nothing periodized is generated.
- **`prohibited_throw_kinds` / prohibited-day conflict logic:** a Plan 5–9 design intent that **never shipped** (`recompute` explicitly has no conflict check). `prescription_mode` / `template_ref` / `volume_summary` live in `data/templates/*` JSON, not the `block_library` schema.
- **Three coexisting program systems:** (1) new `programs`+funnel [live], (2) legacy `programs.py`/`training_programs` [orphan, 12 rows], (3) `team_programs`/`team_assigned_blocks`/`block_library.content` [dead, 0 rows]. Naming collision (`programs` vs `training_programs`) is a real trap.
- **Files that matter most:** `bot/services/program_generator.py` (replace), `program_aware_planner.py` + `program_runtime.py` (keep — projection seam), `checkin_service.py:148-322` (dispatch seam), `shared/builder/BuilderSlideOver.jsx` (keep — front door), `scripts/migrations/020_programs_core.sql` (persistence shell to enrich), `seed_block_library.py` + live `block_library` (knowledge store to populate).
