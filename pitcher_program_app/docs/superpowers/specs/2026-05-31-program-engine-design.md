# Program Engine — Design Spec

> Status: **Draft for review (Revision 3)** · Author: Landon + Claude · Date: 2026-05-31
> Revision 2 reframed the engine from a deterministic compiler (Approach C) to **LLM-forward generation with deterministic guardrails (B+)**, replaced the static typed-spec with a **living knowledge layer**, and made the **multi-week program the primary artifact** that *projects* into days.
>
> **★ Revision 3 (reconciled with the shipped Program Builder — see §14).** A focused recon found that a full **Program Builder is already shipped** (Plans 1–8, PRs #31/#32): a new **`programs` table** + funnel (`program_builder` → `program_builder_socratic` → `program_generator` → `program_lifecycle`/`program_runtime` → `program_aware_planner`), with a Socratic interview, draft/activate/archive lifecycle, a **projection seam already wired into check-in**, hold-on-red counters, a coach mirror, and the **`program_aware_plan_gen` flag already ON for `landon_brice`**. **Consequence:** this is **NOT a greenfield build** — building from scratch would fork an existing feature. The correct strategy is to **replace the generation core in place (`program_generator._build_schedule_from_scaffold` + `_validate_schedule` + the rotation-day delegation), reuse the funnel/lifecycle/projection/flag substrate, and populate the empty knowledge columns.** The new program persists on the **`programs` table** (NOT `training_programs`, which is orphaned legacy v0 — Rev-2's "revive `training_programs`" advice is **stale/superseded**). Where this doc earlier said "separate worktree / clean-room from scratch," read it as **"isolated branch, replacing the generation core, reusing the existing shell."** §14 holds the full reuse/replace/conflict map.

---

## 1. The real goal (stated plainly)

> *Here is a player with XYZ context who wants to gain velocity and keep his arm healthy. The product reads its deep research base and golden templates, and — like a brilliant coach — authors a genuinely individualized multi-week program for him. It then presents and tracks it, so it beats both reading a Google Sheet and asking a raw LLM for a plan.*

The unit of value is **the program** — a multi-week, goal-oriented artifact with intent. The **day is a projection** of that program (locally adjustable by the player's in-the-moment feel, but always oriented under the program's goal).

**V1 = clean-room demo:** one real pitcher (`landon_brice`), goal = **velocity**, lifting + throwing unified. Standalone — it does **not** touch the live daily pipeline (no `triage`/`exercise_pool`/`plan_generated` wiring). The engine is **goal-agnostic**; velocity is simply the first authored knowledge pack.

### V1 "done" / the demo wow
1. Engine reads `landon_brice`'s real context (profile, injury history, baseline) + the **current** research docs/templates → generates a full, individualized velocity program.
2. It renders as a **viewable, trackable artifact**.
3. **Living-knowledge proof:** edit a research doc/template, regenerate, and the program visibly changes — **no code change**.
4. **Projection proof:** project a single day from the program and show it adapt to a "dead arm" readiness input — while staying oriented to the goal.

---

## 2. Diagnosis — where the slop actually is

The raw material is rich (golden programs, research base, 159-exercise library, trajectory triage, WHOOP). The slop is **specifically the layer that turns that material into what the player sees**: a stateless daily slot-filler (`exercise_pool` fills fixed slots, `random.random()` tiebreak) wrapped by an LLM that is *forbidden from adding intelligence* (`plan_generation_structured.md:13-17` — it only reformats and writes prose). There is no program artifact, no progression memory, periodization is a label, and research is injected as decoration. **We replace that curation layer. We keep the substrate.**

---

## 3. Architecture — three planes

LLM-forward generation, deterministic guardrails, living knowledge. Intelligence and safety live in different planes, so we get both.

### 3a. Knowledge plane — *living, editable, never compiled into code*
The research docs, templates, golden programs, and exercise library are **editable content**, retrieved into the generation context at run time (extend the existing `research_resolver` pattern to also pull goal-relevant templates/exemplars). **Edit a doc → the next generation reflects it, with no code change.** Nothing here is hardcoded into Python. *(This kills Revision-1's "typed ProgramSpec compiled into `block_library`.")*

### 3b. Generation plane — *LLM-forward; this is the brain*
A brilliant-coach LLM (reasoning model, latency-tolerant at generation time) reasons over **player context + goal + retrieved knowledge** and **authors** the program: phase structure, week-by-week progression, exercise selection, intent, the "why." This is the "throw my context at a great coach" magic. Generation happens **once** (program creation) and the result is **persisted** — so day-to-day rendering is cheap and stable.

### 3c. Guardrail plane — *deterministic, content-independent; a slop-catcher, not the brain*
A set of **universal invariants** that hold regardless of what any doc says — so editing content never requires touching them: ACWR/load math, injury contraindications, pull:push ratio, deload presence, monotonic intensity ramps, exercise IDs resolve to the library. They **validate → repair → reject+re-prompt** the LLM's output, and if generation can't be made valid (or times out), a **deterministic fallback** produces a safe program. The fallback floor is still a real periodized program, not slop.

> **Net role split:** the LLM *generates*; the docs *guide and tune*; the deterministic plane *keeps it honest*. Determinism is the safety net, not the compiler.

---

## 4. Data model

### Knowledge layer (editable content; source of truth)
Lives where it's easy to edit and already partly lives: `data/knowledge/research/*` (frontmatter docs), `data/templates/*`, the **golden programs copied into the repo** (see prereqs), and the `exercises` library. A resolver assembles the goal-relevant subset into the generation context. Optionally, curated **template exemplars** may also live in `block_library` as *content* (not a compiled spec).

### `PitcherProgram` — the generated artifact (primary object)
The hero. A persisted, individualized, multi-week program instance:
```
PitcherProgram
  ├─ header: { pitcher_id, goal, knowledge_version, generated_at, total_weeks, target_date, status }
  ├─ structure: phases[] → weeks[] → days[] (each day: intent, session targets — throwing 5-tuple + lifting blocks)
  ├─ rationale: the coach's "why" (phase logic, individualization notes) + cited research_doc_ids
  └─ progression_state: current_week/phase, acwr_rolling, banked_vs_planned, gate_status
```
Stored by reviving/enriching the orphan **`training_programs`** table (already has `pitcher_id`, `phases_snapshot`, `total_weeks`, `start/end`). It stores **instances**, not authored specs.

### The day — a *projection* of the program (see §5; mechanism is OPEN)
For v1 standalone, the day is computed by a clean `project(program, date, readiness)` function and shown in the demo artifact — **not** written into `plan_generated` and **not** routed through the live daily pipeline.

---

## 5. OPEN DESIGN QUESTION #1 — "the drive" (program → day projection)

**Deliberately not decided.** This is the most important seam and we agreed not to lock it early.

- **Leading hypothesis (not final):** `day = project(program, date, readiness)`. A low-feel day dials intensity/volume down *within bounds*; the deviation **feeds back to the governor, which re-paces the remaining weeks to defend the goal.** Override changes *today*, never the destination.
- **To resolve later:** how much can a day override; does a bad day trigger re-pacing or silent absorption; how readiness (feel + triage + WHOOP) maps to a bounded modulation; how "oriented under the goal" is enforced. Build `project()` and its feedback loop as first-class, well-tested functions even in v1, because this is the seam the eventual live integration depends on.

---

## 6. Knowledge propagation — coach-mediated, player-confirmed

When research docs/templates change, a pitcher mid-program is **not** silently rewritten. Instead:
1. New knowledge flows automatically to **future** generations (the living knowledge layer).
2. For a **live** program: the in-app **coach becomes aware the relevant content changed** and **proposes a modification**; the **player verifies** before it lands.

This routes living content through the existing coach loop with human consent — nimble *and* safe. (No auto-mutation of active programs.)

---

## 7. The guardrails (content-independent invariants)

Hold for **any** structure the LLM proposes, so novel architectures stay safe and doc edits never touch them. Each can **repair**, else **reject + re-prompt**, else trigger **deterministic fallback**:
1. ACWR within band (default 0.8–1.3, hard cap ~1.5) at every point; weekly ramp within increase cap.
2. Deload cadence present (≥1 per ~3–4 accumulation weeks; the golden 3-up-1-down).
3. Phase gates placed before high-intensity/mound/pulldown phases (readiness-conditional, layered on time).
4. Throwing intensity monotonicity (no 50%→100% jumps; max-intent gated behind distance/volume base).
5. Lifting invariants: pull:push ≥ 2:1 weekly; FPM ≥ 4/7 days.
6. Equipment hard-filter; injury contraindications (e.g. flexor/pronator → no fixed-scap pressing / vertical pulling, per `FPM.md`).
7. Exercise IDs resolve to the live `exercises` table (no orphans).

**Load math (default, tunable, regression-tested against the golden `G` curve):** throwing load ≈ `Σ(throws × intensity_factor)` with distance weighting; lifting load ≈ `Σ(sets × reps × intensity_factor)`. Acute = trailing 7d; chronic = trailing 28d avg.

---

## 8. What we reuse vs. retire

**Sacred — reuse via thin read interfaces:** the `exercises` **library** (data), research docs, templates, golden programs, profile/injury data, **trajectory triage (Phase 1) as a *readiness signal***, WHOOP.

**Retires (slop-DNA):** `exercise_pool.py`'s **selection logic** (slot-fill + `random.random()` tiebreak) — in LLM-forward generation, *selection is the LLM's job grounded in the library + research*; the LLM-as-formatter contract; the daily re-assembly framing. *(Confirmed: "exercise pool is good" = the exercise **library** is sacred; the **selector** retires. Flag if that's wrong.)*

---

## 9. Build approach

- **Separate git worktree.** Build the engine as a clean, well-bounded module (`program_engine/` or similar) that reads the sacred substrate through thin interfaces and owes nothing to the current generation pipeline. Conform to codebase conventions (Python style, Supabase access via `db.py`, env config) — but do **not** retrofit the idea into `plan_generator.py`/`exercise_pool.py`.
- **Standalone for v1.** No wiring into `triage`/`exercise_pool`/`plan_generated`. The demo renders the artifact directly.
- **Stable seams.** `project()` (the drive) and the knowledge resolver are first-class and tested, so later live integration is a wiring job, not a redesign.

---

## 10. Prerequisites & workstreams

0. **Exercise canonical key / alias map** *(grounding dependency)* — research/golden exercise names don't reconcile with the 159-row `exercises` table; the LLM's selection and guardrail #7 need a reliable join. Build the alias map.
1. **Data hygiene** — copy the two crown-jewel xlsx (`Return to mound…`, `Ramp up w/ Bullpen…`) from Google Drive into the repo as editable knowledge/exemplars (they're macOS aliases today).
2. **Author the velocity knowledge pack as *content*** — extract the velocity arc + ramp curves + PDF lifting tables into editable docs/templates the resolver pulls (NOT Python). Make throwing a first-class quantified block (the 5-tuple).
3. **Knowledge resolver** — extend `research_resolver` to assemble goal-relevant research + templates + exemplars into the generation context.
4. **Generation + guardrails + fallback** — the LLM author, the content-independent validators, the deterministic safe fallback.
5. **`PitcherProgram` persistence** — enrich `training_programs`; store the artifact + progression_state.
6. **`project()` + demo artifact** — the day projection (per the OPEN question) and a minimal viewable/trackable render for the demo.

---

## 11. Risks & mitigations

| Risk | Mitigation |
|---|---|
| LLM-forward → variance / non-reproducibility | Generate **once** and persist; guardrails repair/reject; deterministic fallback floor; regenerate is explicit |
| Living content → unsafe or chaotic live programs | Guardrails are content-independent; **coach-mediated, player-confirmed** propagation (no silent mutation) |
| "The drive" decided too early / wrongly | Explicitly **deferred** (OPEN #1); build `project()` as a tested seam, decide the policy with more thought |
| Demo→production gap (clean-room never integrates) | Stable seams (`project()`, resolver) designed for later wiring; substrate reused, not duplicated |
| Exercise-name reconciliation | Alias map prereq; guardrail #7 rejects orphans |
| Greenfield becomes a rewrite | Scope is the **engine module only**; data/infra/auth/UI untouched; worktree-isolated |
| LLM cost/latency at generation | One-time op; reasoning model acceptable; fallback on timeout |

---

## 12. Appendix — asset inventory (the gold, from recon)

- **Two quantified throwing macrocycles** (`Return to mound` 9wk, `Ramp up w/ Bullpen` 12wk): day-by-day `(distance, throw_count, intensity%, drill, note)`; invariant warmup ladder (45ft@50%→60@60%→75@70%); phase-gate unlocks; **`%increase`/`ACWLR` columns scaffolded** (the ACWR mental model).
- **`PITCHING-PROGRAM-FINAL.pdf`** (36pp): day-type vocabulary; named phase macrocycles (Off-season→Velocity→Pitch Design→In-season); RIR-based lifting tables.
- **`The Program.xlsx`**: two-layer model (session-types × content library); anti-phased intensity; 6-level plyocare ladder.
- **Research base**: `FINAL_research_base.md` ≈ "80% of a compilable engine"; `driveline_lifting` week-over-week set notation; `FPM.md` gated RTT state machine; `research_gap_analysis.md` self-diagnoses "GAP 3: PROGRESSION MODEL IS MISSING" and supplies rules.
- **Substrate**: 159-exercise library; Phase-1 trajectory triage (readiness); WHOOP; profile/injury data.

> Full recon evidence (file:line refs, extracted numbers, schemas): `docs/superpowers/research/2026-05-31-program-engine-recon.md`.

---

## 13. Decision log (the brainstorming trail — for post-compaction context)

Decisions made, in order, with the reasoning so they aren't re-litigated:

1. **North star = "both, but generation first."** Generation quality must be real before UI polish matters. The leverage is the program engine, not another coat of paint on the daily card.
2. **Diagnosis accepted:** the slop is the curation-into-UI layer (slot-fill + LLM-as-formatter + no program model), not the data/infra. The gold is real but stranded.
3. **Architecture: started at Hybrid C (deterministic-compiler-primary), then revised to LLM-forward "B+"** under the "keep it the simple AI-program idea" lens — the LLM authors; determinism + docs are guardrails/tuning. Rationale: "just throw my context at a brilliant coach" is LLM-forward; a deterministic compiler reintroduces the rigidity that buries the idea.
4. **V1 slice = velocity, lifting + throwing unified** on one calendar (ACWR couples them) — the most faithful expression of the gold and the strongest answer to "why not just ask an LLM."
5. **Two-layer model → living knowledge layer.** Rejected the Rev-1 "typed ProgramSpec compiled into `block_library`" because it freezes knowledge into code. Knowledge stays **editable content, retrieved at generation time** (edit a doc → next generation reflects it, no code change).
6. **Ontology: program is the primary artifact** that *projects* into days. Days can be locally overridden by in-the-moment feel but stay oriented under the goal.
7. **Self-serve initiation** (pitcher picks goal + tunables; coach has visibility/override).
8. **LLM latitude: high** — may propose novel structures beyond spec exemplars; the **constitution is principle-based** (content-independent invariants) so novelty stays safe; deep reasoning at the latency-tolerant compile step; deterministic safe fallback always available.
9. **Cheapest UI** = conform to existing `ProgramHero`/`DailyCard` contracts + one goal-picker button + a documented API. The real pitcher UI is a **separate parallel effort** — this engine must not collide with it; the API contract is the seam.
10. **OPEN #1 — "the drive" (program→day projection): deliberately deferred.** Leading hypothesis = re-pace to defend the goal; not locked (needs more thought). Build `project()` as a tested seam regardless.
11. **Knowledge propagation = coach-mediated, player-confirmed.** No silent mutation of live programs; the in-app coach notices content changed and proposes a modification the player verifies.
12. **`exercise_pool` selector retires** (LLM selects, grounded in the library); the exercise **library** stays sacred.
13. **Build in a separate worktree** as a clean engine module; **v1 = clean-room demo on `landon_brice`**, goal-agnostic engine underneath.

### Still open before / during implementation
- **OPEN #1: "the drive"** — the projection + override + re-pacing policy (§5).
- ACWR load-unit calibration (validate against the golden `G` curve as a regression fixture).
- Exact knowledge-resolver assembly strategy for goal-relevant templates/exemplars.

---

## 14. Reconciliation with the shipped Program Builder (Rev 3)

A focused recon (2026-05-31; folded into the recon dossier as Front 7) found the Program Builder is **already built end-to-end** — much of what Rev 2 proposed exists. The redesign is therefore a **core replacement inside an existing shell**, not a new system.

### What already exists (REUSE — do not rebuild)
- **`programs` table + lifecycle** (`migration 020_programs_core.sql`): draft/active/archive state machine, partial-unique-index "one active per (pitcher, domain)", `generated_schedule_json`, counters, hold semantics. Plus `program_builder_sessions`, `program_hold_events`, `program_schedule_revisions`, `program_generation_failures`, `coach_visible_override_events`. **This is the home for `PitcherProgram`** (not `training_programs`).
- **Socratic interview + `BuilderSlideOver.jsx`** (`shared/builder/`): the goal-picker + "throw context at a coach" front door. Free-text goal interpretation (`goal_interpreter`), an LLM conversation, INPUTS→chat→PREVIEW→Activate. **The change is the LLM's output contract** — from `{template_id, tuned_spec}` to *authored program structure*.
- **Projection seam (already wired, behind the flag):** `program_runtime.get_active_program_day` → `program_aware_planner.compose_program_aware_plan`, with Green/Yellow→advance, Red→`program_hold_events` (Approach B). **This IS OPEN-QUESTION #1's `project(program, date, readiness)` seam — reuse and deepen it, don't invent it.**
- **Dispatch seam:** `checkin_service._select_plan_path` + the `program_aware_plan_gen` feature flag (**ON for `landon_brice` only** — our exact v1 target). The integration point if/when v1 goes live.
- **Re-anchoring** (`program_anchoring.recompute_program_schedule` — scheduled-throw relative days), **coach mirror endpoints**, **favorites**, **citations panel**, the **`/programs/templates|active|drafts|history`** read contracts, and `mini-app/src/pages/Programs.jsx` / `ProgramRibbon.jsx` / `ProgramDetail.jsx`. Reuse wholesale.
- **`block_library` as the Template/knowledge store** — the schema (`goal_tags`, `research_doc_ids`, `tunable_parameters_schema`, `content`) is the right shape; it just needs to be **populated** (all rows currently `{}`/`null`/`[]`).

### What is the slop (REPLACE)
- **`program_generator._build_schedule_from_scaffold`** — the rotation-repeat core (`days[i] = rotation[i % 7]`). Replace with **LLM-forward authoring** that reads `content.phases` + research + context and produces a periodized schedule.
- **`_validate_schedule`** — day-count only. Replace with the §7 content-independent guardrail plane (ACWR band, deload cadence, monotonic intensity, pull:push, contraindications, exercise-ID resolution).
- **`compose_program_aware_plan`'s `rotation_day_override` delegation** — it just remaps to the legacy `exercise_pool` slot-filler. The new engine authors the day directly; this delegation retires (per §8: the `exercise_pool` *selector* retires, the *library* stays).
- **Dead legacy to retire/ignore:** `programs.py` + `training_programs` + `compute_current_phase` (v0, 12 orphan rows, `active_program_id` FK); `team_programs.resolve_team_block` + `team_assigned_blocks` (0 rows) — the only code reading `content.phases`, but dead.

### Conflicts / constraints to respect
1. **Two "programs" tables** — use the new `programs`; do NOT build on `training_programs`. Retiring it requires dropping the `pitcher_training_model.active_program_id` FK first.
2. **`generated_schedule_json` day shape is load-bearing** (`{days:[{day_index, template_key, date, anchor_kind?}]}`) — consumed by runtime/anchoring/UI/counter logic. A richer authored schedule must **extend it additively**; clean-room v1 can define a richer shape freely but keep the projection seam + counters compatible if the flag is ever flipped.
3. **`template_key` ("day_3") → legacy rotation day** is the coupling the new engine deliberately severs (authoring content directly).
4. **Goal taxonomy is duplicated** — `BuilderSlideOver.jsx` chips must match DB `goal_tags`. New goals need both.
5. **`block_library` is shared** with the (dead) team-block path and the (live) candidate matcher (`match_candidates` reads `goal_tags`/`compatible_phases`/`duration_range_weeks`) — repopulating `content`/`tunable`/`research` is safe (empty today); changing the matched columns affects the live funnel.

### Open questions the recon surfaced (resolve before/at green-light)
- **Q-A:** Confirm `PitcherProgram` lives on `programs` (recommended) — supersedes Rev-2's `training_programs`.
- **Q-B:** Reuse `program_aware_plan_gen` + `_select_plan_path` for eventual live integration (recommended), or a parallel flag? (v1 clean-room sidesteps it.)
- **Q-C:** Fate of the 3 coexisting systems — retire `training_programs`/`programs.py` and `team_programs`/`team_assigned_blocks`, or leave dormant?
- **Q-D:** `prohibited_throw_kinds`/prohibited-day conflict logic (a Plan 5–9 intent) was **never shipped** — in scope for the new guardrail plane, or dropped?
- **Q-E:** Is `block_library.content`'s hand-authored `velocity_12wk_v1` 4-phase arc the **seed** for the velocity knowledge pack, or superseded by the golden-xlsx extraction (prereq #1/#2)?
- **Q-F:** Citations panel is dead (`research_doc_ids=[]` everywhere) — confirm the living-knowledge layer populates it.

### Build strategy correction (supersedes Decision #13.13)
Not "separate worktree, clean-room from scratch." Instead: **an isolated branch that replaces the generation core + guardrails + the day-authoring, reuses the funnel/lifecycle/projection/flag/UI, and populates the knowledge layer.** This better serves the original fear (don't fork or re-slop): the slop is one function; the shell around it is sound.
