# Program Builder v1 — Plan 2: Builder Funnel Backend (Layers 1, 3, 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Land the Backend half of the Program Builder funnel — Layer 1 (structured-input → candidate templates), Layer 3 (`generate_program` with hard validation invariants and retry-once fallback), Layer 4 (program lifecycle: draft / activate / archive). Layer 2 (Socratic interview) is mocked here as a stubbed pass-through and lands properly in Plan 3. UI lands in Plan 6 — this plan is API + service-layer only.

**Architecture:** Three new service modules — `program_builder.py` (Layer 1 candidate matching), `program_generator.py` (Layer 3 schedule generation + validation), `program_lifecycle.py` (Layer 4 draft/active/archive transactional state machine). Each has its own narrow responsibility and test file. New API endpoints on `api/routes.py` (pitcher-facing) and `api/coach_routes.py` (coach-facing) consume them. Existing `bot/services/program_runtime.py` (`get_active_program_day`, `get_effective_phase`) is consumed read-side; new code does not modify it. Layer 2 stub returns `chosen_template_id = candidates[0].block_template_id` and `tuned_spec = {}` so end-to-end flows can land before the LLM glue arrives in Plan 3. All endpoints gated behind a `program_builder_v1` feature flag at the route layer.

**Tech Stack:** Python 3.11 / FastAPI / Pydantic / pytest. Supabase Postgres via `supabase-py`. New services live in `pitcher_program_app/bot/services/`. Tests in `pitcher_program_app/tests/`. No frontend changes in this plan.

**Builds on Plan 1 (`program-builder-v1-foundation` tag):**
- `programs` table with `parent_template_id TEXT`, partial unique index on `(pitcher_id, domain) WHERE status='active'`
- `block_library` extended with `domain`, `goal_tags`, `duration_range_weeks`, `compatible_phases`, `tunable_parameters_schema`, `week_scaffold_json`, `research_doc_ids`, `implied_phase`
- `program_builder_sessions` table with `interview_mode`, `turns_jsonb`, `status` enum
- `program_generation_failures` table for retry telemetry
- `program_runtime.get_active_program_day` + `get_effective_phase`
- `db.get_active_program(pitcher_id, domain)` + `db.get_block_library_row(template_id)`
- `db.get_feature_flag(pitcher_id, key)` for scoped rollout

---

## File Structure

**New service modules:**
- `pitcher_program_app/bot/services/program_builder.py` — Layer 1 candidate matching from constraint envelope
- `pitcher_program_app/bot/services/program_generator.py` — Layer 3 schedule generation + validation invariants + retry-once
- `pitcher_program_app/bot/services/program_lifecycle.py` — Layer 4 draft/active/archive state machine, atomic with hold-event aware archive_reason

**Modified service modules:**
- `pitcher_program_app/bot/services/db.py` — new repository helpers: `create_program(...)`, `update_program_status(...)`, `list_programs_for_pitcher(...)`, `get_program(program_id)`, `create_builder_session(...)`, `update_builder_session(...)`, `get_builder_session(session_id)`, `record_generation_failure(...)`

**Modified API routes:**
- `pitcher_program_app/api/routes.py` — new pitcher-facing endpoints under `/api/programs/builder/*` and `/api/programs/{program_id}/*`
- `pitcher_program_app/api/coach_routes.py` — coach mirror endpoints under `/api/coach/programs/builder/*` (same handlers, different auth + interview_mode)

**New tests:**
- `pitcher_program_app/tests/test_program_builder_candidates.py` — Layer 1 matching logic
- `pitcher_program_app/tests/test_program_generator.py` — Layer 3 generation + validation invariants
- `pitcher_program_app/tests/test_program_lifecycle.py` — Layer 4 draft/active/archive transitions
- `pitcher_program_app/tests/test_program_builder_endpoints.py` — API integration shape (mocking services)

---

## Task 1: Repository helpers in `db.py`

> Pure CRUD functions that the service layer will consume. Test by mocking the Supabase client; we don't need integration tests for one-line query wrappers.

**Files:**
- Modify: `pitcher_program_app/bot/services/db.py`
- Create: `pitcher_program_app/tests/test_db_program_helpers.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for new program/builder_session repository helpers in db.py."""

from unittest.mock import MagicMock, patch
import pytest

from bot.services import db


def _mock_client(execute_data):
    """Build a chainable mock of the Supabase client returning the given data."""
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value = MagicMock(data=execute_data)
    client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=execute_data)
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=execute_data)
    client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(data=execute_data)
    return client


def test_create_program_inserts_and_returns_program_id():
    fake_inserted = [{"program_id": "abc-123", "pitcher_id": "landon_brice", "domain": "throwing"}]
    with patch.object(db, "get_client", return_value=_mock_client(fake_inserted)):
        program_id = db.create_program({
            "pitcher_id": "landon_brice",
            "parent_template_id": "tpl_starter_7day_cadence_v1",
            "domain": "throwing",
            "generated_schedule_json": {"days": []},
            "start_date": "2026-05-01",
            "nominal_end_date": "2026-07-24",
            "status": "draft",
            "created_by": "landon_brice",
            "created_by_role": "pitcher",
        })
    assert program_id == "abc-123"


def test_update_program_status_calls_update():
    with patch.object(db, "get_client", return_value=_mock_client([{"program_id": "abc"}])):
        db.update_program_status("abc-123", "active", activated_at="2026-05-01T00:00:00Z")
    # No exception = pass; behavior verified via mock chain.


def test_get_program_returns_dict_or_none():
    with patch.object(db, "get_client", return_value=_mock_client([{"program_id": "abc"}])):
        assert db.get_program("abc-123") == {"program_id": "abc"}
    with patch.object(db, "get_client", return_value=_mock_client([])):
        assert db.get_program("nonexistent") is None


def test_list_programs_for_pitcher_returns_list():
    with patch.object(db, "get_client", return_value=_mock_client([
        {"program_id": "p1"}, {"program_id": "p2"}
    ])):
        result = db.list_programs_for_pitcher("landon_brice")
        assert len(result) == 2


def test_create_builder_session_returns_session_id():
    fake = [{"session_id": "sess-1", "pitcher_id": "landon_brice"}]
    with patch.object(db, "get_client", return_value=_mock_client(fake)):
        session_id = db.create_builder_session({
            "pitcher_id": "landon_brice",
            "initiator_id": "landon_brice",
            "initiator_role": "pitcher",
            "interview_mode": "personalize",
            "constraint_envelope_json": {},
            "candidate_template_ids": [],
            "status": "in_progress",
        })
    assert session_id == "sess-1"


def test_record_generation_failure_inserts_row():
    with patch.object(db, "get_client", return_value=_mock_client([{"failure_id": "f1"}])):
        db.record_generation_failure(
            session_id="sess-1",
            attempt_number=1,
            validation_failure_kind="exercise_not_found",
            llm_response={"error": "tried ex_999"},
        )
    # No exception = pass.
```

- [ ] **Step 2: Run, expect FAIL**

