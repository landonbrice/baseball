"""Program Engine v1 — LLM-forward program authoring (Task 3.1).

Public surface:
- `author_program(pitcher_profile, pitcher_context, goal_spec, knowledge_pack,
                  *, seed=None, previous_violations=None) -> PitcherProgram`

The brilliant-coach prompt lives at `bot/prompts/program_engine_author.md`.
The LLM is invoked through `bot.services.llm.call_llm_reasoning` (deepseek-reasoner,
120s timeout — L11 latency-tolerant).

On LLM timeout, parse failure, or schema validation error, raises
`GenerationFailure`. The orchestrator (Task 3.3) catches that and falls
back to the deterministic floor.

**Does NOT validate against guardrails** — that's the orchestrator's job.
This function's contract is: produce a schema-valid PitcherProgram OR raise.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from pydantic import ValidationError

from bot.services.llm import call_llm_reasoning, load_prompt
from bot.services.program_engine.schemas import PitcherProgram

logger = logging.getLogger(__name__)


class GenerationFailure(Exception):
    """Raised when LLM authoring cannot produce a schema-valid PitcherProgram.

    Carries a `reason` string the orchestrator surfaces in generation_provenance.
    """

    def __init__(self, reason: str, *, detail: Optional[str] = None):
        super().__init__(reason if not detail else f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail


_SYSTEM_PROMPT = (
    "You are a brilliant pitching coach authoring complete multi-week training "
    "programs as JSON. Emit ONLY valid JSON matching the PitcherProgram schema — "
    "no markdown, no prose, no fences. The downstream guardrails enforce the "
    "invariants; you focus on the program design."
)


def _format_profile_summary(profile: dict) -> str:
    """Compact profile summary for the prompt — keep the LLM context small.

    Pulls the fields the brilliant-coach prompt cares about: id, role, physical
    profile, injury_history summary, training preferences. JSONB nested dicts
    are flattened lightly; lists are bulleted.
    """
    if not profile:
        return "(no profile available)"
    lines: list[str] = []
    for key in ("pitcher_id", "name", "role", "throwing_hand"):
        v = profile.get(key)
        if v:
            lines.append(f"- {key}: {v}")
    phys = profile.get("physical_profile") or profile.get("physical") or {}
    if isinstance(phys, dict) and phys:
        lines.append("- physical_profile:")
        for k, v in phys.items():
            lines.append(f"    - {k}: {v}")
    training = profile.get("training") or {}
    if isinstance(training, dict) and training:
        lines.append("- training:")
        for k, v in training.items():
            if isinstance(v, (str, int, float, bool)):
                lines.append(f"    - {k}: {v}")
    injuries = profile.get("injury_history") or []
    if injuries:
        lines.append("- injury_history:")
        for inj in injuries[:10]:
            if isinstance(inj, dict):
                area = inj.get("area") or inj.get("injury_area") or "?"
                sev = inj.get("severity") or "?"
                status = inj.get("status") or "?"
                lines.append(f"    - {area} (severity={sev}, status={status})")
    return "\n".join(lines) if lines else "(profile fields empty)"


def _format_previous_violations(previous_violations: Optional[list]) -> str:
    """Format guardrail violations for the re-prompt path.

    `previous_violations` is a list of `GuardrailViolation` dataclasses OR dicts
    (both shapes accepted because callers may serialize before passing in).
    """
    if not previous_violations:
        return "(none — this is the first attempt)"
    lines: list[str] = []
    for v in previous_violations:
        if hasattr(v, "kind"):
            kind = getattr(v, "kind", "?")
            where = getattr(v, "where", {}) or {}
            actual = getattr(v, "actual", None)
            expected = getattr(v, "expected", None)
            hint = getattr(v, "repair_hint", None)
        else:
            kind = (v or {}).get("kind", "?")
            where = (v or {}).get("where", {})
            actual = (v or {}).get("actual")
            expected = (v or {}).get("expected")
            hint = (v or {}).get("repair_hint")
        line = f"- {kind} at {where}"
        if expected is not None:
            line += f" (expected={expected}"
            if actual is not None:
                line += f", actual={actual}"
            line += ")"
        if hint:
            line += f" — hint: {hint}"
        lines.append(line)
    return "\n".join(lines)


def _strip_json_fences(text: str) -> str:
    """Remove ```json ... ``` fences the LLM may have added despite instruction."""
    if not text:
        return text
    text = text.strip()
    # Common patterns: ```json\n...\n```  OR  ```\n...\n```
    m = re.match(r"^```(?:json|JSON)?\s*\n?(.*?)\n?```\s*$", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text


def _build_user_prompt(
    *,
    pitcher_profile: dict,
    pitcher_context: str,
    goal_spec: dict,
    knowledge_pack: dict,
    previous_violations: Optional[list],
) -> str:
    """Assemble the user prompt from the template + substitutions."""
    template = load_prompt("program_engine_author.md")
    combined = (knowledge_pack or {}).get("combined", "") or "(no knowledge pack)"
    profile_summary = _format_profile_summary(pitcher_profile or {})
    goal_json = json.dumps(goal_spec or {}, indent=2)
    violations_text = _format_previous_violations(previous_violations)
    user = template.replace("{knowledge_pack_combined}", combined)
    user = user.replace("{pitcher_profile_summary}", profile_summary)
    user = user.replace("{pitcher_context}", pitcher_context or "(no per-pitcher context)")
    user = user.replace("{goal_spec}", goal_json)
    user = user.replace("{previous_violations}", violations_text)
    return user


async def author_program(
    pitcher_profile: dict,
    pitcher_context: str,
    goal_spec: dict,
    knowledge_pack: dict,
    *,
    seed: Optional[int] = None,
    previous_violations: Optional[list] = None,
) -> PitcherProgram:
    """LLM-forward program authoring.

    Args:
        pitcher_profile: The pitcher's profile dict (id, role, physical_profile,
            injury_history, training preferences).
        pitcher_context: Free-form context string (the per-pitcher context.md).
        goal_spec: `{"tags": ["velocity"], "target_weeks": 12, "target_date": "...",
            "tunables": {...}}`.
        knowledge_pack: Output of `research_resolver.resolve_for_program_gen`.
            Must include `knowledge_version` + `combined` keys.
        seed: Optional integer for deterministic LLM sampling (reserved; not
            wired into call_llm_reasoning at v1 — kept for the test surface).
        previous_violations: When set, includes them in the prompt as
            "Your previous output had these issues; fix them" (re-prompt path
            used by Task 3.3).

    Returns:
        A schema-valid `PitcherProgram`. The `knowledge_version` field is
        stamped from `knowledge_pack["knowledge_version"]` AFTER parse — so
        the LLM's placeholder value is overwritten.

    Raises:
        GenerationFailure: On LLM timeout, malformed JSON, or schema validation
            failure. The orchestrator catches this and either re-prompts or
            falls back to the deterministic floor.
    """
    user_prompt = _build_user_prompt(
        pitcher_profile=pitcher_profile,
        pitcher_context=pitcher_context,
        goal_spec=goal_spec,
        knowledge_pack=knowledge_pack,
        previous_violations=previous_violations,
    )

    # Call the reasoning model (L11) — DeepSeek deepseek-reasoner, 120s timeout.
    try:
        raw = await call_llm_reasoning(
            system_prompt=_SYSTEM_PROMPT,
            user_message=user_prompt,
            max_tokens=8000,  # PitcherProgram with 12 weeks is large
        )
    except TimeoutError as e:
        logger.warning("author_program: LLM timeout (%s)", e)
        raise GenerationFailure("llm_timeout", detail=str(e)) from e
    except Exception as e:
        logger.warning("author_program: LLM error (%s)", e)
        raise GenerationFailure("llm_error", detail=str(e)) from e

    if not isinstance(raw, str) or not raw.strip():
        raise GenerationFailure("llm_empty_response")

    text = _strip_json_fences(raw)

    # Parse JSON
    try:
        # PitcherProgram.model_validate_json does both parse + validate in one
        # step, but we strip fences first so error messages are cleaner.
        program = PitcherProgram.model_validate_json(text)
    except ValidationError as e:
        logger.warning("author_program: schema validation failed (%s)", e)
        raise GenerationFailure("schema_validation_failed", detail=str(e)) from e
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("author_program: JSON parse failed (%s)", e)
        raise GenerationFailure("json_parse_failed", detail=str(e)) from e

    # Stamp knowledge_version from the pack — the LLM's placeholder is overwritten.
    kv = (knowledge_pack or {}).get("knowledge_version")
    if kv:
        program = program.model_copy(update={"knowledge_version": kv})

    return program
