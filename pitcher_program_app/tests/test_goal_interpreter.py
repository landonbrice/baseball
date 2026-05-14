"""Service-layer tests for the LLM goal interpreter (Plan 7 / A11)."""
from unittest.mock import patch, AsyncMock

import pytest

from bot.services import goal_interpreter


@pytest.mark.asyncio
async def test_interpret_goal_returns_matched_tag():
    rows = [{"goal_tags": ["velocity", "longtoss"]}]
    with patch.object(goal_interpreter, "db") as db_mock:
        db_mock.get_client.return_value.table.return_value.select.return_value \
              .eq.return_value.execute.return_value.data = rows
        with patch("bot.services.llm.call_llm",
                   new=AsyncMock(return_value="velocity")):
            out = await goal_interpreter.interpret_goal("I want to throw harder", "throwing")
    assert out == "velocity"


@pytest.mark.asyncio
async def test_interpret_goal_returns_unknown_when_llm_fabricates():
    rows = [{"goal_tags": ["velocity"]}]
    with patch.object(goal_interpreter, "db") as db_mock:
        db_mock.get_client.return_value.table.return_value.select.return_value \
              .eq.return_value.execute.return_value.data = rows
        with patch("bot.services.llm.call_llm",
                   new=AsyncMock(return_value="hypertrophy")):
            out = await goal_interpreter.interpret_goal("hyper", "throwing")
    assert out == "unknown"


@pytest.mark.asyncio
async def test_interpret_goal_returns_unknown_on_llm_error():
    rows = [{"goal_tags": ["velocity"]}]
    with patch.object(goal_interpreter, "db") as db_mock:
        db_mock.get_client.return_value.table.return_value.select.return_value \
              .eq.return_value.execute.return_value.data = rows
        with patch("bot.services.llm.call_llm",
                   new=AsyncMock(side_effect=TimeoutError("boom"))):
            out = await goal_interpreter.interpret_goal("anything", "throwing")
    assert out == "unknown"


@pytest.mark.asyncio
async def test_interpret_goal_empty_text_returns_unknown():
    out = await goal_interpreter.interpret_goal("   ", "throwing")
    assert out == "unknown"


@pytest.mark.asyncio
async def test_interpret_goal_rejects_bad_domain():
    with pytest.raises(ValueError):
        await goal_interpreter.interpret_goal("anything", "mobility")
