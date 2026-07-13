"""Tests for bot.services.program_engine.content_invariants (Task 2.3)."""
from __future__ import annotations

import pytest

from bot.services.program_engine.content_invariants import (
    check_contraindications,
    check_equipment,
    check_exercise_ids_resolve,
)
from bot.services.program_engine.schemas import (
    Day,
    LiftingBlock,
    LiftingExercise,
    Phase,
    PitcherProgram,
    ProgressionState,
    Rationale,
)


def _make_lifting_program(*ex_specs) -> PitcherProgram:
    """`ex_specs` is a list of (ex_id, sets, reps, intensity) tuples."""
    exercises = [
        LiftingExercise(exercise_id=ex_id, sets=s, reps=r, intensity=i)
        for (ex_id, s, r, i) in ex_specs
    ]
    days = [Day(
        day_index=0,
        template_key="day_0",
        date="2026-06-01",
        lifting_blocks=[LiftingBlock(block_name="B", exercises=exercises)],
    )]
    return PitcherProgram(
        pitcher_id="p", goal="velocity", domain="unified",
        knowledge_version="testtest",
        generated_at="2026-06-01T12:00:00",
        target_date="2026-08-01", total_weeks=1, status="draft",
        phases=[Phase(phase_id="base", name="Base", week_count=1, intent_summary="x", phase_type="base")],
        days=days,
        rationale=Rationale(phase_logic="x", individualization_notes="x", cited_research_doc_ids=["x"]),
        progression_state=ProgressionState(),
    )


# ─────────── Equipment ───────────


def test_equipment_ok_when_required_available():
    program = _make_lifting_program(("ex_001", 3, "8", "80% 1RM"))
    rows = [{"id": "ex_001", "equipment": "trap_bar"}]
    assert check_equipment(program, rows, ["trap_bar", "DB"]) == []


def test_equipment_violation_when_missing():
    program = _make_lifting_program(("ex_001", 3, "8", "80% 1RM"))
    rows = [{"id": "ex_001", "equipment": "trap_bar"}]
    violations = check_equipment(program, rows, ["DB"])
    assert len(violations) == 1
    assert violations[0].kind == "equipment_unavailable"


def test_equipment_list_form_supported():
    program = _make_lifting_program(("ex_001", 3, "8", "80% 1RM"))
    rows = [{"id": "ex_001", "equipment": ["barbell", "rack"]}]
    # 'rack' missing → violation
    violations = check_equipment(program, rows, ["barbell"])
    assert any(v.actual == "rack" for v in violations)


def test_equipment_no_constraints_means_no_violations():
    program = _make_lifting_program(("ex_001", 3, "8", "80% 1RM"))
    rows = [{"id": "ex_001", "equipment": "trap_bar"}]
    assert check_equipment(program, rows, []) == []


def test_equipment_no_equipment_field_is_bodyweight():
    program = _make_lifting_program(("ex_022", 3, "8", "BW"))
    rows = [{"id": "ex_022"}]
    assert check_equipment(program, rows, []) == []


def test_equipment_dedupe_same_id_same_miss():
    """Same exercise on multiple days → single violation, not N."""
    exs = [LiftingExercise(exercise_id="ex_001", sets=3, reps="8", intensity="80% 1RM")]
    days = [
        Day(day_index=i, template_key=f"day_{i}", date=f"2026-06-{i+1:02d}",
            lifting_blocks=[LiftingBlock(block_name="B", exercises=exs)]) for i in range(7)
    ]
    program = PitcherProgram(
        pitcher_id="p", goal="velocity", domain="unified",
        knowledge_version="testtest", generated_at="2026-06-01T12:00:00",
        target_date="2026-08-01", total_weeks=1, status="draft",
        phases=[Phase(phase_id="b", name="B", week_count=1, intent_summary="x", phase_type="base")],
        days=days,
        rationale=Rationale(phase_logic="x", individualization_notes="x", cited_research_doc_ids=["x"]),
        progression_state=ProgressionState(),
    )
    rows = [{"id": "ex_001", "equipment": "trap_bar"}]
    violations = check_equipment(program, rows, ["DB"])
    assert len(violations) == 1


