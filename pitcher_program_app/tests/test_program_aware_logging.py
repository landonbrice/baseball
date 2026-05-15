"""Plan 8 / A2 — structured logging contract on program-aware compose.

Every program-aware compose call must emit ONE structured ``program_aware_compose``
log event so the 9am digest's D2 canary metric can aggregate "% on program path
vs legacy". The dispatcher's legacy fall-through emits the same shape with
sentinel ``plan_source='legacy_path_selected'`` so a single log filter covers
both branches.
"""

from datetime import date
from unittest.mock import patch, AsyncMock

import pytest


def _legacy_plan_result_fixture():
    """Mirrors plan_generator.generate_plan's success return shape."""
    return {
        "narrative": "Day 3 plan ready.",
        "morning_brief": '{"coaching_note":"Felt good"}',
        "arm_care": {"timing": "pre-lift", "exercises": []},
        "lifting": {
            "intent": "strength",
            "exercises": [
                {"name": "Squat", "sets": 3, "reps": 5},
                {"name": "Bench Press", "sets": 3, "reps": 5},
                {"name": "Row", "sets": 3, "reps": 8},
            ],
            "estimated_duration_min": 45,
        },
        "throwing": {"type": "long_toss", "phases": []},
        "notes": [],
        "soreness_response": None,
        "exercise_blocks": [{"block_name": "Arm Care", "exercises": []}],
        "throwing_plan": {"type": "long_toss"},
        "warmup": {"phases": []},
        "mobility": {"videos": []},
        "estimated_duration_min": 45,
        "modifications_applied": [],
        "template_day": "day_3",
        "source": "llm_enriched",
        "source_reason": None,
        "day_focus": "upper",
        "research_sources": [],
    }


def _find_compose_records(caplog):
    """Filter caplog for the structured event we emit. Both the planner and
    the dispatcher legacy branch use msg='program_aware_compose'."""
    return [
        r for r in caplog.records
        if r.getMessage() == "program_aware_compose"
    ]


@pytest.mark.asyncio
async def test_compose_program_aware_plan_emits_structured_log(caplog):
    """Happy-path program compose must emit exactly ONE event with the full
    contract: pitcher_id, program_id, template_key, plan_source='program_prescribed',
    narrative_present=True, lifting_exercises_count=3.
    """
    import logging
    from bot.services import program_aware_planner as pap

    caplog.set_level(logging.INFO, logger="bot.services.program_aware_planner")

    with patch.object(
        pap, "generate_plan",
        new=AsyncMock(return_value=_legacy_plan_result_fixture()),
    ):
        plan = await pap.compose_program_aware_plan(
            pitcher_id="landon_brice",
            triage_result={"flag_level": "green"},
            throwing_rx={"template_key": "day_3", "day_index": 3},
            lifting_rx=None,
            profile={},
            target_date=date(2026, 5, 14),
            program_id="prog-uuid-1",
        )

    assert plan is not None
    records = _find_compose_records(caplog)
    assert len(records) == 1, (
        f"expected exactly 1 program_aware_compose event, got {len(records)}"
    )
    rec = records[0]
    assert rec.event == "program_aware_compose"
    assert rec.pitcher_id == "landon_brice"
    assert rec.program_id == "prog-uuid-1"
    assert rec.template_key == "day_3"
    assert rec.current_day_index == 3
    assert rec.rotation_day_resolved == 3
    assert rec.domain == "throwing"
    assert rec.plan_source == "program_prescribed"
    assert rec.plan_source_reason is None
    assert rec.narrative_present is True
    assert rec.lifting_exercises_count == 3


@pytest.mark.asyncio
async def test_compose_program_aware_plan_log_domain_both_when_both_rx_present(
    caplog,
):
    import logging
    from bot.services import program_aware_planner as pap

    caplog.set_level(logging.INFO, logger="bot.services.program_aware_planner")

    with patch.object(
        pap, "generate_plan",
        new=AsyncMock(return_value=_legacy_plan_result_fixture()),
    ):
        await pap.compose_program_aware_plan(
            pitcher_id="landon_brice",
            triage_result={"flag_level": "green"},
            throwing_rx={"template_key": "day_3", "day_index": 3},
            lifting_rx={"template_key": "lower_strength", "day_index": 7},
            profile={},
            target_date=date(2026, 5, 14),
            program_id="prog-uuid-1",
        )

    records = _find_compose_records(caplog)
    assert len(records) == 1
    # Throwing wins on tie for rotation_day_resolved (see resolve_program_rotation_day),
    # but `domain` is 'both' since both rx are present.
    assert records[0].domain == "both"
    assert records[0].rotation_day_resolved == 3


@pytest.mark.asyncio
async def test_compose_program_aware_plan_emits_log_on_python_fallback(caplog):
    """When the LLM step falls back to Python, source_reason populates and the
    structured event preserves that observability."""
    import logging
    from bot.services import program_aware_planner as pap

    caplog.set_level(logging.INFO, logger="bot.services.program_aware_planner")

    fallback = _legacy_plan_result_fixture()
    fallback["source"] = "python_fallback"
    fallback["source_reason"] = "llm_timeout:TimeoutError"

    with patch.object(
        pap, "generate_plan", new=AsyncMock(return_value=fallback),
    ):
        await pap.compose_program_aware_plan(
            pitcher_id="landon_brice",
            triage_result={"flag_level": "green"},
            throwing_rx={"template_key": "day_3", "day_index": 3},
            lifting_rx=None,
            profile={},
            target_date=date(2026, 5, 14),
            program_id="prog-uuid-1",
        )

    records = _find_compose_records(caplog)
    assert len(records) == 1
    # Source gets promoted to program_prescribed by the planner.
    assert records[0].plan_source == "program_prescribed"
    # But source_reason is preserved verbatim from the legacy enrichment.
    assert records[0].plan_source_reason == "llm_timeout:TimeoutError"