Run: `cd pitcher_program_app && PYTHONPATH=. pytest tests/test_db_program_helpers.py -v`

Expected: FAIL — none of the helpers exist yet.

- [ ] **Step 3: Implement helpers in `pitcher_program_app/bot/services/db.py`**

Add near the existing program-template helpers. Match the existing function style (one-liner select-or-None pattern, no exceptions on miss, return dict or list):

```python
# ---------------- Programs (spec v1) ----------------

def create_program(row: dict) -> str:
    """Insert a programs row, return the new program_id."""
    resp = get_client().table("programs").insert(row).execute()
    return (resp.data or [{}])[0].get("program_id")


def get_program(program_id: str) -> dict | None:
    resp = (
        get_client()
        .table("programs")
        .select("*")
        .eq("program_id", program_id)
        .limit(1)
        .execute()
    )
    return (resp.data or [None])[0]


def update_program_status(program_id: str, status: str, **extras) -> None:
    """Patch a programs row's status (and optional extra fields like activated_at, archived_at, archive_reason)."""
    valid = {"draft", "active", "archived", "error"}
    if status not in valid:
        raise ValueError(f"status must be one of {valid}, got {status!r}")
    payload = {"status": status, **extras}
    get_client().table("programs").update(payload).eq("program_id", program_id).execute()


def list_programs_for_pitcher(pitcher_id: str, status: str | None = None) -> list[dict]:
    q = get_client().table("programs").select("*").eq("pitcher_id", pitcher_id)
    if status:
        q = q.eq("status", status)
    resp = q.order("created_at", desc=True).execute()
    return resp.data or []


# ---------------- Builder Sessions (spec v1) ----------------

def create_builder_session(row: dict) -> str:
    resp = get_client().table("program_builder_sessions").insert(row).execute()
    return (resp.data or [{}])[0].get("session_id")


def update_builder_session(session_id: str, patch: dict) -> None:
    get_client().table("program_builder_sessions").update(patch).eq("session_id", session_id).execute()


def get_builder_session(session_id: str) -> dict | None:
    resp = (
        get_client()
        .table("program_builder_sessions")
        .select("*")
        .eq("session_id", session_id)
        .limit(1)
        .execute()
    )
    return (resp.data or [None])[0]


# ---------------- Generation Failures ----------------

def record_generation_failure(session_id: str | None, attempt_number: int,
                               validation_failure_kind: str, llm_response: dict | None = None) -> None:
    get_client().table("program_generation_failures").insert({
        "session_id": session_id,
        "attempt_number": attempt_number,
        "validation_failure_kind": validation_failure_kind,
        "llm_response": llm_response,
    }).execute()
```

- [ ] **Step 4: Run tests, expect PASS**

Run: `cd pitcher_program_app && PYTHONPATH=. pytest tests/test_db_program_helpers.py -v`

Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/landonprojects/baseball/.claude/worktrees/epic-darwin-923895
git add pitcher_program_app/bot/services/db.py pitcher_program_app/tests/test_db_program_helpers.py
git commit -m "feat(db): repository helpers for programs + builder_sessions

Thin one-line wrappers matching existing db.py style. Consumed by
program_builder / program_generator / program_lifecycle services."
```

---

## Task 2: `program_builder.py` — Layer 1 candidate matching

> Given a constraint envelope (domain, goal, duration, start_date, hard_constraints), return 1–3 candidate templates from `block_library`. Pure function; reads `block_library` only.

**Files:**
- Create: `pitcher_program_app/bot/services/program_builder.py`
- Create: `pitcher_program_app/tests/test_program_builder_candidates.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for program_builder.match_candidates (Layer 1).

Spec Section 2 — Layer 1 Structured Inputs:
- Filter by domain
- Filter by effective_phase ∈ template.compatible_phases
- Filter by goal ∈ template.goal_tags
- Filter by duration ∈ template.duration_range_weeks
- Filter out templates incompatible with hard_constraints
- Return at most 3, ranked by best fit
- Zero matches blocks the form (returns [])
"""
from unittest.mock import patch
import pytest


def _tpl(tid, **overrides):
    base = {
        "block_template_id": tid,
        "name": tid,
        "domain": "throwing",
        "goal_tags": ["velocity"],
        "duration_range_weeks": "[8,12]",
        "compatible_phases": ["off_season", "preseason"],
        "tunable_parameters_schema": {},
        "implied_phase": "preseason",
        "research_doc_ids": [],
    }
    base.update(overrides)
    return base


def test_filter_by_domain():
    from bot.services import program_builder
    templates = [
        _tpl("t1", domain="throwing"),
        _tpl("t2", domain="lifting"),
    ]
    with patch.object(program_builder, "_load_all_templates", return_value=templates):
        result = program_builder.match_candidates({
            "domain": "throwing", "goal": "velocity", "duration_weeks": 12,
            "effective_phase": "preseason", "hard_constraints": [],
        })
    assert [t["block_template_id"] for t in result] == ["t1"]


def test_filter_by_phase():
    from bot.services import program_builder
    templates = [
        _tpl("t1", compatible_phases=["preseason"]),
        _tpl("t2", compatible_phases=["off_season"]),
    ]
    with patch.object(program_builder, "_load_all_templates", return_value=templates):
        result = program_builder.match_candidates({
            "domain": "throwing", "goal": "velocity", "duration_weeks": 12,
            "effective_phase": "preseason", "hard_constraints": [],
        })
    assert [t["block_template_id"] for t in result] == ["t1"]


def test_filter_by_goal():
    from bot.services import program_builder
    templates = [
        _tpl("t1", goal_tags=["velocity"]),
        _tpl("t2", goal_tags=["return_to_mound"]),
    ]
    with patch.object(program_builder, "_load_all_templates", return_value=templates):
        result = program_builder.match_candidates({
            "domain": "throwing", "goal": "return_to_mound", "duration_weeks": 8,
            "effective_phase": "preseason", "hard_constraints": [],
        })
    assert [t["block_template_id"] for t in result] == ["t2"]


def test_filter_by_duration_within_range():
    from bot.services import program_builder
    templates = [
        _tpl("t1", duration_range_weeks="[4,8]"),
        _tpl("t2", duration_range_weeks="[8,12]"),
    ]
    with patch.object(program_builder, "_load_all_templates", return_value=templates):
        result = program_builder.match_candidates({
            "domain": "throwing", "goal": "velocity", "duration_weeks": 6,
            "effective_phase": "preseason", "hard_constraints": [],
        })
    assert [t["block_template_id"] for t in result] == ["t1"]


def test_returns_at_most_three():
    from bot.services import program_builder
    templates = [_tpl(f"t{i}") for i in range(10)]
    with patch.object(program_builder, "_load_all_templates", return_value=templates):
        result = program_builder.match_candidates({
            "domain": "throwing", "goal": "velocity", "duration_weeks": 12,
            "effective_phase": "preseason", "hard_constraints": [],
        })
    assert len(result) <= 3


def test_zero_matches_returns_empty_list():
    from bot.services import program_builder
    templates = [_tpl("t1", domain="lifting")]
    with patch.object(program_builder, "_load_all_templates", return_value=templates):
        result = program_builder.match_candidates({
            "domain": "throwing", "goal": "velocity", "duration_weeks": 12,
            "effective_phase": "preseason", "hard_constraints": [],
        })
    assert result == []


def test_rejects_unknown_domain():
    from bot.services import program_builder
    with pytest.raises(ValueError, match="domain"):
        program_builder.match_candidates({
            "domain": "yoga", "goal": "x", "duration_weeks": 4,
            "effective_phase": "preseason", "hard_constraints": [],
        })


def test_constraint_envelope_validation_missing_keys():
    from bot.services import program_builder
    with pytest.raises(KeyError):
        program_builder.match_candidates({"domain": "throwing"})
```

- [ ] **Step 2: Run, expect FAIL**

Run: `cd pitcher_program_app && PYTHONPATH=. pytest tests/test_program_builder_candidates.py -v`

Expected: 8 FAIL.

- [ ] **Step 3: Implement `pitcher_program_app/bot/services/program_builder.py`**

```python
"""Layer 1 of the Program Builder funnel: structured-input → candidate templates.

