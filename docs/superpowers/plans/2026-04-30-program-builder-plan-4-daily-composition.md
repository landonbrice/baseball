# Program Builder v1 — Plan 4: Daily Composition Pipeline Rewrite

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Insert program-aware composition into the daily-plan pipeline. When `pitcher_training_model.feature_flags.program_aware_plan_gen=true`, the pipeline composes today's plan from the active program's prescribed day, runs triage against the prescribed plan (not raw inputs), advances or holds the program counter atomically with the `daily_entries` write, and then runs the existing two-pass LLM enrichment unchanged. Pitchers without an active program OR with the flag off route through the **byte-identical legacy `plan_generator`** path. The only behavior change for un-flagged pitchers is logging.

**Architecture:** New module `bot/services/program_aware_planner.py` is the program-path entry point — `compose_prescribed_plan()` (pure), `apply_triage_to_program_plan()` (pure), and `advance_or_hold_counter()` (transactional). The check-in path in `bot/services/checkin_service.py` gains a feature-flag fork: if active program exists for any domain AND flag is on, take the program path; else legacy. The legacy `plan_generator.generate_plan` is touched only to add deterministic test seams needed by the goldens — no behavior change. New transactional helper `db.write_daily_entry_with_counter_advance()` wraps `daily_entries` upsert + `programs.current_day_index` update + `program_hold_events` insert in a single Supabase transaction (Postgres function or SQL).

**Tech Stack:** Python 3.11 / FastAPI / pytest / pytest-asyncio. Supabase Postgres. New tests use the same monkeypatch-the-data-layer pattern as Plans 2/3. Goldens use freezegun for time + JSON-fixture data layer per the Plan 1 deferred-task findings.

**Builds on Plans 1–3:**
- `pitcher_training_model.feature_flags.program_aware_plan_gen` (Plan 1 Task 4)
- `programs` table + partial unique index (Plan 1 Task 1)
- `program_runtime.get_active_program_day(pitcher_id, domain, target_date)` (Plan 1 Task 6)
- `db.get_active_program(pitcher_id, domain)` (Plan 1 Task 5)
- `db.get_feature_flag(pitcher_id, key)` (Plan 1 Task 4)
- `VALID_PLAN_SOURCES` includes `'program_prescribed'` (Plan 1 Task 10)
- 4 bootstrapped 7-day starters on Starter cadence template (Plan 1 Task 9)

---

## Risk profile (per spec R1)

This is the highest-risk change in the project since Phase 1 triage. Mitigations baked into this plan:
1. **Golden-snapshot harness lands FIRST** (Task 4.0). All subsequent tasks must keep the goldens green.
2. **Feature flag gates production rollout.** Default OFF. Enabled per-pitcher via `pitcher_training_model.feature_flags.program_aware_plan_gen=true`. Initial rollout: `landon_brice` only.
3. **Atomic counter updates.** No partial-write states.
4. **Legacy `plan_generator` is not modified for behavior** — only test seams (e.g., injectable `now_provider`). Goldens prove byte-identical output before/after.
5. **Pipeline failure → log + auto-fall-through to legacy.** Programs failing 3 days in a row alert the coach (24h grace) before auto-archiving (deferred to a follow-up; Plan 4 just logs and falls through, leaves auto-archive to a watcher job).

---

## File Structure

**New:**
- `pitcher_program_app/bot/services/program_aware_planner.py` — `compose_prescribed_plan`, `apply_triage_to_program_plan`, `advance_or_hold_counter`
- `pitcher_program_app/scripts/migrations/016_advance_program_counter_fn.sql` — Postgres function for atomic counter+entry+hold-event write
- `pitcher_program_app/tests/test_legacy_plan_generator_golden.py` — golden-snapshot harness (revived from Plan 1 deferred Task 0)
- `pitcher_program_app/tests/fixtures/legacy_plan_generator/` — JSON fixtures (data + time-frozen goldens)
- `pitcher_program_app/scripts/capture_plan_generator_goldens.py` — one-shot fixture capture script
- `pitcher_program_app/tests/test_program_aware_planner.py`
- `pitcher_program_app/tests/test_checkin_service_program_path.py`

**Modified:**
- `pitcher_program_app/bot/services/plan_generator.py` — add deterministic test seams (`now_provider` arg, optional injected data-layer helpers); NO behavior change
- `pitcher_program_app/bot/services/checkin_service.py` — feature-flag fork: program path vs legacy
- `pitcher_program_app/bot/services/db.py` — new `write_daily_entry_with_counter_advance` wrapper

---

## Task 4.0: Golden-snapshot harness for legacy `plan_generator`

> Carry forward the Plan 1 deferred-task findings:
> 1. `generate_plan` is `async`, signature `async def generate_plan(pitcher_id: str, triage_result: dict, checkin_inputs: dict = None, *, triage_rationale_detail=None) -> dict`
> 2. Sources of non-determinism inside the python_plan path: wall clock, recent-entries reads, exercise-history reads, team-block resolution, `compute_days_until_next_start`, mobility week-of-year, file I/O for research docs, emergency-counter writes
> 3. The fallback path to lock is the **timeout-fallback** branch, not a synthetic `force_python_only` (mock `call_llm`/`call_llm_reasoning` to raise)
> 4. `triage_result` real shape includes `protocol_adjustments.{arm_care_template, plyocare_allowed, throwing_adjustments}`
> 5. To make goldens viable: (a) mock LLM → TimeoutError, (b) freezegun, (c) JSON-fixture data layer, (d) expand triage fixtures with `protocol_adjustments`

