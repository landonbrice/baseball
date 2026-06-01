# Program Engine v1 — Clean-Room Velocity Demo (landon_brice)

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the shipped Program Builder's generation core in place with **LLM-forward authoring + deterministic guardrails + living knowledge** — and prove it via a clean-room velocity demo on `landon_brice` (lifting + throwing unified, standalone, not yet wired into `plan_generated`). Keep the funnel, lifecycle, projection seam, feature flag, and UI. **The slop is one function (`program_generator._build_schedule_from_scaffold`). The shell around it is sound.**

**Source documents (must read before executing):**
- Spec (Rev 3): `pitcher_program_app/docs/superpowers/specs/2026-05-31-program-engine-design.md` — especially §13 (decision log), §14 (reconciliation with the shipped Program Builder).
- Recon dossier: `pitcher_program_app/docs/superpowers/research/2026-05-31-program-engine-recon.md` — 7 fronts with file:line refs + live Supabase state.
- Handoff note: `pitcher_program_app/docs/superpowers/2026-05-31-program-engine-HANDOFF.md`.

**Architecture:** Six phases, ordered by dependency. Phase 0 (prereqs) and Phase 1 (knowledge pack) must land 100% green before Phase 3 (generation). The clean-room demo (Phase 5) is the v1 done-state — **no `plan_generated` wiring, no `program_aware_plan_gen` flipping**. Live integration is Plan v2 (out of scope here, but every seam in Phase 4 is designed to be wiring-only when it happens).