Pure function. Reads block_library through a _load_* helper for testability.
"""
from __future__ import annotations

from typing import Optional


_REQUIRED_KEYS = {"domain", "goal", "duration_weeks", "effective_phase", "hard_constraints"}
_VALID_DOMAINS = ("throwing", "lifting")
_MAX_CANDIDATES = 3


def _load_all_templates() -> list[dict]:
    """Read all rows from block_library. Tests monkeypatch this."""
    from bot.services import db
    resp = db.get_client().table("block_library").select("*").execute()
    return resp.data or []


def _parse_int4range(rng: Optional[str]) -> Optional[tuple[int, int]]:
    """Parse Postgres int4range literal '[lo,hi]' or '[lo,hi)' to (lo, hi_inclusive).

    Returns None if rng is None/empty. Treats both '[]' and '[)' as inclusive on lower
    and adjusts the upper bound for half-open notation. Valid examples:
      '[8,12]'  -> (8, 12)
      '[8,12)'  -> (8, 11)
      '(7,12]'  -> (8, 12)
    """
    if not rng:
        return None
    s = rng.strip()
    if len(s) < 5:
        return None
    lo_inc = s[0] == "["
    hi_inc = s[-1] == "]"
    parts = s[1:-1].split(",")
    if len(parts) != 2:
        return None
    try:
        lo = int(parts[0])
        hi = int(parts[1])
    except ValueError:
        return None
    if not lo_inc:
        lo += 1
    if not hi_inc:
        hi -= 1
    return (lo, hi)


def _matches(tpl: dict, env: dict) -> bool:
    if tpl.get("domain") != env["domain"]:
        return False
    if env["effective_phase"] not in (tpl.get("compatible_phases") or []):
        return False
    if env["goal"] not in (tpl.get("goal_tags") or []):
        return False
    rng = _parse_int4range(tpl.get("duration_range_weeks"))
    if rng:
        lo, hi = rng
        if not (lo <= env["duration_weeks"] <= hi):
            return False
    # Hard-constraint filtering: stays light in v1.
    # If a template has tunable_parameters_schema declaring incompatibility tags,
    # honor them. Otherwise no-op (templates self-declare in scaffold).
    incompat = (tpl.get("tunable_parameters_schema") or {}).get("incompatible_with") or []
    for hc in env["hard_constraints"]:
        if hc in incompat:
            return False
    return True


def _score(tpl: dict, env: dict) -> int:
    """Higher = better. Used to rank when more than _MAX_CANDIDATES match."""
    score = 0
    if tpl.get("implied_phase") == env["effective_phase"]:
        score += 5  # template implies the same phase the pitcher is in — good fit
    rng = _parse_int4range(tpl.get("duration_range_weeks"))
    if rng:
        lo, hi = rng
        # Prefer templates whose midpoint is closest to the requested duration
        midpoint = (lo + hi) / 2
        score -= abs(midpoint - env["duration_weeks"])
    return score


def match_candidates(constraint_envelope: dict) -> list[dict]:
    """Layer 1: filter+rank block_library to 1–3 candidate templates.

    constraint_envelope keys (all required):
      - domain: 'throwing' | 'lifting'
      - goal: str (must match a goal_tag on the template)
      - duration_weeks: int
      - effective_phase: str (must be in template.compatible_phases)
      - hard_constraints: list[str]

    Returns up to 3 templates. Empty list if no template matches.
    """
    missing = _REQUIRED_KEYS - constraint_envelope.keys()
    if missing:
        raise KeyError(f"constraint_envelope missing keys: {sorted(missing)}")
    if constraint_envelope["domain"] not in _VALID_DOMAINS:
        raise ValueError(f"domain must be one of {_VALID_DOMAINS}, got {constraint_envelope['domain']!r}")

    candidates = [t for t in _load_all_templates() if _matches(t, constraint_envelope)]
    candidates.sort(key=lambda t: _score(t, constraint_envelope), reverse=True)
    return candidates[:_MAX_CANDIDATES]
```

- [ ] **Step 4: Run tests, expect PASS**

Run: `cd pitcher_program_app && PYTHONPATH=. pytest tests/test_program_builder_candidates.py -v`

Expected: 8 PASS.

- [ ] **Step 5: Commit**

```bash
git add pitcher_program_app/bot/services/program_builder.py \
        pitcher_program_app/tests/test_program_builder_candidates.py
git commit -m "feat: program_builder.match_candidates (Layer 1)

Filters block_library by domain + effective_phase + goal + duration range,
ranks remaining templates, returns up to 3. Pure function with _load_*
seam for tests. Spec Section 2 Layer 1."
```

---

## Task 3: `program_generator.py` — Layer 3 generation + validation

> Given a chosen template + tuned spec, generate a day-by-day schedule and validate hard invariants. Retry once on validation failure with default tuning. Persist the resulting program as `status='draft'`. Mock LLM call for v1 — produce a deterministic schedule from the template's `week_scaffold_json`. Plan 3 will replace the mock with a real `call_llm_reasoning` invocation.

**Files:**
- Create: `pitcher_program_app/bot/services/program_generator.py`
- Create: `pitcher_program_app/tests/test_program_generator.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for program_generator.generate_program (Layer 3).

Validates:
- Happy path: template + tuned_spec → draft program persisted
- Hard invariants: every exercise referenced exists, no contraindicated for active injuries,
  intensity ramp monotonic where required, total duration matches chosen weeks,
  per-week volume within template caps
- Validation fail → retry with default tuning, log to program_generation_failures
- Second fail → return default-tuned scaffold, log, status='error'
"""
from datetime import date
from unittest.mock import patch, MagicMock

import pytest


