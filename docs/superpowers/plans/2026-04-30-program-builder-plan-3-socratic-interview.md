# Program Builder v1 — Plan 3: Socratic Interview (Layer 2)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Replace Plan 2's `candidates[0]` stub with a real LLM-driven Socratic interview. The conversation persists turn-by-turn in `program_builder_sessions.turns_jsonb`. The LLM ends with a structured `READY_TO_GENERATE` directive containing `chosen_template_id` + `tuned_spec`. Validation: `tuned_spec` is checked against the chosen template's `tunable_parameters_schema`. On schema failure, the LLM is re-prompted with the error; two failures fall back to default tuning + log to `program_generation_failures`. Resume window: 24h since `last_activity_at`.

**Architecture:** New service `bot/services/program_builder_socratic.py` orchestrates the conversation. Three prompt variants in `bot/prompts/program_builder_<mode>.md` keyed by `interview_mode`: `personalize`, `team_personalize`, `authoring`. New endpoints `POST /api/programs/builder/turn` (advance the conversation) and `POST /api/programs/builder/finalize` (parse the LLM's `READY_TO_GENERATE` and call `generate_program`). The pitcher-facing `/api/programs/builder/generate` from Plan 2 stays for the deterministic candidates[0] path; new clients use `/turn` + `/finalize`.

**Tech Stack:** Python 3.11 / FastAPI / Pydantic / pytest. LLM via existing `bot/services/llm.py` (`call_llm` async). Prompts in `bot/prompts/`. No DB schema changes — Plan 1's `program_builder_sessions.turns_jsonb` carries everything.

**Builds on Plan 2 (`program-builder-v1-funnel-backend` tag):**
- `program_builder.match_candidates` (Layer 1)
- `program_generator.generate_program` (Layer 3)
- `db.create_builder_session` / `update_builder_session` / `get_builder_session`
- `db.record_generation_failure`
- `/api/programs/builder/candidates` (creates the session, populates `candidate_template_ids`)

---

## File Structure

**New:**
- `pitcher_program_app/bot/prompts/program_builder_personalize.md` — system prompt for player-mode Socratic
- `pitcher_program_app/bot/prompts/program_builder_team_personalize.md` — coach-mode for team programs
- `pitcher_program_app/bot/prompts/program_builder_authoring.md` — coach-mode for authoring new templates
- `pitcher_program_app/bot/services/program_builder_socratic.py` — turn orchestration + structured-output parsing + schema validation
- `pitcher_program_app/tests/test_program_builder_socratic.py`
- `pitcher_program_app/tests/test_program_builder_turn_endpoints.py`

**Modified:**
- `pitcher_program_app/api/routes.py` — add `/api/programs/builder/turn` + `/finalize` endpoints (pitcher)
- `pitcher_program_app/api/coach_routes.py` — add `/api/coach/programs/builder/turn` + `/finalize` (coach mirror)

---

## Task 1: Prompt files

> Three small markdown files. The system prompt rules are nearly identical; the differences are in framing (player vs. coach), and target audience for the questions. Keep each under ~80 lines.

**Files:**
- Create: `pitcher_program_app/bot/prompts/program_builder_personalize.md`
- Create: `pitcher_program_app/bot/prompts/program_builder_team_personalize.md`
- Create: `pitcher_program_app/bot/prompts/program_builder_authoring.md`

- [ ] **Step 1: Write `program_builder_personalize.md`**

```markdown
# Program Builder — Personalize (Player-Driven)

You are a baseball pitching coach helping a pitcher choose between 1–3 candidate training programs and tune the chosen one to their goals. The candidate templates are listed below. Your job is to ask 4–6 short questions that distinguish between candidates or fill in tunable parameters, then issue a structured `READY_TO_GENERATE` directive.

## Conversation rules

- **Maximum 6 questions total.** Hit `READY_TO_GENERATE` by question 6 even if you'd rather ask more.
- **Only ask questions that distinguish candidates or set tuning parameters.** Don't ask anything you can already infer from the pitcher's profile, injury history, recent arm feel, or WHOOP trend (all included in the context block).
- **Honor "I don't know — you decide" on every turn.** If the pitcher says any variant of that, pick the most defensible default for the question you just asked and move on.
- **One question per turn.** Don't bundle. Don't re-ask.
- **Don't propose templates that aren't in the candidate list.** You can recommend one of the 1–3 listed; you cannot invent.
- **No medical or mechanical advice.** Defer to the trainer / coaching staff for those.

## Output format

Every turn output one of these:

1. A single short question, in plain English, ending with a question mark. No preamble.

2. When you have enough information, output exactly:
   ```
   READY_TO_GENERATE
   {"chosen_template_id": "<one of the candidate ids>", "tuned_spec": {<parameters>}}
   ```
   Nothing else. The JSON must validate against the chosen template's `tunable_parameters_schema`.

## Context

{{CONTEXT_BLOCK}}

## Conversation so far

{{TURNS_BLOCK}}
```

- [ ] **Step 2: Write `program_builder_team_personalize.md`**

Same as above, but reframed for a coach asking about a whole team. The questions should be team-grain (e.g. "How many bullpens per week does the staff currently throw?") and the output `chosen_template_id` + `tuned_spec` apply to all pitchers in the fan-out.

- [ ] **Step 3: Write `program_builder_authoring.md`**

For authoring a NEW template. Different end shape — output is the template definition itself (a `block_library` row in JSON), not a `chosen_template_id`. End directive:

```
READY_TO_AUTHOR
{"name": "...", "domain": "...", "goal_tags": [...], "duration_range_weeks": "[lo,hi]", "compatible_phases": [...], "tunable_parameters_schema": {...}, "implied_phase": "...", "week_scaffold_json": {...}}
```

The orchestrator will ask the coach to confirm before INSERTing into `block_library`.

- [ ] **Step 4: Commit**

```bash
git add pitcher_program_app/bot/prompts/program_builder_*.md
git commit -m "feat(prompts): Socratic interview prompts for Program Builder

Three variants keyed by interview_mode: personalize (player), team_personalize
(coach for team), authoring (coach for new template). Each enforces 4–6
question cap, single question per turn, structured READY_TO_GENERATE /
READY_TO_AUTHOR end directive."
```

---

## Task 2: `program_builder_socratic.py` — orchestration

> Three responsibilities: (1) build the LLM context block from candidates + profile + recent triage, (2) call the LLM and append the turn to the session, (3) parse the LLM's response — either a question to relay to the user, or a `READY_TO_GENERATE` payload to validate.

**Files:**
- Create: `pitcher_program_app/bot/services/program_builder_socratic.py`
- Create: `pitcher_program_app/tests/test_program_builder_socratic.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for program_builder_socratic — Layer 2 orchestration."""

from unittest.mock import patch, AsyncMock
import json
import pytest


def _session(turns=None, mode="personalize", candidates=None):
    return {
        "session_id": "sess-1",
        "pitcher_id": "landon_brice",
        "interview_mode": mode,
        "constraint_envelope_json": {"domain": "throwing", "goal": "velocity",
                                     "duration_weeks": 12, "effective_phase": "preseason",
                                     "hard_constraints": []},
        "candidate_template_ids": candidates or ["tpl_a"],
        "turns_jsonb": turns or [],
        "status": "in_progress",
    }


def _template(tid="tpl_a", schema=None):
    return {
        "block_template_id": tid,
        "name": tid,
        "domain": "throwing",
        "tunable_parameters_schema": schema or {
            "weeks": {"type": "integer", "min": 8, "max": 12},
        },
    }


@pytest.mark.asyncio
async def test_advance_returns_ai_question():
    """LLM returns a plain question — orchestrator records the turn and returns it."""
    from bot.services import program_builder_socratic as sock
    with patch.object(sock, "_call_llm", new=AsyncMock(return_value="What's your usual bullpen frequency?")), \
         patch.object(sock, "_load_session", return_value=_session()), \
         patch.object(sock, "_load_candidate_templates", return_value=[_template()]), \
         patch.object(sock, "_load_pitcher_context", return_value={}), \
         patch.object(sock, "_persist_turns") as persist:
        result = await sock.advance("sess-1", user_message="I want to throw harder")
    assert result["kind"] == "question"
    assert "bullpen" in result["text"]
    persist.assert_called_once()


@pytest.mark.asyncio
async def test_advance_ready_to_generate_validates_against_schema():
    """LLM returns READY_TO_GENERATE with valid tuned_spec — passes validation."""
    from bot.services import program_builder_socratic as sock
    llm_payload = 'READY_TO_GENERATE\n{"chosen_template_id": "tpl_a", "tuned_spec": {"weeks": 10}}'
    with patch.object(sock, "_call_llm", new=AsyncMock(return_value=llm_payload)), \
         patch.object(sock, "_load_session", return_value=_session()), \
         patch.object(sock, "_load_candidate_templates", return_value=[_template()]), \
         patch.object(sock, "_load_pitcher_context", return_value={}), \
         patch.object(sock, "_persist_turns"):
        result = await sock.advance("sess-1", user_message="sounds good")
    assert result["kind"] == "ready"
    assert result["chosen_template_id"] == "tpl_a"
    assert result["tuned_spec"] == {"weeks": 10}


@pytest.mark.asyncio
async def test_advance_ready_to_generate_schema_failure_reprompts():
    """tuned_spec fails schema validation — orchestrator re-prompts the LLM with the error.
    Second LLM response succeeds."""
    from bot.services import program_builder_socratic as sock
    bad = 'READY_TO_GENERATE\n{"chosen_template_id": "tpl_a", "tuned_spec": {"weeks": 999}}'
    good = 'READY_TO_GENERATE\n{"chosen_template_id": "tpl_a", "tuned_spec": {"weeks": 10}}'
    mock_llm = AsyncMock(side_effect=[bad, good])
    with patch.object(sock, "_call_llm", new=mock_llm), \
         patch.object(sock, "_load_session", return_value=_session()), \
         patch.object(sock, "_load_candidate_templates", return_value=[_template()]), \
         patch.object(sock, "_load_pitcher_context", return_value={}), \
         patch.object(sock, "_persist_turns"):
        result = await sock.advance("sess-1", user_message="ok")
    assert result["kind"] == "ready"
    assert result["tuned_spec"] == {"weeks": 10}
    assert mock_llm.call_count == 2


@pytest.mark.asyncio
async def test_advance_two_schema_failures_fallback_to_defaults():
    """Two schema failures — fall back to default tuning, log failure."""
    from bot.services import program_builder_socratic as sock
    bad = 'READY_TO_GENERATE\n{"chosen_template_id": "tpl_a", "tuned_spec": {"weeks": 999}}'
    mock_llm = AsyncMock(side_effect=[bad, bad])
    with patch.object(sock, "_call_llm", new=mock_llm), \
         patch.object(sock, "_load_session", return_value=_session()), \
         patch.object(sock, "_load_candidate_templates", return_value=[_template()]), \
         patch.object(sock, "_load_pitcher_context", return_value={}), \
         patch.object(sock, "_persist_turns"), \
         patch.object(sock, "_record_failure") as rec:
        result = await sock.advance("sess-1", user_message="ok")
    assert result["kind"] == "ready"
    assert result["tuned_spec"] == sock.DEFAULT_TUNING
    rec.assert_called()


@pytest.mark.asyncio
async def test_advance_resume_after_24h_returns_expired():
    """Session inactive >24h is treated as abandoned. New conversation must start."""
    from datetime import datetime, timezone, timedelta
    from bot.services import program_builder_socratic as sock
    session = _session()
    session["last_activity_at"] = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    with patch.object(sock, "_load_session", return_value=session):
        with pytest.raises(LookupError, match="expired"):
            await sock.advance("sess-1", user_message="hi")


@pytest.mark.asyncio
async def test_advance_session_not_found():
    from bot.services import program_builder_socratic as sock
    with patch.object(sock, "_load_session", return_value=None):
        with pytest.raises(LookupError, match="not found"):
            await sock.advance("sess-nonexistent", user_message="hi")


def test_validate_against_schema_happy():
    from bot.services import program_builder_socratic as sock
    schema = {"weeks": {"type": "integer", "min": 8, "max": 12}}
    assert sock.validate_tuned_spec({"weeks": 10}, schema) == []


def test_validate_against_schema_min_max():
    from bot.services import program_builder_socratic as sock
    schema = {"weeks": {"type": "integer", "min": 8, "max": 12}}
    failures = sock.validate_tuned_spec({"weeks": 999}, schema)
    assert any("weeks" in f for f in failures)


def test_validate_against_schema_type():
    from bot.services import program_builder_socratic as sock
    schema = {"weeks": {"type": "integer", "min": 8, "max": 12}}
    failures = sock.validate_tuned_spec({"weeks": "twelve"}, schema)
    assert any("weeks" in f for f in failures)


def test_validate_against_schema_required_field_missing():
    from bot.services import program_builder_socratic as sock
    schema = {"weeks": {"type": "integer", "min": 8, "max": 12, "required": True}}
    failures = sock.validate_tuned_spec({}, schema)
    assert any("weeks" in f for f in failures)


def test_parse_llm_output_question():
    from bot.services import program_builder_socratic as sock
    parsed = sock.parse_llm_output("What is your favorite drill?")
    assert parsed["kind"] == "question"
    assert parsed["text"] == "What is your favorite drill?"


def test_parse_llm_output_ready():
    from bot.services import program_builder_socratic as sock
    payload = 'READY_TO_GENERATE\n{"chosen_template_id": "tpl_a", "tuned_spec": {"weeks": 10}}'
    parsed = sock.parse_llm_output(payload)
    assert parsed["kind"] == "ready"
    assert parsed["chosen_template_id"] == "tpl_a"


def test_parse_llm_output_malformed_json_in_ready():
    from bot.services import program_builder_socratic as sock
    payload = "READY_TO_GENERATE\n{not json"
    with pytest.raises(ValueError, match="json"):
        sock.parse_llm_output(payload)
```

- [ ] **Step 2: Run, expect FAIL**

Run: `cd pitcher_program_app && PYTHONPATH=. pytest tests/test_program_builder_socratic.py -v`

Expected: FAIL.

- [ ] **Step 3: Implement `pitcher_program_app/bot/services/program_builder_socratic.py`**

```python
"""Layer 2 of the Program Builder funnel: Socratic interview orchestration.

Single entry point — advance(session_id, user_message). Loads the session, builds
the LLM context, calls the LLM with the conversation history, parses the response.
If the response is a question, returns it for relay to the user. If it's
READY_TO_GENERATE, validates the tuned_spec against the chosen template's
tunable_parameters_schema and returns the parsed payload (caller passes it to
program_generator.generate_program). Schema-validation failure triggers a
re-prompt; two failures fall back to DEFAULT_TUNING and logs to
program_generation_failures.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from typing import Optional


DEFAULT_TUNING = {"weeks": 12}
MAX_SCHEMA_RETRIES = 2
SESSION_TTL_HOURS = 24


# ---- Seams for tests ----

async def _call_llm(system_prompt: str, user_message: str, history: list) -> str:
    from bot.services.llm import call_llm
    return await call_llm(system_prompt=system_prompt, user_message=user_message, history=history)


def _load_session(session_id: str) -> Optional[dict]:
    from bot.services import db
    return db.get_builder_session(session_id)


def _load_candidate_templates(template_ids: list[str]) -> list[dict]:
    from bot.services import db
    return [db.get_block_library_row(tid) for tid in template_ids if tid]


def _load_pitcher_context(pitcher_id: str) -> dict:
    """Load the lightweight context block stuffed into the system prompt."""
    from bot.services import db
    try:
        profile = db.get_pitcher(pitcher_id) or {}
    except KeyError:
        profile = {}
    model = db.get_pitcher_training_model(pitcher_id) or {}
    return {
        "profile": profile,
        "training_model": model,
    }


def _persist_turns(session_id: str, turns: list[dict]) -> None:
    from bot.services import db
    db.update_builder_session(session_id, {
        "turns_jsonb": turns,
        "last_activity_at": datetime.now(timezone.utc).isoformat(),
    })


def _record_failure(session_id: str | None, attempt_number: int, kind: str,
                     llm_response: dict | None = None) -> None:
    from bot.services import db
    db.record_generation_failure(
        session_id=session_id,
        attempt_number=attempt_number,
        validation_failure_kind=kind,
        llm_response=llm_response,
    )


# ---- Public functions ----

def parse_llm_output(text: str) -> dict:
    """Parse an LLM turn into either a question or a READY_TO_GENERATE payload."""
    s = text.strip()
    if s.startswith("READY_TO_GENERATE"):
        # Extract JSON after the directive
        body = s[len("READY_TO_GENERATE"):].strip()
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as e:
            raise ValueError(f"could not parse json after READY_TO_GENERATE: {e}")
        return {
            "kind": "ready",
            "chosen_template_id": payload.get("chosen_template_id"),
            "tuned_spec": payload.get("tuned_spec") or {},
        }
    if s.startswith("READY_TO_AUTHOR"):
        body = s[len("READY_TO_AUTHOR"):].strip()
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as e:
            raise ValueError(f"could not parse json after READY_TO_AUTHOR: {e}")
        return {"kind": "ready_to_author", "template": payload}
    return {"kind": "question", "text": s}


def validate_tuned_spec(tuned_spec: dict, schema: dict) -> list[str]:
    """Validate a tuned_spec dict against tunable_parameters_schema.

    Schema shape (per spec):
      {
        "<param>": {"type": "integer"|"number"|"string"|"boolean", "min": ..., "max": ..., "required": bool},
        ...
      }

    Returns a list of human-readable failure strings; empty = valid.
    """
    failures: list[str] = []
    for key, rule in (schema or {}).items():
        if rule.get("required") and key not in tuned_spec:
            failures.append(f"{key}: required but missing")
            continue
        if key not in tuned_spec:
            continue
        value = tuned_spec[key]
        expected_type = rule.get("type")
        if expected_type == "integer" and not isinstance(value, int):
            failures.append(f"{key}: expected integer, got {type(value).__name__}")
            continue
        if expected_type == "number" and not isinstance(value, (int, float)):
            failures.append(f"{key}: expected number, got {type(value).__name__}")
            continue
        if expected_type == "string" and not isinstance(value, str):
            failures.append(f"{key}: expected string, got {type(value).__name__}")
            continue
        if expected_type == "boolean" and not isinstance(value, bool):
            failures.append(f"{key}: expected boolean, got {type(value).__name__}")
            continue
        if "min" in rule and value < rule["min"]:
            failures.append(f"{key}: {value} below min {rule['min']}")
        if "max" in rule and value > rule["max"]:
            failures.append(f"{key}: {value} above max {rule['max']}")
    return failures


def _build_system_prompt(mode: str, candidates: list[dict], pitcher_context: dict) -> str:
    from bot.services.llm import load_prompt
    template = load_prompt(f"program_builder_{mode}.md")
    candidates_block = json.dumps([
        {"block_template_id": c["block_template_id"], "name": c.get("name"),
         "implied_phase": c.get("implied_phase"),
         "tunable_parameters_schema": c.get("tunable_parameters_schema") or {}}
        for c in candidates if c
    ], indent=2)
    context_block = json.dumps({
        "candidates": json.loads(candidates_block) if candidates_block else [],
        "pitcher": pitcher_context,
    }, indent=2)
    return template.replace("{{CONTEXT_BLOCK}}", context_block).replace("{{TURNS_BLOCK}}", "")


def _is_expired(session: dict) -> bool:
    last = session.get("last_activity_at")
    if not last:
        return False
    try:
        last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
    except ValueError:
        return False
    return datetime.now(timezone.utc) - last_dt > timedelta(hours=SESSION_TTL_HOURS)


def _history_from_turns(turns: list[dict]) -> list[dict]:
    """Convert the session's turns_jsonb into the {role, content} list call_llm expects."""
    return [{"role": t["role"], "content": t["content"]} for t in turns]


async def advance(session_id: str, user_message: str) -> dict:
    """Advance the Socratic conversation by one turn.

    Returns one of:
      - {"kind": "question", "text": str}  — relay to user
      - {"kind": "ready", "chosen_template_id": str, "tuned_spec": dict}
      - {"kind": "ready_to_author", "template": dict}  — only in authoring mode
    """
    session = _load_session(session_id)
    if not session:
        raise LookupError(f"session not found: {session_id}")
    if session.get("status") == "completed":
        raise ValueError(f"session already completed: {session_id}")
    if _is_expired(session):
        raise LookupError(f"session expired: {session_id}")

    candidates = _load_candidate_templates(session.get("candidate_template_ids") or [])
    pitcher_context = _load_pitcher_context(session["pitcher_id"])
    mode = session.get("interview_mode") or "personalize"
    system_prompt = _build_system_prompt(mode, candidates, pitcher_context)

    turns = list(session.get("turns_jsonb") or [])
    turns.append({"role": "user", "content": user_message})
    history = _history_from_turns(turns[:-1])  # everything before the latest user turn

    raw = await _call_llm(system_prompt, user_message, history)
    parsed = parse_llm_output(raw)
    turns.append({"role": "assistant", "content": raw})

    if parsed["kind"] == "ready":
        # Schema validation against the chosen candidate
        chosen = next((c for c in candidates if c and c["block_template_id"] == parsed["chosen_template_id"]),
                      None)
        if not chosen:
            _record_failure(session_id, 1, "chosen_template_not_in_candidates",
                            llm_response={"raw": raw})
            parsed = {"kind": "ready", "chosen_template_id": (candidates[0] or {}).get("block_template_id"),
                      "tuned_spec": DEFAULT_TUNING}
        else:
            schema = chosen.get("tunable_parameters_schema") or {}
            failures = validate_tuned_spec(parsed["tuned_spec"], schema)
            if failures:
                _record_failure(session_id, 1, "schema_validation:" + ";".join(failures),
                                llm_response={"raw": raw})
                # Re-prompt with the error
                error_msg = (
                    "Your previous response failed schema validation: "
                    + "; ".join(failures)
                    + ". Please reissue READY_TO_GENERATE with corrected tuned_spec."
                )
                turns.append({"role": "user", "content": error_msg})
                raw2 = await _call_llm(system_prompt, error_msg, _history_from_turns(turns[:-1]))
                turns.append({"role": "assistant", "content": raw2})
                parsed2 = parse_llm_output(raw2)
                if parsed2["kind"] != "ready":
                    parsed = {"kind": "ready", "chosen_template_id": chosen["block_template_id"],
                              "tuned_spec": DEFAULT_TUNING}
                    _record_failure(session_id, 2, "non_ready_after_reprompt",
                                    llm_response={"raw": raw2})
                else:
                    failures2 = validate_tuned_spec(parsed2["tuned_spec"], schema)
                    if failures2:
                        _record_failure(session_id, 2, "schema_validation:" + ";".join(failures2),
                                        llm_response={"raw": raw2})
                        parsed = {"kind": "ready", "chosen_template_id": chosen["block_template_id"],
                                  "tuned_spec": DEFAULT_TUNING}
                    else:
                        parsed = parsed2

    _persist_turns(session_id, turns)
    return parsed
```

- [ ] **Step 4: Run tests, expect PASS**

Run: `cd pitcher_program_app && PYTHONPATH=. pytest tests/test_program_builder_socratic.py -v`

Expected: ~12 PASS.

- [ ] **Step 5: Commit**

```bash
git add pitcher_program_app/bot/services/program_builder_socratic.py \
        pitcher_program_app/tests/test_program_builder_socratic.py
git commit -m "feat: program_builder_socratic.advance (Layer 2 orchestration)

Loads session, builds system prompt with candidates + pitcher context,
calls LLM, parses output (question vs READY_TO_GENERATE), validates
tuned_spec against template schema, re-prompts once on schema failure,
falls back to DEFAULT_TUNING on second failure with telemetry log.
24h resume TTL via last_activity_at."
```

---

## Task 3: API endpoints — `/turn` + `/finalize`

> Two new endpoints: `/turn` advances the conversation; `/finalize` accepts a final `READY_TO_GENERATE` outcome and calls `program_generator.generate_program`. The pitcher-facing client UI from Plan 6 will call `/turn` repeatedly until it gets a `kind: "ready"` response, then call `/finalize` with the chosen_template_id + tuned_spec.

**Files:**
- Modify: `pitcher_program_app/api/routes.py`
- Modify: `pitcher_program_app/api/coach_routes.py`
- Create: `pitcher_program_app/tests/test_program_builder_turn_endpoints.py`

- [ ] **Step 1: Write tests for the pitcher endpoints**

```python
"""Integration shape tests for /api/programs/builder/{turn,finalize}."""

import os
from unittest.mock import patch, AsyncMock
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DISABLE_AUTH", "true")
    from api import routes as routes_module
    monkeypatch.setattr(routes_module, "DISABLE_AUTH", True)
    from api.main import app
    return TestClient(app)


def test_post_builder_turn_returns_question(client):
    from bot.services import program_builder_socratic as sock
    with patch.object(sock, "advance",
                      new=AsyncMock(return_value={"kind": "question", "text": "What's your goal?"})):
        resp = client.post("/api/programs/builder/turn",
                           json={"session_id": "sess-1", "user_message": "hi"},
                           headers={"X-Test-Pitcher-Id": "landon_brice"})
    assert resp.status_code == 200
    assert resp.json() == {"kind": "question", "text": "What's your goal?"}


def test_post_builder_turn_returns_ready(client):
    from bot.services import program_builder_socratic as sock
    with patch.object(sock, "advance",
                      new=AsyncMock(return_value={
                          "kind": "ready",
                          "chosen_template_id": "tpl_a",
                          "tuned_spec": {"weeks": 12}})):
        resp = client.post("/api/programs/builder/turn",
                           json={"session_id": "sess-1", "user_message": "ok"},
                           headers={"X-Test-Pitcher-Id": "landon_brice"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["kind"] == "ready"
    assert body["chosen_template_id"] == "tpl_a"


def test_post_builder_finalize_calls_generate(client):
    from bot.services import program_generator, db
    fake_session = {"session_id": "sess-1", "pitcher_id": "landon_brice",
                    "constraint_envelope_json": {"start_date": "2026-05-01"}}
    fake_program = {"program_id": "prog-1", "status": "draft"}
    with patch.object(db, "get_builder_session", return_value=fake_session), \
         patch.object(program_generator, "generate_program", return_value=fake_program), \
         patch.object(db, "update_builder_session"):
        resp = client.post("/api/programs/builder/finalize",
                           json={"session_id": "sess-1", "chosen_template_id": "tpl_a",
                                 "tuned_spec": {"weeks": 12}},
                           headers={"X-Test-Pitcher-Id": "landon_brice"})
    assert resp.status_code == 200
    assert resp.json()["program"]["program_id"] == "prog-1"
```

- [ ] **Step 2: Run, expect FAIL**

Run: `cd pitcher_program_app && PYTHONPATH=. pytest tests/test_program_builder_turn_endpoints.py -v`

Expected: FAIL.

- [ ] **Step 3: Add the endpoints to `routes.py`**

In the Program Builder section added in Plan 2 Task 5, append:

```python
class BuilderTurnRequest(BaseModel):
    session_id: str
    user_message: str


class BuilderFinalizeRequest(BaseModel):
    session_id: str
    chosen_template_id: str
    tuned_spec: dict


@router.post("/programs/builder/turn")
async def post_builder_turn(req: BuilderTurnRequest, request: Request):
    pitcher_id = await _resolve_pitcher_id_from_request(request)
    session = db.get_builder_session(req.session_id)
    if not session or session["pitcher_id"] != pitcher_id:
        raise HTTPException(status_code=404, detail="session not found")
    try:
        from bot.services import program_builder_socratic
        return await program_builder_socratic.advance(req.session_id, req.user_message)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/programs/builder/finalize")
def post_builder_finalize(req: BuilderFinalizeRequest, request: Request):
    pitcher_id = _resolve_pitcher_id_from_request_sync(request)  # if helper is async, adapt
    session = db.get_builder_session(req.session_id)
    if not session or session["pitcher_id"] != pitcher_id:
        raise HTTPException(status_code=404, detail="session not found")
    program = program_generator.generate_program(
        pitcher_id=pitcher_id,
        template_id=req.chosen_template_id,
        tuned_spec=req.tuned_spec,
        constraint_envelope=session.get("constraint_envelope_json") or {},
        session_id=req.session_id,
    )
    db.update_builder_session(req.session_id, {
        "chosen_template_id": req.chosen_template_id,
        "tuned_spec_json": req.tuned_spec,
        "status": "completed",
        "generated_program_id": program["program_id"],
    })
    return {"program": program}
```

> If `_resolve_pitcher_id_from_request` from Plan 2 Task 5 is async, the implementer should `await` it and make `post_builder_finalize` async too. Adapt to actual auth helper shape.

- [ ] **Step 4: Add coach mirror endpoints to `coach_routes.py`**

Mirror `/api/coach/programs/builder/turn` and `/api/coach/programs/builder/finalize`. Same logic; team-scoped via the existing `require_coach_auth` + dereference-pitcher pattern from Plan 2 Task 6. Add tests if the existing coach test fixture supports them; otherwise document deferral.

- [ ] **Step 5: Run tests**

Run: `cd pitcher_program_app && PYTHONPATH=. pytest tests/test_program_builder_turn_endpoints.py -v`

Expected: 3 PASS (pitcher) + however many coach tests you added.

- [ ] **Step 6: Run full backend suite**

Expected: 379 (Plan 2 baseline) + 12 (Task 2) + 3-6 (Task 3) = ~394+ PASS / 8 skipped / 0 failed.

- [ ] **Step 7: Commit**

```bash
git add pitcher_program_app/api/routes.py \
        pitcher_program_app/api/coach_routes.py \
        pitcher_program_app/tests/test_program_builder_turn_endpoints.py
git commit -m "feat(api): /api/programs/builder/{turn,finalize}

/turn advances the Socratic conversation, returning either an AI
question or a READY_TO_GENERATE payload. /finalize accepts the
finalized payload and calls generate_program. Plan 2's /generate
stub remains for clients that prefer the candidates[0] path."
```

---

## Task 4: Final verification + tag

- [ ] **Step 1: Run full suite**

Expected ~395 PASS, 8 skipped, 0 failed.

- [ ] **Step 2: Update CLAUDE.md**

Append a row:

```markdown
| Plan 3 (PB) | Program Builder v1 — Socratic Interview (Layer 2) | 04-30 | Plan 3: replaces Plan 2's candidates[0] stub with a real LLM-driven Socratic interview. New module bot/services/program_builder_socratic.py orchestrates turn-by-turn conversation persisted in program_builder_sessions.turns_jsonb. Three prompt variants (personalize / team_personalize / authoring). Schema validation of tuned_spec against template's tunable_parameters_schema; re-prompt on failure; fallback to DEFAULT_TUNING after 2 failures with telemetry. New endpoints /api/programs/builder/{turn,finalize} (pitcher + coach mirror). 24h resume TTL via last_activity_at. |
```

- [ ] **Step 3: Tag**

```bash
git add CLAUDE.md
git commit -m "docs(claude.md): record Program Builder v1 Plan 3 completion"
git tag program-builder-v1-socratic
```

## Self-Review

**Spec coverage:**
- ✅ Layer 2 Socratic interview (Section 2 of design spec): Tasks 1-3
- ✅ 4-6 question cap, single-question-per-turn, structured READY_TO_GENERATE: prompt rules
- ✅ Schema validation + re-prompt: Task 2
- ✅ 24h resume window: `_is_expired` check
- ✅ Three interview modes: prompt files for all three
- ⏭ Hand-edit of generated weeks: out of v1 (D15)
- ⏭ Regeneration cap (3 hard, 2 soft warn): UI-side concern, lands in Plan 6

**Carry-overs to plan 4/6:**
- The system prompt's `{{TURNS_BLOCK}}` placeholder is left empty because we send conversation history via the LLM helper's `history` parameter instead. Worth confirming that approach is consistent with the rest of the codebase (`coach_chat_prompt.md` likely uses similar pattern).
- `READY_TO_AUTHOR` parsing exists but no endpoint actually calls into block_library inserting yet — that's a Plan 6 coach-app feature (template authoring).
- `DEFAULT_TUNING = {"weeks": 12}` is a magic constant; if templates need richer defaults, derive from `tunable_parameters_schema.<key>.default` in a follow-up.
