"""Tests for program_aware_planner.compose_prescribed_plan and
apply_triage_to_program_plan (Plan 4 Tasks 4.1 + 4.2).

Pure functions — never call the LLM or DB; takes throwing_rx + lifting_rx +
profile (4.1) or prescribed plan + triage (4.2) as inputs.
"""
from datetime import date


def test_compose_with_throwing_and_lifting():
    from bot.services import program_aware_planner as pap
    throwing_rx = {"day_index": 3, "template_key": "day_3", "session": {"focus": "upper"}}
    lifting_rx = {"day_index": 8, "template_key": "lower_strength"}
    profile = {"pitcher_id": "landon_brice"}
    plan = pap.compose_prescribed_plan(throwing_rx, lifting_rx, profile, target_date=date(2026, 5, 1))
    assert plan["throwing"] is not None
    assert plan["lifting"] is not None
    assert plan["throwing"]["template_key"] == "day_3"
    assert plan["lifting"]["template_key"] == "lower_strength"
    assert plan["source"] == "program_prescribed"


def test_compose_with_only_throwing():
    from bot.services import program_aware_planner as pap
    throwing_rx = {"day_index": 3, "template_key": "day_3"}
    plan = pap.compose_prescribed_plan(throwing_rx, None, {}, date(2026, 5, 1))
    assert plan["throwing"] is not None
    assert plan["lifting"] is None
    assert plan["source"] == "program_prescribed"


def test_compose_with_neither_returns_none():
    """Caller is responsible for cold-start fallback when both rx are None."""
    from bot.services import program_aware_planner as pap
    plan = pap.compose_prescribed_plan(None, None, {}, date(2026, 5, 1))
    assert plan is None


def test_compose_includes_target_date():
    from bot.services import program_aware_planner as pap
    plan = pap.compose_prescribed_plan({"day_index": 0}, None, {}, date(2026, 5, 1))
    assert plan["target_date"] == "2026-05-01"


def test_compose_preserves_program_metadata():
    from bot.services import program_aware_planner as pap
    throwing_rx = {"day_index": 3, "template_key": "day_3", "session": {"focus": "upper"}, "date": "2026-05-01"}
    plan = pap.compose_prescribed_plan(throwing_rx, None, {}, date(2026, 5, 1))
    # Snapshot is preserved verbatim under program_prescription_snapshot
    assert plan["program_prescription_snapshot"]["throwing"] == throwing_rx


def test_apply_triage_green_returns_unmodified_with_advance():
    from bot.services import program_aware_planner as pap
    prescribed = {"throwing": {"template_key": "day_3"}, "lifting": {"template_key": "lower"}}
    triage = {"flag_level": "green", "modification_flags": []}
    final, hold_event = pap.apply_triage_to_program_plan(prescribed, triage)
    assert final["triage_flag"] == "green"
    assert hold_event is None  # advance, no hold
    assert final["throwing"] == prescribed["throwing"]
    assert final["lifting"] == prescribed["lifting"]


def test_apply_triage_yellow_advances_with_modification_tags():
    from bot.services import program_aware_planner as pap
    prescribed = {"throwing": {"template_key": "day_3"}, "lifting": {"template_key": "lower"}}
    triage = {"flag_level": "yellow", "modification_flags": ["fatigue_general"]}
    final, hold_event = pap.apply_triage_to_program_plan(prescribed, triage)
    assert final["triage_flag"] == "yellow"
    assert hold_event is None
    assert final["modification_flags"] == ["fatigue_general"]


def test_apply_triage_red_holds_counter_and_replaces_throwing_with_recovery():
    from bot.services import program_aware_planner as pap
    prescribed = {"throwing": {"template_key": "day_3", "session": {"intensity": "high"}},
                  "lifting": {"template_key": "lower_strength"}}
    triage = {"flag_level": "red", "modification_flags": ["arm_protect"]}
    final, hold_event = pap.apply_triage_to_program_plan(prescribed, triage)
    assert final["triage_flag"] == "red"
    assert hold_event is not None
    assert hold_event["reason_code"] == "red"
    # Throwing is replaced with a recovery shape
    assert final["throwing"]["recovery_only"] is True
    # Lifting trimmed to light
    assert final["lifting"]["intensity"] == "light"


