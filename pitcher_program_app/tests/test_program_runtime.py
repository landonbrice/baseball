"""Tests for program_runtime — phase precedence resolution.

Spec D6: per-domain phase precedence stack:
  active program implied_phase > coach per-pitcher override > team per-domain default
"""
from unittest.mock import patch

import pytest


def test_phase_precedence_active_program_wins():
    """When pitcher has an active program, its template's implied_phase wins."""
    from bot.services import program_runtime

    with patch.object(program_runtime, "_load_active_program", return_value={
        "program_id": "p1",
        "domain": "throwing",
        "parent_template_id": "tpl1",
    }), patch.object(program_runtime, "_load_template_implied_phase", return_value="return_to_mound"), \
         patch.object(program_runtime, "_load_pitcher_overrides", return_value={
             "coach_throwing_phase_override": "preseason"}), \
         patch.object(program_runtime, "_load_team_phase_for_pitcher", return_value="in_season_active"):
        assert program_runtime.get_effective_phase("landon_brice", "throwing") == "return_to_mound"


def test_phase_precedence_coach_override_wins_when_no_program():
    from bot.services import program_runtime

    with patch.object(program_runtime, "_load_active_program", return_value=None), \
         patch.object(program_runtime, "_load_pitcher_overrides", return_value={
             "coach_throwing_phase_override": "preseason"}), \
         patch.object(program_runtime, "_load_team_phase_for_pitcher", return_value="in_season_active"):
        assert program_runtime.get_effective_phase("landon_brice", "throwing") == "preseason"


def test_phase_precedence_falls_back_to_team_default():
    from bot.services import program_runtime

    with patch.object(program_runtime, "_load_active_program", return_value=None), \
         patch.object(program_runtime, "_load_pitcher_overrides", return_value={
             "coach_throwing_phase_override": None}), \
         patch.object(program_runtime, "_load_team_phase_for_pitcher", return_value="in_season_active"):
        assert program_runtime.get_effective_phase("landon_brice", "throwing") == "in_season_active"


def test_phase_returns_none_when_nothing_configured():
    from bot.services import program_runtime

    with patch.object(program_runtime, "_load_active_program", return_value=None), \
         patch.object(program_runtime, "_load_pitcher_overrides", return_value={}), \
         patch.object(program_runtime, "_load_team_phase_for_pitcher", return_value=None):
        assert program_runtime.get_effective_phase("landon_brice", "throwing") is None


def test_phase_active_program_without_implied_phase_falls_through_to_override():
    """Defensive: program exists but its template has no implied_phase set.
    Should fall through to the coach override rather than returning None."""
    from bot.services import program_runtime

    with patch.object(program_runtime, "_load_active_program", return_value={
        "program_id": "p1",
        "domain": "lifting",
        "parent_template_id": "tpl_no_implied_phase",
    }), patch.object(program_runtime, "_load_template_implied_phase", return_value=None), \
         patch.object(program_runtime, "_load_pitcher_overrides", return_value={
             "coach_lifting_phase_override": "off_season_strength"}), \
         patch.object(program_runtime, "_load_team_phase_for_pitcher", return_value="in_season_active"):
        assert program_runtime.get_effective_phase("landon_brice", "lifting") == "off_season_strength"


def test_phase_rejects_unknown_domain():
    from bot.services import program_runtime
    with pytest.raises(ValueError, match="domain"):
        program_runtime.get_effective_phase("landon_brice", "yoga")


from datetime import date


def test_get_active_program_day_returns_current_day_from_schedule():
    """current_day_index already reflects held days; the function just reads schedule[current_day_index]."""
    from bot.services import program_runtime
    program = {
        "program_id": "p1",
        "domain": "throwing",
        "start_date": "2026-04-01",
        "current_day_index": 30,
        "held_days_count": 0,
        "generated_schedule_json": {
            "days": [{"day_index": i, "session": {"focus": f"day-{i}"}} for i in range(60)]
        },
    }
    with patch.object(program_runtime, "_load_active_program", return_value=program):
        result = program_runtime.get_active_program_day("landon_brice", "throwing", date(2026, 5, 1))
        assert result is not None
        assert result["day_index"] == 30
        assert result["session"]["focus"] == "day-30"


def test_get_active_program_day_held_days_already_baked_into_index():
    """If pitcher has been held 3 days, current_day_index lags by 3. Read returns the lagged day."""
    from bot.services import program_runtime
    program = {
        "program_id": "p1",
        "domain": "throwing",
        "start_date": "2026-04-01",
        "current_day_index": 27,
        "held_days_count": 3,
        "generated_schedule_json": {
            "days": [{"day_index": i, "session": {"focus": f"day-{i}"}} for i in range(60)]
        },
    }
    with patch.object(program_runtime, "_load_active_program", return_value=program):
        result = program_runtime.get_active_program_day("landon_brice", "throwing", date(2026, 5, 1))
        assert result["day_index"] == 27
        assert result["session"]["focus"] == "day-27"


def test_get_active_program_day_returns_none_when_no_active_program():
    from bot.services import program_runtime
    with patch.object(program_runtime, "_load_active_program", return_value=None):
        assert program_runtime.get_active_program_day("nobody", "throwing", date(2026, 5, 1)) is None


def test_get_active_program_day_returns_none_past_end_of_schedule():
    """day_index past the schedule's last day returns None (program is done)."""
    from bot.services import program_runtime
    program = {
        "program_id": "p1",
        "domain": "throwing",
        "start_date": "2026-04-01",
        "current_day_index": 84,
        "held_days_count": 0,
        "generated_schedule_json": {
            "days": [{"day_index": i, "session": {"focus": f"day-{i}"}} for i in range(60)]
        },
    }
    with patch.object(program_runtime, "_load_active_program", return_value=program):
        assert program_runtime.get_active_program_day("landon_brice", "throwing", date(2026, 5, 1)) is None


def test_get_active_program_day_rejects_unknown_domain():
    from bot.services import program_runtime
    with pytest.raises(ValueError, match="domain"):
        program_runtime.get_active_program_day("landon_brice", "yoga", date(2026, 5, 1))


def test_get_active_program_day_handles_missing_schedule_gracefully():
    """Defensive: program exists but generated_schedule_json is empty/missing days."""
    from bot.services import program_runtime
    program = {
        "program_id": "p1",
        "domain": "throwing",
        "current_day_index": 0,
        "generated_schedule_json": {},
    }
    with patch.object(program_runtime, "_load_active_program", return_value=program):
        assert program_runtime.get_active_program_day("landon_brice", "throwing", date(2026, 5, 1)) is None