def _starter_template():
    return {
        "block_template_id": "tpl_test",
        "name": "Test Throwing Block",
        "domain": "throwing",
        "duration_range_weeks": "[8,12]",
        "compatible_phases": ["preseason"],
        "tunable_parameters_schema": {},
        "implied_phase": "preseason",
        "week_scaffold_json": {
            "scaffold_kind": "calendar_relative_repeating_7day",
            "rotation_template_keys": [
                {"day_offset": 0, "template_key": "day_0"},
                {"day_offset": 1, "template_key": "day_1"},
                {"day_offset": 2, "template_key": "day_2"},
                {"day_offset": 3, "template_key": "day_3"},
                {"day_offset": 4, "template_key": "day_4"},
                {"day_offset": 5, "template_key": "day_5"},
                {"day_offset": 6, "template_key": "day_6"},
            ],
        },
    }


def test_generate_program_happy_path_persists_draft():
    from bot.services import program_generator
    template = _starter_template()
    fake_program_id = "prog-1"

    with patch.object(program_generator, "_load_template", return_value=template), \
         patch.object(program_generator, "_load_pitcher_profile", return_value={"pitcher_id": "landon_brice"}), \
         patch.object(program_generator, "_validate_schedule", return_value=[]), \
         patch.object(program_generator, "_persist_program", return_value=fake_program_id):
        result = program_generator.generate_program(
            pitcher_id="landon_brice",
            template_id="tpl_test",
            tuned_spec={"weeks": 12},
            constraint_envelope={"start_date": "2026-05-01"},
            session_id=None,
        )
    assert result["program_id"] == fake_program_id
    assert result["status"] == "draft"


def test_generate_program_validates_total_duration():
    from bot.services import program_generator
    template = _starter_template()

    with patch.object(program_generator, "_load_template", return_value=template), \
         patch.object(program_generator, "_load_pitcher_profile", return_value={"pitcher_id": "landon_brice"}), \
         patch.object(program_generator, "_persist_program", return_value="prog-1"), \
         patch.object(program_generator, "_record_failure") as record:
        # First validation fails, second (default-tuned) passes
        with patch.object(program_generator, "_validate_schedule",
                          side_effect=[["duration_mismatch"], []]):
            result = program_generator.generate_program(
                pitcher_id="landon_brice",
                template_id="tpl_test",
                tuned_spec={"weeks": 999},  # absurd, will fail validation
                constraint_envelope={"start_date": "2026-05-01"},
                session_id="sess-1",
            )
    assert result["status"] == "draft"
    assert record.called  # failure was logged


def test_generate_program_two_failures_returns_error_status():
    from bot.services import program_generator
    template = _starter_template()

    with patch.object(program_generator, "_load_template", return_value=template), \
         patch.object(program_generator, "_load_pitcher_profile", return_value={"pitcher_id": "landon_brice"}), \
         patch.object(program_generator, "_validate_schedule",
                      side_effect=[["fail1"], ["fail2"]]), \
         patch.object(program_generator, "_persist_program", return_value="prog-1"), \
         patch.object(program_generator, "_record_failure"):
        result = program_generator.generate_program(
            pitcher_id="landon_brice",
            template_id="tpl_test",
            tuned_spec={"weeks": 999},
            constraint_envelope={"start_date": "2026-05-01"},
            session_id="sess-1",
        )
    assert result["status"] == "error"


def test_generate_program_unknown_template_raises():
    from bot.services import program_generator
    with patch.object(program_generator, "_load_template", return_value=None):
        with pytest.raises(ValueError, match="template"):
            program_generator.generate_program(
                pitcher_id="landon_brice",
                template_id="nonexistent",
                tuned_spec={"weeks": 12},
                constraint_envelope={"start_date": "2026-05-01"},
                session_id=None,
            )


def test_validate_schedule_flags_duration_mismatch():
    from bot.services import program_generator
    schedule = {"days": [{"day_index": i} for i in range(50)]}
    failures = program_generator._validate_schedule(
        schedule=schedule,
        tuned_spec={"weeks": 12},  # 12 weeks should be 84 days
        template={"block_template_id": "tpl_test"},
        profile={},
    )
    assert "duration_mismatch" in failures


def test_validate_schedule_passes_correct_duration():
    from bot.services import program_generator
    schedule = {"days": [{"day_index": i} for i in range(84)]}
    failures = program_generator._validate_schedule(
        schedule=schedule,
        tuned_spec={"weeks": 12},
        template={"block_template_id": "tpl_test"},
        profile={},
    )
    assert "duration_mismatch" not in failures


def test_generated_schedule_has_correct_day_count():
    from bot.services import program_generator
    template = _starter_template()
    schedule = program_generator._build_schedule_from_scaffold(
        template=template,
        tuned_spec={"weeks": 8},
        start_date=date(2026, 5, 1),
    )
    assert len(schedule["days"]) == 56  # 8 weeks * 7 days


def test_generated_schedule_repeats_rotation():
    from bot.services import program_generator
    template = _starter_template()
    schedule = program_generator._build_schedule_from_scaffold(
        template=template,
        tuned_spec={"weeks": 8},
        start_date=date(2026, 5, 1),
    )
    # Day 0 → day_0, day 7 → day_0, day 14 → day_0
    assert schedule["days"][0]["template_key"] == "day_0"
    assert schedule["days"][7]["template_key"] == "day_0"
    assert schedule["days"][14]["template_key"] == "day_0"
    assert schedule["days"][3]["template_key"] == "day_3"
```

- [ ] **Step 2: Run, expect FAIL**

Run: `cd pitcher_program_app && PYTHONPATH=. pytest tests/test_program_generator.py -v`

Expected: 8 FAIL — module doesn't exist.

- [ ] **Step 3: Implement `pitcher_program_app/bot/services/program_generator.py`**

```python
"""Layer 3 of the Program Builder funnel: schedule generation + hard-invariant validation.

v1 implementation builds a deterministic schedule from the template's
week_scaffold_json (no LLM call). Plan 3 will replace _build_schedule_from_scaffold
with an LLM-driven path; the validation layer stays the same.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional


_DEFAULT_WEEKS = 12  # default tuning when retry-with-defaults kicks in


def _load_template(template_id: str) -> Optional[dict]:
    from bot.services import db
    return db.get_block_library_row(template_id)


def _load_pitcher_profile(pitcher_id: str) -> Optional[dict]:
    from bot.services import db
    try:
        return db.get_pitcher(pitcher_id)
    except KeyError:
        return None


def _persist_program(row: dict) -> str:
    from bot.services import db
    return db.create_program(row)


def _record_failure(session_id: str | None, attempt_number: int, kind: str,
                     llm_response: dict | None = None) -> None:
    from bot.services import db
    db.record_generation_failure(
        session_id=session_id,
        attempt_number=attempt_number,
        validation_failure_kind=kind,
        llm_response=llm_response,
    )


def _build_schedule_from_scaffold(template: dict, tuned_spec: dict, start_date: date) -> dict:
    """Build a day-by-day schedule by repeating the template's rotation."""
    weeks = int(tuned_spec.get("weeks", _DEFAULT_WEEKS))
    total_days = weeks * 7
    scaffold = (template.get("week_scaffold_json") or {})
    rotation = scaffold.get("rotation_template_keys") or []
    if not rotation:
        return {"days": [], "scaffold_kind": "empty"}

    days = []
    for i in range(total_days):
        rk = rotation[i % len(rotation)]
        days.append({
            "day_index": i,
            "template_key": rk["template_key"],
            "date": (start_date + timedelta(days=i)).isoformat(),
        })
    return {
        "scaffold_kind": scaffold.get("scaffold_kind", "calendar_relative_repeating_7day"),
        "days": days,
    }