def test_apply_triage_critical_red_shutdown_and_alert():
    from bot.services import program_aware_planner as pap
    prescribed = {"throwing": {"template_key": "day_3"},
                  "lifting": {"template_key": "lower_strength"}}
    triage = {"flag_level": "red", "modification_flags": ["arm_shutdown"],
              "arm_feel": 2}
    final, hold_event = pap.apply_triage_to_program_plan(prescribed, triage)
    assert final["throwing"]["shutdown"] is True
    assert hold_event["reason_code"] == "critical_red"
    assert final["auto_alert_coach"] is True


def test_apply_triage_red_with_no_throwing_still_holds():
    """Lifting-only program in Red still pauses the lifting counter."""
    from bot.services import program_aware_planner as pap
    prescribed = {"throwing": None,
                  "lifting": {"template_key": "lower_strength"}}
    triage = {"flag_level": "red", "modification_flags": []}
    final, hold_event = pap.apply_triage_to_program_plan(prescribed, triage)
    assert hold_event is not None
    assert final["lifting"]["intensity"] == "light"


# ---------------------------------------------------------------------------
# resolve_program_rotation_day — template_key / day_index extraction
# ---------------------------------------------------------------------------

def test_resolve_rotation_day_from_throwing_template_key():
    from bot.services import program_aware_planner as pap
    assert pap.resolve_program_rotation_day(
        {"template_key": "day_3", "day_index": 99},
        None,
    ) == 3


def test_resolve_rotation_day_falls_back_to_lifting_when_throwing_absent():
    from bot.services import program_aware_planner as pap
    assert pap.resolve_program_rotation_day(
        None,
        {"template_key": "day_5"},
    ) == 5


def test_resolve_rotation_day_throwing_wins_on_tie():
    from bot.services import program_aware_planner as pap
    # Throwing's day_3 wins over lifting's day_7
    assert pap.resolve_program_rotation_day(
        {"template_key": "day_3"},
        {"template_key": "day_7"},
    ) == 3


def test_resolve_rotation_day_falls_back_to_day_index_when_template_key_missing():
    from bot.services import program_aware_planner as pap
    assert pap.resolve_program_rotation_day(
        {"day_index": 4},
        None,
    ) == 4


def test_resolve_rotation_day_handles_non_day_template_key():
    """Template keys like 'lower_strength' have no numeric suffix → fall back."""
    from bot.services import program_aware_planner as pap
    assert pap.resolve_program_rotation_day(
        {"template_key": "lower_strength", "day_index": 2},
        None,
    ) == 2


def test_resolve_rotation_day_returns_none_when_both_rx_absent():
    from bot.services import program_aware_planner as pap
    assert pap.resolve_program_rotation_day(None, None) is None


# ---------------------------------------------------------------------------
# derive_hold_event — counter-hold decision (Approach B)
# ---------------------------------------------------------------------------

def test_derive_hold_event_green_returns_none():
    from bot.services import program_aware_planner as pap
    assert pap.derive_hold_event({"flag_level": "green"}) is None


def test_derive_hold_event_yellow_returns_none():
    from bot.services import program_aware_planner as pap
    assert pap.derive_hold_event({"flag_level": "yellow"}) is None


def test_derive_hold_event_red_returns_red_hold():
    from bot.services import program_aware_planner as pap
    hold = pap.derive_hold_event(
        {"flag_level": "red", "modification_flags": ["arm_protect"]}
    )
    assert hold is not None
    assert hold["reason_code"] == "red"


def test_derive_hold_event_red_with_arm_shutdown_is_critical():
    from bot.services import program_aware_planner as pap
    hold = pap.derive_hold_event(
        {"flag_level": "red", "modification_flags": ["arm_shutdown"]}
    )
    assert hold["reason_code"] == "critical_red"


def test_derive_hold_event_red_with_low_arm_feel_is_critical():
    from bot.services import program_aware_planner as pap
    hold = pap.derive_hold_event(
        {"flag_level": "red", "arm_feel": 2, "modification_flags": []}
    )
    assert hold["reason_code"] == "critical_red"


# ---------------------------------------------------------------------------
# compose_program_aware_plan — full enrichment via generate_plan
# ---------------------------------------------------------------------------

