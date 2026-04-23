"""F4 checkin_service integration tests — rationale persists through the pipeline,
failures are non-fatal, kill-switch works."""
from unittest.mock import AsyncMock, patch

import pytest


BASE_TRIAGE = {
    "flag_level": "green",
    "modifications": [],
    "alerts": [],
    "category_scores": {"tissue": 8, "load": 8, "recovery": 8},
    "baseline_tier": 2,
    "protocol_adjustments": {},
    "trajectory_context": {},
    "reasoning": "",
}

BASE_PLAN = {
    "narrative": "n",
    "morning_brief": "m",
    "arm_care": None,
    "lifting": {"exercises": [
        {"id": "ex_1", "name": "Squat", "sets": 3, "reps": 5},
        {"id": "ex_2", "name": "Row", "sets": 3, "reps": 8},
    ]},
    "throwing": None,
    "throwing_plan": None,
    "bullpen": None,
    "warmup": None,
    "notes": [],
    "soreness_response": None,
    "exercise_blocks": [],
    "modifications_applied": [],
    "estimated_duration_min": 45,
    "source": "llm_enriched",
    "source_reason": None,
    "day_focus": "lift",
    "template_day": "day_3",
}


def _fake_profile():
    return {
        "pitcher_id": "x",
        "name": "X",
        "role": "starter",
        "rotation_length": 7,
        "active_flags": {
            "days_since_outing": 3,
            "current_arm_feel": 7,
            "active_modifications": [],
            "grip_drop_reported": False,
        },
        "injury_history": [],
    }


def _baseline():
    return {
        "baseline_state": "full",
        "total_check_ins": 30,
        "tier": 2,
        "overall_mean": 8.0,
    }


def _patches(triage_result, plan_result, extra_rationale_patch=None):
    """Build the common patch stack."""
    stack = [
        patch("bot.services.checkin_service.load_profile", return_value=_fake_profile()),
        patch(
            "bot.services.checkin_service.load_training_model",
            return_value={"baseline_snapshot": {}},
        ),
        patch("bot.services.checkin_service.get_daily_entries", return_value=[]),
        patch("bot.services.checkin_service.update_training_model_partial"),
        patch(
            "bot.services.checkin_service.get_or_refresh_baseline",
            return_value=_baseline(),
        ),
        patch("bot.services.checkin_service.triage", return_value=dict(triage_result)),
        patch(
            "bot.services.checkin_service.analyze_progression",
            return_value={"flags": [], "observations": [], "weekly_summary": None},
        ),
        patch("bot.services.checkin_service.update_active_flags"),
        patch("bot.services.checkin_service.append_context"),
        patch(
            "bot.services.checkin_service.generate_plan",
            new=AsyncMock(return_value=dict(plan_result) if plan_result else None),
        ),
    ]
    return stack


@pytest.mark.asyncio
async def test_checkin_persists_rationale_on_success():
    from bot.services import checkin_service

    with patch("bot.services.checkin_service.append_log_entry") as mock_append, \
         patch("bot.services.checkin_service.load_profile", return_value=_fake_profile()), \
         patch("bot.services.checkin_service.load_training_model", return_value={"baseline_snapshot": {}}), \
         patch("bot.services.checkin_service.get_daily_entries", return_value=[]), \
         patch("bot.services.checkin_service.update_training_model_partial"), \
         patch("bot.services.checkin_service.get_or_refresh_baseline", return_value=_baseline()), \
         patch("bot.services.checkin_service.triage", return_value=dict(BASE_TRIAGE)), \
         patch("bot.services.checkin_service.analyze_progression",
               return_value={"flags": [], "observations": [], "weekly_summary": None}), \
         patch("bot.services.checkin_service.update_active_flags"), \
         patch("bot.services.checkin_service.append_context"), \
         patch("bot.services.checkin_service.generate_plan",
               new=AsyncMock(return_value=dict(BASE_PLAN))):
        await checkin_service.process_checkin(
            pitcher_id="x", arm_feel=7, sleep_hours=7.5, energy=7,
        )

    # Final append_log_entry call should carry the full entry with rationale
    final_entry = mock_append.call_args_list[-1][0][1]
    assert "rationale" in final_entry
    assert final_entry["rationale"] is not None
    assert "rationale_short" in final_entry["rationale"]
    assert final_entry["rationale"]["rationale_short"] == "All systems good."