> **Decision: do NOT add a `force_python_only` arg to `plan_generator.py`.** Instead, mock `call_llm`/`call_llm_reasoning` to raise. This locks real production fallback behavior and avoids touching the legacy code's branching shape.

**Files:**
- Create: `pitcher_program_app/tests/fixtures/legacy_plan_generator/`
- Create: `pitcher_program_app/scripts/capture_plan_generator_goldens.py`
- Create: `pitcher_program_app/tests/test_legacy_plan_generator_golden.py`

- [ ] **Step 1: Verify `freezegun` is available**

```bash
grep -n "freezegun" pitcher_program_app/requirements.txt 2>/dev/null
pip show freezegun 2>&1 | head -3
```

If not present, add `freezegun>=1.4` to `requirements.txt` AND `pip install freezegun`.

- [ ] **Step 2: Inspect the data-layer functions `plan_generator` actually calls**

Read `pitcher_program_app/bot/services/plan_generator.py` end to end. List every `db.` / `load_*` / `get_*` / file-I/O call inside `generate_plan` (the async one). The capture script + tests will mock all of them.

Example (will need adjustment based on actual code):
- `load_profile(pitcher_id)` or `db.get_pitcher(pitcher_id)`
- `db.get_recent_entries(pitcher_id, n=7)`
- `db.get_recent_exercise_ids(pitcher_id, days=7)`
- `get_rotation_day(profile)`
- `resolve_team_block(...)`, `compute_days_until_next_start(...)`
- `get_today_mobility()`
- `resolve_research(...)` and the `research_load_log` write inside it
- `record_and_check_emergency(...)`

Write the list to a comment block at the top of the capture script.

- [ ] **Step 3: Build per-pitcher data fixtures**

For each of 4 cases (start small):
1. `landon_brice_starter_green` — full profile, recent_entries showing arm_feel ≥7, exercise history with diversity
2. `landon_brice_starter_yellow_arm_feel` — same profile, recent_entries trending lower, triage_result with `flag_level=yellow` + `modification_flags` + `protocol_adjustments`
3. `pitcher_kamat_001_reliever_green` — reliever profile, no team block
4. `pitcher_benner_001_starter_red_critical` — flag=red, arm_feel ≤2, `arm_shutdown` modification

Capture real production data via Supabase MCP `execute_sql` for each pitcher's profile, recent entries, exercise history. Save as JSON files under `tests/fixtures/legacy_plan_generator/data/<case_name>.json` with this shape:

```json
{
  "case_name": "landon_brice_starter_green",
  "pitcher_id": "landon_brice",
  "frozen_time": "2026-05-01T08:00:00-05:00",
  "checkin_inputs": {"arm_feel": 8, "overall_energy": 7, "sleep_hours": 7.5},
  "triage_result": {
    "flag_level": "green",
    "modification_flags": [],
    "reasons": [],
    "protocol_adjustments": {
      "arm_care_template": "standard",
      "plyocare_allowed": true,
      "throwing_adjustments": {}
    }
  },
  "data_layer": {
    "profile": {...},
    "recent_entries": [...],
    "recent_exercise_ids": [...],
    "team_block": null,
    "days_until_next_start": null,
    "today_mobility": {...},
    "research_docs": [...]
  }
}
```

The exact `data_layer` shape mirrors what each mocked helper would return.

- [ ] **Step 4: Write the capture script**

Create `pitcher_program_app/scripts/capture_plan_generator_goldens.py`:

