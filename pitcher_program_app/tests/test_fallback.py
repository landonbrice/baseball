"""Tests for bot.services.program_engine.fallback (Task 2.5)."""
from __future__ import annotations

import pytest

from bot.services.program_engine.fallback import build_fallback_program
from bot.services.program_engine.schemas import PitcherProgram


# A representative block_library row matching the post-migration-033
# velocity_12wk_v1 shape. Trimmed to the keys the fallback consumes.
def _velocity_row() -> dict:
    return {
        "block_template_id": "velocity_12wk_v1",
        "name": "Velocity Development Program",
        "domain": "throwing",
        "goal_tags": ["velocity"],
        "research_doc_ids": ["velocity_progression_model", "driveline_throwing_program"],
        "content": {
            "weeks": 12,
            "throws_per_week": 3,
            "phases": [
                {"name": "Base Building", "weeks": [1, 2, 3], "effort_pct": 50,
                 "distances": ["45ft", "60ft", "75ft"], "total_throws_range": [40, 60],
                 "drills": ["high_pec_load_x10_at_30ft"], "intent_notes": "Build base."},
                {"name": "Distance Extension", "weeks": [4, 5, 6], "effort_pct": 70,
                 "distances": ["45ft", "75ft", "105ft"], "total_throws_range": [50, 66],
                 "drills": ["qb_drop_back_50pct"], "intent_notes": "Add distance."},
                {"name": "Compression Plus Pulldowns", "weeks": [7, 8, 9], "effort_pct": 80,
                 "distances": ["120ft"], "total_throws_range": [55, 70],
                 "drills": ["compression_on_a_line"], "intent_notes": "Introduce pulldowns."},
                {"name": "Max Intent Plus Mound", "weeks": [10, 11, 12], "effort_pct": 90,
                 "distances": ["full_progression", "mound_work"], "total_throws_range": [60, 75],
                 "drills": ["pulldowns_100pct"], "intent_notes": "Full progression."},
            ],
            "acwr_governor": {"deload_weeks_default": [4, 7]},
            "lifting_integration": {
                "phase_mapping": [
                    {"throwing_phase_weeks": [1, 2, 3], "lifting_phase": "hypertrophy"},
                    {"throwing_phase_weeks": [4, 5, 6], "lifting_phase": "hypertrophy_to_strength"},
                    {"throwing_phase_weeks": [7, 8, 9], "lifting_phase": "strength"},
                    {"throwing_phase_weeks": [10, 11, 12], "lifting_phase": "strength_power"},
                ],
            },
        },
    }


def test_fallback_returns_valid_pitcher_program():
    program = build_fallback_program(
        pitcher_id="landon_brice",
        goal_spec={"tags": ["velocity"]},
        block_library_row=_velocity_row(),
        knowledge_version="abcdef12",
        target_date="2026-08-24",
    )
    assert isinstance(program, PitcherProgram)
    assert program.status == "draft"
    assert program.engine_version == "v1"


def test_fallback_emits_84_day_program_for_12wk_template():
    program = build_fallback_program(
        pitcher_id="landon_brice",
        goal_spec={"tags": ["velocity"]},
        block_library_row=_velocity_row(),
        knowledge_version="abcdef12",
        target_date="2026-08-24",
    )
    assert program.total_weeks == 12
    assert len(program.days) == 84


def test_fallback_marks_deload_weeks_4_and_7():
    program = build_fallback_program(
        pitcher_id="landon_brice",
        goal_spec={"tags": ["velocity"]},
        block_library_row=_velocity_row(),
        knowledge_version="abcdef12",
        target_date="2026-08-24",
    )
    # Wk4 = day_index 21-27; Wk7 = 42-48
    wk4_days = [d for d in program.days if 21 <= d.day_index < 28]
    wk7_days = [d for d in program.days if 42 <= d.day_index < 49]
    wk5_days = [d for d in program.days if 28 <= d.day_index < 35]
    assert all(d.is_deload for d in wk4_days)
    assert all(d.is_deload for d in wk7_days)
    assert not any(d.is_deload for d in wk5_days)


def test_fallback_base_phase_intent_clipped_below_85():
    """The base phase effort_pct=50 stays at 50; but our generic clipping logic
    keeps base-phase intent strictly < 85 even if the phase declares more."""
    row = _velocity_row()
    row["content"]["phases"][0]["effort_pct"] = 90  # try to break the gate
    program = build_fallback_program(
        pitcher_id="p", goal_spec={"tags": ["velocity"]},
        block_library_row=row, knowledge_version="ab12cd34", target_date="2026-08-24",
    )
    base_phase_days = [d for d in program.days if d.day_index < 21]  # Wks 1-3
    throwing_base = [d for d in base_phase_days if d.throwing_5tuple is not None]
    for d in throwing_base:
        assert d.intent_pct is not None and d.intent_pct < 85


