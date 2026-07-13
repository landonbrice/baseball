"""Tests for bot.services.program_engine.orchestrator (Task 3.3)."""
from __future__ import annotations

import json
from copy import deepcopy
from unittest.mock import AsyncMock, patch

import pytest

from bot.services.program_engine.author import GenerationFailure
from bot.services.program_engine.orchestrator import (
    GenerationResult,
    author_validate_persist,
)
from bot.services.program_engine.schemas import PitcherProgram


def _valid_program() -> PitcherProgram:
    """A 1-week program with balanced lifting on days 0-3 so FPM (4/7) +
    pull:push (2:1) checks pass under _tag_lookup."""
    balanced_lifting = [{
        "block_name": "B",
        "exercises": [
            {"exercise_id": "ex_001", "sets": 3, "reps": "8", "intensity": "80% 1RM"},  # pull
            {"exercise_id": "ex_020", "sets": 3, "reps": "8", "intensity": "80% 1RM"},  # pull
            {"exercise_id": "ex_025", "sets": 3, "reps": "8", "intensity": "80% 1RM"},  # push
            {"exercise_id": "ex_041", "sets": 3, "reps": "10", "intensity": "BW"},      # fpm
        ],
    }]
    days = []
    for i in range(7):
        d = {"day_index": i, "template_key": f"d_{i}", "date": f"2026-06-{i+1:02d}"}
        if i < 4:
            d["lifting_blocks"] = balanced_lifting
        days.append(d)
    return PitcherProgram.model_validate({
        "pitcher_id": "landon_brice", "goal": "velocity", "domain": "unified",
        "knowledge_version": "placeholder_abc12345",
        "generated_at": "2026-06-01T12:00:00",
        "target_date": "2026-08-24", "total_weeks": 1, "status": "draft",
        "phases": [{"phase_id": "base", "name": "Base", "week_count": 1, "intent_summary": "x", "phase_type": "base"}],
        "days": days,
        "rationale": {"phase_logic": "x", "individualization_notes": "x", "cited_research_doc_ids": ["x"]},
        "progression_state": {},
    })


def _velocity_block() -> dict:
    """Minimal block_library row the fallback can consume."""
    return {
        "block_template_id": "velocity_12wk_v1",
        "content": {
            "weeks": 12, "throws_per_week": 3,
            "phases": [{"name": "Base", "weeks": [1], "effort_pct": 50, "distances": ["45ft"], "total_throws_range": [40, 60]}],
            "acwr_governor": {"deload_weeks_default": []},
            "lifting_integration": {"phase_mapping": [{"throwing_phase_weeks": [1], "lifting_phase": "hypertrophy"}]},
        },
        "research_doc_ids": ["x"],
    }


def _ctx() -> dict:
    return {
        "exercises_rows": [
            {"id": "ex_001", "equipment": None, "contraindications": []},
            {"id": "ex_020", "equipment": None, "contraindications": []},
            {"id": "ex_025", "equipment": None, "contraindications": []},
            {"id": "ex_041", "equipment": None, "contraindications": []},
        ],
        "available_equipment": [],
        "active_modifications": [],
        "tag_lookup": {
            "ex_001": {"pull"},
            "ex_020": {"pull"},
            "ex_025": {"push"},
            "ex_041": {"fpm"},
        },
    }


_KV = "kv_orch_test_12345678"  # >= 8 chars to satisfy schema


@pytest.mark.asyncio
async def test_first_attempt_valid_returns_immediately():
    with patch("bot.services.program_engine.orchestrator.author_program", new=AsyncMock(return_value=_valid_program())):
        result = await author_validate_persist(
            pitcher_profile={"pitcher_id": "landon_brice"}, pitcher_context="",
            goal_spec={"tags": ["velocity"]}, knowledge_pack={"combined": "", "knowledge_version": _KV},
            pitcher_validation_ctx=_ctx(), block_library_row=_velocity_block(),
        )
    assert isinstance(result, GenerationResult)
    assert result.fallback_used is False
    assert len(result.attempts) == 1
    assert result.attempts[0]["status"] in ("valid", "repaired")
    assert result.knowledge_version == _KV
    assert result.program.generation_provenance.get("fallback_used") is False
    assert result.program.generation_provenance.get("attempts") == 1


@pytest.mark.asyncio
async def test_first_attempt_repaired_returns_immediately():
    """Phase-gate repair fires → status='repaired' → return."""
    # A program with high-intent in base phase that the orchestrator repairs.
    bad = deepcopy(_valid_program().model_dump())
    bad["days"][0]["intent_pct"] = 100  # Wk1 Day0 at 100% — gate violation
    bad_program = PitcherProgram.model_validate(bad)
    with patch("bot.services.program_engine.orchestrator.author_program", new=AsyncMock(return_value=bad_program)):
        result = await author_validate_persist(
            pitcher_profile={"pitcher_id": "p"}, pitcher_context="",
            goal_spec={"tags": ["velocity"]}, knowledge_pack={"combined": "", "knowledge_version": _KV},
            pitcher_validation_ctx=_ctx(), block_library_row=_velocity_block(),
        )
    assert result.fallback_used is False
    assert result.attempts[0]["status"] == "repaired"