def _validate_schedule(schedule: dict, tuned_spec: dict, template: dict, profile: dict) -> list[str]:
    """Return a list of validation_failure_kind strings; empty = valid."""
    failures: list[str] = []

    # Total duration matches chosen weeks
    weeks = int(tuned_spec.get("weeks", _DEFAULT_WEEKS))
    expected_days = weeks * 7
    actual_days = len((schedule or {}).get("days") or [])
    if actual_days != expected_days:
        failures.append("duration_mismatch")

    # Per-week volume within template caps — v1: no caps declared, no-op.
    # Intensity ramp monotonic where required — v1: not declared in scaffold, no-op.
    # Every referenced exercise exists in `exercises` — v1: scaffold is template-key based,
    #   actual exercise binding happens at consume-time via exercise_pool, so no-op here.
    # No contraindicated exercise for active injuries — v1: same reasoning.

    return failures


def generate_program(pitcher_id: str, template_id: str, tuned_spec: dict,
                      constraint_envelope: dict, session_id: str | None) -> dict:
    """Layer 3: produce a draft program for the pitcher.

    Returns the persisted program row. Status will be 'draft' on success or 'error'
    after two consecutive validation failures (the second falls back to default tuning).
    """
    template = _load_template(template_id)
    if not template:
        raise ValueError(f"template not found: {template_id}")

    profile = _load_pitcher_profile(pitcher_id) or {}
    start_date_str = constraint_envelope.get("start_date") or date.today().isoformat()
    start_date = date.fromisoformat(start_date_str)

    # Attempt 1: with tuned_spec
    schedule = _build_schedule_from_scaffold(template, tuned_spec, start_date)
    failures = _validate_schedule(schedule, tuned_spec, template, profile)
    final_status = "draft"

    if failures:
        _record_failure(session_id, 1, ",".join(failures))
        # Attempt 2: default tuning
        default_spec = {"weeks": _DEFAULT_WEEKS}
        schedule = _build_schedule_from_scaffold(template, default_spec, start_date)
        failures2 = _validate_schedule(schedule, default_spec, template, profile)
        if failures2:
            _record_failure(session_id, 2, ",".join(failures2))
            final_status = "error"
        tuned_spec = default_spec

    weeks = int(tuned_spec.get("weeks", _DEFAULT_WEEKS))
    nominal_end_date = start_date + timedelta(days=weeks * 7)

    row = {
        "pitcher_id": pitcher_id,
        "parent_template_id": template_id,
        "domain": template.get("domain"),
        "tuned_spec_json": tuned_spec,
        "generated_schedule_json": schedule,
        "start_date": start_date.isoformat(),
        "nominal_end_date": nominal_end_date.isoformat(),
        "current_day_index": 0,
        "held_days_count": 0,
        "status": final_status,
        "created_by": pitcher_id,  # caller may override via constraint_envelope
        "created_by_role": constraint_envelope.get("created_by_role", "pitcher"),
    }
    if "created_by" in constraint_envelope:
        row["created_by"] = constraint_envelope["created_by"]

    program_id = _persist_program(row)
    row["program_id"] = program_id
    return row
```

- [ ] **Step 4: Run tests, expect PASS**

Run: `cd pitcher_program_app && PYTHONPATH=. pytest tests/test_program_generator.py -v`

Expected: 8 PASS.

- [ ] **Step 5: Commit**

```bash
git add pitcher_program_app/bot/services/program_generator.py \
        pitcher_program_app/tests/test_program_generator.py
git commit -m "feat: program_generator.generate_program (Layer 3)

Builds day-by-day schedule from template scaffold, validates hard
invariants, retries once with default tuning on failure, logs to
program_generation_failures, persists as draft. v1 schedule path is
deterministic (no LLM); Plan 3 replaces _build_schedule_from_scaffold
with an LLM-driven path."
```

---

## Task 4: `program_lifecycle.py` — Layer 4 draft / activate / archive

> The state machine: drafts are inert; activating a program archives any existing active program in the same (pitcher, domain) slot (D9 confirm-then-archive); archiving sets a reason. Caller is responsible for showing the confirmation prompt — this layer just does the transactional swap.

**Files:**
- Create: `pitcher_program_app/bot/services/program_lifecycle.py`
- Create: `pitcher_program_app/tests/test_program_lifecycle.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for program_lifecycle (Layer 4).

State machine: draft → active (with confirm-then-archive of any existing active in same domain),
              draft → archived,
              active → archived.
"""
from unittest.mock import patch, call


def test_activate_draft_with_no_existing_active():
    from bot.services import program_lifecycle
    with patch.object(program_lifecycle, "_get_program", return_value={
            "program_id": "p1", "pitcher_id": "landon_brice",
            "domain": "throwing", "status": "draft"}), \
         patch.object(program_lifecycle, "_get_active_program_in_domain", return_value=None), \
         patch.object(program_lifecycle, "_update_status") as upd:
        result = program_lifecycle.activate("p1")
    assert result["activated"] == "p1"
    assert result["archived"] is None
    upd.assert_called_once_with("p1", "active", activated_at=upd.call_args.kwargs["activated_at"])


def test_activate_archives_existing_active_in_same_domain():
    from bot.services import program_lifecycle
    with patch.object(program_lifecycle, "_get_program", return_value={
            "program_id": "p2", "pitcher_id": "landon_brice",
            "domain": "throwing", "status": "draft"}), \
         patch.object(program_lifecycle, "_get_active_program_in_domain", return_value={
            "program_id": "p1_old", "pitcher_id": "landon_brice",
            "domain": "throwing", "status": "active"}), \
         patch.object(program_lifecycle, "_update_status") as upd:
        result = program_lifecycle.activate("p2", archive_reason="superseded")
    assert result["activated"] == "p2"
    assert result["archived"] == "p1_old"
    # Two update calls in order: archive old, then activate new
    assert len(upd.call_args_list) == 2
    assert upd.call_args_list[0][0][0] == "p1_old"
    assert upd.call_args_list[0][0][1] == "archived"
    assert upd.call_args_list[1][0][0] == "p2"
    assert upd.call_args_list[1][0][1] == "active"


def test_activate_does_nothing_if_already_active():
    from bot.services import program_lifecycle
    with patch.object(program_lifecycle, "_get_program", return_value={
            "program_id": "p1", "status": "active", "domain": "throwing"}), \
         patch.object(program_lifecycle, "_update_status") as upd:
        result = program_lifecycle.activate("p1")
    assert result["activated"] == "p1"
    assert result["already_active"] is True
    upd.assert_not_called()


def test_activate_rejects_archived_program():
    from bot.services import program_lifecycle
    import pytest
    with patch.object(program_lifecycle, "_get_program", return_value={
            "program_id": "p1", "status": "archived"}):
        with pytest.raises(ValueError, match="archived"):
            program_lifecycle.activate("p1")


def test_archive_sets_reason_and_archived_at():
    from bot.services import program_lifecycle
    with patch.object(program_lifecycle, "_get_program", return_value={
            "program_id": "p1", "status": "active"}), \
         patch.object(program_lifecycle, "_update_status") as upd:
        program_lifecycle.archive("p1", reason="completed")
    upd.assert_called_once()
    args, kwargs = upd.call_args
    assert args == ("p1", "archived")
    assert kwargs["archive_reason"] == "completed"
    assert "archived_at" in kwargs


def test_archive_idempotent_on_already_archived():
    from bot.services import program_lifecycle
    with patch.object(program_lifecycle, "_get_program", return_value={
            "program_id": "p1", "status": "archived"}), \
         patch.object(program_lifecycle, "_update_status") as upd:
        program_lifecycle.archive("p1", reason="x")
    upd.assert_not_called()


def test_get_program_or_raise_not_found():
    from bot.services import program_lifecycle
    import pytest
    with patch.object(program_lifecycle, "_get_program", return_value=None):
        with pytest.raises(LookupError):
            program_lifecycle.activate("nonexistent")
```

- [ ] **Step 2: Run, expect FAIL**

Run: `cd pitcher_program_app && PYTHONPATH=. pytest tests/test_program_lifecycle.py -v`

Expected: 7 FAIL — module doesn't exist.

- [ ] **Step 3: Implement `pitcher_program_app/bot/services/program_lifecycle.py`**

```python
"""Layer 4 of the Program Builder funnel: program lifecycle.