```python
"""One-shot capture of legacy plan_generator output for golden tests.

Run: PYTHONPATH=. python -m scripts.capture_plan_generator_goldens

For each fixture under tests/fixtures/legacy_plan_generator/data/:
  - freezegun the wall clock to fixture.frozen_time
  - mock call_llm + call_llm_reasoning to raise asyncio.TimeoutError
    (so the python-fallback branch executes)
  - mock every data-layer call from plan_generator.py to return fixture.data_layer.*
  - run generate_plan(pitcher_id, triage_result, checkin_inputs)
  - serialize the result to tests/fixtures/legacy_plan_generator/goldens/<case>.json

Re-run after intentional changes to plan_generator. Otherwise leave alone —
the whole point is to lock today's behavior.
"""
import asyncio
import json
from pathlib import Path
from unittest.mock import patch, AsyncMock

from freezegun import freeze_time

DATA_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "legacy_plan_generator" / "data"
GOLDENS_DIR = DATA_DIR.parent / "goldens"


async def _capture_one(fixture_path: Path):
    fixture = json.loads(fixture_path.read_text())
    case_name = fixture["case_name"]

    with freeze_time(fixture["frozen_time"]):
        # Mock all data-layer + LLM calls
        from bot.services import plan_generator, db, llm
        # ... extensive mocking; see Task 4.0 Step 5 for the full pattern

        result = await plan_generator.generate_plan(
            pitcher_id=fixture["pitcher_id"],
            triage_result=fixture["triage_result"],
            checkin_inputs=fixture["checkin_inputs"],
        )

    GOLDENS_DIR.mkdir(parents=True, exist_ok=True)
    out = GOLDENS_DIR / f"{case_name}.json"
    out.write_text(json.dumps(result, indent=2, default=str, sort_keys=True))
    print(f"Wrote {out}")


async def main():
    for fixture in sorted(DATA_DIR.glob("*.json")):
        await _capture_one(fixture)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 5: Build the mock layer**

Create `pitcher_program_app/tests/fixtures/legacy_plan_generator/_mocks.py` (shared between capture + test):

```python
"""Shared mock fixtures for legacy plan_generator goldens.

apply_legacy_mocks(fixture, monkeypatch) replaces every data-layer call
in plan_generator.py with deterministic data from the fixture, and mocks
the LLM helpers to raise TimeoutError so the python-fallback branch runs.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock


def apply_legacy_mocks(fixture: dict, monkeypatch):
    from bot.services import plan_generator, db, llm
    data = fixture["data_layer"]

    # --- LLM forced to fall through to python-fallback branch ---
    monkeypatch.setattr(llm, "call_llm",
                        AsyncMock(side_effect=asyncio.TimeoutError))
    monkeypatch.setattr(llm, "call_llm_reasoning",
                        AsyncMock(side_effect=asyncio.TimeoutError))

    # --- Data layer ---
    # Adjust each setattr call to match the actual function names found in Step 2.
    if "profile" in data:
        monkeypatch.setattr(db, "get_pitcher",
                            lambda pid: data["profile"])
    if "recent_entries" in data:
        monkeypatch.setattr(db, "get_recent_entries",
                            lambda pid, n=7: data["recent_entries"])
    if "recent_exercise_ids" in data:
        monkeypatch.setattr(db, "get_recent_exercise_ids",
                            lambda pid, days=7: data["recent_exercise_ids"])
    if "team_block" in data:
        # If plan_generator imports resolve_team_block from a service module, patch there.
        # Adjust attribute path based on Step 2 findings.
        pass
    # ... etc for each function in the Step 2 list

    # --- Suppress writes ---
    monkeypatch.setattr(db, "record_and_check_emergency",
                        lambda *a, **kw: None)
    # research_load_log writes inside resolve_research:
    monkeypatch.setattr(db, "log_research_load",
                        lambda *a, **kw: None)
```

> **Implementer note:** This is the most labor-intensive part of Task 4.0. Spend the time to enumerate every data-layer function actually called and patch all of them. If you find a call you can't easily mock (e.g., a deeply imported helper), surface it as a finding — we may need to push a `from bot.services import x` indirection seam into `plan_generator.py` to make it patchable. That's an acceptable Task 4.0 deliverable.

- [ ] **Step 6: Run the capture script against current main**

```bash
cd /Users/landonprojects/baseball/.claude/worktrees/epic-darwin-923895/pitcher_program_app
PYTHONPATH=. python -m scripts.capture_plan_generator_goldens
```

Expected: 4 golden JSON files written. Inspect one (`head -30 tests/fixtures/legacy_plan_generator/goldens/landon_brice_starter_green.json`) to confirm shape (has `exercise_blocks` or `lifting`, `warmup`, `day_focus`, etc.).

If a fixture errors during capture, note which one + why. Common causes:
- A data-layer function not yet mocked (extend `_mocks.py`)
- A required field missing from the fixture's `data_layer` (extend the fixture)
- The fixture's `triage_result.protocol_adjustments` shape doesn't match what `plan_generator` reads (extend the fixture)

- [ ] **Step 7: Write the golden test**

Create `pitcher_program_app/tests/test_legacy_plan_generator_golden.py`:

```python
"""Golden-snapshot lockdown for legacy plan_generator.

These tests assert that the python-fallback branch produces byte-identical
output for representative cases. Plan 4+ depend on this: cold-start pitchers
(no active program OR feature flag off) must continue to get exactly today's
plans.

If a test fails, do NOT regenerate the fixture unless the change is intentional
and called out in the PR description. Regenerate via:
  PYTHONPATH=. python -m scripts.capture_plan_generator_goldens
"""
import asyncio
import json
from pathlib import Path

import pytest
from freezegun import freeze_time

from bot.services import plan_generator
from tests.fixtures.legacy_plan_generator._mocks import apply_legacy_mocks


DATA_DIR = Path(__file__).parent / "fixtures" / "legacy_plan_generator" / "data"
GOLDENS_DIR = DATA_DIR.parent / "goldens"


def _cases():
    return sorted(DATA_DIR.glob("*.json"))


@pytest.mark.asyncio
@pytest.mark.parametrize("fixture_path", _cases(), ids=lambda p: p.stem)
async def test_legacy_plan_generator_matches_golden(fixture_path, monkeypatch):
    fixture = json.loads(fixture_path.read_text())
    golden_path = GOLDENS_DIR / f"{fixture['case_name']}.json"
    if not golden_path.exists():
        pytest.skip(f"No golden captured for {fixture['case_name']}")
    expected = json.loads(golden_path.read_text())

    with freeze_time(fixture["frozen_time"]):
        apply_legacy_mocks(fixture, monkeypatch)
        actual = await plan_generator.generate_plan(
            pitcher_id=fixture["pitcher_id"],
            triage_result=fixture["triage_result"],
            checkin_inputs=fixture["checkin_inputs"],
        )

    actual_json = json.dumps(actual, sort_keys=True, default=str)
    expected_json = json.dumps(expected, sort_keys=True, default=str)
    assert actual_json == expected_json, (
        f"Plan output drifted for {fixture['case_name']}.\n"
        "If intentional, regenerate via:\n"
        "  PYTHONPATH=. python -m scripts.capture_plan_generator_goldens"
    )
```

- [ ] **Step 8: Run goldens, expect PASS**

```bash
cd /Users/landonprojects/baseball/.claude/worktrees/epic-darwin-923895/pitcher_program_app
PYTHONPATH=. pytest tests/test_legacy_plan_generator_golden.py -v
```

Expected: 4 PASS. If any fail, the capture and the test are diverging — most likely a data-layer mock that wasn't applied identically in both. Investigate.

- [ ] **Step 9: Commit**

```bash
cd /Users/landonprojects/baseball/.claude/worktrees/epic-darwin-923895
git add pitcher_program_app/tests/test_legacy_plan_generator_golden.py \
        pitcher_program_app/tests/fixtures/legacy_plan_generator/ \
        pitcher_program_app/scripts/capture_plan_generator_goldens.py \
        pitcher_program_app/requirements.txt
git commit -m "test: golden-snapshot lockdown for legacy plan_generator

Captures byte-exact python-fallback-branch output for 4 representative
cases (starter green/yellow/red, reliever green) using freezegun + a
mocked data layer + LLM mocked to TimeoutError. Plan 4+ depend on this
to claim no behavior change for cold-start pitchers."
```

---

## Task 4.1: `program_aware_planner.compose_prescribed_plan` (pure)

**Files:**
- Create: `pitcher_program_app/bot/services/program_aware_planner.py`
- Create: `pitcher_program_app/tests/test_program_aware_planner.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for program_aware_planner.compose_prescribed_plan (Plan 4 Task 4.1).

Composes today's prescribed plan from the active program(s)' prescribed days.
Pure function — never calls the LLM or DB; takes throwing_rx + lifting_rx +
profile as inputs.
"""
from datetime import date


