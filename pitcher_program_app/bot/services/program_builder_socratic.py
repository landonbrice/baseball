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
    try:
        db.record_generation_failure(
            session_id=session_id,
            attempt_number=attempt_number,
            validation_failure_kind=kind,
            llm_response=llm_response,
        )
    except Exception:
        # Telemetry; never let logging failure break the conversation.
        pass


# ---- Public functions ----

def parse_llm_output(text: str) -> dict:
    """Parse an LLM turn into either a question or a READY_TO_GENERATE payload."""
    s = text.strip()
    if s.startswith("READY_TO_GENERATE"):
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
    history = _history_from_turns(turns[:-1])

    raw = await _call_llm(system_prompt, user_message, history)
    parsed = parse_llm_output(raw)
    turns.append({"role": "assistant", "content": raw})

    if parsed["kind"] == "ready":
        chosen = next((c for c in candidates if c and c["block_template_id"] == parsed["chosen_template_id"]),
                      None)
        if not chosen:
            _record_failure(session_id, 1, "chosen_template_not_in_candidates",
                            llm_response={"raw": raw})
            parsed = {"kind": "ready",
                      "chosen_template_id": (candidates[0] or {}).get("block_template_id") if candidates else None,
                      "tuned_spec": DEFAULT_TUNING}
        else:
            schema = chosen.get("tunable_parameters_schema") or {}
            failures = validate_tuned_spec(parsed["tuned_spec"], schema)
            if failures:
                _record_failure(session_id, 1, "schema_validation:" + ";".join(failures),
                                llm_response={"raw": raw})
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