@pytest.mark.asyncio
async def test_reject_then_reprompt_then_valid():
    """First attempt has unknown ex id (fatal) → reject → re-prompt → valid."""
    bad = deepcopy(_valid_program().model_dump())
    bad["days"][0]["lifting_blocks"] = [{
        "block_name": "B",
        "exercises": [{"exercise_id": "ex_999", "sets": 3, "reps": "8", "intensity": "80% 1RM"}],
    }]
    bad_program = PitcherProgram.model_validate(bad)
    good_program = _valid_program()

    call_counter = {"n": 0}
    async def author_mock(**kwargs):
        call_counter["n"] += 1
        return bad_program if call_counter["n"] == 1 else good_program

    with patch("bot.services.program_engine.orchestrator.author_program", new=author_mock):
        # Use _ctx() which knows about ex_001/ex_020/ex_025/ex_041 — ex_999
        # is not in rows → fatal on attempt 1; the good_program uses only
        # canonical ids and passes on attempt 2.
        result = await author_validate_persist(
            pitcher_profile={"pitcher_id": "p"}, pitcher_context="",
            goal_spec={"tags": ["velocity"]}, knowledge_pack={"combined": "", "knowledge_version": _KV},
            pitcher_validation_ctx=_ctx(), block_library_row=_velocity_block(),
        )
    assert result.fallback_used is False
    assert len(result.attempts) == 2
    assert result.attempts[0]["status"] == "reject"
    assert result.attempts[1]["status"] in ("valid", "repaired")


@pytest.mark.asyncio
async def test_all_attempts_rejected_falls_back():
    """All attempts return unknown exercise ids → fallback used."""
    bad = deepcopy(_valid_program().model_dump())
    bad["days"][0]["lifting_blocks"] = [{
        "block_name": "B",
        "exercises": [{"exercise_id": "ex_999", "sets": 3, "reps": "8", "intensity": "x"}],
    }]
    bad_program = PitcherProgram.model_validate(bad)
    with patch("bot.services.program_engine.orchestrator.author_program", new=AsyncMock(return_value=bad_program)):
        ctx = {**_ctx(), "exercises_rows": [{"id": "ex_001"}]}
        result = await author_validate_persist(
            pitcher_profile={"pitcher_id": "p"}, pitcher_context="",
            goal_spec={"tags": ["velocity"]}, knowledge_pack={"combined": "", "knowledge_version": _KV},
            pitcher_validation_ctx=ctx, block_library_row=_velocity_block(),
        )
    assert result.fallback_used is True
    assert result.program.generation_provenance.get("fallback_used") is True
    assert len(result.attempts) >= 1


@pytest.mark.asyncio
async def test_generation_failure_short_circuits_to_fallback():
    """LLM timeout on first attempt → straight to fallback (no re-prompt)."""
    with patch("bot.services.program_engine.orchestrator.author_program",
               new=AsyncMock(side_effect=GenerationFailure("llm_timeout"))):
        result = await author_validate_persist(
            pitcher_profile={"pitcher_id": "p"}, pitcher_context="",
            goal_spec={"tags": ["velocity"]}, knowledge_pack={"combined": "", "knowledge_version": _KV},
            pitcher_validation_ctx=_ctx(), block_library_row=_velocity_block(),
        )
    assert result.fallback_used is True
    assert result.attempts[0]["status"] == "generation_failure"
    assert result.attempts[0]["reason"] == "llm_timeout"


@pytest.mark.asyncio
async def test_max_reprompts_is_honored():
    """max_reprompts=0 → exactly 1 attempt, no re-prompts."""
    bad = deepcopy(_valid_program().model_dump())
    bad["days"][0]["lifting_blocks"] = [{
        "block_name": "B",
        "exercises": [{"exercise_id": "ex_999", "sets": 3, "reps": "8", "intensity": "x"}],
    }]
    bad_program = PitcherProgram.model_validate(bad)
    with patch("bot.services.program_engine.orchestrator.author_program", new=AsyncMock(return_value=bad_program)):
        ctx = {**_ctx(), "exercises_rows": [{"id": "ex_001"}]}
        result = await author_validate_persist(
            pitcher_profile={"pitcher_id": "p"}, pitcher_context="",
            goal_spec={"tags": ["velocity"]}, knowledge_pack={"combined": "", "knowledge_version": _KV},
            pitcher_validation_ctx=ctx, block_library_row=_velocity_block(),
            max_reprompts=0,
        )
    assert len(result.attempts) == 1
    assert result.fallback_used is True