def test_compose_with_throwing_and_lifting():
    from bot.services import program_aware_planner as pap
    throwing_rx = {"day_index": 3, "template_key": "day_3", "session": {"focus": "upper"}}
    lifting_rx = {"day_index": 8, "template_key": "lower_strength"}
    profile = {"pitcher_id": "landon_brice"}
    plan = pap.compose_prescribed_plan(throwing_rx, lifting_rx, profile, target_date=date(2026, 5, 1))
    assert plan["throwing"] is not None
    assert plan["lifting"] is not None
    assert plan["throwing"]["template_key"] == "day_3"
    assert plan["lifting"]["template_key"] == "lower_strength"
    assert plan["source"] == "program_prescribed"


def test_compose_with_only_throwing():
    from bot.services import program_aware_planner as pap
    throwing_rx = {"day_index": 3, "template_key": "day_3"}
    plan = pap.compose_prescribed_plan(throwing_rx, None, {}, date(2026, 5, 1))
    assert plan["throwing"] is not None
    assert plan["lifting"] is None
    assert plan["source"] == "program_prescribed"


def test_compose_with_neither_returns_none():
    """Caller is responsible for cold-start fallback when both rx are None."""
    from bot.services import program_aware_planner as pap
    plan = pap.compose_prescribed_plan(None, None, {}, date(2026, 5, 1))
    assert plan is None


def test_compose_includes_target_date():
    from bot.services import program_aware_planner as pap
    plan = pap.compose_prescribed_plan({"day_index": 0}, None, {}, date(2026, 5, 1))
    assert plan["target_date"] == "2026-05-01"


def test_compose_preserves_program_metadata():
    from bot.services import program_aware_planner as pap
    throwing_rx = {"day_index": 3, "template_key": "day_3", "session": {"focus": "upper"}, "date": "2026-05-01"}
    plan = pap.compose_prescribed_plan(throwing_rx, None, {}, date(2026, 5, 1))
    # Snapshot is preserved verbatim under program_prescription_snapshot
    assert plan["program_prescription_snapshot"]["throwing"] == throwing_rx
```

- [ ] **Step 2: Run, expect FAIL**

```bash
PYTHONPATH=. pytest tests/test_program_aware_planner.py -v -k compose
```

- [ ] **Step 3: Implement `compose_prescribed_plan`**

```python
"""Plan 4: Program-aware daily-plan composition.

Three responsibilities:
  - compose_prescribed_plan: pure composition of throwing_rx + lifting_rx + profile
  - apply_triage_to_program_plan: pure adjustment of prescribed plan based on triage flag
  - advance_or_hold_counter: transactional counter update + hold event
"""
from __future__ import annotations

from datetime import date
from typing import Optional


def compose_prescribed_plan(
    throwing_rx: Optional[dict],
    lifting_rx: Optional[dict],
    profile: dict,
    target_date: date,
) -> Optional[dict]:
    """Compose today's prescribed plan from active program(s).

    Returns None when neither domain has an active program prescription
    (caller falls back to legacy plan_generator).
    """
    if throwing_rx is None and lifting_rx is None:
        return None
    return {
        "source": "program_prescribed",
        "target_date": target_date.isoformat(),
        "throwing": throwing_rx,
        "lifting": lifting_rx,
        "program_prescription_snapshot": {
            "throwing": throwing_rx,
            "lifting": lifting_rx,
        },
    }
```

- [ ] **Step 4: Run, expect PASS**

```bash
PYTHONPATH=. pytest tests/test_program_aware_planner.py -v -k compose
```

Expected: 5 PASS.

---

## Task 4.2: `apply_triage_to_program_plan`

> Implements spec D7 approach B: Yellow trims/adjusts; Red replaces with recovery; Critical Red shuts down. Yellow/Red/Critical Red return a flag indicating "should the counter advance?" — Green/Yellow advance, Red/Critical Red hold.

- [ ] **Step 1: Tests**

```python
def test_apply_triage_green_returns_unmodified_with_advance():
    from bot.services import program_aware_planner as pap
    prescribed = {"throwing": {"template_key": "day_3"}, "lifting": {"template_key": "lower"}}
    triage = {"flag_level": "green", "modification_flags": []}
    final, hold_event = pap.apply_triage_to_program_plan(prescribed, triage)
    assert final["triage_flag"] == "green"
    assert hold_event is None  # advance, no hold
    assert final["throwing"] == prescribed["throwing"]
    assert final["lifting"] == prescribed["lifting"]