import pytest
from unittest.mock import patch, AsyncMock


def _legacy_plan_result_fixture():
    """Mirrors plan_generator.generate_plan's success return shape."""
    return {
        "narrative": "Day 3 plan ready.",
        "morning_brief": '{"coaching_note":"Felt good"}',
        "arm_care": {"timing": "pre-lift", "exercises": []},
        "lifting": {"intent": "strength", "exercises": [], "estimated_duration_min": 45},
        "throwing": {"type": "long_toss", "phases": []},
        "notes": ["sleep ok"],
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


@pytest.mark.asyncio
async def test_compose_program_aware_plan_returns_none_when_no_rx():
    from bot.services import program_aware_planner as pap
    plan = await pap.compose_program_aware_plan(
        pitcher_id="landon_brice",
        triage_result={"flag_level": "green"},
        throwing_rx=None,
        lifting_rx=None,
        profile={},
        target_date=date(2026, 5, 14),
    )
    assert plan is None


@pytest.mark.asyncio
async def test_compose_program_aware_plan_delegates_to_generate_plan_with_override():
    from bot.services import program_aware_planner as pap
    fixture = _legacy_plan_result_fixture()
    with patch.object(pap, "generate_plan", new=AsyncMock(return_value=fixture)) as gen:
        plan = await pap.compose_program_aware_plan(
            pitcher_id="landon_brice",
            triage_result={"flag_level": "green"},
            throwing_rx={"template_key": "day_3", "day_index": 3},
            lifting_rx=None,
            profile={},
            target_date=date(2026, 5, 14),
            checkin_inputs={"lift_preference": "auto"},
            triage_rationale_detail={"status_line": "ok"},
        )
    gen.assert_awaited_once()
    kwargs = gen.await_args.kwargs
    assert kwargs["rotation_day_override"] == 3
    assert kwargs["checkin_inputs"] == {"lift_preference": "auto"}
    assert kwargs["triage_rationale_detail"] == {"status_line": "ok"}
    # Source is promoted; full shape is preserved.
    assert plan["source"] == "program_prescribed"
    assert plan["narrative"] == "Day 3 plan ready."
    assert plan["warmup"] == {"phases": []}
    assert plan["exercise_blocks"] == [{"block_name": "Arm Care", "exercises": []}]


@pytest.mark.asyncio
async def test_compose_program_aware_plan_attaches_snapshot():
    from bot.services import program_aware_planner as pap
    throwing_rx = {"template_key": "day_3", "day_index": 3, "date": "2026-05-14"}
    lifting_rx = {"template_key": "lower_strength"}
    with patch.object(pap, "generate_plan", new=AsyncMock(return_value=_legacy_plan_result_fixture())):
        plan = await pap.compose_program_aware_plan(
            pitcher_id="landon_brice",
            triage_result={"flag_level": "green"},
            throwing_rx=throwing_rx,
            lifting_rx=lifting_rx,
            profile={},
            target_date=date(2026, 5, 14),
        )
    assert plan["program_prescription_snapshot"] == {
        "throwing": throwing_rx,
        "lifting": lifting_rx,
    }


@pytest.mark.asyncio
async def test_compose_program_aware_plan_preserves_source_reason_on_python_fallback():
    """When the legacy LLM step falls back to Python, source_reason carries the
    failure context. The program-aware wrapper promotes ``source`` but must not
    clobber ``source_reason`` — that's how we keep enrichment observability."""
    from bot.services import program_aware_planner as pap
    fixture = _legacy_plan_result_fixture()
    fixture["source"] = "python_fallback"
    fixture["source_reason"] = "llm_timeout:TimeoutError: deadline"
    with patch.object(pap, "generate_plan", new=AsyncMock(return_value=fixture)):
        plan = await pap.compose_program_aware_plan(
            pitcher_id="landon_brice",
            triage_result={"flag_level": "green"},
            throwing_rx={"template_key": "day_3"},
            lifting_rx=None,
            profile={},
            target_date=date(2026, 5, 14),
        )
    assert plan["source"] == "program_prescribed"
    assert plan["source_reason"] == "llm_timeout:TimeoutError: deadline"