State machine:
  draft  → active   (confirm-then-archive existing active in same (pitcher, domain) slot)
  draft  → archived
  active → archived

The partial unique index `idx_programs_one_active_per_domain` enforces "one active
per (pitcher, domain)" at the DB level — this layer just sequences the swap.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


def _get_program(program_id: str) -> Optional[dict]:
    from bot.services import db
    return db.get_program(program_id)


def _get_active_program_in_domain(pitcher_id: str, domain: str) -> Optional[dict]:
    from bot.services import db
    return db.get_active_program(pitcher_id, domain)


def _update_status(program_id: str, status: str, **extras) -> None:
    from bot.services import db
    db.update_program_status(program_id, status, **extras)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def activate(program_id: str, archive_reason: str = "superseded") -> dict:
    """Transition a program to status='active', archiving any existing active in the same domain."""
    program = _get_program(program_id)
    if not program:
        raise LookupError(f"program not found: {program_id}")

    if program["status"] == "archived":
        raise ValueError(f"cannot activate an archived program: {program_id}")

    if program["status"] == "active":
        return {"activated": program_id, "archived": None, "already_active": True}

    existing = _get_active_program_in_domain(program["pitcher_id"], program["domain"])
    archived_id = None
    if existing and existing["program_id"] != program_id:
        _update_status(existing["program_id"], "archived",
                       archived_at=_now_iso(), archive_reason=archive_reason)
        archived_id = existing["program_id"]

    _update_status(program_id, "active", activated_at=_now_iso())
    return {"activated": program_id, "archived": archived_id}


def archive(program_id: str, reason: str) -> dict:
    """Archive a draft or active program. Idempotent on already-archived."""
    program = _get_program(program_id)
    if not program:
        raise LookupError(f"program not found: {program_id}")
    if program["status"] == "archived":
        return {"archived": program_id, "already_archived": True}
    _update_status(program_id, "archived",
                   archived_at=_now_iso(), archive_reason=reason)
    return {"archived": program_id}
```

- [ ] **Step 4: Run tests, expect PASS**

Run: `cd pitcher_program_app && PYTHONPATH=. pytest tests/test_program_lifecycle.py -v`

Expected: 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add pitcher_program_app/bot/services/program_lifecycle.py \
        pitcher_program_app/tests/test_program_lifecycle.py
git commit -m "feat: program_lifecycle activate/archive (Layer 4)

State machine: draft→active confirms-then-archives existing active in
same (pitcher, domain) slot per spec D9. Idempotent on no-op transitions.
Partial unique index enforces the invariant at the DB level; this layer
sequences the swap and writes archive_reason + activated_at."
```

---

## Task 5: API endpoints — pitcher-facing builder routes

> Wire all three layers into `/api/programs/builder/*` endpoints. Layer 2 stub: just records the session as completed and picks `candidates[0]` as `chosen_template_id`. Plan 3 replaces this with the real Socratic loop.

**Files:**
- Modify: `pitcher_program_app/api/routes.py`
- Create: `pitcher_program_app/tests/test_program_builder_endpoints.py`

- [ ] **Step 1: Inspect routes.py for the auth dependency style**

Run: `grep -n "Depends\|require_pitcher_auth\|pitcher_id" pitcher_program_app/api/routes.py | head -20`

Note the existing pattern for pitcher-authenticated endpoints. Match it for the new routes.

- [ ] **Step 2: Write tests**

```python
"""Integration shape tests for /api/programs/builder/* endpoints.

Mocks the service layer; exercises only the FastAPI wiring (request shape, auth,
response shape). End-to-end tests live elsewhere (Plan 6 or QA).
"""
from unittest.mock import patch
from fastapi.testclient import TestClient

import pytest


@pytest.fixture
def client():
    from api.main import app
    return TestClient(app)


def test_post_builder_candidates_happy_path(client):
    from bot.services import program_builder
    with patch.object(program_builder, "match_candidates", return_value=[
        {"block_template_id": "tpl_a", "name": "A"},
        {"block_template_id": "tpl_b", "name": "B"},
    ]):
        # Minimal auth: assume DISABLE_AUTH or explicit test pitcher_id header
        resp = client.post("/api/programs/builder/candidates", json={
            "domain": "throwing",
            "goal": "velocity",
            "duration_weeks": 12,
            "effective_phase": "preseason",
            "hard_constraints": [],
        }, headers={"X-Test-Pitcher-Id": "landon_brice"})
    assert resp.status_code == 200
    body = resp.json()
    assert "candidates" in body
    assert "session_id" in body
    assert len(body["candidates"]) == 2


def test_post_builder_generate_uses_first_candidate_in_v1(client):
    """Layer 2 stub: picks candidates[0]. Plan 3 will replace with Socratic flow."""
    from bot.services import program_generator, program_builder
    with patch.object(program_builder, "match_candidates", return_value=[
        {"block_template_id": "tpl_a"}]), \
         patch.object(program_generator, "generate_program",
                      return_value={"program_id": "prog-1", "status": "draft"}):
        resp = client.post("/api/programs/builder/generate", json={
            "session_id": "sess-1",
            "tuned_spec": {"weeks": 12},
        }, headers={"X-Test-Pitcher-Id": "landon_brice"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["program"]["program_id"] == "prog-1"
    assert body["program"]["status"] == "draft"


def test_post_program_activate_returns_activation_result(client):
    from bot.services import program_lifecycle
    with patch.object(program_lifecycle, "activate", return_value={
        "activated": "prog-1", "archived": "prog-old"}):
        resp = client.post("/api/programs/prog-1/activate",
                            headers={"X-Test-Pitcher-Id": "landon_brice"})
    assert resp.status_code == 200
    assert resp.json() == {"activated": "prog-1", "archived": "prog-old"}


def test_post_program_archive_returns_archive_result(client):
    from bot.services import program_lifecycle
    with patch.object(program_lifecycle, "archive", return_value={"archived": "prog-1"}):
        resp = client.post("/api/programs/prog-1/archive", json={"reason": "user_cancelled"},
                           headers={"X-Test-Pitcher-Id": "landon_brice"})
    assert resp.status_code == 200
    assert resp.json() == {"archived": "prog-1"}
```