def test_apply_triage_yellow_advances_with_modification_tags():
    from bot.services import program_aware_planner as pap
    prescribed = {"throwing": {"template_key": "day_3"}, "lifting": {"template_key": "lower"}}
    triage = {"flag_level": "yellow", "modification_flags": ["fatigue_general"]}
    final, hold_event = pap.apply_triage_to_program_plan(prescribed, triage)
    assert final["triage_flag"] == "yellow"
    assert hold_event is None
    assert final["modification_flags"] == ["fatigue_general"]


def test_apply_triage_red_holds_counter_and_replaces_throwing_with_recovery():
    from bot.services import program_aware_planner as pap
    prescribed = {"throwing": {"template_key": "day_3", "session": {"intensity": "high"}},
                  "lifting": {"template_key": "lower_strength"}}
    triage = {"flag_level": "red", "modification_flags": ["arm_protect"]}
    final, hold_event = pap.apply_triage_to_program_plan(prescribed, triage)
    assert final["triage_flag"] == "red"
    assert hold_event is not None
    assert hold_event["reason_code"] == "red"
    # Throwing is replaced with a recovery shape
    assert final["throwing"]["recovery_only"] is True
    # Lifting trimmed to light
    assert final["lifting"]["intensity"] == "light"


def test_apply_triage_critical_red_shutdown_and_alert():
    from bot.services import program_aware_planner as pap
    prescribed = {"throwing": {"template_key": "day_3"},
                  "lifting": {"template_key": "lower_strength"}}
    triage = {"flag_level": "red", "modification_flags": ["arm_shutdown"],
              "arm_feel": 2}
    final, hold_event = pap.apply_triage_to_program_plan(prescribed, triage)
    assert final["throwing"]["shutdown"] is True
    assert hold_event["reason_code"] == "critical_red"
    assert final["auto_alert_coach"] is True


def test_apply_triage_red_with_no_throwing_still_holds():
    """Lifting-only program in Red still pauses the lifting counter."""
    from bot.services import program_aware_planner as pap
    prescribed = {"throwing": None,
                  "lifting": {"template_key": "lower_strength"}}
    triage = {"flag_level": "red", "modification_flags": []}
    final, hold_event = pap.apply_triage_to_program_plan(prescribed, triage)
    assert hold_event is not None
    assert final["lifting"]["intensity"] == "light"
```

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: Implement**

```python
def apply_triage_to_program_plan(
    prescribed: dict,
    triage_result: dict,
) -> tuple[dict, Optional[dict]]:
    """Apply triage flag to a program-prescribed plan. Returns (final_plan, hold_event).

    hold_event is None when counter advances; populated dict when counter holds.
    """
    flag = (triage_result or {}).get("flag_level", "green")
    modification_flags = list((triage_result or {}).get("modification_flags") or [])
    arm_feel = (triage_result or {}).get("arm_feel")
    is_critical_red = flag == "red" and (
        "arm_shutdown" in modification_flags or (arm_feel is not None and arm_feel <= 2)
    )

    final = dict(prescribed or {})
    final["triage_flag"] = flag
    final["modification_flags"] = modification_flags
    hold_event: Optional[dict] = None

    if flag == "green":
        return final, None

    if flag == "yellow":
        # Modification tags carried; downstream exercise_pool applies YELLOW logic.
        return final, None

    # red / critical_red
    if final.get("throwing"):
        if is_critical_red:
            final["throwing"] = {"shutdown": True, "original": prescribed.get("throwing")}
            final["auto_alert_coach"] = True
        else:
            final["throwing"] = {"recovery_only": True, "original": prescribed.get("throwing")}
    if final.get("lifting"):
        final["lifting"] = {**final["lifting"], "intensity": "light"}

    hold_event = {
        "reason_code": "critical_red" if is_critical_red else "red",
        "triage_result": triage_result,
    }
    return final, hold_event
```

- [ ] **Step 4: Run, expect PASS**

Expected: 5 PASS.

---

## Task 4.3: Migration 016 — atomic counter-advance Postgres function

**Files:**
- Create: `pitcher_program_app/scripts/migrations/016_advance_program_counter_fn.sql`

- [ ] **Step 1: Write the function**

```sql
-- Migration 016: Postgres function for atomic program counter advance + hold-event log.
--
-- Called from db.write_daily_entry_with_counter_advance after the daily_entries
-- upsert. Handles two cases per (program_id, hold_event) pair:
--   - hold_event is NULL: advance current_day_index by 1, recompute nominal_end_date
--   - hold_event is provided: insert into program_hold_events, increment held_days_count,
--     do NOT advance current_day_index, recompute nominal_end_date
--
-- All within a single transaction (the SQL function is implicitly transactional).
--
-- Idempotency: program_hold_events has UNIQUE (program_id, hold_date), so re-runs
-- for the same date will fail loudly rather than double-incrementing.

CREATE OR REPLACE FUNCTION advance_program_counter(
  p_program_id UUID,
  p_hold_event JSONB,  -- NULL when advancing; {reason_code, triage_result, hold_date} when holding
  p_event_date DATE
) RETURNS VOID AS $$
DECLARE
  v_held_days INT;
  v_current_idx INT;
BEGIN
  IF p_hold_event IS NULL THEN
    -- Advance counter
    UPDATE programs
    SET current_day_index = current_day_index + 1
    WHERE program_id = p_program_id;
  ELSE
    -- Hold: insert event, increment held_days_count
    INSERT INTO program_hold_events (program_id, hold_date, triage_result, reason_code)
    VALUES (
      p_program_id,
      p_event_date,
      p_hold_event->'triage_result',
      p_hold_event->>'reason_code'
    );

    UPDATE programs
    SET held_days_count = held_days_count + 1,
        nominal_end_date = nominal_end_date + INTERVAL '1 day'
    WHERE program_id = p_program_id;
  END IF;
