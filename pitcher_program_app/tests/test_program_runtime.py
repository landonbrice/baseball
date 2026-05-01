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
