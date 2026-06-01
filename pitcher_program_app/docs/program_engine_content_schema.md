# Program Engine — Content Schema

> Authoritative reference for the `PitcherProgram` artifact shape.
> Pydantic source: `bot/services/program_engine/schemas.py`.
> Phase 1.1 of the [Program Engine v1 plan](../docs/superpowers/plans/2026-06-01-program-engine-v1.md).

## Design principles

1. **Additive over the migration-020 `programs.generated_schedule_json` shape.** Every day MUST carry `{day_index, template_key, date, anchor_kind?}` so existing readers (`program_runtime`, `program_anchoring`, mini-app `Programs.jsx`, coach `TeamPrograms.jsx`) keep working. New fields are optional.
2. **`extra="forbid"` everywhere.** The LLM is asked to emit JSON that exactly matches this schema; unrecognized keys are a hard parse failure that triggers a re-prompt (Task 3.3).
3. **Freeform where it matters, bounded where it must.** `LiftingExercise.reps` is a string so it can hold ranges + RIR + "each leg" notation directly from the golden xlsx. `intent_pct` is a tight 0–100 int because the ACWR governor reads it.
4. **Exercise IDs are canonical at content-author time.** The author step (Task 3.1) resolves every name through `bot.services.exercise_alias.resolve_alias` BEFORE producing the LiftingExercise, so the schema only stores `ex_NNN`. Guardrail #7 (Task 2.3) re-verifies at validate time.

## Hierarchy

```
PitcherProgram
├── (header) pitcher_id, goal, domain, knowledge_version, engine_version,
│            generated_at, target_date, total_weeks, status
├── phases: [Phase, …]          ─── multi-week chunks with shared intent
│   ├── phase_id, name, week_count, phase_type, intent_summary, intent_kpis
├── days: [Day, …]              ─── the projection target
│   ├── (legacy) day_index, template_key, date, anchor_kind?
│   ├── (engine) phase_name, intent_pct, is_deload, is_rest, day_focus, cues
│   ├── throwing_5tuple: ThrowingFiveTuple?
│   │   ├── distance_ft, throw_count, intensity_pct, drill, note?
│   └── lifting_blocks: [LiftingBlock, …]
│       ├── block_name
│       └── exercises: [LiftingExercise, …]
│           ├── exercise_id (canonical ex_NNN)
│           ├── sets, reps (freeform string), intensity?, rest_s?, superset_group?
├── rationale: Rationale       ─── coach-readable "why"
│   ├── phase_logic, individualization_notes
│   ├── cited_research_doc_ids: [str, …]
│   └── citations: [Citation, …]  (hydrated by research_resolver)
├── progression_state: ProgressionState
│   ├── current_week, current_phase, acwr_rolling, banked_vs_planned, gate_status
└── generation_provenance: dict
    └── {attempts, repair_log, fallback_used, …}  ─── Task 3.3 stamps
```

## ThrowingFiveTuple

Direct lift of the `Ramp up with Bullpen` xlsx schema (recon Front 5):

```
distance_ft   int 0–400    Max distance for the exposure
throw_count   int 0–200    Throws executed
intensity_pct int 0–100    Average intent; Wk1D1 anchor is 50
drill         str          Free-text; throwing-exercise drills resolve via exercise_alias
note?         str          Cueing prose, not parsed
```

The verified daily load anchor lives in `tests/fixtures/golden_acwr_curve.json`:
`(45ft × 40 throws × 50%) → G ≈ 2145` — Phase 2.1's `load_math.daily_throwing_load()` must reproduce this within 5%.

## LiftingBlock + LiftingExercise

Mirrors the `periodized_lifting.xlsx` block structure (Block 1/2/3/4 per day). The superset_group regex (`^[A-Z][0-9]?$`) matches the A1/A2/B1/B2 convention from `The Program.xlsx` Arm Care Heavy tab.

```
LiftingBlock:
  block_name      str  e.g. "Block 1: Posterior Chain"
  exercises       1–8 LiftingExercise

LiftingExercise:
  exercise_id     pattern ex_NNN
  sets            int 1–10
  reps            str   "8" | "8-10" | "3 each leg" | "AMRAP" | "2RIR"
  intensity?      str   "50-75% 1RM" | "2RIR" | "BW"
  rest_s?         int 0–600
  superset_group? "A1" | "B" | "C2" …
  note?           str
```

## Day — the projection unit

```
day_index       int (unique within program)
template_key    str — legacy "day_3" OR engine-native "wk2_d3_velo"
date            ISO YYYY-MM-DD
anchor_kind?    calendar_relative | scheduled_throw_relative | phase_boundary
phase_name?     str
intent_pct?     int 0–100
is_deload       bool
is_rest         bool
throwing_5tuple? ThrowingFiveTuple
lifting_blocks  list[LiftingBlock]   (default [])
day_focus?      str — one-line summary (authoritative at write time, Plan 6 A1.5)
cues            list[str]
```

A rest day looks like:
```json
{
  "day_index": 4,
  "template_key": "wk1_d5_rest",
  "date": "2026-06-06",
  "phase_name": "Base Building",
  "is_rest": true,
  "day_focus": "Full rest — mobility only."
}
```

## Phase

```
phase_id          lower_snake_case, e.g. "base_building"
name              "Base Building"
week_count        int 1–16
phase_type        accumulation | intensification | realization | deload | transition | base
intent_summary    one-paragraph "why"
intent_kpis       e.g. ["max long-toss dist", "weekly G load"]
default_training_intent?  for legacy ProgramDetail.jsx
```

## Citation + Rationale

The Phase 1.2 velocity knowledge pack populates `block_library.velocity_12wk_v1.research_doc_ids` with at least:
- `velocity_progression_model` (new doc, extracted from golden xlsx)
- `driveline_throwing_program` (existing)
- `driveline_lifting_programs` (existing)
- `advanced_workload_performance` (existing — A:C ratio bands)
- `FPM` (existing — gated return-to-throw)
- `ucl_flexor_pronator_protection` (existing)

The author step (Task 3.1) emits `Rationale.cited_research_doc_ids`; `research_resolver` (Task 1.3) hydrates `Rationale.citations` with title + 1-line "why" per citation for the "why this program" panel (Plan 6 B3 State C).

## ProgressionState

`acwr_rolling` and `banked_vs_planned` are populated at check-in time (Phase 2.1's load math). At generation time both are at their defaults; the engine commits a fresh program with `current_week=1`, `gate_status={}`, no ACWR yet.

## Generation provenance

Phase 3.3 stamps this every generation attempt:

```json
{
  "attempts": [
    {"attempt": 1, "status": "rejected", "violations": [...]},
    {"attempt": 2, "status": "valid"}
  ],
  "repair_log": [
    {"violation": "deload_missing_wk4", "applied": "demoted Wk4 to deload"}
  ],
  "fallback_used": false,
  "knowledge_version": "abc12345…"
}
```

## What's NOT in the schema (deliberately)

- **Daily completion tracking** — that lives on `daily_entries`, not on the program artifact.
- **WHOOP biometrics** — readiness inputs feed into `project()` (Phase 4.1), they're never persisted on the program.
- **Coach overrides** — phase overrides remain on `pitcher_training_model.coach_throwing_phase_override` etc. per the existing schema.
- **Modification tags** — `pitcher_training_model.active_modifications` is the source of truth; the engine reads it at generation, doesn't duplicate it.
- **Saved-plans semantics** — those are pitcher-favorited block snapshots (Plan 6 A2); separate from program-as-artifact.