END;
$$ LANGUAGE plpgsql;
```

- [ ] **Step 2: Apply via Supabase MCP**

`apply_migration(name='016_advance_program_counter_fn', query=<sql>)`.

- [ ] **Step 3: Verify**

```sql
SELECT proname, pg_get_function_arguments(oid)
FROM pg_proc WHERE proname = 'advance_program_counter';
```

Expected: 1 row.

- [ ] **Step 4: Smoke test**

Pick a test program (NOT a bootstrapped one), or temporarily insert one. Call the function with NULL hold_event, verify `current_day_index` increments. Call with a hold_event, verify `held_days_count` increments + a row appears in `program_hold_events` + `nominal_end_date` advances by 1 day. Clean up.

- [ ] **Step 5: Commit**

```bash
git add pitcher_program_app/scripts/migrations/016_advance_program_counter_fn.sql
git commit -m "feat(schema): advance_program_counter() atomic Postgres function

Single-transaction counter advance OR hold-event insert (mutually
exclusive). UNIQUE (program_id, hold_date) prevents double-write
on the same date. Consumed by db.write_daily_entry_with_counter_advance."
```

---

## Task 4.4: `db.write_daily_entry_with_counter_advance`

**Files:**
- Modify: `pitcher_program_app/bot/services/db.py`
- Create: `pitcher_program_app/tests/test_db_atomic_write.py`

- [ ] **Step 1: Tests**

```python
"""Tests for db.write_daily_entry_with_counter_advance.

Wraps daily_entries upsert + counter advance/hold + hold_event insert in
a single Supabase transaction. We test the orchestration shape (correct
args passed to the underlying Postgres function), not the SQL itself.
"""
from unittest.mock import patch, MagicMock
from datetime import date


def test_advance_path_no_hold_event():
    from bot.services import db
    fake_client = MagicMock()
    with patch.object(db, "get_client", return_value=fake_client):
        db.write_daily_entry_with_counter_advance(
            entry={"pitcher_id": "landon_brice", "date": "2026-05-01"},
            program_id="prog-1",
            hold_event=None,
            event_date=date(2026, 5, 1),
        )
    # daily_entries upsert
    fake_client.table.assert_any_call("daily_entries")
    # advance_program_counter RPC
    fake_client.rpc.assert_called_with("advance_program_counter", {
        "p_program_id": "prog-1",
        "p_hold_event": None,
        "p_event_date": "2026-05-01",
    })


def test_hold_path_passes_hold_event_jsonb():
    from bot.services import db
    fake_client = MagicMock()
    with patch.object(db, "get_client", return_value=fake_client):
        db.write_daily_entry_with_counter_advance(
            entry={"pitcher_id": "landon_brice", "date": "2026-05-01"},
            program_id="prog-1",
            hold_event={"reason_code": "red", "triage_result": {"flag_level": "red"}},
            event_date=date(2026, 5, 1),
        )
    fake_client.rpc.assert_called_with("advance_program_counter", {
        "p_program_id": "prog-1",
        "p_hold_event": {"reason_code": "red", "triage_result": {"flag_level": "red"}},
        "p_event_date": "2026-05-01",
    })


def test_no_program_id_skips_counter_call():
    from bot.services import db
    fake_client = MagicMock()
    with patch.object(db, "get_client", return_value=fake_client):
        db.write_daily_entry_with_counter_advance(
            entry={"pitcher_id": "landon_brice", "date": "2026-05-01"},
            program_id=None,
            hold_event=None,
            event_date=date(2026, 5, 1),
        )
    fake_client.table.assert_called_with("daily_entries")
    fake_client.rpc.assert_not_called()
```

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: Implement**

```python
def write_daily_entry_with_counter_advance(
    entry: dict,
    program_id: str | None,
    hold_event: dict | None,
    event_date: "date",
) -> None:
    """Upsert a daily_entries row + atomically advance/hold the program counter.

    When program_id is None, only the daily_entries upsert runs (cold-start path
    with feature flag on but no active program — same end state as legacy).
    """
    client = get_client()
    # 1) daily_entries upsert (existing pattern; use _DAILY_ENTRY_COLUMNS whitelist)
    safe = {k: v for k, v in entry.items() if k in _DAILY_ENTRY_COLUMNS}
    client.table("daily_entries").upsert(safe, on_conflict="pitcher_id,date").execute()
    # 2) Atomic counter advance (single Postgres function call)
    if program_id is None:
        return
    client.rpc("advance_program_counter", {
        "p_program_id": program_id,
        "p_hold_event": hold_event,
        "p_event_date": event_date.isoformat(),
    }).execute()
```

> **Implementer note:** Pure two-step. NOT atomic across the two — the upsert and the rpc are separate Supabase calls. True atomicity requires both inside one transaction, which Supabase's REST client doesn't expose directly. v1 acceptable: if step 2 fails after step 1 succeeds, we have a daily_entry without a counter advance — log + alert + manual reconciliation. Document this limitation in the docstring + a test that asserts the call order.

- [ ] **Step 4: Run, expect PASS**

- [ ] **Step 5: Commit**

```bash
git add pitcher_program_app/bot/services/db.py \
        pitcher_program_app/tests/test_db_atomic_write.py
git commit -m "feat(db): write_daily_entry_with_counter_advance helper