@pytest.mark.asyncio
async def test_checkin_completes_when_rationale_raises():
    """Rationale generation failure is non-fatal."""
    from bot.services import checkin_service

    with patch("bot.services.checkin_service.append_log_entry") as mock_append, \
         patch("bot.services.checkin_service.load_profile", return_value=_fake_profile()), \
         patch("bot.services.checkin_service.load_training_model", return_value={"baseline_snapshot": {}}), \
         patch("bot.services.checkin_service.get_daily_entries", return_value=[]), \
         patch("bot.services.checkin_service.update_training_model_partial"), \
         patch("bot.services.checkin_service.get_or_refresh_baseline", return_value=_baseline()), \
         patch("bot.services.checkin_service.triage", return_value=dict(BASE_TRIAGE)), \
         patch("bot.services.checkin_service.analyze_progression",
               return_value={"flags": [], "observations": [], "weekly_summary": None}), \
         patch("bot.services.checkin_service.update_active_flags"), \
         patch("bot.services.checkin_service.append_context"), \
         patch("bot.services.checkin_service.generate_plan",
               new=AsyncMock(return_value=dict(BASE_PLAN))), \
         patch("bot.services.checkin_service.generate_triage_rationale",
               side_effect=RuntimeError("boom")):
        # Should NOT raise
        await checkin_service.process_checkin(
            pitcher_id="x", arm_feel=7, sleep_hours=7.0, energy=7,
        )

    final_entry = mock_append.call_args_list[-1][0][1]
    # rationale is either None or a dict with a None rationale_short
    assert (
        final_entry.get("rationale") is None
        or final_entry["rationale"].get("rationale_short") is None
    )


@pytest.mark.asyncio
async def test_kill_switch_disables_rationale(monkeypatch):
    monkeypatch.setenv("RATIONALE_ENABLED", "false")
    # Reimport to pick up env
    import importlib
    from bot.services import checkin_service
    importlib.reload(checkin_service)

    try:
        with patch("bot.services.checkin_service.append_log_entry") as mock_append, \
             patch("bot.services.checkin_service.load_profile", return_value=_fake_profile()), \
             patch("bot.services.checkin_service.load_training_model",
                   return_value={"baseline_snapshot": {}}), \
             patch("bot.services.checkin_service.get_daily_entries", return_value=[]), \
             patch("bot.services.checkin_service.update_training_model_partial"), \
             patch("bot.services.checkin_service.get_or_refresh_baseline",
                   return_value=_baseline()), \
             patch("bot.services.checkin_service.triage", return_value=dict(BASE_TRIAGE)), \
             patch("bot.services.checkin_service.analyze_progression",
                   return_value={"flags": [], "observations": [], "weekly_summary": None}), \
             patch("bot.services.checkin_service.update_active_flags"), \
             patch("bot.services.checkin_service.append_context"), \
             patch("bot.services.checkin_service.generate_plan",
                   new=AsyncMock(return_value=dict(BASE_PLAN))):
            await checkin_service.process_checkin(
                pitcher_id="x", arm_feel=7, sleep_hours=7.5, energy=7,
            )

        final_entry = mock_append.call_args_list[-1][0][1]
        assert final_entry.get("rationale") is None
    finally:
        # Reset env + reload to leave module clean for other tests
        monkeypatch.delenv("RATIONALE_ENABLED", raising=False)
        importlib.reload(checkin_service)


@pytest.mark.asyncio
async def test_per_exercise_rationale_attached_when_constraints_present():
    from bot.services import checkin_service

    triage_yellow = {
        **BASE_TRIAGE,
        "flag_level": "yellow",
        "modifications": ["maintain_compounds_reduced"],
        "category_scores": {"tissue": 5.2, "load": 7, "recovery": 7},
    }
    plan_with_mods = {
        **BASE_PLAN,
        "modifications_applied": ["maintain_compounds_reduced"],
    }

    with patch("bot.services.checkin_service.append_log_entry") as mock_append, \
         patch("bot.services.checkin_service.load_profile", return_value=_fake_profile()), \
         patch("bot.services.checkin_service.load_training_model", return_value={"baseline_snapshot": {}}), \
         patch("bot.services.checkin_service.get_daily_entries", return_value=[]), \
         patch("bot.services.checkin_service.update_training_model_partial"), \
         patch("bot.services.checkin_service.get_or_refresh_baseline", return_value=_baseline()), \
         patch("bot.services.checkin_service.triage", return_value=triage_yellow), \
         patch("bot.services.checkin_service.analyze_progression",
               return_value={"flags": [], "observations": [], "weekly_summary": None}), \
         patch("bot.services.checkin_service.update_active_flags"), \
         patch("bot.services.checkin_service.append_context"), \
         patch("bot.services.checkin_service.generate_plan",
               new=AsyncMock(return_value=plan_with_mods)):
        await checkin_service.process_checkin(
            pitcher_id="x", arm_feel=5, sleep_hours=6.5, energy=5,
        )

    final_entry = mock_append.call_args_list[-1][0][1]
    # day_summary_rationale attached on plan_generated
    assert "day_summary_rationale" in final_entry["plan_generated"]
    assert final_entry["plan_generated"]["day_summary_rationale"] is not None
    # lifting.exercises[*].rationale attached
    exs = final_entry["lifting"]["exercises"]
    assert len(exs) >= 1
    # At least one exercise got a non-None rationale from the constraint
    assert any(e.get("rationale") for e in exs)