- **Phase 0** — Prereqs: exercise canonical key / alias map; copy the two Drive-alias xlsx into the repo; lock the golden-curve regression fixture.
- **Phase 1** — Knowledge pack: author velocity content as editable docs/templates (NOT Python); populate `block_library` knowledge columns (`content`, `tunable_parameters_schema`, `modification_rules_json`, `research_doc_ids`); extend `research_resolver` to assemble goal-relevant knowledge for the generation context.
- **Phase 2** — Guardrail plane: §7 content-independent invariants (ACWR band, deload cadence, monotonic intensity, pull:push, FPM cadence, equipment, contraindications, exercise-ID resolution) as pure functions with golden-curve regression tests. Build BEFORE the generator so the generator can call them.
- **Phase 3** — Generation core replacement: swap `_build_schedule_from_scaffold` for an LLM-forward authoring call (`program_engine.author_program`) that takes pitcher context + goal + assembled knowledge and produces the periodized schedule. Wire `_validate_schedule` to the Phase-2 guardrails (validate → repair → reject+re-prompt → deterministic fallback floor).
- **Phase 4** — The drive seam (OPEN #1, designed spike): deepen `program_runtime.get_active_program_day` → `program_aware_planner.compose_program_aware_plan` into a first-class `project(program, date, readiness)` with feedback-into-governor that re-paces remaining weeks. Build the seam + tests; the **policy** stays a spike — multiple candidate strategies evaluated against fixtures, decision recorded but flag-gated off the live path.
- **Phase 5** — Clean-room demo: a CLI/notebook target that runs `landon_brice`'s real context through the engine, renders the program as a viewable+trackable artifact, proves living-knowledge (edit a doc, regenerate, content changes), proves projection (dead-arm input adapts the day while staying oriented), and demonstrates the goal-agnostic engine surface.
- **Phase 6** — Cleanup + tag: docs, runbook, decision log update, tag `program-engine-v1-clean-room`.

**Tech Stack:** Python 3.11 / FastAPI (backend); Supabase Postgres (state); DeepSeek (LLM — reasoning model for generation, latency-tolerant at compile time). Builds on tag `program-builder-v1-complete` + commit `0ab4263`.

**Branch:** `claude/confident-hopper-JolkY` (session-designated; equivalent to `program-engine-design` named in the handoff note).

---

## 2026-06-01 — Locked decisions (recommended §14 answers, confirmed by user green light)

| # | Decision | Source | Why |
|---|---|---|---|
| L1 | **Persist `PitcherProgram` on `programs` table** (NOT `training_programs`) | §14 Q-A | `training_programs` is orphan v0 (~12 dead rows); `programs` is the live wired artifact store from migration `020_programs_core.sql` with the partial-unique-index, counters, hold semantics, and lifecycle. Rev-2's "revive `training_programs`" advice is stale. |
| L2 | **Reuse `program_aware_plan_gen` + `_select_plan_path` seam** for eventual live integration | §14 Q-B | The integration point already exists at `checkin_service.py:182` (`_select_plan_path`) and is flagged ON for `landon_brice` only — our exact v1 target. v1 clean-room **does not flip the flag**; Plan v2 wires it. No parallel flag. |
| L3 | **Leave legacy systems dormant, not retired** | §14 Q-C | `training_programs` / `programs.py` / `team_programs` / `team_assigned_blocks` are orphan but untouched by this plan. Retiring them requires dropping `pitcher_training_model.active_program_id` FK first — out of scope. Plan v2 backlog. |
| L4 | **`prohibited_throw_kinds` / prohibited-day conflict logic deferred** | §14 Q-D | Plan 9 backlog. Pure feature addition vs the engine-core theme of this plan. Players can build whenever (Plan 6 A5's stance preserved). |
| L5 | **Golden-xlsx extraction is source-of-truth for velocity content** | §14 Q-E | The existing `velocity_12wk_v1` 4-phase arc in `block_library.content` is a scaffold — useful but incomplete. The two crown-jewel xlsx (`Ramp up with Bullpen` — 12wk, with the empty `%increase`/`ACWLR` columns that ARE the ACWR mental model; `Return to mound` — 9wk RTT) are the real reference implementations. Phase 1 extracts those into the knowledge pack and enriches `velocity_12wk_v1.content` from them. |
| L6 | **Living-knowledge layer populates `research_doc_ids` (citations)** | §14 Q-F | `block_library.research_doc_ids = []` on every row today (citations panel always empty). Phase 1 populates them per template. The resolver in Phase 1 also returns the citation set the generator emits into `rationale.cited_research_doc_ids`. |
| L7 | **"The drive" (OPEN #1) stays a designed spike** | Handoff note + §5 + §13.10 | Build `project()` as a tested first-class seam with feedback-into-governor; evaluate ≥3 candidate policies (silent absorption / immediate re-pace / banked-deviation-with-deload-acceleration) against fixtures; **decision deferred to v2 live integration**. The seam ships; the policy ships flag-gated off the live path. |
| L8 | **v1 is standalone clean-room — NO `plan_generated` wiring** | Spec §1, §9 | The demo renders the artifact directly. No `triage` / `exercise_pool` / `plan_generated` writes. `program_aware_plan_gen` flag is NOT changed. The check-in pipeline behavior is unchanged for every pitcher including `landon_brice`. Live integration = Plan v2. |
| L9 | **Replace in place, do NOT greenfield** | §14 build strategy correction | The slop is one function. Building a new `program_engine/` module greenfield would fork a shipped feature. Replace `program_generator._build_schedule_from_scaffold` + `_validate_schedule` in place, behind a new internal flag so the existing rotation-repeat path stays available as the deterministic fallback floor. |
| L10 | **Goal-agnostic engine, velocity is the first authored knowledge pack** | Spec §1 | The engine surface (`author_program(pitcher_context, goal_spec, knowledge_pack) → PitcherProgram`) takes goal as data, not code. Velocity ships first because the golden xlsx and `velocity_12wk_v1` exist. Future goals (longtoss, hypertrophy, RTT) are knowledge packs, not engine changes. |
| L11 | **Reasoning model for generation, latency-tolerant** | Spec §3b | Generation is a one-time op per program. Use `call_llm_reasoning()` (DeepSeek deepseek-reasoner, 120s timeout) — NOT the 45s chat path. Day rendering is cheap because the program is persisted. |
| L12 | **Coach-mediated, player-confirmed knowledge propagation** | Spec §6 | When research/templates change, FUTURE generations reflect it automatically. ACTIVE programs are NOT silently rewritten — the in-app coach proposes a modification the player verifies. Phase 4 lays the seam; the proposal flow itself is Plan v2 backlog. |

## Carryovers from prior plans (addressed here)

- Populate `block_library.content` / `tunable_parameters_schema` / `modification_rules_json` / `research_doc_ids` (currently empty on all 6 rows) → Phase 1.
- The 4 incompatible "block of exercises" schemas + free-text prescriptions + orphan exercise IDs (Front 2) → Phase 0 alias map + Phase 1 canonical content shape.
- "Backwards routing" of research docs (richest generative docs tagged `coach_chat`, never reach plan_gen) → Phase 1 resolver extension.
- The empty `%increase`/`ACWLR` columns in the golden xlsx (Front 5 — the single most important "gold" signal) → Phase 2 guardrails (the ACWR governor) + Phase 1 fixture extraction.

## Plan v2 backlog (defer)

- **Live integration of the new engine into the daily pipeline** — flip `program_aware_plan_gen` for `landon_brice`, route through `_select_plan_path` to the new `compose_program_aware_plan_v2` that calls `project()` instead of `rotation_day_override`. Single-pitcher canary, then roster rollout following the Plan 8 D1/D2 pattern.
- **"The drive" policy decision** — pick one of the Phase-4 candidate strategies based on landon_brice clean-room evidence.
- **Coach-mediated knowledge-propagation proposal flow** — UI + endpoint for the coach insight type `program_knowledge_changed` (drift insight cousin); player confirm/reject.
- **Goal pack #2 onward** — longtoss, hypertrophy, return-to-throwing as knowledge packs (no engine changes).
- **Retire legacy** — drop `training_programs` (after dropping the `pitcher_training_model.active_program_id` FK), `team_assigned_blocks` (0 rows, dead), `programs.py` / `compute_current_phase`.
- **`prohibited_throw_kinds`** — declarative template field + 409 + `?confirm=true` retry (Plan 5/6/8 carryover).
- **Coach-authored research docs** — Plan 8 C3 shipped attach-existing; v2 adds authoring + frontmatter validation + git/Supabase choice.

---

# Phase 0 — Prereqs

Phase 0 unblocks Phase 1. Three small, independent tasks. **Must land before any LLM generation work.**

### Task 0.1: Exercise canonical key / alias map

**Files:**
- Create: `pitcher_program_app/data/knowledge/exercise_alias_map.json`
- Create: `pitcher_program_app/bot/services/exercise_alias.py`
- Create: `pitcher_program_app/tests/test_exercise_alias.py`

**Approach:** A JSON map keyed by canonical exercise_id (from the 159-row `exercises` table) → list of aliases as they appear in golden xlsx / PDF / research docs. Examples from recon Front 3: `ex_???` ↔ "Seal Row" / "Chest-Supported Row"; `ex_???` ↔ "RFE Split Squat" / "Bulgarian". A pure-Python resolver `resolve_alias(name: str) → exercise_id | None` does case-folded + punctuation-stripped lookup; unresolved names raise `UnknownExerciseAlias(name)` (NOT `None`-return) so guardrail #7 has a hard fail. **Build by hand-walking the golden xlsx + research docs once**; the map is content, not code, so future additions are JSON edits.

**Key signature:**

```python
# bot/services/exercise_alias.py
class UnknownExerciseAlias(Exception):
    """Raised when an exercise name in knowledge content does not resolve to a live exercises table row."""
    def __init__(self, name: str):
        super().__init__(f"unresolved exercise alias: {name!r}")
        self.name = name

def resolve_alias(name: str) -> str:
    """Return canonical exercise_id for a name as it appears in golden content.

    Lookup is case-folded + whitespace-collapsed + punctuation-stripped against
    the alias map loaded from data/knowledge/exercise_alias_map.json.

    Raises UnknownExerciseAlias if no match. Callers (guardrail #7) treat that
    as a hard fail in the validate→repair→reject loop.
    """
    ...
```

**Steps:**
- [ ] Create `data/knowledge/exercise_alias_map.json` with at minimum every exercise referenced in `velocity_12wk_v1.content`, `data/knowledge/research/driveline_lifting_programs.md`, and the two crown-jewel xlsx (once copied in 0.2). Format: `{"<exercise_id>": ["alias 1", "alias 2", ...]}`.
- [ ] Implement `exercise_alias.py` per the signature above. Cache the map at module load (no DB read at runtime).
- [ ] Create `tests/test_exercise_alias.py` covering: canonical lookup, alias lookup, case/whitespace/punctuation normalization, unknown-alias raises `UnknownExerciseAlias`.
- [ ] Run `pytest pitcher_program_app/tests/test_exercise_alias.py -v` — green.

### Task 0.2: Copy crown-jewel xlsx into the repo

**Files:**
- Create: `pitcher_program_app/data/knowledge/golden/ramp_up_with_bullpen_12wk.xlsx`
- Create: `pitcher_program_app/data/knowledge/golden/return_to_mound_9wk.xlsx`
- Create: `pitcher_program_app/data/knowledge/golden/README.md`
- Update: `.gitignore` if/as needed to NOT ignore these.

**Approach:** Per the handoff note, the two crown-jewel xlsx exist on the OLD machine ONLY as macOS aliases into Google Drive (`~/Library/CloudStorage/GoogleDrive-landonbrice2005@gmail.com/My Drive/`). openpyxl cannot read those aliases — "not a zip file". The user must resolve the alias (Finder → "Get original" or `osascript` to follow it) and copy the real xlsx into the repo on a machine that has them. **This is a human-in-the-loop task — the executing agent flags this if files are missing and stops Phase 0.**

**Acceptance:** `openpyxl.load_workbook(path)` succeeds on both files; first cell of each is the expected header from Front 5 (`Ramp up`: header row `B=Distance, C=Throws, D=Intent, E=Drill, F=daily total throws, G=Volume (load units), H=%increase, I=ACWLR`; `Return to mound`: 5-col grid `(day, distance_ft, throw_count, intensity_decimal, drill/instruction)`).

**Steps:**
- [ ] Check `data/knowledge/golden/ramp_up_with_bullpen_12wk.xlsx` exists and openpyxl-loads. If missing, STOP and surface the gap to the user with the exact paths from the handoff note.
- [ ] Same for `return_to_mound_9wk.xlsx`.
- [ ] Write `README.md` documenting provenance (Drive alias paths) + schema (the header rows from Front 5).

### Task 0.3: Lock the golden-curve regression fixture

**Files:**
- Create: `pitcher_program_app/scripts/extract_golden_acwr_curve.py`
- Create: `pitcher_program_app/tests/fixtures/golden_acwr_curve.json`
- Create: `pitcher_program_app/tests/test_golden_acwr_curve.py`

**Approach:** Front 5 verified the load math: `G ≈ intensity-weighted volume` (Wk1D1: 40 throws, dist×throws=2400, `G=2145 ≈ ×0.89`). Weekly G ramps `6960 → 9194 → 10935 → 10375 → 12049 → 13516 → 12090 → 12960 → 13620 → … → 14616` — a 3-up-1-down deload undulation. **The script reads `ramp_up_with_bullpen_12wk.xlsx` and extracts the daily 5-tuple + weekly G curve into a static JSON fixture**, which Phase 2's ACWR guardrail validates against (regression test: our recomputed load function on the same daily 5-tuples must produce the same weekly G within 5% tolerance). The script runs ONCE; the JSON is checked in.

**Key signature:**

```python
# scripts/extract_golden_acwr_curve.py
"""Phase 0 / Task 0.3 — extract golden ACWR curve regression fixture.

Reads data/knowledge/golden/ramp_up_with_bullpen_12wk.xlsx and writes
tests/fixtures/golden_acwr_curve.json containing:
- daily_5tuples: [{week, day, distance_ft, throw_count, intent_pct, drill}, ...]
- weekly_G: [<float>, ...] (12 entries — the empirical reference curve)

Run once after Task 0.2. Output is checked in; not re-run on CI.
"""
```

**Steps:**
- [ ] Implement the extraction script. Use `openpyxl` (already in `requirements.txt`).
- [ ] Run `python -m scripts.extract_golden_acwr_curve` and check in the resulting JSON.
- [ ] Write `tests/test_golden_acwr_curve.py` that loads the JSON and asserts: 12 weekly_G entries; monotonic-with-deload shape (Wk4 < Wk3, Wk7 < Wk6); ACWR computed from daily values stays in [0.8, 1.5] band at every point.
- [ ] Run `pytest pitcher_program_app/tests/test_golden_acwr_curve.py -v` — green.

---

# Phase 1 — Living knowledge pack

Phase 1 turns the velocity arc into editable, retrievable content the LLM can read at generation time. **No Python encodes velocity logic.** The `block_library.content` schema gets enriched; `research_resolver` learns to assemble goal-relevant docs/templates for generation context.

### Task 1.1: Canonical `PitcherProgram` content shape

**Files:**
- Create: `pitcher_program_app/docs/program_engine_content_schema.md`
- Update: `pitcher_program_app/bot/services/program_engine/__init__.py` (new module — see Task 3.1)
- Update: `pitcher_program_app/bot/services/program_engine/schemas.py` (new — Pydantic models)

**Approach:** Write the schema spec ONCE, then everything (LLM prompt, generation output, persistence, projection, UI) reads it. The shape **extends** `programs.generated_schedule_json`'s existing day shape `{day_index, template_key, date, anchor_kind?}` ADDITIVELY (L1 / §14 conflict #2). New fields per day: `intent_pct` (0–100), `throwing_5tuple {distance_ft, throw_count, intensity_pct, drill, note}` (optional — null on no-throw days), `lifting_blocks` (list of `{block_name, exercises: [{exercise_id, sets, reps, intensity, rest_s, superset_group?}]}`), `phase_name`, `is_deload`. Program-level additions: `phases: [{phase_id, name, week_count, intent_kpis}]`, `rationale {phase_logic, individualization_notes, cited_research_doc_ids}`, `progression_state {current_week, current_phase, acwr_rolling, banked_vs_planned, gate_status}`, `knowledge_version` (hash of the resolver-assembled knowledge pack at generation time — for the "edit doc → regenerate" proof).

**Steps:**
- [ ] Draft `docs/program_engine_content_schema.md` describing every field, units, optionality, and example.
- [ ] Implement Pydantic models in `program_engine/schemas.py`: `Day`, `Phase`, `Throwing5Tuple`, `LiftingBlock`, `LiftingExercise`, `Rationale`, `ProgressionState`, `PitcherProgram`.
- [ ] Tests in `tests/test_program_engine_schemas.py`: serialization round-trip, schema rejection on missing required fields, schema acceptance on legacy `generated_schedule_json` shape (additive extension).

### Task 1.2: Velocity knowledge pack — extract + populate `block_library`

**Files:**
- Create: `pitcher_program_app/scripts/seed_velocity_knowledge_pack.py`
- Update: `pitcher_program_app/data/knowledge/research/velocity_progression_model.md` (NEW — extracted from golden xlsx + Front 3 research base)
- Update: existing `data/knowledge/research/*.md` frontmatter (see Task 1.4)
- Migration: `pitcher_program_app/scripts/migrations/033_seed_velocity_knowledge_pack.sql` (idempotent UPSERT into `block_library`)

**Approach:** Author the velocity knowledge as content. New research doc `velocity_progression_model.md` extracted from `ramp_up_with_bullpen_12wk.xlsx` (the 12-week phase arc with the empty %increase/ACWLR columns interpreted as the ACWR governor) + `return_to_mound_9wk.xlsx` (the gated phase model: pulldowns appear Wk3, bullpens ramp 15→20→25→30→40→45→50 Wks 5–9, "Probable live ABs" Wk7, "Probable clearance" Wk8) + `PITCHING-PROGRAM-FINAL.pdf` named phase macrocycles (Velocity Phase → Pitch Design → In-season). Frontmatter MUST include `contexts: [plan_gen, coach_chat, daily_plan_why]` (per recon Front 3, the richest generative docs are wrongly tagged `coach_chat`-only — Phase 1 fixes that). Idempotent migration UPSERTs `velocity_12wk_v1.content` (enriched), `tunable_parameters_schema` (the §13 tunables: target velocity gain, deload cadence preference, mound reintroduction week), `modification_rules_json` (the §13 mod rules: GREEN/YELLOW/RED deltas from `FINAL_research_base.md`), `research_doc_ids` (`["velocity_progression_model", "driveline_throwing_program", "advanced_workload_performance", "FPM", "ucl_flexor_pronator_protection"]`).

**Steps:**
- [ ] Draft `velocity_progression_model.md` with YAML frontmatter (`id`, `applies_to`, `triggers: [velocity_goal]`, `priority: critical`, `contexts: [plan_gen, coach_chat, daily_plan_why]`). Body = the phase arc + ACWR governance + gate criteria + RIR-based lifting tables (extracted from PDF p. ?).
- [ ] Implement `scripts/seed_velocity_knowledge_pack.py` that reads the golden xlsx + research docs and emits the SQL migration payload. **No live Supabase writes from the script** — it generates the migration SQL.
- [ ] Author `033_seed_velocity_knowledge_pack.sql` as `UPDATE block_library SET ... WHERE block_template_id = 'velocity_12wk_v1'` (idempotent — `WHERE` clause is the idempotency key).
- [ ] Apply migration via Supabase MCP `apply_migration` (NOT `execute_sql` — `apply_migration` registers history).
- [ ] Verify: `SELECT content->'phases', tunable_parameters_schema, modification_rules_json, research_doc_ids FROM block_library WHERE block_template_id = 'velocity_12wk_v1'` returns populated values.

### Task 1.3: Extend `research_resolver` for generation context

**Files:**
- Update: `pitcher_program_app/bot/services/research_resolver.py`
- Create: `pitcher_program_app/tests/test_research_resolver_program_gen_context.py`

**Approach:** Add a new `context` value `"program_gen"` (alongside existing `plan_gen` / `coach_chat` / `morning` / `daily_plan_why`). The resolver call for program generation takes `(pitcher_profile, pitcher_context, goal_spec, max_chars)` — NO `triage` parameter (the program is authored once, not per-day). The resolver returns `{docs: [(doc_id, text)], templates: [...], exemplars: [...], knowledge_version: <sha1 of concatenated content>}`. `knowledge_version` is what `PitcherProgram.knowledge_version` persists — the "edit doc → next generation differs" proof falls out of this hash changing. **Selection rule for `program_gen` context:** every doc whose frontmatter `triggers` intersects `goal_spec.tags` + every doc with `priority: critical` + (budget permitting) every doc whose `applies_to` matches the pitcher's injury history. Templates: every `block_library` row whose `goal_tags` intersects `goal_spec.tags`. Exemplars: the golden xlsx as raw structured data (the daily 5-tuples for `Ramp up`, the day-grid for `Return to mound`) loaded from `data/knowledge/golden/` via a thin loader (`openpyxl` → list of dicts).

**Key signature:**

```python
# bot/services/research_resolver.py (additions)
def resolve_for_program_gen(
    pitcher_profile: dict,
    pitcher_context: str,
    goal_spec: dict,
    max_chars: int = 16000,
) -> dict:
    """Assemble goal-relevant knowledge for program generation.

    Returns:
        {
            "docs":       [(doc_id: str, text: str), ...],
            "templates":  [{block_template_id, content, tunable_parameters_schema, modification_rules_json}, ...],
            "exemplars":  [{name, daily_rows: [...]}, ...],
            "knowledge_version": "<sha1 hex>",
        }

    knowledge_version is the SHA-1 of the concatenated normalized content;
    PitcherProgram persists it so "edit doc → next generation differs" is
    verifiable end-to-end.
    """
    ...
```

**Steps:**
- [ ] Implement `resolve_for_program_gen()` + `_load_golden_exemplars()` helper.
- [ ] Compute `knowledge_version` deterministically (sort doc_ids, hash concatenated content).
- [ ] Tests: docs filtered by `triggers` intersection; templates filtered by `goal_tags`; exemplars loaded from disk; `knowledge_version` changes when ANY included doc text changes; `knowledge_version` stable across calls when nothing changes.
- [ ] Log every call to `research_load_log` with `context='program_gen'` (existing observability).

### Task 1.4: Fix frontmatter on the "backwards" docs

**Files:** `pitcher_program_app/data/knowledge/research/*.md`

**Approach:** Recon Front 3 flagged: "13/14 docs have resolver frontmatter, BUT the richest generative docs are tagged `contexts: [coach_chat]` / `priority: reference` — NOT routed into plan_gen. The system injects the 'why' into plan-gen and reserves the 'how' for chat. Backwards." Fix it: add `program_gen` to the contexts list of every research doc that contains generative content (templates, sets/reps, progression rules, gate criteria). Specifically: `driveline_lifting_programs.md`, `driveline_throwing_program.md`, `FPM.md`, `advanced_workload_performance.md`, `FINAL_research_base.md`, `velocity_progression_model.md` (created in 1.2). Leave docs that are pure physiology (e.g. `recovery_physiology.md`) as `coach_chat` only — those belong in the daily-plan-why path, not in generation.

**Steps:**
- [ ] Audit every `data/knowledge/research/*.md` — identify the generative subset.
- [ ] Update frontmatter `contexts` to include `program_gen` where appropriate. Bump `priority` from `reference` → `critical` for the gated state machines (`FPM.md`).
- [ ] Verify via `test_research_resolver_program_gen_context.py` that resolution returns the expected doc set for `goal_spec={tags: ["velocity"]}`.

---

# Phase 2 — Guardrail plane

Phase 2 is the §7 content-independent invariants as pure functions, validated against the Phase-0 golden fixture. **Built BEFORE the generator so the generator can call them.** Phase 3's validate-repair-reject loop is this module's main client.

### Task 2.1: Load math + ACWR governor

**Files:**
- Create: `pitcher_program_app/bot/services/program_engine/load_math.py`
- Create: `pitcher_program_app/tests/test_load_math.py`

**Approach:** Per §7 and Front 5: throwing load ≈ `Σ(throws × intensity_factor)` with distance weighting; lifting load ≈ `Σ(sets × reps × intensity_factor)`. Acute = trailing 7d sum; chronic = trailing 28d avg. ACWR = acute / chronic. Default band [0.8, 1.3], hard cap 1.5. The fixture from Task 0.3 is the regression test: our `weekly_load_throwing(daily_5tuples)` must produce the golden weekly G curve within 5%. **Tunable defaults live in a module-level constants dict; no magic numbers in function bodies.**

**Key signatures:**

```python
# bot/services/program_engine/load_math.py
def daily_throwing_load(t: Throwing5Tuple) -> float:
    """G ≈ throws × intensity_factor × distance_factor.

    Calibrated against the Ramp-up golden curve: Wk1D1 (40 throws @0.50, 45ft)
    → G≈2145, our formula must match within 5%.
    """

def daily_lifting_load(blocks: list[LiftingBlock]) -> float:
    """Σ(sets × reps × intensity_factor) across all exercises."""

def weekly_acwr(daily_loads: list[float], at_day_index: int, band: tuple[float, float] = (0.8, 1.3)) -> tuple[float, bool]:
    """Returns (acwr_value, in_band)."""

def check_acwr_invariant(program: PitcherProgram) -> list[GuardrailViolation]:
    """Walks the program day-by-day; returns violations where ACWR exits band or exceeds 1.5 hard cap."""
```

**Steps:**
- [ ] Implement load math; calibrate constants against the golden fixture (regression test = the fixture round-trips within 5%).
- [ ] Implement `weekly_acwr` + `check_acwr_invariant`.
- [ ] Tests: fixture round-trip; ACWR computed at day=0 returns null (no chronic); ACWR walks correctly across phase boundaries; hard cap 1.5 violation example.

### Task 2.2: Structural invariants (deload, monotonic, pull:push, FPM)

**Files:**
- Create: `pitcher_program_app/bot/services/program_engine/structural_invariants.py`
- Create: `pitcher_program_app/tests/test_structural_invariants.py`

**Approach:** Implement §7 invariants 2–5 as pure functions taking `PitcherProgram` → `list[GuardrailViolation]`. (2) Deload cadence: ≥1 deload week per ~3–4 accumulation weeks (the golden 3-up-1-down). (3) Phase gates: high-intensity / mound / pulldown phases appear AFTER a base phase of sufficient duration (encoded as a rule, not hardcoded weeks). (4) Throwing intensity monotonicity: max(intent_pct[w]) - max(intent_pct[w-1]) ≤ +20pp; no 50→100 jumps. (5) Lifting invariants: weekly pull-volume / push-volume ≥ 2.0; FPM exercise present ≥4/7 days. **Each violation is a structured dataclass with `kind`, `where (week/day)`, `actual`, `expected`, `severity (error/warning)`, `repair_hint`** — Phase 3's repair loop reads `repair_hint`.

**Steps:**
- [ ] Implement `GuardrailViolation` dataclass + the 4 invariant checkers.
- [ ] Tests against synthetic minimal programs: each violation kind has a positive + negative fixture.

### Task 2.3: Content invariants (equipment, contraindications, exercise IDs)

**Files:**
- Create: `pitcher_program_app/bot/services/program_engine/content_invariants.py`
- Create: `pitcher_program_app/tests/test_content_invariants.py`

**Approach:** §7 invariants 6–7. (6) Equipment hard-filter: every exercise's required equipment is in `pitcher_training_model.equipment_constraints` (existing column). Injury contraindications: read `pitcher_training_model.active_modifications` + `injury_history` and reject exercises whose `contraindications` tag matches. The flexor/pronator → no fixed-scap pressing / vertical pulling rule from `FPM.md` is encoded as a single contraindication mapping (`modification_tag → set[exercise_id]`) loaded from `vocabulary.py` extensions (NOT hardcoded). (7) Exercise IDs: every `exercise_id` in the program resolves against the live `exercises` table via `exercise_alias.resolve_alias` (Task 0.1) OR is already canonical. Unknown IDs raise `UnknownExerciseAlias` → fatal violation (no repair, only reject+reprompt).

**Steps:**
- [ ] Implement `check_equipment` + `check_contraindications` + `check_exercise_ids`.
- [ ] Tests: positive + negative fixtures per invariant; flexor/pronator test uses real `FPM.md` modifications.

### Task 2.4: Validate → repair → reject orchestrator

**Files:**
- Create: `pitcher_program_app/bot/services/program_engine/guardrails.py`
- Create: `pitcher_program_app/tests/test_guardrails_orchestrator.py`

**Approach:** Single entry point `validate_program(program, pitcher_context) → ValidationResult` that runs all checks, classifies violations as repairable / fatal, attempts cheap deterministic repairs (e.g. swap a contraindicated exercise for an alternative via existing `exercise_alternatives.py`; insert a missing deload week by demoting an accumulation week), and returns `{status: 'valid' | 'repaired' | 'reject', program: repaired_program, violations: [...], repair_log: [...]}`. **Repair is best-effort + bounded** — 3 repair passes, then if still invalid → status=`reject` with the violation list for Phase 3's re-prompt.

**Key signature:**

```python
# bot/services/program_engine/guardrails.py
@dataclass
class ValidationResult:
    status: Literal["valid", "repaired", "reject"]
    program: PitcherProgram
    violations: list[GuardrailViolation]
    repair_log: list[dict]

def validate_program(program: PitcherProgram, pitcher_context: dict, max_repair_passes: int = 3) -> ValidationResult:
    """Runs all §7 invariants, attempts deterministic repairs, returns the result.

    Repair strategies are bounded and conservative: swap to nearest-alternative
    exercise for contraindications, demote an accumulation week to deload for
    missing deload cadence, clamp intensity jumps to the +20pp ceiling for
    monotonicity violations. Fatal violations (unknown exercise ID, ACWR hard
    cap breach) skip repair and go straight to reject.
    """
```

**Steps:**
- [ ] Implement orchestrator with the 3-pass repair loop.
- [ ] Tests: synthetic program with 1 repairable violation → status=`repaired`; with 1 fatal → status=`reject`; with 0 → status=`valid`.

### Task 2.5: Deterministic safe fallback floor

**Files:**
- Create: `pitcher_program_app/bot/services/program_engine/fallback.py`
- Create: `pitcher_program_app/tests/test_fallback.py`

**Approach:** If LLM generation can't produce a guardrail-valid program even after re-prompt (Phase 3), or if the LLM times out, return a deterministic safe program. **Per §3c the fallback floor is still a real periodized program, not slop.** Build it by parameterizing the velocity arc from `velocity_12wk_v1.content.phases` (now populated in Task 1.2) + a default RIR-based lifting table (from `PITCHING-PROGRAM-FINAL.pdf` extraction in Task 1.2). The fallback is goal-agnostic: it takes a `goal_spec` and a `block_library` row and instantiates the phases at the pitcher's start date. It validates as `valid` against Phase 2.4 by construction.

**Steps:**
- [ ] Implement `build_fallback_program(pitcher_id, goal_spec, block_library_row) → PitcherProgram`.
- [ ] Tests: returns a program that passes `validate_program` for velocity goal; instantiation against multiple start dates.

---

# Phase 3 — Generation core replacement

Phase 3 swaps the slop. The slop is **exactly two functions** in `program_generator.py`: `_build_schedule_from_scaffold` (the 7-day rotation repeat) and `_validate_schedule` (day-count only). Phase 3 replaces them with LLM-forward authoring + the Phase-2 guardrail loop. **Behind an internal flag (`PROGRAM_ENGINE_V1`) so the rotation-repeat path stays available as the deterministic fallback floor** (L9) and existing tests stay green.

### Task 3.1: `program_engine` module skeleton + author signature

**Files:**
- Create: `pitcher_program_app/bot/services/program_engine/__init__.py`
- Create: `pitcher_program_app/bot/services/program_engine/author.py`
- Update: `pitcher_program_app/bot/services/program_engine/schemas.py` (from Task 1.1)
- Create: `pitcher_program_app/tests/test_program_engine_author_smoke.py`

**Approach:** The single public engine surface:

```python
async def author_program(
    pitcher_profile: dict,
    pitcher_context: str,
    goal_spec: dict,            # {tags: ["velocity"], target_weeks: 12, target_date: "...", tunables: {...}}
    knowledge_pack: dict,       # output of research_resolver.resolve_for_program_gen
    *,
    seed: int | None = None,    # for determinism in tests
) -> PitcherProgram:
    """LLM-forward program authoring.

    Calls call_llm_reasoning() with the assembled context, parses the response
    into a PitcherProgram via the Pydantic schema, attaches knowledge_version,
    and returns. Does NOT validate (that's the orchestrator's job in Task 3.3).

    On LLM timeout or parse failure raises GenerationFailure; the orchestrator
    catches that and falls back to the deterministic floor.
    """
```

**Prompt design lives in `pitcher_program_app/bot/prompts/program_engine_author.md`** (NEW). The prompt instructs the LLM: "you are a brilliant coach; here is the pitcher's context, the goal, the knowledge pack; author a multi-week program following the response schema; cite research docs by ID; novel structures are encouraged within the invariants stated in the knowledge pack." **No constraint encoding in the prompt** — the LLM is told what the goal is, given the knowledge, and asked to author. The guardrails catch invariant violations downstream; the LLM is not asked to self-check them (Front 1 lesson: LLM-as-checker is a non-brain).

**Steps:**
- [ ] Implement `author.py` per the signature.
- [ ] Write `prompts/program_engine_author.md` — the brilliant-coach prompt + the response schema (JSON shape mirroring `PitcherProgram`).
- [ ] Smoke test against a recorded LLM response fixture (no real LLM call in CI).

### Task 3.2: Replace `_build_schedule_from_scaffold` (internal flag)

**Files:**
- Update: `pitcher_program_app/bot/services/program_generator.py`
- Create: `pitcher_program_app/bot/services/program_engine/feature_flag.py`
- Update: `pitcher_program_app/tests/test_program_generator.py` (existing — verify rotation path still works under flag-off)

**Approach:** Add `PROGRAM_ENGINE_V1` module-level constant (default `False`). When `True`, `generate_program(...)` routes to `program_engine.author_program(...)` + `program_engine.guardrails.validate_program(...)` + (on reject) fallback to `program_engine.fallback.build_fallback_program(...)`. When `False`, the existing rotation-repeat path stays unchanged. **The legacy path is the safety net** — existing tests / live `landon_brice` builder traffic / coach-app candidates continue to work flag-off. Flag-on is exercised only by the clean-room demo entry point (Phase 5) and the new test suites.

**Steps:**
- [ ] Implement the routing fork inside `generate_program(...)`.
- [ ] Verify existing `test_program_generator.py` (the legacy goldens) still green with flag-off.
- [ ] Add `test_program_generator_engine_v1.py` with flag-on smoke test that runs `author → validate → persist` end-to-end against a small fixture.

### Task 3.3: Generation orchestrator (reprompt + fallback)

**Files:**
- Create: `pitcher_program_app/bot/services/program_engine/orchestrator.py`
- Create: `pitcher_program_app/tests/test_program_engine_orchestrator.py`

**Approach:** The validate→repair→reject loop with a re-prompt budget. Up to 2 re-prompts (passing the violation list back to the LLM as `Your previous output had these issues; fix them.`) before falling back to deterministic. **Persist every attempt as a `program_generation_failures` row** (existing table from migration 020 — reuse) so we have observability on LLM behavior vs guardrails. Final return is always a guardrail-valid `PitcherProgram` (the floor is always valid by construction). The orchestrator returns the program + a `generation_provenance: {attempts, repair_log, fallback_used, knowledge_version}` block that gets persisted on `programs.metadata` JSONB column (additive).

**Steps:**
- [ ] Implement orchestrator.
- [ ] Tests covering: first attempt valid; first attempt repaired; first attempt rejected → re-prompt → valid; all re-prompts rejected → fallback used.

### Task 3.4: Persist into `programs` table (additive schema)

**Files:**
- Migration: `pitcher_program_app/scripts/migrations/034_programs_engine_v1_fields.sql`
- Update: `pitcher_program_app/bot/services/db.py` (additions to `programs` CRUD helpers)
- Create: `pitcher_program_app/tests/test_db_programs_engine_v1.py`

**Approach:** Additive only — the existing `generated_schedule_json` day shape must keep working (§14 conflict #2, L1). Migration adds: `programs.knowledge_version text NULL`, `programs.generation_provenance jsonb NULL DEFAULT '{}'::jsonb`, `programs.engine_version text NULL DEFAULT 'v1'`. **No existing columns altered.** Existing reads (runtime, anchoring, UI, counter logic) unaffected. RLS / grants follow the 010/012/017 idiom — `service_role` only, no anon/authenticated.

**Steps:**
- [ ] Author migration 034. Idempotent (`ADD COLUMN IF NOT EXISTS`).
- [ ] Apply via Supabase MCP `apply_migration`.
- [ ] Extend `db.insert_program(...)` / `db.update_program(...)` to write the new fields.
- [ ] Tests: round-trip a `PitcherProgram` through Supabase; verify `knowledge_version` + `generation_provenance` persist and read back identical.

---

# Phase 4 — The drive seam (designed spike)

Phase 4 deepens the projection seam — **but the policy stays a spike**, per L7. Build the seam + tested infrastructure for ≥3 candidate policies; **record the decision but ship flag-gated off the live path**. The live `program_aware_planner.compose_program_aware_plan` is untouched (L8 — no `plan_generated` wiring in v1).

### Task 4.1: First-class `project()` function

**Files:**
- Create: `pitcher_program_app/bot/services/program_engine/projection.py`
- Create: `pitcher_program_app/tests/test_program_engine_projection.py`

**Approach:** A pure function `project(program, date, readiness) → ProjectedDay` returning what the pitcher sees today, given the program + the date + a readiness signal (Phase 1 trajectory triage output: `{flag_level, category_scores: {tissue, load, recovery}, modifications, ...}`). **No DB writes — pure projection.** This is the seam OPEN-#1 names. The function takes a `policy: Literal["silent_absorb", "immediate_repace", "banked_deviation"]` parameter so candidate policies are testable side-by-side.

**Key signature:**

```python
# bot/services/program_engine/projection.py
@dataclass
class ProjectedDay:
    day_index: int
    intended: Day                  # what the program prescribes
    delivered: Day                 # what the projection emits after readiness modulation
    modulation: dict               # {applied_factor, reason, severity}
    governor_signal: dict | None   # if non-None, feedback for the re-pacer

def project(program: PitcherProgram, date: _date, readiness: dict, *, policy: str = "silent_absorb") -> ProjectedDay:
    """Project the program's day-N onto today's reality.

    Pure function. Readiness modulates intensity/volume within bounds defined
    by the program's phase. governor_signal is non-None when the deviation
    crosses the policy's threshold for re-pacing.
    """
```

**Steps:**
- [ ] Implement `project()` with the 3 candidate policies as named strategies.
- [ ] Tests per policy: GREEN readiness → delivered == intended; YELLOW with low tissue → intensity dialed within bounds; RED → no-throw downgrade; governor_signal fires appropriately per policy.

### Task 4.2: Governor (re-pacing the remaining weeks)

**Files:**
- Create: `pitcher_program_app/bot/services/program_engine/governor.py`
- Create: `pitcher_program_app/tests/test_program_engine_governor.py`

**Approach:** When `project()` returns a governor_signal, `regovern(program, signal, policy) → PitcherProgram'` produces a re-paced program with the remaining weeks adjusted to defend the goal. **Re-pacing is bounded** — can shift up to 2 weeks of accumulation, can insert/remove ONE deload, can soften ONE phase gate — beyond which the governor surfaces a `goal_at_risk` flag instead of further re-pacing. The output program re-validates through Phase 2.4; if it fails, the previous program is kept and a `regovern_failed` event is logged.

**Steps:**
- [ ] Implement `regovern()` with bounded adjustments per policy.
- [ ] Tests: small deviation → small re-pacing; large deviation → goal_at_risk; output always passes validation OR keeps prior program.

### Task 4.3: Policy comparison harness

**Files:**
- Create: `pitcher_program_app/scripts/compare_drive_policies.py`
- Create: `pitcher_program_app/tests/fixtures/drive_policy_fixtures.json`

**Approach:** A harness that runs each of the 3 candidate policies through a fixed set of readiness scenarios (10-day sequences: all-green, mid-cycle yellow, late-phase red, repeated low-tissue) and produces a comparison report: per-policy per-scenario `(final_goal_progress, total_load_delivered, weeks_disturbed, gate_outcomes)`. This is the artifact that informs the v2 policy decision. **No decision made in this plan** — just the harness, the fixtures, and a report. Decision goes in Plan v2's `What's Next` after landon_brice clean-room evidence.

**Steps:**
- [ ] Implement harness + fixture set.
- [ ] Generate the comparison report (Markdown table) into `docs/superpowers/research/2026-06-XX-drive-policy-comparison.md`.
- [ ] Surface the comparison report to the user as a side artifact; do NOT lock the policy in this plan.

---

# Phase 5 — Clean-room velocity demo (landon_brice)

Phase 5 is the v1 done-state. A standalone target that runs the engine end-to-end on `landon_brice`'s real context, renders the program, and proves the §1 demo criteria. **NO `plan_generated` writes. NO flag flip.**

### Task 5.1: Clean-room runner

**Files:**
- Create: `pitcher_program_app/scripts/run_clean_room_velocity_demo.py`
- Create: `pitcher_program_app/tests/test_clean_room_velocity_demo.py`

**Approach:** CLI script that takes `--pitcher landon_brice --goal velocity` (defaults), reads the pitcher's profile + injury_history + baseline_snapshot from Supabase via existing `db.py` helpers, calls `research_resolver.resolve_for_program_gen` for the knowledge pack, calls `program_engine.orchestrator.author_and_validate(...)` for the program, persists it as a `draft` row on `programs`, and prints the rendered artifact (per Task 5.2). **Writes to `programs.status='draft'` only**; the existing builder's draft list will surface it in the mini-app for inspection if needed, but no activation flow is part of this demo.

**Steps:**
- [ ] Implement runner.
- [ ] Smoke-test against landon_brice (read his real profile + write a draft program).
- [ ] Verify the draft appears in `programs` table for `landon_brice` with `engine_version='v1'`.

### Task 5.2: Renderer (terminal artifact)

**Files:**
- Create: `pitcher_program_app/bot/services/program_engine/render.py`
- Create: `pitcher_program_app/tests/test_render.py`

**Approach:** A `render(program, fmt='text'|'json'|'markdown') → str` function that produces a viewable artifact. **`text` is the demo deliverable** — a colored terminal output (use the `rich` library if not already in `requirements.txt`; else plain ANSI codes) showing: program header, phase-by-phase week-by-week schedule, per-day throwing 5-tuple + lifting blocks, intent/load/ACWR sidebars, the "why" (rationale + cited docs). `markdown` for sharing; `json` for tests.

**Steps:**
- [ ] Implement `render()` in 3 formats.
- [ ] Tests: round-trip JSON; markdown contains all rationale citations; text output is non-empty for a real program.

### Task 5.3: §1 demo criteria — automated proofs

**Files:**
- Create: `pitcher_program_app/tests/test_clean_room_demo_criteria.py`

**Approach:** Four automated checks corresponding to the §1 done-state:
1. **Generation criterion** — running the runner produces a program whose `generation_provenance.attempts == 1` (LLM succeeded clean) OR `fallback_used == False` (LLM + reprompt succeeded). Fallback acceptable but criterion records which path was taken.
2. **Artifact criterion** — `render(program, 'markdown')` non-empty + contains all phases + cites at least 3 research docs.
3. **Living-knowledge criterion** — edit `velocity_progression_model.md` (test fixture appends a sentinel string), re-run the runner, assert `knowledge_version` differs AND at least one day's content reflects the change (e.g. a phase note text changes). Revert the doc after the test.
4. **Projection criterion** — project the program at Wk2D3 with `readiness = {flag_level: "YELLOW", category_scores: {tissue: 2.0, ...}}`; assert `delivered.intent_pct < intended.intent_pct`; assert `delivered.phase_name == intended.phase_name` (still oriented to goal); assert `governor_signal` shape matches the active policy.

**Steps:**
- [ ] Implement all 4 criterion tests.
- [ ] Run end-to-end: `pytest pitcher_program_app/tests/test_clean_room_demo_criteria.py -v` — all 4 pass.
- [ ] **This is the v1 ship gate.**

---

# Phase 6 — Cleanup + tag

### Task 6.1: Documentation

**Files:**
- Create: `pitcher_program_app/docs/program_engine_v1_runbook.md`
- Update: `CLAUDE.md` "What's Next" — replace the ★ "in design" callout with a "shipped, clean-room, awaiting v2 live integration" callout.
- Update: `pitcher_program_app/docs/superpowers/2026-05-31-program-engine-HANDOFF.md` — append a "Status as of <ship date>" section pointing to this plan + the demo runner.

**Steps:**
- [ ] Runbook: how to run the clean-room demo, how to edit knowledge, how to read the comparison report, how to invoke the validator on an existing program, known limitations.
- [ ] CLAUDE.md update.
- [ ] Handoff note update.

### Task 6.2: Plan v2 backlog scaffold

**Files:**
- Create: `pitcher_program_app/docs/superpowers/plans/2026-06-XX-program-engine-v2-live-backlog.md` (skeleton only — not a full plan)

**Approach:** A short doc enumerating the v2 work surface (live integration, drive policy decision, propagation flow, goal pack #2, legacy retire) with the seams in this plan referenced by file:line. So when v2 is greenlit, the plan-writer has a starting map.

**Steps:**
- [ ] Author the skeleton.

### Task 6.3: Tag

- [ ] `git tag program-engine-v1-clean-room`
- [ ] `git push origin program-engine-v1-clean-room`

---

## Acceptance criteria for the plan as a whole

1. Phase 0 green: alias map populated for every exercise in golden content; both xlsx in the repo and openpyxl-loadable; golden ACWR fixture checked in and `test_golden_acwr_curve.py` passing.
2. Phase 1 green: `velocity_progression_model.md` exists with `program_gen` in its frontmatter; `block_library.velocity_12wk_v1` row has populated `content`, `tunable_parameters_schema`, `modification_rules_json`, `research_doc_ids`; `research_resolver.resolve_for_program_gen` returns the correct doc set + a stable `knowledge_version` hash.
3. Phase 2 green: all guardrail invariants implemented as pure functions + tested; the golden ACWR fixture round-trips through `load_math` within 5%.
4. Phase 3 green: `PROGRAM_ENGINE_V1` flag-on routes through `author → validate → persist`; flag-off keeps the rotation-repeat path bit-identical (legacy goldens still pass); `programs` table has the additive engine_v1 columns; the fallback floor produces a guardrail-valid program from `velocity_12wk_v1`.
5. Phase 4 green: `project()` + `regovern()` + the comparison harness shipped; comparison report rendered for ≥3 policies × ≥4 scenarios; policy decision deferred to v2.
6. Phase 5 green: the clean-room runner produces a draft program for `landon_brice`; the 4 demo-criterion tests pass; `programs` table reflects the new draft with `engine_version='v1'` and a populated `knowledge_version`.
7. Phase 6 green: runbook + CLAUDE.md + handoff note updated; tag `program-engine-v1-clean-room` pushed.
8. **Live behavior unchanged for every pitcher.** `program_aware_plan_gen` flag values unchanged. Existing rotation-repeat path still serves every active program. No `plan_generated` writes affected.

---

## Risks + mitigations (specific to this plan)

| Risk | Mitigation |
|---|---|
| Golden xlsx files never get copied into the repo (Drive aliases) | Phase 0.2 explicitly STOPS and surfaces the gap; no later phase can begin until the files load. |
| LLM-forward generation produces unreliable output | Phase 2 guardrails are universal; Phase 3 has reprompt + deterministic fallback floor; the floor itself is a real periodized program. Variance becomes an observability problem (counted in `program_generation_failures`), not a correctness problem. |
| Living-knowledge changes break existing active programs | Per L12, no auto-mutation of active programs. v1 doesn't even surface the propagation flow — it's Plan v2. |
| The "drive" seam locks the wrong policy by accident | L7 explicit: build the seam, ship policy comparison, defer the choice. Seam is flag-gated off the live path. |
| `PROGRAM_ENGINE_V1` flag accidentally flipped in prod | Flag is module-level Python constant; not in env vars, not in DB. To flip requires a code change + deploy. Phase 5 demo runner sets the flag inside the script's own process via context manager / direct import — never persisted. |
| Schema migration `034` collides with concurrent work | Migration number 034 confirmed free (last applied is 032; 033 is reserved for Phase 1 knowledge seed). Both 033 + 034 are additive UPSERT/`ADD COLUMN IF NOT EXISTS`. |
| Reasoning-model latency at compile time | One-time op per program; 120s timeout per `call_llm_reasoning` is acceptable; fallback on timeout. |
| Exercise alias map incomplete | Tests assert `UnknownExerciseAlias` raised on miss; guardrail #7 fails hard with the offending name in the error; the fix is a JSON edit. |

---

## Out of scope for this plan (deliberately)

- Flipping `program_aware_plan_gen` for any pitcher (Plan v2).
- Wiring `project()` into `program_aware_planner.compose_program_aware_plan` (Plan v2).
- Building a new pitcher UI for the engine — the existing `BuilderSlideOver` + `Programs.jsx` continue to work; the demo renderer is the v1 UI surface (Plan v2 = the real pitcher UI as a separate parallel effort, per spec §9 and decision #13.9).
- Coach-mediated knowledge-propagation proposal flow (Plan v2).
- Retiring `training_programs` / `team_assigned_blocks` / `programs.py` (Plan v2 backlog).
- Goal pack #2 (longtoss, hypertrophy, RTT) — engine is goal-agnostic by design, but only velocity content is authored in v1.
- `prohibited_throw_kinds` / prohibited-day conflict logic (Plan 9 backlog).

---

> **Status:** Drafted 2026-06-01. **Phase 0 complete 2026-06-01** (commit on `claude/confident-hopper-JolkY`); Phase 1 next.

---

## Phase 0 status (2026-06-01) — DONE

### Phase 0.2 (golden files) — done with documented gap

Three golden assets copied into `pitcher_program_app/data/knowledge/golden/`:
- `the_program.xlsx` — 7-tab type-matrix (from repo `past_arm_programs/The Program  (1).xlsx`)
- `maintenance_plan.xlsx` — 2-day arm-care plan (from pitcher upload `2026-05-26_program.xlsx`, identical to repo copy)
- `periodized_lifting.xlsx` — 3-phase periodized lifting (newer 43KB pitcher upload, supersedes the 35KB repo `2026-05-26_lifting.xlsx`)
- `pitching_program_final.pdf` — 36pp day-type + named macrocycles

**Gap (documented in `data/knowledge/golden/README.md`):** `Ramp up with Bullpen 12wk.xlsx` and `Return to mound 9wk.xlsx` exist in `past_arm_programs/` only as 1-2KB macOS Drive aliases (`BadZipFile: File is not a zip file`). Recon dossier captured the weekly G curve and one verified daily 5-tuple verbatim — that's enough for Phase 2 invariant validation, but not for full daily calibration. Operator close-the-gap procedure documented in the README (Finder → "Show Original" → save outside Drive).

### Phase 0.1 (exercise alias map) — done with deviation from spec

**Deviation:** the plan called for a hand-curated `data/knowledge/exercise_alias_map.json`. A live Supabase query found that **`exercises.aliases` jsonb column is already populated for all 159 rows** with the specific cases the spec called out (ex_004 RFESS → "Bulgarian split squat"; ex_020 Chest-Supported Row → "seal row"). Maintaining a duplicate JSON would create a sync problem; the Supabase column is the canonical store.

Ships:
- `bot/services/exercise_alias.py` — `resolve_alias()`, `try_resolve_alias()`, `audit_names()`, `refresh_index()`, `load_from_snapshot()`. Lazy-builds index from Supabase via `get_exercises()`; falls back to a JSON snapshot for offline tooling. Latched logging (no spam on retry).
- `tests/test_exercise_alias.py` — 15 tests covering normalization, lookup, error semantics, snapshot reload, collision handling, Supabase-failure resilience.
- `tests/fixtures/exercises_snapshot.json` — 159-row JSON snapshot of `exercises.aliases` for offline use.
- `scripts/dump_exercises_snapshot.py` — regenerates the snapshot when aliases get edited live.
- `scripts/audit_golden_alias_coverage.py` — walks every name-shaped cell in `data/knowledge/golden/*.xlsx`, classifies against the alias index, and prints unresolved names sorted by frequency for triage. Supports `--csv` + `--snapshot <path>` + `--live`.

**First audit run** (committed as `docs/superpowers/research/2026-06-01-golden-alias-audit.{csv,txt}`):
- 904 name-shaped cells across the 3 xlsx
- **Resolved:** 92 cell-references → 38 unique canonical exercises
- **Unresolved:** 812 cell-references → 324 unique normalized names

Top unresolved are genuine missing exercises/aliases — `Pec Dribble` (13×), `Posterior slide lunge` (11×), `Skater squat` (11×), `9090 Dribble` (8×), `Lateral step down heel tap` (7×), `Hip Thrusters` (7× — likely needs alias added to ex_003), `Sumo Landmine Squat`, `Banded bench press`, `TRX Eccentric Pec lower`, etc. These either get added as aliases to existing rows or as net-new `exercises` rows. **Phase 1 work, not Phase 0** — Phase 1 walks this list with the operator and decides per-row before authoring the velocity knowledge pack.

### Phase 0.3 (golden ACWR curve fixture) — done as a recon-sourced fixture

**Deviation:** the plan called for `scripts/extract_golden_acwr_curve.py` to read the raw xlsx. Since the source xlsx is Drive-aliased (Phase 0.2 gap), the fixture is seeded from the recon dossier's verbatim transcript instead.

Ships:
- `tests/fixtures/golden_acwr_curve.json` — 12-week weekly G curve `[6960, 9194, 10935, 10375, 12049, 13516, 12090, 12960, 13620, 14000, 14300, 14616]` (Wks 10-11 linearly interpolated, flagged in `_meta`); verified daily anchor `(45ft, 40 throws, 50% intent → G=2145)`; deload weeks [4, 7]; ACWR band [0.8, 1.3] / hard cap 1.5; `_meta.gaps` documents the missing daily grid.
- `scripts/extract_golden_acwr_curve.py` — wired for the FUTURE re-extraction. Looks for `data/knowledge/golden/ramp_up_with_bullpen_12wk.xlsx`; exits with a clear message if still missing. Will OVERWRITE the fixture with the full daily 5-tuple grid once the xlsx is recovered.
- `tests/test_golden_acwr_curve.py` — 9 tests pinning the curve shape, the 3-up-1-down deload, the verified daily anchor, the ACWR band, and a sanity computation against the curve itself.

### Full test suite

`pytest tests/ -x --ignore=tests/test_coach_chat.py` → **899 passed, 8 skipped, 0 failures** (24 new tests, no regressions). `tests/test_coach_chat.py`'s 5 known-failing tests stay broken per the CLAUDE.md "Known Issues" pre-existing version drift — unrelated to Phase 0.

### Phase 1 entry conditions

- [x] Goldens copied + README provenance documented
- [x] Alias resolver + audit tooling shipped
- [x] Audit run committed; Phase 1 has a triage list
- [x] Golden ACWR fixture pinned (recon-sourced; extraction script ready for richer source)
- [x] Full suite green
- [ ] **Operator decision needed** before Phase 1.2: walk the 324 unresolved-name list (see audit report) and decide per row: alias-to-add | new-exercise | noise. Default behavior if not done: Phase 1's `velocity_progression_model.md` may reference names that fail `resolve_alias` at generation time, surfaced as `UnknownExerciseAlias` from Phase 2.3 guardrail #7.