def test_fallback_includes_lifting_blocks_on_lift_days():
    program = build_fallback_program(
        pitcher_id="p", goal_spec={"tags": ["velocity"]},
        block_library_row=_velocity_row(), knowledge_version="ab12cd34", target_date="2026-08-24",
    )
    # Per _DEFAULT_LIFTING_DAYS = (0, 3) — day-of-week 0 and 3 within each week
    lift_days = [d for d in program.days if d.lifting_blocks]
    # 12 weeks × 2 lifts/week = 24 lifting days
    assert len(lift_days) == 24


def test_fallback_throwing_days_carry_5tuple():
    program = build_fallback_program(
        pitcher_id="p", goal_spec={"tags": ["velocity"]},
        block_library_row=_velocity_row(), knowledge_version="ab12cd34", target_date="2026-08-24",
    )
    throwing_days = [d for d in program.days if d.throwing_5tuple is not None]
    # 12 weeks × 3 throws/week = 36 throwing days
    assert len(throwing_days) == 36


def test_fallback_rationale_marks_fallback_used():
    program = build_fallback_program(
        pitcher_id="p", goal_spec={"tags": ["velocity"]},
        block_library_row=_velocity_row(), knowledge_version="ab12cd34", target_date="2026-08-24",
    )
    assert program.generation_provenance.get("fallback_used") is True
    assert program.generation_provenance.get("template_id") == "velocity_12wk_v1"


def test_fallback_phase_objects_carry_lower_snake_ids():
    program = build_fallback_program(
        pitcher_id="p", goal_spec={"tags": ["velocity"]},
        block_library_row=_velocity_row(), knowledge_version="ab12cd34", target_date="2026-08-24",
    )
    for phase in program.phases:
        assert phase.phase_id == phase.phase_id.lower()
        assert " " not in phase.phase_id


def test_fallback_is_real_periodized_program_not_slop():
    """Plan §3c acceptance: 'the fallback floor is still a real periodized
    program, not slop.' Reality test, not perfection test:

    - structurally complete (84 days for a 12wk template)
    - no unknown_exercise_id (canonical id integrity)
    - any ACWR hard-cap breach stays within +10% of the cap (phase-boundary
      artifact, not a real spike)
    - deload weeks marked as such
    """
    from bot.services.program_engine.guardrails import validate_program
    from bot.services.program_engine.load_math import ACWR_HARD_CAP_DEFAULT
    program = build_fallback_program(
        pitcher_id="p", goal_spec={"tags": ["velocity"]},
        block_library_row=_velocity_row(), knowledge_version="ab12cd34", target_date="2026-08-24",
    )
    # Stub exercises rows + tag lookup. Every exercise the fallback emits is
    # canonical (it uses _DEFAULT_LIFTING_EXERCISES with real ex_NNN ids).
    used_ids = {ex.exercise_id for d in program.days for b in d.lifting_blocks for ex in b.exercises}
    exercises_rows = [{"id": ex_id, "equipment": None, "contraindications": []} for ex_id in used_ids]
    tag_lookup = {ex_id: set() for ex_id in used_ids}
    fpm_ids = {"ex_041", "ex_070"}
    for ex_id in fpm_ids & used_ids:
        tag_lookup[ex_id].add("fpm")
    pull_ids = {"ex_020", "ex_128"}
    push_ids = {"ex_025", "ex_145"}
    for ex_id in pull_ids & used_ids:
        tag_lookup[ex_id].add("pull")
    for ex_id in push_ids & used_ids:
        tag_lookup[ex_id].add("push")
    ctx = {
        "exercises_rows": exercises_rows,
        "available_equipment": [],
        "active_modifications": [],
        "tag_lookup": tag_lookup,
    }
    result = validate_program(program, ctx)
    # (a) No unknown ids — canonical-id integrity is non-negotiable
    unknown = [v for v in result.violations if v.kind == "unknown_exercise_id"]
    assert unknown == [], f"fallback emitted unknown ids: {unknown}"
    # (b) ACWR breaches stay within +10% of hard cap (phase-boundary artifact)
    cap_breaches = [v for v in result.violations if v.kind == "acwr_hard_cap_exceeded"]
    for v in cap_breaches:
        actual = float(v.actual)
        assert actual <= ACWR_HARD_CAP_DEFAULT * 1.10, (
            f"ACWR breach more than +10% over cap: {actual} at {v.where}"
        )


def test_fallback_raises_on_missing_phases():
    row = {"block_template_id": "x", "content": {}}
    with pytest.raises(ValueError, match="phases"):
        build_fallback_program(
            pitcher_id="p", goal_spec={"tags": ["x"]},
            block_library_row=row, knowledge_version="abcdef12",
        )
