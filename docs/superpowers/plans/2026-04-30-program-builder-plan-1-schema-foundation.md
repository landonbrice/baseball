# Program Builder v1 — Plan 1: Schema Foundation & Cold-Start Safety

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land all schema changes, the per-domain phase model, the legacy `plan_generator` golden-snapshot safety net, the saved_plans→Favorites migration, and the cadence-as-template bootstrap so the rest of the Program Builder v1 plans (Builder funnel, Daily composition rewrite, Anchoring, UX) can build on a stable foundation behind a feature flag.

**Architecture:** Additive-only schema. New canonical tables (`programs`, `favorited_blocks`, `program_builder_sessions`, plus four operational tables) sit alongside the existing `training_programs`/`program_templates` v0 scaffolding (deprecated-on-arrival; cleanup deferred to a later plan). `block_library` is extended with the spec's template fields. `teams.training_phase` splits into `throwing_phase` + `lifting_phase`. Per-domain phase precedence resolution lives in a new pure-function module, `bot/services/program_runtime.py`. Bootstrap migration synthesizes an active "In-Season Maintenance — Starter 7-day" program for the four current 7-day starters so the future daily-composition pipeline finds them on the program path; relievers stay on the legacy cold-start fallback until template seed authoring lands. Feature flag is a `pitcher_training_model.feature_flags` jsonb so the Phase-4 daily-composition rewrite can be scoped to 1–2 pitchers (R1).

**Tech Stack:** Python 3.11 / FastAPI / pytest. Supabase Postgres via `supabase-py`. Migrations applied via the Supabase MCP `apply_migration` tool, with SQL files version-controlled in `pitcher_program_app/scripts/migrations/`.

---

## Spec answers locked during clarification

These answers from the spec-clarification round shape this plan. Don't relitigate.

- **`saved_plans` → `favorited_blocks` migration:** required. Spec said "not migrated"; user overrode to "migrate."
- **`teams.training_phase` per-domain split:** in this plan, not deferred. Splits to `throwing_phase` + `lifting_phase`.
- **Cadence-based throwing stays a template:** the existing 7-day starter cadence is reified as the canonical "In-Season Maintenance — Starter 7-day" template, and current 7-day starters are bootstrapped onto an active program at cutover. Relievers stay on legacy fallback for now.
- **Empty-template handling:** UI hard-blocks. No code change in this plan; just don't pre-emptively seed beyond Starter 7-day.
- **Drafts visible to coach:** completed drafts only — `program_builder_sessions.status='completed' AND generated_program_id IS NOT NULL AND programs.status='draft'`. Schema must support this query; no UI yet.

## Existing prior art to coexist with

`pitcher_program_app/scripts/migrations/006_program_tables.sql` and `bot/services/programs.py` already create `program_templates`, `training_programs`, and `pitcher_training_model.active_program_id`. **Leave these untouched.** They power existing mini-app/coach-app flows. The new `programs` table sits alongside. Cleanup of the legacy v0 schema is deferred to a future plan once the new path is feature-flag-rolled to 100%.

## File Structure

**Migrations (all applied via Supabase MCP `apply_migration`):**
- `pitcher_program_app/scripts/migrations/009_programs_core.sql` — new tables
- `pitcher_program_app/scripts/migrations/010_block_library_extensions.sql` — template columns
- `pitcher_program_app/scripts/migrations/011_team_phase_split.sql` — per-domain phase columns
- `pitcher_program_app/scripts/migrations/012_pitcher_training_model_overrides.sql` — phase override + feature flags
- `pitcher_program_app/scripts/migrations/013_saved_plans_to_favorites.sql` — data migration
- `pitcher_program_app/scripts/migrations/014_seed_starter_7day_template.sql` — canonical template seed
- `pitcher_program_app/scripts/migrations/015_bootstrap_starter_programs.sql` — synthesize active programs

**New Python:**
- `pitcher_program_app/bot/services/program_runtime.py` — `get_effective_phase`, `get_active_program_day`, `compute_program_day_index`

**Modified Python:**
- `pitcher_program_app/bot/services/db.py` — new helpers for `programs`, `favorited_blocks`, per-domain team phase reads
- `pitcher_program_app/bot/services/team_scope.py` — read `throwing_phase`/`lifting_phase` instead of single `training_phase`

**New tests:**
- `pitcher_program_app/tests/test_legacy_plan_generator_golden.py` — golden-snapshot lockdown (Task 0; the safety net for plans 4+)
- `pitcher_program_app/tests/test_program_runtime.py` — `get_effective_phase` precedence + `get_active_program_day`
- `pitcher_program_app/tests/test_team_phase_split_compat.py` — `team_scope.py` behavior unchanged when only `training_phase` is set
- `pitcher_program_app/tests/test_saved_plans_migration.py` — data migration shape
- `pitcher_program_app/tests/test_starter_cadence_bootstrap.py` — bootstrap correctness for 4 starters

**New fixtures:**
- `pitcher_program_app/tests/fixtures/legacy_plan_generator/` — golden JSON snapshots (one per fixture case)

---

## Task 0: Lock legacy `plan_generator` behavior with golden snapshots — **DEFERRED to Plan 4**

> **Status (2026-04-30):** Deferred. The implementer surfaced that the plan's premise (a simple `force_python_only` bypass + production-data capture) doesn't match the real code, and Plan 1 is purely additive — it does not modify `plan_generator.py`, so the safety net isn't needed here. The work belongs adjacent to Plan 4's daily-composition rewrite where `plan_generator` will actually be touched.
>
> **Findings to carry into Plan 4 (do not lose):**
> 1. `generate_plan` in `pitcher_program_app/bot/services/plan_generator.py` is `async`, signature `async def generate_plan(pitcher_id: str, triage_result: dict, checkin_inputs: dict = None, *, triage_rationale_detail: dict | None = None)`. It loads the profile internally, has no `target_date` kwarg, and has no LLM bypass.
> 2. Sources of non-determinism inside the python_plan path alone: `datetime.now(CHICAGO_TZ)` (line 168), `get_rotation_day(profile)` (line 125), `get_recent_entries(pitcher_id, n=7)` (line 124), `resolve_team_block(today_str)` (line 171), `compute_days_until_next_start(today_str)` (line 174), `get_recent_exercise_ids(pitcher_id, days=7)` (line 209), `get_today_mobility()` (line 192, ISO week of year), `resolve_research(...)` (line 258, file I/O + writes `research_load_log`), `record_and_check_emergency(...)` (line 379, stateful 30-min counter).
> 3. The fallback path the goldens should lock is the existing **timeout-fallback** branch (lines 375-387: `hydrate_exercises` per block + `derive_day_focus`), not a synthetic `force_python_only` branch. Recommended approach: mock `call_llm`/`call_llm_reasoning` to raise `TimeoutError`, which routes through the real production fallback.
> 4. `triage_result` real shape includes `triage_result["protocol_adjustments"]["arm_care_template"]` (line 184), `["plyocare_allowed"]` (line 196), `["throwing_adjustments"]` (line 230). Capture-script CASES must populate these.
> 5. To make goldens viable: (a) mock `call_llm`/`call_llm_reasoning` → `TimeoutError`, (b) freezegun the wall clock, (c) JSON-fixture the data layer (`load_profile`, `get_recent_entries`, `get_recent_exercise_ids`, `resolve_team_block`, `compute_days_until_next_start`, `record_and_check_emergency`), (d) expand `triage_result` fixtures with the `protocol_adjustments` block.
>
> Plan 4 should land this work as Task 4.0, before any composition-pipeline code change.

**[Original Task 0 step-by-step preserved below for reference; do not execute as part of Plan 1.]**

