"""Tests for the program-aware fork in checkin_service (Plan 4 + Plan 6 / A1).

The fork was reorganized in Plan 6 / A1: instead of an early-return in
``process_checkin`` driven by a special ``checkin_inputs=`` kwarg shape, the
decision now lives in ``_select_plan_path`` and fires inline from the main
positional-arg pipeline after triage runs. Both legacy and program paths
converge into the same rich entry-persistence and weekly-state flow below.

Verifies the fork decision:
- Flag off                       → legacy ``generate_plan``
- Flag on, active program        → program path (``_compose_program_plan``)
- Flag on, no active program     → legacy
- Flag on, program-path failure  → log + auto-fall-through to legacy
"""
from datetime import date

import pytest
from unittest.mock import patch, AsyncMock


PROFILE = {"pitcher_id": "landon_brice", "name": "Landon Brice"}
TRIAGE = {"flag_level": "green", "modifications": []}
TARGET = date(2026, 5, 13)


@pytest.mark.asyncio
async def test_flag_off_takes_legacy_path():
    from bot.services import checkin_service
    with patch.object(checkin_service, "_is_program_aware_enabled", return_value=False), \
         patch.object(checkin_service, "_compose_program_plan",
                      new=AsyncMock()) as composer, \
         patch.object(checkin_service, "generate_plan",
                      new=AsyncMock(return_value={"source": "python_fallback"})):
        plan, program_id, hold = await checkin_service._select_plan_path(
            pitcher_id="landon_brice",
            triage_result=TRIAGE,
            profile=PROFILE,
            target_date=TARGET,
        )
    assert plan == {"source": "python_fallback"}
    assert program_id is None
    assert hold is None
    composer.assert_not_called()


@pytest.mark.asyncio
async def test_flag_on_with_active_program_takes_program_path():
    from bot.services import checkin_service
    composer_return = {
        "plan": {"source": "program_prescribed"},
        "program_id": "prog-uuid-1",
        "hold_event": None,
    }
    with patch.object(checkin_service, "_is_program_aware_enabled", return_value=True), \
         patch.object(checkin_service, "_has_any_active_program", return_value=True), \
         patch.object(checkin_service, "_compose_program_plan",
                      new=AsyncMock(return_value=composer_return)), \
         patch.object(checkin_service, "generate_plan",
                      new=AsyncMock()) as legacy:
        plan, program_id, hold = await checkin_service._select_plan_path(
            pitcher_id="landon_brice",
            triage_result=TRIAGE,
            profile=PROFILE,
            target_date=TARGET,
        )
    assert plan == {"source": "program_prescribed"}
    assert program_id == "prog-uuid-1"
    assert hold is None
    legacy.assert_not_called()


@pytest.mark.asyncio
async def test_flag_on_without_active_program_takes_legacy_path():
    from bot.services import checkin_service
    with patch.object(checkin_service, "_is_program_aware_enabled", return_value=True), \
         patch.object(checkin_service, "_has_any_active_program", return_value=False), \
         patch.object(checkin_service, "_compose_program_plan",
                      new=AsyncMock()) as composer, \
         patch.object(checkin_service, "generate_plan",
                      new=AsyncMock(return_value={"source": "python_fallback"})):
        plan, program_id, hold = await checkin_service._select_plan_path(
            pitcher_id="landon_brice",
            triage_result=TRIAGE,
            profile=PROFILE,
            target_date=TARGET,
        )
    assert plan == {"source": "python_fallback"}
    assert program_id is None
    assert hold is None
    composer.assert_not_called()


@pytest.mark.asyncio
async def test_program_path_logs_failure_and_falls_back_on_error():
    from bot.services import checkin_service
    with patch.object(checkin_service, "_is_program_aware_enabled", return_value=True), \
         patch.object(checkin_service, "_has_any_active_program", return_value=True), \
         patch.object(checkin_service, "_compose_program_plan",
                      new=AsyncMock(side_effect=RuntimeError("boom"))), \
         patch.object(checkin_service, "generate_plan",
                      new=AsyncMock(return_value={"source": "python_fallback"})), \
         patch.object(checkin_service, "_log_program_path_failure") as log:
        plan, program_id, hold = await checkin_service._select_plan_path(
            pitcher_id="landon_brice",
            triage_result=TRIAGE,
            profile=PROFILE,
            target_date=TARGET,
        )
    assert plan == {"source": "python_fallback"}
    assert program_id is None
    assert hold is None
    log.assert_called_once()


@pytest.mark.asyncio
async def test_program_path_propagates_hold_event_on_red_triage():
    """When triage paused the counter, the program path returns a hold_event
    that the caller must pass to write_daily_entry_with_counter_advance."""
    from bot.services import checkin_service
    composer_return = {
        "plan": {"source": "program_prescribed"},
        "program_id": "prog-uuid-1",
        "hold_event": {"reason": "red_flag", "triage_snapshot": {"flag_level": "red"}},
    }
    with patch.object(checkin_service, "_is_program_aware_enabled", return_value=True), \
         patch.object(checkin_service, "_has_any_active_program", return_value=True), \
         patch.object(checkin_service, "_compose_program_plan",
                      new=AsyncMock(return_value=composer_return)):
        _, program_id, hold = await checkin_service._select_plan_path(
            pitcher_id="landon_brice",
            triage_result={"flag_level": "red"},
            profile=PROFILE,
            target_date=TARGET,
        )
    assert program_id == "prog-uuid-1"
    assert hold == {"reason": "red_flag", "triage_snapshot": {"flag_level": "red"}}