# ─────────── Contraindications ───────────


def test_contraindications_no_mods_means_no_violations():
    program = _make_lifting_program(("ex_041", 3, "10", "BW"))
    rows = [{"id": "ex_041", "contraindications": ["acute_medial_elbow_pain"]}]
    assert check_contraindications(program, rows, []) == []


def test_contraindications_violation_on_mod_match():
    program = _make_lifting_program(("ex_041", 3, "10", "BW"))
    rows = [{"id": "ex_041", "contraindications": ["acute_medial_elbow_pain"]}]
    violations = check_contraindications(program, rows, ["acute_medial_elbow_pain"])
    assert len(violations) == 1
    assert violations[0].kind == "contraindicated_exercise"


def test_contraindications_case_insensitive():
    program = _make_lifting_program(("ex_041", 3, "10", "BW"))
    rows = [{"id": "ex_041", "contraindications": ["ACUTE_MEDIAL_ELBOW_PAIN"]}]
    violations = check_contraindications(program, rows, ["acute_medial_elbow_pain"])
    assert len(violations) == 1


def test_contraindications_no_overlap_clean():
    program = _make_lifting_program(("ex_001", 3, "8", "80% 1RM"))
    rows = [{"id": "ex_001", "contraindications": ["knee_pain"]}]
    assert check_contraindications(program, rows, ["shoulder_impingement"]) == []


# ─────────── Exercise IDs ───────────


def test_exercise_ids_clean_when_index_matches():
    program = _make_lifting_program(("ex_001", 3, "8", "80% 1RM"))
    rows = [{"id": "ex_001", "name": "Trap Bar Deadlift"}]
    assert check_exercise_ids_resolve(program, rows) == []


def test_exercise_ids_violation_unknown_id():
    program = _make_lifting_program(("ex_999", 3, "8", "80% 1RM"))
    rows = [{"id": "ex_001", "name": "Trap Bar Deadlift"}]
    violations = check_exercise_ids_resolve(program, rows)
    assert len(violations) == 1
    v = violations[0]
    assert v.kind == "unknown_exercise_id"
    assert v.repair_hint is None  # FATAL


def test_exercise_ids_dedupe_same_id():
    """One unknown id used on N days → ONE violation."""
    exs = [LiftingExercise(exercise_id="ex_999", sets=3, reps="8", intensity="x")]
    days = [
        Day(day_index=i, template_key=f"d_{i}", date=f"2026-06-{i+1:02d}",
            lifting_blocks=[LiftingBlock(block_name="B", exercises=exs)]) for i in range(5)
    ]
    program = PitcherProgram(
        pitcher_id="p", goal="velocity", domain="unified",
        knowledge_version="testtest", generated_at="2026-06-01T12:00:00",
        target_date="2026-08-01", total_weeks=1, status="draft",
        phases=[Phase(phase_id="b", name="B", week_count=1, intent_summary="x", phase_type="base")],
        days=days,
        rationale=Rationale(phase_logic="x", individualization_notes="x", cited_research_doc_ids=["x"]),
        progression_state=ProgressionState(),
    )
    violations = check_exercise_ids_resolve(program, [{"id": "ex_001"}])
    assert len(violations) == 1


def test_exercise_ids_falls_back_to_alias_resolver_when_no_rows(monkeypatch):
    """Without an exercises_rows arg, use bot.services.exercise_alias.try_resolve_alias."""
    from bot.services import exercise_alias
    monkeypatch.setattr(
        exercise_alias, "get_exercises",
        lambda: [{"id": "ex_001", "name": "Foo", "aliases": []}],
    )
    exercise_alias.refresh_index()
    program = _make_lifting_program(("ex_999", 3, "8", "80% 1RM"))
    violations = check_exercise_ids_resolve(program, None)
    assert len(violations) == 1
    assert violations[0].kind == "unknown_exercise_id"
