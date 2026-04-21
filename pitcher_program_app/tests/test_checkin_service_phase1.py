"""Integration tests for Phase 1 triage wiring into checkin_service.

These tests use unittest.mock to isolate the flow from Supabase and LLM calls,
verifying that recent history + baseline are assembled correctly and passed
to triage, and that the arm_clarification override has been removed.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _fake_profile(pitcher_id="test_001", role="starter", rotation_length=7):
    return {
        "pitcher_id": pitcher_id,
        "name": "Test Pitcher",
        "role": role,
        "rotation_length": rotation_length,
        "active_flags": {
            "days_since_outing": 3,
            "current_arm_feel": 7,
            "active_modifications": [],
            "grip_drop_reported": False,
        },
        "injury_history": [],
    }


def _fake_daily_entry(date, arm_feel, rotation_day):
    return {
        "date": date,
        "rotation_day": rotation_day,
        "pre_training": {"arm_feel": arm_feel, "overall_energy": 3, "sleep_hours": 7.0, "flag_level": "green"},
    }


@pytest.mark.asyncio
async def test_phase1_args_passed_to_triage():
    """Verify recent_arm_feel and pitcher_baseline get passed into triage()."""
    from bot.services import checkin_service

    triage_calls = []

    def fake_triage(*args, **kwargs):
        triage_calls.append(kwargs)
        return {
            "flag_level": "green", "modifications": [], "alerts": [],
            "protocol_adjustments": {
                "lifting_intensity_cap": None, "remove_exercises": [],
                "add_exercises": [], "arm_care_template": "light",
                "plyocare_allowed": True,
                "throwing_adjustments": {
                    "max_day_type": None, "skip_phases": [], "intensity_cap_pct": None,
                    "volume_modifier": 1.0, "override_to": None,
                },
            },
            "reasoning": "Test",
        }

    entries = [
        _fake_daily_entry("2026-04-10", 7, 1),
        _fake_daily_entry("2026-04-11", 8, 2),
        _fake_daily_entry("2026-04-12", 8, 3),
    ]

    with patch("bot.services.checkin_service.load_profile", return_value=_fake_profile()), \
         patch("bot.services.checkin_service.load_training_model", return_value={"baseline_snapshot": {}}), \
         patch("bot.services.checkin_service.get_daily_entries", return_value=entries), \
         patch("bot.services.checkin_service.update_training_model_partial"), \
         patch("bot.services.checkin_service.triage", side_effect=fake_triage), \
         patch("bot.services.checkin_service.analyze_progression", return_value={"flags": [], "observations": [], "weekly_summary": None}), \
         patch("bot.services.checkin_service.update_active_flags"), \
         patch("bot.services.checkin_service.append_log_entry"), \
         patch("bot.services.checkin_service.append_context"), \
         patch("bot.services.checkin_service.generate_plan", new_callable=AsyncMock, return_value=None):

        await checkin_service.process_checkin(
            pitcher_id="test_001", arm_feel=7, sleep_hours=7.0, energy=3,
        )

    assert len(triage_calls) == 1
    call_kwargs = triage_calls[0]
    assert "recent_arm_feel" in call_kwargs
    assert "pitcher_baseline" in call_kwargs
    assert "recent_history" in call_kwargs
    assert "arm_clarification" in call_kwargs
    assert call_kwargs["arm_clarification"] is None
    assert len(call_kwargs["recent_arm_feel"]) == 3


@pytest.mark.asyncio
async def test_arm_clarification_passed_not_post_processed():
    """Verify arm_clarification is passed to triage(), not applied as post-triage override."""
    from bot.services import checkin_service

    triage_calls = []
    def fake_triage(*args, **kwargs):
        triage_calls.append(kwargs)
        return {
            "flag_level": "red", "modifications": [], "alerts": [],
            "protocol_adjustments": {
                "lifting_intensity_cap": None, "remove_exercises": [],
                "add_exercises": [], "arm_care_template": "light",
                "plyocare_allowed": True,
                "throwing_adjustments": {
                    "max_day_type": None, "skip_phases": [], "intensity_cap_pct": None,
                    "volume_modifier": 1.0, "override_to": None,
                },
            },
            "reasoning": "Test",
        }

    with patch("bot.services.checkin_service.load_profile", return_value=_fake_profile()), \
         patch("bot.services.checkin_service.load_training_model", return_value={}), \
         patch("bot.services.checkin_service.get_daily_entries", return_value=[]), \
         patch("bot.services.checkin_service.update_training_model_partial"), \
         patch("bot.services.checkin_service.triage", side_effect=fake_triage), \
         patch("bot.services.checkin_service.analyze_progression", return_value={"flags": [], "observations": [], "weekly_summary": None}), \
         patch("bot.services.checkin_service.update_active_flags"), \
         patch("bot.services.checkin_service.append_log_entry"), \
         patch("bot.services.checkin_service.append_context"), \
         patch("bot.services.checkin_service.generate_plan", new_callable=AsyncMock, return_value=None):

        # With arm_clarification="expected_soreness" and arm_feel=4, OLD behavior
        # downgraded red->yellow post-hoc. NEW behavior: triage is just called with
        # arm_clarification and the flag_level from triage is returned as-is.
        result = await checkin_service.process_checkin(
            pitcher_id="test_001", arm_feel=4, sleep_hours=7.0, energy=3,
            arm_clarification="expected_soreness",
        )

    assert len(triage_calls) == 1
    assert triage_calls[0]["arm_clarification"] == "expected_soreness"
    # Flag should be whatever triage returned (no post-processing)
    assert result["flag_level"] == "red"
