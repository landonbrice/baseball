"""Program Engine v1 — author + validate + repair + fallback orchestrator (Task 3.3).

Public surface:
- `author_validate_persist(...)` → `GenerationResult`

Pipeline:
  attempt 1 → author_program → validate_program
    valid|repaired → return
    reject       → re-prompt with violations (up to max_reprompts more attempts)
  if all attempts rejected OR any GenerationFailure on LAST attempt
    → build_fallback_program (always valid by construction)

Every attempt persisted to `program_generation_failures` for observability.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from bot.services.program_engine.author import GenerationFailure, author_program
from bot.services.program_engine.fallback import build_fallback_program
from bot.services.program_engine.guardrails import (
    ValidationResult,
    validate_program,
)
from bot.services.program_engine.schemas import PitcherProgram

logger = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    program: PitcherProgram
    attempts: list[dict] = field(default_factory=list)
    fallback_used: bool = False
    knowledge_version: str = ""


def _violation_to_dict(v) -> dict:
    """Coerce GuardrailViolation dataclass → plain dict for serialization."""
    return {
        "kind": getattr(v, "kind", None),
        "where": getattr(v, "where", None),
        "actual": getattr(v, "actual", None),
        "expected": getattr(v, "expected", None),
        "severity": getattr(v, "severity", None),
        "repair_hint": getattr(v, "repair_hint", None),
    }


async def _persist_attempt(
    *,
    pitcher_id: str,
    attempt_n: int,
    status: str,
    violations: Optional[list],
    reason: Optional[str],
):
    """Best-effort write to `program_generation_failures`. Never raises.

    Schema (from migration 020):
      program_generation_failures(id, pitcher_id, attempt_n, status, violations, reason, created_at)
    """
    try:
        from bot.services import db
        if hasattr(db, "insert_program_generation_failure"):
            await _maybe_await(db.insert_program_generation_failure(
                pitcher_id=pitcher_id,
                attempt_n=attempt_n,
                status=status,
                violations=violations,
                reason=reason,
            ))
    except Exception as e:
        logger.warning("orchestrator: persist_attempt failed (%s) — continuing", e)


async def _maybe_await(maybe_coro):
    """Allow `insert_program_generation_failure` to be sync or async."""
    import inspect
    if inspect.iscoroutine(maybe_coro):
        return await maybe_coro
    return maybe_coro


async def author_validate_persist(
    pitcher_profile: dict,
    pitcher_context: str,
    goal_spec: dict,
    knowledge_pack: dict,
    pitcher_validation_ctx: dict,
    *,
    block_library_row: dict,
    max_reprompts: int = 2,
    target_date: Optional[str] = None,
) -> GenerationResult:
    """End-to-end generation. Always returns a guardrail-valid program.

    Args:
        pitcher_profile: For author_program + provenance.
        pitcher_context: Per-pitcher context.md content.
        goal_spec: {"tags": [...], "target_weeks": N, "target_date": "...", ...}.
        knowledge_pack: Output of `research_resolver.resolve_for_program_gen`.
            Must include knowledge_version + combined.
        pitcher_validation_ctx: Passed to validate_program — must include
            exercises_rows, available_equipment, active_modifications, tag_lookup.
        block_library_row: Live block_library row for the goal's template;
            used as the fallback source.
        max_reprompts: Extra attempts after the first if the LLM is rejected.
            Total attempts = 1 + max_reprompts.
        target_date: Optional final-day date for fallback.

    Returns:
        GenerationResult with the always-valid program, attempt log, and
        fallback_used flag.
    """
    kv = (knowledge_pack or {}).get("knowledge_version", "")
    pitcher_id = (pitcher_profile or {}).get("pitcher_id") or "unknown"
    attempts: list[dict] = []
    previous_violations: Optional[list] = None

    total_tries = max_reprompts + 1
    for attempt_n in range(1, total_tries + 1):
        is_last = attempt_n == total_tries
        try:
            program = await author_program(
                pitcher_profile=pitcher_profile,
                pitcher_context=pitcher_context,
                goal_spec=goal_spec,
                knowledge_pack=knowledge_pack,
                previous_violations=previous_violations,
            )
        except GenerationFailure as e:
            attempts.append({
                "attempt_n": attempt_n,
                "status": "generation_failure",
                "reason": e.reason,
                "detail": e.detail,
            })
            await _persist_attempt(
                pitcher_id=pitcher_id, attempt_n=attempt_n,
                status="generation_failure", violations=None, reason=e.reason,
            )
            if is_last:
                break
            # Don't re-prompt on a GenerationFailure — the LLM is broken in
            # some way (timeout, malformed). Skip re-prompt, go to fallback.
            logger.warning("orchestrator: GenerationFailure on attempt %d, going to fallback", attempt_n)
            break

        result: ValidationResult = validate_program(program, pitcher_validation_ctx)
        attempts.append({
            "attempt_n": attempt_n,
            "status": result.status,
            "violations": [_violation_to_dict(v) for v in result.violations] if result.violations else [],
            "repair_log": result.repair_log,
        })
        await _persist_attempt(
            pitcher_id=pitcher_id, attempt_n=attempt_n,
            status=result.status,
            violations=[_violation_to_dict(v) for v in result.violations] if result.violations else None,
            reason=None,
        )

        if result.status in ("valid", "repaired"):
            program = result.program
            # Stamp provenance
            prov = dict(program.generation_provenance or {})
            prov["fallback_used"] = False
            prov["attempts"] = attempt_n
            prov["status"] = result.status
            program = program.model_copy(update={"generation_provenance": prov})
            return GenerationResult(
                program=program,
                attempts=attempts,
                fallback_used=False,
                knowledge_version=kv,
            )

        # status == "reject" — prepare re-prompt with the violations
        previous_violations = result.violations
        if is_last:
            break

    # Out of attempts — deterministic fallback
    logger.warning("orchestrator: all %d attempts rejected, using fallback", total_tries)
    fallback = build_fallback_program(
        pitcher_id=pitcher_id,
        goal_spec=goal_spec,
        block_library_row=block_library_row,
        knowledge_version=kv,
        target_date=target_date,
    )
    prov = dict(fallback.generation_provenance or {})
    prov["attempts"] = len(attempts)
    prov["reject_reason"] = "max_reprompts_exhausted"
    fallback = fallback.model_copy(update={"generation_provenance": prov})
    return GenerationResult(
        program=fallback,
        attempts=attempts,
        fallback_used=True,
        knowledge_version=kv,
    )
