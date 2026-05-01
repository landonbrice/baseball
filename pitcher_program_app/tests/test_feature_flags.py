"""Tests for db.get_feature_flag — per-pitcher feature flags from
pitcher_training_model.feature_flags JSONB."""

from unittest.mock import patch

from bot.services import db


def test_feature_flag_default_false():
    """Empty feature_flags dict returns False for any key."""
    with patch.object(db, "get_pitcher_training_model",
                      return_value={"feature_flags": {}}):
        assert db.get_feature_flag("landon_brice", "program_aware_plan_gen") is False


def test_feature_flag_explicit_true():
    with patch.object(db, "get_pitcher_training_model",
                      return_value={"feature_flags": {"program_aware_plan_gen": True}}):
        assert db.get_feature_flag("landon_brice", "program_aware_plan_gen") is True


def test_feature_flag_explicit_false():
    with patch.object(db, "get_pitcher_training_model",
                      return_value={"feature_flags": {"program_aware_plan_gen": False}}):
        assert db.get_feature_flag("landon_brice", "program_aware_plan_gen") is False


def test_feature_flag_missing_model_row_is_false():
    with patch.object(db, "get_pitcher_training_model", return_value=None):
        assert db.get_feature_flag("nonexistent", "program_aware_plan_gen") is False


def test_feature_flag_missing_flags_field_is_false():
    """Defensive: if the row exists but feature_flags is missing or None."""
    with patch.object(db, "get_pitcher_training_model",
                      return_value={"feature_flags": None}):
        assert db.get_feature_flag("landon_brice", "program_aware_plan_gen") is False

    with patch.object(db, "get_pitcher_training_model", return_value={}):
        assert db.get_feature_flag("landon_brice", "program_aware_plan_gen") is False