Two-step write: daily_entries upsert + advance_program_counter RPC.
NOT cross-step atomic (Supabase REST limitation); program_id=None
path skips the RPC for cold-start parity. v2 follow-up: explore
Postgres function that takes the entry payload + does both steps."
```

---

## Task 4.5: Wire program-aware path into `checkin_service.py`

> The check-in pipeline gains a fork: if `feature_flags.program_aware_plan_gen=true` AND any active program exists, take the program path. Else, legacy. The fork happens AFTER triage runs.

**Files:**
- Modify: `pitcher_program_app/bot/services/checkin_service.py`
- Create: `pitcher_program_app/tests/test_checkin_service_program_path.py`

- [ ] **Step 1: Tests**

```python
"""Tests for the program-aware fork in checkin_service.process_checkin.

Verifies:
- Flag off → legacy path (existing behavior, goldens still pass)
- Flag on + active program → program path: compose, triage-adjust, write atomic
- Flag on + no active program → legacy path (cold-start)
- Plan source tagged 'program_prescribed' on the program path
- Counter advances on green, holds on red
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import date


@pytest.mark.asyncio
async def test_flag_off_takes_legacy_path():
    from bot.services import checkin_service
    with patch.object(checkin_service, "_is_program_aware_enabled", return_value=False), \
         patch.object(checkin_service, "_legacy_plan_path", new=AsyncMock(return_value={"source": "python_fallback"})), \
         patch.object(checkin_service, "_program_aware_plan_path", new=AsyncMock()) as program_path:
        result = await checkin_service.process_checkin(
            pitcher_id="landon_brice",
            checkin_inputs={"arm_feel": 8},
        )
    assert result["source"] == "python_fallback"
    program_path.assert_not_called()


@pytest.mark.asyncio
async def test_flag_on_with_active_program_takes_program_path():
    from bot.services import checkin_service
    with patch.object(checkin_service, "_is_program_aware_enabled", return_value=True), \
         patch.object(checkin_service, "_has_any_active_program", return_value=True), \
         patch.object(checkin_service, "_program_aware_plan_path",
                      new=AsyncMock(return_value={"source": "program_prescribed"})), \
         patch.object(checkin_service, "_legacy_plan_path", new=AsyncMock()) as legacy:
        result = await checkin_service.process_checkin(
            pitcher_id="landon_brice",
            checkin_inputs={"arm_feel": 8},
        )
    assert result["source"] == "program_prescribed"
    legacy.assert_not_called()


@pytest.mark.asyncio
async def test_flag_on_without_active_program_takes_legacy_path():
    from bot.services import checkin_service
    with patch.object(checkin_service, "_is_program_aware_enabled", return_value=True), \
         patch.object(checkin_service, "_has_any_active_program", return_value=False), \
         patch.object(checkin_service, "_legacy_plan_path",
                      new=AsyncMock(return_value={"source": "python_fallback"})):
        result = await checkin_service.process_checkin(
            pitcher_id="landon_brice",
            checkin_inputs={"arm_feel": 8},
        )
    assert result["source"] == "python_fallback"


@pytest.mark.asyncio
async def test_program_path_logs_failure_and_falls_back_on_error():
    from bot.services import checkin_service
    with patch.object(checkin_service, "_is_program_aware_enabled", return_value=True), \
         patch.object(checkin_service, "_has_any_active_program", return_value=True), \
         patch.object(checkin_service, "_program_aware_plan_path",
                      new=AsyncMock(side_effect=RuntimeError("boom"))), \
         patch.object(checkin_service, "_legacy_plan_path",
                      new=AsyncMock(return_value={"source": "python_fallback"})), \
         patch.object(checkin_service, "_log_program_path_failure") as log:
        result = await checkin_service.process_checkin(
            pitcher_id="landon_brice",
            checkin_inputs={"arm_feel": 8},
        )
    assert result["source"] == "python_fallback"
    log.assert_called_once()
```

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: Inspect existing `process_checkin` shape**

Read `pitcher_program_app/bot/services/checkin_service.py`. Find the function the bot + API call. Note its signature, return shape, and where it currently calls `plan_generator.generate_plan` (or its equivalent).

- [ ] **Step 4: Add the fork**

Refactor minimally. Extract the existing legacy-call code into `_legacy_plan_path(pitcher_id, triage_result, checkin_inputs)`, add the helpers `_is_program_aware_enabled(pitcher_id)`, `_has_any_active_program(pitcher_id)`, `_program_aware_plan_path(pitcher_id, triage_result, checkin_inputs)`, `_log_program_path_failure(pitcher_id, exc)`. Wire them into `process_checkin`:

```python
async def process_checkin(pitcher_id, checkin_inputs, ...):
    # ... existing code that runs triage ...
    triage_result = await run_triage(...)

    if _is_program_aware_enabled(pitcher_id) and _has_any_active_program(pitcher_id):
        try:
            plan = await _program_aware_plan_path(pitcher_id, triage_result, checkin_inputs)
        except Exception as e:
            _log_program_path_failure(pitcher_id, e)
            plan = await _legacy_plan_path(pitcher_id, triage_result, checkin_inputs)
    else:
        plan = await _legacy_plan_path(pitcher_id, triage_result, checkin_inputs)

    # ... existing code that persists daily_entries ...
```

The new `_program_aware_plan_path`:
1. Reads active programs in both domains (`db.get_active_program(pitcher_id, 'throwing')`, lifting).
2. Calls `program_runtime.get_active_program_day(...)` for each.
3. Calls `program_aware_planner.compose_prescribed_plan(...)`. If None, raises (caller falls back to legacy).
4. Calls `program_aware_planner.apply_triage_to_program_plan(prescribed, triage_result)`.
5. Calls `_run_two_pass_llm_review(plan, profile, triage_result)` — same review the legacy path uses (extract this into a shared helper to avoid duplication, or call the existing `plan_generator` review function directly).
6. Returns the enriched plan.

Note the program counter advance happens in `_persist_daily_entry`, not here — keep `_program_aware_plan_path` pure-ish (just composition + LLM review).

- [ ] **Step 5: Wire counter advance into the persistence step**

Find the existing `db.upsert_daily_entry(...)` call. Replace with `db.write_daily_entry_with_counter_advance(...)` when on the program path, with the active program's `program_id` and the `hold_event` returned by `apply_triage_to_program_plan`.

- [ ] **Step 6: Run all tests**

```bash
PYTHONPATH=. pytest 2>&1 | tail -10
```

Expected: 402 (Plan 3 baseline) + 4 (Task 4.0 goldens) + 5 (Task 4.1) + 5 (Task 4.2) + 3 (Task 4.4) + 4 (Task 4.5) = 423 PASS. Existing tests unchanged; no regressions.

If goldens fail after this task, the legacy path was perturbed — investigate. The most likely cause is the refactor accidentally rerouting cold-start flow.

- [ ] **Step 7: Commit**

```bash
git add pitcher_program_app/bot/services/checkin_service.py \
        pitcher_program_app/bot/services/program_aware_planner.py \
        pitcher_program_app/tests/test_checkin_service_program_path.py
git commit -m "feat: program-aware fork in checkin_service.process_checkin

Behind feature flag pitcher_training_model.feature_flags.program_aware_plan_gen.
Flag off OR no active program → legacy path (byte-identical, goldens lock).
Flag on + active program → compose from program → triage-adjust → atomic
counter advance/hold + daily_entries upsert. Program-path failure logs +
auto-falls-through to legacy."
```

---

## Task 4.6: Enable feature flag for `landon_brice` only

**Files:** Supabase MCP only.

- [ ] **Step 1: Enable flag in production**

```sql
UPDATE pitcher_training_model
SET feature_flags = jsonb_set(
  COALESCE(feature_flags, '{}'::jsonb),
  '{program_aware_plan_gen}',
  'true'::jsonb
)
WHERE pitcher_id = 'landon_brice';
```

- [ ] **Step 2: Verify**

```sql
SELECT pitcher_id, feature_flags FROM pitcher_training_model WHERE pitcher_id = 'landon_brice';
```

Expected: `feature_flags = {"program_aware_plan_gen": true}`.

- [ ] **Step 3: Smoke test the live path**

The next time `landon_brice` checks in via Telegram or mini-app, confirm the daily entry has `plan_generated.source = 'program_prescribed'` and the program's `current_day_index` advanced (or held, on Red). Pull live data via Supabase MCP.

- [ ] **Step 4: No commit needed** — production-only data change.

---

## Task 4.7: Final verification + tag

- [ ] **Step 1: Full suite**

Expected ~423 PASS / 8 skipped / 0 failed. Goldens green.

- [ ] **Step 2: Update CLAUDE.md**

Append:

```markdown
| Plan 4 (PB) | Program Builder v1 — Daily Composition Pipeline Rewrite | 04-30 | Plan 4: program-aware fork in checkin_service. Behind pitcher_training_model.feature_flags.program_aware_plan_gen (initial rollout: landon_brice only). New module bot/services/program_aware_planner.py — compose_prescribed_plan + apply_triage_to_program_plan (B-mode counter pause on Red/Critical Red). New Postgres function advance_program_counter() for atomic counter+hold-event write. New helper db.write_daily_entry_with_counter_advance. Legacy plan_generator path locked via 4-case golden snapshots (test_legacy_plan_generator_golden.py + freezegun + mocked data layer + LLM→TimeoutError). 21 new tests. |
```

- [ ] **Step 3: Tag**

```bash
git tag program-builder-v1-daily-composition
```

- [ ] **Step 4: Commit doc updates + tag**

```bash
git add CLAUDE.md
git commit -m "docs(claude.md): record Program Builder v1 Plan 4 completion"
git tag program-builder-v1-daily-composition
```

## Self-Review

**Spec coverage (Plan 4 design spec Section 3):**
- ✅ build_daily_plan with throwing_rx + lifting_rx + compose_prescribed_plan: Task 4.1
- ✅ Triage interaction approach B (Yellow advances, Red holds, Critical Red shutdown+alert): Task 4.2
- ✅ Cold-start fallback (no active program → legacy): Task 4.5 fork
- ✅ Counter updates atomic with daily_entries write: Task 4.3 + 4.4
- ✅ daily_entries.plan_generated.source='program_prescribed': Task 4.1
- ✅ daily_entries.plan_generated.program_prescription_snapshot: Task 4.1
- ✅ Program lookup failure → fall through to legacy + log: Task 4.5
- ✅ Feature flag rollout (R1): Task 4.6
- ⏭ Programs failing 3 days in a row → coach alert + auto-archive: deferred (watcher job, separate plan)
- ⏭ Scheduled-throw anchoring: Plan 5

**Carry-overs:**
- `db.write_daily_entry_with_counter_advance` is two Supabase calls, not cross-step atomic. v2 should explore a Postgres function that takes the daily_entry payload too.
- Critical Red detection uses both `'arm_shutdown' in modification_flags` and `arm_feel ≤ 2`. The triage layer should produce one or the other consistently — verify in production telemetry.
- `_program_aware_plan_path` reuses the existing two-pass LLM review. If refactoring `plan_generator.py` to extract the review helper is too risky, just call `plan_generator.generate_plan` directly with a pre-composed plan as input — but that needs a parameter we don't have. Implementer should propose the cleanest refactor at execution time.