PROFILE = {"pitcher_id": "landon_brice", "name": "Landon Brice"}
TRIAGE = {"flag_level": "green", "modifications": []}
TARGET = date(2026, 5, 13)


@pytest.mark.asyncio
async def test_select_plan_path_legacy_flag_off_emits_structured_log(caplog):
    """When the flag is off, the dispatcher emits the same event shape with
    sentinel ``plan_source='legacy_path_selected'`` and reason ``flag_off``."""
    import logging
    from bot.services import checkin_service

    caplog.set_level(logging.INFO, logger="bot.services.checkin_service")

    with patch.object(
        checkin_service, "_is_program_aware_enabled", return_value=False,
    ), patch.object(
        checkin_service, "_compose_program_plan", new=AsyncMock(),
    ) as composer, patch.object(
        checkin_service, "generate_plan",
        new=AsyncMock(return_value={"source": "python_fallback"}),
    ):
        await checkin_service._select_plan_path(
            pitcher_id="landon_brice",
            triage_result=TRIAGE,
            profile=PROFILE,
            target_date=TARGET,
        )

    composer.assert_not_called()
    records = _find_compose_records(caplog)
    assert len(records) == 1
    assert records[0].plan_source == "legacy_path_selected"
    assert records[0].plan_source_reason == "flag_off"
    assert records[0].pitcher_id == "landon_brice"
    assert records[0].program_id is None
    assert records[0].lifting_exercises_count == 0
    assert records[0].narrative_present is False


@pytest.mark.asyncio
async def test_select_plan_path_no_active_program_emits_structured_log(caplog):
    """Flag on but no active program → legacy + reason='no_active_program'."""
    import logging
    from bot.services import checkin_service

    caplog.set_level(logging.INFO, logger="bot.services.checkin_service")

    with patch.object(
        checkin_service, "_is_program_aware_enabled", return_value=True,
    ), patch.object(
        checkin_service, "_has_any_active_program", return_value=False,
    ), patch.object(
        checkin_service, "_compose_program_plan", new=AsyncMock(),
    ), patch.object(
        checkin_service, "generate_plan",
        new=AsyncMock(return_value={"source": "python_fallback"}),
    ):
        await checkin_service._select_plan_path(
            pitcher_id="landon_brice",
            triage_result=TRIAGE,
            profile=PROFILE,
            target_date=TARGET,
        )

    records = _find_compose_records(caplog)
    assert len(records) == 1
    assert records[0].plan_source == "legacy_path_selected"
    assert records[0].plan_source_reason == "no_active_program"


@pytest.mark.asyncio
async def test_select_plan_path_program_failure_emits_legacy_log_with_reason(
    caplog,
):
    """Flag on, program path raised → log + auto-fall-through to legacy.
    The dispatcher's legacy fall-through emits the structured event with
    reason='program_path_failed' so D2 can count these too.
    """
    import logging
    from bot.services import checkin_service

    caplog.set_level(logging.INFO, logger="bot.services.checkin_service")

    with patch.object(
        checkin_service, "_is_program_aware_enabled", return_value=True,
    ), patch.object(
        checkin_service, "_has_any_active_program", return_value=True,
    ), patch.object(
        checkin_service, "_compose_program_plan",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ), patch.object(
        checkin_service, "generate_plan",
        new=AsyncMock(return_value={"source": "python_fallback"}),
    ), patch.object(
        checkin_service, "_log_program_path_failure",
    ):
        await checkin_service._select_plan_path(
            pitcher_id="landon_brice",
            triage_result=TRIAGE,
            profile=PROFILE,
            target_date=TARGET,
        )

    records = _find_compose_records(caplog)
    assert len(records) == 1
    assert records[0].plan_source == "legacy_path_selected"
    assert records[0].plan_source_reason == "program_path_failed"


@pytest.mark.asyncio
async def test_select_plan_path_program_path_does_not_emit_legacy_log(caplog):
    """When the program path succeeds, the dispatcher must NOT emit the
    legacy event — the planner emits its own structured event instead."""
    import logging
    from bot.services import checkin_service

    caplog.set_level(logging.INFO, logger="bot.services.checkin_service")

    composer_return = {
        "plan": {"source": "program_prescribed"},
        "program_id": "prog-uuid-1",
        "hold_event": None,
    }
    with patch.object(
        checkin_service, "_is_program_aware_enabled", return_value=True,
    ), patch.object(
        checkin_service, "_has_any_active_program", return_value=True,
    ), patch.object(
        checkin_service, "_compose_program_plan",
        new=AsyncMock(return_value=composer_return),
    ):
        await checkin_service._select_plan_path(
            pitcher_id="landon_brice",
            triage_result=TRIAGE,
            profile=PROFILE,
            target_date=TARGET,
        )

    # The dispatcher must NOT emit a `legacy_path_selected` event here —
    # the planner emits its own with plan_source='program_prescribed'.
    # We mocked _compose_program_plan, so no planner event is fired in this
    # test either. The contract being verified is that the dispatcher
    # short-circuits before reaching the legacy emit when the program path
    # returned.
    legacy_records = [
        r for r in _find_compose_records(caplog)
        if getattr(r, "plan_source", None) == "legacy_path_selected"
    ]
    assert legacy_records == []