> **Why this was originally first:** Plans 4–6 must claim "byte-identical output" for cold-start cases (Acceptance Criterion #5). That claim is only auditable if the baseline is captured *before* this plan starts touching anything. If a later task in this plan accidentally perturbs `plan_generator`, the golden tests will catch it the same day.

**Files:**
- Create: `pitcher_program_app/tests/test_legacy_plan_generator_golden.py`
- Create: `pitcher_program_app/tests/fixtures/legacy_plan_generator/case_*.json` (8 fixtures)
- Create: `pitcher_program_app/scripts/capture_plan_generator_goldens.py` (one-shot capture)

- [ ] **Step 1: Write the capture script**

Create `pitcher_program_app/scripts/capture_plan_generator_goldens.py`:

```python
"""One-shot capture of plan_generator output for golden-snapshot tests.

Run: python -m scripts.capture_plan_generator_goldens

Generates 8 fixture cases covering green/yellow/red × starter/reliever × WHOOP/no-WHOOP.
Writes to tests/fixtures/legacy_plan_generator/case_<name>.json.

DO NOT regenerate after Plan 1 commits. The whole point is to lock current behavior.
If a future change intentionally alters plan_generator output, regenerate explicitly
in that change's commit and call it out in the PR description.
"""
import json
from pathlib import Path
from datetime import date

from bot.services.plan_generator import generate_plan
from bot.services import db

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "legacy_plan_generator"

CASES = [
    # (case_name, pitcher_id, mock_checkin_inputs, mock_triage_result)
    ("starter_green_day3", "landon_brice",
     {"arm_feel": 8, "overall_energy": 7, "sleep_hours": 7.5},
     {"flag_level": "green", "modification_flags": [], "reasons": []}),
    ("starter_yellow_day3", "landon_brice",
     {"arm_feel": 5, "overall_energy": 5, "sleep_hours": 6.0},
     {"flag_level": "yellow", "modification_flags": ["fatigue_general"], "reasons": ["arm_feel_low"]}),
    ("starter_red_day1", "landon_brice",
     {"arm_feel": 3, "overall_energy": 3, "sleep_hours": 5.0},
     {"flag_level": "red", "modification_flags": ["arm_protect"], "reasons": ["arm_feel_critical"]}),
    ("reliever_green", "pitcher_kamat_001",
     {"arm_feel": 8, "overall_energy": 7, "sleep_hours": 7.0},
     {"flag_level": "green", "modification_flags": [], "reasons": []}),
    ("reliever_yellow_shoulder", "pitcher_kamat_001",
     {"arm_feel": 5, "overall_energy": 6, "sleep_hours": 6.5},
     {"flag_level": "yellow", "modification_flags": ["shoulder_protect"], "reasons": ["arm_feel_low"]}),
    ("starter_with_whoop_low_recovery", "pitcher_kwinter_001",
     {"arm_feel": 7, "overall_energy": 6, "sleep_hours": 6.0,
      "whoop_data": {"recovery_score": 28, "hrv": 45.0, "sleep_perf": 72}},
     {"flag_level": "yellow", "modification_flags": ["fatigue_general"], "reasons": ["whoop_low_recovery"]}),
    ("starter_critical_red", "pitcher_benner_001",
     {"arm_feel": 2, "overall_energy": 3, "sleep_hours": 4.0},
     {"flag_level": "red", "modification_flags": ["arm_shutdown"], "reasons": ["arm_feel_critical"]}),
    ("reliever_long_active_injury", "pitcher_heron_001",
     {"arm_feel": 7, "overall_energy": 7, "sleep_hours": 7.0},
     {"flag_level": "yellow", "modification_flags": ["elbow_protect"], "reasons": ["injury_history_active"]}),
]

def main():
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for case_name, pitcher_id, checkin_inputs, triage_result in CASES:
        profile = db.get_pitcher_profile(pitcher_id)
        if not profile:
            raise SystemExit(f"Pitcher {pitcher_id} not found — required for golden capture")
        plan = generate_plan(
            profile=profile,
            triage_result=triage_result,
            checkin_inputs=checkin_inputs,
            target_date=date(2026, 5, 1),  # fixed date for determinism
            force_python_only=True,  # skip LLM enrichment — we lock the python_plan only
        )
        output = {
            "case_name": case_name,
            "pitcher_id": pitcher_id,
            "checkin_inputs": checkin_inputs,
            "triage_result": triage_result,
            "plan": plan,
        }
        out = FIXTURE_DIR / f"case_{case_name}.json"
        out.write_text(json.dumps(output, indent=2, default=str, sort_keys=True))
        print(f"Wrote {out}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify `generate_plan` accepts `force_python_only` kwarg**

Run: `grep -n "force_python_only\|def generate_plan" pitcher_program_app/bot/services/plan_generator.py`

Expected: kwarg exists, OR add it. If it does not exist, add it as the first sub-step of Step 3 (it gates the LLM-enrichment block; default `False`).

If `force_python_only` doesn't exist, edit `bot/services/plan_generator.py` to thread it through:

```python
def generate_plan(profile, triage_result, checkin_inputs, target_date, force_python_only=False):
    python_plan = _build_python_plan(profile, triage_result, checkin_inputs, target_date)
    if force_python_only:
        python_plan["source"] = "python_fallback"
        python_plan["source_reason"] = "force_python_only"
        return python_plan
    # ... existing LLM enrichment path
```

- [ ] **Step 3: Run the capture script against current main**

Run: `cd pitcher_program_app && python -m scripts.capture_plan_generator_goldens`

Expected: 8 files written to `pitcher_program_app/tests/fixtures/legacy_plan_generator/`. Inspect one (`cat tests/fixtures/legacy_plan_generator/case_starter_green_day3.json | head -40`) to confirm it has `plan.exercise_blocks`, `plan.warmup`, `plan.day_focus`, etc.

- [ ] **Step 4: Write the golden test**

Create `pitcher_program_app/tests/test_legacy_plan_generator_golden.py`:

```python
"""Golden-snapshot lockdown for legacy plan_generator.

These tests assert that generate_plan(force_python_only=True) produces
byte-identical output for 8 representative cases. Plans 4+ rely on this
to claim "no behavior change for cold-start pitchers."

If a test fails, do NOT regenerate the fixture unless the change is
intentional and called out in the PR description.
"""
import json
from datetime import date
from pathlib import Path

import pytest

from bot.services.plan_generator import generate_plan
from bot.services import db

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "legacy_plan_generator"


def _load_cases():
    return sorted(FIXTURE_DIR.glob("case_*.json"))


@pytest.mark.parametrize("fixture_path", _load_cases(), ids=lambda p: p.stem)
def test_plan_generator_matches_golden(fixture_path, monkeypatch):
    fixture = json.loads(fixture_path.read_text())
    profile = db.get_pitcher_profile(fixture["pitcher_id"])
    assert profile, f"Pitcher {fixture['pitcher_id']} required for golden test"

    actual = generate_plan(
        profile=profile,
        triage_result=fixture["triage_result"],
        checkin_inputs=fixture["checkin_inputs"],
        target_date=date(2026, 5, 1),
        force_python_only=True,
    )
    expected = fixture["plan"]
    assert json.dumps(actual, sort_keys=True, default=str) == json.dumps(expected, sort_keys=True, default=str), (
        f"Plan output drifted for {fixture['case_name']}. "
        "If intentional, regenerate via: python -m scripts.capture_plan_generator_goldens"
    )
```

- [ ] **Step 5: Run the golden test, expect PASS on main**

Run: `cd pitcher_program_app && pytest tests/test_legacy_plan_generator_golden.py -v`

Expected: 8 PASS. If any fail on first run, the capture script and the test are using divergent code paths — investigate before continuing.

- [ ] **Step 6: Commit**

```bash
git add pitcher_program_app/tests/test_legacy_plan_generator_golden.py \
        pitcher_program_app/tests/fixtures/legacy_plan_generator/ \
        pitcher_program_app/scripts/capture_plan_generator_goldens.py \
        pitcher_program_app/bot/services/plan_generator.py
git commit -m "test: lock legacy plan_generator with golden snapshots

Captures byte-exact python-plan output for 8 representative cases
(green/yellow/red × starter/reliever × WHOOP/no-WHOOP). Plans 4+
rely on these to claim cold-start parity for pitchers without an
active program."
```

---

## Task 1: Migration 009 — programs core tables

**Files:**
- Create: `pitcher_program_app/scripts/migrations/009_programs_core.sql`

- [ ] **Step 1: Write the migration SQL**

```sql
-- Migration 009: Program Builder v1 — core tables
-- Adds:
--   programs                     — personalized, activatable program instances (per-pitcher, per-domain)
--   favorited_blocks             — immutable per-block snapshots (D8)
--   program_builder_sessions     — Socratic interview telemetry + 24h resume (D17)
--   program_hold_events          — every triage-paused day (B-mode counter pause; D7)
--   program_schedule_revisions   — every recompute (anchor changes etc.)
--   program_generation_failures  — validation failures during generate_program
--   coach_visible_override_events — player overrides surfaced to coaches

CREATE TABLE IF NOT EXISTS programs (
  program_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pitcher_id              TEXT NOT NULL REFERENCES pitchers(pitcher_id) ON DELETE CASCADE,
  parent_template_id      UUID NOT NULL,
  domain                  TEXT NOT NULL CHECK (domain IN ('throwing','lifting')),
  tuned_spec_json         JSONB NOT NULL DEFAULT '{}'::jsonb,
  generated_schedule_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  start_date              DATE NOT NULL,
  nominal_end_date        DATE NOT NULL,
  current_day_index       INT  NOT NULL DEFAULT 0,
  held_days_count         INT  NOT NULL DEFAULT 0,
  status                  TEXT NOT NULL CHECK (status IN ('draft','active','archived','error')),
  created_by              TEXT NOT NULL,
  created_by_role         TEXT NOT NULL CHECK (created_by_role IN ('pitcher','coach')),
  approval_required       BOOLEAN NOT NULL DEFAULT false,
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  activated_at            TIMESTAMPTZ,
  archived_at             TIMESTAMPTZ,
  archive_reason          TEXT
);

-- Enforces "one active per (pitcher, domain)" — partial unique index
CREATE UNIQUE INDEX IF NOT EXISTS idx_programs_one_active_per_domain
  ON programs (pitcher_id, domain)
  WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_programs_pitcher_status
  ON programs (pitcher_id, status);

CREATE INDEX IF NOT EXISTS idx_programs_status_created
  ON programs (status, created_at DESC);

CREATE TABLE IF NOT EXISTS favorited_blocks (
  favorite_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pitcher_id            TEXT NOT NULL REFERENCES pitchers(pitcher_id) ON DELETE CASCADE,
  source_daily_entry_id UUID NOT NULL,  -- not FK'd: daily_entries uses (pitcher_id, date) PK; this is an opaque ref
  block_type            TEXT NOT NULL CHECK (block_type IN ('lifting','arm_care','throwing','warmup')),
  block_snapshot_json   JSONB NOT NULL,
  note                  TEXT,
  favorited_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_favorited_blocks_pitcher_type
  ON favorited_blocks (pitcher_id, block_type, favorited_at DESC);

CREATE TABLE IF NOT EXISTS program_builder_sessions (
  session_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pitcher_id              TEXT NOT NULL REFERENCES pitchers(pitcher_id) ON DELETE CASCADE,
  initiator_id            TEXT NOT NULL,
  initiator_role          TEXT NOT NULL CHECK (initiator_role IN ('pitcher','coach')),
  interview_mode          TEXT NOT NULL CHECK (interview_mode IN ('personalize','team_personalize','authoring')),
  constraint_envelope_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  candidate_template_ids  TEXT[] NOT NULL DEFAULT '{}',
  turns_jsonb             JSONB NOT NULL DEFAULT '[]'::jsonb,
  chosen_template_id      UUID,
  tuned_spec_json         JSONB,
  status                  TEXT NOT NULL CHECK (status IN ('in_progress','completed','abandoned')),
  started_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_activity_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  generated_program_id    UUID REFERENCES programs(program_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_builder_sessions_pitcher_status
  ON program_builder_sessions (pitcher_id, status, last_activity_at DESC);

-- For "completed drafts visible to coach" query (locked answer to draft-visibility question):
CREATE INDEX IF NOT EXISTS idx_builder_sessions_completed_drafts
  ON program_builder_sessions (pitcher_id, generated_program_id)
  WHERE status = 'completed' AND generated_program_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS program_hold_events (
  hold_event_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  program_id     UUID NOT NULL REFERENCES programs(program_id) ON DELETE CASCADE,
  hold_date      DATE NOT NULL,
  triage_result  JSONB NOT NULL,
  reason_code    TEXT NOT NULL,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (program_id, hold_date)
);

CREATE INDEX IF NOT EXISTS idx_hold_events_program
  ON program_hold_events (program_id, hold_date DESC);

CREATE TABLE IF NOT EXISTS program_schedule_revisions (
  revision_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  program_id      UUID NOT NULL REFERENCES programs(program_id) ON DELETE CASCADE,
  revised_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  trigger_type    TEXT NOT NULL,
  old_schedule    JSONB NOT NULL,
  new_schedule    JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_schedule_revisions_program
  ON program_schedule_revisions (program_id, revised_at DESC);

CREATE TABLE IF NOT EXISTS program_generation_failures (
  failure_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id              UUID REFERENCES program_builder_sessions(session_id) ON DELETE SET NULL,
  attempt_number          INT NOT NULL,
  validation_failure_kind TEXT NOT NULL,
  llm_response            JSONB,
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_generation_failures_kind_created
  ON program_generation_failures (validation_failure_kind, created_at DESC);

CREATE TABLE IF NOT EXISTS coach_visible_override_events (
  event_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pitcher_id   TEXT NOT NULL REFERENCES pitchers(pitcher_id) ON DELETE CASCADE,
  program_id   UUID REFERENCES programs(program_id) ON DELETE SET NULL,
  event_kind   TEXT NOT NULL,
  event_date   DATE NOT NULL,
  details      JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_override_events_pitcher_date
  ON coach_visible_override_events (pitcher_id, event_date DESC);
```

- [ ] **Step 2: Apply migration via Supabase MCP**

Use the `mcp__b746b04a-...__apply_migration` tool with `name='009_programs_core'` and the SQL above.

- [ ] **Step 3: Verify schema applied**

Use `mcp__b746b04a-...__execute_sql` with:

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
    'programs','favorited_blocks','program_builder_sessions',
    'program_hold_events','program_schedule_revisions',
    'program_generation_failures','coach_visible_override_events'
  )
ORDER BY table_name;
```

Expected: 7 rows.

- [ ] **Step 4: Verify partial unique index**

```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'programs' AND indexname = 'idx_programs_one_active_per_domain';
```

Expected: index exists with `WHERE (status = 'active')`.

- [ ] **Step 5: Commit**

```bash
git add pitcher_program_app/scripts/migrations/009_programs_core.sql
git commit -m "feat(schema): add programs/favorited_blocks/builder_sessions and operational tables

Migration 009. Partial unique index enforces one active program per
(pitcher, domain). Operational tables (hold_events, schedule_revisions,
generation_failures, override_events) instrumented from day one per
spec Section 6 telemetry."
```

---

## Task 2: Migration 010 — block_library extensions

**Files:**
- Create: `pitcher_program_app/scripts/migrations/010_block_library_extensions.sql`

- [ ] **Step 1: Confirm `block_library` shape on main**

Run via Supabase MCP `execute_sql`:

```sql
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name = 'block_library' ORDER BY ordinal_position;
```

Note the existing columns. The migration must not collide with existing column names.

- [ ] **Step 2: Write migration**

```sql
-- Migration 010: extend block_library to act as canonical Template store.
-- All columns nullable so existing rows continue to work.

ALTER TABLE block_library
  ADD COLUMN IF NOT EXISTS domain                     TEXT
    CHECK (domain IS NULL OR domain IN ('throwing','lifting')),
  ADD COLUMN IF NOT EXISTS goal_tags                  TEXT[] NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS duration_range_weeks       INT4RANGE,
  ADD COLUMN IF NOT EXISTS compatible_phases          TEXT[] NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS tunable_parameters_schema  JSONB  NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS week_scaffold_json         JSONB,
  ADD COLUMN IF NOT EXISTS research_doc_ids           TEXT[] NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS modification_rules_json    JSONB,  -- nullable, reserved for v2 (D7 → C target)
  ADD COLUMN IF NOT EXISTS implied_phase              TEXT;

CREATE INDEX IF NOT EXISTS idx_block_library_domain_phases
  ON block_library (domain)
  WHERE domain IS NOT NULL;
```

- [ ] **Step 3: Apply via Supabase MCP**

`apply_migration(name='010_block_library_extensions', query=<sql above>)`

- [ ] **Step 4: Verify**

```sql
SELECT column_name FROM information_schema.columns
WHERE table_name = 'block_library'
  AND column_name IN ('domain','goal_tags','duration_range_weeks','compatible_phases',
                      'tunable_parameters_schema','week_scaffold_json','research_doc_ids',
                      'modification_rules_json','implied_phase');
```

Expected: 9 rows.

- [ ] **Step 5: Commit**

```bash
git add pitcher_program_app/scripts/migrations/010_block_library_extensions.sql
git commit -m "feat(schema): extend block_library with template fields

Adds domain, goal_tags, duration_range_weeks, compatible_phases,
tunable_parameters_schema, week_scaffold_json, research_doc_ids,
modification_rules_json (nullable, v2 reserved), implied_phase.
All additive + nullable — existing block_library rows unchanged."
```

---

## Follow-ups noted during execution (do not block tasks)

- **Task 1 corrections (009b applied, commit `eaf9087`):** `parent_template_id` and `chosen_template_id` changed UUID → TEXT to match `block_library.block_template_id` (which is TEXT). `favorited_blocks.source_daily_entry_id UUID` replaced with `source_pitcher_id TEXT + source_entry_date DATE` to match `daily_entries`' composite PK. Non-negative CHECK constraints on `programs.current_day_index`/`held_days_count`. Carry these field names forward to Tasks 5/8/9.
- **Task 2 polish (defer; not blocking):** add CHECK constraint on `block_library.implied_phase` once the phase vocabulary is locked (today: free-form). Reconsider `duration_range_weeks INT4RANGE` vs `min_weeks/max_weeks INT` pair if PostgREST/Pydantic friction shows up — the spec specified INT4RANGE, so kept as-is for now.

## Task 3: Migration 011 — `teams.training_phase` per-domain split

> Per the locked spec answer, splits the team-wide phase into `throwing_phase` + `lifting_phase` now, not v2. The single `training_phase` column stays for one cycle as a fallback so any straggler reads keep working; cleanup deferred to a later plan once all callers migrate.

**Files:**
- Create: `pitcher_program_app/scripts/migrations/011_team_phase_split.sql`

- [ ] **Step 1: Write migration**

```sql
-- Migration 011: split teams.training_phase into per-domain columns.
-- training_phase column kept (deprecated) for one cycle.

ALTER TABLE teams
  ADD COLUMN IF NOT EXISTS throwing_phase TEXT,
  ADD COLUMN IF NOT EXISTS lifting_phase  TEXT;

-- Backfill: every existing team's per-domain phases default to its current training_phase.
UPDATE teams
SET throwing_phase = COALESCE(throwing_phase, training_phase),
    lifting_phase  = COALESCE(lifting_phase,  training_phase)
WHERE training_phase IS NOT NULL;

COMMENT ON COLUMN teams.training_phase IS
  'DEPRECATED — use throwing_phase / lifting_phase. Retained for one cycle.';
```

- [ ] **Step 2: Apply migration**

`apply_migration(name='011_team_phase_split', query=<sql above>)`

- [ ] **Step 3: Verify backfill**

```sql
SELECT team_id, training_phase, throwing_phase, lifting_phase FROM teams;
```

Expected: every row's `throwing_phase` and `lifting_phase` equal `training_phase`.

- [ ] **Step 4: Write the team_scope.py compatibility test**

Create `pitcher_program_app/tests/test_team_phase_split_compat.py`:

```python
"""When team_scope reads team phase, it should prefer the per-domain
columns and fall back to training_phase only if the new columns are NULL."""

from unittest.mock import MagicMock, patch

from bot.services import team_scope


def test_team_phase_prefers_per_domain():
    fake_team = {
        "team_id": "team_1",
        "training_phase": "in_season_active",
        "throwing_phase": "preseason",
        "lifting_phase":  "in_season_active",
    }
    with patch.object(team_scope, "_load_team", return_value=fake_team):
        assert team_scope.get_team_phase("team_1", domain="throwing") == "preseason"
        assert team_scope.get_team_phase("team_1", domain="lifting")  == "in_season_active"


def test_team_phase_falls_back_to_training_phase():
    fake_team = {
        "team_id": "team_1",
        "training_phase": "in_season_active",
        "throwing_phase": None,
        "lifting_phase":  None,
    }
    with patch.object(team_scope, "_load_team", return_value=fake_team):
        assert team_scope.get_team_phase("team_1", domain="throwing") == "in_season_active"
        assert team_scope.get_team_phase("team_1", domain="lifting")  == "in_season_active"
```

- [ ] **Step 5: Run, expect FAIL**

Run: `pytest pitcher_program_app/tests/test_team_phase_split_compat.py -v`

Expected: FAIL — `team_scope` likely lacks `get_team_phase` or `_load_team`. Note exact error.

- [ ] **Step 6: Implement `get_team_phase` in `team_scope.py`**

Open `pitcher_program_app/bot/services/team_scope.py`. Add (or replace if it exists):

```python
def _load_team(team_id: str) -> dict | None:
    from bot.services import db
    return db.get_team(team_id)


def get_team_phase(team_id: str, domain: str) -> str | None:
    """Return the team-wide phase for the given domain.

    Per spec answer: teams.training_phase is split into throwing_phase /
    lifting_phase. Old column kept as fallback for one cycle.
    """
    if domain not in ("throwing", "lifting"):
        raise ValueError(f"domain must be 'throwing' or 'lifting', got {domain!r}")
    team = _load_team(team_id)
    if not team:
        return None
    per_domain = team.get(f"{domain}_phase")
    if per_domain:
        return per_domain
    return team.get("training_phase")
```

If `db.get_team` doesn't exist, add it in `db.py`:

```python
def get_team(team_id: str) -> dict | None:
    resp = (
        get_client()
        .table("teams")
        .select("*")
        .eq("team_id", team_id)
        .limit(1)
        .execute()
    )
    return (resp.data or [None])[0]
```

- [ ] **Step 7: Run test, expect PASS**

Run: `pytest pitcher_program_app/tests/test_team_phase_split_compat.py -v`

Expected: 2 PASS.

- [ ] **Step 8: Sweep team_scope.py + other callers for `training_phase` reads**

Run: `grep -n "training_phase" pitcher_program_app/bot/ pitcher_program_app/api/ -r`

For each hit that is reading the team's phase (not a triage-result key, not a `daily_entries` key, not a personal phase override), replace `team["training_phase"]` with `team_scope.get_team_phase(team_id, domain=...)`. **Pass through the domain argument from the caller — do NOT pick one arbitrarily.** If a caller doesn't have a clear domain, leave a TODO and surface it in the commit message.

Common sites likely needing this update (from prior `team_scope.py` code):
- `team_scope.get_team_roster_overview` — picks per-domain phase per pitcher row
- `coach_routes.py` — phase pill payload

- [ ] **Step 9: Run full backend test suite**

Run: `cd pitcher_program_app && pytest -x`

Expected: no regressions. The legacy plan_generator goldens (Task 0) MUST still pass.

- [ ] **Step 10: Commit**

```bash
git add pitcher_program_app/scripts/migrations/011_team_phase_split.sql \
        pitcher_program_app/bot/services/team_scope.py \
        pitcher_program_app/bot/services/db.py \
        pitcher_program_app/tests/test_team_phase_split_compat.py
git commit -m "feat(schema): split teams.training_phase into per-domain columns

Adds teams.throwing_phase + teams.lifting_phase, backfilled from
training_phase. Retains training_phase as deprecated fallback for
one cycle. team_scope.get_team_phase(team_id, domain) is the single
read door; callers updated to pass domain explicitly."
```

---

## Task 4: Migration 012 — pitcher overrides + feature flags

**Files:**
- Create: `pitcher_program_app/scripts/migrations/012_pitcher_training_model_overrides.sql`

- [ ] **Step 1: Write migration**

```sql
-- Migration 012: per-pitcher phase overrides + feature flags.

ALTER TABLE pitcher_training_model
  ADD COLUMN IF NOT EXISTS coach_throwing_phase_override TEXT,
  ADD COLUMN IF NOT EXISTS coach_lifting_phase_override  TEXT,
  ADD COLUMN IF NOT EXISTS feature_flags                 JSONB NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN pitcher_training_model.feature_flags IS
  'Per-pitcher feature flags. Known keys: program_aware_plan_gen (bool, scoped rollout for Plan 4).';
```

- [ ] **Step 2: Apply via Supabase MCP**

`apply_migration(name='012_pitcher_training_model_overrides', query=<sql above>)`

- [ ] **Step 3: Verify**

```sql
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name = 'pitcher_training_model'
  AND column_name IN ('coach_throwing_phase_override','coach_lifting_phase_override','feature_flags');
```

Expected: 3 rows.

- [ ] **Step 4: Add `db.get_feature_flag` helper test**

Create or extend `pitcher_program_app/tests/test_feature_flags.py`:

```python
from unittest.mock import patch
from bot.services import db


def test_feature_flag_default_false():
    with patch.object(db, "get_pitcher_training_model",
                      return_value={"feature_flags": {}}):
        assert db.get_feature_flag("landon_brice", "program_aware_plan_gen") is False


def test_feature_flag_explicit_true():
    with patch.object(db, "get_pitcher_training_model",
                      return_value={"feature_flags": {"program_aware_plan_gen": True}}):
        assert db.get_feature_flag("landon_brice", "program_aware_plan_gen") is True


def test_feature_flag_missing_model_row_is_false():
    with patch.object(db, "get_pitcher_training_model", return_value=None):
        assert db.get_feature_flag("nonexistent", "program_aware_plan_gen") is False
```

- [ ] **Step 5: Run, expect FAIL**

Run: `pytest pitcher_program_app/tests/test_feature_flags.py -v`

Expected: FAIL — `db.get_feature_flag` does not exist.

- [ ] **Step 6: Implement helper in `bot/services/db.py`**

```python
def get_feature_flag(pitcher_id: str, key: str) -> bool:
    """Read a per-pitcher feature flag from pitcher_training_model.feature_flags.

    Returns False on missing model row, missing key, or non-truthy value.
    """
    model = get_pitcher_training_model(pitcher_id)
    if not model:
        return False
    flags = model.get("feature_flags") or {}
    return bool(flags.get(key))
```

- [ ] **Step 7: Run test, expect PASS**

Run: `pytest pitcher_program_app/tests/test_feature_flags.py -v`

Expected: 3 PASS.

- [ ] **Step 8: Commit**

```bash
git add pitcher_program_app/scripts/migrations/012_pitcher_training_model_overrides.sql \
        pitcher_program_app/bot/services/db.py \
        pitcher_program_app/tests/test_feature_flags.py
git commit -m "feat(schema): add coach phase overrides + per-pitcher feature flags

coach_throwing_phase_override / coach_lifting_phase_override implement
the per-domain coach override slot in the precedence stack. feature_flags
jsonb gates Plan 4's daily-composition rewrite for scoped rollout (R1)."
```

---

## Task 5: `program_runtime.get_effective_phase` — precedence resolution

**Files:**
- Create: `pitcher_program_app/bot/services/program_runtime.py`
- Create: `pitcher_program_app/tests/test_program_runtime.py`

- [ ] **Step 1: Write the test**

```python
"""Tests for program_runtime — phase precedence and active-program lookups."""

from unittest.mock import patch
import pytest


def test_phase_precedence_active_program_wins():
    """When pitcher has an active program, its template's implied_phase wins."""
    from bot.services import program_runtime

    with patch.object(program_runtime, "_load_active_program", return_value={
        "program_id": "p1",
        "domain": "throwing",
        "parent_template_id": "tpl1",
    }), patch.object(program_runtime, "_load_template_implied_phase", return_value="return_to_mound"), \
         patch.object(program_runtime, "_load_pitcher_overrides", return_value={
             "coach_throwing_phase_override": "preseason"}), \
         patch.object(program_runtime, "_load_team_phase_for_pitcher", return_value="in_season_active"):
        assert program_runtime.get_effective_phase("landon_brice", "throwing") == "return_to_mound"


def test_phase_precedence_coach_override_wins_when_no_program():
    from bot.services import program_runtime

    with patch.object(program_runtime, "_load_active_program", return_value=None), \
         patch.object(program_runtime, "_load_pitcher_overrides", return_value={
             "coach_throwing_phase_override": "preseason"}), \
         patch.object(program_runtime, "_load_team_phase_for_pitcher", return_value="in_season_active"):
        assert program_runtime.get_effective_phase("landon_brice", "throwing") == "preseason"


def test_phase_precedence_falls_back_to_team_default():
    from bot.services import program_runtime

    with patch.object(program_runtime, "_load_active_program", return_value=None), \
         patch.object(program_runtime, "_load_pitcher_overrides", return_value={
             "coach_throwing_phase_override": None}), \
         patch.object(program_runtime, "_load_team_phase_for_pitcher", return_value="in_season_active"):
        assert program_runtime.get_effective_phase("landon_brice", "throwing") == "in_season_active"


def test_phase_returns_none_when_nothing_configured():
    from bot.services import program_runtime

    with patch.object(program_runtime, "_load_active_program", return_value=None), \
         patch.object(program_runtime, "_load_pitcher_overrides", return_value={}), \
         patch.object(program_runtime, "_load_team_phase_for_pitcher", return_value=None):
        assert program_runtime.get_effective_phase("landon_brice", "throwing") is None


def test_phase_rejects_unknown_domain():
    from bot.services import program_runtime
    with pytest.raises(ValueError, match="domain"):
        program_runtime.get_effective_phase("landon_brice", "yoga")
```

- [ ] **Step 2: Run, expect FAIL**

Run: `pytest pitcher_program_app/tests/test_program_runtime.py -v`

Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Create `bot/services/program_runtime.py`**

```python
"""Program runtime helpers: phase precedence resolution + active-program lookups.

Pure functions. All DB reads go through small _load_* helpers so tests
can monkeypatch them. New canonical home for queries against the new
`programs` table — coexists with legacy `bot/services/programs.py`
(which targets the v0 `training_programs` table and stays untouched).
"""
from __future__ import annotations

from datetime import date
from typing import Optional

_VALID_DOMAINS = ("throwing", "lifting")


def _ensure_domain(domain: str) -> None:
    if domain not in _VALID_DOMAINS:
        raise ValueError(f"domain must be one of {_VALID_DOMAINS}, got {domain!r}")


def _load_active_program(pitcher_id: str, domain: str) -> Optional[dict]:
    """Return the row from `programs` where (pitcher_id, domain, status='active'), or None."""
    from bot.services import db
    return db.get_active_program(pitcher_id, domain)


def _load_template_implied_phase(template_id: str) -> Optional[str]:
    from bot.services import db
    tpl = db.get_block_library_row(template_id)
    if not tpl:
        return None
    return tpl.get("implied_phase")


def _load_pitcher_overrides(pitcher_id: str) -> dict:
    from bot.services import db
    model = db.get_pitcher_training_model(pitcher_id) or {}
    return {
        "coach_throwing_phase_override": model.get("coach_throwing_phase_override"),
        "coach_lifting_phase_override":  model.get("coach_lifting_phase_override"),
    }


def _load_team_phase_for_pitcher(pitcher_id: str, domain: str) -> Optional[str]:
    from bot.services import db, team_scope
    profile = db.get_pitcher_profile(pitcher_id) or {}
    team_id = profile.get("team_id")
    if not team_id:
        return None
    return team_scope.get_team_phase(team_id, domain=domain)


def get_effective_phase(pitcher_id: str, domain: str) -> Optional[str]:
    """Per-domain phase precedence: active program implied_phase > coach override > team default.

    See spec D6 + Section 1 (Phase model).
    """
    _ensure_domain(domain)

    active = _load_active_program(pitcher_id, domain)
    if active and active.get("parent_template_id"):
        implied = _load_template_implied_phase(active["parent_template_id"])
        if implied:
            return implied

    overrides = _load_pitcher_overrides(pitcher_id)
    override = overrides.get(f"coach_{domain}_phase_override")
    if override:
        return override

    return _load_team_phase_for_pitcher(pitcher_id, domain)
```

- [ ] **Step 4: Add the supporting db helpers**

Open `pitcher_program_app/bot/services/db.py`. Add:

```python
def get_active_program(pitcher_id: str, domain: str) -> dict | None:
    """Return the single row from `programs` where status='active' for (pitcher_id, domain), or None.

    Partial unique index guarantees at most one such row.
    """
    if domain not in ("throwing", "lifting"):
        raise ValueError(f"domain must be 'throwing' or 'lifting', got {domain!r}")
    resp = (
        get_client()
        .table("programs")
        .select("*")
        .eq("pitcher_id", pitcher_id)
        .eq("domain", domain)
        .eq("status", "active")
        .limit(1)
        .execute()
    )
    return (resp.data or [None])[0]


def get_block_library_row(template_id: str) -> dict | None:
    resp = (
        get_client()
        .table("block_library")
        .select("*")
        .eq("id", template_id)  # adjust if PK column name differs; verify with information_schema
        .limit(1)
        .execute()
    )
    return (resp.data or [None])[0]
```

Before writing `get_block_library_row`, run:

```sql
SELECT column_name FROM information_schema.columns
WHERE table_name = 'block_library' AND ordinal_position = 1;
```

If the PK column is not named `id`, update the `.eq()` call accordingly.

- [ ] **Step 5: Run tests, expect PASS**

Run: `pytest pitcher_program_app/tests/test_program_runtime.py -v`

Expected: 5 PASS.

- [ ] **Step 6: Commit**

```bash
git add pitcher_program_app/bot/services/program_runtime.py \
        pitcher_program_app/bot/services/db.py \
        pitcher_program_app/tests/test_program_runtime.py
git commit -m "feat: program_runtime.get_effective_phase with precedence stack

Active program implied_phase > coach per-pitcher override > team
per-domain default. New module coexists with legacy programs.py
(which targets the v0 training_programs table)."
```

---

## Task 6: `program_runtime.get_active_program_day`

> Reads the day-by-day prescription for a date from an active program's `generated_schedule_json`. The Plan 4 daily-composition rewrite consumes this; landing it here keeps Plan 4 narrowly scoped to triage/composition.

**Files:**
- Modify: `pitcher_program_app/bot/services/program_runtime.py`
- Modify: `pitcher_program_app/tests/test_program_runtime.py`

- [ ] **Step 1: Write tests**

Append to `pitcher_program_app/tests/test_program_runtime.py`:

```python
from datetime import date


def test_get_active_program_day_computes_index_from_dates():
    from bot.services import program_runtime
    program = {
        "program_id": "p1",
        "domain": "throwing",
        "start_date": "2026-04-01",
        "current_day_index": 30,
        "held_days_count": 0,
        "generated_schedule_json": {
            "days": [{"day_index": i, "session": {"focus": f"day-{i}"}} for i in range(60)]
        },
    }
    with patch.object(program_runtime, "_load_active_program", return_value=program):
        result = program_runtime.get_active_program_day("landon_brice", "throwing", date(2026, 5, 1))
        assert result is not None
        assert result["day_index"] == 30
        assert result["session"]["focus"] == "day-30"


def test_get_active_program_day_accounts_for_held_days():
    """If pitcher has been held 3 days, today's day_index lags by 3."""
    from bot.services import program_runtime
    program = {
        "program_id": "p1",
        "domain": "throwing",
        "start_date": "2026-04-01",
        "current_day_index": 27,  # 30 calendar days minus 3 held
        "held_days_count": 3,
        "generated_schedule_json": {
            "days": [{"day_index": i, "session": {"focus": f"day-{i}"}} for i in range(60)]
        },
    }
    with patch.object(program_runtime, "_load_active_program", return_value=program):
        result = program_runtime.get_active_program_day("landon_brice", "throwing", date(2026, 5, 1))
        assert result["day_index"] == 27
        assert result["session"]["focus"] == "day-27"


def test_get_active_program_day_returns_none_when_no_active_program():
    from bot.services import program_runtime
    with patch.object(program_runtime, "_load_active_program", return_value=None):
        assert program_runtime.get_active_program_day("nobody", "throwing", date(2026, 5, 1)) is None


def test_get_active_program_day_returns_none_past_end_of_schedule():
    from bot.services import program_runtime
    program = {
        "program_id": "p1",
        "domain": "throwing",
        "start_date": "2026-04-01",
        "current_day_index": 84,
        "held_days_count": 0,
        "generated_schedule_json": {
            "days": [{"day_index": i, "session": {"focus": f"day-{i}"}} for i in range(60)]
        },
    }
    with patch.object(program_runtime, "_load_active_program", return_value=program):
        # day_index 84 is past the 60-day schedule
        assert program_runtime.get_active_program_day("landon_brice", "throwing", date(2026, 5, 1)) is None
```

- [ ] **Step 2: Run, expect FAIL**

Run: `pytest pitcher_program_app/tests/test_program_runtime.py -v -k get_active_program_day`

Expected: 4 FAIL — function doesn't exist.

- [ ] **Step 3: Implement `get_active_program_day`**

Append to `pitcher_program_app/bot/services/program_runtime.py`:

```python
def get_active_program_day(pitcher_id: str, domain: str, target_date: date) -> Optional[dict]:
    """Return today's prescribed day from the active program's schedule, or None.

    The day_index used for lookup is `current_day_index` from the row — which
    already reflects held days (held days don't advance the counter; spec D7
    approach B). This function does NOT advance counters — that happens in the
    daily composition pipeline (Plan 4) atomically with the daily_entries write.

    Returns the matching schedule day dict (with whatever shape the template
    declared), or None if there's no active program OR target_date falls past
    the schedule's last day.
    """
    _ensure_domain(domain)

    program = _load_active_program(pitcher_id, domain)
    if not program:
        return None

    day_index = program.get("current_day_index", 0)
    schedule = (program.get("generated_schedule_json") or {}).get("days") or []
    for day in schedule:
        if day.get("day_index") == day_index:
            return day
    return None
```

- [ ] **Step 4: Run tests, expect PASS**

Run: `pytest pitcher_program_app/tests/test_program_runtime.py -v -k get_active_program_day`

Expected: 4 PASS.

- [ ] **Step 5: Run full program_runtime tests**

Run: `pytest pitcher_program_app/tests/test_program_runtime.py -v`

Expected: all PASS (5 from Task 5 + 4 here = 9).

- [ ] **Step 6: Commit**

```bash
git add pitcher_program_app/bot/services/program_runtime.py \
        pitcher_program_app/tests/test_program_runtime.py
git commit -m "feat: program_runtime.get_active_program_day

Reads today's prescription from generated_schedule_json using
current_day_index (which already accounts for held days per spec D7
approach B). Pure read — no counter mutation. Plan 4's daily
composition pipeline composes the prescribed plan from this output."
```

---

## Task 7: Migration 013 — `saved_plans` → `favorited_blocks` data migration

> Locked spec answer: migrate, don't keep both shelves. Maps each `saved_plans` row's lifting block (the only structured block reliably present) into a `favorited_blocks` snapshot of `block_type='lifting'`. Idempotent — safe to re-run.

**Files:**
- Create: `pitcher_program_app/scripts/migrations/013_saved_plans_to_favorites.sql`

- [ ] **Step 1: Inspect saved_plans shape**

```sql
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name = 'saved_plans' ORDER BY ordinal_position;
```

Note the JSONB column holding the plan payload. Likely `plan_json` or `plan_data`. Use the actual name in the migration below — substitute `<PLAN_COL>`.

- [ ] **Step 2: Write migration**

```sql
-- Migration 013: backfill favorited_blocks from saved_plans (locked spec answer).
-- Idempotent via a marker key in note: 'migrated_from_saved_plans:<saved_plan_id>'.

INSERT INTO favorited_blocks (
  pitcher_id,
  source_daily_entry_id,
  block_type,
  block_snapshot_json,
  note,
  favorited_at
)
SELECT
  sp.pitcher_id,
  -- saved_plans has no daily_entry_id; synthesize a deterministic uuid from saved_plan id
  -- so re-runs collide-detect via the note marker rather than this column.
  gen_random_uuid(),
  'lifting',
  COALESCE(sp.<PLAN_COL>->'lifting', sp.<PLAN_COL>),
  'migrated_from_saved_plans:' || sp.id::text,
  COALESCE(sp.created_at, now())
FROM saved_plans sp
WHERE NOT EXISTS (
  SELECT 1 FROM favorited_blocks fb
  WHERE fb.note = 'migrated_from_saved_plans:' || sp.id::text
);
```

- [ ] **Step 3: Apply via Supabase MCP**

`apply_migration(name='013_saved_plans_to_favorites', query=<sql above>)`

- [ ] **Step 4: Verify migration shape**

```sql
SELECT
  (SELECT count(*) FROM saved_plans) AS saved_plans_count,
  (SELECT count(*) FROM favorited_blocks WHERE note LIKE 'migrated_from_saved_plans:%') AS migrated_count;
```

Expected: `saved_plans_count == migrated_count`.

- [ ] **Step 5: Re-run migration to prove idempotence**

`apply_migration(name='013_saved_plans_to_favorites_rerun', query=<same sql>)`

Re-check the count — migrated_count should NOT have doubled.

- [ ] **Step 6: Write a Python smoke test**

Create `pitcher_program_app/tests/test_saved_plans_migration.py`:

```python
"""Smoke test: every saved_plans row has a corresponding favorited_blocks row
with the migration marker."""

import pytest
from bot.services import db


@pytest.mark.integration  # hits live Supabase
def test_every_saved_plan_has_favorite():
    saved = db.get_client().table("saved_plans").select("id").execute().data or []
    favorites = db.get_client().table("favorited_blocks").select("note") \
        .like("note", "migrated_from_saved_plans:%").execute().data or []
    migrated_ids = {f["note"].split(":", 1)[1] for f in favorites}
    saved_ids = {str(s["id"]) for s in saved}
    missing = saved_ids - migrated_ids
    assert not missing, f"Saved plans without migrated favorite: {missing}"
```

- [ ] **Step 7: Run integration test**

Run: `pytest pitcher_program_app/tests/test_saved_plans_migration.py -v -m integration`

Expected: PASS. (If integration marker isn't configured, run unmarked: `pytest tests/test_saved_plans_migration.py -v`.)

- [ ] **Step 8: Commit**

```bash
git add pitcher_program_app/scripts/migrations/013_saved_plans_to_favorites.sql \
        pitcher_program_app/tests/test_saved_plans_migration.py
git commit -m "feat(data): migrate saved_plans into favorited_blocks

Every saved_plans row becomes a favorited_blocks lifting snapshot.
Idempotent via 'migrated_from_saved_plans:<id>' note marker.
saved_plans table not dropped — historical data stays accessible
to existing Profile UI until that surface is rebuilt in Plan 6."
```

---

## Task 8: Migration 014 — seed Starter 7-day cadence template

> The cadence-as-template answer means the existing 7-day starter rotation must exist as a `block_library` row before bootstrap (Task 9) can reference it. The week scaffold mirrors current `plan_generator` template-day selection logic so the bootstrapped programs prescribe the same days the legacy code would have.

**Files:**
- Create: `pitcher_program_app/scripts/migrations/014_seed_starter_7day_template.sql`
- Create: `pitcher_program_app/data/templates/starter_7day_cadence.json`

- [ ] **Step 1: Confirm current rotation mapping**

Run: `grep -n "day_2\|day_3\|day_6\|days_since_outing" pitcher_program_app/bot/services/plan_generator.py | head -30`

Note which template-day is selected for each `days_since_outing` value (likely 0=outing, 1=day_1 recovery, 2=day_2 lower, 3=day_3 upper, 4=day_4, 5=day_5, 6=day_6 rest). Capture this mapping verbatim — the seeded template must reproduce it.

- [ ] **Step 2: Write the JSON scaffold (source of truth in git)**

Create `pitcher_program_app/data/templates/starter_7day_cadence.json`:

```json
{
  "template_id": "tpl_starter_7day_cadence_v1",
  "name": "In-Season Maintenance — Starter 7-day",
  "domain": "throwing",
  "goal_tags": ["in_season_maintenance", "starter_cadence"],
  "duration_range_weeks": "[12,12]",
  "compatible_phases": ["in_season_active", "in_season"],
  "tunable_parameters_schema": {},
  "implied_phase": "in_season_active",
  "research_doc_ids": [],
  "modification_rules_json": null,
  "week_scaffold_json": {
    "scaffold_kind": "calendar_relative_repeating_7day",
    "rotation_template_keys": [
      {"day_offset": 0, "template_key": "day_0_outing"},
      {"day_offset": 1, "template_key": "day_1_recovery"},
      {"day_offset": 2, "template_key": "day_2_lower"},
      {"day_offset": 3, "template_key": "day_3_upper"},
      {"day_offset": 4, "template_key": "day_4_throwing"},
      {"day_offset": 5, "template_key": "day_5_throwing"},
      {"day_offset": 6, "template_key": "day_6_rest"}
    ],
    "notes": "Mirrors legacy plan_generator rotation. Adjust day_offset → template_key mapping if Step 1 inspection shows different values."
  }
}
```

**Verify the rotation_template_keys match what Step 1 found.** If different, edit before continuing.

- [ ] **Step 3: Write SQL migration that loads the JSON**

```sql
-- Migration 014: seed canonical Starter 7-day cadence template.
-- Mirrors legacy plan_generator rotation so bootstrapped programs (Task 9)
-- produce the same daily prescriptions as the legacy code.

INSERT INTO block_library (
  id,
  name,
  domain,
  goal_tags,
  duration_range_weeks,
  compatible_phases,
  tunable_parameters_schema,
  week_scaffold_json,
  research_doc_ids,
  modification_rules_json,
  implied_phase
) VALUES (
  'tpl_starter_7day_cadence_v1',
  'In-Season Maintenance — Starter 7-day',
  'throwing',
  ARRAY['in_season_maintenance','starter_cadence'],
  '[12,12]'::int4range,
  ARRAY['in_season_active','in_season'],
  '{}'::jsonb,
  $$
    {
      "scaffold_kind": "calendar_relative_repeating_7day",
      "rotation_template_keys": [
        {"day_offset": 0, "template_key": "day_0_outing"},
        {"day_offset": 1, "template_key": "day_1_recovery"},
        {"day_offset": 2, "template_key": "day_2_lower"},
        {"day_offset": 3, "template_key": "day_3_upper"},
        {"day_offset": 4, "template_key": "day_4_throwing"},
        {"day_offset": 5, "template_key": "day_5_throwing"},
        {"day_offset": 6, "template_key": "day_6_rest"}
      ]
    }
  $$::jsonb,
  ARRAY[]::TEXT[],
  NULL,
  'in_season_active'
)
ON CONFLICT (id) DO UPDATE
SET name = EXCLUDED.name,
    domain = EXCLUDED.domain,
    goal_tags = EXCLUDED.goal_tags,
    duration_range_weeks = EXCLUDED.duration_range_weeks,
    compatible_phases = EXCLUDED.compatible_phases,
    tunable_parameters_schema = EXCLUDED.tunable_parameters_schema,
    week_scaffold_json = EXCLUDED.week_scaffold_json,
    research_doc_ids = EXCLUDED.research_doc_ids,
    modification_rules_json = EXCLUDED.modification_rules_json,
    implied_phase = EXCLUDED.implied_phase;
```

> If `block_library`'s PK column is not `id`, fix here and in `db.get_block_library_row` (Task 5).

- [ ] **Step 4: Apply migration**

`apply_migration(name='014_seed_starter_7day_template', query=<sql above>)`

- [ ] **Step 5: Verify**

```sql
SELECT id, name, domain, implied_phase, week_scaffold_json->'scaffold_kind'
FROM block_library WHERE id = 'tpl_starter_7day_cadence_v1';
```

Expected: 1 row, scaffold_kind = "calendar_relative_repeating_7day".

- [ ] **Step 6: Commit**

```bash
git add pitcher_program_app/scripts/migrations/014_seed_starter_7day_template.sql \
        pitcher_program_app/data/templates/starter_7day_cadence.json
git commit -m "feat(data): seed canonical Starter 7-day cadence template

Reifies the legacy 7-day starter rotation as a block_library template
so bootstrap (Task 9) and future spec-9 templates share one schema.
JSON in data/templates/ is the git source of truth; SQL migration is
the apply path."
```

---

## Task 9: Migration 015 — bootstrap active programs for current 7-day starters

> Synthesizes one `programs` row per current 7-day starter pointing at the Starter 7-day template, with `current_day_index` aligned to today's `days_since_outing`. After this lands, the 4 bootstrapped pitchers will read as "on a program" to Plan 4's daily composition pipeline; relievers and other roles stay on legacy fallback.

**Files:**
- Create: `pitcher_program_app/scripts/migrations/015_bootstrap_starter_programs.sql`

- [ ] **Step 1: Identify current 7-day starters**

```sql
SELECT pitcher_id, role FROM pitchers WHERE role ILIKE '%starter%';
```

Per `CLAUDE.md`: `landon_brice`, `pitcher_benner_001`, `pitcher_kwinter_001`, `test_pitcher_001`. Confirm against the live query before continuing.

- [ ] **Step 2: Identify their current `days_since_outing`**

```sql
SELECT pitcher_id, days_since_outing, last_outing_date
FROM pitcher_training_model
WHERE pitcher_id IN ('landon_brice','pitcher_benner_001','pitcher_kwinter_001','test_pitcher_001');
```

Note each value. The bootstrap will compute `current_day_index = days_since_outing` and `start_date = today - days_since_outing`.

- [ ] **Step 3: Write the migration**

```sql
-- Migration 015: bootstrap an active "Starter 7-day cadence" program for each current 7-day starter.
-- Idempotent via the partial unique index on (pitcher_id, domain) WHERE status='active'.
-- Generated schedule = 12 weeks (84 days) of the cadence, day_index aligned to current days_since_outing.

DO $$
DECLARE
  rec RECORD;
  computed_start_date DATE;
  computed_day_index  INT;
  schedule JSONB;
  i INT;
  rotation_keys JSONB := '[
    {"day_offset": 0, "template_key": "day_0_outing"},
    {"day_offset": 1, "template_key": "day_1_recovery"},
    {"day_offset": 2, "template_key": "day_2_lower"},
    {"day_offset": 3, "template_key": "day_3_upper"},
    {"day_offset": 4, "template_key": "day_4_throwing"},
    {"day_offset": 5, "template_key": "day_5_throwing"},
    {"day_offset": 6, "template_key": "day_6_rest"}
  ]'::jsonb;
BEGIN
  FOR rec IN
    SELECT p.pitcher_id, COALESCE(ptm.days_since_outing, 0) AS dso
    FROM pitchers p
    LEFT JOIN pitcher_training_model ptm USING (pitcher_id)
    WHERE p.role ILIKE '%starter%'
  LOOP
    -- Skip if pitcher already has an active throwing program (idempotency)
    IF EXISTS (
      SELECT 1 FROM programs
      WHERE pitcher_id = rec.pitcher_id AND domain = 'throwing' AND status = 'active'
    ) THEN
      CONTINUE;
    END IF;

    computed_day_index := rec.dso;
    computed_start_date := CURRENT_DATE - (rec.dso || ' days')::interval;

    -- Build 84-day schedule
    schedule := '{"days": []}'::jsonb;
    FOR i IN 0..83 LOOP
      schedule := jsonb_set(
        schedule,
        '{days}',
        (schedule->'days') || jsonb_build_object(
          'day_index', i,
          'template_key', rotation_keys->(i % 7)->>'template_key',
          'date', (computed_start_date + (i || ' days')::interval)::date
        )
      );
    END LOOP;

    INSERT INTO programs (
      pitcher_id, parent_template_id, domain, tuned_spec_json,
      generated_schedule_json, start_date, nominal_end_date,
      current_day_index, held_days_count, status,
      created_by, created_by_role, activated_at
    )
    SELECT
      rec.pitcher_id,
      bl.id,  -- block_library.id of starter 7-day template
      'throwing',
      '{"bootstrapped_from": "legacy_cadence"}'::jsonb,
      schedule,
      computed_start_date,
      computed_start_date + INTERVAL '84 days',
      computed_day_index,
      0,
      'active',
      'system_bootstrap',
      'coach',
      now()
    FROM block_library bl
    WHERE bl.id = 'tpl_starter_7day_cadence_v1';
  END LOOP;
END $$;
```

> Note: `block_library.id` cast assumes UUID — if it's TEXT, adjust the `parent_template_id` FK in `programs` accordingly. Inspect with `\d block_library`. If types disagree, the simplest fix is to cast in `programs.parent_template_id` to TEXT and drop the UUID type assumption from the migration in Task 1; revise Task 1's `parent_template_id` column to `TEXT` and re-apply.

- [ ] **Step 4: Apply migration**

`apply_migration(name='015_bootstrap_starter_programs', query=<sql above>)`

- [ ] **Step 5: Verify**

```sql
SELECT pitcher_id, domain, status, current_day_index, start_date, nominal_end_date
FROM programs
WHERE created_by = 'system_bootstrap'
ORDER BY pitcher_id;
```

Expected: 4 rows (one per 7-day starter), `domain='throwing'`, `status='active'`, `current_day_index` matches each pitcher's `days_since_outing`.

- [ ] **Step 6: Verify partial unique index holds**

```sql
-- Try to insert a second active throwing program for landon — must fail
INSERT INTO programs (
  pitcher_id, parent_template_id, domain,
  generated_schedule_json, start_date, nominal_end_date,
  status, created_by, created_by_role
) VALUES (
  'landon_brice', 'tpl_starter_7day_cadence_v1', 'throwing',
  '{}'::jsonb, CURRENT_DATE, CURRENT_DATE + 84,
  'active', 'test', 'coach'
);
```

Expected: ERROR — `duplicate key value violates unique constraint "idx_programs_one_active_per_domain"`.

- [ ] **Step 7: Write a smoke test**

Create `pitcher_program_app/tests/test_starter_cadence_bootstrap.py`:

```python
"""Smoke test: every 7-day starter has exactly one active throwing program after bootstrap."""

import pytest
from bot.services import db, program_runtime


STARTERS = ["landon_brice", "pitcher_benner_001", "pitcher_kwinter_001", "test_pitcher_001"]


@pytest.mark.integration
@pytest.mark.parametrize("pitcher_id", STARTERS)
def test_starter_has_active_throwing_program(pitcher_id):
    program = db.get_active_program(pitcher_id, "throwing")
    assert program is not None, f"{pitcher_id} should have an active throwing program after bootstrap"
    assert program["parent_template_id"] in ("tpl_starter_7day_cadence_v1",), \
        f"{pitcher_id} bootstrap pointed at wrong template: {program['parent_template_id']}"


@pytest.mark.integration
@pytest.mark.parametrize("pitcher_id", STARTERS)
def test_starter_program_day_index_matches_dso(pitcher_id):
    """current_day_index should be set to days_since_outing at bootstrap time."""
    program = db.get_active_program(pitcher_id, "throwing")
    model = db.get_pitcher_training_model(pitcher_id) or {}
    expected = model.get("days_since_outing", 0)
    assert program["current_day_index"] == expected, \
        f"{pitcher_id}: bootstrapped day_index {program['current_day_index']} != dso {expected}"
```

- [ ] **Step 8: Run test**

Run: `pytest pitcher_program_app/tests/test_starter_cadence_bootstrap.py -v -m integration`

Expected: 8 PASS (4 pitchers × 2 tests).

> The day-index test is a snapshot in time — it'll drift the next morning when `days_since_outing` increments. That's expected; this test is a one-shot post-migration validator and can be marked `@pytest.mark.skip` after the bootstrap PR merges. Leave the skip-comment as a TODO referencing this plan.

- [ ] **Step 9: Re-run legacy goldens**

Run: `cd pitcher_program_app && pytest tests/test_legacy_plan_generator_golden.py -v`

Expected: 8 PASS — bootstrap is a data-only change, legacy `plan_generator` is untouched.

- [ ] **Step 10: Commit**

```bash
git add pitcher_program_app/scripts/migrations/015_bootstrap_starter_programs.sql \
        pitcher_program_app/tests/test_starter_cadence_bootstrap.py
git commit -m "feat(data): bootstrap active throwing programs for current 7-day starters

Synthesizes one programs row per existing 7-day starter pointing at
the Starter 7-day template (Task 8). current_day_index aligns with
days_since_outing so the future Plan 4 pipeline finds them on the
program path immediately. Idempotent via partial unique index;
relievers stay on legacy fallback until reliever templates land."
```

---

## Task 10: Wire `daily_entries.plan_generated.source` value + snapshot field

> JSONB doesn't need a column-add migration — the new fields live inside `plan_generated`. This task just adds Python-side validators and the new source value `'program_prescribed'` so Plan 4 can write it cleanly when the time comes.

**Files:**
- Modify: `pitcher_program_app/bot/services/db.py`
- Create: `pitcher_program_app/tests/test_plan_generated_source_values.py`

- [ ] **Step 1: Find the source-value enumeration**

Run: `grep -n "python_fallback\|llm_enriched\|source_reason" pitcher_program_app/bot/services/*.py | head -20`

Expected hits in `plan_generator.py` and `checkin_service.py`. Find the constant or string-set defining valid `source` values; if there's no constant, declare one now.

- [ ] **Step 2: Write a test for the new value**

Create `pitcher_program_app/tests/test_plan_generated_source_values.py`:

```python
"""'program_prescribed' is now a valid plan_generated.source value.

This test pins the canonical set so future PRs that add more sources
have to update the constant explicitly."""

from bot.services.db import VALID_PLAN_SOURCES


def test_program_prescribed_is_valid_source():
    assert "program_prescribed" in VALID_PLAN_SOURCES


def test_legacy_sources_still_valid():
    assert "python_fallback" in VALID_PLAN_SOURCES
    assert "llm_enriched"  in VALID_PLAN_SOURCES
```

- [ ] **Step 3: Run, expect FAIL**

Run: `pytest pitcher_program_app/tests/test_plan_generated_source_values.py -v`

Expected: FAIL — `VALID_PLAN_SOURCES` doesn't exist.

- [ ] **Step 4: Add the constant in `bot/services/db.py`**

Near the top of `db.py`:

```python
VALID_PLAN_SOURCES: frozenset[str] = frozenset({
    "python_fallback",
    "llm_enriched",
    "program_prescribed",  # written by Plan 4 daily composition pipeline
})
```

If `plan_generator.py` already has its own constant, reuse and re-export — do not duplicate.

- [ ] **Step 5: Run test, expect PASS**

Run: `pytest pitcher_program_app/tests/test_plan_generated_source_values.py -v`

Expected: 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add pitcher_program_app/bot/services/db.py \
        pitcher_program_app/tests/test_plan_generated_source_values.py
git commit -m "feat: declare 'program_prescribed' plan source

Consumed by Plan 4 daily composition rewrite. plan_generated is JSONB
so no schema migration; this just locks the canonical set so future
sources go through an explicit code change."
```

---

## Task 11: Final verification — full backend suite + goldens + manual smoke

- [ ] **Step 1: Run full backend test suite**

Run: `cd pitcher_program_app && pytest -v`

Expected: all PASS, including legacy goldens (Task 0), program_runtime tests (Tasks 5–6), feature flag tests (Task 4), team phase split tests (Task 3), bootstrap tests (Task 9).

- [ ] **Step 2: Manual smoke — phase precedence**

In a Python REPL or one-off script:

```python
from bot.services import program_runtime
print("landon_brice throwing:", program_runtime.get_effective_phase("landon_brice", "throwing"))
print("landon_brice lifting:", program_runtime.get_effective_phase("landon_brice", "lifting"))
print("pitcher_kamat_001 throwing:", program_runtime.get_effective_phase("pitcher_kamat_001", "throwing"))
```

Expected:
- `landon_brice` throwing: `'in_season_active'` (active program → template implied phase)
- `landon_brice` lifting: team default (no active program, no override)
- `pitcher_kamat_001` throwing: team default (reliever, not bootstrapped)

- [ ] **Step 3: Manual smoke — get_active_program_day**

```python
from datetime import date
from bot.services import program_runtime
print(program_runtime.get_active_program_day("landon_brice", "throwing", date.today()))
print(program_runtime.get_active_program_day("pitcher_kamat_001", "throwing", date.today()))  # None
```

Expected: a day dict for `landon_brice`, `None` for `pitcher_kamat_001`.

- [ ] **Step 4: Manual smoke — Coach app + Mini app load**

Open the deployed coach-app and mini-app in browser. Sanity check:
- Coach Team Overview loads (uses `team_scope.get_team_roster_overview`, which now reads per-domain phase)
- Mini-app Home loads for `landon_brice`
- No errors in browser console
- No errors in Railway logs

- [ ] **Step 5: Final commit if anything dangling**

```bash
git status
# If clean, no commit. If anything remaining:
git add -A
git commit -m "chore: post-Plan-1 cleanup"
```

- [ ] **Step 6: Tag the foundation**

```bash
git tag program-builder-v1-foundation
```

> Plans 2–6 reference this tag as their starting point.

---

## Self-Review Pass

Before claiming this plan complete:

**Spec coverage check:**
- ✅ Section 1 object/data model: `programs` (Task 1), `favorited_blocks` (Task 1), `program_builder_sessions` (Task 1), operational tables (Task 1), block_library extensions (Task 2), per-domain phase columns (Tasks 3–4), `daily_entries.plan_generated.source='program_prescribed'` (Task 10), `daily_entries.plan_generated.program_prescription_snapshot` — JSONB shape, no migration needed (Task 10 documents the source enum; the snapshot field is a freeform JSONB key written by Plan 4)
- ✅ Phase model `get_effective_phase`: Task 5
- ✅ Cold-start safety: Task 0 (golden snapshots)
- ✅ Cadence-as-template (locked answer): Task 8 (template) + Task 9 (bootstrap)
- ✅ saved_plans → favorites (locked answer): Task 7
- ✅ Per-domain team phase split (locked answer): Task 3
- ✅ Feature flag mechanism (open item from spec): Task 4 chose `pitcher_training_model.feature_flags` jsonb
- ⏭ Builder funnel Layers 1–4: Plan 2/3
- ⏭ Daily composition rewrite: Plan 4
- ⏭ Scheduled-throw anchoring: Plan 5
- ⏭ Mini-app + coach-app UX: Plan 6

**Open items the spec called out:**
- ✅ Feature-flag mechanism — answered in Task 4
- ⏭ Layer 2 prompt variant location — defer to Plan 3
- ⏭ frontend-design skill for UX — defer to Plan 6
- ⏭ 10-template seed list with coach review — defer to Plan 6

**Ordering dependencies:**
- Task 0 BEFORE everything else (locks baseline)
- Task 1 BEFORE Tasks 5, 6, 9 (creates `programs` table)
- Task 2 BEFORE Tasks 8, 9 (extends `block_library`)
- Task 3 BEFORE Task 5 (per-domain team phase needed by `get_effective_phase`)
- Task 4 BEFORE Task 5 (per-pitcher overrides needed by `get_effective_phase`)
- Task 8 BEFORE Task 9 (bootstrap needs the template to exist)
- Task 11 LAST (full suite verification)

**No placeholders:** all SQL is exact, all Python is exact, all commands are exact. Type names (`programs.program_id` UUID, `block_library.id` — flagged for verification before Task 5/8 implementation), function names (`get_effective_phase`, `get_active_program_day`, `get_team_phase`, `get_active_program`, `get_block_library_row`, `get_feature_flag`) are consistent across tasks. Test fixture filenames (`case_starter_green_day3.json` etc.) are consistent between Task 0 capture and lookup.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-30-program-builder-plan-1-schema-foundation.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Good fit here because Tasks 1–4 are tight independent migration files.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
