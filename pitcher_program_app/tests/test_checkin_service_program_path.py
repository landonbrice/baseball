"""Tests for the program-aware fork in checkin_service.process_checkin (Plan 4 Task 4.5).

Verifies:
- Flag off → legacy path (existing behavior, goldens still pass)
- Flag on + active program → program path: compose, triage-adjust, write atomic
- Flag on + no active program → legacy path (cold-start)
- Program-path failure → log + auto-fall-through to legacy
"""
import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_flag_off_takes_legacy_path():
    from bot.services import checkin_service
    with patch.object(checkin_service, "_is_program_aware_enabled", return_value=False), \
         patch.object(checkin_service, "_legacy_plan_path",
                      new=AsyncMock(return_value={"source": "python_fallback"})), \
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
