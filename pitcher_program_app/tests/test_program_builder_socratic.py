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