- [ ] **Step 3: Run, expect FAIL**

Run: `cd pitcher_program_app && PYTHONPATH=. pytest tests/test_program_builder_endpoints.py -v`

Expected: FAIL — endpoints don't exist.

- [ ] **Step 4: Implement endpoints in `pitcher_program_app/api/routes.py`**

Add a new section near the bottom of the file (or wherever pitcher-facing endpoints live). Structure:

```python
# ============================================================
# Program Builder v1 — Layers 1, 3, 4 (Plan 2)
# ============================================================

from pydantic import BaseModel, Field
from typing import Optional

from bot.services import program_builder, program_generator, program_lifecycle, db


class BuilderCandidatesRequest(BaseModel):
    domain: str = Field(..., pattern="^(throwing|lifting)$")
    goal: str
    duration_weeks: int = Field(..., gt=0, le=52)
    effective_phase: str
    hard_constraints: list[str] = []


class BuilderGenerateRequest(BaseModel):
    session_id: str
    tuned_spec: dict
    chosen_template_id: Optional[str] = None  # explicit choice; v1 stub falls back to candidates[0]


class ProgramArchiveRequest(BaseModel):
    reason: str


def _resolve_pitcher_id(request) -> str:
    """Pull pitcher_id from the existing auth pattern (Telegram initData HMAC).

    For tests, honors X-Test-Pitcher-Id header when DISABLE_AUTH is true.
    """
    # MATCH EXISTING ROUTES.PY PATTERN — likely uses Depends(verify_telegram_init_data)
    # The implementer should locate the canonical helper (e.g. get_authenticated_pitcher_id)
    # and reuse it here. Do NOT roll a new auth path.
    raise NotImplementedError("replace with existing auth helper from routes.py")


@app.post("/api/programs/builder/candidates")
def post_builder_candidates(req: BuilderCandidatesRequest, request: Request):
    pitcher_id = _resolve_pitcher_id(request)
    candidates = program_builder.match_candidates(req.dict())
    session_id = db.create_builder_session({
        "pitcher_id": pitcher_id,
        "initiator_id": pitcher_id,
        "initiator_role": "pitcher",
        "interview_mode": "personalize",
        "constraint_envelope_json": req.dict(),
        "candidate_template_ids": [c["block_template_id"] for c in candidates],
        "status": "in_progress",
    })
    return {"session_id": session_id, "candidates": candidates}


@app.post("/api/programs/builder/generate")
def post_builder_generate(req: BuilderGenerateRequest, request: Request):
    pitcher_id = _resolve_pitcher_id(request)
    session = db.get_builder_session(req.session_id)
    if not session or session["pitcher_id"] != pitcher_id:
        raise HTTPException(status_code=404, detail="session not found")

    # Layer 2 stub: if chosen_template_id is None, pick the first candidate.
    template_id = req.chosen_template_id
    if not template_id:
        candidate_ids = session.get("candidate_template_ids") or []
        if not candidate_ids:
            raise HTTPException(status_code=400, detail="no candidates and no chosen_template_id")
        template_id = candidate_ids[0]

    program = program_generator.generate_program(
        pitcher_id=pitcher_id,
        template_id=template_id,
        tuned_spec=req.tuned_spec,
        constraint_envelope=session.get("constraint_envelope_json") or {},
        session_id=req.session_id,
    )

    db.update_builder_session(req.session_id, {
        "chosen_template_id": template_id,
        "tuned_spec_json": req.tuned_spec,
        "status": "completed",
        "generated_program_id": program["program_id"],
    })

    return {"program": program}


@app.post("/api/programs/{program_id}/activate")
def post_program_activate(program_id: str, request: Request):
    pitcher_id = _resolve_pitcher_id(request)
    program = db.get_program(program_id)
    if not program or program["pitcher_id"] != pitcher_id:
        raise HTTPException(status_code=404, detail="program not found")
    return program_lifecycle.activate(program_id)


@app.post("/api/programs/{program_id}/archive")
def post_program_archive(program_id: str, req: ProgramArchiveRequest, request: Request):
    pitcher_id = _resolve_pitcher_id(request)
    program = db.get_program(program_id)
    if not program or program["pitcher_id"] != pitcher_id:
        raise HTTPException(status_code=404, detail="program not found")
    return program_lifecycle.archive(program_id, reason=req.reason)
```

> **Implementer note:** the `_resolve_pitcher_id(request)` helper is a placeholder. Locate the actual auth helper used by adjacent endpoints (likely something like `verify_telegram_init_data` returning a pitcher_id, or a `Depends(...)` shorthand) and REPLACE the placeholder with that pattern. Do not introduce a new auth path.

- [ ] **Step 5: Run tests, expect PASS**

Run: `cd pitcher_program_app && PYTHONPATH=. DISABLE_AUTH=true pytest tests/test_program_builder_endpoints.py -v`

Expected: 4 PASS. If the existing test suite uses different auth bypass, adapt accordingly.

- [ ] **Step 6: Run full backend suite**

Run: `cd pitcher_program_app && PYTHONPATH=. pytest 2>&1 | tail -10`

Expected: previous total + new tests, no regressions.

- [ ] **Step 7: Commit**

```bash
git add pitcher_program_app/api/routes.py \
        pitcher_program_app/tests/test_program_builder_endpoints.py
git commit -m "feat(api): /api/programs/builder/* + /api/programs/{id}/{activate,archive}

Wires Layer 1 (candidates), Layer 3 (generate), Layer 4 (activate/archive).
Layer 2 is stubbed — picks candidates[0] when chosen_template_id is null.
Plan 3 will replace the stub with a real Socratic loop. Auth follows the
existing pitcher-facing pattern."
```

---

## Task 6: Coach-app mirror endpoints

> Same handlers, different auth + interview_mode. Coach can hit the same builder for any pitcher on their team. The locked spec answer for "Build for a specific pitcher" + "Build a team program" both flow through these.

**Files:**
- Modify: `pitcher_program_app/api/coach_routes.py`

- [ ] **Step 1: Inspect existing coach auth + team scoping**

Run: `grep -n "require_coach_auth\|team_id\|coach_id" pitcher_program_app/api/coach_routes.py | head -20`

