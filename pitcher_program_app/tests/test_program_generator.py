"""Tests for program_generator.generate_program (Layer 3).

Validates:
- Happy path: template + tuned_spec → draft program persisted
- Hard invariants: every exercise referenced exists, no contraindicated for active injuries,
  intensity ramp monotonic where required, total duration matches chosen weeks,
  per-week volume within template caps
- Validation fail → retry with default tuning, log to program_generation_failures
- Second fail → return default-tuned scaffold, log, status='error'
"""
from datetime import date
from unittest.mock import patch, MagicMock

import pytest


def _starter_template():
    return {
        "block_template_id": "tpl_test",
        "name": "Test Throwing Block",
        "domain": "throwing",
        "duration_range_weeks": "[8,12]",
        "compatible_phases": ["preseason"],
        "tunable_parameters_schema": {},
        "implied_phase": "preseason",
        "week_scaffold_json": {
            "scaffold_kind": "calendar_relative_repeating_7day",
            "rotation_template_keys": [
                {"day_offset": 0, "template_key": "day_0"},
                {"day_offset": 1, "template_key": "day_1"},
                {"day_offset": 2, "template_key": "day_2"},
                {"day_offset": 3, "template_key": "day_3"},
                {"day_offset": 4, "template_key": "day_4"},
                {"day_offset": 5, "template_key": "day_5"},
                {"day_offset": 6, "template_key": "day_6"},
            ],
        },
    }


def test_generate_program_happy_path_persists_draft():
    from bot.services import program_generator
    template = _starter_template()
    fake_program_id = "prog-1"

    with patch.object(program_generator, "_load_template", return_value=template), \
         patch.object(program_generator, "_load_pitcher_profile", return_value={"pitcher_id": "landon_brice"}), \
         patch.object(program_generator, "_validate_schedule", return_value=[]), \
         patch.object(program_generator, "_persist_program", return_value=fake_program_id):
        result = program_generator.generate_program(
            pitcher_id="landon_brice",
            template_id="tpl_test",
            tuned_spec={"weeks": 12},
            constraint_envelope={"start_date": "2026-05-01"},
            session_id=None,
        )
    assert result["program_id"] == fake_program_id
    assert result["status"] == "draft"


def test_generate_program_validates_total_duration():
    from bot.services import program_generator
    template = _starter_template()

    with patch.object(program_generator, "_load_template", return_value=template), \
         patch.object(program_generator, "_load_pitcher_profile", return_value={"pitcher_id": "landon_brice"}), \
         patch.object(program_generator, "_persist_program", return_value="prog-1"), \
         patch.object(program_generator, "_record_failure") as record:
        # First validation fails, second (default-tuned) passes
        with patch.object(program_generator, "_validate_schedule",
                          side_effect=[["duration_mismatch"], []]):
            result = program_generator.generate_program(
                pitcher_id="landon_brice",
                template_id="tpl_test",
                tuned_spec={"weeks": 999},  # absurd, will fail validation
                constraint_envelope={"start_date": "2026-05-01"},
                session_id="sess-1",
            )
    assert result["status"] == "draft"
    assert record.called  # failure was logged


def test_generate_program_two_failures_returns_error_status():
    from bot.services import program_generator
    template = _starter_template()

    with patch.object(program_generator, "_load_template", return_value=template), \
         patch.object(program_generator, "_load_pitcher_profile", return_value={"pitcher_id": "landon_brice"}), \
         patch.object(program_generator, "_validate_schedule",
                      side_effect=[["fail1"], ["fail2"]]), \
         patch.object(program_generator, "_persist_program", return_value="prog-1"), \
         patch.object(program_generator, "_record_failure"):
        result = program_generator.generate_program(
            pitcher_id="landon_brice",
            template_id="tpl_test",
            tuned_spec={"weeks": 999},
            constraint_envelope={"start_date": "2026-05-01"},
            session_id="sess-1",
        )
    assert result["status"] == "error"


def test_generate_program_unknown_template_raises():
    from bot.services import program_generator
    with patch.object(program_generator, "_load_template", return_value=None):
        with pytest.raises(ValueError, match="template"):
            program_generator.generate_program(
                pitcher_id="landon_brice",
                template_id="nonexistent",
                tuned_spec={"weeks": 12},
                constraint_envelope={"start_date": "2026-05-01"},
                session_id=None,
            )


def test_validate_schedule_flags_duration_mismatch():
    from bot.services import program_generator
    schedule = {"days": [{"day_index": i} for i in range(50)]}
    failures = program_generator._validate_schedule(
        schedule=schedule,
        tuned_spec={"weeks": 12},  # 12 weeks should be 84 days
        template={"block_template_id": "tpl_test"},
        profile={},
    )
    assert "duration_mismatch" in failures


def test_validate_schedule_passes_correct_duration():
    from bot.services import program_generator
    schedule = {"days": [{"day_index": i} for i in range(84)]}
    failures = program_generator._validate_schedule(
        schedule=schedule,
        tuned_spec={"weeks": 12},
        template={"block_template_id": "tpl_test"},
        profile={},
    )
    assert "duration_mismatch" not in failures


def test_generated_schedule_has_correct_day_count():
    from bot.services import program_generator
    template = _starter_template()
    schedule = program_generator._build_schedule_from_scaffold(
        template=template,
        tuned_spec={"weeks": 8},
        start_date=date(2026, 5, 1),
    )
    assert len(schedule["days"]) == 56  # 8 weeks * 7 days


def test_generated_schedule_repeats_rotation():
    from bot.services import program_generator
    template = _starter_template()
    schedule = program_generator._build_schedule_from_scaffold(
        template=template,
        tuned_spec={"weeks": 8},
        start_date=date(2026, 5, 1),
    )
    # Day 0 → day_0, day 7 → day_0, day 14 → day_0
    assert schedule["days"][0]["template_key"] == "day_0"
    assert schedule["days"][7]["template_key"] == "day_0"
    assert schedule["days"][14]["template_key"] == "day_0"
    assert schedule["days"][3]["template_key"] == "day_3"
