"""When team_scope reads team phase, it should prefer the per-domain
columns and fall back to training_phase only if the new columns are NULL."""

from unittest.mock import patch

import pytest

from bot.services import team_scope


def test_team_phase_prefers_per_domain():
    fake_team = {
        "team_id": "team_1",
        "training_phase": "in_season_active",
        "throwing_phase": "preseason",
        "lifting_phase":  "in_season_active",
    }
    with patch.object(team_scope, "_load_team", return_value=fake_team):
        assert team_scope.get_team_phase("team_1", domain="throwing") == "preseason"
        assert team_scope.get_team_phase("team_1", domain="lifting")  == "in_season_active"


def test_team_phase_falls_back_to_training_phase():
    fake_team = {
        "team_id": "team_1",
        "training_phase": "in_season_active",
        "throwing_phase": None,
        "lifting_phase":  None,
    }
    with patch.object(team_scope, "_load_team", return_value=fake_team):
        assert team_scope.get_team_phase("team_1", domain="throwing") == "in_season_active"
        assert team_scope.get_team_phase("team_1", domain="lifting")  == "in_season_active"


def test_team_phase_returns_none_when_team_missing():
    with patch.object(team_scope, "_load_team", return_value=None):
        assert team_scope.get_team_phase("nonexistent", domain="throwing") is None


def test_team_phase_rejects_unknown_domain():
    with pytest.raises(ValueError, match="domain"):
        team_scope.get_team_phase("team_1", domain="yoga")
