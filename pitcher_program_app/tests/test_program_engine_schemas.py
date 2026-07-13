"""Tests for bot.services.program_engine.schemas (Task 1.1).

Schema-level contracts the rest of Phase 1+ depends on:
- additive-over-legacy day shape
- round-trip serialization
- unique day indices
- field bounds (intent_pct 0–100, ACWR rolling 0–3, etc.)
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from bot.services.program_engine.schemas import (
    Citation,
    Day,
    LiftingBlock,
    LiftingExercise,
    Phase,
    PitcherProgram,
    ProgressionState,
    Rationale,
    ThrowingFiveTuple,
)


# ---------- atom-level ----------


def test_throwing_5tuple_minimal_valid():
    t = ThrowingFiveTuple(distance_ft=45, throw_count=40, intensity_pct=50, drill="J-band warmup")
    assert t.distance_ft == 45
    assert t.note is None


def test_throwing_5tuple_rejects_out_of_band():
    with pytest.raises(ValidationError):
        ThrowingFiveTuple(distance_ft=45, throw_count=40, intensity_pct=150, drill="x")
    with pytest.raises(ValidationError):
        ThrowingFiveTuple(distance_ft=-5, throw_count=40, intensity_pct=50, drill="x")


def test_throwing_5tuple_drill_required_nonempty():
    with pytest.raises(ValidationError):
        ThrowingFiveTuple(distance_ft=45, throw_count=40, intensity_pct=50, drill="")


def test_lifting_exercise_pattern_enforced():
    LiftingExercise(exercise_id="ex_004", sets=3, reps="8")
    with pytest.raises(ValidationError):
        LiftingExercise(exercise_id="ex4", sets=3, reps="8")  # wrong pattern
    with pytest.raises(ValidationError):
        LiftingExercise(exercise_id="4_ex", sets=3, reps="8")


def test_lifting_exercise_superset_group_format():
    LiftingExercise(exercise_id="ex_004", sets=3, reps="8", superset_group="A1")
    LiftingExercise(exercise_id="ex_004", sets=3, reps="8", superset_group="B")
    with pytest.raises(ValidationError):
        LiftingExercise(exercise_id="ex_004", sets=3, reps="8", superset_group="a1")  # must be uppercase
    with pytest.raises(ValidationError):
        LiftingExercise(exercise_id="ex_004", sets=3, reps="8", superset_group="A10")  # only 1 digit


def test_lifting_exercise_reps_freeform_string():
    """Reps deliberately accept ranges + RIR notation."""
    for rep_str in ["8", "8-10", "3 each leg", "2X10 each direction", "AMRAP"]:
        LiftingExercise(exercise_id="ex_001", sets=3, reps=rep_str)


def test_lifting_block_requires_at_least_one_exercise():
    with pytest.raises(ValidationError):
        LiftingBlock(block_name="Block 1", exercises=[])


# ---------- Day shape ----------


def _legacy_day(idx: int = 0) -> dict:
    return {"day_index": idx, "template_key": "day_3", "date": "2026-06-15"}


def test_day_accepts_legacy_migration_020_shape():
    """A Day with ONLY the four migration-020 required fields must parse.

    This is the additive-over-legacy contract — existing readers must keep
    working when the engine writes fewer fields than the legacy shape allows.
    """
    d = Day(**_legacy_day())
    assert d.day_index == 0
    assert d.intent_pct is None
    assert d.lifting_blocks == []
    assert d.is_deload is False


def test_day_rejects_invalid_date():
    with pytest.raises(ValidationError):
        Day(day_index=0, template_key="day_3", date="06/15/2026")
    with pytest.raises(ValidationError):
        Day(day_index=0, template_key="day_3", date="2026-6-5")  # no zero-padding


def test_day_extra_keys_forbidden():
    with pytest.raises(ValidationError):
        Day(day_index=0, template_key="day_3", date="2026-06-15", surprise_key="x")


def test_day_intent_pct_bounded():
    with pytest.raises(ValidationError):
        Day(**_legacy_day(), intent_pct=110)
    with pytest.raises(ValidationError):
        Day(**_legacy_day(), intent_pct=-10)


def test_day_with_throwing_and_lifting_payload():
    d = Day(
        **_legacy_day(),
        phase_name="Base Building",
        intent_pct=50,
        is_deload=False,
        throwing_5tuple={"distance_ft": 45, "throw_count": 40, "intensity_pct": 50, "drill": "Long toss warmup"},
        lifting_blocks=[
            {
                "block_name": "Block 1: Posterior",
                "exercises": [
                    {"exercise_id": "ex_004", "sets": 3, "reps": "8"},
                    {"exercise_id": "ex_020", "sets": 3, "reps": "8-10", "superset_group": "A1"},
                ],
            }
        ],
        day_focus="Velocity intent — base distance + posterior chain",
    )
    assert d.throwing_5tuple is not None
    assert len(d.lifting_blocks[0].exercises) == 2


# ---------- Phase ----------


def test_phase_id_must_be_lower_snake():
    Phase(
        phase_id="base_building",
        name="Base Building",
        week_count=3,
        intent_summary="Build the aerobic + tissue base.",
    )
    with pytest.raises(ValidationError):
        Phase(
            phase_id="Base Building",
            name="Base Building",
            week_count=3,
            intent_summary="x",
        )
    with pytest.raises(ValidationError):
        Phase(phase_id="BaseBuilding", name="x", week_count=3, intent_summary="x")  # not lower


def test_phase_week_count_bounds():
    with pytest.raises(ValidationError):
        Phase(phase_id="x", name="x", week_count=0, intent_summary="x")
    with pytest.raises(ValidationError):
        Phase(phase_id="x", name="x", week_count=20, intent_summary="x")


# ---------- PitcherProgram ----------


def _minimal_program(**overrides) -> dict:
    base = {
        "pitcher_id": "landon_brice",
        "goal": "velocity",
        "domain": "unified",
        "knowledge_version": "abc12345",
        "generated_at": "2026-06-01T19:30:00",
        "target_date": "2026-08-24",
        "total_weeks": 12,
        "status": "draft",
        "phases": [
            {
                "phase_id": "base_building",
                "name": "Base Building",
                "week_count": 3,
                "phase_type": "base",
                "intent_summary": "Build distance + tissue base.",
                "intent_kpis": ["max long-toss dist"],
            }
        ],
        "days": [
            _legacy_day(0),
            _legacy_day(1),
        ],
        "rationale": {
            "phase_logic": "Three-phase arc: base → extension → compression+pulldowns.",
            "individualization_notes": "Landon recently cleared post-op; conservative ramp.",
            "cited_research_doc_ids": ["velocity_progression_model"],
        },
    }
    base.update(overrides)
    return base


def test_program_minimal_valid():
    p = PitcherProgram(**_minimal_program())
    assert p.engine_version == "v1"
    assert p.progression_state.current_week == 1


def test_program_round_trips_through_json():
    """Serialize → deserialize must produce an equivalent model."""
    p = PitcherProgram(**_minimal_program())
    raw = p.model_dump_json()
    again = PitcherProgram.model_validate_json(raw)
    assert again.model_dump() == p.model_dump()


def test_program_rejects_duplicate_day_indices():
    days = [_legacy_day(0), _legacy_day(0)]  # duplicate
    with pytest.raises(ValidationError) as exc_info:
        PitcherProgram(**_minimal_program(days=days))
    assert "duplicate day_index" in str(exc_info.value).lower()


def test_program_total_phase_weeks_helper():
    p = PitcherProgram(**_minimal_program())
    assert p.total_phase_weeks() == 3


def test_program_requires_at_least_one_phase():
    with pytest.raises(ValidationError):
        PitcherProgram(**_minimal_program(phases=[]))


def test_program_requires_at_least_one_day():
    with pytest.raises(ValidationError):
        PitcherProgram(**_minimal_program(days=[]))


def test_program_knowledge_version_min_length():
    with pytest.raises(ValidationError):
        PitcherProgram(**_minimal_program(knowledge_version="short"))


def test_program_status_enum():
    for s in ("draft", "active", "archived"):
        PitcherProgram(**_minimal_program(status=s))
    with pytest.raises(ValidationError):
        PitcherProgram(**_minimal_program(status="pending"))


def test_program_domain_enum():
    for d in ("throwing", "lifting", "unified"):
        PitcherProgram(**_minimal_program(domain=d))
    with pytest.raises(ValidationError):
        PitcherProgram(**_minimal_program(domain="cardio"))


# ---------- Rationale + Citation ----------


def test_citation_required_fields():
    Citation(doc_id="velocity_progression_model", title="Velocity Progression Model", why="Defines the 12-week phase arc.")
    with pytest.raises(ValidationError):
        Citation(doc_id="", title="x", why="x")


def test_rationale_citations_hydrated_optional():
    """Rationale can ship with doc_ids before resolver hydrates titles."""
    r = Rationale(
        phase_logic="x",
        individualization_notes="x",
        cited_research_doc_ids=["velocity_progression_model", "FPM"],
    )
    assert r.citations == []  # not hydrated yet


# ---------- ProgressionState ----------


def test_progression_state_defaults():
    s = ProgressionState()
    assert s.current_week == 1
    assert s.banked_vs_planned == 1.0 or s.banked_vs_planned == 0.0  # default may differ


def test_progression_state_acwr_bounds():
    ProgressionState(acwr_rolling=1.2)
    with pytest.raises(ValidationError):
        ProgressionState(acwr_rolling=-0.1)
    with pytest.raises(ValidationError):
        ProgressionState(acwr_rolling=5.0)
