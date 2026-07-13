"""Smoke test for bot.services.program_engine.author (Task 3.1)."""
from __future__ import annotations

import json
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from bot.services.program_engine.author import (
    GenerationFailure,
    _build_user_prompt,
    _format_previous_violations,
    _format_profile_summary,
    _strip_json_fences,
    author_program,
)


def _valid_program_json() -> str:
    """Minimal schema-valid PitcherProgram JSON the LLM might emit."""
    return json.dumps({
        "pitcher_id": "landon_brice",
        "goal": "velocity",
        "domain": "unified",
        "knowledge_version": "placeholder",
        "generated_at": "2026-06-01T12:00:00",
        "target_date": "2026-08-24",
        "total_weeks": 12,
        "status": "draft",
        "phases": [
            {"phase_id": "base", "name": "Base", "week_count": 12, "intent_summary": "x", "phase_type": "base"},
        ],
        "days": [
            {"day_index": 0, "template_key": "day_0", "date": "2026-06-01"},
        ],
        "rationale": {"phase_logic": "x", "individualization_notes": "x", "cited_research_doc_ids": ["x"]},
        "progression_state": {},
    })


@pytest.mark.asyncio
async def test_author_program_happy_path():
    """Valid LLM response → PitcherProgram with stamped knowledge_version."""
    with patch("bot.services.program_engine.author.call_llm_reasoning", new=AsyncMock(return_value=_valid_program_json())):
        program = await author_program(
            pitcher_profile={"pitcher_id": "landon_brice", "role": "Starter (7-day)"},
            pitcher_context="Test context",
            goal_spec={"tags": ["velocity"], "target_weeks": 12},
            knowledge_pack={"combined": "research text", "knowledge_version": "abc123"},
        )
    assert program.pitcher_id == "landon_brice"
    assert program.knowledge_version == "abc123"  # stamped, not the LLM's placeholder
    assert program.total_weeks == 12


@pytest.mark.asyncio
async def test_author_program_strips_json_fences():
    """LLM may wrap output in ```json ... ``` despite system prompt."""
    fenced = f"```json\n{_valid_program_json()}\n```"
    with patch("bot.services.program_engine.author.call_llm_reasoning", new=AsyncMock(return_value=fenced)):
        program = await author_program(
            pitcher_profile={"pitcher_id": "p"}, pitcher_context="", goal_spec={"tags": ["x"]},
            knowledge_pack={"combined": "", "knowledge_version": "k1"},
        )
    assert program.pitcher_id == "landon_brice"


@pytest.mark.asyncio
async def test_author_program_timeout_raises_generation_failure():
    with patch("bot.services.program_engine.author.call_llm_reasoning", new=AsyncMock(side_effect=TimeoutError("boom"))):
        with pytest.raises(GenerationFailure) as exc_info:
            await author_program(
                pitcher_profile={}, pitcher_context="", goal_spec={"tags": ["x"]},
                knowledge_pack={"combined": "", "knowledge_version": "k"},
            )
    assert exc_info.value.reason == "llm_timeout"


@pytest.mark.asyncio
async def test_author_program_malformed_json_raises():
    with patch("bot.services.program_engine.author.call_llm_reasoning", new=AsyncMock(return_value="not even json")):
        with pytest.raises(GenerationFailure) as exc_info:
            await author_program(
                pitcher_profile={}, pitcher_context="", goal_spec={"tags": ["x"]},
                knowledge_pack={"combined": "", "knowledge_version": "k"},
            )
    # Either json_parse_failed or schema_validation_failed depending on which catches first
    assert exc_info.value.reason in {"json_parse_failed", "schema_validation_failed"}


@pytest.mark.asyncio
async def test_author_program_empty_response_raises():
    with patch("bot.services.program_engine.author.call_llm_reasoning", new=AsyncMock(return_value="")):
        with pytest.raises(GenerationFailure) as exc_info:
            await author_program(
                pitcher_profile={}, pitcher_context="", goal_spec={"tags": ["x"]},
                knowledge_pack={"combined": "", "knowledge_version": "k"},
            )
    assert exc_info.value.reason == "llm_empty_response"


@pytest.mark.asyncio
async def test_author_program_schema_invalid_raises():
    bad = json.dumps({"pitcher_id": "p", "goal": "velocity"})  # missing required fields
    with patch("bot.services.program_engine.author.call_llm_reasoning", new=AsyncMock(return_value=bad)):
        with pytest.raises(GenerationFailure) as exc_info:
            await author_program(
                pitcher_profile={}, pitcher_context="", goal_spec={"tags": ["x"]},
                knowledge_pack={"combined": "", "knowledge_version": "k"},
            )
    assert exc_info.value.reason == "schema_validation_failed"


@pytest.mark.asyncio
async def test_author_program_includes_previous_violations_in_prompt():
    """Re-prompt path: previous_violations is woven into the user prompt."""
    captured = {}
    async def _capture(system_prompt, user_message, max_tokens):
        captured["user_message"] = user_message
        return _valid_program_json()

    with patch("bot.services.program_engine.author.call_llm_reasoning", new=_capture):
        await author_program(
            pitcher_profile={}, pitcher_context="", goal_spec={"tags": ["x"]},
            knowledge_pack={"combined": "", "knowledge_version": "k"},
            previous_violations=[{"kind": "acwr_hard_cap_exceeded", "where": {"day_index": 30}, "actual": 1.7, "expected": "≤ 1.5"}],
        )
    assert "acwr_hard_cap_exceeded" in captured["user_message"]
    assert "day_index" in captured["user_message"]


def test_strip_json_fences_plain():
    assert _strip_json_fences('{"a": 1}') == '{"a": 1}'


def test_strip_json_fences_with_fences():
    assert _strip_json_fences('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert _strip_json_fences('```\n{"a": 1}\n```') == '{"a": 1}'


def test_format_profile_summary_handles_empty():
    assert "no profile" in _format_profile_summary({})


def test_format_profile_summary_compacts_known_keys():
    s = _format_profile_summary({"pitcher_id": "landon_brice", "role": "Starter (7-day)", "physical_profile": {"height": "6ft"}})
    assert "landon_brice" in s
    assert "Starter" in s
    assert "height" in s


def test_format_previous_violations_handles_none():
    assert "first attempt" in _format_previous_violations(None)


def test_format_previous_violations_handles_dataclasses():
    """GuardrailViolation dataclasses work via attribute access."""
    from bot.services.program_engine.load_math import GuardrailViolation
    v = GuardrailViolation(kind="x", where={"day": 1}, actual=1.7, expected="<=1.5", repair_hint="clip")
    s = _format_previous_violations([v])
    assert "x" in s
    assert "day" in s
    assert "clip" in s