Note the standard coach-route shape. Most likely a dependency injection pattern.

- [ ] **Step 2: Add coach mirror endpoints**

Add to `coach_routes.py`:

```python
# ============================================================
# Program Builder v1 — Coach mirror (Plan 2)
# ============================================================

from pydantic import BaseModel
from bot.services import program_builder, program_generator, program_lifecycle, db


class CoachBuilderCandidatesRequest(BaseModel):
    pitcher_id: str
    domain: str
    goal: str
    duration_weeks: int
    effective_phase: str
    hard_constraints: list[str] = []


class CoachBuilderGenerateRequest(BaseModel):
    session_id: str
    tuned_spec: dict
    chosen_template_id: str | None = None


@router.post("/api/coach/programs/builder/candidates")
def post_coach_builder_candidates(req: CoachBuilderCandidatesRequest,
                                   coach=Depends(require_coach_auth)):
    # Verify the pitcher belongs to the coach's team
    pitcher = db.get_pitcher(req.pitcher_id)
    if not pitcher or pitcher.get("team_id") != coach["team_id"]:
        raise HTTPException(status_code=404, detail="pitcher not found")

    envelope = req.dict(exclude={"pitcher_id"})
    candidates = program_builder.match_candidates(envelope)
    session_id = db.create_builder_session({
        "pitcher_id": req.pitcher_id,
        "initiator_id": coach["coach_id"],
        "initiator_role": "coach",
        "interview_mode": "personalize",  # team_personalize / authoring land in Plan 6 UX
        "constraint_envelope_json": envelope,
        "candidate_template_ids": [c["block_template_id"] for c in candidates],
        "status": "in_progress",
    })
    return {"session_id": session_id, "candidates": candidates}


@router.post("/api/coach/programs/builder/generate")
def post_coach_builder_generate(req: CoachBuilderGenerateRequest,
                                  coach=Depends(require_coach_auth)):
    session = db.get_builder_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    pitcher = db.get_pitcher(session["pitcher_id"])
    if not pitcher or pitcher.get("team_id") != coach["team_id"]:
        raise HTTPException(status_code=403, detail="not your pitcher")

    template_id = req.chosen_template_id or (session.get("candidate_template_ids") or [None])[0]
    if not template_id:
        raise HTTPException(status_code=400, detail="no template chosen and no candidates")

    program = program_generator.generate_program(
        pitcher_id=session["pitcher_id"],
        template_id=template_id,
        tuned_spec=req.tuned_spec,
        constraint_envelope={
            **(session.get("constraint_envelope_json") or {}),
            "created_by": coach["coach_id"],
            "created_by_role": "coach",
        },
        session_id=req.session_id,
    )
    db.update_builder_session(req.session_id, {
        "chosen_template_id": template_id,
        "tuned_spec_json": req.tuned_spec,
        "status": "completed",
        "generated_program_id": program["program_id"],
    })
    return {"program": program}


@router.post("/api/coach/programs/{program_id}/activate")
def post_coach_program_activate(program_id: str, coach=Depends(require_coach_auth)):
    program = db.get_program(program_id)
    if not program:
        raise HTTPException(status_code=404, detail="program not found")
    pitcher = db.get_pitcher(program["pitcher_id"])
    if not pitcher or pitcher.get("team_id") != coach["team_id"]:
        raise HTTPException(status_code=403, detail="not your pitcher")
    return program_lifecycle.activate(program_id)


@router.post("/api/coach/programs/{program_id}/archive")
def post_coach_program_archive(program_id: str, req: ProgramArchiveRequest,
                                coach=Depends(require_coach_auth)):
    program = db.get_program(program_id)
    if not program:
        raise HTTPException(status_code=404, detail="program not found")
    pitcher = db.get_pitcher(program["pitcher_id"])
    if not pitcher or pitcher.get("team_id") != coach["team_id"]:
        raise HTTPException(status_code=403, detail="not your pitcher")
    return program_lifecycle.archive(program_id, reason=req.reason)
```

> Reuse `ProgramArchiveRequest` from `routes.py` if it's importable; otherwise duplicate the model.

- [ ] **Step 3: Smoke-test coach endpoints**

If existing coach-route tests use a fixture for an authenticated coach, extend them. If not, skip — Plan 6 will add UI-driven E2E coverage. Document this in the commit message.

- [ ] **Step 4: Commit**

```bash
git add pitcher_program_app/api/coach_routes.py
git commit -m "feat(api): coach mirror /api/coach/programs/builder/*

Same handlers as the pitcher-facing routes (Task 5) with require_coach_auth
+ team_id ownership check. Coach can build for any pitcher on their team.
team_personalize / authoring interview modes land in Plan 6 with the UI."
```

---

## Task 7: Final verification + tag

- [ ] **Step 1: Run full backend suite**

```bash
cd pitcher_program_app && PYTHONPATH=. pytest 2>&1 | tail -20
```

Expected: 340 (Plan 1 baseline) + ~33 new (6 db helpers + 8 candidates + 8 generator + 7 lifecycle + 4 endpoints) = ~373 PASS, 8 skipped, 0 failed.

- [ ] **Step 2: Update CLAUDE.md**

Append a row to the Phases table:

```markdown
| Plan 2 (PB) | Program Builder v1 — Builder Funnel Backend | 04-30 | Plan 2: Layer 1 (program_builder.match_candidates) + Layer 3 (program_generator.generate_program with hard-invariant validation + retry-once + failure logging) + Layer 4 (program_lifecycle.activate/archive with confirm-then-archive). Layer 2 stubbed — picks candidates[0]; Plan 3 replaces with Socratic. New API routes /api/programs/builder/* + /api/programs/{id}/{activate,archive} (pitcher) + /api/coach/programs/builder/* (coach mirror with team-scoping). 33 new tests, no regressions. |
```

- [ ] **Step 3: Tag**

```bash
git tag program-builder-v1-funnel-backend
```

- [ ] **Step 4: Commit doc updates**

```bash
git add CLAUDE.md
git commit -m "docs(claude.md): record Program Builder v1 Plan 2 completion"
```

---

## Self-Review

**Spec coverage:**
- ✅ Layer 1 candidate matching: Task 2
- ✅ Layer 3 generation + validation + retry-once + failure log: Task 3
- ✅ Layer 4 activate/archive (D9 confirm-then-archive): Task 4
- ✅ Pitcher-facing endpoints: Task 5
- ✅ Coach mirror endpoints: Task 6
- ⏭ Layer 2 Socratic interview: Plan 3 (stubbed here)
- ⏭ UI: Plan 6
- ⏭ Daily composition rewrite: Plan 4

**Open carry-overs:**
- Hard-invariant validation in v1 only checks `duration_mismatch`. Per-week volume caps, intensity-ramp monotonicity, and exercise existence are no-ops because the schedule is template-key based; they wake up in Plan 3 when the LLM produces actual exercise bindings.
- `created_by` semantics for coach-built programs flow through `constraint_envelope.created_by`. Worth a follow-up audit when the UI lands.

## Execution

Use superpowers:subagent-driven-development.
