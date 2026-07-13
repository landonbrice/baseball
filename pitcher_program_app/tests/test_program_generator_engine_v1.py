"""Tests for the PROGRAM_ENGINE_V1 flag routing in program_generator
(Task 3.2)."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from bot.services import program_generator


def _stub_template():
    return {
        "block_template_id": "velocity_12wk_v1",
        "domain": "throwing",
        "goal_tags": ["velocity"],
        "week_scaffold_json": {
            "scaffold_kind": "calendar_relative_repeating_7day",
            "rotation_template_keys": [{"template_key": "day_0"}, {"template_key": "day_1"}],
        },
    }


def test_flag_off_routes_to_legacy_path(monkeypatch):
    """Default PROGRAM_ENGINE_V1=False → legacy _build_schedule_from_scaffold runs.

    Asserts the legacy path is called by monkeypatching the engine entrypoint to
    a sentinel that should NOT be invoked.
    """
    sentinel_called = {"hit": False}

    def _sentinel(*a, **kw):
        sentinel_called["hit"] = True
        return {}

    monkeypatch.setattr(program_generator, "_generate_program_v1_engine", _sentinel)
    monkeypatch.setattr(program_generator, "_load_template", lambda tid: _stub_template())
    monkeypatch.setattr(program_generator, "_load_pitcher_profile", lambda pid: {})
    monkeypatch.setattr(program_generator, "_persist_program", lambda row: "prog_123")
    monkeypatch.setattr(program_generator, "_record_failure", lambda *a, **kw: None)

    # Make sure the flag is False
    monkeypatch.setattr("bot.services.program_engine.feature_flag.PROGRAM_ENGINE_V1", False)

    row = program_generator.generate_program(
        pitcher_id="landon_brice",
        template_id="velocity_12wk_v1",
        tuned_spec={"weeks": 12},
        constraint_envelope={"start_date": "2026-06-01"},
        session_id="sess1",
    )
    assert sentinel_called["hit"] is False
    assert row["program_id"] == "prog_123"
    assert row["generated_schedule_json"]["scaffold_kind"] == "calendar_relative_repeating_7day"


def test_flag_on_routes_to_engine_path(monkeypatch):
    """Flipping PROGRAM_ENGINE_V1=True routes through the engine entrypoint."""
    sentinel_called = {"hit": False}
    expected_row = {"program_id": "prog_engine_42", "engine_version": "v1"}

    def _sentinel(*a, **kw):
        sentinel_called["hit"] = True
        return expected_row

    monkeypatch.setattr(program_generator, "_generate_program_v1_engine", _sentinel)
    monkeypatch.setattr("bot.services.program_engine.feature_flag.PROGRAM_ENGINE_V1", True)

    row = program_generator.generate_program(
        pitcher_id="landon_brice",
        template_id="velocity_12wk_v1",
        tuned_spec={"weeks": 12},
        constraint_envelope={"start_date": "2026-06-01"},
        session_id="sess1",
    )
    assert sentinel_called["hit"] is True
    assert row is expected_row


def test_default_flag_value_is_false():
    """The shipped flag value must be False — explicit by design."""
    from bot.services.program_engine.feature_flag import PROGRAM_ENGINE_V1
    assert PROGRAM_ENGINE_V1 is False
