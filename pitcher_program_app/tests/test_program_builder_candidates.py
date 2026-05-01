"""Tests for program_builder.match_candidates (Layer 1).

Spec Section 2 — Layer 1 Structured Inputs:
- Filter by domain
- Filter by effective_phase ∈ template.compatible_phases
- Filter by goal ∈ template.goal_tags
- Filter by duration ∈ template.duration_range_weeks
- Filter out templates incompatible with hard_constraints
- Return at most 3, ranked by best fit
- Zero matches blocks the form (returns [])
"""
from unittest.mock import patch
import pytest


def _tpl(tid, **overrides):
    base = {
        "block_template_id": tid,
        "name": tid,
        "domain": "throwing",
        "goal_tags": ["velocity"],
        "duration_range_weeks": "[8,12]",
        "compatible_phases": ["off_season", "preseason"],
        "tunable_parameters_schema": {},
        "implied_phase": "preseason",
        "research_doc_ids": [],
    }
    base.update(overrides)
    return base


def test_filter_by_domain():
    from bot.services import program_builder
    templates = [
        _tpl("t1", domain="throwing"),
        _tpl("t2", domain="lifting"),
    ]
    with patch.object(program_builder, "_load_all_templates", return_value=templates):
        result = program_builder.match_candidates({
            "domain": "throwing", "goal": "velocity", "duration_weeks": 12,
            "effective_phase": "preseason", "hard_constraints": [],
        })
    assert [t["block_template_id"] for t in result] == ["t1"]


def test_filter_by_phase():
    from bot.services import program_builder
    templates = [
        _tpl("t1", compatible_phases=["preseason"]),
        _tpl("t2", compatible_phases=["off_season"]),
    ]
    with patch.object(program_builder, "_load_all_templates", return_value=templates):
        result = program_builder.match_candidates({
            "domain": "throwing", "goal": "velocity", "duration_weeks": 12,
            "effective_phase": "preseason", "hard_constraints": [],
        })
    assert [t["block_template_id"] for t in result] == ["t1"]


def test_filter_by_goal():
    from bot.services import program_builder
    templates = [
        _tpl("t1", goal_tags=["velocity"]),
        _tpl("t2", goal_tags=["return_to_mound"]),
    ]
    with patch.object(program_builder, "_load_all_templates", return_value=templates):
        result = program_builder.match_candidates({
            "domain": "throwing", "goal": "return_to_mound", "duration_weeks": 8,
            "effective_phase": "preseason", "hard_constraints": [],
        })
    assert [t["block_template_id"] for t in result] == ["t2"]


def test_filter_by_duration_within_range():
    from bot.services import program_builder
    templates = [
        _tpl("t1", duration_range_weeks="[4,8]"),
        _tpl("t2", duration_range_weeks="[8,12]"),
    ]
    with patch.object(program_builder, "_load_all_templates", return_value=templates):
        result = program_builder.match_candidates({
            "domain": "throwing", "goal": "velocity", "duration_weeks": 6,
            "effective_phase": "preseason", "hard_constraints": [],
        })
    assert [t["block_template_id"] for t in result] == ["t1"]


def test_returns_at_most_three():
    from bot.services import program_builder
    templates = [_tpl(f"t{i}") for i in range(10)]
    with patch.object(program_builder, "_load_all_templates", return_value=templates):
        result = program_builder.match_candidates({
            "domain": "throwing", "goal": "velocity", "duration_weeks": 12,
            "effective_phase": "preseason", "hard_constraints": [],
        })
    assert len(result) <= 3


def test_zero_matches_returns_empty_list():
    from bot.services import program_builder
    templates = [_tpl("t1", domain="lifting")]
    with patch.object(program_builder, "_load_all_templates", return_value=templates):
        result = program_builder.match_candidates({
            "domain": "throwing", "goal": "velocity", "duration_weeks": 12,
            "effective_phase": "preseason", "hard_constraints": [],
        })
    assert result == []


def test_rejects_unknown_domain():
    from bot.services import program_builder
    with pytest.raises(ValueError, match="domain"):
        program_builder.match_candidates({
            "domain": "yoga", "goal": "x", "duration_weeks": 4,
            "effective_phase": "preseason", "hard_constraints": [],
        })


def test_constraint_envelope_validation_missing_keys():
    from bot.services import program_builder
    with pytest.raises(KeyError):
        program_builder.match_candidates({"domain": "throwing"})
